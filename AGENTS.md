# KPW4 / 5.18.1.1.1 / SpringBreak 专用候选工程约束

- 精确基线 3acda144ee7bf3a09d7472628efdffd9c09ab240；仅在 SpringBreak 独立 worktree 工作；当前分支 9.7.6-5.18-springbreak，不修改 Vera/5.19/main/KS 或其他工作树，不移植 V4 compatibility。
- 2026-10-14 用户确认该 SpringBreak 版本运行成功并授权公开发布：仅在当前分支更新文档和必要发布校验，提交/push、创建 v9.7.6-5.18-springbreak tag 和同名 Release；只上传原样验证 ZIP。保留其他分支/tag/产物，不 merge、不创建 PR、不 force push。
- 专用身份为 9.7.6-5.18-springbreak；固件精确为 5.18.1.1.1。型号识别须引用上游真实证据，不记录序列号或其他个人信息。
- 复用基线真实 FBInk UI 调用、GC16_FAST/GC16 fallback、只读 Lua evdev 和 Standard 行为。禁止执行 fbink -e 或替换系统 FBInk/Lua/KMC。没有设备证据不重写触摸/ABI 体系。
- Test 1 真机已确认 goodix-ts 漏匹配并误选 bd71827-power。两版选择器动态识别 goodix-ts，保留原名称匹配；覆盖路径必须是可读非链接 evdev 字符节点并通过 sysfs 正向名称识别，优先拒绝 power/snvs。无可靠节点时明确错误退出，禁止无证据 event1 回退或写死 event2。Lua 解析和坐标保持原字节。
- eatTapMode 全程无 get/set；保留 orientationLock/preventScreenSaver 原值和 pending、统一幂等清理、owned child 的 TERM/wait、fork/PID 交接和运行/安装互斥。
- 可研究专用会话时长上限，但须先证明阻塞 reader、旧渲染 fallback、信号、并发、提前退出时进程回收与状态恢复。不声称 SIGKILL、断电、LIPC 或内核阻塞可被保证恢复。
- 保留安装事务/rollback/repair 及白名单清理；禁止删除 reading-time 目录、历史、备份、配置、封面、缓存和核心日志。失败保留安装文件及必要恢复快照。
- 本次发布已有通过确认的 SpringBreak ZIP 原样文件，保留其历史两文件名 reading-records-9.7.6-install.sh 和 reading-records-9.7.6-data.tar；不因其他开发线的命名约定改写已验证包，用户只解压一次。
- 静态审计 → 修改前离线复现 → 最小修改 → 定向验证 → python scripts/validate_all.py 全回归 → 最终归档/manifest/checksum 校验。保留现有断言；身份/目标变化须增加严格断言，不减少覆盖。
- 不要求测试用户执行命令、选 runtime、替换依赖、收集原始事件流或承担开发探测。用户已反馈 Test 2 在 KPW4/5.18.1.1.1/SpringBreak 实机成功；不能扩展到其他型号/固件，也不假设所有退出及异常场景逐项确认。命名之外不修改已测运行逻辑，120 秒保护保持。

# 电脑操控

使用任何接管前台屏幕、占用/移动鼠标、模拟键盘或操纵窗口的能力前，必须明确询问并等待用户同意；完全访问权限或一般任务授权不能替代此同意。未获同意时只用后台/只读工具。
