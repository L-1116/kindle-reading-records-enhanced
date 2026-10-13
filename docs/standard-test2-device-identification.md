# 9.7.6-5.20.1-vera-test2：Standard 设备识别修复

本轮仅修复安装资格判断，生成独立 Standard 测试包。正式版 `9.7.6-5.20.1-vera`、已验证的 test1、Git Tag 和 Release 保留。KS 暂停开发；工作区中本轮开始前已有的 KS 改动也按字节保护。真机验收尚未完成。

## 故障及读取来源审计

正式版 `v4/bootstrap.template.sh` 只读取 `/var/local/deviceType.txt` 第一行，把空结果直接变成 `device variant unknown`，发生在 payload 解包、服务操作和计时恢复之前。文件缺失、不可读、读取失败、零字节和空首行都可能产生缺失信息；旧代码不能区分其中原因。离线使用原样正式包、空型号文件及合成 Colorsoft USID 复现了 `exit_code=1`、`build_id=fc4e9d8b7c1b4403436e`。

现有售后日志不足以确认两台设备上的实际文件状态。未获得固件文件或现场文件状态前，不能断言 5.20.1 普遍删除该文件，也不能把安装失败归因于 Colorsoft UI。`/var/local` 用户空间文件可能尚未生成、被移除、权限不允许读取或存在空内容，这些是待排查情况，不是已确认的固件行为。

