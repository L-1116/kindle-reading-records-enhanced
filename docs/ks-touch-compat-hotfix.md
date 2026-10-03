# V3-KS 触摸兼容热修审计

## 证据边界与根因排序

本仓库没有这位 KS 5.19.6 用户的 evdev 事件、`/proc/bus/input/devices` 或日志，所以**无法确认该设备的单一具体根因**。已确认的源码故障链是：日历首屏绘制后，shell 启动 KS 专用 Lua reader 并 `wait`；reader 只有识别出有效 action 才返回。设备无事件、16/24 字节错帧、或触摸坐标一直落在热区外时，shell 会一直等待，页面保持在已绘制的日历。

排序：① 原始 ABS 坐标与 framebuffer 朝向或范围不匹配；② `/dev/input/touch` 别名或名称优先选择到错误设备；③ Lua 用户态 ABI 与固定 16 字节记录不符；④ 多点触控事件序列与当前 reader 假设不符；⑤ reader 明确错误但恢复不完整。②、③、④的次序需由真机日志确认。公开的同款 KS 5.19.6 [KOReader 日志](https://github.com/koreader/koreader/issues/15858)列出 `pt_mt` 触屏、两个笔设备和 `event1` 加速度计，也报告了触摸层与 framebuffer 朝向不一致；这不是本插件用户的日志，不能直接当作其根因。

KS 实际设计画布是 **1860×2480**，与普通 V3 的 1272×1696 不同。原 KS reader 直接把 `ABS_X/Y`、`ABS_MT_POSITION_X/Y` 当像素坐标，并尝试轴交换与镜像；没有读取 ABS min/max。Linux 的原始范围应由 `EVIOCGABS` 获取，[内核头文件](https://github.com/torvalds/linux/blob/master/include/uapi/linux/input.h)定义了该 ioctl 和 16/24 字节 `input_event` 布局。本项目 Lua 运行时没有通用 ioctl 接口，也没有可靠证据表明目标系统自带读取 ABS min/max 的工具；热修不猜测范围。`coordinate_mode=direct_unverified_range` 表示真机仍需验证该项。若有经过设备测量的范围，可通过 `READING_TOUCH_ABS_X_MIN/MAX` 与 `READING_TOUCH_ABS_Y_MIN/MAX` 提供，reader 会先归一化，再做朝向、viewport、逻辑坐标映射。

## 改动

- preflight 枚举 sysfs event 设备、名称、EV/ABS/PROP 能力，优先 finger MT；拒绝笔、传感器与未经验证的覆盖路径。没有 `/dev/input/event1` fallback。读取 Lua ELF class 决定 16/24 字节；无法确认 ABI 时在绘制前失败。
- reader 按选定记录大小解码。短读、打不开、明显坏流均非零退出。每次关键触摸立即覆盖更新最近一次事件与动作，避免按事件无限追加。等待正常触摸不设空闲倒计时。
- shell 对 reader 非零退出写 `error_stage=touch`，执行原有 KS cleanup，恢复 orientation、输入/休眠状态，并请求 appmgrd Library。launcher 同步普通 V3 的环境探测、Lua/FBInk 探针、runtime fallback、`launch-last.log`、失败恢复及 5.18.x 非 flashing 首刷/cleanup。
- KS 渲染、图片、画布尺寸、热区、累计时长、封面、统计数据和 daemon 均未更改。

## 诊断文件示例

以下仅为模拟示例，非用户真机结果：

```text
timestamp=2026-10-03T10:00:00+0800
firmware=5.19.6
device=KindleScribe
machine=armv7l
arch=armv7l
screen_width=1860
screen_height=2480
orientation=portrait
viewport=1860x2480+0+0
logical_size=1860x2480
touch_candidates_count=3
candidate_0_path=/dev/input/event1
candidate_0_name=bma4xy_acc
candidate_0_classification=sensor_or_button
candidate_1_path=/dev/input/event3
candidate_1_name=WacomDigitizer
candidate_1_classification=pen_digitizer
candidate_2_path=/dev/input/event4
candidate_2_name=pt_mt
candidate_2_ev_cap=f
candidate_2_abs_cap=ee18000 0
candidate_2_classification=finger_mt
selected_touch=/dev/input/event4
selection_reason=finger_mt
event_struct_size=16
coordinate_mode=direct_unverified_range
raw_abs_x_min=unknown
raw_abs_x_max=unknown
raw_abs_y_min=unknown
raw_abs_y_max=unknown
last_event_type=3
last_event_code=54
last_raw_x=130
last_raw_y=90
last_physical_x=130
last_physical_y=90
last_logical_x=130
last_logical_y=90
last_action=exit
```

真实设备只需覆盖安装本 hotfix，重启一次，打开阅读记录并测试日期、阅读书籍、累计时长、左上角退出。若仍卡住，只需 `launch-last.log` 与 `touch-last.log`。真机通过后才能把普通 V3 与 V3-KS 正式冻结；本轮没有开展 V4 或发布 Release。
