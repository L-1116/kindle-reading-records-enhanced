# Kindle Reading Records Enhanced

适用于越狱 Kindle 的原生阅读时长统计插件增强版。当前稳定版本为
`v9.7.1-day-detail`，可在设备上查看月历、阅读热力、周/年统计、书籍筛选和
当天阅读详情。

本项目基于 [Plutoill/kindle-reading-records](https://github.com/Plutoill/kindle-reading-records)
的代码，经原作者授权后继续迭代。本仓库不是上游项目的官方版本；原始工作归
Plutoill，本仓库中的后续增强和维护由 L-1116 完成。

> 这不是 Amazon 官方项目。安装前请确认 Kindle 已越狱，并能运行
> `;log runme`。操作前建议备份 `/mnt/us/reading-time/`。

## 功能

- 原生阅读器处于前台且屏幕亮起时统计阅读时长，锁屏或离开阅读器后停止。
- 月历按日展示阅读热力，可进入当天书籍明细并分页查看。
- 累计页支持本周与年度统计，书籍页支持 7 天、月度和年度筛选。
- 保留真实书籍进度读取、跨午夜拆分、历史数据保护和兼容模式回退。
- 逻辑画布为 1272×1696，并提供等比例缩放和触摸坐标转换。

## 测试版本

`v9.7.2-测试版` 已作为 GitHub Pre-release 提供，新增月份详情、月历/年度月份钻取和最近 8 周趋势。测试版用于提前验证新功能，不作为默认推荐安装版本；希望参与测试的用户请从 [Releases](../../releases) 中明确选择带“Pre-release”标记的版本。

## 界面预览

| 每日时长 | 阅读书籍 | 当天详情 |
|---|---|---|
| ![每日时长](docs/images/daily.png) | ![阅读书籍](docs/images/books.png) | ![当天详情](docs/images/day-detail.png) |

## 安装与回滚

1. 从 [Releases](../../releases) 下载当前稳定版 `v9.7.1-day-detail` 安装包并解压。
2. 将 `RUNME.sh` 和完整的 `native-reading-time-package/` 复制到 Kindle USB 根目录。
3. 安全弹出并断开 USB，在 Kindle 搜索栏执行 `;log runme`。

升级和回滚不会主动替换 `reading-time.tsv`。完整步骤和注意事项见
[安装与回滚说明](docs/安装与回滚.md)。

已重点验证 Kindle Paperwhite 6 / 固件 5.19.6；其他机型和固件需要实机复核。

## 开发与验证

需要 Python 3.11+、POSIX `sh`/`dash`，以及：

```sh
python -m pip install -r requirements-dev.txt
python scripts/validate_all.py
```

验证结果写入 `build/validation/`，安装包写入 `dist/`，两者均不提交到 Git。
`RUNME.sh` 与 `native-reading-time-package/` 始终保持可直接打包的设备目录结构。

## 版本历史

仓库历史由 11 个本地发布快照按继承关系重建，每个快照都有同名 Git 标签。
提交时间取自原快照目录的修改时间，只用于恢复时间顺序，并非原始开发提交记录。
版本摘要见 [CHANGELOG.md](CHANGELOG.md)。

## 授权说明

本仓库不附加通用软件许可证，也不应被视为向第三方授予复制、修改或再发布代码
的许可。上游代码经原作者明确授权在此发布；如需复用，请分别联系相关权利人。

随包 `NotoSansCJKsc-Regular.otf` 字体仍按 SIL Open Font License 1.1 分发，完整
条款见 `native-reading-time-package/FONT-LICENSE.txt`。
