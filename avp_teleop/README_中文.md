# Apple Vision Pro 遥操作——未验收的选配参考

[English](README.md) · [NX 安装入口](../README.md)

这里的脚本将手部追踪映射到 Isaac Gym 中的 D1 模型：

- `d1_isaac_control.py`：通过 avp_stream 接收实时追踪。
- `d1_isaac_replay.py`：回放 `demo_data/demo_data.npz`。

**此仿真流程未在 Jetson Orin NX 验收。** SDK 的 ARM64/Python 支持矩阵不等于
Isaac Gym、AVP、Torch 或手部重定向已兼容。不能仅因 NX 有 CUDA 就直接套用仿真安装步骤，
也不要在已验收的真实机器人环境里安装选配依赖。

## 环境前提

需要独立验证的环境，包含 Isaac Gym Preview 4、与该环境架构/ABI 匹配的 D1 SDK、
Pinocchio、SciPy 和 dex_retargeting；实时输入还需要 avp_stream 与 Vision Pro 网络连接。
随附重定向库声明 Python `>=3.7,<3.11`，有独立依赖要求。
本发行未提供已验收的完整仿真依赖锁定文件；随附 SDK wheel 仅适用于 ARM64，不适用于 x86 主机。

## 参考命令

只有在单独确认仿真环境可用后，才从仓库根目录运行。先替换解释器路径和实际 Vision Pro IP：

```bash
/path/to/verified-simulator/bin/python avp_teleop/d1_isaac_control.py --ip VISION_PRO_IP
/path/to/verified-simulator/bin/python avp_teleop/d1_isaac_replay.py
```

实时脚本不传 `--ip` 时支持无外部输入的仿真模式；在 viewer 中用 `S` 标定并开始追踪。
回放脚本在数据结束后重置并循环。这些是参考行为说明，不是 NX 运行验收结论。

## 回放数据

`ReplayCfg.tracking_data_path` 默认指向附带 NPZ，数组格式为：

| 字段 | 形状 |
| --- | --- |
| timestamps | (T,) |
| right_wrist_poses | (T, 4, 4) |
| right_pinch | (T,) |
| right_fingers（可选） | (T, 25, 4, 4) |

选配代码与模型位于 [lib/dex-retargeting](../lib/dex-retargeting/README.md)。
