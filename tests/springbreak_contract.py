"""Exact allowed candidate deltas; historical assertions still compare full bodies."""
BASE = '3acda144ee7bf3a09d7472628efdffd9c09ab240'
VERSION = '9.7.6-5.18-springbreak'
VERA = '9.7.6-5.18-vera'

MODEL_BLOCK = '''# Non-unique product code only: read exactly bytes 4..6, never the serial.
# KOReader frontend/device/kindle/device.lua pw4_set; pinned source in audit.
product_code="$(dd if=/proc/usid bs=1 skip=3 count=3 2>/dev/null)"
case "$product_code" in
    0PP|0T1|0T2|0T3|0T4|0T5|0T6|0T7|0TJ|0TK|0TL|0TM|0TN|102|103|16Q|16R|16S|16T|16U|16V) :;;
    *) fail '此专用测试包仅适用于 KPW4，无法确认型号，安装已停止。';;
esac
unset product_code
'''

SESSION_BLOCK = '''# Dedicated candidate: a bounded session, managed by the existing parent.
# No timer child, detached process, input grab, or alternate cleanup path.
SESSION_LIMIT=120
session_ticks=0
echo "session_limit_seconds=$SESSION_LIMIT ui_pid=$UI_PID"
while kill -0 "$UI_PID" 2>/dev/null; do
    if [ "$session_ticks" -ge "$SESSION_LIMIT" ]; then
        echo 'SAFETY_EXIT: session time limit reached; cleaning owned UI'
        exit 124
    fi
    sleep 1
    session_ticks=$((session_ticks+1))
done
'''

DIAGNOSTIC_BLOCK = '''# Once per launch: existing logs only; no executable probes or personal data.
echo 'candidate=9.7.6-5.18-springbreak target=KPW4/5.18.1.1.1'
echo "fbink_path=/var/local/kmc/bin/fbink lua_path=$(command -v lua 2>/dev/null)"
for runtime_link in /var/local/kmc/bin /var/local/kmc/lib; do
    echo "runtime_link=$runtime_link target=$(readlink "$runtime_link" 2>/dev/null)"
done
if [ -r /var/local/kmc/bin/fbink ]; then
    echo "fbink_cksum=$(cksum < /var/local/kmc/bin/fbink 2>/dev/null)"
fi
for input_name in /sys/class/input/event*/device/name; do
    [ -r "$input_name" ] || continue
    echo "input_node=$input_name name=$(cat "$input_name" 2>/dev/null)"
done
'''

def baseline_launcher(source):
    # Accept exactly the reviewed additions, then compare every other byte.
    assert source.count(SESSION_BLOCK) == 1
    assert source.count(DIAGNOSTIC_BLOCK) == 1
    return source.replace(SESSION_BLOCK, '').replace(DIAGNOSTIC_BLOCK, '').replace(VERSION, VERA)

TOUCH_BLOCK = 'touch_device_is_valid() {\n    touch_candidate="$1"\n    case "$touch_candidate" in /dev/input/event*) touch_number="${touch_candidate#/dev/input/event}";; *) return 1;; esac\n    case "$touch_number" in \'\'|*[!0-9]*) return 1;; esac\n    [ ! -L "$touch_candidate" ] && [ -c "$touch_candidate" ] && [ -r "$touch_candidate" ] || return 1\n    [ -r "/sys/class/input/event$touch_number/device/name" ] || return 1\n    touch_name="$(tr \'[:upper:]\' \'[:lower:]\' < "/sys/class/input/event$touch_number/device/name" 2>/dev/null)"\n    case "$touch_name" in *power*|*snvs*) return 1;; esac\n    case "$touch_name" in *touch*|*zforce*|*cyttsp*|*fts*|*_ts*|*goodix-ts*) return 0;; esac\n    return 1\n}\n\nfind_touch_device() {\n    TOUCH=\n    if [ -n "${READING_TOUCH_DEVICE:-}" ]; then\n        touch_device_is_valid "$READING_TOUCH_DEVICE" || fail "READING_TOUCH_DEVICE 无效或不是已识别的触摸设备"\n        TOUCH="$READING_TOUCH_DEVICE"\n        echo "touch_device=$TOUCH source=override"\n        return\n    fi\n    for event_path in /sys/class/input/event*; do\n        candidate="/dev/input/${event_path##*/}"\n        if touch_device_is_valid "$candidate"; then\n            TOUCH="$candidate"\n            echo "touch_device=$TOUCH source=sysfs"\n            return\n        fi\n    done\n    fail "未找到可读的触摸设备（sysfs 名称校验失败）"\n}\n\n'

def baseline_ui(source, original):
    # Exactly the reviewed selector replacement; every other byte still audited.
    assert source.count(TOUCH_BLOCK) == 1
    old = original[original.index('find_touch_device() {'):original.index('scale_len() {')]
    return source.replace(TOUCH_BLOCK, old)
