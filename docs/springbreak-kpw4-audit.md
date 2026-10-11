# 9.7.6-5.18-springbreak 当前记录

2026-10-12 用户反馈 Test 2 实机成功，授权将源码命名并推送为 `9.7.6-5.18-springbreak`，允许公开仓库源码可见但不创建 Release。范围仍为 KPW4 / 5.18.1.1.1 / SpringBreak；120 秒退出仍保留。

Test 2 原源码与 ZIP 在 Git 检查点 `b7684a07715ac85eb9b0a58ef726c8b50e61131b` 及开发者本地保留。当前包仅版本身份变化。新增历史归档重建测试工具，保持 Vera、Test 1、Test 2 原 ZIP SHA 断言，避免克隆后的回归依赖未跟踪的开发目录。详见 `springbreak-hardware-confirmation.md`。

以下为此前 Test 1/Test 2 审计历史；“尚待实机”等状态是当时记录，不覆盖当前用户反馈。

# 9.7.6 SpringBreak / KPW4 Test 2 审计

## 本轮真实证据与最小修复（2026-10-11）

在原独立 worktree 继续，HEAD 仍为 `3acda144ee7bf3a09d7472628efdffd9c09ab240`，未提交修改逐项检查后保留。修改前把全部已有源码、未提交 diff、Test 1 ZIP、完整验证结果和上游证据备份到 `build/test2-audit/test1-source`、`test1-results` 及同目录 Test 1 ZIP；原 `dist` Test 1 包也保留。其他 worktree 状态与所有 refs 记录在 `before.json`，最终须一致。本轮禁止提交/push/tag/merge/PR/Release。

用户提供的真实 Test 1 日志明确枚举 `event0=20cc000.snvs`、`event1=bd71827-power`、`event2=goodix-ts`，而实际选择 `touch=/dev/input/event1`，仅有 watcher started。安装成功，优化 UI 首次绘制 2590ms、fbink_calls=5、fallback=0。此前“不足以证明 event1 错”的判断已被这份新证据更新：两版选择器漏掉 goodix-ts，随后错误默认到电源键。这证明了本次错误选节点，不等于证明所有历史无响应均由同一原因造成。

两版修改前的精确 Test 1 函数在上述 sysfs 布局上离线复现 event1。Test 2 两版使用相同最小选择校验：原 touch/zforce/cyttsp/fts/_ts 匹配加 goodix-ts，优先拒绝 power/snvs；节点必须是 `/dev/input/event` 加纯数字、可读字符节点、非符号链接，名称来自该节点 sysfs。READING_TOUCH_DEVICE 使用同一校验，错误覆盖立即明确报错，不能绕过识别；无覆盖时遍历实际 sysfs，不预设编号。找不到可信触摸节点即 ERROR 并进入原退出清理，不启动 reader 或绘制 UI。不增加设备扫描矩阵或 ioctl 探测。

真实布局 fixture 断言两版选择 event2 且绝不选择 event0/event1；更换 goodix-ts 到 event7 及大小写仍正确。原全部名称规则和正向识别的 Standard event1 保留验证。powerkey/power/带 touch 或 _ts 的电源名称均被拒绝。坏路径、缺设备、普通文件、未知名称、模拟符号链接及错误覆盖全部失败。宿主无法创建 Kindle 字符节点或特权 Windows symlink，类型及链接元数据使用显式 fixture marker；路径/名称/可读检查及 shell 控制流真实运行，生产仍为 `-c/-r/! -L`。测试开发时发现 Git 的 `ln -s` 默认复制文件、严格 native link 权限不足，因此采用明确模拟，不把副本称为真实链接。

安装后的完整 launcher→优化/legacy→reader 两条路径另外验证选中节点传入 reader、切页/退出、失败初始化、方向/休眠恢复、锁清理、安装文件和数据保留。精确 Test 1 ZIP 升级到 Test 2 有失败回滚、重试、repair 和手动清理测试；原全套安装/运行/120 秒退出回归保持。

两版 Lua 固定 16 字节 little-endian evdev，支持 ABS_X/Y、ABS_MT_POSITION_X/Y，完整坐标在 SYN_REPORT 触发动作，忽略 BTN/slot/tracking/SYN_MT_REPORT。已有真实 Lua 5.1 fixture 全部复用；这说明解析器支持上述事件组合。尚无 goodix-ts 原始事件证据，不能宣称真实驱动的事件布局、坐标范围或 SYN 时序已确认，因此 Lua、坐标和 viewport 均不修改。

