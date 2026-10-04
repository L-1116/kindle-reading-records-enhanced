# Kindle 阅读记录 V4 稳定兼容版本验收报告

日期：2026-10-04（Asia/Shanghai）。

阶段说明：本文记录稳定兼容版本的发布前验收。后续用户已明确授权以 V4 Test 3（v4-test.3）发布 Pre-release；本次完整重验与发布准备记录见 [V4 Test 3 最终验收](v4-test3-final-validation.md)，用户发布说明见 [V4 Test 3](releases/v4-test3.md)。以下“未发布”描述对应当时的审计阶段。

代码、历史审计、完整离线回归及最终包一致性验证已完成。判断：已达到可正常发布给用户使用的工程标准。本轮没有创建 GitHub Release，等待用户审阅后明确指示发布。

## 35 项答复

1. **回归根因**：确认：强制 FBInk `-e` gate 是三例日志被阻挡在 UI 之外的直接原因，也是本轮最主要的 launcher 兼容性回归。日志没有证明真实 draw/refresh 失败，因此不能据此判整个 runtime 不可用；`-e` 内部为何崩溃的底层原因不作无证据推断。

2. **引入 commit**：首次引入为 `982ea7131c81a198997315602a79c684bb4f3d7d`（2026-10-03，V3 startup / V3-KS touch hotfix）。`88164e9` 的 V4 Test1 延续该 gate；`0dc8c1b` 的 Test2 增加 bounded watchdog，不是 gate 的起点。

3. **历史差异**：`a48d8c7910cdf5cabff11828663f4fb2f142c322` 只按存在/可执行选择 FBInk 并 export 后启动 UI；后来加入信息命令执行门禁、更多启动日志及 failure recovery。本轮保留真实资源/语法检查、日志、Lua bounded checks 和信号清理，移除 FBInk info gate、unknown-arch 门禁以及安装器单凭 loader 存在的推测门禁。详见后面的启动差异表。

4. **Standard 修复**：`launch.sh` 只构建 executable candidate list，不执行 FBInk。`阅读记录-optimized.sh` 在第一次真实 UI 命令中选择并锁定 runtime；没有 help/info 替代 gate，没有 bypass 环境开关。

5. **KS 同步**：`launch-ks.sh` 与 `阅读记录-ks.sh` 使用相同 resolver/wrapper 合约。KS 的 Lua source 检查仍为 touch-probe-ks、touch-ks 和四个公共 helper，新增严格名单审计及 fixture 可读性检查。touch reader/probe 没有修改。最终静态审计发现独立 force-exit 仍有旧 FBInk 旁路，已仅删除四行未经验证的 runtime 选择/刷新，保留进程终止及 LIPC 恢复。失败时把现有 touch-last 内容并入 launch-last，保持一份日志即可支持定位。

6. **候选顺序**：用户明确的 `READING_FBINK` → `/var/local/kmc/bin/fbink` → `/mnt/us/libkh/bin/fbink` → ABI 对应的 `/var/local/kmc/armhf/bin/fbink` 或 `/var/local/kmc/armel/bin/fbink` → `command -v fbink`。保留历史 KMC、libkh、PATH 的相对优先顺序，优先恢复已知正常设备行为。

7. **去重**：先比较路径/realpath（readlink -f fallback），再比较 device/inode，再比较 size+POSIX cksum。cksum 相同时可用 cmp 会进一步确认内容；cksum 不可用时可直接用 cmp。工具缺失不形成启动 gate。重复候选记录 `duplicate_of` 并从执行列表排除。复制、hardlink、同路径，以及部分 identity 工具缺失均有验证。

8. **actual-use fallback**：首次绘制原样调用 `"$candidate" "$@"`。首个候选失败，下一候选执行完全相同的真实 UI 参数；成功即继续当前 UI。首次候选尝试约 3 秒有界，不依赖 timeout 工具或额外服务。

9. **首次失败切换**：返回非零、139/SIGSEGV、不可用或首次超时均记录 candidate/exit code，再尝试下一候选。A=139/B=0 在两版完整 UI 中通过；另外真实 SIGSEGV 子进程测试也通过。

10. **成功锁定**：首次真实 framebuffer 命令成功设 `FBINK_LOCKED=1`，更新 FBINK 与 export 的 READING_FBINK。后续不遍历候选、不重算 identity、不启动 watchdog 轮询。锁定后真实错误直接安全退出；普通 GC16_FAST 拒绝保留同 runtime 的 GC16 降级，崩溃/126/127 不作 waveform 降级。

