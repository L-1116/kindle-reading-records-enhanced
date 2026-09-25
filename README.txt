Kindle 阅读记录 9.7.5兼容版-V2（公开测试）
==============================

把本 ZIP 的全部内容解压到 Kindle USB 根目录，不要只复制单个脚本。

【安装 / 升级】

documents/reading-records-install.sh

在安装了 SH Integration 的 Kindle 书库中显示为“阅读记录安装”。用于首次安装、
升级，以及修复/覆盖安装。也可使用 KUAL → 阅读记录 → 安装 / 升级，或 ;log runme。

【卸载】

documents/reading-records-uninstall.sh

在书库中显示为“阅读记录卸载”。它会停止阅读记录服务，删除程序、启动图标、KUAL
入口和可重建缓存，但保留 reading-time.tsv、备份、阅读统计报告、用户配置和其他
未被安装清单明确认定为程序文件的内容。它不会修改 Kindle jailbreak、Universal
Hotfix、MKK、KUAL 本体、MRPI、SH Integration、;log 环境或 Amazon 系统服务。

安全卸载完成后，“阅读记录卸载”会删除自身，“阅读记录安装”和安装 payload 会保留。
再次点击“阅读记录安装”即可重新安装，并继续读取保留的阅读历史数据。

失败结果：documents/reading-records-uninstall-result.txt
失败诊断：documents/reading-records-uninstall-diagnostic.txt

注意：9.7.5、firmware 5.18 的系统接口以及书库条目刷新仍需 Kindle 真机验证。
