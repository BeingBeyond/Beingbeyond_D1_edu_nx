# Python 3.8 / ARM64 的补充依赖：ECOS 2.0.14

`ecos-2.0.14-cp38-cp38-linux_aarch64.whl` 已在本次 NX 的 Python 3.8.20 下原生编译，
并随 CVXPY 1.5.2 完成安装、pip check、QP 与 SDK IK 软件验证。
它不是 D1 SDK 核心，也不能装入 Python 3.9/3.10/3.11。

安装 D1 的 py38 锁定文件时使用 `--find-links /path/to/Beingbeyond_D1_edu_nx/lib/dependencies/py38`。
不要将 sources/ 添加到 PYTHONPATH。

源码来源：[PyPI ECOS 2.0.14](https://pypi.org/project/ecos/2.0.14/)。
本目录 `sources/ecos-2.0.14.tar.gz` 是用于本次构建的原始源码分发包，
SHA-256 与 PyPI 官方元数据一致；`sources/LICENSE` 为该归档原有的 GPLv3 文本。
其他包含在归档中的版权/许可证说明一并保留，具体以各源文件和上游内容为准。

构建使用 Python 3.8.20、GCC 11.4、NumPy 1.24.4、SciPy 1.10.1、
setuptools 75.3.2、wheel 0.45.1，命令为：

```bash
/absolute/path/to/build-py38/bin/python -m pip wheel --no-deps --no-build-isolation \
  --wheel-dir /absolute/output/directory /absolute/path/to/ecos-2.0.14.tar.gz
```

同一个 build venv 中需先安装上述构建工具和 NumPy/SciPy。
这是 Linux aarch64 本机产物，不承诺在所有发行版/glibc 上通用。

```text
38f38e9687d6d3cea38a410a23ecdd1c132fa359c26f95cb2469d344af0dfb8a  ecos-2.0.14-cp38-cp38-linux_aarch64.whl
64b3201c0e0a7f0129050557c4ac50b00031e80a10534506dba1200c8dc1efe4  sources/ecos-2.0.14.tar.gz
```