本轮生产文件：`阅读记录-optimized.sh`、`阅读记录.sh` 只改选择器及 Test 2 身份；`launch.sh`、`install.sh`、`resources/reading-records-install-cleanup.sh`、`documents/reading-records-9.7.6-install.sh` 仅同步身份。120 秒父进程退出循环、cleanup/traps/runtime helpers、固件/型号限制及安装事务逐字节保持 Test 1；FBInk/字体/daemon/统计/封面/UI 资产/两版 Lua 全字节保持。测试工具中的旧“选择器全字节未改”断言改为严格逆变换仅准许指定选择器差异，原断言保留并增加新行为覆盖。

最终实际计数及 ZIP/TAR/manifest/checksum 在 `build/validation/springbreak-final-report.md`。安装说明为 `docs/中文说明.md`。仍需真机确认 goodix-ts 实际事件能触发按钮、正常及到期退出、回书库后的原生触摸/方向/休眠；首绘成功不能代替其他绘制/刷新路径验证。不要求用户命令或原始事件采集。

## 以下保留 Test 1 修改前历史审计

以下有关“event1 尚未证实错误”“未改选择器”的文字是 Test 1 当时证据的历史记录，当前结论以本节 Test 2 真实日志及修复为准。

2026-10-11，状态：Pre-hardware candidate。基线为远端和本地均核对一致的 `3acda144ee7bf3a09d7472628efdffd9c09ab240`；独立分支 `9.7.6-5.18-springbreak-kpw4`，仅本地操作。主目录已有其他工作，本轮不使用或改动；Vera、5.19、main、KS 及 V4 发布历史保持原样。最终执行结果、完整计数、包大小及 SHA-256 由 `scripts/report_springbreak.py` 从实际结果生成，位于 `build/validation/springbreak-final-report.md`。

## 依赖调查的事实与边界

SpringBreak README 描述其利用链最终运行在线 `jb.sh`；Véra 的 `privesc.sh` 同样执行 `curl -L https://kindlemodding.org/jb.sh | RUN_MODE=1 sh`。它们的漏洞入口不同，不能据此认定安装后的 Lua/FBInk ABI 不同。调查时没有连接测试 Kindle，无法证明她和 Vera 测试设备已安装的 KMC 版本、符号链接目标、ELF 解释器和库字节相同或不同。

当前统一 `jb.sh` 为 `72ab85c7efe211b9ab5757410d48ec73b504d345`。其 helpers 默认平台 `kindlepw2`，检测 `/lib/ld-linux-armhf.so.3` 后选 `kindlehf`；setup_kmc 将 `/var/local/kmc/bin`、`lib` 链接到所选平台，还复制 FBInk 至 `/mnt/us/libkh/bin/fbink`。因此 Vera 分支实际使用的 `/var/local/kmc/bin/fbink` 是上游支持的路径；不应因为越狱名称而改为另一套运行体系。

旧 Universal Hotfix 使用 `armel/armhf` 目录，当前统一 jb.sh 使用 `kindlepw2/kindlehf`。这是已证实的**上游安装代际差异**，不是已证实的“她的 SpringBreak 与 Vera 真机差异”。两者都有按平台准备的 FBInk 和 SH Integration；SH Integration launcher 通过 su 运行登录 shell。不能仅按 5.18 固件号、CPU 型号或越狱名称推断 soft/hard-float。

统一 jb.sh 构建 FBInk、SH Integration、KPM 和 system patcher，并启用 bitmap/draw/fonts/image/opentype。其 meson patch 把 FBInk CLI 链入 `fbink_static_lib`，并非必须动态加载同目录 `libfbink.so`；这不表示 CLI 无 libc/解释器依赖，也不证明她实际安装的二进制如此构建。调查的构建任务未发现负责安装插件所需 Lua 的任务，不能把 KPM 存在等同于特定 Lua 版本已存在。

插件实际调用 PATH 中的 `lua`，渲染和监听器用 Lua 5.1 可用的标准库，没有引入 LuaJIT FFI 或 lua-fbink 模块；外部 shell 还使用 Kindle 原有 LIPC、fbset、awk、cksum、SQLite、unzip 等工具。历史 Test 2 的 Lua 通过可作旧环境参考，不能证明当前 PATH、解释器和当前所有绘制路径已通过。本次不安装/替换系统依赖，不改 PATH 或 LD_LIBRARY_PATH，不加入 ABI 搜索矩阵。

固定上游证据保存在开发目录 `build/springbreak-audit/upstream`（只读下载，不执行）；关键来源：

