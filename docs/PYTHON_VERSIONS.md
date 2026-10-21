# ARM64 Python 版本选择与安装

本包提供 SDK 当前声明范围 `>=3.8,<3.12` 内的四个 CPython 小版本。
不是 x86 包，不包括 Python 2、PyPy、3.12+ 或 free-threaded ABI。
本次构建/软件验证设备为 Jetson Orin NX、Ubuntu 22.04、L4T R36.4.3。

## 1. 支持矩阵

| Python 小版本 | 实测解释器 | SDK wheel 标签 | 对应依赖清单 | 示例 1～3 真机/GUI |
| --- | --- | --- | --- | --- |
| 3.8 | 3.8.20 | cp38-cp38-linux_aarch64 | requirements-jetson-py38.lock.txt | 未实测 |
| 3.9 | 3.9.25 | cp39-cp39-linux_aarch64 | requirements-jetson-py39.lock.txt | 未实测 |
| 3.10（默认） | 3.10.12 | cp310-cp310-linux_aarch64 | requirements-jetson-py310.lock.txt | 通过 |
| 3.11 | 3.11.17 | cp311-cp311-linux_aarch64 | requirements-jetson-py311.lock.txt | 未实测 |

四份 SDK wheel 都在 `lib/`，文件名前缀均为 `beingbeyond_d1_edu_sdk-0.2.0-`，均已通过软件验证。
新增三个版本分别完成 pip check、四个核心的安装/ELF/ABI 审计、URDF/mesh、FK/QP、
SDK 单步 IK、示例 4 参数帮助和 10 项无硬件回归。
Python 3.10 已完成示例 1～3 的实际串口/CAN 动作及触觉、相机窗口验证。
各 Python 版本使用独立 ABI 和依赖组合，3.10 的结果不能代替其他版本的真机/GUI 实测。
示例 0、4～10 和其他选配功能尚未测试，不属于本次已验收范围。

