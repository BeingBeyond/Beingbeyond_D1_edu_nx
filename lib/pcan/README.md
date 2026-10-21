# PCAN-USB：本次 NX 使用的 SocketCAN 驱动

硬件：PEAK PCAN-USB，USB ID `0c72:000c`。
本机原生 `can0` 是 NVIDIA `mttcan`；USB PCAN 加载 netdev 驱动后分配为 `can1`。
接口编号依赖系统已有设备，其他机器上必须重新确认。

## 文件和来源

- `5.15.148-tegra/pcan.ko`：本次在 NX 编译、加载并实际通信通过的内核模块。
- `peak-linux-driver-9.3.1.tar.gz`：构建该模块时使用的完整、未修改上游源码压缩包。
- `LICENSE.gpl`、`LICENSE.lgpl`：上游许可证；压缩包内还保留 `Documentation/COPYING`。
- 源码获取地址：<https://www.peak-system.com/fileadmin/media/linux/files/peak-linux-driver-9.3.1.tar.gz>。

源码版本 9.3.1，模块版本 `Release_20260916_n`，`modinfo` 的 license 为 GPL。
netdev 构建提供 Linux SocketCAN，不是安装 PCAN-Basic Python API。
D1 SDK 使用 `python-can` 的 SocketCAN 后端。
发布模块时应同时保留这里的对应源码和许可证，不要只发送 `.ko`。

## 1. 同一台已验证 NX：重启后的手动恢复

本次仅临时 `insmod`，**未执行 `make install`，未设置自动加载、udev 或 systemd 服务**。
不需要为此主动重启；已经加载且 can1 正常时，不要重复加载或重配正在使用的总线。

先检查：

```bash
uname -r
lsmod | grep -E '^(pcan|can_dev) '
ip -details link show
modinfo /home/nvidia/Beingbeyond_D1_edu_nx/lib/pcan/5.15.148-tegra/pcan.ko
```

附带模块的 vermagic：`5.15.148-tegra SMP preempt mod_unload modversions aarch64`。
仅在内核、模块 ABI 和配置匹配，且没有其他驱动占用 PCAN 时加载：

```bash
sudo modprobe can-dev
sudo insmod /home/nvidia/Beingbeyond_D1_edu_nx/lib/pcan/5.15.148-tegra/pcan.ko
ip -details link show
```

相同 `uname -r` 也不保证不同内核构建的符号版本一定兼容。
遇到 `Invalid module format`、符号版本错误或签名限制，应看内核日志并重新构建/处理策略，
不要使用强制加载选项。若系统已由 `peak_usb` 等驱动正确提供接口，也不要盲目卸载或换驱动。

确认 pcan 提供的接口确实是 `can1` 后，停止所有使用该接口的程序，再执行：

```bash
sudo ip link set can1 down
sudo ip link set can1 type can bitrate 1000000 restart-ms 100
sudo ip link set can1 up
ip -details -statistics link show can1
```

预期 `UP`、`ERROR-ACTIVE`、`bitrate 1000000`，通信后 RX/TX 增长且错误计数不增长。
名称 ERROR-ACTIVE 是正常 CAN 错误状态分类，不表示正在报错。
此配置不是持久化配置，重启、驱动卸载或拔插设备后需要检查。

## 2. 其他内核：重新构建

先取得与当前 NVIDIA 内核严格匹配、已准备好的 kernel headers/build tree。
不要用通用 Ubuntu 内核头文件代替 Tegra 头文件；不要为安装驱动随意升级工作内核。

```bash
uname -r
readlink -f /lib/modules/$(uname -r)/build
test -f /lib/modules/$(uname -r)/build/Makefile
```

在新的临时目录解压、编译，不覆盖正在使用的驱动：

```bash
PCAN_BUILD_DIR=$(mktemp -d /home/nvidia/d1-pcan-build.XXXXXXXX)
tar -xzf /home/nvidia/Beingbeyond_D1_edu_nx/lib/pcan/peak-linux-driver-9.3.1.tar.gz \
  -C "$PCAN_BUILD_DIR"
make -C "$PCAN_BUILD_DIR/peak-linux-driver-9.3.1/driver" netdev -j2 \
  KERNEL_LOCATION="/lib/modules/$(uname -r)/build" \
  PCI=NO_PCI_SUPPORT PAR=NO_PARPORT_SUBSYSTEM ISA=NO_ISA_SUPPORT \
  PCC=NO_PCCARD_SUPPORT DNG=NO_DONGLE_SUPPORT
modinfo "$PCAN_BUILD_DIR/peak-linux-driver-9.3.1/driver/pcan.ko"
file "$PCAN_BUILD_DIR/peak-linux-driver-9.3.1/driver/pcan.ko"
```

这些参数是本次使用的 USB-only / netdev 配置，`-j2` 控制编译峰值资源。
对新内核的源码兼容性需要实际编译验证，不保证 9.3.1 支持所有未来内核。
编译成功后先核对架构、vermagic、依赖和签名策略，再由设备负责人决定加载。
不要在机器人控制程序运行中卸载/替换驱动。

## 校验值

```text
25ec72f3ba16760a94979ffb56cf6f7a51eb61cdcd4968f7cf8825ddfe164c5c  peak-linux-driver-9.3.1.tar.gz
b152a74c787049fa0567333f2db0951ae658ddec70423e0eead9f4564f4c87c2  5.15.148-tegra/pcan.ko
```
