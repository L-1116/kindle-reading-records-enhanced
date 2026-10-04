# Kindle Reading Records Enhanced — 9.7.6-5.19-normal

这是从 `v9.7.5-测试版`（`e41707492b985284d77e0ec5ec5ceffe98209a89`）建立的独立 Standard 主线，仅面向 firmware 5.19.x 的 Kindle 青春版、Paperwhite/KPW 等普通 Kindle。Scribe/KS 和旧固件不适用。

本地安装包：`ReadingTime-9.7.6-5.19-normal.zip`。解压一次，只会得到两个文件：

- `reading-records-9.7.6-install.sh`
- `阅读记录安装数据.tar`

将两个文件一起复制到 Kindle 的 `documents/`，在书库点击“安装阅读记录”。安装后先打开“阅读记录”确认运行正常，再点击“安装好之后，确认无误了再点这个”。清理仅删除安装残留，长期保留正式“阅读记录”入口及所有用户数据。沿用原版本的越狱、Véra/KPM Scriptlet、FBInk/Lua 环境，不要求用户选择 runtime 或执行命令。

保留周统计、每日/月历、阅读书籍、累计时长，日期/月/最近 8 周/书籍详情及单书日历，最近 7 天/本月/今年/全部筛选，Kindle 阅读进度、每页 3 本和原封面提取/fallback。原始 TSV 格式、计时/session/book ID 模型不变。

本轮没有公开发布。横屏方向恢复与实体电源键必须先完成 KPW 5.19 真机验证；真机清单见 `docs/5.19-normal-kpw-checklist.md`。后台完整离线验证：`python scripts/validate_all.py`。`dist/` 为本地用户包，`build/validation/` 为开发验证报告，均不会成为额外用户安装文件。基线旧 RUNME/installer 源文件仅供历史审计，不进入新 payload，也不参与新安装路径。
