# Kindle 阅读记录 v9.6.4-ui-calendar

本版本仅复制自 `v9.6.3-optimized-pw6-5.19.6-cmp-fix`，面向已安装该版本的 Kindle Paperwhite 6 / 固件 5.19.6。源基线目录没有修改。没有使用另外两个历史目录的实现。

## 本轮修改

- Tab 改为「每日时长 → 阅读书籍 → 累计时长」，启动默认每日时长。
- 月历周一开始，七列、按月份四至六行；每格黑色边框，选中整格反白；日期和当日时长同格显示，空日期不显示时长。格内没有书名、黑点或图例。
- 逻辑画布仍为 1272×1696。月历点击格宽 154，高 90/109/138，间隔 6；以前的选中块是 105×78。整格含边框可点击，格间隙与月首/月尾空位不可点击。
- 保留左右月份导航，切月选中第一天；本月阅读天数和累计时长放在月历下方，留出内边距。
- 每日详情书名增大，时长改用较小的常规字重。长书名最多两行，超出用省略号，避免覆盖右侧时长与下一本书。
- 阅读书籍页书名放大，时长与百分比减弱字重；保留进度条、每页五本，以及上一页/下一页原有逻辑和样式。
- 日均按原始总秒数和阅读天数计算，再四舍五入到分钟；246 分钟 / 4 天显示 1小时2分钟。零阅读天数显示 0分钟。
- 年度柱状图保持底部坐标位置，绘图区顶部上移 120 个逻辑像素，高度从 470 扩至 590；没有新增动画、阴影或颜色状态。

时长显示：月历中不足一分钟显示秒数，例如 25秒；一分钟以上显示 18分、1时18分。原始秒数不变；总时长与月度摘要仍使用分钟精度，只有日均新增四舍五入。

## 修改文件清单（相对 native-reading-time-package）

修改：

1. `阅读记录-optimized.sh`：页面状态、布局、日均显示、标题调用和对应局部刷新范围。
2. `Install-Native-Reading-Time-Optimized.sh`：独立发布路径 `releases/9.6.4-ui-calendar`，安装新增资源；保留 PW6 固件所需的 `cmp -s` 检查流程。

新增：

3. `reading-insights-touch-ui.lua`：新版 Tab 与日历点击区域；沿用原输入事件读取、屏幕缩放及坐标转换。
4. `reading-insights-titles.lua`：只读书名换行、截断，不改变书名数据或进度匹配。
5. `reading-insights-title-widths.lua`：从原 Noto 字体生成的 ASCII 字宽表，用于限制书名占位。
6. `ui-calendar/daily.png`
7. `ui-calendar/books.png`
8. `ui-calendar/total.png`

交付辅助文件：`build_ui.py`、`validate_ui.py`、`validate_install.py`、`package_release.py`、本说明及 `validation/` 验证记录/预览。辅助文件无需复制到 Kindle。

原始 `ui/`、`render-assets/`、`reading-insights-render.lua`、`reading-insights-touch.lua`、`阅读记录.sh`、字体、计时守护进程、Upstart 配置和统计 AWK 全部保持原文件内容。新版资源与兼容后备资源分离，避免后备界面出现触控错位。

## 安装到 Kindle

1. 在 Kindle 上退出「阅读记录」，再通过 USB 连接电脑。
2. 将本版本目录中的 **`RUNME.sh` 文件**和**整个 `native-reading-time-package` 文件夹**复制到 Kindle USB 根目录，同名文件选择覆盖。文件夹内部结构必须完整保留。
3. 根目录应能看到 `RUNME.sh` 以及 `native-reading-time-package/Install-Native-Reading-Time-Optimized.sh`，不要多套一层 `v9.6.4-ui-calendar` 目录。
4. 安全弹出 Kindle。在 Kindle 搜索栏输入 `;log runme` 并执行，沿用当前基线的安装入口。
5. 等待安装成功提示后，在书库打开「阅读记录」。默认应进入左侧「每日时长」。

也可以使用附带的 `Kindle安装包-v9.6.4-ui-calendar.zip`，解压后将里面上述两项复制到 Kindle 根目录；不要直接把 ZIP 留在设备上当作安装。

不需要手动复制单个 Lua/PNG 到已安装目录。安装器会将新版界面放进 `/mnt/us/reading-time/releases/9.6.4-ui-calendar/`，并更新 `/mnt/us/documents/阅读记录.sh`。它仍使用基线的安装流程，会短暂停止、恢复计时服务，并校验守护进程完全一致；没有改变计时规则或清除阅读历史。

## 恢复到当前基线

1. 退出阅读记录，通过 USB 连接 Kindle。
2. 从电脑原目录 **`v9.6.3-optimized-pw6-5.19.6-cmp-fix`** 复制其 `RUNME.sh` 和整个 `native-reading-time-package` 到 Kindle 根目录，覆盖同名文件。
3. 安全弹出 Kindle，搜索栏执行 `;log runme`，等待原版安装成功。
4. 重新打开阅读记录，即恢复本轮开始前的优化版界面。新版发布目录留在设备上也不会被调用。

不要删除或用旧副本覆盖 Kindle 的 `reading-time/reading-time.tsv`；回滚界面不需要回滚阅读数据。请使用指定的 cmp-fix 基线包，不要用另外两个历史目录。

## 验证及实机复核

离线验证细目见 `validation/results.json`。Shell/Lua 语法、1900—2100 年 2,412 个月份、263,634 个日期格点击位置、跨月跨年、空月份、时长范围、中英文长标题、实际 Lua 合成器输出，以及后台文件逐字节不变等 14 组检查全部通过。额外检查了图元/字形是否越出画布。

`validation/installer-results.json` 记录隔离目录中的安装验证：计时程序不一致时会在停止服务前拒绝安装；正常安装时新版文件完整落位、阅读数据和原发布目录保留。验证中 Kindle 服务、根分区及提示命令均被替代，未操作真实设备。预览 PNG 由实际 Lua 绘图结果与近似 FBInk 文本合成，没有通过桌面浏览器模拟 Kindle。

本轮尚未在物理 Kindle 上运行新版。设备上请重点查看六行月历的时长字号、长书名两行间距、月历格边缘点击和选日后的残影。遇到安装或渲染问题，可以保留 `reading-time/install.log`、`dashboard-launch.log`、`dashboard-touch.log` 和 `display-layout.txt` 供定位。

保留的基线行为：每日详情最多显示当天时长最多的三本书；「阅读书籍」仍按累计时长排序，并非最近阅读时间排序。如果渲染失败，原有后备机制会提示兼容模式并显示原界面。本轮没有扩展这两处列表逻辑或改写后备界面。
