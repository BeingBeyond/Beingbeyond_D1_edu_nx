# dex-retargeting 0.4.0 — 可选运行/资源副本

来源：[dexsuite/dex-retargeting](https://github.com/dexsuite/dex-retargeting)。
此副本用于手部重定向相关参考，不是 D1 示例 1～3 的依赖，也未在本次 NX 发布中完成运行验收。

## 内容与版本边界

- `dex_retargeting/`：保留运行包，包括包内 `example/single_hand_detector.py` 辅助模块。
- `dex_retargeting/configs/`：保留 D1 手部重定向配置。
- `assets/`：保留 D1 左右手 URDF 与网格。
- `setup.py`、`pyproject.toml`：保留本地安装描述。
- `LICENSE`、`CITATION.cff`：保留原始版权、许可和引用信息。

本地版本字符串为 0.4.0，`setup.py` 声明 Python `>=3.7,<3.11`。
它与 D1 SDK 的 Python 3.8～3.11 wheel 支持范围不同，不能直接装到 SDK 的 3.11 环境后声称兼容。
安装描述还可能引入 Torch、nlopt 等额外依赖；不要直接在已验收的机器人 venv 中试装。
选配功能应在独立环境中确定平台、Python、依赖锁定及模型路径后另行验收。

此目录不是完整的上游仓库：上游顶层独立演示、演示媒体、测试和 CI 不包含在本发行中。
完整项目资料请从上游项目入口获取；不要依赖本地不存在的顶层 example/ 路径。
本地配置中的相对 URDF 路径需要以 `assets/robots/hands` 为资源根解析，
使用者应按所调用的重定向示例设置资源根，不能依赖开发者工作目录。

## 关节映射

不同模型解析器、仿真器和真实驱动可能产生不同关节顺序。
集成重定向结果时应根据唯一关节名称建立映射，不要假设数组索引顺序一致。

## 来源与学术引用

该项目源于 [AnyTeleop](https://yzqin.github.io/anyteleop/)。引用信息保留在 CITATION.cff；
原项目引用为：

```bibtex
@inproceedings{qin2023anyteleop,
  title = {AnyTeleop: A General Vision-Based Dexterous Robot Arm-Hand Teleoperation System},
  author = {Qin, Yuzhe and Yang, Wei and Huang, Binghao and Van Wyk, Karl and Su, Hao and Wang, Xiaolong and Chao, Yu-Wei and Fox, Dieter},
  booktitle = {Robotics: Science and Systems},
  year = {2023}
}
```

上游说明中注明的模型来源为 [dex-urdf](https://github.com/dexsuite/dex-urdf)，
运动学依赖为 [Pinocchio](https://github.com/stack-of-tasks/pinocchio)。
本地保留的 D1 资产以随附文件为准，不据此声明本包与上游完整资产集合相同。
上游演示使用 [SAPIEN](https://github.com/haosulab/SAPIEN)；PositionOptimizer 的方法来源说明
还涉及 [From One Hand to Multiple Hands](https://yzqin.github.io/dex-teleop-imitation/)，
DexPilotOptimizer 的来源说明见 [DexPilot](https://sites.google.com/view/dex-pilot)。
许可见 [LICENSE](LICENSE)。本 README 为该发行子集的使用说明，不改变原始许可证。
