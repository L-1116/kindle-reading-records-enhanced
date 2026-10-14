# Kindle 阅读记录

适用于已越狱 Kindle 的本地阅读记录插件。原生阅读器处于前台、屏幕亮起时记录阅读时长，可查看月历热力、每日与累计统计、最近 8 周、阅读书籍、本地封面、月份与单书详情。

**[下载最新正式版本](https://github.com/L-1116/kindle-reading-records-enhanced/releases/latest)** · [v9.7.6 统一发布页](https://github.com/L-1116/kindle-reading-records-enhanced/releases/tag/v9.7.6) · [安装与原地升级](docs/安装与回滚.md)

当前正式版本为 **v9.7.6｜多固件兼容版**。在同一 Release 的 **Assets** 中选择匹配固件、越狱方式和机型的安装 ZIP。**不要下载 GitHub 自动生成的 Source code ZIP，它不是 Kindle 安装包。**

## 界面预览

| 每日时长 | 阅读书籍 | 当天详情 |
|---|---|---|
| ![每日时长](docs/images/daily.png) | ![阅读书籍](docs/images/books.png) | ![当天详情](docs/images/day-detail.png) |

## 安装包选择

KS 表示 **Kindle Scribe**。本次三个包均为 Standard 普通版，禁止覆盖 KS；没有提供 9.7.6 KS 或 5.18 Vera 正式包。

| 固件与越狱方式 | 适用范围与实机证据 | 安装 ZIP |
|---|---|---|
| 5.20.1（保留 5.17 / 5.18 / 5.19 及 GC16 兼容路径，未据此追加实机结论） / vera | 普通 Kindle（排除 Scribe / KS）；用户确认当前 test2 实机成功，具体机型未注明；此前原基线为 KPW6 / 5.20.1 / Vera | [Kindle-Reading-Records-v9.7.6-5.20-vera.zip](https://github.com/L-1116/kindle-reading-records-enhanced/releases/download/v9.7.6/Kindle-Reading-Records-v9.7.6-5.20-vera.zip) |
| 5.19.x / vera | 普通 Kindle（已验收 KPW6；排除 Scribe / KS）；KPW6 / 5.19.6 / Vera | [Kindle-Reading-Records-v9.7.6-5.19-vera.zip](https://github.com/L-1116/kindle-reading-records-enhanced/releases/download/v9.7.6/Kindle-Reading-Records-v9.7.6-5.19-vera.zip) |
| 仅 5.18.1.1.1 / springbreak | 仅 KPW4（Paperwhite 10 代）；一台 KPW4 / 5.18.1.1.1 / SpringBreak | [Kindle-Reading-Records-v9.7.6-5.18-springbreak.zip](https://github.com/L-1116/kindle-reading-records-enhanced/releases/download/v9.7.6/Kindle-Reading-Records-v9.7.6-5.18-springbreak.zip) |

文件名中的 `5.20` 是选择标签，当前已确认的目标为 **5.20.1**。该包保留 5.17、5.18、5.19 与 GC16 兼容路径，但这不代表所有组合已完成实机测试。当前 5.20.1 附件内部身份为已验收的 `9.7.6-5.20.1-vera-test2`；具体证据及各包 SHA-256 见统一 Release。SpringBreak 包仅限 **KPW4 / 5.18.1.1.1**，不能扩大为所有 5.18 或其他机型。

## 安装与原地升级

Kindle 须已越狱并具备可用的书库 Scriptlet 执行支持。Vera 包使用 SH Integration；SpringBreak 仅确认上述 KPW4 的书库脚本入口，不假定其他越狱环境的安装方式相同。

1. **先备份 Kindle 的 `reading-time` 文件夹**，包含历史记录、配置和封面缓存。
2. 下载匹配的安装 ZIP，只解压一次；把得到的安装脚本和数据 TAR 一起复制到 Kindle `documents`。**不要继续解压 TAR。**
3. 安全弹出 Kindle，在书库点击“安装阅读记录”，等待安装完成。旧普通版使用相同步骤原地升级，无需先卸载或手动删除原数据。
4. 打开“阅读记录”，确认历史和新增计时正常，再执行该包对应的安装文件清理。

| 安装包 | 解压后复制到 documents 的两个文件 | 清理入口 |
|---|---|---|
| 5.20 Vera（当前目标 5.20.1） | `reading-records-v4-install.sh` + `阅读记录安装数据.tar` | 确认无误之后，再点这个 |
| 5.19 Vera / KPW4 SpringBreak | `reading-records-9.7.6-install.sh` + `reading-records-9.7.6-data.tar` | 安装好之后，确认无误了再点这个 |

清理不是卸载。安装、升级与清理沿用已验证的事务和保护规则，保留阅读历史、用户配置、封面缓存、当前运行资源及必要回滚文件；归属不明的资源不会被当作普通残留随意删除。不要手动清空 `reading-time`。5.20.1 服务恢复无法补算停服期间未记录的时长；KPW4 SpringBreak 每次会话约 120 秒自动退出，也可主动退出。

失败时保留安装文件和备份，通过 [Issues](https://github.com/L-1116/kindle-reading-records-enhanced/issues) 提供机型、固件、越狱方式、操作步骤与错误现象。已有异常日志仅用于售后；普通用户无需执行诊断命令、选择 runtime 或测试二进制。

## 历史版本与开发

[全部历史 Releases](https://github.com/L-1116/kindle-reading-records-enhanced/releases) · [9.7.5 兼容版 V3](https://github.com/L-1116/kindle-reading-records-enhanced/releases/tag/v9.7.5-compat-v3) · [9.7.4](https://github.com/L-1116/kindle-reading-records-enhanced/releases/tag/v9.7.4) · [历史 KS 测试版](https://github.com/L-1116/kindle-reading-records-enhanced/releases/tag/v9.7.5-KS-1)

三个旧 9.7.6 环境发布页、旧 Tag 和原附件继续保留。详细更新见 [CHANGELOG](CHANGELOG.md) 和 [v9.7.6 发布说明](docs/releases/v9.7.6.md)。

各安装包来自独立的已验证分支，真实源提交记录在 Release 正文。统一发布工程可从 [v9.7.6 Tag](https://github.com/L-1116/kindle-reading-records-enhanced/tree/v9.7.6) 查看；main 的本次更新只同步用户文档，没有合并运行分支。维护者的构建与测试要求见 Tag 中的发布流程，普通用户只需下载 Assets。

## 作者、上游授权与致谢

本项目基于 [Plutoill/kindle-reading-records](https://github.com/Plutoill/kindle-reading-records) 的代码，经原作者明确授权后继续维护。原始工作归 Plutoill，后续增强和维护由 L-1116 完成；本仓库不是上游或 Amazon 的官方版本。

本仓库不附加通用软件许可证，也不应被视为向第三方授予复制、修改或再发布代码的许可；如需复用，请分别联系相关权利人。随包 NotoSansCJK 字体按 SIL Open Font License 1.1 分发，条款见 [FONT-LICENSE.txt](native-reading-time-package/FONT-LICENSE.txt)。
