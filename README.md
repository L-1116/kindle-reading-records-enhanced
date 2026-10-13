# Kindle Reading Records Enhanced

适用于越狱 Kindle 的原生阅读时长统计插件增强版，可在设备上查看月历、阅读热力、累计统计、最近 8 周、月份详情、阅读书籍、本地封面和单书详情。

当前正式版本：**[9.7.6-5.20.1-vera](https://github.com/L-1116/kindle-reading-records-enhanced/releases/tag/v9.7.6-5.20.1-vera)**。

本项目基于 [Plutoill/kindle-reading-records](https://github.com/Plutoill/kindle-reading-records) 的代码，经原作者授权后继续迭代。本仓库不是上游项目的官方版本；原始工作归 Plutoill，本仓库中的后续增强和维护由 L-1116 完成。

本次为 **Standard 普通版正式发布**，不发布 KS 版。已在 **KPW6（Kindle Paperwhite 12 代）、固件 5.20.1、Vera 越狱**环境完成实机验证，启动、计时、覆盖升级、清理入口名称及自删除功能均正常。

## 本版改进

- **5.20.1 计时服务恢复**：保留服务配置持久副本、健康检查、按需恢复、Upstart 验证、挂载恢复和生命周期锁。正常服务快速返回，避免重复启动计时进程；原计时规则与 TSV 格式不变。
- **启动性能优化**：减少启动链重复校验及不必要的等待，保留实际 framebuffer 命令验证、fallback、单实例锁、横屏和电源恢复。KPW6 实机启动速度已达到可接受水平。
- **两文件简易安装**：首次安装、旧版原地升级和同版修复均自动处理，无需卸载旧版、选择 runtime 或手动安装服务。
- **安全升级与清理**：按真实路径和已知历史内容迁移旧启动及清理入口，保留一个“阅读记录”。清理入口严格显示 **“确认无误之后，再点这个”**，执行后自删除并请求书库 scanner 更新。
- **数据与回滚保护**：历史阅读记录、配置、封面缓存和必要服务保留。安装失败恢复旧状态，旧 release 在确认清理时经逐文件验证且无有效引用后才移除；归属不明的文件保留并报告。

继续保留既有 5.17、5.18、5.19 和 GC16 兼容路径，目标固件名称不意味着只允许该固件运行。本轮实机验收范围为 KPW6 / 5.20.1 / Vera。已安装 KS 的设备会被普通版安装器安全拒绝，不应使用本包覆盖。自动恢复无法补算停服期间未记录的阅读时长。

## 首次安装与覆盖升级

下载本 Release 的 **`9.7.6-5.20.1-vera.zip`**，不要把 GitHub 自动生成的 Source code 压缩包当作安装包。Kindle 需已越狱并具有可用的 SH Integration 书库 Scriptlet 支持。

1. 只解压 ZIP 一次，得到 `reading-records-v4-install.sh` 和 `阅读记录安装数据.tar`；**不要继续解压 tar**。脚本保留已有物理文件名，产品版本为 `9.7.6-5.20.1-vera`。
2. 把两个文件一起复制到 Kindle `documents` 目录，安全弹出。
3. 点击书库 **“安装阅读记录”** 并等待安装完成。旧普通版用户使用相同步骤直接覆盖升级，**无需先卸载或手动删除旧版**。
4. 打开 **“阅读记录”**，确认历史记录和新增计时正常。
5. 点击 **“确认无误之后，再点这个”**。安装文件及已确认无效的旧入口会被安全清理，清理入口随后删除自己，扫描更新后仅保留一个“阅读记录”。

**历史阅读数据可以保留。** 升级与清理不会清空 `reading-time.tsv`、历史备份、用户配置或封面缓存，也不会删除当前 runtime 或必要计时服务。清理入口用于清除安装文件，不卸载插件。scanner 请求接受不等于索引已完成，书库显示更新可能需要等待。

## 验收与安装包校验

已完成 15 项必要离线回归、37 个迁移/故障/清理场景、26 个服务场景及 5 个安装清理后服务恢复场景，并通过上述 KPW6 实机验收。本次直接上传该已验证候选 ZIP，没有在发布过程中修改生产代码或重新构建安装包。

- 文件：`9.7.6-5.20.1-vera.zip`
- 大小：15,222,419 字节
- 构建标识：`fc4e9d8b7c1b4403436e`
- SHA-256：`339a3ff395ca593eff0e2ee851b466decbdabdc7ded521c37b1fee49450de487`

ZIP 顶层严格为两个安装文件。手动上传资产仅有这个 Standard ZIP；KS 构建与交付暂停。原测试基线 `9.7.6-5.20.1-vera-test1` 及既有历史产物、tag 保留。

## 界面预览

| 每日时长 | 阅读书籍 | 当天详情 |
|---|---|---|
| ![每日时长](docs/images/daily.png) | ![阅读书籍](docs/images/books.png) | ![当天详情](docs/images/day-detail.png) |

## 开发与版本记录

发布说明见 [正式版本](docs/releases/9.7.6-5.20.1-vera.md)，源码与包的校验记录见 [发布校验清单](docs/releases/9.7.6-5.20.1-vera-verification.json)，版本历史见 [CHANGELOG.md](CHANGELOG.md)。

开发需要 Python 3.11+、POSIX sh/dash 及 `requirements-dev.txt` 中的依赖。完整离线回归和历史归属清单生成需要开发者本地保存的历史安装包与基线快照；它们不是普通用户的安装依赖，也不作为日志、测试数据或构建缓存提交。`scripts/package_release.py` 默认仅生成 Standard 本地候选；本轮发布直接使用已验证 ZIP。注册测试为 `scripts/validate_all.py`，发布源码校验为 `scripts/verify_published_release.py`。结果与缓存写入 `build/`，本地交付文件写入 `dist/`。

## 授权说明

本仓库不附加通用软件许可证，也不应被视为向第三方授予复制、修改或再发布代码的许可。上游代码经原作者明确授权在此发布；如需复用，请分别联系相关权利人。

随包 `NotoSansCJKsc-Regular.otf` 字体仍按 SIL Open Font License 1.1 分发，完整条款见 `native-reading-time-package/FONT-LICENSE.txt`。
