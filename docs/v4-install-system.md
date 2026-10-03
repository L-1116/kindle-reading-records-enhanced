# V4 / V4-KS 安装体系测试说明

基线：`982ea7131c81a198997315602a79c684bb4f3d7d`。本轮 runtime freeze 仅允许 `native-reading-time-package/launch.sh` 和 `ks-package/native-reading-time-package/launch-ks.sh` 与 checkpoint 不同；检查器仍逐字节核对其余 runtime，并核对两份新 launcher 已进入 tar payload。UI、touch、daemon、统计及数据格式保持原字节。构建脚本在 `scripts/build_v4.py`，冻结文件核对脚本在 `scripts/check_v4_runtime.py`。

两个 launcher 的 runtime probe 使用相同的内建轮询 watchdog，无需 `timeout` 或新二进制。每次 Lua 执行、Lua source 语法检查和 FBInk `-e` 约 3 秒超时；仅终止并回收本次启动的子 PID，再尝试下一个去重候选。`launch-last.log` 记录候选、每步开始和结果、退出码、fallback 和最终选择。全部候选失败时 `error_stage=runtime_probe`，恢复书库并输出诊断。5.18 全家族、5.17 和 5.19 使用同一流程；KS touch 热修复不变。

## 推荐的两文件安装

本轮本地测试包 `ReadingTime-V4-Test2.zip` 用于普通 Kindle，`ReadingTime-V4-KS-Test2.zip` 用于 Kindle Scribe。每个 ZIP 顶层只有：

- `reading-records-v4-install.sh`（Scriptlet 显示名仍为中文；旧长文件名仅在清理时识别）
- `阅读记录安装数据.tar`

将两个文件一同复制到 Kindle 的 `documents` 文件夹，点击安装 Scriptlet。安装成功后先打开“阅读记录”验证，再点击自动生成的 `安装好之后，确认无误了再点这个.sh` 清理安装文件。安装失败时保留两个原始文件和日志。

bootstrap 使用 `/tmp/reading-records-installer.$$`，检查 payload 文件大小、可用时的 POSIX `cksum`、tar 成员路径及 payload variant，然后解包并调用 tar 内的原有 `native-reading-time-package/install.sh`。优先用 `tar`，否则尝试 `busybox tar`，均不可用则停止。tar 内保留 `PACKAGE-MANIFEST.json` 或 `PACKAGE-MANIFEST-KS.json` 的逐文件 SHA-256 记录，并包含 `V4-PAYLOAD`、`v4/cleanup.sh`、各自独立的 runtime payload 与完整兼容安装树。

## fresh、upgrade、repair

设备型号从 `/var/local/deviceType.txt` 识别；无法识别时拒绝安装。现有 variant 先读 `reading-time/release-info`，旧版本再根据 `VERSION` 和 launcher/release 路径判断。跨 variant 一律拒绝，不静默混装。无 daemon 时运行原基础安装器，然后运行普通或 KS 核心；有 daemon 时直接原地升级。V4 再运行同一包即覆盖修复。正式安装核心仍负责环境探测、FBInk、daemon、Upstart、launcher 和 runtime 安装。

升级前，bootstrap 在 `reading-time/.v4-rollback.$$` 备份已有的 `bin/`、`releases/`、`compat/`、`ui/`、`fonts/`、`assets/`、版本标记、正式书库入口、KUAL 安装入口和 service 配置。原安装核心也有各自的 staging/rollback。核心非零退出、最终验证失败或版本/cleanup 入口发布失败时，外层恢复升级前 runtime；`reading-time.tsv`、`book-covers/`、用户配置与统计缓存不进入替换清单。成功后删回滚暂存。真机上的断电与文件系统故障仍需设备测试。

成功条件：核心返回零，正式 resolver、launcher、书库“阅读记录”入口、daemon、`reading-time.tsv` 和 Upstart job 存在；KS 还检查 force-exit helper。随后原子写入 `VERSION=V4` 或 `V4-KS` 与 `release-info` 的 `release_family=V4`、`variant=standard|ks`、`runtime_release`，最后生成 cleanup Scriptlet。任何非零结果都不生成新的 cleanup 入口。

## cleanup 精确白名单

cleanup 再次验证上述激活条件才执行。精确目标为 V4 bootstrap、tar、cleanup 本身、V4 安装结果/日志，以及已知旧版安装结果、旧诊断临时报告、cover-debug 临时包、旧 install Scriptlet、旧安全 cleanup Scriptlet、旧 installer KUAL tree、旧 RUNME/README、旧 payload tree、旧 manifest。通用文件名和目录需有安装器签名；旧 payload tree 必须匹配已校验 V4 tar 的逐路径清单，因此没有 manifest 或 `install.sh` 的 9.7.4 目录也能安全清理，未知文件会导致整次清理中止。`reading-time/`、正式入口、daemon、service、release、历史数据、封面、配置、`launch-last.log` 和 `touch-last.log` 均不在删除清单。重复执行 cleanup 视为幂等。

## 完整兼容备用包

`ReadingTime-V4-Full-Compatibility-Test2.zip` 与 `ReadingTime-V4-KS-Full-Compatibility-Test2.zip` 保留传统目录、`RUNME.sh`、Scriptlet 与 KUAL 入口，适用于 `;log runme`、KUAL 或排障；这些安装入口转调同一 bootstrap。完整包包含相同的两文件安装数据，不能与另一 variant 混用。

## 离线验证与真机边界

运行 `python scripts/build_v4.py`、`python tests/validate_runtime_probe.py`、`python tests/validate_v4.py`、`python scripts/check_v4_runtime.py`。离线测试从实际 ZIP 取出脚本和 tar，沙箱替换仅限安装脚本内的设备绝对路径，模拟 initctl、FBInk 等 Kindle 命令。真机仍需验证 Scriptlet root 权限、书库扫描、KPW4 5.18.1.1.1 的真实 runtime，以及 KS 5.19.6 的点击与退出；失败时普通版只取 `launch-last.log`，KS 只取 `launch-last.log` 和 `touch-last.log`。
