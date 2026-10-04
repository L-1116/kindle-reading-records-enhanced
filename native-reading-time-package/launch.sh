#!/bin/sh
# Name: 阅读记录
# Author: Kindle Reading Records Enhanced
# Icon: /mnt/us/reading-time/assets/launcher-icon.png
BASE="/mnt/us/reading-time"
RELEASE="$BASE/releases/9.7.6-5.19-normal"
MAIN="$RELEASE/bin/reading-records-ui.sh"
LOG="$BASE/dashboard-launch.log"
LOCK="/tmp/reading-records-ui.lock"
UI_PID=; SPAWNING=0; SIGNAL_STATUS=0; LOCK_OWNED=0; ORIENTATION_PENDING=0; EAT_PENDING=0; POWER_PENDING=0
ORIGINAL_ORIENTATION=; ORIGINAL_EAT=; ORIGINAL_POWER=; UI_ENTERED=0; CLEANED=0
exec >> "$LOG" 2>&1
fail() { echo "ERROR: $1"; lipc-set-prop com.lab126.system toasterMessage "$1" >/dev/null 2>&1 || true; exit 1; }
cleanup_runtime_state() {
    [ "$CLEANED" -eq 0 ] || return 0
    CLEANED=1
    if [ -n "$UI_PID" ]; then : > "$LOCK/ui-cancel"; : > "$LOCK/ui-start"; fi
    if [ -n "$UI_PID" ]; then kill -TERM "$UI_PID" 2>/dev/null || true; wait "$UI_PID" 2>/dev/null || true; UI_PID=; fi
    # Flags are set BEFORE each LIPC request: interruption during the request
    # must also restore the saved property, even when its return code is unknown.
    if [ "$POWER_PENDING" -eq 1 ]; then lipc-set-prop com.lab126.powerd preventScreenSaver "$ORIGINAL_POWER" || echo 'restore preventScreenSaver failed'; fi
    if [ "$EAT_PENDING" -eq 1 ]; then lipc-set-prop com.lab126.winmgr eatTapMode "$ORIGINAL_EAT" || echo 'restore eatTapMode failed'; fi
    # Native Library redraw owns recovery, including after a failed FBInk call.
    if [ "$UI_ENTERED" -eq 1 ] || [ "$ORIENTATION_PENDING" -eq 1 ]; then
        lipc-set-prop com.lab126.appmgrd start 'app://com.lab126.KPPMainApp?view=KPP_LIBRARY' >/dev/null 2>&1 || true
    fi
    # Let the native view open before restoring the user's original direction;
    # a Library launch must not overwrite our final orientation request.
    if [ "$ORIENTATION_PENDING" -eq 1 ]; then
        sleep 1
        lipc-set-prop com.lab126.winmgr orientationLock "$ORIGINAL_ORIENTATION" || echo 'restore orientation failed'
        echo "orientation_restore=$ORIGINAL_ORIENTATION"
    fi
    if [ "$LOCK_OWNED" -eq 1 ]; then rm -f "$LOCK/pid" "$LOCK/ui-start" "$LOCK/ui-cancel"; rmdir "$LOCK" 2>/dev/null || true; fi
}
on_signal() { [ "$CLEANED" -eq 0 ] || return 0; SIGNAL_STATUS=$1; [ "$SPAWNING" -eq 1 ] || exit "$1"; }
trap cleanup_runtime_state EXIT
trap 'on_signal 130' INT
trap 'on_signal 143' TERM
trap 'on_signal 129' HUP
# Reject concurrent sessions before taking any system-state snapshot.
if ! mkdir "$LOCK" 2>/dev/null; then
    old_pid="$(cat "$LOCK/pid" 2>/dev/null)"
    case "$old_pid" in ''|*[!0-9]*) fail "阅读记录已在启动，请稍后重试";; esac
    kill -0 "$old_pid" 2>/dev/null && fail "阅读记录已经打开"
    rm -f "$LOCK/pid" "$LOCK/ui-start" "$LOCK/ui-cancel"; rmdir "$LOCK" 2>/dev/null || fail "无法清理旧会话锁"
    mkdir "$LOCK" 2>/dev/null || fail "阅读记录已经打开"
