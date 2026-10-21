#!/usr/bin/env python3
"""Exercise installed SDK numerical IK only; never creates robot hardware objects."""

import numpy as np
import pinocchio as pin

from beingbeyond_d1_edu_sdk.pin_kinematics import D1Kinematics, IKOptions


def main():
    kin = D1Kinematics()
    q_head = np.zeros(2)
    q_arm = np.deg2rad([0.0, -60.0, 60.0, 0.0, 0.0, 0.0])
    target_arm = q_arm + np.deg2rad([0.5, -0.25, 0.25, 0.25, -0.25, 0.25])
    target = kin.ee_in_base(q_head, target_arm)
    initial = kin.ee_in_base(q_head, q_arm)
    error_before = float(np.linalg.norm(pin.log6(pin.SE3(target).actInv(pin.SE3(initial))).vector))
    head_out, arm_out, error_reported, iterations = kin.ik_T_ee_with_arm_only(
        target, q_head, q_arm, options=IKOptions()
    )
    result = kin.ee_in_base(head_out, arm_out)
    error_after = float(np.linalg.norm(pin.log6(pin.SE3(target).actInv(pin.SE3(result))).vector))
    if not (np.isfinite(arm_out).all() and np.allclose(head_out, q_head, atol=1e-12)):
        raise ValueError("IK produced non-finite arm joints or changed the fixed head joints")
    if not (iterations == 1 and error_before > 1e-4 and error_after < error_before * 0.2):
        raise ValueError("IK did not sufficiently reduce error: {} -> {} ({} iterations)".format(
            error_before, error_after, iterations))
    if not np.isclose(error_reported, error_after, atol=1e-8, rtol=1e-5):
        raise ValueError("SDK-reported IK error does not match independently recomputed FK")
    print("PASS IK: nq={} error {:.12g} -> {:.12g}; fixed head unchanged".format(
        kin.nq, error_before, error_after))


if __name__ == "__main__":
    main()
