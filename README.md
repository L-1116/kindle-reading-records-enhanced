# Kindle Reading Records Enhanced — 9.7.6-5.18-vera

这是从冻结 `9.7.6-5.19-vera`（`df5fd1e128d6a943435ea0ee8426b8f9f166b250`）建立的独立开发线，状态为 **Pre-hardware candidate**，仅面向 firmware 5.18.x + Vera 的 Kindle 青春版、Paperwhite/KPW 等普通 Kindle。5.17、5.19、Scribe/KS 不适用。

本地安装包：`ReadingTime-9.7.6-5.18-vera.zip`。解压一次，只会得到两个文件：

- `reading-records-9.7.6-install.sh`
- `reading-records-9.7.6-data.tar`

将两个文件一起复制到 Kindle 的 `documents/`，在书库点击“安装阅读记录”。安装后先打开“阅读记录”确认运行正常，再点击“安装好之后，确认无误了再点这个”。清理仅删除安装残留，长期保留正式“阅读记录”入口及所有用户数据。沿用原版本的越狱、Vera Scriptlet、FBInk/Lua 环境，不要求用户选择 runtime 或执行命令。

USB/MTP 复制用的物理文件名统一使用短 ASCII；中文显示名保留在 Scriptlet 的 `# Name`。安装入口排除重复点击，解包前检查临时空间，事务开始前检查安装和备份空间。空间不足或无法可靠读取容量时保留两个安装文件及旧运行版本，并提示“存储空间不足”；请在正常管理存储后重新安装。回滚无法完整恢复时保留恢复快照，位置记录在 `reading-time/install-last.log`。

保留周统计、每日/月历、阅读书籍、累计时长，日期/月/最近 8 周/书籍详情及单书日历，最近 7 天/本月/今年/全部筛选，Kindle 阅读进度、每页 3 本和原封面提取/fallback。原始 TSV 格式、计时/session/book ID 模型不变。

2026-10-10 本地修复移除启动器对只写 `eatTapMode` 的全部读取和写入。两个触摸监听器继续只读 evdev，不独占输入；这表示保持该属性不变，不是恢复未知原值。`orientationLock` 和 `preventScreenSaver` 仍保存、校验并恢复实际原值，正常/失败/信号统一清理，Library 打开后再恢复方向。9.7.5 的进入/退出尽力写入 0 也不应描述为恢复原触摸状态。

修复已完成定向 28 项和本分支完整 13 阶段、425 项离线验证，全部 PASS。2026-10-11 用户另行授权提交并推送到现有 GitHub 分支作为源码备份，更新分支最新版本并保留旧提交历史；不创建 tag、Release 或 PR。状态仍为 **Pre-hardware candidate**；5.19 真机成功不代表 5.18 通过。最新修复审计见 `docs/5.18-vera-eattapmode-fix.md`，上一轮历史记录保留在 `docs/5.18-vera-pre-hardware-candidate.md`。5.18 真机仍需确认启动、触摸/穿透、横屏退出方向、电源键/休眠和连续启动退出。后台完整离线验证：`python scripts/validate_all.py`。`dist/` 为本地用户包，`build/validation/` 为开发验证报告，均不会成为额外用户安装文件。基线旧 RUNME/installer 源文件仅供历史审计，不进入新 payload，也不参与新安装路径。