11. **全部失败恢复**：wrapper 写 `fbink_runtime_failure`、failing_command、candidate、原始 exit code，并明确 `exit 31`。该 exit 不会被普通 `|| renderer fallback` 吞掉。UI trap 清理会话/子进程/方向；launcher 收到非零后清 eatTapMode、清 preventScreenSaver、启动 KPP Library。三候选实际命令全失败和首轮超时均有检查。

12. **restore_native**：launcher、UI cleanup 及最终修复的 KS 独立 force-exit 均不再调用 FBInk。Library 自己刷新原生界面；不存在用未验证或已经失败的 runtime 再次清屏的路径。

13. **Lua 检查**：保留约 3 秒有界的 `assert(type(loadfile)=="function")` 和每个真实 UI Lua source 的 loadfile 检查，以及已有 fallback 和信号/超时子进程回收；没有增加无关 Lua probe。

14. **5.18 detection**：detect_env.sh 与冻结基线字节一致。以 major=5/minor=18 识别全家族，没有对 5.18.1.1.1 硬编码；11 个 5.18 标签全部覆盖。

15. **5.18 GC16**：两版 refresh_region 与冻结基线逐字节一致：首次 nonflash GC16、GC16_FAST → GC16、周期 full refresh 保留。40 组历史命令比较、30 个 stage/failure 场景、216 个方向/退出/fallback 场景通过。旧兼容界面也继承 fw518 首刷策略。

16. **5.17.1.0.4**：完整 Standard startup 在 1072×1448 和 1272×1696 均 PASS，进入真实生产 UI 的触摸监听阶段；安装器不再仅凭 hard-float loader 断言拒绝源码包。

17. **5.18.1.1.1**：KPW4 证据参数（armv7l、hard_float=1、kernel=4.1.15-lab126、1072×1448）fixture PASS；1272×1696 也 PASS。`-e=139` 不影响真实 UI 启动。

18. **5.19.2**：两种 Standard 屏幕完整 startup PASS；kernel=4.9.77-lab126 fixture 中 `-e=139`、actual commands=0，进入 UI。

19. **5.19.5**：两种 Standard 屏幕完整 startup PASS；kernel=5.15.41-lab126，包含 1272×1696，`-e=139`、actual commands=0，进入 UI。

20. **KS 5.19.6**：完整 startup、实际 fallback、全部失败恢复、touch preflight/设备选择、16/24-byte events、坐标映射、方向恢复、force-exit、INT/TERM/HUP、reader 错误及静默等待均 PASS。touch 核心 SHA-256 与基线一致。

21. **最重要的回归**：永久保留的 mock：`-e` 返回 139，实际图片/矩形/文字/GC16/full refresh 返回 0。两版正常进入 UI，不执行 FBInk info probe。完整固件/屏幕矩阵及 fallback 共 40 个完整 UI 场景 PASS。

22. **A=139/B=0**：完整 Standard/KS PASS：A 只尝试一次，B 收到同一实际参数并被锁定，继续渲染与 refresh。没有在每次绘制时重复候选循环。

23. **全部 actual 失败**：A=139、B=6、C=7 的完整两版测试返回 31，复位输入/休眠并返回 Library；没有继续跑 UI、没有额外 FBInk cleanup。两候选均超时和相同内容仅试一次的场景也通过。

24. **安装/升级/repair**：V4 安装系统 38 个场景 PASS，包括 fresh、9.7.4/9.7.5/V1/V2/V3/V3-KS/V4/Test1/Test2 原地覆盖、repair、Standard/KS 无 hard-float loader 的 fresh install、payload/解包/staging/activation/最终校验失败、rollback、防混装、busybox tar、提前清理拒绝及历史残留清理。最后用户 ZIP 又分别从 Test2 覆盖安装并核对已安装字节。

25. **reading-time.tsv**：保留。升级/repair/rollback/cleanup 以升级前 SHA-256 验证历史 TSV、备份和历史统计导出；tracker daemon、Upstart 与缓存统计算法保持基线字节。

26. **book-covers**：保留。两个既有封面、cover-cache、用户配置及核心日志均通过升级和 cleanup 保留检查。没有卸载再重装要求。

27. **短 bootstrap**：保持 `reading-records-v4-install.sh`，物理名为短 ASCII；Scriptlet `# Name: 安装阅读记录`。没有恢复旧长中文安装实体文件名。

