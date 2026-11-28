"""Camera and hand-tracking helpers for the two rock-paper-scissors examples."""
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

from d1_example_errors import missing_joints_error

EXAMPLES_DIR = Path(__file__).resolve().parent
D1_EDU_DIR = EXAMPLES_DIR.parent
DEX_RETARGETING_DIR = D1_EDU_DIR / "lib" / "dex-retargeting"
DEX_VECTOR_EXAMPLE_DIR = DEX_RETARGETING_DIR / "example" / "vector_retargeting"

sys.path.append(str(DEX_RETARGETING_DIR))
sys.path.append(str(DEX_VECTOR_EXAMPLE_DIR))

from dex_retargeting.constants import RobotName, RetargetingType, HandType, get_default_config_path
from dex_retargeting.retargeting_config import RetargetingConfig
from single_hand_detector import SingleHandDetector


FINGER_ORDER = ("thumb", "index", "middle", "ring", "pinky")


@dataclass(frozen=True)
class StereoCfg:
    device: str = "auto"
    single_width: int = 640
    single_height: int = 480
    fps: int = 30
    fourcc: str = "MJPG"
    swap_lr: bool = False
    view: str = "both"


@dataclass
class StableGesture:
    last_raw: str = "unknown"
    last_stable: str = "unknown"
    count: int = 0
    unknown_count: int = 0

    def update(self, raw: str, stable_frames: int, unknown_reset_frames: int) -> str:
        if raw == self.last_raw:
            self.count += 1
        else:
            self.last_raw = raw
            self.count = 1

        if raw == "unknown":
            self.unknown_count += 1
            if self.unknown_count >= unknown_reset_frames:
                self.last_stable = "unknown"
            return self.last_stable

        self.unknown_count = 0
        if self.count >= stable_frames:
            self.last_stable = raw
        return self.last_stable


def init_right_hand_retargeting():
    robot_name = RobotName.d1hand

    dex_pkg = importlib.util.find_spec("dex_retargeting")
    if dex_pkg and dex_pkg.origin:
        robot_dir = Path(dex_pkg.origin).absolute().parent.parent / "assets" / "robots" / "hands"
    else:
        robot_dir = DEX_RETARGETING_DIR / "assets" / "robots" / "hands"
    RetargetingConfig.set_default_urdf_dir(str(robot_dir))

    config_path = get_default_config_path(robot_name, RetargetingType.dexpilot, HandType.right)
    return RetargetingConfig.load_from_file(config_path).build()


def retarget_joint_pos(retargeting, joint_pos: np.ndarray) -> np.ndarray:
    retargeting_type = retargeting.optimizer.retargeting_type
    indices = retargeting.optimizer.target_link_human_indices

    if retargeting_type == "POSITION":
        ref_value = joint_pos[indices, :]
    else:
        origin_indices = indices[0, :]
        task_indices = indices[1, :]
        ref_value = joint_pos[task_indices, :] - joint_pos[origin_indices, :]

    return retargeting.retarget(ref_value)


def infer_finger_indices(joint_names) -> Dict[str, Tuple[int, ...]]:
    aliases = {
        "thumb": ("thumb",),
        "index": ("index",),
        "middle": ("middle",),
        "ring": ("ring",),
        "pinky": ("pinky", "little"),
    }
    indices = {finger: [] for finger in FINGER_ORDER}
    for i, name in enumerate(joint_names):
        lname = name.lower()
        for finger, keys in aliases.items():
            if any(key in lname for key in keys):
                indices[finger].append(i)

    missing = [finger for finger, values in indices.items() if not values]
    if missing:
        raise missing_joints_error(missing)
    return {finger: tuple(values) for finger, values in indices.items()}


def finger_bend_scores(qpos: np.ndarray, finger_indices: Dict[str, Tuple[int, ...]]) -> Dict[str, float]:
    scores = {}
    for finger, indices in finger_indices.items():
        values = np.abs(qpos[list(indices)])
        scores[finger] = float(np.max(values))
    return scores


def winning_gesture(human_gesture: str) -> Optional[str]:
    return {
        "rock": "paper",
        "paper": "scissors",
        "scissors": "rock",
    }.get(human_gesture)


def draw_overlay(
    image: np.ndarray,
    fps: float,
    camera,
    human: str,
    robot: Optional[str],
    scores: Optional[Dict[str, float]],
    thresholds: Dict[str, float],
) -> np.ndarray:
    out = image.copy()
    lines = [
        f"FPS: {fps:.1f} | {camera.device} | {camera.view}",
        f"Human: {human.upper()}",
        f"D1: {robot.upper() if robot else '-'}",
    ]
    if scores is not None:
        score_text = " ".join(
            f"{finger[0]}:{scores[finger]:.2f}/{thresholds[finger]:.2f}"
            for finger in FINGER_ORDER
        )
        lines.append(score_text)
    lines.append("q: quit")

    for i, line in enumerate(lines):
        y = 28 + i * 26
        cv2.putText(out, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(out, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1, cv2.LINE_AA)
    return out
