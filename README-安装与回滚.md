# Kindle 阅读记录 v9.6.9-calendar-heatmap

本版完整复制自已实机验证的 `v9.6.8-summary-sync-fix`，原目录未修改。本轮只为「每日时长」月历加入固定绝对时长阈值的灰度热力背景，不改整体布局、统计口径、缓存结构、数据库、阅读 daemon、一级导航、阅读书籍页或累计时长页。

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

日期格边框保持原样。普通真实日期只填充边框内部；无阅读日为白底，不显示 `0min`。非本月的首尾空白格只保留原白底。当前选中日期仍用原有灰度 20 的深色整格背景和白字，优先级高于热力色。选中其他日期时，月历在离屏画布上重新合成，因此旧选中格会从同一份原始秒数恢复真实热力灰度。

上一月、下一月、重新进入每日页和插件重新启动都会重新从 `DAYS` 生成目标月份的全部日期格。沿用 v9.6.8 的离屏绘制与刷新机制：整个月历先生成一个 PGM、只发布一次，再对现有必要区域执行一次 GC16 刷新；没有逐格刷新。点击日期仍采用原有低风险路径，重绘月历与下方详情的离屏内容后执行一次区域刷新，未为双 cell 刷新做高风险重构。

## 修改文件

| 文件 | 修改内容 |
| --- | --- |
| `native-reading-time-package/阅读记录-optimized.sh` | 新增 `calendar_heat_level()`、`calendar_heat_gray()`、`calendar_heat_ink()`；在 `render_daily()` 内填充日期格背景；更新版本发布路径 |
| `native-reading-time-package/Install-Native-Reading-Time-Optimized.sh` | 更新新版本发布目录、安装暂存目录和版本标记 |
| `validate_ui.py` | 增加秒级边界、灰度像素、文字颜色、选中恢复、空月/单日/31日、月份切换、页面返回、刷新隔离等离线测试 |
| `validate_install.py` | 将隔离安装目标与保留旧发布验证更新为 v9.6.9 / v9.6.8 |
| `package_release.py` | 生成新版 ZIP，并以 v9.6.8 发布哈希作为不可变基线 |
| `README-安装与回滚.md` | 记录实现、测试、安装和回滚方式 |

`native-reading-time-daemon.sh`、`native-reading-time.conf`、`reading-insights-cache.awk`、`reading-insights-render.lua`、数据库与数据格式均未修改。阅读书籍页和累计时长页的函数片段与 v9.6.8 逐字节一致。

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

模拟月历覆盖：完全空月、仅一天有阅读、Level 1–6 混合、31 天全有数据、月初非星期一、月末不足一周、换月、浅/深灰选择、深灰切浅灰、旧选择恢复、深浅背景文字、Level 6 与选中态区分、详情与本月统计不变、其他页返回、重新生成和旧月灰度清除。

离线 PNG 能验证精确 PGM 灰度与布局，但不能替代 Kindle 实机。相邻灰度在目标电子墨水屏上的主观区分度、GC16_FAST/GC16 的残影表现仍需实机观察；若需调整，只调整灰度值，不改变 30 分、1 小时、2 小时、3 小时、4 小时阈值。

## 安装

1. 退出 Kindle 上的「阅读记录」，USB 连接电脑。
2. 将本目录的 `RUNME.sh` 和完整 `native-reading-time-package` 复制到 Kindle USB 根目录；也可解压 `Kindle安装包-v9.6.9-calendar-heatmap.zip` 后复制这两项。
3. 安全弹出 Kindle，在搜索栏执行 `;log runme`。

安装器发布到 `/mnt/us/reading-time/releases/9.6.9-calendar-heatmap/`，保留阅读历史、备份和旧发布目录。

## 回滚到 v9.6.8-summary-sync-fix

从电脑原目录 `v9.6.8-summary-sync-fix` 复制其 `RUNME.sh` 和完整 `native-reading-time-package` 到 Kindle USB 根目录，覆盖 USB 根目录中的同名项，安全弹出后再次执行 `;log runme`。

不要删除或替换 `/mnt/us/reading-time/reading-time.tsv`。回滚 UI 不需要回滚阅读历史；v9.6.9 发布目录留在设备上不会影响 v9.6.8 运行。
