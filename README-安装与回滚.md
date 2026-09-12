# Kindle 阅读记录 v9.7.1-day-detail

本版完整复制自 `v9.6.10-ui-layout-fix`，旧目录保持不变。本轮只修复月历选中边框，并新增可由月历与周视图共同进入的“当天阅读详情”二级页。阅读 daemon、计时规则、`reading-time.tsv` 格式、缓存聚合口径、热力阈值、周切换与一级页面布局均未改变。

## v9.7.1-install-fix 安装修复

这是基于 `v9.7.1-day-detail` 的纯安装流程热修复，功能版本标记仍为 `9.7.1-day-detail`。修复后的同一安装包同时支持全新安装和旧版升级；`RUNME.sh` 会根据实际 daemon 是否存在自动选择路径，用户无需手动运行包内的两个安装器。

该热修复不改变 daemon、统计循环、界面、触摸、字体、后台服务或阅读数据格式，也不增加常驻进程、数据库或运行时依赖。

## 月历选中状态

- `today_date` 只保存插件启动时的真实系统日期。
- `selected_date` 始终保存完整 `YYYY-MM-DD`，首次进入默认等于 `today_date`。
- 月历粗边框只比较 `cell_date == selected_date`；热力填充仍只由该日原始秒数决定。
- 点击新日期会离屏重绘完整月历与快速预览，再做一次既有区域刷新，因此旧格恢复 2 px、新格得到 4 px 内向边框，不会留下双框。
- 切换月份时将 `selected_date` 设为目标月 1 日，杜绝只比较日号导致的“8月11日也被当作9月11日”问题。

热力阈值保持 v9.6.10 原样：0、30分钟、1小时、2小时、3小时、4小时六个边界，对应灰度 255、235、210、180、145、105、70。选中不会改写灰度或文字黑白。

## 当天阅读详情

统一入口为 `open_day_detail(date, source)`，统一聚合为 `get_day_detail(date)`。后者只读取启动时已经一次性生成的 `DAYS` 和 `DAY_BOOKS` 会话缓存，不扫描原始历史日志。

页面展示完整日期、星期、总时长、书籍数，以及每本书的当天时长和占比。书籍按当天秒数降序；同秒数时按标题稳定排序。比例在总时长大于 0 时四舍五入为整数百分比，0 分钟时不计算比例。

列表按可用高度计算为每页 4 本，超过后显示上一页、页码和下一页；页面切换只重绘列表卡片。无数据日期仍可进入，显示“0分钟”“0本”和“当日暂无阅读记录”。

入口包括：

- 月历下方快速预览标题整行的大触摸区；
- 已选日期格再次点击；
- 周视图七个柱/日期对应的纵向触摸区（仅“本周”模式，年度图不响应）。

返回时按 `day_detail_source` 恢复月历或累计时长页。月历的 `selected_date`、当前年月和快速预览不重置；周视图的 `week_offset` 与周/年状态不重置。

## 修改范围

- `native-reading-time-package/阅读记录-optimized.sh`：完整日期状态、统一详情聚合/渲染/导航、分页和局部刷新。
- `native-reading-time-package/reading-insights-touch-ui.lua`：快速预览、周七日热区、详情分页与返回热区。
- `native-reading-time-package/ui-calendar/day_detail.png`：新增 Kindle 黑白二级页背景。
- `native-reading-time-package/render-assets/dynamic-glyphs.*`：只补充详情页所需静态字形。
- `native-reading-time-package/Install-Native-Reading-Time-Optimized.sh`：发布目录、版本标记与新资源检查更新到 v9.7.1。
- `build_ui.py`、`validate_ui.py`、`checks_polish.py`、`validate_day_detail.py`、`validate_install.py`、`package_release.py`：资源构建、旧回归、新功能回归、隔离安装和打包校验。

`native-reading-time-daemon.sh`、`native-reading-time.conf`、`reading-insights-cache.awk`、`阅读记录.sh`、`reading-insights-touch.lua` 与 v9.6.10 字节一致。

## 离线验证

```sh
python validate_ui.py
python validate_stats_filters.py
python validate_day_detail.py
python validate_install.py
python package_release.py
```

结果分别写入 `validation/results.json`、`stats-filters-results.json`、`day-detail-results.json`、`installer-results.json` 和 `package-results.json`。PNG 可以验证离屏布局与精确灰度，但电子墨水残影和触摸手感仍需 Kindle 实机确认。

## 安装

1. 退出 Kindle 上的“阅读记录”，USB 连接电脑。
2. 将本目录的 `RUNME.sh` 和完整 `native-reading-time-package` 复制到 Kindle USB 根目录；也可解压 `Kindle安装包-v9.7.1-install-fix.zip` 后复制这两项。解压后不应多出一层包装目录。
3. 安全弹出 Kindle，在搜索栏执行 `;log runme`。

脚本会自动判断安装路径：

- 未找到 `/mnt/us/reading-time/bin/native-reading-time-daemon.sh` 时，先完成基础安装，确认 daemon 存在后再继续安装完整的 `9.7.1-day-detail`。已有 `reading-time/` 或 `reading-time.tsv` 但缺少 daemon 的半安装状态也走该路径，阅读历史会保留。
- 已找到 daemon 时，直接走原有 Optimized 升级路径。对未知或被修改 daemon 的 `cmp` 一致性检查仍保持不变，检查失败时不会强制覆盖。

安装器发布到 `/mnt/us/reading-time/releases/9.7.1-day-detail/`，保留阅读历史、已有备份和旧发布目录。

### 故障排查

执行 `;log runme` 后如果 Kindle 图书馆中没有出现“阅读记录”，请重新连接电脑并查看：

```text
/mnt/us/reading-time/install.log
```

日志会说明脚本判定为全新安装还是旧版升级，并标出失败的阶段。普通用户不需要、也不应手动运行两个内部安装器。

## 回滚到 v9.6.10-ui-layout-fix

从电脑原目录 `v9.6.10-ui-layout-fix` 复制其 `RUNME.sh` 和完整 `native-reading-time-package` 到 Kindle USB 根目录，覆盖 USB 根目录中的同名项，安全弹出后再次执行 `;log runme`。

不要删除或替换 `/mnt/us/reading-time/reading-time.tsv`。回滚 UI 不需要回滚阅读历史。
