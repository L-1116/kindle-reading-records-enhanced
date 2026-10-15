# Kindle 阅读记录

适用于越狱 Kindle 的本地阅读记录插件，可查看每日时长、月历热力、累计统计、最近 8 周、阅读书籍、本地封面及单书详情。

**[下载最新正式安装包](https://github.com/L-1116/kindle-reading-records-enhanced/releases/latest)** · [安装与原地升级](docs/安装与回滚.md) · [全部历史版本](https://github.com/L-1116/kindle-reading-records-enhanced/releases)

在 Release 页的 **Assets** 中选择匹配固件、越狱方式和机型的安装 ZIP。GitHub 自动生成的 **Source code ZIP 不是 Kindle 安装包**。KS 表示 **Kindle Scribe**；普通版不能用于 KS。

## 界面预览

| 每日时长 | 阅读书籍 | 当天详情 |
|---|---|---|
| ![每日时长](docs/images/daily.png) | ![阅读书籍](docs/images/books.png) | ![当天详情](docs/images/day-detail.png) |

## 如何选包

当前 9.7.6 的已公开安装包仍在各自历史页面。统一 `v9.7.6` 页面正在准备，尚未发布；下面的历史链接继续有效。以后每个正式插件版本使用一个页面，在 Assets 中选择环境，不通过改名扩大兼容范围。

| 固件 / 越狱 | 机型与实机证据 | 当前下载 |
|---|---|---|
| 5.20.1 / Vera | Standard；当前 test2 已获用户实机成功确认，具体机型未注明；此前原基线在 KPW6 验收 | [5.20.1 Vera](https://github.com/L-1116/kindle-reading-records-enhanced/releases/tag/v9.7.6-5.20.1-vera) |
| 5.19.x / Vera | Standard；已确认 KPW6 / 5.19.6 正常运行及横屏启动修复 | [5.19 Vera](https://github.com/L-1116/kindle-reading-records-enhanced/releases/tag/v9.7.6-5.19-vera) |
| 仅 5.18.1.1.1 / SpringBreak | 仅 KPW4（Paperwhite 10 代），一台设备运行成功 | [KPW4 SpringBreak](https://github.com/L-1116/kindle-reading-records-enhanced/releases/tag/v9.7.6-5.18-springbreak) |
| 5.18.x / Vera | 候选已构建并通过离线测试，等待真机验收 | 暂无正式下载 |
| Kindle Scribe / KS | 9.7.6 KS 暂停开发；9.7.5 KS 为历史测试版 | [历史 KS 测试页](https://github.com/L-1116/kindle-reading-records-enhanced/releases/tag/v9.7.5-KS-1) |

5.20.1 包保留 5.17、5.18、5.19 与 GC16 兼容路径，这不代表这些组合都经过实机测试。当前附件内部身份为 `9.7.6-5.20.1-vera-test2`，详见该页面说明。正式下载资格仅限表内证据，不把离线测试称为真机验收。

## 安装与原地升级

设备须已越狱并有可用的书库 Scriptlet 执行支持；Vera 包使用 SH Integration。SpringBreak 仅确认上述 KPW4 的书库脚本入口，不假定其他环境相同。

1. 先备份 Kindle 的 `reading-time` 文件夹，包含历史、配置和封面缓存。
2. 下载匹配的安装 ZIP，只解压一次，将脚本和数据 TAR 一起复制到 `documents`；不要再解压 TAR。
3. 安全弹出 Kindle，在书库点击“安装阅读记录”，等待完成。旧普通版使用相同步骤原地升级，无需先卸载或删除原数据。
4. 打开“阅读记录”，确认历史和新增计时正常，再点击该包对应的安装文件清理入口。

5.20.1 包的两个文件为 `reading-records-v4-install.sh` 与 `阅读记录安装数据.tar`；5.19 和 KPW4 SpringBreak 包为 `reading-records-9.7.6-install.sh` 与 `reading-records-9.7.6-data.tar`。清理不是卸载，会保护历史、配置、封面、当前运行资源与必要回滚文件。失败时保留安装文件和备份，通过 [Issues](https://github.com/L-1116/kindle-reading-records-enhanced/issues) 提供机型、固件、越狱方式与错误现象；不要求普通用户执行命令或选择 runtime。

## 历史版本与开发

[全部 Releases](https://github.com/L-1116/kindle-reading-records-enhanced/releases) · [9.7.5 兼容版 V3](https://github.com/L-1116/kindle-reading-records-enhanced/releases/tag/v9.7.5-compat-v3) · [9.7.4](https://github.com/L-1116/kindle-reading-records-enhanced/releases/tag/v9.7.4) · [CHANGELOG](CHANGELOG.md)

详细变更放在 Releases 和 CHANGELOG。历史源码标签保留；此前已有五个历史草稿不在公开列表中，本次不改变其状态。

开发需要 Python 3.11+、POSIX sh/dash 与 `requirements-dev.txt`。统一发布矩阵见 [release/9.7.6.json](release/9.7.6.json)，流程、草稿命令和未来版本维护见 [统一发布流程](docs/unified-release-process.md)。默认入口为 `python scripts/unified_release.py --fetch`，只在本地校验与准备附件；不创建 Tag 或公开发布。正式草稿准备另用 `--release-commit 完整工程SHA`，分别记录 Tag 工程基线、Standard 运行基线及各包真实源提交。输出位于 `dist/unified/`，来源记录在 `release-manifest.json`。

现有构建与安装器继续沿用各自分支，不合并运行代码。完整 Standard 回归入口仍为 `scripts/validate_all.py`；其中历史安装包与基线快照是开发依赖。统一流程的安全测试为 `tests/validate_unified_release.py`，冻结生产源码验证为 `scripts/verify_published_release.py`。KS 历史源码及本地实验产物保留。

项目目录按以下用途维护，固件适配继续保留在现有分支和 worktree 中：

| 目录 | 用途 |
|---|---|
| `native-reading-time-package/` | Standard 源码、资源及 `compat/` 固件适配 |
| `ks-package/` | KS 适配源码与尚未完成的开发 |
| `documents/`、`extensions/`、`v4/` | 书库、KUAL 安装入口与两文件安装器模板 |
| `scripts/`、`release/` | 构建、验证、发布工具及固定来源矩阵 |
| `tests/` | 回归测试、fixtures 与历史基线 |
| `docs/` | 安装说明、当前开发文档、发布流程与必需的冻结校验记录 |
| `tools/`、`debug/` | 微信读书同步、封面调查及诊断工具 |
| `build/`、`dist/` | 忽略跟踪的构建、测试输出和安装包 |

`build/`、`dist/` 目前还保存构建所需的历史输入、KS 开发基线和已注册 worktree，不能整体删除。固定构建输入由 `release/9.7.6.json` 的 `build.inputs` 列出；`build/standard-next-baseline/` 的精简源码用于历史回归，KS 原包用于精确迁移归属。`build/standard-touch-candidate-workspace/` 含独立 Git 历史和未提交源码，继续保留。生成的审计、验证、预览和差异文件应放在 `build/`，不再堆入 `docs/`；历史报告和 Release 正文可从 Git 历史及 Releases 查阅。

## 致谢与授权

基于 [Plutoill/kindle-reading-records](https://github.com/Plutoill/kindle-reading-records) 的代码，经原作者授权后继续维护。本仓库为 L-1116 维护的增强版，原始工作归 Plutoill。

本仓库不附加通用软件许可证，也不应被视为向第三方授予复制、修改或再发布代码的许可；复用请分别联系相关权利人。随包 NotoSansCJK 字体按 SIL Open Font License 1.1 分发，完整条款见 [FONT-LICENSE.txt](native-reading-time-package/FONT-LICENSE.txt)。
