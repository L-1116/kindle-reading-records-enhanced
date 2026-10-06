# Kindle Reading Records Enhanced — 9.7.6-5.18-vera

这是从冻结 `9.7.6-5.19-vera`（`df5fd1e128d6a943435ea0ee8426b8f9f166b250`）建立的独立开发线，状态为 **Pre-hardware candidate**，仅面向 firmware 5.18.x + Vera 的 Kindle 青春版、Paperwhite/KPW 等普通 Kindle。5.17、5.19、Scribe/KS 不适用。

本地安装包：`ReadingTime-9.7.6-5.18-vera.zip`。解压一次，只会得到两个文件：

- `reading-records-9.7.6-install.sh`
- `reading-records-9.7.6-data.tar`

将两个文件一起复制到 Kindle 的 `documents/`，在书库点击“安装阅读记录”。安装后先打开“阅读记录”确认运行正常，再点击“安装好之后，确认无误了再点这个”。清理仅删除安装残留，长期保留正式“阅读记录”入口及所有用户数据。沿用原版本的越狱、Vera Scriptlet、FBInk/Lua 环境，不要求用户选择 runtime 或执行命令。

USB/MTP 复制用的物理文件名统一使用短 ASCII；中文显示名保留在 Scriptlet 的 `# Name`。安装入口排除重复点击，解包前检查临时空间，事务开始前检查安装和备份空间。空间不足或无法可靠读取容量时保留两个安装文件及旧运行版本，并提示“存储空间不足”；请在正常管理存储后重新安装。回滚无法完整恢复时保留恢复快照，位置记录在 `reading-time/install-last.log`。

保留周统计、每日/月历、阅读书籍、累计时长，日期/月/最近 8 周/书籍详情及单书日历，最近 7 天/本月/今年/全部筛选，Kindle 阅读进度、每页 3 本和原封面提取/fallback。原始 TSV 格式、计时/session/book ID 模型不变。

本轮没有公开发布。横屏方向恢复与实体电源键必须先完成 KPW 5.18 Vera 真机验证；本轮审计及待真机观察项见 `docs/5.18-vera-pre-hardware-candidate.md`。后台完整离线验证：`python scripts/validate_all.py`。`dist/` 为本地用户包，`build/validation/` 为开发验证报告，均不会成为额外用户安装文件。基线旧 RUNME/installer 源文件仅供历史审计，不进入新 payload，也不参与新安装路径。
