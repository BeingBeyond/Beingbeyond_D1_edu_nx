"""
Example 10: Rock-paper-scissors on the real DexHand.

Pipeline:
  USB stereo RGB camera -> MediaPipe right-hand landmarks -> dex-retargeting qpos
  -> classify human rock/paper/scissors from five finger bend thresholds
  -> command the real right DexHand to play the winning gesture.

This example moves the head + arm to an initial pose, then controls the
DexHand during the game. Keep the physical emergency stop button within reach.
Capture, recognition and OpenCV stay on the main thread; robot commands run
serially in a worker. Each clearance sequence finishes before the latest gesture
is applied; pending gestures do not accumulate. Press q to interrupt waits and exit.
"""


from d1_example_errors import (
    configuration_error,
    install_error_hook,
    report_error,
    require_display,
    target_warning,
)

if __name__ == "__main__":
    install_error_hook()

import random
import threading
import time
from dataclasses import dataclass, replace
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

from beingbeyond_d1_edu_sdk import HeadArmRobot
from beingbeyond_d1_edu_sdk.hand import DexHand
from beingbeyond_d1_edu_sdk.urdf_path import get_default_urdf_path

from vision import StereoRGBCamera
from utils import deg_list_to_rad
from device_detection import resolve_devices, device_operation


from rps_common import (
    FINGER_ORDER, SingleHandDetector, StableGesture, StereoCfg, draw_overlay,
    finger_bend_scores, infer_finger_indices, init_right_hand_retargeting,
    retarget_joint_pos, winning_gesture,
)


@dataclass(frozen=True)
class HeadArmCfg:
    dev: str = "auto"
    baudrate: int = 1_000_000
    q_init_deg: Tuple[float, ...] = (
        0.0, -15.0,
         20.0, -60.0, 50.0, 0.0, 40.0, 30.0,
    )
    wait_pos_tol_deg: float = 10.0
    wait_vel_tol_deg_s: float = 20.0
    wait_timeout_s: float = 3.0


