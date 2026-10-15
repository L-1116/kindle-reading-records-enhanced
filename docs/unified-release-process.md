# 统一发布流程

每个正式插件版本只有一个规范页面：Tag `v9.7.6`、标题 `Kindle 阅读记录 v9.7.6｜多固件兼容版`。同一页面包含已验证环境的 ZIP、`SHA256SUMS.txt` 与 `release-manifest.json`。KS 表示 Kindle Scribe，不能由普通包改名得到。历史环境专用页面保留为迁移前存档，不删除或重编号。

## 维护矩阵

`release/9.7.6.json` 是本轮唯一发布输入。它记录真实源提交、来源分支、包内身份、实际固件范围、越狱方式、机型、真机证据、结构、资源、SHA-256 和构建入口。固件文件名标签不代表所有 patch 或机型均已验收。

`publish: true` 要求 `status: hardware` 及证据链接。`automated` 与 `experimental` 可以记录在矩阵和说明中，但不得进入普通用户的正式下载资源。未构建或暂停的变体没有可公开文件；5.18 Vera 的历史 425 项离线通过不是本轮真机结论，KS 暂停。已发布 9.7.5 的旧包不能改成 9.7.6。

一个 Tag 只能指向一个提交。矩阵 `baseline_commit` 固定为已发布 Standard 修复源 `b46407c3b73cd1d5445a3db2159662ca9ffd4c75`，代表已验收运行源码。**正式 Tag 建议指向本轮包含发布工程的新提交（方案 B）**，通过 `--release-commit 完整SHA` 单独指定。脚本要求它是该运行基线的后代、保护路径无源码变化，且包含当前审阅的脚本、矩阵和工作流。生成清单分别记录 Tag 的 `baseline_commit`、原 `runtime_baseline_commit` 和每包真实 `source_commit`，不合并运行分支，不把工程提交伪装成各包构建源。

方案 A 保持旧运行提交作为 Tag，但该 Tag 下找不到统一入口、矩阵和工作流；用户必须另外检出工程分支才能复现整次发布。方案 B 同时保留完整 Standard 运行代码和发布工具，各变体仍按固定源提交构建，更便于从正式 Tag 复现。GitHub 的自动 Source code 仍只包含 Tag 所指向的一份树，不能代表三个运行分支，也不是 Kindle 安装包。默认不带 `--release-commit` 的 dry-run 仍验证原运行基线，避免改写已固定的原包证据；正式草稿必须使用审阅的新工程 SHA 和新输出目录。

## 默认本地准备

开发者使用 Python 3.11+，本地 Git 历史须包含矩阵中的源提交。所有命令都是维护者命令，不是普通用户安装要求。

```powershell
python scripts/unified_release.py audit --authenticated
python tests/validate_unified_release.py
python scripts/unified_release.py --matrix release/9.7.6.json --fetch
```

`audit` 仅执行 GitHub GET 和本地只读 Git 查询；`--authenticated` 使用已有非交互凭据才能看见历史草稿，不打印凭据或拉起窗口。审计分页读取 Releases、Tags、Branches、latest 和仓库不可变设置，结果留在 `build/unified-release-audit/`。

默认 `prepare` 下载矩阵明确指定的公开原包，核对预先固定的哈希；缓存以哈希为文件名。也可用 `--local ID=PATH` 提供维护者已持有的同一原包，仍要求固定哈希。原 ZIP 字节只复制，不改内部版本、bootstrap、TAR、runtime 或安装核心。不会扫描 dist 收集附件，不会混入历史/测试包。

输出 `dist/unified/v9.7.6/`：三个安装 ZIP、`SHA256SUMS.txt`、`release-manifest.json`、`RELEASE.md`。校验包括两文件 ZIP 的精确布局与入口、TAR 全部普通文件及安全路径、必需 Standard 资源、KS 资源排除、内层逐文件清单、bootstrap checksum、实际生产源提交和环境 guard。5.20.1 包沿用其 JSON 清单与冻结发布验证；5.19、SpringBreak 沿用其 TSV/POSIX checksum 与真实源码模板。

重复运行时只接受相同内容。输出目录有未知文件或已存在同名不同字节时安全失败；使用新 `--output` 目录审阅修订，不自动删旧目录或旧文件。正文和 SHA256SUMS 均从同一批已校验变体生成，待测试变体不生成虚构下载名或链接。

## 复用分支构建

```powershell
python scripts/unified_release.py --matrix release/9.7.6.json --rebuild --output build/unified-rebuild
```

该命令在独立临时 clone 中检出每个完整源 SHA，复用对应分支已有构建脚本，不操作现有 worktree。Standard 5.20.1 调用 `scripts/build_v4.py`，5.19 与 SpringBreak 调用各自 `scripts/package_release.py`。KS 不构建、不上传，未来解除暂停需单独审阅 KS 资源和验证适配器。

5.20.1 的成熟构建器会读取历史安装包、原基线、test1 及 Git 历史以生成安全归属清单。统一入口将这些依赖逐文件枚举到矩阵 `build.inputs`，固定 SHA-256 和目标路径，另固定相关历史修订集合。缺失、改变或新增历史输入须审阅，不悄悄绕过。clone 设置 `core.autocrlf=false`、`core.eol=lf`，保证 XML 等 `text=auto` 资源不会在 Windows 检出时变为 CRLF；这是构建环境固定，不是修改安装器源码。

本轮重建必须和已验收原包 **整个 ZIP 的 SHA-256 相同** 才可继续。不同则拒绝，不上传重建文件，比较报告写入 `build/unified-release-audit/*-rebuild-mismatch.json`。未来新功能版本的候选须先用原构建器完成必要回归与设备验证，再把其完整提交、字节哈希和证据登记到新版本矩阵；统一入口不把新构建自动晋升为已验收。生成的报告、预览、差异和临时 clone 均放在忽略跟踪的 `build/` 中，审阅结束后清除；固定构建输入和仍在使用的 worktree 须保留。

