# 2026-10-14 公开发布确认

已在**一台 Kindle Paperwhite 4（KPW4，10 代）、固件 5.18.1.1.1、SpringBreak 越狱环境**的机器上运行成功。实机验证范围仅为这台设备及该固件/越狱组合；不据此宣称其他型号或其他 5.18 固件均已通过。

用户再次确认 `9.7.6-5.18-springbreak` 目前运行没有问题，并授权公开发布；发布介绍须包含安装方式和一台 KPW4 / 5.18.1.1.1 的成功记录。上传原样既有 Standard ZIP（SHA-256 `24aa298857ad99e18b339d8fea91f91191f21e12f3152ce73147bbe80c891221`），不修改生产代码或安装架构。Tag 为 `v9.7.6-5.18-springbreak`，保留所有历史版本。

以下为此前源码备份阶段的历史记录；其中“不创建 Release”“命名包未单独取得反馈”是当时状态，当前以本节反馈与发布授权为准。

# 9.7.6-5.18-springbreak 实机与源码记录

2026-10-12，用户反馈上轮交付的 Test 2 在 **KPW4 / firmware 5.18.1.1.1 / SpringBreak** 实机测试成功。未提供逐项功能清单或原始 evdev 数据；不据此宣称其他型号、固件或全部异常恢复场景已验证。

实机成功包为 `ReadingTime-9.7.6-5.18-springbreak-kpw4-test2.zip`，SHA-256：

`718517ed78953ec6e88acaed67a9ca049ee6a82300e3d7ec86ff73cb097ba59c`

原源码完整保留在 Git 检查点 `b7684a07715ac85eb9b0a58ef726c8b50e61131b`。该源码原完整离线回归为 **16 阶段 / 709 项 PASS**（含 142 项触摸专项），详见 `springbreak-test2-validation.json`。

用户授权新名称 `9.7.6-5.18-springbreak`，同名独立分支提交并 push 到现有公开仓库；明确允许源码可见，但不创建 GitHub Release、tag、PR 或合并其他分支。命名包的固件/型号范围、goodix-ts 动态选择、Lua/坐标/绘制、字体、daemon/统计/封面、120 秒退出、锁、状态恢复与安装事务均保留。仅内部身份和对应 release 路径同步。

`tests/validate_springbreak_naming.py` 对每个运行文件与实机成功检查点做字节比较，仅允许版本字符串替换；另验证精确 Test 2 → 新名称的失败回滚、重试、repair、手动清理及历史保护。命名包尚未单独取得实机反馈，不能把历史 Test 2 结果写成新包逐项实机通过。

历史 Vera / Test 1 / Test 2 归档由 `tests/springbreak_archives.py` 从固定 Git 对象精确重建，保留原 ZIP SHA-256 断言。源码回归不依赖未提交的个人工作目录、设备日志或下载后的二进制。开发者原 ZIP、完整日志和源文件快照仍留在本地。

完整回归入口仍为 `python scripts/validate_all.py`，包括全部原阶段及新增命名验证。包校验和当前结果可用 `python scripts/report_springbreak.py` 生成。此项目的工作流只验证源码，不发布 Release 或上传用户 ZIP。
