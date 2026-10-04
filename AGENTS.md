# 9.7.6-5.19-normal 工程约束

- 基线为 v9.7.5-测试版，SHA e41707492b985284d77e0ec5ec5ceffe98209a89；不得 merge main 或整体移植 compatibility commits。
- 仅服务 firmware 5.19.x Standard（青春版、Paperwhite/KPW）；不引入 5.17/5.18、KS、Oasis 专项、ABI 搜索矩阵、probe/watchdog 或诊断入口。
- 原 Standard Lua 触摸解析、点击区域、tracker daemon、AWK 数据模型、封面提取与 UI 资产保持基线；运行修复应尽量小。
- FBInk 直接执行真正的 UI 命令，不用 -e、help/info 或独立 capability probe 控制启动；真实操作失败必须退出。保留 GC16_FAST 到 GC16 的刷新 fallback。
- launcher 统一保存/恢复 orientationLock、eatTapMode、preventScreenSaver；正常、异常、初始化失败和 INT/TERM/HUP 走统一清理。不可独占输入或更改电源键处理。
- 安装/upgrade/repair 保留 reading-time.tsv、备份、配置、历史、封面与统计缓存；只替换运行文件，禁止删除 reading-time 目录。
- ZIP 严格为 reading-records-9.7.6-install.sh 与 reading-records-9.7.6-data.tar；用户将两文件复制进 documents。所有通过 USB/MTP 复制的物理文件名及正式/安装/清理 Scriptlet 必须短 ASCII，中文显示名放在 # Name。
- 清理入口只有文件与服务激活校验成功后才生成，只按显式白名单删除安装残留，最后删除自己；正式入口、runtime、release、daemon、service、数据和核心日志必须保留。
- 完成完整离线回归与包校验；本轮只做本地提交和本地交付，不 push、不 tag、不发布 GitHub Release。
- 横屏阅读 → 打开插件 → 正常运行 → 退出 → 恢复原方向的 KPW 5.19 真机验证是发布 blocker；离线模拟不等于真机通过。

# 电脑操控

使用任何接管前台屏幕、占用/移动鼠标、模拟键盘或操纵窗口的能力前，必须明确询问并等待用户同意；完全访问权限或一般任务授权不能替代此同意。未获同意时只用后台/只读工具。
