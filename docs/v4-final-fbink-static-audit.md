# V4 发布前 FBInk 静态调用审计

日期：2026-10-04。审计对象为当前 Standard/KS 两个最终用户包对应的生产源码。

阶段说明：此审计完成时尚未授权发布。用户随后已授权 V4 Test 3 Pre-release；完整重验与发布准备另见 [最终验收](v4-test3-final-validation.md)。本文的调用点和最小修复结论保持有效。

结论：发现一处 KS 独立强制退出入口的真实旁路，已删除。修复后 Standard、KS 所有实际 FBInk 执行均经过现有统一 wrapper；没有剩余绕过 fallback / locked runtime 的生产路径。三个 UI 文件及其 runtime selection、绘制、刷新逻辑本轮均未修改。

## 发现与最小修复

`ks-package/native-reading-time-package/force-exit-ks.sh` 原第 37–40 行，顶层恢复流程：自行选择 READING_FBINK / KMC / libkh 后直接执行 `"$FBINK" -q -f -W GC16 -s`。此进程由独立 Scriptlet/KUAL 入口启动，不知道正在退出的 UI 实际锁定了哪个 runtime。它可能再次执行已失败的候选，返回 139 被 `|| true` 吞掉，或在恢复 Library 后阻塞。这是上一轮遗漏的恢复路径。

本轮只删除上述四行；保留原有 TERM/KILL、PID 清理、两个 sleep、LIPC 输入/休眠复位、Library 启动、日志及提示。历史审计严格验证“原文件仅删除这四行”，没有修改触摸或进程终止逻辑。恢复 Library 已有原生 LIPC 路径，无需加入另一套 FBInk resolver。

辅助改动仅用于验证：`tests/validate_ks.py` 永久拒绝 force-exit 中出现 FBInk；历史审计对这四行作精确例外比对；包哈希检查登记这一真实修复。

## 扫描范围与可达路径

按 `build_v4.sources()` 的 Standard/KS 实际 payload 清单核对全部 Shell、Lua、AWK、Upstart、JSON/XML 入口，并扫描对应生产目录、documents、extensions、RUNME、V4 bootstrap/cleanup。逐文件扫描清单及 SHA-256 存于 `build/validation/final-fbink-static-audit.json`。

- Standard：Scriptlet → launch.sh resolver → optimized UI；渲染 fallback → 已选 runtime 的 legacy UI。
- KS：Scriptlet → launch-ks.sh resolver → KS UI；独立退出 Scriptlet / KUAL / install.sh force-exit → force-exit-ks.sh。
- Standard 旧安装器携带的 legacy UI 也纳入扫描；其每个 framebuffer 命令同样经过 fb()。在当前 V4 的渲染 fallback 中，它继承父 UI 选定的 runtime，不重访已经失败的候选。
- 检查启动、封面、日/月/周/书籍详情、首次/区域/周期刷新、方向恢复、EXIT/信号、强制退出、安装/repair/rollback、卸载及安装文件清理。
- Lua helper 仅处理图像、文字布局、触摸和文件；没有 os.execute / io.popen 调用 FBInk。AWK 无 system() 调用。没有 eval 构造 FBInk 命令。

## 全部 FBInk 执行及 wrapper 调用点

以下每行对应一个静态命令点；同一行的 FAST 与 GC16 分别列出。共 **31 个**：25 个 UI → fb() 调用点，6 个 wrapper 内部二进制执行点。

Standard 文件：`native-reading-time-package/阅读记录-optimized.sh`。

| 行 | 函数 | 调用 | 统一控制 |
|---:|---|---|---|
| 164 | fbink_first_attempt | "$fb_candidate" "$@" | 是，仅由 fb() 首次候选循环调用 |
| 188 | fb | "$FBINK" "$@" | 是，仅 FBINK_LOCKED=1 分支 |
| 227 | ot | fb -q -b -t … | 是 |
| 231 | rect | fb -q -b -B … -k … | 是 |
| 235 | image | fb -q -b -g … | 是 |
| 1327 | refresh_region | fb -q -W GC16 -s | 是 |
| 1328 | refresh_region | fb -q -f -W GC16 -s | 是 |
| 1330 | refresh_region | fb -q -W GC16_FAST -s … | 是 |
| 1330 | refresh_region | fb -q -W GC16 -s … | 是，同 runtime waveform 降级 |

KS 文件：`ks-package/native-reading-time-package/阅读记录-ks.sh`。

| 行 | 函数 | 调用 | 统一控制 |
|---:|---|---|---|
| 190 | fbink_first_attempt | "$fb_candidate" "$@" | 是，仅由 fb() 首次候选循环调用 |
| 214 | fb | "$FBINK" "$@" | 是，仅 FBINK_LOCKED=1 分支 |
| 253 | ot | fb -q -b -t … | 是 |
| 257 | rect | fb -q -b -B … -k … | 是 |
| 261 | image | fb -q -b -g … | 是 |
| 1396 | refresh_region | fb -q -W GC16 -s | 是 |
| 1397 | refresh_region | fb -q -f -W GC16 -s | 是 |
| 1399 | refresh_region | fb -q -W GC16_FAST -s … | 是 |
| 1399 | refresh_region | fb -q -W GC16 -s … | 是，同 runtime waveform 降级 |

