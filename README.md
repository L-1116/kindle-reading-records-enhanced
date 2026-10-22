# Kindle 阅读记录

适用于已越狱 Kindle 的本地阅读记录插件。原生阅读器处于前台、屏幕亮起时记录阅读时长，可查看月历热力、每日与累计统计、最近 8 周、阅读书籍、本地封面、月份与单书详情。

**[下载最新正式版本](https://github.com/L-1116/kindle-reading-records-enhanced/releases/latest)** · [v9.8.1 发布页](https://github.com/L-1116/kindle-reading-records-enhanced/releases/tag/v9.8.1) · [v9.7.6 其他环境](https://github.com/L-1116/kindle-reading-records-enhanced/releases/tag/v9.7.6) · [安装与原地升级](docs/安装与回滚.md)

新版 **v9.8.1** 提供 **5.20 Vera 与 5.19 Vera Standard 普通版**。5.20 已获 KPW6 / 5.20.1 / Vera test10 蓝牙计时、暂停及启动验收；青春版 test9 启动确认为历史基线；**5.19 已确认 KPW6 / 固件 5.19.6 / Vera 实机测试正常**。其他机型、固件与越狱组合尚未完成本版实机验证；KS（Kindle Scribe）不适用。其他环境按下表选择已验证的 v9.7.6 安装包。**不要下载 GitHub 自动生成的 Source code ZIP，它不是 Kindle 安装包。**

2026-10-22 更新 5.20 Vera 附件：采用已验收 test10 原包，修复蓝牙翻页阅读时长漏记；KPW6 / 5.20.1 / Vera 已确认持续翻页、无操作暂停正常，启动等待约 5 秒降至 4 秒。5.19 附件保持原样，其他机型不据此增加实测声明。

2026-10-22 新增 5.19 Vera 资产：采用 KPW6 / 5.19.6 / Vera 实机验收的 test1 原包，仅更改外层名称，内部 test1 身份保留。

2026-10-19 同版本修复触摸预检查误判：**青春版 2024 / 5.20.1 的 test9 启动已获用户实测确认**，正式包保留该修复。其他非 KS 设备按能力检测，不宣称全部机型均已实测。旧包和旧 Tag 目标在原发布页归档，推荐下载仍为下方同名正式 ZIP。

## v9.8.1 新功能

- **自定义缺失封面**：支持通用替代图片，也可给每本书指定专属图片；已有可用原始封面继续优先使用。历史书籍以双列卡片显示，并标明当前封面来源。
- **新增设置界面**：在插件内管理计时选项和自定义封面。
- **自定义无操作计时上限**：可设置连续多少分钟无操作后暂停计时（1～1440 分钟）；5.20/Vera 当前包支持触摸与蓝牙翻页恢复，5.19/Vera 原包保持原有触摸行为，减少忘记翻页时的误计时；可单独开关。
- **累计时长与阅读书籍 UI 更新**：调整文字、图表和按钮布局；阅读书籍及历史书籍均可点击底部页码直接跳页，历史书籍每页显示 10 本。
- **修复插件界面无法熄屏的问题**，改善停留在插件内时的休眠与恢复行为。

安装完成后，USB 存储中的 `reading-time/custom-covers/` 图片目录即已存在，无需先启动插件或开启封面开关。把 JPG / PNG 图片复制到该目录，再到“设置 → 自定义缺失封面”启用并选择通用或专属图片。自定义封面与无操作暂停计时初始均关闭，已有设置在升级时保留。

[完整发布说明与封面使用方法](docs/releases/v9.8.1.md)。v9.8.1 使用独立的 Release 和 `v9.8.1` Tag，后续适配并验证的其他固件包可作为同一页面的新附件加入。

## 界面预览（旧版参考）

| 每日时长 | 阅读书籍 | 当天详情 |
|---|---|---|
| ![每日时长](docs/images/daily.png) | ![阅读书籍](docs/images/books.png) | ![当天详情](docs/images/day-detail.png) |

## 安装包选择

下列均为 **Standard 普通版**，不能用于 KS（Kindle Scribe）。新版提供下列前两行环境的安装包；其他环境保留 v9.7.6，不包含 v9.8.1 的新功能。

| 固件与越狱方式 | 适用范围与实机证据 | 安装 ZIP |
|---|---|---|
| **v9.8.1：5.20.1 / Vera** | **KPW6 / 5.20.1 / Vera test10 蓝牙计时、暂停和启动实测通过；青春版 test9 为历史启动证据**；其他组合尚未验证，KS 不适用 | [Kindle-Reading-Records-v9.8.1-5.20-vera.zip](https://github.com/L-1116/kindle-reading-records-enhanced/releases/download/v9.8.1/Kindle-Reading-Records-v9.8.1-5.20-vera.zip) |
| **v9.8.1：5.19.6 / Vera** | **KPW6 / 5.19.6 / Vera，2026-10-22 用户实机验收**；内部身份为 `9.8.1-5.19-vera-test1`，其他组合未验证 | [Kindle-Reading-Records-v9.8.1-5.19-vera.zip](https://github.com/L-1116/kindle-reading-records-enhanced/releases/download/v9.8.1/Kindle-Reading-Records-v9.8.1-5.19-vera.zip) |
| v9.7.6：5.20.1（保留 5.17 / 5.18 / 5.19 及 GC16 兼容路径，未据此追加实机结论） / vera | 普通 Kindle（排除 Scribe / KS）；用户确认当前 test2 实机成功，具体机型未注明；此前原基线为 KPW6 / 5.20.1 / Vera | [Kindle-Reading-Records-v9.7.6-5.20-vera.zip](https://github.com/L-1116/kindle-reading-records-enhanced/releases/download/v9.7.6/Kindle-Reading-Records-v9.7.6-5.20-vera.zip) |
| v9.7.6：5.19.x / vera | 普通 Kindle（已验收 KPW6；排除 Scribe / KS）；KPW6 / 5.19.6 / Vera | [Kindle-Reading-Records-v9.7.6-5.19-vera.zip](https://github.com/L-1116/kindle-reading-records-enhanced/releases/download/v9.7.6/Kindle-Reading-Records-v9.7.6-5.19-vera.zip) |
| v9.7.6：仅 5.18.1.1.1 / springbreak | 仅 KPW4（Paperwhite 10 代）；一台 KPW4 / 5.18.1.1.1 / SpringBreak | [Kindle-Reading-Records-v9.7.6-5.18-springbreak.zip](https://github.com/L-1116/kindle-reading-records-enhanced/releases/download/v9.7.6/Kindle-Reading-Records-v9.7.6-5.18-springbreak.zip) |

文件名中的 `5.19`、`5.20` 是环境选择标签，当前确认的目标固件分别为 **5.19.6**、**5.20.1**，不代表各自全部小版本。v9.8.1 延续既有 5.17、5.18、5.19 与 GC16 兼容路径，其他机型和固件组合仍不能据此追加实机结论。v9.7.6 各包来源、范围与校验值见原 Release；KPW4 SpringBreak 包不能扩大为所有 5.18 或其他机型。

## 安装与原地升级

Kindle 须已越狱并具备可用的书库 Scriptlet 执行支持。Vera 包使用 SH Integration；SpringBreak 仅确认上述 KPW4 的书库脚本入口，不假定其他越狱环境的安装方式相同。

1. **先备份 Kindle 的 `reading-time` 文件夹**，包含历史记录、配置和封面缓存。
2. 下载匹配的安装 ZIP，只解压一次；把得到的安装脚本和数据 TAR 一起复制到 Kindle `documents`。**不要继续解压 TAR。**
3. 安全弹出 Kindle，在书库点击“安装阅读记录”，等待安装完成。旧普通版使用相同步骤原地升级，无需先卸载或手动删除原数据。
4. 打开“阅读记录”，确认历史和新增计时正常，再执行该包对应的安装文件清理。

| 安装包 | 解压后复制到 documents 的两个文件 | 清理入口 |
|---|---|---|
| v9.8.1 的 5.19 / 5.20 Vera，以及 v9.7.6 的 5.20 Vera | `reading-records-v4-install.sh` + `阅读记录安装数据.tar` | 确认无误之后，再点这个 |
| v9.7.6 的 5.19 Vera / KPW4 SpringBreak | `reading-records-9.7.6-install.sh` + `reading-records-9.7.6-data.tar` | 安装好之后，确认无误了再点这个 |

清理不是卸载。安装、升级与清理沿用已验证的事务和保护规则，保留阅读历史、用户配置、封面缓存、当前运行资源及必要回滚文件；归属不明的资源不会被当作普通残留随意删除。不要手动清空 `reading-time`。5.20.1 服务恢复无法补算停服期间未记录的时长；KPW4 SpringBreak 每次会话约 120 秒自动退出，也可主动退出。

失败时保留安装文件和备份，通过 [Issues](https://github.com/L-1116/kindle-reading-records-enhanced/issues) 提供机型、固件、越狱方式、操作步骤与错误现象。已有异常日志仅用于售后；普通用户无需执行诊断命令、选择 runtime 或测试二进制。

## 历史版本与开发

[全部历史 Releases](https://github.com/L-1116/kindle-reading-records-enhanced/releases) · [9.7.5 兼容版 V3](https://github.com/L-1116/kindle-reading-records-enhanced/releases/tag/v9.7.5-compat-v3) · [9.7.4](https://github.com/L-1116/kindle-reading-records-enhanced/releases/tag/v9.7.4) · [历史 KS 测试版](https://github.com/L-1116/kindle-reading-records-enhanced/releases/tag/v9.7.5-KS-1)

v9.8.1 与 v9.7.6 分属独立 Release。既有 9.7.6 页面、Tag 与附件保持原样。详细更新见 [CHANGELOG](CHANGELOG.md)、[v9.8.1 发布说明](docs/releases/v9.8.1.md) 和 [v9.7.6 发布说明](docs/releases/v9.7.6.md)。

各环境安装包独立验证，源提交、内部版本与校验值记录在相应 Release。main 仅同步用户文档，运行源码以相应版本 Tag 和发布分支为准。普通用户只需下载 Assets 中匹配环境的安装 ZIP。

## 作者、上游授权与致谢

本项目基于 [Plutoill/kindle-reading-records](https://github.com/Plutoill/kindle-reading-records) 的代码，经原作者明确授权后继续维护。原始工作归 Plutoill，后续增强和维护由 L-1116 完成；本仓库不是上游或 Amazon 的官方版本。

本仓库不附加通用软件许可证，也不应被视为向第三方授予复制、修改或再发布代码的许可；如需复用，请分别联系相关权利人。随包 NotoSansCJK 字体按 SIL Open Font License 1.1 分发，条款见 [FONT-LICENSE.txt](native-reading-time-package/FONT-LICENSE.txt)。
