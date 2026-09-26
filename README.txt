Kindle 阅读记录 9.7.5 兼容版 V3
==============================

把本 ZIP 的全部内容解压到 Kindle USB 根目录，不要只复制单个脚本。

【安装 / 升级】

documents/reading-records-install.sh

在安装了 SH Integration 的 Kindle 书库中显示为“阅读记录安装”。用于首次安装、
升级，以及修复/覆盖安装。也可使用 KUAL → 阅读记录 → 安装 / 升级，或 ;log runme。

【安装后清理】

documents/reading-records-uninstall.sh

历史文件名继续用于覆盖旧的卸载入口，但在书库中显示为“安装文件清理”。请先确认
“阅读记录”能正常打开，再点击清理。它只删除明确列出的安装包、安装入口、临时封面
诊断工具及报告，并在最后删除自己的书库入口。它不会停止服务，也不会删除运行中的
阅读记录程序、历史、配置或封面缓存；不会修改 Kindle 越狱和系统服务。

清理完成后，书库里本插件的长期入口只剩“阅读记录”。安装 payload 和安装入口会
一起清理；若以后需要重新安装或升级，请重新解压完整 ZIP。内部结果日志位于
/mnt/us/reading-time/cleanup-last.log，不会生成新的书库文档。

安全前置条件：清理器必须确认 V3 resolver、launcher、书库入口和服务文件均已安装。
若未确认，它会中止并保留安装包。删除白名单见 native-reading-time-package/cleanup-manifest.txt。

包内 PACKAGE-MANIFEST.json 列出全部文件的大小、SHA-256 和可执行标记。
V3 修复同一 book ID 多条 catalog 记录时先选中空记录、新书无法显示
Kindle 已有封面的回归。《北平无战事(上下册)》与《平凡的世界》的
新封面已在问题 Kindle 上验证。安装文件清理也已在 Kindle 上机验证。
其他设备/固件请按实际环境确认。