[KindleModding Hotfix 的 libhotfixutils](https://github.com/KindleModding/Hotfix/blob/rewrite-lite/src/kmc/hotfix/libhotfixutils) 用 `/proc/usid` 的第一个字符区分旧/新序列编码：B 或 9 开头取第 3–4 位，其余取第 4–6 位。其旧 Scribe 表不足以覆盖后续代际，故参照 [KindleTool 设备枚举](https://github.com/NiLuJe/KindleTool/blob/master/KindleTool/kindle_tool.h) 和 [KindleModding FBInk 设备识别](https://github.com/KindleModding/FBInk/blob/master/fbink_device_id.c) 补齐 Scribe 2/3/Colorsoft。

识别器只让 2/3 位共用设备代码离开 awk；不输出完整序列号、个人后缀或序列号哈希。完整型号文本也不写入新增识别日志。所有外部命令输出均使用明确格式或丢弃 stderr。

只校验包含设备代码的 4/6 位前缀，不要求完整序列号长度或后缀格式：已知 KS 代码不会因后缀变化、截短后缀或 NUL 结束符失去拦截资格。设备代码本身缺位或包含非法字符时才记录 `invalid`，然后继续检查其他来源。

## 安装规则

| 有效证据 | 决策 | 诊断 |
|---|---|---|
| 任一来源确认 KS，其他来源未知或一致 | 拒绝 Standard | `scribe_confirmed` |
| 明确 KS 与明确非 KS 相互冲突 | 安全停止 | `conflicting_ks_evidence` |
| 明确非 KS，无 KS 证据 | 继续原环境验证 | `non_scribe_confirmed` |
| 所有来源缺失、空、不可读、无效或未知 | 继续原环境验证 | `no_ks_evidence`、`model_confirmation=unconfirmed` |
| 已有 KS launcher、运行目录、VERSION 或 release-info | 拒绝混装 | `installation_evidence=ks_residue` |

依次检查全部来源，不在首个成功来源后短路：`deviceType.txt`、`/proc/usid`、`/proc/device-tree/model`、`/sys/firmware/devicetree/base/model`。后两个是可选内核型号文本；这两个路径可能指向同一设备树，并不算两个独立的硬件证明。只认明确型号名称，不使用共享 CPU、ABI、分辨率、手写笔输入节点或已安装应用推断 KS。

非 KS 设备代码和名称只作为识别来源冲突的正面证据，不构成安装白名单；未列出的普通 Kindle 和未来新设备仍可尝试 Standard。型号判断不会跳过固件、ABI、依赖、挂载、FBInk、服务、UI 或触摸检查。当真正的 KS 所有可用来源都缺失/未知时，无法证明其型号；按本轮要求允许尝试，而非宣称已确定非 KS。

| 家族 | 共用 USID 设备代码 | 型号判断 |
|---|---|---|
| KS / Scribe 2022 | 27J、2BL、263、227、2BM、23L、23M、270 | KS |
| Scribe 2 | 3V0、3V1、3X5、3UV、3X4、3X3、41E、41D | KS |
| Scribe 3 | 4PG、4PE、4PL、4F8、4FA、454 | KS |
| Scribe Colorsoft | 4VX、4PF、4PH、4F9、4FB、46P | KS |
| 普通 KC / Colorsoft | 3H9、3H4、3HB、3H6、3H2、34X、3H7、3JT、3J6、456、455、4EP | 非 KS |
| PW6 | 349、346、33X、33W、3HA、3H5、3H3、3H8、3J5、3JS | 非 KS |
| 基础版 2024 | 3L5、3L6、3L4、3L3、A89、3L2、3KM | 非 KS |
| 其他已知普通 Kindle / 未知设备 | 旧普通设备按上游证据识别；未知代码不作型号推断 | 都可以进入后续检查，无 KS 证据时 |

上游部分枚举的问号表示具体容量/销售地区未确认，不代表将全部未知设备当 KS。`KOReader` 的当前 Scribe 2 表出现 `410`，而 KindleTool 和 FBInk 对应的是 `41D`/`0x102D`；本轮采用后两者相互一致的表，不把该差异猜成已确认硬件代码。

## 所有入口使用同一实现

新增 `native-reading-time-package/compat/device_variant.sh`，包含判断和 KS 安装残留检查。构建器将同一源码嵌入 bootstrap，同时将其装入 payload；核心 `install.sh` 在 `install|upgrade|repair` 共用分支再次调用同一函数。外层及核心分别重读来源，可发现安装中途变化；核心拒绝时沿用原事务 rollback。

传统 Scriptlet、RUNME 与 KUAL 安装/覆盖/repair 已路由到 bootstrap 或核心；无需单独维护一套检测。`detect_env.sh` 虽然也读取设备型号，但本来就把缺失值设为 `unknown`，不负责 KS 安装资格，保持原样。内部基础安装器与优化安装器由核心派发，未增加另一份设备规则。诊断和 cleanup 不被误当作安装。

安装结果新增 `device_variant`、`device_decision`、`device_reason`、`device_sources`；日志逐来源区分 `missing`、`unreadable`、`read_failed`、`empty`、`invalid`、`read`。成功读到未知内容会以 `classification=unknown` 记录。冲突信息只保留分类与短代码；结果文件仍原子写入。

## 保留已验收运行链

产品版本与包名为 `9.7.6-5.20.1-vera-test2`，内部运行目录沿用 `releases/9.7.6-5.20.1-vera`。bootstrap、release-info、VERSION、BUILD-INFO、payload manifest 和 cleanup 的身份一致；`runtime_release` 明确记录实际内部路径。内部目录名不是产品编号。

UI、旧渲染 fallback、launcher、计时 daemon、Upstart job、固件/ABI 探测、FBInk 候选去重与同命令回退、成功锁定、真实绘制失败安全退出、GC16 回退、迁移和清理删除算法保持字节不变。cleanup 仅调整测试版本标识与实际运行路径的对应关系。回滚快照及用户历史数据按既有机制保护。

## Colorsoft 独立兼容性审计

| 项目 | 源码结论 | 仍需真机确认 |
|---|---|---|
| 屏幕尺寸/方向 | launcher 与 UI 动态读取 `fbset` 或 framebuffer 尺寸，使用原缩放与居中规则 | KC 当前 framebuffer 几何、旋转后的坐标及画面裁切 |
| FBInk | [上游实现](https://github.com/KindleModding/FBInk/blob/master/fbink_device_id.c) 为普通 Colorsoft 标记 Bellatrix4、MTK 和彩色面板；插件不捆绑或替换设备 FBInk | 用户已安装的实际 FBInk 构建及当前 5.20.1 驱动组合能否执行 UI 绘制/刷新 |
| 刷新 | [FBInk MTK 刷新路径](https://github.com/KindleModding/FBInk/blob/master/fbink.c) 包含 Colorsoft；插件保留 GC16 和 GC16_FAST 失败后 GC16 回退 | 彩色面板上的灰度、残影、完整刷新及退出恢复表现 |
| 触摸 | 现有代码识别实际输入结构与轴范围，处理 MT slot/坐标变换，遇到真实 reader 错误安全退出 | KC 输入节点、事件格式、坐标轴范围及所有按钮命中 |
| 渲染 | 使用既有灰度 PGM/PNG 素材和 compositor，没有增加彩色渲染功能 | 屏幕上显示与触摸区域一致、竖横屏/待机后恢复 |
| 计时/服务 | 本轮未改源码；保留服务修复与恢复路径 | 两台设备安装后继续产生有效计时记录 |

上述源码和离线模拟不能证明 Colorsoft 整机已经兼容；也未以 Windows/MSYS 时间宣称 Kindle 启动速度达标。另一台设备型号未确认，用“全部识别来源缺失”覆盖其入口故障，未猜测型号。

## 离线验证与交付

`tests/validate_device_variant.py` 包含原样正式包故障复现、sh/dash 的 KS/普通 KC 代码与名称用例、缺失/空/不可读/读取失败/未知内容、CRLF/NUL、冲突、隐私断言，以及实际 bootstrap 和核心 install/upgrade/repair 流程。受拒设备不得调用系统服务、创建安装回滚区或改变已有运行文件；允许路径保留历史并完成服务验证。

另运行原有安装迁移/rollback/cleanup 矩阵、5.20.1 服务恢复、固件解析、FBInk 实际命令及 resolver、Standard 触摸、launcher 状态与最终包验证。报告写入 `build/standard-test2-audit/`。最终状态及交付摘要由 `scripts/finalize_standard_test2.py` 在所有必要检查通过后生成；失败则不交付。

测试包 ZIP 顶层严格只有 `reading-records-v4-install.sh` 和 `阅读记录安装数据.tar`。只需解压外层一次，将两个文件放入 Kindle documents 并按原安装流程操作；不要求普通用户执行命令、探测二进制或选择 runtime。测试目的为完整安装及真实功能验证，故障日志只用于售后。

## 最终离线结果

状态：离线通过，真实设备待验证。

构建：`b1f08cf0bdbcceae6abb`；ZIP：`dist/standard-test2/9.7.6-5.20.1-vera-test2.zip`；大小：15227772 字节。

SHA-256：`45d333a6c677e66a927d48c5cb3e3de1d182b94e73e1ad4db96f0736e82d4a44`。

设备识别/入口测试 203 个用例、6 个读取权限拒绝用例、原安装迁移/rollback/cleanup 的必要子集 20 个场景，以及 12 项相关 Standard 回归全部通过。新增设备测试包含两种 shell 的识别用例及各实际安装入口；成功安装场景保持原数据，拒绝场景不修改运行文件。生产运行 payload 的 78 个文件与已发布正式包逐字节一致。完整差异白名单、测试记录与保护校验见 `build/standard-test2-audit/final-validation.json`。本轮未重新运行所有无关统计/UI 检查，采用逐字节保护和与本次变更相关的必要回归；未把上轮结果称为本轮完整测试。

## 2026-10-14 实机验收及发布授权

用户已确认此测试包测试成功，并明确要求推送 GitHub、更新原 `9.7.6-5.20.1-vera` Release 的下载附件，说明其内部为已验收 test2 构建。上述生成阶段的真机待验收描述作为历史审计记录保留。发布不重建 ZIP，不修改测试通过的安装/运行代码；仅更新文档、校验和 CI。具体机型及逐项实测信息未在此次确认中列出，因此不追加未提供的机型验收声明。