## 显式草稿上传

先审阅本地 `RELEASE.md`、来源和校验清单；随后由维护者在新的授权阶段创建并推送目标 Tag。本轮不执行以下远端写入命令。设备使用者无需执行这些命令。

```powershell
$releaseCommit = git rev-parse HEAD
# 先确认它等于本轮报告的完整工程 SHA；不要追随以后变动的 HEAD。
python scripts/unified_release.py --fetch --release-commit $releaseCommit --output dist/unified/v9.7.6-release
git -c http.sslBackend=openssl push origin "${releaseCommit}:refs/heads/codex/release-9.7.6-5.20.1-vera"
# 分支推送完成并核对只读 CI 后，按下一阶段授权创建 Tag。
git tag -a v9.7.6 $releaseCommit -m "Kindle Reading Records v9.7.6 unified release baseline"
git -c http.sslBackend=openssl push origin refs/tags/v9.7.6
# 草稿与附件阶段需明确授权，既不公开也不设置 Latest。
gh release create v9.7.6 --repo L-1116/kindle-reading-records-enhanced --draft --verify-tag --latest=false --title "Kindle 阅读记录 v9.7.6｜多固件兼容版" --notes "附件校验尚未完成；请勿公开发布。"
python scripts/unified_release.py --fetch --release-commit $releaseCommit --output dist/unified/v9.7.6-release --upload-draft
```

上传要求可用且已认证的 GitHub CLI `gh`。统一脚本只支持 gh 草稿上传，认证 API 仅用于读取。使用 `gh --version` 和 `gh auth status --hostname github.com` 检查本机环境；不能以 Git Credential Manager 已登录代替 gh 认证。

Windows 可使用 WinGet 安装：

```powershell
winget install --id GitHub.cli --exact --source winget
gh --version
gh auth status --hostname github.com
```

如 WinGet 不可用，使用 [GitHub CLI 官方 Release](https://github.com/cli/cli/releases) 对应架构的 MSI。安装后新开终端或确认 `C:\Program Files\GitHub CLI` 已加入进程 PATH。登录可使用 gh 的安全身份验证流程；如复用已有效的 GCM 凭据，应只在维护者进程内存中交给 gh，不能打印 Token、使用 `--show-token`、保存明文脚本/日志或提交配置。需要拉起浏览器的操作由用户自己进行，或先取得当次屏幕操控同意。[官方安装说明](https://github.com/cli/cli#installation)。

本轮 Git 默认 schannel 曾遇到 TLS 握手错误，使用仅对该条命令生效的 `-c http.sslBackend=openssl` 后只读 ls-remote 成功；没有修改全局配置或关闭证书验证。后续 push 前须再次读远端并确认 fast-forward；远端若改变就停止，不使用 force。

草稿入口先核对远端 Tag 的真实提交和不可变设置，再分页检查同 Tag/标题重复页。仅操作未公开、非预发布、未锁定的草稿；Tag 不存在、指向不同源、同名不同哈希、附件未完成或有未知附件时拒绝。创建使用 `gh release create --draft --verify-tag`；分文件上传不用 `--clobber`，没有删除命令。中断时保留已上传附件，下次仅跳过哈希相同的文件并补齐缺项。

每次上传前重读草稿状态和本地字节；上传后校验完整远端附件集合及 GitHub digest（缺失时下载远端原文件比对 SHA-256）。全部通过才用 `--notes-file` 写最终正文，随后再次核对标题、正文和附件。上传附件为 ZIP、SHA256SUMS 和来源清单，`RELEASE.md` 用作正文，不另上传冗余文档。工具没有公开发布选项。

GitHub 不可变发布启用后，必须在草稿内一次准备完整矩阵再发布；公开后不能增加/替换 ZIP 或移动 Tag，新增适配须进入下个正式插件版本。即使当前未启用，本流程也拒绝向已公开页补传或替换附件。[GitHub 不可变 Release 文档](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases)；[gh 上传文档](https://cli.github.com/manual/gh_release_upload)说明 `--clobber` 会先删旧资源，上传失败时可能丢失旧附件，因此本流程禁止使用。

## CI 和以后版本

新增 `unified-release.yml`：发布工程安全测试，以及维护者手动触发的公开原包校验与 artifact 准备。只有 `contents: read`，不创建 Tag、不上传 Release、不公开发布。纯插件版本 Tag 在本轮工程提交上会准备对应矩阵，传入实际 `GITHUB_SHA` 并保留独立运行基线；安装器运行回归仍使用原分支已存在的测试。本轮仅本地提交、不 push，没有触发真实 GitHub Actions。

下一轮分阶段执行：安全推送工程分支 → 创建并推送唯一 Tag → 明确授权后创建草稿及上传 ZIP/校验/来源清单 → 核对草稿并报告 → 经用户另行确认正式公开 → 设置 Latest → 最后更新三个历史页面的新入口。公开与历史迁移不得由草稿脚本自动串联，旧页面须保留原附件、Tag、说明及 URL。

9.7.7、9.7.8 复制矩阵为相应插件版本，修改 Tag、标题、变化、生产基线、变体源提交、已验收身份与证据，重新记录构建输入和验收原包哈希。未验收变体设置 `publish: false`。运行审计 → 安全测试 → 原包准备 → 必要隔离构建验证 → 审阅正文 → 另行授权 Tag 和草稿上传。只维护一个规范正式页面，历史来源通过清单追溯。