截至 2026-10-20，Python 3.8、3.9、3.10 已结束 CPython 上游维护，3.11 仍处于安全维护阶段；
Linux 发行商对系统 Python 的维护另计，不能将上游生命周期等同于 Ubuntu 系统包停止维护。
生命周期参考：[Python 官方版本状态](https://devguide.python.org/versions/)。
提供旧版本是为了既有环境兼容，不是安全维护承诺。
当前机器人演示继续使用已有的 Python 3.10，不为交付 wheel 自动切换；
若希望以 3.11 作为新的正式环境，应先补齐该版本的硬件/GUI 验收再决定迁移。

## 2. 选择原则

1. 用实际要运行示例的解释器检查 `--version`，不要依赖 shell 中含义不明的 python/pip。
2. CPU 必须是 aarch64，Python 小版本必须匹配 wheel 标签。
3. 每个小版本用独立 venv 和自己的锁定文件，不能把 3.10 依赖清单装入 3.8。
4. 不能重命名 wheel 解决 ABI；不要一次安装 `lib/*.whl`。
5. 不修改 `/usr/bin/python3`，不通过系统 pip/sudo pip 安装本包。
6. 此矩阵只覆盖 D1 SDK。随附可选 dex-retargeting 声明 `>=3.7,<3.11`，
   仿真/AVP/手部重定向还需独立验证，不能套用 SDK 的 3.11 支持结论。

Python 解释器本身不包含在客户包内。NX 默认系统一般只有本次使用的 3.10；
其他解释器需要预先在独立位置准备并验证，不能假设 22.04 默认 apt 仓库就提供所有版本。
SDK wheel 不会替客户安装 Python。

## 3. 默认 3.10 安装

继续使用根 README 的步骤。已有的验证环境是：

```text
/home/nvidia/d1_edu_deploy/venv-py310/bin/python
```

该环境没有因增加 wheel 而重装或切换。

## 4. Python 3.8 安装示例

以下假定用户为 nvidia、交付目录为 `/home/nvidia/Beingbeyond_D1_edu_nx`，
且已知一个可用的 ARM64 Python 3.8 绝对路径。第一条路径需要替换成实际值。
新 venv 的创建路径不应覆盖已存在的环境。

```bash
/absolute/path/to/python3.8 -m venv /home/nvidia/d1_edu_deploy/venv-py38
cd /home/nvidia/Beingbeyond_D1_edu_nx
/home/nvidia/d1_edu_deploy/venv-py38/bin/python -m pip install \
  --find-links /home/nvidia/Beingbeyond_D1_edu_nx/lib/dependencies/py38 \
  -r requirements-jetson-py38.lock.txt
/home/nvidia/d1_edu_deploy/venv-py38/bin/python -m pip install --no-deps \
  lib/beingbeyond_d1_edu_sdk-0.2.0-cp38-cp38-linux_aarch64.whl
/home/nvidia/d1_edu_deploy/venv-py38/bin/python -m pip check
```

3.8 的 CVXPY 1.5.2 需要 ECOS，而本次依赖解析没有找到可用的 ECOS ARM64 cp38 上游 wheel。
因此已用 NX 编译 `ecos-2.0.14-cp38-cp38-linux_aarch64.whl` 并放在 find-links 指定的目录。
`sources/` 中保留原始 ECOS 源码和许可证，不参与运行导入。
安装步骤必须保留 find-links，否则 pip 可能尝试在客户机器上源码编译 ECOS。

主要依赖为 NumPy 1.24.4、CVXPY 1.5.2、Matplotlib 3.7.5、SciPy 1.10.1、python-can 4.5.0。
这与 3.10 的依赖并不相同，不能为了“版本统一”直接升级旧 Python 环境的依赖。

## 5. Python 3.9 / 3.11 安装示例

以 3.11 为例，首先替换解释器路径：

```bash
/absolute/path/to/python3.11 -m venv /home/nvidia/d1_edu_deploy/venv-py311
cd /home/nvidia/Beingbeyond_D1_edu_nx
/home/nvidia/d1_edu_deploy/venv-py311/bin/python -m pip install \
  -r requirements-jetson-py311.lock.txt
/home/nvidia/d1_edu_deploy/venv-py311/bin/python -m pip install --no-deps \
  lib/beingbeyond_d1_edu_sdk-0.2.0-cp311-cp311-linux_aarch64.whl
/home/nvidia/d1_edu_deploy/venv-py311/bin/python -m pip check
```

3.9 同理使用 python3.9、venv-py39、requirements-jetson-py39.lock.txt 和 cp39 wheel。
3.9/3.11 不需要安装本包中的 cp38 ECOS wheel。
两个版本顶层基线为 NumPy 1.26.4、CVXPY 1.6.6、Matplotlib 3.9.4；
实际 SciPy 等传递依赖仍各有差异，以各自锁定文件为准。

## 6. 安装后无硬件验证

以 3.11 新建的环境为例：

```bash
cd /home/nvidia/Beingbeyond_D1_edu_nx
PYTHONDONTWRITEBYTECODE=1 /home/nvidia/d1_edu_deploy/venv-py311/bin/python \
  tools/check_sdk_binary.py \
  --wheel lib/beingbeyond_d1_edu_sdk-0.2.0-cp311-cp311-linux_aarch64.whl \
  --runtime --expected-prefix /home/nvidia/d1_edu_deploy/venv-py311
PYTHONDONTWRITEBYTECODE=1 /home/nvidia/d1_edu_deploy/venv-py311/bin/python tools/check_sdk_ik.py
```

换版本时同时替换解释器、wheel 标签及 expected-prefix。两条命令只检查软件/数值计算，
不会打开机器人串口、CAN 或摄像头，不会发送运动命令。
示例 1/2/4 的普通运行与这些检查不同，它们可能立即控制机器人。

PCAN 内核驱动与 Python ABI 无关，不需要每个 Python 版本各编译一份。
它仍要求内核匹配、模块加载、正确接口/1 Mbps 配置以及设备权限。
相机仍需 USB 实际连接和桌面显示会话。这些条件不会随安装 SDK 自动完成。

## 7. 校验值

```text
6dd9262c2afd4cb4d35c943f75b3026f1f6f94257bc8da075d5473c1baacaf3b  cp38 SDK
cf0fbf3ed74f7ba3c37e390b595f8a327b6d64d340d88d4571ef84566003bc30  cp39 SDK
2af417c3386cc6f2aa367130f50119588029355892c05de5bac4d6d4e8adc0aa  cp310 SDK
4ee261dfec86a1da28234b429687b7031092745a0aa0a734baf22e460967a084  cp311 SDK
38f38e9687d6d3cea38a410a23ecdd1c132fa359c26f95cb2469d344af0dfb8a  cp38 ECOS
```

完整的路径校验以交付根目录 SHA256SUMS 为准。本包仍不是包含全部依赖 wheel 的离线仓库，
除 SDK 与专门补充的 ECOS 外，其他依赖需要通过网络或客户自己的受控镜像安装。
