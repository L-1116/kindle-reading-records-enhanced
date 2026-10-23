# 9.8.1-5.20-vera-test11：KC 彩色封面修复

本包基于 GitHub 当前 5.20/Vera Standard test10，修复原始封面和自定义封面在进入 FBInk 前丢失颜色的问题。仅交付本地候选，未更新 GitHub Release、Tag 或其他固件附件。KC 实机彩色显示尚未验收。

## 原因与处理

回归由 test7 提交 `e0e7544242ee7b85c7c95f224937de5915d0bd03` 引入：真实封面也经过新增的 `cover-image` 预览流程，而解码器请求两个通道（灰度及透明度），最终写出 P5 PGM。当前 test10 的同一程序已用红、绿、蓝色块复现输出灰度 76、149、28。

test11 改为 RGBA 解码，将透明度合成到白底后逐通道双线性缩放，输出 P6 RGB PPM。240×360、等比缩放、居中白边、输入大小和执行资源上限保留。原始 JPEG/PNG/BMP/GIF 及自定义 JPEG/PNG 保持原格式范围。FBInk 官方说明支持 PNM：https://github.com/NiLuJe/FBInk/blob/master/CLI.md 。

修复覆盖共用封面流程的阅读书籍、书籍详情、每日详情，以及设置中的通用、专属和选择图片预览。原始封面 → 已启用的专属图片 → 已启用的通用图片的优先级保持原样；不可用时仍回退占位。

缓存内容哈希从 v1 改为 v2，返回 `.ppm` 路径。旧灰度缓存不再命中，无需手动清缓存。缓存校验包含 RGB 格式、尺寸及完整长度；只对名称和内容均符合生成规则的普通 PGM/PPM 文件共用 128 项上限，保护当前图片、未知文件、目录及链接。全部替换为 RGB 后，生成预览最多约 31.6 MiB。

## 安装与身份

外层 ZIP 为 `Kindle-Reading-Records-v9.8.1-5.20-vera-test11.zip`，顶层仅 `reading-records-v4-install.sh` 与 `阅读记录安装数据.tar`。只解压外层一次，将两者一起复制到 Kindle `documents`，按原步骤覆盖安装，无需先卸载。确认正常后再运行原有清理入口。

产品身份为 `9.8.1-5.20-vera-test11`；既有内部 runtime 路径 `9.8.1-5.20-vera-test1` 保留。BUILD-INFO、payload manifest、bootstrap、VERSION、release-info、安装提示及 launcher 的产品日志使用 test11。runtime 路径和源文件中的历史注释不作为产品版本。

没有改动主 UI/旧渲染器、封面源解析、刷新 waveform、触摸、后台计时或蓝牙翻页实现。安装器只改产品身份及其提示，事务、回滚、repair、防混装、用户历史、图片、关联和配置保护规则保留。5.19 附件、KS 源码及历史产物保持原样。

## 验证与证据

完整包身份、大小、SHA-256、来源和最终回归结果见 [test11 核验记录](releases/9.8.1-5.20-vera-test11-verification.json)。独立核验命令：

```powershell
python scripts/verify_color_test11.py
```

该核验器验证已发布 test10 原 ZIP 的 SHA-256，再逐文件限制 test11 的差异，核对全部 payload 哈希、build_id、ARM EABI5/soft-float、无动态 loader 和当前源码对应关系；不会构建或发布。

新增像素测试运行真实 C 程序，覆盖 RGB 色块、JPEG、PNG、原始 BMP/GIF、透明合成、白边、灰度源、旧缓存升级、热缓存、图片替换、损坏重建及混合缓存上限。共用 UI 集成测试捕获生产 `image()` 和 `rr_settings_image()` 调用的 FBInk 参数，检查最终输入文件确有 RGB 像素；这些检查不冒充 framebuffer 实机测试。

升级测试使用 SHA-256 匹配正式下载的 test10 原包，在隔离目录执行真实历史安装器和 test11 bootstrap，检查覆盖升级、重复安装、清理、回滚及拒绝场景。Windows/MSYS 的测试进程等待可单独延长，设备端超时与安全退出策略不变。首次 130 秒本机超时记录保留在 `build/validation/color-test11-install.log`。

FBInk 全固件矩阵的绘制用例通过后，异步服务检查在 Windows 上触发了另一处本机时限问题：原始 11 秒恢复 watchdog 在证据工具创建进程期间中断工作，未生成状态文件；独立运行相同 `ensure` 可正确报告启动失败。Windows 的隔离执行副本将该 watchdog 放宽为 60 秒、观察等待放宽为 65 秒后重跑目标固件集成；Linux 和安装包内仍是原始 11 秒。此项只验证恢复结果及 UI 继续可用，不证明真机恢复耗时。

所有离线结果只说明代码及隔离环境验证情况；不扩展 KC、其他机型或固件的既有实机覆盖声明。当前固件标签仍是 5.20/Vera，继续保留 5.17、5.18 全家族、5.19 与 GC16 兼容路径。
