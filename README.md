# Kindle 阅读记录 — 9.7.6-5.18-springbreak

已在**一台 Kindle Paperwhite 4（KPW4，10 代）、固件 5.18.1.1.1、SpringBreak 越狱环境**的机器上运行成功。实机验证范围仅为这台设备及该固件/越狱组合；不据此宣称其他型号或其他 5.18 固件均已通过。

适用范围：KPW4 / **固件 5.18.1.1.1** / SpringBreak，且已有 Scriptlet 安装入口可用。安装器保留精确固件和型号检查。不适用于 KS/Scribe，也不扩展到其他固件。

[下载公开版本](https://github.com/L-1116/kindle-reading-records-enhanced/releases/tag/v9.7.6-5.18-springbreak)。本次发布既有 ZIP 原文件，插件运行代码、安装逻辑和 UI 均不修改。

## 安装方式

1. 下载 `ReadingTime-9.7.6-5.18-springbreak.zip`，**只解压一次**。
2. 将得到的 `reading-records-9.7.6-install.sh` 与 `reading-records-9.7.6-data.tar` 两个文件一起复制到 Kindle 的 `documents` 文件夹。**不要继续解压 TAR**。
3. 安全断开 USB，在书库点击“安装阅读记录”，等待安装完成提示，然后打开“阅读记录”。已有版本可直接覆盖安装，保留阅读历史、备份、配置、封面和统计缓存；不要删除原有 `reading-time` 文件夹。
4. 确认安装正常后，可使用安装清理入口移除安装文件。出现安装或使用异常时保留两个安装文件，便于修复。

## 使用说明

保留每次会话约 120 秒自动退出的安全保护；也可点击左上角退出。历史时长、书籍封面、用户配置和统计缓存继续保留。不需要执行命令、选择 runtime 或替换系统依赖。

- [完整中文说明](docs/中文说明.md)
- [实机及离线验证记录](docs/springbreak-hardware-confirmation.md)
- [历史适配审计](docs/springbreak-kpw4-audit.md)

## 开发者验证

`python scripts/validate_all.py` 执行全部离线回归，`python scripts/report_springbreak.py` 校验当前包。离线或 Windows/MSYS 模拟不代表真机性能测量。

## 保留的 Vera 基线历史记录

下文是分叉前历史，旧包名、425 项和提交授权不适用于本轮候选。

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
