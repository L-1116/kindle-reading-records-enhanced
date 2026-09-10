# Kindle 阅读记录 v9.6.10-ui-layout-fix

本版完整复制自 `v9.6.9-calendar-heatmap`，原目录未修改。本轮只修正月历“今天”的视觉编码和周视图横向布局，不改统计口径、缓存结构、数据库、阅读 daemon、数据过滤、PW6 / 5.19.6 兼容处理、一级导航或阅读书籍页。

## 月历热力效果

月历继续使用现有 `DAYS` 会话缓存中的每日累计原始秒数。同一个 `sec` 一方面传给 `calendar_time()` 生成日期格时长文字，另一方面传给 `calendar_heat_level()` 决定背景，不另建数据源，也不重新扫描原始阅读记录。

| Level | 原始秒数边界 | 背景灰度 | 文字颜色 |
| --- | --- | ---: | --- |
| 0 | `t <= 0` | 255 | 黑 |
| 1 | `0 < t < 1800` | 235 | 黑 |
| 2 | `1800 <= t < 3600` | 210 | 黑 |
| 3 | `3600 <= t < 7200` | 180 | 黑 |
| 4 | `7200 <= t < 10800` | 145 | 黑 |
| 5 | `10800 <= t < 14400` | 105 | 白 |
| 6 | `t >= 14400` | 70 | 白 |

现有 Lua compositor 输出最大值为 255 的 8 位 PGM，并将矩形灰度直接写入像素，因此以上 7 个值均为实际写入值，没有抖动或相对归一化。

普通日期继续使用 2 px 黑色边框。所有真实日期（包括今天和当前详情所选日期）的内部背景始终来自上述 heatmap 灰度；无阅读日为白底，不显示 `0min`。今天额外绘制 4 px 粗黑边框，四条边都向格子内部加粗，不侵占相邻日期格，也不改变日期和时长文字的 heatmap 黑白判断。选中日期只决定下方详情内容，不再用深色整格覆盖真实阅读灰度。非本月的首尾空白格仍只保留原白底和普通边框。

上一月、下一月、重新进入每日页和插件重新启动都会重新从 `DAYS` 生成目标月份的全部日期格。沿用 v9.6.9 的离屏绘制与刷新机制：整个月历先生成一个 PGM、只发布一次，再对现有必要区域执行一次 GC16 刷新；没有逐格刷新。点击日期仍采用原有低风险路径，重绘月历与下方详情的离屏内容后执行一次区域刷新，未为双 cell 刷新做高风险重构。

## 周视图布局修正

旧布局在 1122 px 图表画布中把 Y 轴刻度从 `x=7` 开始绘制，同时把周一柱放在 `x=22`、宽 76 px；周一柱和柱顶时长文字因此直接进入刻度区域。

新布局使用同一套整体公式：离屏合成器先按当前字体、字号和最高刻度（如 `3h`、`10h`）测出最长 Y 轴标签的真实墨迹宽度；`axis_text_right = 7 + measured_width`，之后保留 28 px 安全间距，得到 `plot_left = axis_text_right + 28`。右边界固定保留 16 px，即 `plot_right = 1106`，`plot_width = plot_right - plot_left`。周一至周日的柱心统一按 `plot_left + plot_width × (2i+1) / (2×7)` 等分计算，底部星期标签复用相同柱心。柱顶时长文字由合成器按真实字体宽度限制在 `[plot_left, plot_right]` 内；不存在周一专用偏移。

## 修改文件

| 文件 | 修改内容 |
| --- | --- |
| `native-reading-time-package/阅读记录-optimized.sh` | 移除选中日整格覆盖；增加今天的 4 px 内向粗框；按实测 Y 轴标签宽度建立 gutter / gap / plot area，并统一计算柱心与标签边界；更新版本发布路径 |
| `native-reading-time-package/reading-insights-render.lua` | 复用既有 glyph 度量增加只读文字宽度查询，并为柱顶标签增加 plot area 边界约束 |
| `native-reading-time-package/Install-Native-Reading-Time-Optimized.sh` | 更新新版本发布目录、安装暂存目录和版本标记 |
| `validate_ui.py` | 增加今天五种时长的像素/边框/文字回归，以及周一四种时长的 gutter、等距柱心、标签边界和右侧余量检查 |
| `validate_install.py` | 将隔离安装目标更新为 v9.6.10，并验证 v9.6.9 发布仍保留 |
| `package_release.py` | 生成新版 ZIP，并以 v9.6.9 发布哈希作为不可变基线 |
| `README-安装与回滚.md` | 记录实现、测试、安装和回滚方式 |

`native-reading-time-daemon.sh`、`native-reading-time.conf`、`reading-insights-cache.awk`、数据库与数据格式均未修改。周/月/年统计数据准备函数、筛选逻辑和阅读书籍页函数与 v9.6.9 逐字节一致。

## 离线验证

运行：

```sh
python validate_ui.py
python validate_stats_filters.py
python validate_install.py
python package_release.py
```

`validation/results.json` 记录月历和回归测试结果，`validation/stats-filters-results.json` 记录周/年、书籍筛选与 summary 同步回归，`validation/installer-results.json` 记录隔离安装结果，`validation/package-results.json` 记录打包与哈希结果。

热力边界覆盖：0 秒、1 秒、29分59秒、30分、59分59秒、1小时、1小时59分59秒、2小时、2小时59分59秒、3小时、3小时59分59秒、4小时、5小时17分和10小时。

模拟月历覆盖：完全空月、仅一天有阅读、Level 1–6 混合、31 天全有数据、月初非星期一、月末不足一周、换月、选择日期不改灰度、深浅背景文字、详情与本月统计不变、其他页返回、重新生成和旧月灰度清除。今天专项覆盖 0 分、4 分、45 分、90 分和 4 小时，逐像素确认热力内区与 4 px 粗框同时存在。

模拟周图覆盖：周一 0 分、35 分、2 小时和 3 小时 30 分；逐项检查 Y 轴标签右边界、28 px 安全间距、统一 plot area、七个等距柱心、星期标签中心、柱顶文字边界和周日右侧余量。

离线 PNG 能验证精确 PGM 灰度与布局，但不能替代 Kindle 实机。相邻灰度在目标电子墨水屏上的主观区分度、GC16_FAST/GC16 的残影表现仍需实机观察；若需调整，只调整灰度值，不改变 30 分、1 小时、2 小时、3 小时、4 小时阈值。

## 安装

1. 退出 Kindle 上的「阅读记录」，USB 连接电脑。
2. 将本目录的 `RUNME.sh` 和完整 `native-reading-time-package` 复制到 Kindle USB 根目录；也可解压 `Kindle安装包-v9.6.10-ui-layout-fix.zip` 后复制这两项。
3. 安全弹出 Kindle，在搜索栏执行 `;log runme`。

安装器发布到 `/mnt/us/reading-time/releases/9.6.10-ui-layout-fix/`，保留阅读历史、备份和旧发布目录。

## 回滚到 v9.6.9-calendar-heatmap

从电脑原目录 `v9.6.9-calendar-heatmap` 复制其 `RUNME.sh` 和完整 `native-reading-time-package` 到 Kindle USB 根目录，覆盖 USB 根目录中的同名项，安全弹出后再次执行 `;log runme`。

不要删除或替换 `/mnt/us/reading-time/reading-time.tsv`。回滚 UI 不需要回滚阅读历史；v9.6.10 发布目录留在设备上不会影响 v9.6.9 运行。