@dataclass(frozen=True)
class HandCfg:
    hand_type: str = "right"
    can_iface: str = "auto"
    baudrate: int = 1_000_000
    speed: Tuple[float, ...] = (1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
    torque: Tuple[float, ...] = (1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
    open_value: float = 0.0


@dataclass(frozen=True)
class RpsArmCfg:
    enabled: bool = True
    wait: bool = False
    wait_pos_tol_deg: float = 8.0
    wait_vel_tol_deg_s: float = 15.0
    wait_timeout_s: float = 2.0


@dataclass(frozen=True)
class RpsCfg:
    show_scores: bool = False
    thumb_threshold: float = 0.45
    index_threshold: float = 0.45
    middle_threshold: float = 0.45
    ring_threshold: float = 0.35
    pinky_threshold: float = 0.30
    stable_frames: int = 3
    unknown_reset_frames: int = 2

    @property
    def thresholds(self) -> Dict[str, float]:
        return {
            "thumb": self.thumb_threshold,
            "index": self.index_threshold,
            "middle": self.middle_threshold,
            "ring": self.ring_threshold,
            "pinky": self.pinky_threshold,
        }


@dataclass(frozen=True)
class IdleCfg:
    enabled: bool = False
    trigger_after_s: float = 2.0
    dance_interval_s: float = 1.0
    dance_steps: int = 4
    thumbs_up_hold_s: float = 2.0
    wait_pos_tol_deg: float = 5.0
    wait_vel_tol_deg_s: float = 5.0
    wait_timeout_s: float = 3.0


def classify_rps(scores: Dict[str, float], thresholds: Dict[str, float]) -> str:
    bent = {finger: scores[finger] >= thresholds[finger] for finger in FINGER_ORDER}
    non_thumb = ("index", "middle", "ring", "pinky")
    bent_non_thumb_count = sum(1 for finger in non_thumb if bent[finger])
    index_open = scores["index"] < thresholds["index"] * 0.55
    middle_open = scores["middle"] < thresholds["middle"] * 0.55

    if bent_non_thumb_count == 0:
        return "paper"

    if (
        scores["index"] < thresholds["index"] * 0.95
        and scores["middle"] < thresholds["middle"] * 0.95
        and scores["ring"] < thresholds["ring"] * 1.25
        and scores["pinky"] < thresholds["pinky"] * 1.25
    ):
        return "paper"

    if (
        index_open
        and middle_open
        and bent["ring"]
        and bent["pinky"]
    ):
        return "scissors"

    if bent_non_thumb_count >= 3:
        return "rock"

    if (
        index_open
        and middle_open
        and (bent["ring"] or bent["pinky"])
        and scores["thumb"] >= thresholds["thumb"] * 0.8
    ):
        return "scissors"

    return "unknown"


def build_real_hand_gesture_sequences(cfg: HandCfg) -> Dict[str, Tuple[Tuple[np.ndarray, float], ...]]:
    open_value = float(cfg.open_value)

    return {
        "paper": ((np.full(6, open_value, dtype=np.float64), 0.0),),
        # DexHand order: thumb pitch, thumb yaw, index, middle, ring, pinky.
        # Close the four fingers before moving the thumb into the rock pose.
        "rock": (
            (np.asarray([0.3, 0.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float64), 0.8),
            (np.asarray([0.7, 1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float64), 0.0),
        ),
        # Clear the thumb before extending the index and middle fingers.
        "scissors": (
            (np.asarray([0.7, 0.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float64), 0.5),
            (np.asarray([0.7, 0.0, 0.0, 0.0, 1.0, 1.0], dtype=np.float64), 0.5),
            (np.asarray([1.0, 0.8, 0.0, 0.0, 1.0, 1.0], dtype=np.float64), 0.0),
        ),
    }


def apply_real_hand_gesture_sequence(hand: DexHand, sequence: Tuple[Tuple[np.ndarray, float], ...], can_iface="未指定 / unspecified", stop_event=None) -> None:
    for qpos, delay_s in sequence:
        if stop_event is not None and stop_event.is_set():
            return
        with device_operation('hand CAN', can_iface, 'set_joint_pos'):
            hand.set_joint_pos(np.clip(qpos, 0.0, 1.0).tolist())
        if delay_s > 0.0:
            if stop_event is None:
                time.sleep(delay_s)
            elif stop_event.wait(delay_s):
                return


def build_rps_head_arm_postures() -> Dict[str, Tuple[Tuple[float, ...], Tuple[float, ...]]]:
    return {
        "paper": (
            (0.0, -10.0),
            (20.0, -60.0, 50.0, 0.0, 40.0, 20.0),
        ),
        "rock": (
            (-5.0, -25.0),
            (25.0, -65.0, 60.0, 30.0, 45.0, -20.0),
        ),
        "scissors": (
            (5.0, -15.0),
            (30.0, -55.0, 45.0, 0.0, -20.0, 0.0),
        ),
    }


def apply_rps_head_arm_posture(
    head_arm: HeadArmRobot,
    gesture: str,
    postures: Dict[str, Tuple[Tuple[float, ...], Tuple[float, ...]]],
    cfg: RpsArmCfg,
    arm_dev="未指定 / unspecified",
) -> None:
    if not cfg.enabled:
        return

    posture = postures.get(gesture)
    if posture is None:
        return

    head_deg, arm_deg = posture
    head_arm_q = deg_list_to_rad(list(head_deg) + list(arm_deg))
    with device_operation('head_arm', arm_dev, 'set_positions'):
        head_arm.set_positions(head_arm_q)

    if cfg.wait:
        with device_operation('head_arm', arm_dev, 'wait_until_reached'):
            head_arm.wait_until_reached(
                head_arm_q,
                pos_tol_deg=cfg.wait_pos_tol_deg,
                vel_tol_deg_s=cfg.wait_vel_tol_deg_s,
                timeout_s=cfg.wait_timeout_s,
            )


def apply_posture(
    head_arm: HeadArmRobot,
    hand: DexHand,
    head_deg: Tuple[float, ...],
    arm_deg: Tuple[float, ...],
    hand_q_norm: Tuple[float, ...],
    wait: bool = False,
    idle_cfg: Optional[IdleCfg] = None,
    devices=None,
) -> Optional[float]:
    devices = devices or {}
    head_q = deg_list_to_rad(list(head_deg))
    arm_q = deg_list_to_rad(list(arm_deg))
    head_arm_q = head_q + arm_q

    with device_operation('head_arm', devices.get('head_arm', "未指定 / unspecified"), 'set_positions'):
        head_arm.set_positions(head_arm_q)
    with device_operation('hand CAN', devices.get('can_iface', "未指定 / unspecified"), 'set_joint_pos'):
        hand.set_joint_pos(list(hand_q_norm))

    if not wait:
        return None

    wait_cfg = idle_cfg or IdleCfg()
    with device_operation('head_arm', devices.get('head_arm', "未指定 / unspecified"), 'wait_until_reached'):
        return head_arm.wait_until_reached(
            head_arm_q,
            pos_tol_deg=wait_cfg.wait_pos_tol_deg,
            vel_tol_deg_s=wait_cfg.wait_vel_tol_deg_s,
            timeout_s=wait_cfg.wait_timeout_s,
        )


def apply_thumbs_up_idle_posture(head_arm: HeadArmRobot, hand: DexHand, idle_cfg: IdleCfg, devices=None) -> None:
    elapsed = apply_posture(
        head_arm,
        hand,
        head_deg=(0.0, 0.0),
        arm_deg=(20.0, -60.0, 50.0, 90.0, 70.0, 10.0),
        hand_q_norm=(0.0, 0.0, 1.0, 1.0, 1.0, 1.0),
        wait=True,
        idle_cfg=idle_cfg,
        devices=devices,
    )
    if elapsed is not None:
        print(f"Reached idle thumbs-up posture in {elapsed:.2f} s.")
    else:
        report_error(target_warning(), severity="warning")


class IdleMotion:
    def __init__(
        self,
        cfg: IdleCfg,
        ready_head_arm_deg: Tuple[float, ...],
        ready_hand_q_norm: Tuple[float, ...],
        devices=None,
    ):
        self.devices = devices or {}
        self.cfg = cfg
        self.ready_head_arm_deg = ready_head_arm_deg
        self.ready_hand_q_norm = ready_hand_q_norm
        self.mode: Optional[str] = None
        self.next_step_time = 0.0
        self.dance_index = 0
        self.dance_steps_done = 0
        self.completed = False

    def reset(self) -> None:
        self.mode = None
        self.next_step_time = 0.0
        self.dance_index = 0
        self.dance_steps_done = 0
        self.completed = False

    def _move_to_ready_posture(self, head_arm: HeadArmRobot, hand: DexHand) -> None:
        apply_posture(
            head_arm,
            hand,
            head_deg=self.ready_head_arm_deg[:2],
            arm_deg=self.ready_head_arm_deg[2:],
            hand_q_norm=self.ready_hand_q_norm,
            wait=True,
            idle_cfg=self.cfg,
            devices=self.devices,
        )
        self.completed = True
        print("Idle action finished. Back to rock-paper-scissors ready posture.")

    def update(self, head_arm: HeadArmRobot, hand: DexHand, now: float) -> Optional[str]:
        if self.completed:
            return None

        if self.mode is None:
            self.mode = random.choice(("dance", "thumbs_up"))
            self.next_step_time = 0.0
            self.dance_index = 0
            self.dance_steps_done = 0
            print(f"No active rock-paper-scissors gesture detected. Idle action: {self.mode}.")

        if self.mode == "thumbs_up":
            if self.next_step_time == 0.0:
                apply_thumbs_up_idle_posture(head_arm, hand, self.cfg, self.devices)
                self.next_step_time = now + self.cfg.thumbs_up_hold_s
            elif now >= self.next_step_time:
                self._move_to_ready_posture(head_arm, hand)
            return self.mode

        if now < self.next_step_time:
            return self.mode

        if self.dance_steps_done >= self.cfg.dance_steps:
            self._move_to_ready_posture(head_arm, hand)
            return self.mode

        dance_postures = (
            (
                (-25.0, 35.0),
                (30.0, -50.0, 30.0, 0.0, -30.0, 0.0),
                (0.0, 1.0, 0.0, 1.0, 1.0, 0.0),
            ),
            (
                (-25.0, -15.0),
                (30.0, -70.0, 60.0, 0.0, 30.0, 0.0),
                (0.0, 1.0, 0.0, 1.0, 1.0, 0.0),
            ),
        )
        head_deg, arm_deg, hand_q_norm = dance_postures[self.dance_index]
        apply_posture(head_arm, hand, head_deg, arm_deg, hand_q_norm, devices=self.devices)
        self.dance_index = (self.dance_index + 1) % len(dance_postures)
        self.dance_steps_done += 1
        self.next_step_time = now + self.cfg.dance_interval_s
        return self.mode


class RpsMotionWorker:
    """Own runtime robot commands; keep capture and OpenCV on the main thread.

    Finish each gesture's clearance sequence before taking the latest request.
    There is no command backlog. Shutdown alone interrupts a sequence's delays.
    """

    def __init__(self, head_arm, hand, gestures, postures, arm_cfg, idle_motion,
                 devices, clock=time.monotonic):
        self.head_arm = head_arm
        self.hand = hand
        self.gestures = gestures
        self.postures = postures
        self.arm_cfg = arm_cfg
        self.idle_motion = idle_motion
        self.devices = devices
        self.clock = clock
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._requested = None
        self._error = None
        self._last_gesture = None
        self._inactive_since = clock()
        self._thread = threading.Thread(target=self._run, name="rps-motion")

    def start(self):
        self._thread.start()

    def request(self, gesture):
        if gesture is not None and gesture not in self.gestures:
            raise ValueError("Unknown robot gesture: {}".format(gesture))
        self.raise_if_failed()
        with self._lock:
            self._requested = gesture

    def raise_if_failed(self):
        with self._lock:
            error = self._error
        if error is not None:
            raise error

    def close(self):
        self._stop.set()
        if self._thread.ident is not None:
            # Never close controllers while the worker may still be using them.
            self._thread.join()

    def _update(self):
        with self._lock:
            gesture = self._requested
        now = self.clock()
        if gesture is not None:
            self._inactive_since = now
            self.idle_motion.reset()
            if gesture != self._last_gesture:
                apply_rps_head_arm_posture(
                    self.head_arm, gesture, self.postures, self.arm_cfg,
                    arm_dev=self.devices["head_arm"],
                )
                if self._stop.is_set():
                    return
                apply_real_hand_gesture_sequence(
                    self.hand, self.gestures[gesture],
                    can_iface=self.devices["can_iface"], stop_event=self._stop,
                )
                self._last_gesture = gesture
                self._inactive_since = self.clock()
        else:
            self._last_gesture = None
            if (self.idle_motion.cfg.enabled
                    and now - self._inactive_since >= self.idle_motion.cfg.trigger_after_s):
                self.idle_motion.update(self.head_arm, self.hand, now)

    def _run(self):
        try:
            while not self._stop.is_set():
                self._update()
                self._stop.wait(0.01)
        except Exception as exc:
            with self._lock:
                self._error = exc
            self._stop.set()


def move_head_arm_to_initial_pose(head_arm: HeadArmRobot, cfg: HeadArmCfg) -> None:
    q_init_deg = list(cfg.q_init_deg)
    if len(q_init_deg) != 8:
        raise configuration_error("q_init_deg", len(q_init_deg), 8)

    q_init_rad = deg_list_to_rad(q_init_deg)
    print(f"\n[Step] Move head + arm to initial pose (deg): {q_init_deg}")
    head_arm.set_positions(q_init_rad)
    head_arm.wait_until_reached(
        q_init_rad,
        active_joint_indices=range(8),
        pos_tol_deg=cfg.wait_pos_tol_deg,
        vel_tol_deg_s=cfg.wait_vel_tol_deg_s,
        timeout_s=cfg.wait_timeout_s,
    )
    time.sleep(0.3)


def main() -> None:
    require_display()
    stereo_cfg = StereoCfg()
    head_arm_cfg = HeadArmCfg()
    hand_cfg = HandCfg()
    devices = resolve_devices(head_arm=head_arm_cfg.dev, can_iface=hand_cfg.can_iface,
                              camera=stereo_cfg.device, head_arm_baud=head_arm_cfg.baudrate,
                              check_ready=True, auto_can_up=True, hand_type=hand_cfg.hand_type, hand_baud=hand_cfg.baudrate)
    head_arm_cfg = replace(head_arm_cfg, dev=devices["head_arm"])
    hand_cfg = replace(hand_cfg, can_iface=devices["can_iface"])
    stereo_cfg = replace(stereo_cfg, device=devices["camera"])
    rps_arm_cfg = RpsArmCfg()
    rps_cfg = RpsCfg()
    idle_cfg = IdleCfg()

    print("\033[91m警告：本示例会控制真实 D1 头臂和灵巧手 / WARNING: This example controls real D1 head + arm and DexHand.\033[0m")
    print("\033[91mKeep the physical emergency stop button within reach.\033[0m\n")

    retargeting = init_right_hand_retargeting()
    detector = SingleHandDetector(hand_type="Right", selfie=False)
    finger_indices = infer_finger_indices(retargeting.joint_names)
    robot_gestures = build_real_hand_gesture_sequences(hand_cfg)
    rps_head_arm_postures = build_rps_head_arm_postures()

    print(f"Retargeting output joints: {retargeting.joint_names}")
    print(f"Finger qpos indices: {finger_indices}")
    print(f"Finger thresholds: {rps_cfg.thresholds}")

    head_arm = None
    right_hand = None
    motion_worker = None
    try:
        with device_operation('head_arm', head_arm_cfg.dev, 'controller initialization'):
            head_arm = HeadArmRobot(
                urdf_path=get_default_urdf_path(),
                dev=head_arm_cfg.dev,
                baudrate=head_arm_cfg.baudrate,
                return_delay=0,
            )
        with device_operation('head_arm', head_arm_cfg.dev, 'motion/readback'):
            move_head_arm_to_initial_pose(head_arm, head_arm_cfg)

        with device_operation('hand CAN', hand_cfg.can_iface, 'controller initialization'):
            right_hand = DexHand(hand_type=hand_cfg.hand_type, can_iface=hand_cfg.can_iface, baudrate=hand_cfg.baudrate)
        with device_operation('hand CAN', hand_cfg.can_iface, 'set_speed'):
            right_hand.set_speed(speed=list(hand_cfg.speed))
        with device_operation('hand CAN', hand_cfg.can_iface, 'set_torque'):
            right_hand.set_torque(torque=list(hand_cfg.torque))
        with device_operation('hand CAN', hand_cfg.can_iface, 'open_hand'):
            right_hand.open_hand()
        time.sleep(0.2)

        window_name = "D1 Rock-Paper-Scissors Real"
        last_time = time.time()
        fps = 0.0
        stable = StableGesture()
        idle_motion = IdleMotion(
            idle_cfg,
            ready_head_arm_deg=head_arm_cfg.q_init_deg,
            ready_hand_q_norm=(hand_cfg.open_value,) * 6,
            devices=devices,
        )

        motion_worker = RpsMotionWorker(
            head_arm, right_hand, robot_gestures, rps_head_arm_postures,
            rps_arm_cfg, idle_motion, devices,
        )

        print("Starting real DexHand rock-paper-scissors. Press q in the OpenCV window to exit.")
        with StereoRGBCamera(
            device=stereo_cfg.device,
            single_width=stereo_cfg.single_width,
            single_height=stereo_cfg.single_height,
            fps=stereo_cfg.fps,
            fourcc=stereo_cfg.fourcc,
            swap_lr=stereo_cfg.swap_lr,
            view=stereo_cfg.view,
        ) as camera:
            motion_worker.start()
            while True:
                motion_worker.raise_if_failed()
                now = time.time()
                dt = now - last_time
                last_time = now
                if dt > 0:
                    fps = 0.9 * fps + 0.1 * (1.0 / dt) if fps > 0 else 1.0 / dt

                try:
                    bgr_view = camera.read_view()
                except RuntimeError as exc:
                    report_error(exc)
                    break

                rgb = cv2.cvtColor(bgr_view, cv2.COLOR_BGR2RGB)
                _, joint_pos, _, _ = detector.detect(rgb)

                previous = stable.last_stable
                raw = "unknown"
                scores = None
                if joint_pos is not None:
                    qpos = retarget_joint_pos(retargeting, joint_pos)
                    scores = finger_bend_scores(qpos, finger_indices)
                    raw = classify_rps(scores, rps_cfg.thresholds)

                human_stable = stable.update(raw, rps_cfg.stable_frames, rps_cfg.unknown_reset_frames)
                robot_gesture = winning_gesture(human_stable) if joint_pos is not None else None
                if human_stable != previous:
                    print(f"Human: {human_stable} | D1: {robot_gesture or '-'}")
                motion_worker.request(robot_gesture)

                overlay = draw_overlay(
                    bgr_view,
                    camera=camera,
                    fps=fps,
                    human=human_stable,
                    robot=robot_gesture,
                    scores=scores if rps_cfg.show_scores else None,
                    thresholds=rps_cfg.thresholds,
                )
                with device_operation("display", "OpenCV", "visualization"):
                    cv2.imshow(window_name, overlay)
                    key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break


    except KeyboardInterrupt:
        pass
    finally:
        if motion_worker is not None:
            motion_worker.close()
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
        try:
            if right_hand is not None:
                with device_operation('hand CAN', hand_cfg.can_iface, 'open_hand'):
                    right_hand.open_hand()
                time.sleep(0.2)
        except Exception as exc:
            report_error(exc, role="hand CAN", device=hand_cfg.can_iface, stage="open_hand")
        try:
            if right_hand is not None:
                with device_operation('hand CAN', hand_cfg.can_iface, 'close_can'):
                    right_hand.close_can()
        except Exception as exc:
            report_error(exc, role="hand CAN", device=hand_cfg.can_iface, stage="close_can")
        try:
            if head_arm is not None:
                head_arm.home_and_close()
        except Exception as exc:
            report_error(exc, role="head_arm", device=head_arm_cfg.dev, stage="home_and_close")


if __name__ == "__main__":
    main()