fi
LOCK_OWNED=1
printf '%s\n' "$$" > "$LOCK/pid" || fail "无法记录会话锁"
[ -r "$MAIN" ] || fail "缺少阅读记录运行文件，请重新安装"
/bin/sh -n "$MAIN" || fail "阅读记录运行文件损坏"
read_geometry() {
    geometry="$(fbset 2>/dev/null | awk '/geometry/{print $2 " " $3;exit}')"
    set -- $geometry; SCREEN_W="${1:-0}"; SCREEN_H="${2:-0}"
    case "$SCREEN_W:$SCREEN_H" in *[!0-9:]*|0:*|*:0) SCREEN_W=0; SCREEN_H=0;; esac
    if [ "$SCREEN_W" -le 0 ] || [ "$SCREEN_H" -le 0 ]; then
        virtual="$(cat /sys/class/graphics/fb0/virtual_size 2>/dev/null)"
        SCREEN_W="${virtual%%,*}"; SCREEN_H="${virtual#*,}"
        case "$SCREEN_W:$SCREEN_H" in *[!0-9:]*|0:*|*:0) SCREEN_W=0; SCREEN_H=0;; esac
        [ "$SCREEN_H" -lt $((SCREEN_W*2)) ] || SCREEN_H=$((SCREEN_H/2))
    fi
    [ "$SCREEN_W" -ge 600 ] && [ "$SCREEN_H" -ge 600 ]
}
read_geometry || fail "无法识别 Kindle 屏幕尺寸"
ORIGINAL_ORIENTATION="$(lipc-get-prop com.lab126.winmgr orientationLock 2>/dev/null)" || ORIGINAL_ORIENTATION=
echo "orientation_original=$ORIGINAL_ORIENTATION geometry=${SCREEN_W}x${SCREEN_H}"
if [ "$SCREEN_W" -ge "$SCREEN_H" ] || [ "$ORIGINAL_ORIENTATION" = L ] || [ "$ORIGINAL_ORIENTATION" = R ]; then
    case "$ORIGINAL_ORIENTATION" in U|D|L|R) :;; *) fail "无法保存原屏幕方向，请先将 Kindle 调回竖屏";; esac
    ORIENTATION_PENDING=1
    lipc-set-prop com.lab126.winmgr orientationLock U || fail "无法切换为竖屏"
    tries=0
    while :; do
        if read_geometry && [ "$SCREEN_H" -gt "$SCREEN_W" ]; then break; fi
        [ "$tries" -lt 4 ] || fail "无法切换为竖屏"
        sleep 1; tries=$((tries+1))
    done
fi
# Preserve the baseline UI behavior; restore actual original values, never
# assume zero. Neither runtime uses EVIOCGRAB or changes power-key handlers.
ORIGINAL_EAT="$(lipc-get-prop com.lab126.winmgr eatTapMode 2>/dev/null)" || fail "无法保存触摸状态"
ORIGINAL_POWER="$(lipc-get-prop com.lab126.powerd preventScreenSaver 2>/dev/null)" || fail "无法保存休眠状态"
case "$ORIGINAL_EAT:$ORIGINAL_POWER" in *[!0-9:]*|:*|*:) fail "无效的系统状态";; esac
EAT_PENDING=1; lipc-set-prop com.lab126.winmgr eatTapMode 0 || fail "无法设置触摸状态"
POWER_PENDING=1; lipc-set-prop com.lab126.powerd preventScreenSaver 1 || fail "无法设置休眠状态"
UI_ENTERED=1
SPAWNING=1
(
    while [ ! -f "$LOCK/ui-start" ]; do sleep 1; done
    [ ! -f "$LOCK/ui-cancel" ] || exit 143
    exec /bin/sh "$MAIN"
) &
UI_PID=$!
SPAWNING=0
[ "$SIGNAL_STATUS" -eq 0 ] || exit "$SIGNAL_STATUS"
: > "$LOCK/ui-start" || fail "无法开始阅读记录会话"
wait "$UI_PID"; result=$?; UI_PID=
echo "ui_exit=$result"
exit "$result"