兼容界面文件：`native-reading-time-package/阅读记录.sh`；该文件也包含在 KS payload 中，KS 主 UI 不进入 legacy fallback。

| 行 | 函数 | 调用 | 统一控制 |
|---:|---|---|---|
| 120 | fbink_first_attempt | "$fb_candidate" "$@" | 是，fb() 首次实际尝试 |
| 144 | fb | "$FBINK" "$@" | 是，仅锁定分支 |
| 185 | ot | fb -q -b -t … | 是 |
| 191 | ot_white | fb -q -b -m -C WHITE -B BLACK -t … | 是 |
| 197 | ot_center | fb -q -b -m -t … | 是 |
| 203 | rect | fb -q -b -B … -k … | 是 |
| 343 | draw_daily | fb -q -b -g day-N.png … | 是 |
| 430 | draw | fb -q -b -B WHITE -k … | 是 |
| 432 | draw | fb -q -b -g mode.png … | 是 |
| 439 | draw | fb -q -W GC16 -s | 是 |
| 440 | draw | fb -q -f -W GC16 -s | 是 |
| 442 | draw | fb -q -W GC16_FAST -s … | 是 |
| 443 | draw | fb -q -W GC16 -s … | 是 |

## 特殊路径复核

| 路径 | 结果 |
|---|---|
| Standard/KS render_cover | image() → fb()；Lua 封面 helper 不调用 FBInk |
| Standard/KS 背景、统计、日/月/周/书籍详情 | image()/ot()/rect() → fb()；canvas/srect/stext 先写绘图指令，最终仍通过 image() |
| Standard legacy 日期图片、底图、矩形、字体 | 上表列出的 fb() 调用 |
| 两版 refresh_region / legacy draw refresh | 全部 fb()，保留现有 GC16 策略 |
| 两版 launcher restore_native | 只有 LIPC，无 framebuffer 命令 |
| 三个 UI cleanup / EXIT / signal / orientation restore | 回收子进程及 LIPC，无 FBInk 执行 |
| KS force-exit 两个 Scriptlet 入口 / install.sh force-exit | 只转发 helper；helper 已无 FBInk |
| launch.sh / launch-ks.sh 的 KMC/libkh/ABI/PATH 路径 | 仅添加候选和读取 identity，不执行二进制 |
| install.sh 的 FBInk 文件/PATH 检查 | 仅可执行文件存在性，不执行 FBInk |
| diagnostics.sh 的 native_candidate | file/readelf 读取文件；不是执行 native_candidate |
| 安装、repair、rollback、卸载、V4 安装文件 cleanup | 无直接或间接 FBInk 绘制命令 |

没有直接执行硬编码 KMC/libkh 的语句；没有 command -v 后直接执行 FBInk；仅 wrapper 内存在受锁定分支保护的 "$FBINK" 执行。三个 UI 的 fbink_first_attempt / fb / fbink_abort 等函数保持同一实现，没有外部重定义，也没有在绘制过程中重新赋值已锁定 runtime 的旁路。

## 最终结论

- Standard：所有实际 FBInk 调用受现有统一 wrapper / runtime selection 控制。
- KS：包括独立强制退出入口，所有剩余实际 FBInk 调用受现有统一 wrapper / runtime selection 控制。
- 没有剩余绕过 fallback / locked runtime 的路径。未新增功能、未额外重构、未创建 GitHub Release。

相关回归、最终 ZIP 信息及详细执行记录附于下方。

## 修复后验证

KS 结构/布局/Shell 语法、历史保护审计、安装事务/数据保护、KS 完整兼容套件、包 runtime 哈希及源码逐字节匹配全部通过。另执行两个 force-exit 定向场景：指定的 FBInk 分别为 exit 139 和 hang，均零次 FBInk 调用、正常返回 0、恢复 Library。`git diff --check` 退出码 0。

首次 KS 兼容套件在 5.18.2 场景收到非预期 TERM；原始日志保留。该 fixture 未安装 force-exit helper，生产主 UI 本轮也未修改。隔离完整重跑，包括 INT/TERM/HUP、方向、5.19.6 touch reader failure 与 quiet wait 均通过；没有为此修改产品或测试逻辑。

验证记录：[final-fbink-static-audit.json](../build/validation/final-fbink-static-audit.json)。原始完整回归仍保留在 stable-suite-results.json；本次只重跑与唯一旁路修复相关的检查。

## 最终用户包

| 版本 | ZIP | 字节 | SHA-256 |
|---|---|---:|---|
| standard | [ReadingTime-V4.zip](../dist/ReadingTime-V4.zip) | 15189054 | `579b998dc54176e4163eb473503b79b8c2d7976a54ceae13612c980cea5c030a` |
| ks | [ReadingTime-V4-KS.zip](../dist/ReadingTime-V4-KS.zip) | 15182708 | `780447b50296e6f746d07153a5b22459336785dcbf202f77707096121e7d5ef6` |

Standard 包字节未变；KS 包已重建并包含修复后的 helper。两包顶层仍严格只有短 ASCII 安装入口与安装 tar。未发布 GitHub Release。
