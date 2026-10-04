# V4 Test 3 最终验收与发布准备

日期：2026-10-04。Release 名称 V4 Test 3，tag v4-test.3，类型 Pre-release；面向普通用户正常使用。

用户已明确授权提交、push 当前 codex/v4-install-system 分支、创建新 tag 和 GitHub Pre-release。保留 Test1/Test2；手动资产仅两个用户 ZIP。

## 完整重验

本次从当前源码重新运行 scripts/validate_all.py，33 个测试/构建/审计入口全部通过，未跳过失败项。该入口包含当前 stable compatibility suite。随后再次构建最终用户 ZIP，并重跑 runtime freeze、历史审计、包逐字节一致性及全部 FBInk 调用点审计。

完整生产 UI 离线模拟 40 个场景通过，另覆盖 legacy 选定 runtime 的完整 UI。V4 安装系统 38 个场景通过。没有新增真机执行或将离线结果描述为真机验证。

| 验收 | 结果 |
|---|---|
| FBInk -e hard gate 删除；Standard / KS actual-use fallback | PASS |
| 候选内容去重；首个实际调用失败后切换；成功锁定 | PASS |
| 全部实际命令失败安全退出并恢复 Library；restore/cleanup 不调用坏 runtime | PASS |
| 5.17.1.0.4、5.18 全家族、5.18.1.1.1、5.19.2 / 5.19.5 | PASS |
| Standard 1072×1448 / 1272×1696；KS 5.18.x / 5.19.6 | PASS |
| 5.18 GC16、KS touch/方向/信号/退出 | PASS |
| 两版 A=139 / B=0；全部 actual failure；重复候选只试一次 | PASS |
| install / upgrade / repair / rollback / cleanup | PASS |
| TSV、book-covers、封面缓存、历史统计、用户配置保留 | PASS |
| runtime freeze / package consistency | PASS |
| KS force-exit 无 FBInk；崩溃/挂起 runtime 均零次调用并恢复 Library | PASS |
| 两版全部生产 FBInk 路径无旁路，31 个静态调用点 | PASS |
| 短 ASCII bootstrap；ZIP 顶层严格两个文件 | PASS |

## 最终资产

| ZIP | 字节 | SHA-256 |
|---|---:|---|
| ReadingTime-V4.zip | 15189054 | `579b998dc54176e4163eb473503b79b8c2d7976a54ceae13612c980cea5c030a` |
| ReadingTime-V4-KS.zip | 15182708 | `780447b50296e6f746d07153a5b22459336785dcbf202f77707096121e7d5ef6` |

两个 ZIP 顶层均仅为 reading-records-v4-install.sh 与 阅读记录安装数据.tar。旧超长中文安装实体文件名不存在。KS 包包含最终 force-exit 修复，没有 bundled FBInk。Full Compatibility、SHA sums 和诊断产物只留本地。

## 证据与发布约束

- build/validation/v4-test3-full-suite.log 与 v4-test3-full-suite-results.json：本次完整重验。
- build/validation/fbink-actual-use-results.json：40 个完整 UI 场景。
- build/validation/v4-results.json：38 个安装事务场景。
- build/validation/final-fbink-static-audit.json：调用点清单及恢复补验。
- build/validation/v4-stable-artifacts.json：最终源码一致性和包哈希。
- [完整兼容验收报告](v4-stable-compatibility-report.md)、[最终静态审计](v4-final-fbink-static-audit.md)。

验收产物和 ZIP 不提交 Git。只提交本轮代码、测试、文档与审计报告；原有 tools/ 不暂存、不提交、不推送。git diff --check 通过。

GitHub Actions checkout 设置 fetch-depth: 0，使完整回归可读取它明确依赖的历史 commit / tag；未改变生产逻辑或测试断言。

发布流程在完整验收通过后执行：提交 → push 分支 → 创建并 push 指向最终 commit 的 tag → 创建 draft prerelease → 上传并下载验证两个资产 → 公开 prerelease → 再读取 API 和下载资产，确认名称、类型、数量、顶层文件与哈希。发布后验证结果保存在 build/validation/v4-test3-post-release-verification.json。

Release 地址：[V4 Test 3](https://github.com/L-1116/kindle-reading-records-enhanced/releases/tag/v4-test.3)。

## GitHub 干净环境验收修正

首次 tag CI 暴露了测试环境缺陷，已停止公开发布并保持 Release 为 draft：Python mock 依赖 Windows py launcher、复制后的候选缺少 Linux 可执行位、KS 页面检查依赖未跟踪的本地 build 缓存、V4 安装测试固定 Windows shell 路径。

测试 mock 现使用运行验收的同一 Python 解释器；复制候选保留执行权限；预览与 KS 导航 fixture 从源码在临时目录生成；V4 安装测试按平台寻找 shell 和转换路径。全部原有断言与场景保留，未修改生产代码、安装 payload 或用户包逻辑。开发分支开启与 tag 相同的完整 CI，最终 tag 和公开发布仅使用完整验收成功的最终 commit。

后续干净环境重验确认：KS 诊断 fixture 也必须恢复 Linux 执行权限；历史包清理枚举改用 git ls-tree -z，直接读取中文原始路径而不依赖本机 core.quotepath=false 配置。未跳过诊断导出或历史清理断言，生产代码继续保持不变。