28. **Standard ZIP 顶层**：严格只有 `reading-records-v4-install.sh` 与 `阅读记录安装数据.tar`；解压外层 ZIP 一次，无需手动解压 tar。

29. **KS ZIP 顶层**：同样严格只有 `reading-records-v4-install.sh` 与 `阅读记录安装数据.tar`。variant、payload 和 runtime 独立。

30. **所有现有测试**：PASS。完整套件运行后，对本轮允许改变的 legacy runtime 整文件哈希断言改为严格历史核心比对，并重跑相关测试；最终共 33 项测试/构建/审计入口全部通过。另有最后 runtime/安装的 8 个定向场景以及当前 KS 完整 UI 重验。最终结果见机器可读验收记录，不将早期失败尝试伪装成未经发生。

31. **git diff --check**：PASS，退出码 0。

32. **修改文件**：完整列表见下方。开始时已存在的 untracked tools/ 原样保留，未纳入用户包。没有自动 commit/push/Release。

33. **git diff 摘要**： 30 files changed, 583 insertions(+), 218 deletions(-)；新增文件另列。核心为移除错误 gate、actual-use fallback、原生恢复、旧兼容界面安全调用、移除源码包 loader 推测门禁、自动化保护与正式包命名。最终静态审计另删除 KS force-exit 中四行旧 FBInk 旁路。

34. **bundled FBInk**：没有增加。最终两包逐成员检查 bundled ELF=0；没有完整 KMC/libkh、大 runtime、daemon 或额外后台服务。Full Compatibility 与校验和仅留在开发者本地。

35. **离线无法消除的边界**：外部 Lua/FBInk 与设备驱动的具体实现、eInk 异步更新的物理显示效果、USB/存储/突然断电行为不能由离线 mock 完整证明。已有历史可用行为及原始日志支持本轮修复方向；代码中的 fallback、非零退出、原生恢复和数据保护已完成。没有将这些边界转为用户 runtime 选择或反复安装诊断版本的要求。

## 从历史 launcher 到稳定 V4 的差异

| 项目 | a48d8c7 | Test1 / Test2 | 本轮最终实现 |
|---|---|---|---|
| FBInk selection | 文件存在/可执行；KMC/libkh/PATH | primary/fallback 均须 -e 成功 | 有序去重列表；真实 UI 命令决定选择 |
| Lua | command -v；旧 loader 规则 | execution/source probes；Test2 有界 | 保留 bounded execution + 真实 source parser；KS 名单独立 |
| Environment/ABI | firmware detection；5.18 loader 推断 gate | ABI/profile/unknown arch 预检 | family detector 保留；ABI 只用于候选路径排序 |
| Preflight | 基本文件和依赖 | 额外 Shell/resource checks + FB info gate | 真实 UI 语法/资源/数据依赖保留；FB info gate 删除 |
| PATH/export | export READING_FBINK | 优先 probed Lua 目录；export selected runtimes | 保留 Lua PATH/export；新增 newline candidates；成功后更新 READING_FBINK |
| UI launch | 直接运行 UI 并捕获输出 | gate 失败不启动 UI | 候选可执行即进入 UI；actual wrapper 选择 |
| First framebuffer draw | 普通 UI 调用 | 实际绘制尚未发生就可能被拦 | 第一次真实 draw 有界同命令 fallback，成功锁定 |
| GC16 | 既有刷新策略 | 5.18 首刷修复 | Standard/KS refresh_region 与修复基线字节一致 |
| Signal/children | 基础信号 trap | Lua watchdog PID 回收 | 保留；launcher 管 UI child，FB wait 可中断并回收其 child |
| Failure cleanup | 基础 status/diagnostic | LIPC + SELECTED_FBINK refresh | LIPC-only Library 恢复；不再执行坏 runtime |
| Legacy renderer | 写死 KMC，无统一检查 | 仍写死 KMC | 继承选定 runtime；同 wrapper；pipeline 错误传播到主进程 |

## 固件 / 屏幕结果

Standard：5.17.1.0.4、5.18、5.18.0、5.18.1、5.18.1.1.1、5.18.1.2、5.18.2、5.18.4、5.18.5、5.18.5.0.1、5.18.6、5.18.10、5.19.1、5.19.2、5.19.5、5.19.6，全部分别覆盖 1072×1448 与 1272×1696，PASS。

KS：5.18、5.18.1.1.1、5.18.10、5.19.6 的 1860×2480 完整 UI 场景 PASS；已有 5.18.1 / 5.18.2 / 5.19.1 方向及 touch compatibility 场景也 PASS。