- [SpringBreak README](https://github.com/KindleModding/SpringBreak/blob/665a6560ed3a15c5c180594422fb65ca82e15594/README.md)
- [Véra privesc](https://github.com/KindleModding/kindlemodding.github.io/blob/81d049d340edea6dbd39700a99072b2151300731/static/vera/aprivesc/privesc.sh)（本地证据另存固定 SHA）
- [平台选择](https://github.com/KindleModding/jb.sh/blob/72ab85c7efe211b9ab5757410d48ec73b504d345/src/helpers/00_helpers.sh)
- [KMC 路径设置](https://github.com/KindleModding/jb.sh/blob/72ab85c7efe211b9ab5757410d48ec73b504d345/src/jb_sh_jobs/04_setup_kmc.sh)
- [原生组件构建](https://github.com/KindleModding/jb.sh/blob/72ab85c7efe211b9ab5757410d48ec73b504d345/build_jobs/02_build_natives.sh)
- [FBInk 链接方式](https://github.com/KindleModding/jb.sh/blob/72ab85c7efe211b9ab5757410d48ec73b504d345/fbink_patch/meson.build)

## 历史故障与触摸结论

只读对照 v4-test.1/.2/.3、`0dc8c1b`、`3c7034b` 和精确 Vera HEAD，记录在 `history-source-audit.json`；没有 merge/cherry-pick/执行历史二进制。仓库历史版本不能自动等同于她手里旧 ZIP 的字节，缺旧包 checksum 和完整设备元数据时不声称精确匹配。

最新 Vera 两套实际 UI 使用真实 FBInk 绘制，启动链不以 `fbink -e`、help/info 等探测控制启动。本候选保留这些真实命令和 GC16_FAST → GC16 fallback。Test 2 的 `-e` 崩溃入口已经绕开，并非已修复 FBInk 本身。真正的图片/字体/清屏/刷新调用仍可能因链接器、ABI、缺依赖、framebuffer ioctl 或二进制问题失败；离线模拟真实 UI 命令返回 139 时验证了退出/状态恢复，而没有制造真实 SIGSEGV。

`find_touch_device()` 的实际次序为：可读的已有环境 override → sysfs 名称匹配 touch/zforce/cyttsp/fts/_ts 且节点可读 → 默认 event1。可读仅证明可以打开，不证明该节点送来触摸事件。两个 Lua reader 都固定读 16 字节、按 little-endian 偏移解析，支持 ABS_X/Y 和 ABS_MT_POSITION_X/Y；只在 SYN_REPORT 且 X/Y 完整时产生 tap，忽略其他类型/MT slot/tracking/key 事件。没有 BTN_TOUCH 门槛或 EVIOCGRAB。没有支持 24 字节布局、ABS 范围归一化、复杂多点 slot 状态或 SYN_DROPPED 重同步；缺实机证据，不扩写这些行为。

上游 KOReader 的 PW4 默认是 Wi-Fi event2、LTE 可能 event3，说明默认 event1 不是可靠的 PW4 型号结论；编号也不能直接照搬到她当前固件。现有选择器会优先识别驱动名称。真实 sysfs 名称、选中节点、是否送事件及 ABI 尚未取得，不能仅因无 tap 日志认定 event1 错。本候选不改变设备识别或 Lua 解析，在 launcher 启动日志一次记录 event 的名称；已有 `display-layout.txt` 记录真正选择的节点。

修改前对两个原始 Lua 文件执行了真实 Lua 5.1 事件 fixture：16 字节 ABS、MT、BTN/slot/SYN_MT、跨 SYN 的缺一轴组合能命中退出；非触摸事件、缺 Y、24 字节布局均能产生 watcher 但无 tap；越界坐标则会有 tap、无 mapped。因此历史 no-tap 不能由纯 viewport 偏移解释，也不能从多个可复现原因中选定一个。没有记录设备原始事件流。

1072×1448 的整数等比布局恰好是 1072×1429+0+9。fixture 在此 viewport 验证了两套 reader 的坐标映射。上游 [KOReader Kindle device](https://github.com/koreader/koreader/blob/0deae50039d414c5fbd179aec7096fd798b4ff37/frontend/device/kindle/device.lua) 和 [FBInk device ID](https://github.com/NiLuJe/FBInk/blob/886f25f13368859ad8a899b88d04c26e19cda32e/fbink_device_id.c) 的固定版本及哈希另存开发证据；上游代码是模型依据，不是真机事件采样。

## 安全退出与数据保护

修改前运行实际 launcher/UI 壳，模拟 reader 阻塞，sh/dash 中确认它会一直等待；外部 TERM 能走现有清理并恢复。专用 launcher 在 UI PID/gate 交接后增加固定 120 次 sleep 1 的会话上限。父进程轮询自己拥有的 UI，不生成独立计时/watchdog 子进程，不向其他 PID 或服务发信号。到期返回 124，进入原有 EXIT 清理：终止/wait UI；UI 终止/wait reader 或 legacy；恢复原 preventScreenSaver；请求 Library；再恢复原 orientationLock；最后释放互斥锁。

没有改动 cleanup 函数、runtime-child、runtime-lock、信号处理或 fork 交接；没有 eatTapMode get/set。120 秒不是硬实时承诺：进程调度、系统命令和清理需要时间；初始化阶段 LIPC 先于会话计时。SIGKILL、断电、无响应 LIPC 或不可中断的内核 I/O 仍不能保证恢复。本次没有宣称解决全部设备卡死。定向测试同时覆盖优化 UI/legacy、U/R 方向、0/非零 power、拒绝第二个启动、到期后重开；完整原矩阵保留 INT/TERM/HUP、fork/PID、安装/运行竞争。长会话模拟只加速 mock sleep，另用真实 sleep 和 2 秒字面量验证阻塞 child 回收，不要求用户调环境变量。

原 launcher 请求 `app://com.lab126.KPPMainApp?view=KPP_LIBRARY`；SpringBreak 的 static 页面调用 `com.lab126.booklet.home`。这是可见入口字符串差异，可能涉及应用入口或别名，不能推断她设备上前者无效；本次没有以此加入猜测性 appmgr fallback。调查的 SH Integration launcher 在退出时还有原生 booklet 退出/部分环境 xrefresh 行为，插件不能把其外部时序当成已经验证。真正回到书库、复画及之后的方向恢复仍是实机项。另外，会话上限专门覆盖 reader 阻塞；渲染期间如果前台子命令永久阻塞、导致 UI shell 的 TERM trap 无法及时运行，原来的 wait 清理也不能提供硬时限保证。

安装器精确接受 5.18.1.1.1；型号基于 KOReader PW4 已知 21 个非唯一产品代码，`dd` 只读 `/proc/usid` 的第 4–6 字节，随后 unset，既不读取完整序列号也不记录该字段。不能确认时在事务和停服务前拒绝。标准 pen/屏幕及 KS 混装拒绝继续保留。没有利用未知的营销名称、猜测 board_id 或分辨率充当型号证明。

生产改动仅为：

| 文件 | 目的 |
|---|---|
| `native-reading-time-package/launch.sh` | 专用 release、一次启动诊断、120 秒会话上限；其余逐字节保持 |
| `native-reading-time-package/install.sh` | 专用身份、精确固件、可靠产品代码拒绝；事务/回滚不改 |
| `native-reading-time-package/阅读记录-optimized.sh`、`阅读记录.sh` | 仅 release 身份同步，不改触摸/绘制 |
| `native-reading-time-package/resources/reading-records-install-cleanup.sh` | 仅版本检查同步，白名单和顺序不改 |
| `documents/reading-records-9.7.6-install.sh` | 不再截断 install-last.log，追加本次安装分隔行 |

启动诊断只复用 `dashboard-launch.log`，记录候选身份、Lua 路径、KMC bin/lib 链接、FBInk 文件 cksum、输入节点名称。没有执行 FBInk probe，不采集账户/序列号/正文，也不影响每次 UI 页切换。安装失败不会自动删除用户安装文件；清理入口仍是明确手动操作，说明要求失败后保留。

所有未列出的 payload 源、两套 Lua、字体/UI 资产、计时 daemon、统计/封面、runtime helpers 均与精确基线一致。打包脚本、AGENTS、README、变更记录、测试/报告工具同步本地专用目标。测试改动包括身份路径更新、原版本实际包重建、新增严固件拒绝、日志保留和会话上限矩阵。原宽 5.18 parser 用例仍执行精确历史 install.sh；新固件/型号限制另执行当前 install.sh。原事务、回滚、运行断言继续针对最终候选，旧包 SHA 断言保留。没有删除/跳过已有断言；launcher/installer 的允许差异逆变换后还与基线全字节比较。

安装事务只替换文件及专用 release，不删除整个 reading-time。真实最新 Vera payload → 候选失败回滚 → 重试 → 同版 repair → 手动清理矩阵校验 reading-time.tsv、历史/备份、配置、封面、统计缓存、旧 release 和核心日志。安装日志初始化截断行为在修改前已单独复现；当前追加，测试断言只解析最新 BEGIN 段，实际文件保留前段。恢复失败继续保留快照及安装文件。

## 交付与剩余实机项

最终完整回归与 ZIP/TAR/manifest/checksum 报告以生成结果为准。ZIP 两文件、ASCII 名、正常覆盖安装均沿用基线。包只在开发者本地生成，不提交/push/tag/merge/PR/Release，不增加公开诊断包。

仍需她的设备确认实际 KMC 链接/FBInk 和 Lua、真实绘制、选择的 input 节点与事件、月历触摸/原生触摸穿透、正常及到期退出、L/R 方向与自动休眠恢复。自动退出已离线证明，实机 LIPC/驱动响应没有证明。失败只复制已有几份插件日志；不要求命令、系统日志/个人信息、原始触摸流、runtime 选择或重装越狱。中文简短说明见 `springbreak-kpw4-install-test.md`。
