# Apple Vision Pro teleoperation — optional, unvalidated reference

[中文版](README_中文.md) · [Main NX installation guide](../README.md)

These scripts map hand tracking to a D1 model in Isaac Gym:

- `d1_isaac_control.py`: live tracking through `avp_stream`.
- `d1_isaac_replay.py`: replay of `demo_data/demo_data.npz`.

This optional simulator workflow has **not** been validated on Jetson Orin NX.
The SDK's ARM64/Python support matrix does not establish Isaac Gym, AVP, Torch or retargeting compatibility.
Do not install optional dependencies into the verified robot environment or assume the presence of CUDA is sufficient.

## Environment requirements

A separately verified environment must provide Isaac Gym Preview 4, a matching D1 SDK,
Pinocchio, SciPy and `dex_retargeting`; live input additionally requires `avp_stream` and Vision Pro connectivity.
The bundled retargeting package declares Python `>=3.7,<3.11` and has its own dependency requirements.
No complete, tested simulator dependency lock is provided in this release.
The SDK wheels in this package are ARM64 only, not suitable for an x86 simulator host.

## Reference commands

Only after independently validating the simulator environment, run from this repository root.
Replace the interpreter path and `VISION_PRO_IP` with actual values:

```bash
/path/to/verified-simulator/bin/python avp_teleop/d1_isaac_control.py --ip VISION_PRO_IP
/path/to/verified-simulator/bin/python avp_teleop/d1_isaac_replay.py
```

The live script supports operation without `--ip` for a simulation-only input mode;
its viewer uses `S` to calibrate/start tracking. Replay resets and loops at the end of the recording.
These descriptions do not constitute NX runtime acceptance.

## Replay data

`ReplayCfg.tracking_data_path` defaults to the bundled NPZ. Expected arrays:

| Field | Shape |
| --- | --- |
| timestamps | (T,) |
| right_wrist_poses | (T, 4, 4) |
| right_pinch | (T,) |
| right_fingers (optional) | (T, 25, 4, 4) |

The optional retargeting code and models are in [lib/dex-retargeting](../lib/dex-retargeting/README.md).
