# Kindle Reading Records Enhanced — 9.7.6-5.19-vera

下载正式安装包：[ReadingTime-9.7.6-5.19-vera.zip](https://github.com/L-1116/kindle-reading-records-enhanced/releases/download/v9.7.6-5.19-vera/ReadingTime-9.7.6-5.19-vera.zip)。[查看发布说明](https://github.com/L-1116/kindle-reading-records-enhanced/releases/tag/v9.7.6-5.19-vera)。

**仅适用于固件 5.19.x 的普通 Kindle。非 5.19 固件请勿安装，Scribe/KS 不适用。**

已在 **KPW6、固件 5.19.6、Véra 越狱环境**下试运行成功。本版本主要解决“横屏阅读后打开阅读记录插件会闪退”的问题，支持原地安装或更新，保留已有阅读历史和封面缓存。

## 安装或更新方法

1. 下载并解压安装 ZIP，得到 `reading-records-9.7.6-install.sh` 和 `reading-records-9.7.6-data.tar` 两个文件。
2. 将两个文件一起拖入 Kindle 根目录的 **`documents` 文件夹**。
3. 安全弹出 Kindle 并断开 USB 连接，回到书库，点击出现的“安装阅读记录”书本，即可安装或更新。
4. 完成后，书库会同时出现阅读记录插件图标和清理功能书本。
5. 打开插件，稍作检查并确认运行正常后，点击“安装好之后，确认无误了再点这个”清理书本。

清理功能只删除安装残留，保留正式插件、阅读历史、配置和封面缓存。

## 保留的功能与数据

保留周统计、每日时长/月历、阅读书籍、累计时长，日期、月份、最近 8 周、书籍详情和单书日历，以及最近 7 天、本月、今年和全部筛选。统计、封面、Lua 渲染、触摸坐标、daemon 和历史格式保持不变。

沿用原有越狱及 Véra/KPM Scriptlet、FBInk/Lua 环境。安装、升级和 repair 保留阅读历史、备份、用户配置及封面缓存；清理只处理安装残留。空间不足或容量无法可靠读取时，安装会保留两个安装文件和旧运行版本并提示存储空间不足。回滚无法完成时保留恢复快照，位置记录在 `reading-time/install-last.log`。

## 开发与验证记录

这是从 `v9.7.5-测试版`（`e41707492b985284d77e0ec5ec5ceffe98209a89`）建立的独立 5.19.x Standard 分支。启动器不再读写只写的 `eatTapMode`，保留原有只读触摸监听与可读写系统状态的保存、恢复。为保持原地升级，内部 release ID 仍为 `9.7.6-5.19-normal`，运行目录和旧数据不迁移。

本地包为 `dist/ReadingTime-9.7.6-5.19-vera.zip`；后台完整回归入口为 `python scripts/validate_all.py`。修复阶段的 12 阶段、407 项检查通过，宿主超时及完整末阶段重跑记录保留。修复与真机反馈见 [修复记录](docs/5.19-vera-eattapmode-fix.md)，具体物理行为清单见 [KPW 验证清单](docs/5.19-normal-kpw-checklist.md)。已确认的真机结果限于用户反馈的 KPW6 / 5.19.6 / Véra 运行成功及横屏阅读后启动闪退修复，不扩大为所有机型、固件或电源/休眠行为均已验证。

`build/validation/` 为开发者本地报告，不作为额外安装附件。基线旧 RUNME/installer 仅供历史审计，不参与本版本安装路径。main 和历史 tag 保留；指定旧版本取消公开发布时仅改为 Release 草稿，保留历史说明、附件和代码。
