# 第三方组件与许可证

项目原有许可证为 [LICENSE](LICENSE)。随附第三方组件保留各自的来源、版权和许可证文本；
本清单不替代这些原始文件，也不将根目录许可证套用于全部第三方内容。

| 组件 | 本地内容 | 来源及许可证入口 |
| --- | --- | --- |
| dex-retargeting 0.4.0 | 运行代码、配置、D1 手模型、安装描述及引用信息 | [项目](https://github.com/dexsuite/dex-retargeting)、[本地 MIT LICENSE](lib/dex-retargeting/LICENSE)、[CITATION](lib/dex-retargeting/CITATION.cff) |
| PEAK Linux driver 9.3.1 | pcan.ko、对应完整源码归档 | [说明](lib/pcan/README.md)、[GPL](lib/pcan/LICENSE.gpl)、[LGPL](lib/pcan/LICENSE.lgpl)；归档内保留 Documentation/COPYING 及其他原始声明 |
| ECOS 2.0.14 | ARM64 cp38 wheel、对应原始源码归档 | [说明](lib/dependencies/py38/README.md)、[原 GPLv3 LICENSE](lib/dependencies/py38/sources/LICENSE)；归档内保留其他源文件的原始声明 |

PCAN 模块与其配套源码/许可证一起发布；ECOS 的源码和许可证也与 wheel 一起保留。
这些公开第三方源码与不随本包发布的 D1 SDK 私有核心源码是不同内容。

dex-retargeting 的上游来源、学术引用及模型来源说明见其
[README](lib/dex-retargeting/README.md) 与 CITATION。
本地副本为运行/资源子集，不包含上游独立演示媒体、测试和 CI，不应描述为完整上游仓库。

NumPy、Pinocchio、CVXPY、OpenCV、python-can 等其余运行依赖按相应锁定文件另行安装，
其许可证和元数据由对应分发包提供。当前包不是这些依赖的完整离线再分发镜像。
