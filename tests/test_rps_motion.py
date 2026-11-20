"""Hardware-free checks for responsive capture and serialized game motions."""
import ast
from pathlib import Path
import os
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call

import numpy as np

EXAMPLES = Path(os.environ.get("D1_EXAMPLES_DIR", str(Path(__file__).resolve().parents[1] / "examples"))).resolve()
sys.path.insert(0, str(EXAMPLES))
from device_detection import device_operation, DeviceDetectionError


def load_helpers():
    tree = ast.parse((EXAMPLES / "10_rock_paper_scissors_real.py").read_text())
    names = {"RpsMotionWorker", "apply_real_hand_gesture_sequence", "build_real_hand_gesture_sequences"}
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module = ast.Module(body=[future] + [n for n in tree.body if getattr(n, "name", None) in names], type_ignores=[])
    namespace = dict(threading=threading, time=time, np=np, device_operation=device_operation,
                     apply_rps_head_arm_posture=Mock())
    exec(compile(ast.fix_missing_locations(module), "rps_helpers", "exec"), namespace)
    return namespace


class RpsMotionTests(unittest.TestCase):
    def setUp(self):
        self.ns = load_helpers()
        self.hand = Mock()
        self.idle = Mock(cfg=SimpleNamespace(enabled=False, trigger_after_s=2))
        self.gestures = self.ns["build_real_hand_gesture_sequences"](SimpleNamespace(open_value=0))
        self.worker = self.ns["RpsMotionWorker"](
            Mock(), self.hand, self.gestures, {}, Mock(), self.idle,
            {"head_arm": "/dev/mock-arm", "can_iface": "mock-can"}, clock=lambda: 10,
        )
        self.addCleanup(self.worker.close)

    def test_exact_clearance_sequences_and_delays(self):
        timer = Mock()
        timer.is_set.return_value = False
        timer.wait.return_value = False
        events = Mock()
        events.attach_mock(self.hand.set_joint_pos, "pose")
        events.attach_mock(timer.wait, "wait")
        for gesture in ("rock", "scissors", "paper"):
            self.ns["apply_real_hand_gesture_sequence"](
                self.hand, self.gestures[gesture], "mock-can", stop_event=timer)
        self.assertEqual(events.mock_calls, [
            call.pose([0.3, 0, 1, 1, 1, 1]), call.wait(0.8), call.pose([0.7, 1, 1, 1, 1, 1]),
            call.pose([0.7, 0, 1, 1, 1, 1]), call.wait(0.5),
            call.pose([0.7, 0, 0, 0, 1, 1]), call.wait(0.5),
            call.pose([1, 0.8, 0, 0, 1, 1]), call.pose([0] * 6)])

    def test_capture_can_continue_and_only_latest_request_runs(self):
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        self.addCleanup(release.set)
        # Zero delays isolate scheduling from pose timing, which is tested above.
        self.worker.gestures = {key: tuple((pose, 0) for pose, delay in seq)
                                for key, seq in self.gestures.items()}
        thread_ids = []
        poses = []
        def send(pose):
            thread_ids.append(threading.get_ident())
            poses.append(pose)
            if len(poses) == 1:
                entered.set()
                if not release.wait(2):
                    raise TimeoutError("test gate timed out")
            if len(poses) == 3:
                finished.set()
        self.hand.set_joint_pos.side_effect = send
        self.worker.request("rock")
        self.worker.start()
        self.assertTrue(entered.wait(2))
        camera, display = Mock(), Mock()
        # Main thread keeps processing frames while the worker is blocked in motion.
        for gesture in ("scissors", "rock", "scissors", "paper"):
            display(camera.read_view())
            self.worker.request(gesture)
        self.assertEqual(camera.read_view.call_count, 4)
        self.assertEqual(len(poses), 1)
        release.set()
        self.assertTrue(finished.wait(2))
        self.worker.close()
        self.worker.raise_if_failed()
        self.assertEqual(poses, [self.gestures["rock"][0][0].tolist(),
                                 self.gestures["rock"][1][0].tolist(), [0] * 6])
        self.assertEqual(set(thread_ids), {self.worker._thread.ident})

    def test_repeated_request_does_not_restart_sequence(self):
        self.worker.request("paper")
        self.worker._update()
        self.worker.request("paper")
        self.worker._update()
        self.hand.set_joint_pos.assert_called_once_with([0] * 6)
        self.worker.request(None)
        self.worker._update()
        self.worker.request("paper")
        self.worker._update()
        self.assertEqual(self.hand.set_joint_pos.call_count, 2)

    def test_close_interrupts_wait_and_joins_before_further_commands(self):
        entered = threading.Event()
        self.worker.gestures = {"rock": ((np.zeros(6), 60), (np.ones(6), 0))}
        self.hand.set_joint_pos.side_effect = lambda pose: entered.set()
        self.worker.request("rock")
        self.worker.start()
        self.assertTrue(entered.wait(2))
        self.worker.close()
        self.assertFalse(self.worker._thread.is_alive())
        self.hand.set_joint_pos.assert_called_once_with([0] * 6)

    def test_motion_failure_is_forwarded_with_device_and_stops_worker(self):
        failed = threading.Event()
        def send(pose):
            failed.set()
            raise OSError("CAN disconnected")
        self.hand.set_joint_pos.side_effect = send
        self.worker.request("paper")
        self.worker.start()
        self.assertTrue(failed.wait(2))
        self.worker._thread.join(2)
        self.assertFalse(self.worker._thread.is_alive())
        with self.assertRaisesRegex(DeviceDetectionError, "mock-can.*CAN disconnected"):
            self.worker.raise_if_failed()
        with self.assertRaises(DeviceDetectionError):
            self.worker.request("rock")
        self.hand.set_joint_pos.assert_called_once()

    def test_idle_runs_in_worker_after_inactivity(self):
        self.idle.cfg.enabled = True
        self.worker._inactive_since = 7
        self.worker._update()
        self.idle.update.assert_called_once_with(self.worker.head_arm, self.hand, 10)


if __name__ == "__main__":
    unittest.main()
