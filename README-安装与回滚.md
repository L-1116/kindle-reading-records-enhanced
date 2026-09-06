# Kindle 阅读记录 v9.6.8-summary-sync-fix

本版基于已实机验证的 `v9.6.7-week-view` 做单点修复，原目录未修改。开发、验证和打包均在独立目录 `v9.6.8-summary-sync-fix` 中完成。

## 本版修复

- 修复「累计时长」切换周、切换年或切换「本周 / 今年」后，日期标题与柱状图已更新、顶部摘要却仍显示上一周期的问题。
- 实际原因是累计页的局部刷新矩形从逻辑坐标 y=625 开始，遗漏了 y=380–560 的摘要卡。数据聚合与 framebuffer 绘制原本已经使用最新周期，电子墨水刷新范围没有覆盖摘要。
- 继续使用一次局部刷新：范围现在同时覆盖顶部摘要、本周/今年按钮、周期标题和柱状图；没有改为全屏刷新，也没有重新扫描原始记录。
- 周/年摘要仍由 `render_total` 在每次操作中，紧接当前周期图表数据之后重新聚合；没有独立摘要缓存，也未增加缓存 key。

## 功能变更

### 累计时长

- 二级按钮改为「本周 / 今年」，插件新启动时明确默认「本周」。
- 本周以周一 00:00 至周日 23:59:59 为自然周，每屏固定显示周一至周日 7 根日柱；左右按钮每次移动 1 周，且不允许越过包含今天的当前周。
- 周数据直接从启动时的每日汇总缓存按连续 7 个公历日聚合，使用公历日序号计算周一边界，不依赖 GNU `date -d`。
- 今年保留 1–12 月、年份标题与前后年切换，并限制不能进入未来年份。
- 柱顶使用 `45min` / `1h` / `2h5min` / `9h36min` 格式；纵轴使用自适应整数小时刻度。原始秒数和现有月统计口径未改。
- 总时长、阅读天数和阅读日均均跟随当前选中周或年份；空周期显示 0 分钟、0 天并避免除零。

### 阅读书籍

- 筛选精简为「近7日 / 本月 / 今年」，默认近7日。
- 口径：今天及前 6 个自然日；本月 1 日至今天；当年 1 月 1 日至今天。未来日期记录不进入当前区间。
- 启动时在同一次原始 TSV 扫描中预聚合三个区间；点击筛选只切换临时会话缓存，不重扫原始文件。
- UI 缓存层以 `>=300秒` 过滤；`299秒` 不显示，`300秒` 显示。原始记录、每日与累计统计不受影响。
- 每个区间按该区间阅读秒数降序排列，再每页 5 本分页。切换筛选强制回到第 1 页。
- 长书名延续两行布局；`(`、`[`、`{`、`《` 与后续词组作为轻量换行单元，避免左符号孤立在行末。

## Kindle 商店书进度：只读调查与接入

`/var/local/cc.db` 的 `Entries` 表公开可读字段包含 `p_percentFinished`、`p_lastAccessedPosition`、`p_cdeKey` 和 `p_location`。本插件原先已只读查询 `p_percentFinished`，但仅用完整书名匹配。Kindle 商店书的计时标题与目录显示标题可能不完全一致，这是「时长正常但暂无进度」的高概率原因。

本版继承同一条只读查询读取 `p_cdeKey` 的实现：先用 daemon 已记录的 `cdeKey` 与目录 `p_cdeKey` 精确匹配，再回退到完整书名匹配。不需要解密，不读取/修改 KFX，不修改 `cc.db`、sidecar 或 Kindle 行为。如果目录行没有合法百分比，或内容键/书名都无法精确匹配，仍显示「暂无进度」，不用 location 或文件大小猜测。

公开实机架构记录：[cc.db schema](https://github.com/zevisvei/kindle-reading-dashboard/blob/main/docs/cc-db-schema.md)、[KRDS sidecar format](https://github.com/zevisvei/kindle-reading-dashboard/blob/main/docs/KRDS-format.md)。这些是第三方实机观察，不是 Amazon 官方保证。本轮未获得用户当前 Kindle 的 `cc.db` 副本，所以仍需实机验证这本特定英文书。

## v9.6.8 修改文件

| 文件 | 职责 |
| --- | --- |
| `native-reading-time-package/阅读记录-optimized.sh` | 扩大累计页状态变化时的局部刷新范围，使摘要与图表同时显现；更新版本号 |
| `native-reading-time-package/Install-Native-Reading-Time-Optimized.sh` | 发布目录与版本号 |
| `validate_stats_filters.py` | 增加连续切周、双历史周、周/年切换、跨年切换及局部刷新覆盖测试 |
| `validate_install.py` | 隔离安装、数据保留、daemon 一致性验证 |
| `package_release.py` | 新版 ZIP 与哈希 |

`native-reading-time-daemon.sh`、数据库结构、`reading-time.tsv` 结构、Upstart 配置、每日页面、一级导航和原后备界面均未修改。

## 测试与已知限制

`validation/stats-filters-results.json` 记录离线集成检查，新增覆盖：10小时10分钟/5天/2小时2分钟当前周、空上一周、有数据的另一历史周、连续往返切周、本周与今年往返、2026 与 2025 往返，以及局部刷新矩形完整覆盖摘要、标题和图表。

`validation/installer-results.json` 记录隔离安装验证。离线布局预览为 `validation/total-year.png`、`total-week.png`、`books-7d.png`、`books-month.png`、`books-year.png`。

已知限制：本轮没有连接用户的 Kindle 实机；修复后的 FBInk 局部刷新最终效果仍需在目标设备上复核。

## 安装

1. 退出 Kindle 上的「阅读记录」，USB 连接电脑。
2. 将本目录的 `RUNME.sh` 和完整 `native-reading-time-package` 复制到 Kindle USB 根目录；也可解压 `Kindle安装包-v9.6.8-summary-sync-fix.zip` 后复制这两项。
3. 安全弹出 Kindle，在搜索栏执行 `;log runme`。

安装器发布到 `/mnt/us/reading-time/releases/9.6.8-summary-sync-fix/`，保留历史数据、备份和旧发布目录。

## 回滚到 v9.6.7-week-view

从电脑原目录 `v9.6.7-week-view` 复制其 `RUNME.sh` 和完整 `native-reading-time-package` 到 Kindle USB 根目录，覆盖同名项，安全弹出后再次执行 `;log runme`。

不要删除或替换 `/mnt/us/reading-time/reading-time.tsv`；回滚 UI 不需要回滚阅读历史。新发布目录留在设备上不影响旧版运行。
