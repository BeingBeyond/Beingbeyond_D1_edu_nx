"""
Example 4: Full D1 control demo with live RGB view.

This script:

  - Instantiates a high-level D1Robot wrapper (head + arm + hand + USB stereo RGB)
  - Starts a background thread to display RGB in real time
  - Commands several head/arm/hand poses in sequence
  - Uses wait_until_reached() to synchronize arm/head motions
  - Prints the current robot state (joint names, positions, velocities, hand q)

Press 'q' in the RGB window to stop the demo and release resources.
Use --headless for camera capture without a window, or --no-vision to skip it.

Use this example as a high-level integration demo to:
  - Validate that the arm, head, hand and camera all work together
  - Inspect the robot behavior from the camera's point of view
  - Use as a starting point for teleoperation or task-level applications.
"""
from __future__ import annotations

import argparse
import time
from typing import TYPE_CHECKING

from utils import deg_list_to_rad, rad_list_to_deg

if TYPE_CHECKING:
    from D1_robot import D1Robot


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm-dev", default="/dev/ttyACM0", help="Head/arm serial device")
    parser.add_argument("--arm-baud", type=int, default=1000000)
    parser.add_argument("--hand-type", choices=("left", "right"), default="right")
    parser.add_argument("--hand-can", default="can0", help="SocketCAN interface")
    parser.add_argument("--hand-baud", type=int, default=1000000)
    parser.add_argument(
        "--camera",
        default="/dev/v4l/by-id/usb-SunplusIT_Inc_SPCA2100_PC_Camera-video-index0",
        help="USB V4L2 camera device",
    )
    parser.add_argument("--urdf", help="Override the SDK's default URDF")
    parser.add_argument("--headless", action="store_true", help="Capture RGB without GUI windows")
    parser.add_argument("--no-vision", action="store_true", help="Run without opening the camera")
    return parser.parse_args(argv)


def print_state(robot: D1Robot):
    q_rad, dq_rad = robot.head_arm.get_positions_and_velocities()
    q_deg = rad_list_to_deg(q_rad)
    dq_deg = rad_list_to_deg(dq_rad)

    hand_q_norm = robot.hand.read_joint_pos()

    print("\n[Robot State]")
    print("Joint names: ", robot.head_arm.joint_names)
    print("HeadArm Pos (deg)  :", ["{:+5.2f}".format(v) for v in q_deg])
    print("HeadArm Vel (deg/s):", ["{:+5.2f}".format(v) for v in dq_deg])
    print("Hand normed pos    :", ["{:+5.2f}".format(v) for v in hand_q_norm])


def should_exit(robot: D1Robot) -> bool:
    if robot.vision_stop_requested():
        print("\nExit requested from RGB window.")
        return True
    return False


def interruptible_sleep(robot: D1Robot, duration_s: float, step_s: float = 0.05) -> bool:
    deadline = time.time() + duration_s
    while time.time() < deadline:
        if should_exit(robot):
            return True
        time.sleep(min(step_s, max(0.0, deadline - time.time())))
    return False


