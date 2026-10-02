# 原生阅读器横屏遗留状态：启动恢复与自动诊断

本修复基于已经完成的 5.18.1 首次刷新补丁继续修改。固件检测、IS_FW_5181、refresh_region() 和首次渲染阶段记录函数保持原样；方向恢复不按固件版本分支。

已确认的失败链路是：原生阅读器横屏退出后，framebuffer 仍为 landscape → 阅读记录入口进入 launch.sh → optimized detect_screen() 读取横屏尺寸 → 主动 fail，返回 1 → launcher 自动调用 diagnostics.sh → 默认在 documents 创建英文和中文两个 txt，被书库扫描。错误文本来自代码里的竖屏校验，能够解释用户提供的实机错误；尚未在 Kindle 上验证修复后的实际旋转。

现在 detect_screen() 先读取几何尺寸。已经竖屏时不读写 orientationLock、不等待，继续原来的尺寸校验和 viewport 计算。横屏时读取 com.lab126.winmgr orientationLock，只有读取成功且值严格为 U/D/L/R 才保存；读取失败或无效值留空，仍可尝试设置 U。

设置 U 成功后才标记 ORIENTATION_CHANGED=1，立即重读 framebuffer；如果还没有变成有效竖屏，最多执行四次 sleep 1，每次后重读，共约四秒等待。最后一次检查仍未恢复或设置失败时，显示“无法切换为竖屏，请先将 Kindle 调回竖屏后再打开阅读记录”，返回失败。不增加小数 sleep 或无限等待。无法识别几何尺寸仍沿用原有失败路径。

cleanup 和 signal traps 均在 detect_screen() 调用前安装。当前工作区原本就满足这个安装顺序，但原来的 trap cleanup INT/TERM/HUP 并不主动退出，fallback 的 exec 还会丢失当前 shell。现在 INT/TERM/HUP 分别退出 130/143/129，通过 EXIT 统一执行一次 cleanup。正常退出、初始化失败、超时和后续 UI 失败均走同一恢复路径。恢复前清零状态，只写入之前有效的 U/D/L/R；恢复失败记录 result=failed，避免空值、非法值或重复恢复。

另外用 orientation_request_pending 覆盖“设置命令刚返回、成功状态尚未保存时收到信号”的窗口。只有成功返回的设置才令 ORIENTATION_CHANGED=1；信号中断尚未确认的请求时，有有效原方向就尝试恢复。

后台 shell 实测表明：同步命令替换里的子进程阻塞时，sh/dash 会延后执行信号 trap。因此，只有临时切换过方向的会话，才把同一个 Lua 触摸 reader 作为已有子进程启动，用可中断的 wait 等待，结果写入现有会话临时目录再读取。Lua 文件、参数、事件解析和 hitbox 不变；正常竖屏仍执行原来的命令替换。每次交互没有固件检查或进程扫描，没有增加触摸读取进程的数量。

临时切换过方向后进入 legacy fallback 时，optimized shell 保留恢复 trap，等待未修改的 legacy 子进程退出。正常结束后恢复方向，成功 fallback 不重复进行原有回主页刷新。异常中断时，只暂停本会话拥有的子进程，读取一次 /proc/*/stat 确定其后代，终止读取子进程并回收直接子进程，再执行 dashboard cleanup 和方向恢复。这个快照只发生在中断清理时，不是后台轮询；legacy 原文件及原 Lua reader 保持字节不变。

方向诊断写到现有 stdout/dashboard 日志：orientation_original、geometry_before、orientation_force、geometry_after、orientation_restore。launcher 会捕获 last-launch.stdout / last-launch.stderr，退出后合并进 dashboard-launch.log。没有给每个绘制操作增加日志。

diagnostics.sh 新增 READING_DIAGNOSTIC_INTERNAL=1：自动失败固定写到 reading-time/last-launch-diagnostic.txt，忽略可能继承的手动输出路径，不创建 documents 目录，也不复制中文报告。launch.sh 自动失败及入口缺少 launcher 时均使用此模式，入口错误文本也写入 reading-time 内部。默认手动调用及 KUAL“生成诊断”保持原来行为，在 documents 生成 reading-records-diagnostic.txt 和 阅读记录诊断.txt，支持原有自定义报告路径。

验证使用真实 optimized 启动、cleanup、fallback 和 refresh 函数，替换硬件命令及统计/渲染调用。覆盖正常竖屏、R/L/D/U 遗留状态、读取失败/非法值、设置失败、四秒超时、最后一次轮询成功、初始化失败、fallback 正常/异常退出、重复 cleanup、恢复失败，以及旋转等待、设置命令返回窗口、UI 和阻塞 reader/fallback 中的 INT/TERM/HUP。每个案例在 sh/dash 和 5.18.1、5.18.2、5.19.1 下执行；检查子进程没有遗留，并验证旋转完成后的首次刷新。原有 40 个刷新命令基线对比和 30 个启动阶段案例继续运行。诊断测试覆盖 launcher 自动失败、入口自动失败、手动导出和内部模式忽略 documents 路径覆盖。

2026-10-02 离线验证完成：17 项检查全部通过；保留已通过的前 9 项，方向矩阵首次超时后补齐子进程启动信号窗口保护并全量重跑 210 个案例，随后完成剩余 7 项。子进程目标选择另有纯模拟名单测试、复用 PID 保护测试及无关后台进程存活检查。安装/卸载/清理/升级矩阵与本地打包校验通过，包内 resolver 与源码字节一致。过程日志保留首次失败和最终通过结果，位置为 build/validation/orientation-suite.log。与本轮开始时快照比较，环境检测、refresh_region 和 startup_stage 完全一致，112 个其余原有函数体不变。本轮没有真机测试或发布。

仍需实机验证：各机型 winmgr 是否在四秒内让 framebuffer 变为竖屏；恢复 orientationLock 是否保留原生阅读器的实际方向偏好；原生菜单/主页旋转与插件清理的时序；横屏恢复和 5.18.1 non-flashing 首刷共同运行。fbset 不可用时仍沿用原有 virtual_size 高度推断，双缓冲横屏的虚拟尺寸可能有歧义。读取不到原方向时不能恢复未知偏好；LIPC 本身卡住、SIGKILL 或断电不能依靠 shell trap 保证恢复。这些未用无关渲染、统计或触摸系统改动掩盖。
