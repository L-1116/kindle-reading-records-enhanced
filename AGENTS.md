# 9.7.6-5.18-vera 工程约束

- 基线为冻结 9.7.6-5.19-vera，SHA df5fd1e128d6a943435ea0ee8426b8f9f166b250；冻结分支及 worktree 不得修改。不得 merge main 或整体移植 compatibility commits。
- 仅服务 firmware 5.18.x Vera Standard（青春版、Paperwhite/KPW）；不扩展到 5.17/5.19、KS、Scribe 或 Oasis 专项。不加入推测性的 hard-float、framebuffer、touch、launcher workaround、ABI 搜索矩阵、probe/watchdog 或诊断入口。旧 5.18 compatibility 仅用于历史对照；无新设备证据不自动移植。
- 原 Standard Lua 触摸解析、点击区域、tracker daemon、AWK 数据模型、封面提取与 UI 资产保持基线；运行修复应尽量小。
- FBInk 直接执行真正的 UI 命令，不用 -e、help/info 或独立 capability probe 控制启动；真实操作失败必须退出。保留 GC16_FAST 到 GC16 的刷新 fallback。
- launcher 保存、校验并恢复可读写的 orientationLock、preventScreenSaver；修改请求前先设置 pending。eatTapMode 按只写属性处理，运行全程禁止 get/set，不伪造原值或声称写入 0 恢复未知状态。正常、异常、初始化失败和 INT/TERM/HUP 走幂等统一清理，保持 owned child 的终止/wait、fork/PID 交接、Library 后方向恢复和锁顺序。不可独占输入或更改电源键处理。
- 安装/upgrade/repair 保留 reading-time.tsv、备份、配置、历史、封面与统计缓存；只替换运行文件，禁止删除 reading-time 目录。
- ZIP 严格为 reading-records-9.7.6-install.sh 与 reading-records-9.7.6-data.tar；用户将两文件复制进 documents。所有通过 USB/MTP 复制的物理文件名及正式/安装/清理 Scriptlet 必须短 ASCII，中文显示名放在 # Name。
- 清理入口只有文件与服务激活校验成功后才生成，只按显式白名单删除安装残留，最后删除自己；正式入口、runtime、release、daemon、service、数据和核心日志必须保留。
- 顺序：静态审计 → 生产修改前定向复现 → 最小修改 → 定向验证 → 完整离线回归与最终包校验。2026-10-10 修复阶段仅做本地验证；2026-10-11 用户另行明确授权将已验证修复提交并 push 到现有 9.7.6-5.18-vera 分支，更新云端分支并保留历史，不 force push。不创建 tag、Release 或 PR，不修改 main、5.19 分支及其他 worktree；仍为 Pre-hardware candidate，源码备份不等于发布授权。
- 历史 Git 路径清单使用 NUL 分隔；模拟路径只对原字符串替换一次；宿主超时保留日志和断言，publishing 现有 40 秒预算不得机械放宽。CI 分支为 9.7.6-5.18-vera。
- 横屏阅读 → 打开插件 → 正常运行 → 退出 → 恢复原方向的 KPW 5.18 Vera 真机验证是发布 blocker；离线模拟不等于真机通过。

# 电脑操控

使用任何接管前台屏幕、占用/移动鼠标、模拟键盘或操纵窗口的能力前，必须明确询问并等待用户同意；完全访问权限或一般任务授权不能替代此同意。未获同意时只用后台/只读工具。