def main(argv=None) -> int:
    args = parse_args(argv)
    # Parse --help before loading the SDK or any camera dependencies.
    from D1_robot import D1Robot

    print("=== D1 Control Demo ===")
    print("\033[91mWARNING: Always keep the physical emergency stop button within reach.\033[0m")
    print("\033[91m         Press it immediately if the robot motion looks unsafe.\033[0m\n")

    from beingbeyond_d1_edu_sdk.urdf_path import get_default_urdf_path
    urdf = args.urdf or get_default_urdf_path()

    try:
        with D1Robot(
            urdf_path=urdf,
            arm_dev=args.arm_dev,
            arm_baud=args.arm_baud,
            hand_type=args.hand_type,
            hand_can=args.hand_can,
            hand_baud=args.hand_baud,
            vision_device=args.camera,
            enable_vision=not args.no_vision,
        ) as robot:
            vels_rad = deg_list_to_rad([30.0] * 8)
            accs_rad = deg_list_to_rad([30.0] * 8)
            robot.head_arm.set_profile(vels_rad, accs_rad)


            # Wait for camera startup before sending any posture commands.
            if not args.no_vision:
                robot.start_vision_thread(display=not args.headless)

            print_state(robot)
            if should_exit(robot):
                return 0

            # 1)
            head_q = deg_list_to_rad([0.0, 0.0])
            arm_q = deg_list_to_rad([0.0, -60.0, 60.0, 0.0, 0.0, 0.0])
            hand_q_norm = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            q = head_q + arm_q + hand_q_norm
            robot.set_q(q)
            print_state(robot)
            robot.head_arm.wait_until_reached(
                head_q + arm_q,
                pos_tol_deg=5.0,
                vel_tol_deg_s=5.0,
            )
            print_state(robot)
            if should_exit(robot):
                return 0

            # 2) First posture
            head_q = deg_list_to_rad([20.0, -50.0])
            arm_q = deg_list_to_rad([30.0,
                                     -50.0,
                                     40.0,
                                     30.0, 30.0, -30.0])
            hand_q_norm = [0.55, 0.4, 0.0, 0.6, 0.8, 1.0]
            q = head_q + arm_q + hand_q_norm
            robot.set_q(q)
            print_state(robot)
            robot.head_arm.wait_until_reached(
                head_q + arm_q,
                pos_tol_deg=5.0,
                vel_tol_deg_s=5.0,
            )
            print_state(robot)
            if should_exit(robot):
                return 0

            # 3) Second posture
            head_q = deg_list_to_rad([-25.0, 15.0])
            arm_q = deg_list_to_rad([30.0, -50.0, 30.0, 0.0, -30.0, 0.0])
            hand_q_norm = [0.0, 1.0, 0.0, 1.0, 1.0, 0.0]
            q = head_q + arm_q + hand_q_norm
            robot.set_q(q)
            if interruptible_sleep(robot, 3.0):
                return 0

            # 4) Third posture
            head_q = deg_list_to_rad([-30.0, -35.0])
            arm_q = deg_list_to_rad([-15.0, -50.0, 50.0, 90.0, 70.0, 10.0])
            hand_q_norm = [0.0, 0.0, 1.0, 1.0, 1.0, 1.0]
            q = head_q + arm_q + hand_q_norm
            robot.set_q(q)
            t2 = robot.head_arm.wait_until_reached(
                head_q + arm_q,
                pos_tol_deg=5.0,
                vel_tol_deg_s=5.0,
            )
            if t2 is not None:
                print(f"Reached third posture in {t2:.2f} s.")
            else:
                print("Third posture NOT reached (timeout or no progress).")

            # 5) Configure a motion profile
            print("\nSetting custom motion profile ...")
            vels_rad = deg_list_to_rad([90.0] * 8)
            accs_rad = deg_list_to_rad([90.0] * 8)
            robot.head_arm.set_profile(vels_rad, accs_rad)

            # 6) Back to a neutral posture
            head_q = deg_list_to_rad([20.0, -30.0])
            arm_q = deg_list_to_rad([0.0, -60.0, 60.0, 0.0, -30.0, 90.0])
            robot.hand.set_speed(speed=[1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
            hand_q_norm = [0.0, 0.0, 1.0, 1.0, 1.0, 1.0]
            q = head_q + arm_q + hand_q_norm
            robot.set_q(q)
            t_home = robot.head_arm.wait_until_reached(
                head_q + arm_q,
                pos_tol_deg=5.0,
                vel_tol_deg_s=5.0,
            )
            if t_home is not None:
                print(f"Reached neutral posture in {t_home:.2f} s.")
            else:
                print("Neutral posture NOT reached (timeout or no progress).")
            if interruptible_sleep(robot, 1.0):
                return 0

            if interruptible_sleep(robot, 1.0):
                return 0
            print("\nDemo finished, homing and releasing resources in `close()` ...")

    except KeyboardInterrupt:
        print("\nInterrupted by user (Ctrl+C).")
        return 130

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