## 最终用户包

| 版本 | 文件 | 字节 | SHA-256 |
|---|---|---:|---|
| standard | `ReadingTime-V4.zip` | 15189054 | `579b998dc54176e4163eb473503b79b8c2d7976a54ceae13612c980cea5c030a` |
| ks | `ReadingTime-V4-KS.zip` | 15182708 | `780447b50296e6f746d07153a5b22459336785dcbf202f77707096121e7d5ef6` |

两个 ZIP 顶层均仅两文件；tar、bootstrap size/cksum、成员类型、manifest 与当前 sources 逐字节匹配。Full Compatibility 与 sums 不作为公开手动资产。正式发布文案已写入 [v4.md](releases/v4.md)，没有邀请普通用户帮忙测试。

## 修改文件

- `.github/workflows/validate.yml`
- `CHANGELOG.md`
- `README.md`
- `docs/v4-install-system.md`
- `ks-package/native-reading-time-package/Install-Native-Reading-Time-KS.sh`
- `ks-package/native-reading-time-package/install.sh`
- `ks-package/native-reading-time-package/force-exit-ks.sh`
- `ks-package/native-reading-time-package/launch-ks.sh`
- `ks-package/native-reading-time-package/阅读记录-ks.sh`
- `native-reading-time-package/Install-Native-Reading-Time-Optimized.sh`
- `native-reading-time-package/Install-Native-Reading-Time.sh`
- `native-reading-time-package/install.sh`
- `native-reading-time-package/launch.sh`
- `native-reading-time-package/阅读记录-optimized.sh`
- `native-reading-time-package/阅读记录.sh`
- `scripts/build_v4.py`
- `scripts/check_v4_runtime.py`
- `scripts/validate_all.py`
- `tests/validate_compat.py`
- `tests/validate_day_detail.py`
- `tests/validate_ks_compat_sync.py`
- `tests/validate_ks.py`
- `tests/validate_orientation_startup.py`
- `tests/validate_period_details.py`
- `tests/validate_runtime_probe.py`
- `tests/validate_startup_refresh.py`
- `tests/validate_stats_filters.py`
- `tests/validate_ui.py`
- `tests/validate_v4.py`
- `v4/bootstrap.template.sh`
- `AGENTS.md`（新增）
- `docs/releases/v4.md`（新增）
- `docs/releases/v4-test3.md`（新增）
- `docs/v4-test3-final-validation.md`（新增）
- `docs/v4-stable-compatibility-report.md`（新增）
- `docs/v4-final-fbink-static-audit.md`（新增）
- `scripts/audit_v4_startup.py`（新增）
- `scripts/verify_v4_artifacts.py`（新增）
- `tests/legacy_runtime_contract.py`（新增）
- `tests/validate_fbink_actual_use.py`（新增）
- `tests/validate_fbink_resolver.py`（新增）

## 验收证据

- `build/validation/stable-suite-results.json`：最终 33 项验收及重跑记录。
- `build/validation/final-fbink-static-audit.json`：最后静态审计的完整生产源码清单、31 个 FBInk 调用点、KS force-exit 最小修复及相关回归；详情见 [最终静态审计](v4-final-fbink-static-audit.md)。
- `build/validation/stable-suite-initial-results.json`：保留首次执行结果，供复核。
- `build/validation/fbink-actual-use-results.json`：40 个完整 UI 场景。
- `build/validation/v4-final-targeted-results.json`：最终 runtime 与真实 ZIP 升级补验。
- `build/validation/v4-runtime-hashes.json`：Standard 62 文件、KS 65 文件，mismatches 均为空。
- `build/validation/v4-startup-history-audit.json`：引入 commit、保护文件 hash、刷新与 legacy 核心比对。
- `build/validation/v4-results.json`：38 个安装系统场景与数据保留 hash。
- `build/validation/v4-stable-artifacts.json`：最终两个用户包、SHA-256、顶层内容和 source equality。
- `build/validation/v4-final-verification.log`、`v4-final-resolver.log`、`v4-final-ks-actual.log`、`v4-final-one-log.log`：最后检查输出。

## 发布建议

可以按正常软件版本发布这两个 V4 用户 ZIP。该判断基于历史可用路径与绘制参数保留、错误 gate 移除、完整回归和最终包字节验证；不以普通用户继续安装测试包作为前提。本轮保持未发布状态，等待用户审阅和明确发布指示。
