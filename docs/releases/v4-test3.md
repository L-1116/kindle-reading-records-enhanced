# V4 Test 3

这是 V4 安装与兼容性更新版本，以 Pre-release 形式提供，面向普通用户正常使用。阅读统计功能、历史数据和 UI 使用方式保持不变。

## 修复内容

此前部分 5.18.x / 5.19.x Kindle 安装成功后，打开“阅读记录”会白屏或自动返回书库。新版启动器使用了一项过于严格的 FBInk 启动检查，这项检查在部分设备上会错误失败，即使设备仍可能正常执行阅读记录真正需要的显示操作。

本版本已调整 Standard 和 KS：

- 不再使用这项不可靠检查阻止界面启动。
- 在真实显示操作中自动选择可用的 FBInk runtime；一个真正失败时尝试下一个。
- 成功后固定使用同一个 runtime，不反复切换。
- 全部显示 runtime 均失败时，释放触摸和防休眠状态，安全返回 Kindle 书库。
- 删除 KS 强制退出路径残留的 FBInk 直接调用，避免退出时再次依赖失败的显示 runtime。

本轮离线兼容回归覆盖 5.17.x、5.18.x、5.19.x、Standard Kindle 和 Kindle Scribe / KS，并保留 5.18 刷新兼容处理与 KS 5.19.6 触摸兼容修复。

## 下载与安装

普通 Kindle 下载 **ReadingTime-V4.zip**；Kindle Scribe / KS 下载 **ReadingTime-V4-KS.zip**。需要已有可用的越狱及 Scriptlet 启动环境。

1. 下载对应 ZIP，只解压最外层 ZIP 一次。
2. 得到 `reading-records-v4-install.sh` 和 `阅读记录安装数据.tar`。
3. **不要解压 `阅读记录安装数据.tar`**，将两个文件一起复制到 Kindle 的 `documents` 文件夹。
4. 安全弹出 Kindle，在书库点击“安装阅读记录”。
5. 安装完成后打开“阅读记录”，正常使用即可。
6. 确认安装正常后，可以点击生成的安装文件清理入口。它只删除安装文件，不删除插件、阅读历史、封面或用户配置。

无需手动改名、执行命令或选择 runtime。GitHub 自动生成的 Source code 压缩包不是安装包。

## 已有用户升级

9.7.4、9.7.5、V1、V2、V3、V3-KS、V4 Test1、V4 Test2 均可使用对应 Standard / KS 包直接覆盖升级，**不要先卸载**。升级保留 `reading-time.tsv`、历史阅读记录、`book-covers`、封面缓存、用户配置及统计数据，并保留安装校验、repair 和失败回滚机制。

## 安装文件名修复

V4 Test1 曾使用很长的中文物理文件名，部分 Windows 用户复制到 Kindle 时出现 `0x800700EA`。现在安装脚本物理文件名固定为 **reading-records-v4-install.sh**，Kindle 书库中仍显示中文“安装阅读记录”，用户无需手动改名。

## SHA-256

`ReadingTime-V4.zip`

```text
579b998dc54176e4163eb473503b79b8c2d7976a54ceae13612c980cea5c030a
```

`ReadingTime-V4-KS.zip`

```text
780447b50296e6f746d07153a5b22459336785dcbf202f77707096121e7d5ef6
```

## 故障支持

如果使用过程中仍出现无法启动等异常，可通过现有支持渠道提供 `/mnt/us/reading-time/launch-last.log`。KS 如果已经进入界面但触摸异常，还可以提供 `/mnt/us/reading-time/touch-last.log`。
