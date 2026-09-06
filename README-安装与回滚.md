# Kindle 阅读记录 v9.6.6-stats-filters

本版唯一稳定基线是 `v9.6.5-ui-polish`，基线目录未修改。开发、验证和打包均在新目录 `v9.6.6-stats-filters` 中完成。

## 功能变更

### 累计时长

- 新增「按周 / 按月」，默认按月。
- 按月保留原 1–12 月、年份标题与前后年切换，不改统计口径。
- 按周以周一 00:00 至周日 23:59:59 为自然周，每屏 8 个连续周；左右按钮每次移动 8 周。横轴显示周一的 `M/D`。
- 周数据启动时从日缓存聚合，使用公历日序号计算周一边界，不依赖 GNU `date -d`。
- 柱顶使用 `45min` / `1h` / `2h5min` / `9h36min` 格式；纵轴使用自适应整数小时刻度。原始秒数和现有月统计口径未改。
- 摘要文案「日均」改为「阅读日均」，算法仍为总阅读时间除以有阅读行为的天数。

### 阅读书籍

- 新增「近7日 / 本周 / 本月 / 今年」，默认近7日。
- 口径：今天及前 6 个自然日；本周周一至今天；本月 1 日至今天；当年 1 月 1 日至今天。未来日期记录不进入当前区间。
- 启动时在同一次原始 TSV 扫描中预聚合四个区间；点击筛选只切换临时会话缓存，不重扫原始文件。
- UI 缓存层以 `>=300秒` 过滤；`299秒` 不显示，`300秒` 显示。原始记录、每日与累计统计不受影响。
- 每个区间按该区间阅读秒数降序排列，再每页 5 本分页。切换筛选强制回到第 1 页。
- 长书名延续两行布局；`(`、`[`、`{`、`《` 与后续词组作为轻量换行单元，避免左符号孤立在行末。

## Kindle 商店书进度：只读调查与接入

`/var/local/cc.db` 的 `Entries` 表公开可读字段包含 `p_percentFinished`、`p_lastAccessedPosition`、`p_cdeKey` 和 `p_location`。本插件原先已只读查询 `p_percentFinished`，但仅用完整书名匹配。Kindle 商店书的计时标题与目录显示标题可能不完全一致，这是「时长正常但暂无进度」的高概率原因。

本版将同一条只读查询扩展为同时读取 `p_cdeKey`：先用 daemon 已记录的 `cdeKey` 与目录 `p_cdeKey` 精确匹配，再回退到完整书名匹配。不需要解密，不读取/修改 KFX，不修改 `cc.db`、sidecar 或 Kindle 行为。如果目录行没有合法百分比，或内容键/书名都无法精确匹配，仍显示「暂无进度」，不用 location 或文件大小猜测。

公开实机架构记录：[cc.db schema](https://github.com/zevisvei/kindle-reading-dashboard/blob/main/docs/cc-db-schema.md)、[KRDS sidecar format](https://github.com/zevisvei/kindle-reading-dashboard/blob/main/docs/KRDS-format.md)。这些是第三方实机观察，不是 Amazon 官方保证。本轮未获得用户当前 Kindle 的 `cc.db` 副本，所以仍需实机验证这本特定英文书。

## 修改文件

| 文件 | 职责 |
| --- | --- |
| `native-reading-time-package/阅读记录-optimized.sh` | 二级状态、8 周视图、h/min 图表、书籍范围/分页、进度 cdeKey 匹配、局部重绘 |
| `native-reading-time-package/reading-insights-cache.awk` | 单次扫描生成周缓存及四个书籍时间范围缓存 |
| `native-reading-time-package/reading-insights-touch-ui.lua` | 新增累计视图、周组和四个书籍筛选命中区 |
| `native-reading-time-package/reading-insights-titles.lua` | 左符号与后续内容同行的轻量换行规则 |
| `native-reading-time-package/ui-calendar/total.png` | 保留卡片/箭头，腾出二级按钮区 |
| `native-reading-time-package/ui-calendar/books.png` | 保留 5 行卡片/翻页区，腾出筛选区 |
| `native-reading-time-package/render-assets/dynamic-glyphs.tsv/.pgm` | 用原 Noto 字体补全新动态文字 |
| `native-reading-time-package/Install-Native-Reading-Time-Optimized.sh` | 发布目录与版本号 |
| `build_ui.py` | 确定性生成底图和字形资源 |
| `validate_stats_filters.py` | 新功能、边界、触控、性能路径与 Lua 合成测试 |
| `validate_install.py` | 隔离安装、数据保留、daemon 一致性验证 |
| `package_release.py` | 新版 ZIP、哈希和预览联络表 |

`native-reading-time-daemon.sh`、数据库结构、`reading-time.tsv` 结构、Upstart 配置、每日页面、一级导航和原后备界面均未修改。

## 测试与已知限制

`validation/stats-filters-results.json` 记录 13 组离线集成检查：四个时间范围、周中日期/未来记录、`4m59s/5m00s`、降序排列、5+1 分页/筛选回首页、四个指定 h/min 值、`12h30min`、按月/按周、前后 8 周、无数据、跨年周、整小时刻度、长中英文和左符号、cdeKey/书名/无进度、Lua 合成与触控命中、不重扫原始 TSV。

`validation/installer-results.json` 记录隔离安装验证。离线布局预览为 `validation/total-month.png`、`total-week.png`、`books-7d.png`、`books-week.png`、`books-month.png`、`books-year.png`。

已知限制：本轮没有连接用户的 Kindle 实机；安装、FBInk 最终字形、局部刷新残影和指定商店书的 `cc.db` 实际行仍需在 PW6 / 目标固件上复核。

## 安装

1. 退出 Kindle 上的「阅读记录」，USB 连接电脑。
2. 将本目录的 `RUNME.sh` 和完整 `native-reading-time-package` 复制到 Kindle USB 根目录；也可解压 `Kindle安装包-v9.6.6-stats-filters.zip` 后复制这两项。
3. 安全弹出 Kindle，在搜索栏执行 `;log runme`。

安装器发布到 `/mnt/us/reading-time/releases/9.6.6-stats-filters/`，保留历史数据、备份和旧发布目录。

## 回滚到 v9.6.5-ui-polish

从电脑原目录 `v9.6.5-ui-polish` 复制其 `RUNME.sh` 和完整 `native-reading-time-package` 到 Kindle USB 根目录，覆盖同名项，安全弹出后再次执行 `;log runme`。

不要删除或替换 `/mnt/us/reading-time/reading-time.tsv`；回滚 UI 不需要回滚阅读历史。新发布目录留在设备上不影响旧版运行。
