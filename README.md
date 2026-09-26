# Kindle Reading Records Enhanced

适用于越狱 Kindle 的原生阅读时长统计插件增强版。**建议下载
[`9.7.5 兼容版 V3`](https://github.com/L-1116/kindle-reading-records-enhanced/releases/tag/v9.7.5-compat-v3)**
作为全新安装或原地升级包；
可在设备上查看月历、阅读热力、周/年统计、月份与最近 8 周趋势、当天阅读详情、
本地书籍封面和单书阅读日历。

本项目基于 [Plutoill/kindle-reading-records](https://github.com/Plutoill/kindle-reading-records)
的代码，经原作者授权后继续迭代。本仓库不是上游项目的官方版本；原始工作归
Plutoill，本仓库中的后续增强和维护由 L-1116 完成。

> 这不是 Amazon 官方项目。安装前请确认 Kindle 已越狱，并至少具备
> SH Integration、KUAL 或 `;log runme` 中的一种可用入口。操作前建议备份
> `/mnt/us/reading-time/`。

## 功能

- 原生阅读器处于前台且屏幕亮起时统计阅读时长，锁屏或离开阅读器后停止。
- 月历按日展示阅读热力，可进入当天书籍明细并分页查看。
- 累计页支持本周、年度与全部历史统计，书籍页支持 7 天、月度、年度和全部历史筛选、本地封面与单书阅读日历。
- 保留真实书籍进度读取、跨午夜拆分、历史数据保护和兼容模式回退。
- 逻辑画布为 1272×1696，并提供等比例缩放和触摸坐标转换。

## 推荐版本：9.7.5 兼容版 V3

V3 修复了新书无封面的回归：当 Kindle catalog 中同一个 book ID 有多条记录时，旧兼容版可能提前选中第一条空的 `p_thumbnail` / `p_location` 记录，导致明明存在的 Kindle 缩略图无法使用。V3 会选择有可用缩略图和书籍路径的同 ID 记录。此前已缓存的封面继续保留；《北平无战事(上下册)》和《平凡的世界》的新封面已在真实问题 Kindle 上验证成功。

V3 还把旧“阅读记录卸载”改为**“安装文件清理”**。安装并确认“阅读记录”能正常打开后，点击一次该入口，它只清除本插件安装、测试和封面诊断过程中留下的安装包、临时脚本、调试入口和报告，最后删除清理入口自身。这样 Kindle 书库中长期只保留“阅读记录”，USB 根目录也不再散落安装文件。**它不是卸载，也不是清空阅读数据**：不会停止插件、删除主程序、阅读历史、统计、用户配置或封面缓存；旧 release 也保留。若以后需要再次升级，重新解压完整安装 ZIP 即可。

9.7.4、兼容版 V1/V2 仍可直接覆盖升级至 V3，无需清空数据。V1/V2 是历史公开测试版本，不再建议新用户下载。发现问题可在发布本插件的小红书笔记评论区留言、私信作者或提交 GitHub Issue。

## 界面预览

| 每日时长 | 阅读书籍 | 当天详情 |
|---|---|---|
| ![每日时长](docs/images/daily.png) | ![阅读书籍](docs/images/books.png) | ![当天详情](docs/images/day-detail.png) |

## 安装与安装文件清理

> 请从 [兼容版 V3 Release](https://github.com/L-1116/kindle-reading-records-enhanced/releases/tag/v9.7.5-compat-v3) 的 **Assets** 下载 **`kindle-reading-records-v9.7.5-compat-v3.zip`**；不要下载 GitHub 自动生成的 `Source code` 压缩包，它们不是 Kindle 安装包。

1. 将 ZIP **全部内容**解压到 Kindle USB 根目录，安全弹出设备。
2. 在书库点击“阅读记录安装”（需要 SH Integration）；也可用 KUAL → 阅读记录 → 安装 / 升级，或搜索栏执行 `;log runme`。
3. 确认“阅读记录”可以正常打开，阅读数据和封面正常。
4. 点击书库中的“安装文件清理”。它只删除白名单列出的安装/调试杂文件和自己的入口，不删除插件或用户数据。清理后书库中本插件的长期入口为“阅读记录”。

安装与升级使用同一个 ZIP，保留阅读历史、配置、封面缓存和旧 release。清理前会验证 V3 已正常安装；验证失败时不会删除安装包。完整路径白名单见 [`cleanup-manifest.txt`](native-reading-time-package/cleanup-manifest.txt)，详细说明见 [安装与回滚说明](docs/安装与回滚.md)。

## 开发与验证

需要 Python 3.11+、POSIX `sh`/`dash`，以及：

```sh
python -m pip install -r requirements-dev.txt
python scripts/validate_all.py
```

验证结果写入 `build/validation/`，安装包写入 `dist/`，两者均不提交到 Git。
`RUNME.sh`、`documents/`、`extensions/` 与 `native-reading-time-package/` 始终保持可直接解压到 Kindle USB 根目录的结构。

## 版本历史

仓库早期历史由本地发布快照按继承关系重建，每个正式或测试快照都有对应 Git 标签。
提交时间取自原快照目录的修改时间，只用于恢复时间顺序，并非原始开发提交记录。
版本摘要见 [CHANGELOG.md](CHANGELOG.md)。

## 授权说明

本仓库不附加通用软件许可证，也不应被视为向第三方授予复制、修改或再发布代码
的许可。上游代码经原作者明确授权在此发布；如需复用，请分别联系相关权利人。

随包 `NotoSansCJKsc-Regular.otf` 字体仍按 SIL Open Font License 1.1 分发，完整
条款见 `native-reading-time-package/FONT-LICENSE.txt`。
