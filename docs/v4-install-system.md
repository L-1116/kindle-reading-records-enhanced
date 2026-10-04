# V4 安装与运行系统

V4 是面向正常使用的稳定兼容版本。系统 runtime 通过实际 UI framebuffer 命令选择；launcher 不执行 FBInk `-e`、help 或 info probe。Lua 保留有界的基本 `loadfile` 能力及真实 UI 源码解析检查。

FBInk 候选顺序为用户明确路径、KMC 通用路径、libkh、ABI 对应 KMC 路径、PATH。保留旧版 KMC/libkh 相对优先顺序；通过真实路径、device/inode、size+cksum 去重，可用时再以 cmp 确认相同内容。首次实际命令有约 3 秒边界；失败就以原参数尝试下一候选，成功后锁定。锁定后的真实错误安全退出；普通 GC16_FAST waveform 拒绝保留同 runtime 的 GC16 降级。恢复 Library 只使用 LIPC，不再执行 FBInk。

## 推荐的两文件安装

本地发布候选包 `ReadingTime-V4.zip` 用于普通 Kindle，`ReadingTime-V4-KS.zip` 用于 Kindle Scribe。每个 ZIP 顶层只有：

- `reading-records-v4-install.sh`（Scriptlet 显示名仍为中文；旧长文件名仅在清理时识别）
- `阅读记录安装数据.tar`

将两个文件一同复制到 Kindle 的 `documents` 文件夹，点击安装 Scriptlet。安装成功后先打开“阅读记录”验证，再点击自动生成的 `安装好之后，确认无误了再点这个.sh` 清理安装文件。安装失败时保留两个原始文件和日志。

bootstrap 使用 `/tmp/reading-records-installer.$$`，检查 payload 文件大小、可用时的 POSIX `cksum`、tar 成员路径及 payload variant，然后解包并调用 tar 内的原有 `native-reading-time-package/install.sh`。优先用 `tar`，否则尝试 `busybox tar`，均不可用则停止。tar 内保留 `PACKAGE-MANIFEST.json` 或 `PACKAGE-MANIFEST-KS.json` 的逐文件 SHA-256 记录，并包含 `V4-PAYLOAD`、`v4/cleanup.sh`、各自独立的 runtime payload 与完整兼容安装树。

## fresh、upgrade、repair

设备型号从 `/var/local/deviceType.txt` 识别；无法识别时拒绝安装。现有 variant 先读 `reading-time/release-info`，旧版本再根据 `VERSION` 和 launcher/release 路径判断。跨 variant 一律拒绝，不静默混装。无 daemon 时运行原基础安装器，然后运行普通或 KS 核心；有 daemon 时直接原地升级。V4 再运行同一包即覆盖修复。正式安装核心仍负责环境探测、FBInk、daemon、Upstart、launcher 和 runtime 安装。

升级前，bootstrap 在 `reading-time/.v4-rollback.$$` 备份已有的 `bin/`、`releases/`、`compat/`、`ui/`、`fonts/`、`assets/`、版本标记、正式书库入口、KUAL 安装入口和 service 配置。原安装核心也有各自的 staging/rollback。核心非零退出、最终验证失败或版本/cleanup 入口发布失败时，外层恢复升级前 runtime；`reading-time.tsv`、`book-covers/`、用户配置与统计缓存不进入替换清单。成功后删回滚暂存。运行中断电与文件系统故障属于离线测试无法完整模拟的系统边界。

成功条件：核心返回零，正式 resolver、launcher、书库“阅读记录”入口、daemon、`reading-time.tsv` 和 Upstart job 存在；KS 还检查 force-exit helper。随后原子写入 `VERSION=V4` 或 `V4-KS` 与 `release-info` 的 `release_family=V4`、`variant=standard|ks`、`runtime_release`，最后生成 cleanup Scriptlet。任何非零结果都不生成新的 cleanup 入口。

## cleanup 精确白名单

cleanup 再次验证上述激活条件才执行。精确目标为 V4 bootstrap、tar、cleanup 本身、V4 安装结果/日志，以及已知旧版安装结果、旧诊断临时报告、cover-debug 临时包、旧 install Scriptlet、旧安全 cleanup Scriptlet、旧 installer KUAL tree、旧 RUNME/README、旧 payload tree、旧 manifest。通用文件名和目录需有安装器签名；旧 payload tree 必须匹配已校验 V4 tar 的逐路径清单，因此没有 manifest 或 `install.sh` 的 9.7.4 目录也能安全清理，未知文件会导致整次清理中止。`reading-time/`、正式入口、daemon、service、release、历史数据、封面、配置、`launch-last.log` 和 `touch-last.log` 均不在删除清单。重复执行 cleanup 视为幂等。

## 开发者本地完整包

`ReadingTime-V4-Full-Compatibility.zip` 与 `ReadingTime-V4-KS-Full-Compatibility.zip` 仅供开发者本地保留，含传统目录、RUNME 和 KUAL 入口，转调同一 bootstrap。公开 Release 的手动 assets 严格只有 Standard 与 KS 两个用户 ZIP。

## 工程验证

运行 `python scripts/validate_all.py`，覆盖统计、封面、真实 Lua 渲染、Standard/KS startup、FBInk resolver、固件与屏幕矩阵、KS touch、安装/升级/repair/rollback/cleanup，以及最终包字节校验。测试中模拟设备路径与命令，不接管前台屏幕。自动化输出见 `build/validation/stable-suite-results.json`。

核心回归永久保留：FBInk `-e=139` 而实际绘制成功时进入 UI；A 实际命令 139、B 成功时自动切换并锁定；全部实际命令失败时非零退出并返回 Library；内容相同候选不重复执行。公开版本不要求普通用户安装诊断包或执行手动 runtime 测试。
