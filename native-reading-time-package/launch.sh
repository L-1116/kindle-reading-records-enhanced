#!/bin/sh
BASE="${READING_BASE:-/mnt/us/reading-time}"
RELEASE="$BASE/releases/9.7.5-test"
MAIN="$RELEASE/bin/reading-records.sh"
DETECT_ENV="$BASE/compat/detect_env.sh"
DIAGNOSTICS="$BASE/bin/diagnostics.sh"
STATUS="$BASE/last-launch-status.txt"
LOG="$BASE/launch-last.log"
STAGE=launcher
UI_ENTERED=0
FALLBACK_USED=0
SELECTED_LUA=none
SELECTED_FBINK=none

mkdir -p "$BASE" 2>/dev/null || exit 1
: > "$LOG" 2>/dev/null || exit 1
: > "$BASE/last-launch.stdout" 2>/dev/null || true
: > "$BASE/last-launch.stderr" 2>/dev/null || true
exec >> "$LOG" 2>&1
printf 'timestamp=%s\nui_entry=%s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z' 2>/dev/null || echo unknown)" "$MAIN"
printf 'firmware=unknown\nkernel=unknown\nmachine=unknown\narch=unknown\ndetected_env=unknown\nhard_float=unknown\n'
printf 'selected_runtime=none\nselected_lua=none\nselected_fbink=none\n'
printf 'screen_width=unknown\nscreen_height=unknown\norientation=unknown\n'
printf 'launch_command=none\nprimary_probe_result=not_run\nfallback_used=0\nexit_code=pending\nerror_stage=none\n'

write_status() {
    status_tmp="${STATUS}.new.$$"
    {
        printf 'timestamp=%s\nstage=%s\nexit_code=%s\n' "$(date 2>/dev/null || echo unknown)" "$STAGE" "$1"
        printf 'firmware=%s\ndevice=%s\narch=%s\nhard_float=%s\nprofile=%s\n' \
            "${FIRMWARE_FULL:-unknown}" "${DEVICE_TYPE:-unknown}" "${ARCH:-unknown}" \
            "${HARD_FLOAT:-unknown}" "${COMPAT_PROFILE:-unknown}"
        [ -n "$2" ] && printf 'error=%s\n' "$2"
        :
    } > "$status_tmp" && mv "$status_tmp" "$STATUS"
}
restore_native() {
    # The Kindle launcher may have opened a blank scriptlet surface even if
    # plugin preflight failed before our first framebuffer write.
    if command -v lipc-set-prop >/dev/null 2>&1; then
        lipc-set-prop com.lab126.winmgr eatTapMode 0 >/dev/null 2>&1 || true
        lipc-set-prop com.lab126.powerd preventScreenSaver 0 >/dev/null 2>&1 || true
        lipc-set-prop com.lab126.appmgrd start 'app://com.lab126.KPPMainApp?view=KPP_LIBRARY' >/dev/null 2>&1 || true
    fi
    [ "$UI_ENTERED" = 1 ] && [ -x "$SELECTED_FBINK" ] && \
        "$SELECTED_FBINK" -q -W GC16 -s >/dev/null 2>&1 || true
}
fail() {
    failure_code="$1"; shift
    printf 'error=%s\nerror_stage=%s\nexit_code=%s\n' "$*" "$STAGE" "$failure_code"
    write_status "$failure_code" "$*"
    restore_native
    command -v lipc-set-prop >/dev/null 2>&1 && \
        lipc-set-prop com.lab126.system toasterMessage '阅读记录启动失败，请查看 launch-last.log' >/dev/null 2>&1 || true
    cp "$LOG" "$BASE/last-launch.stderr" 2>/dev/null || true
    [ -r "$DIAGNOSTICS" ] && READING_DIAGNOSTIC_INTERNAL=1 /bin/sh "$DIAGNOSTICS" >/dev/null 2>&1 || true
    exit "$failure_code"
}
trap 'STAGE=interrupted; fail 70 "launcher interrupted"' INT TERM HUP

STAGE=environment
[ -r "$DETECT_ENV" ] || fail 20 "missing environment detector: $DETECT_ENV"
. "$DETECT_ENV" || fail 21 'environment detection failed'
case "$HARD_FLOAT:$COMPAT_PROFILE:$ARCH" in
    0:default:*|1:default:*|0:fw518:*|1:fw518:*) :;;
    *) fail 21 'environment detector returned invalid ABI/profile';;
esac
[ "$ARCH" != unknown ] || fail 21 'machine architecture is unknown'
printf 'firmware=%s\nkernel=%s\nmachine=%s\narch=%s\ndetected_env=%s\nhard_float=%s\n' \
    "$FIRMWARE_FULL" "${KERNEL:-unknown}" "${MACHINE:-unknown}" "$ARCH" "$COMPAT_PROFILE" "$HARD_FLOAT"

STAGE=preflight
for required_cmd in sh awk sed sort grep date cp mv mkdir; do
    command -v "$required_cmd" >/dev/null 2>&1 || fail 30 "missing required command: $required_cmd"
done
[ -x "$MAIN" ] || fail 50 "UI entry is missing or not executable: $MAIN"
/bin/sh -n "$MAIN" || fail 53 "UI entry has a shell syntax error: $MAIN"
for required_file in "$RELEASE/ui-calendar/daily.png" "$RELEASE/ui-calendar/total.png" \
    "$RELEASE/ui-calendar/books.png" "$RELEASE/ui-calendar/day_detail.png" \
    "$RELEASE/ui-calendar/month_detail.png" "$RELEASE/ui-calendar/week_trend.png" \
    "$RELEASE/ui-calendar/book_detail.png" \
    "$RELEASE/bin/reading-insights-touch-ui.lua" "$RELEASE/bin/reading-insights-render.lua" \
    "$RELEASE/bin/reading-insights-cover.lua" "$RELEASE/bin/reading-insights-titles.lua" \
    "$RELEASE/bin/reading-insights-title-widths.lua" "$RELEASE/render-assets/dynamic-glyphs.pgm" \
    "$RELEASE/render-assets/dynamic-glyphs.tsv" "$BASE/fonts/NotoSansCJKsc-Regular.otf"; do
    [ -r "$required_file" ] || fail 51 "missing UI dependency: $required_file"
done
[ -r "$BASE/reading-time.tsv" ] || fail 41 'reading history is missing or unreadable'
[ -w "$BASE" ] || fail 40 'plugin directory is not writable'

geometry="$(fbset 2>/dev/null | awk '/geometry/{print $2 " " $3;exit}')"
set -- $geometry
SCREEN_W="${1:-unknown}"; SCREEN_H="${2:-unknown}"
case "$SCREEN_W:$SCREEN_H" in :*|*:|*[!0-9:]*|0:*|*:0)
    virtual="$(cat /sys/class/graphics/fb0/virtual_size 2>/dev/null)"
    SCREEN_W="${virtual%%,*}"; SCREEN_H="${virtual#*,}"
    case "$SCREEN_W:$SCREEN_H" in :*|*:|*[!0-9:]*|0:*|*:0) SCREEN_W=unknown; SCREEN_H=unknown;; esac
    if [ "$SCREEN_W" != unknown ] && [ "$SCREEN_H" != unknown ] && \
        [ "$SCREEN_H" -ge $((SCREEN_W * 2)) ]; then SCREEN_H=$((SCREEN_H / 2)); fi
    ;;
esac
case "$SCREEN_W:$SCREEN_H" in
    unknown:*|*:unknown) ORIENTATION=unknown;;
    *) if [ "$SCREEN_H" -gt "$SCREEN_W" ]; then ORIENTATION=portrait; else ORIENTATION=landscape; fi;;
esac
printf 'screen_width=%s\nscreen_height=%s\norientation=%s\n' "$SCREEN_W" "$SCREEN_H" "$ORIENTATION"

# This package has Lua source and shell UI, but no Lua or FBInk binaries.
# FBInk -e initializes and reports state without drawing to the framebuffer.
LUA_PRIMARY="$(command -v lua 2>/dev/null || true)"
FBINK_PRIMARY="${READING_FBINK:-}"
[ -n "$FBINK_PRIMARY" ] || {
    for candidate in /var/local/kmc/bin/fbink /mnt/us/libkh/bin/fbink; do
        [ -x "$candidate" ] && { FBINK_PRIMARY="$candidate"; break; }
    done
}
[ -n "$FBINK_PRIMARY" ] || FBINK_PRIMARY="$(command -v fbink 2>/dev/null || true)"
printf 'primary_lua=%s\nprimary_fbink=%s\n' "${LUA_PRIMARY:-missing}" "${FBINK_PRIMARY:-missing}"

probe_lua() {
    [ -n "$1" ] && [ -x "$1" ] || return 1
    "$1" -e 'assert(type(loadfile)=="function")' || return 1
    for source in "$RELEASE/bin/reading-insights-touch-ui.lua" \
        "$RELEASE/bin/reading-insights-render.lua" "$RELEASE/bin/reading-insights-cover.lua" \
        "$RELEASE/bin/reading-insights-titles.lua" "$RELEASE/bin/reading-insights-title-widths.lua"; do
        READING_PROBE_SOURCE="$source" "$1" -e 'assert(loadfile(os.getenv("READING_PROBE_SOURCE")))' || return 1
    done
}
probe_fbink() { [ -n "$1" ] && [ -x "$1" ] && "$1" -e; }

if probe_lua "$LUA_PRIMARY"; then SELECTED_LUA="$LUA_PRIMARY"; lua_result=ok
else
    lua_result=failed
    for candidate in /mnt/us/libkh/bin/lua /usr/bin/lua /usr/local/bin/lua; do
        [ "$candidate" = "$LUA_PRIMARY" ] && continue
        if [ -x "$candidate" ] && probe_lua "$candidate"; then
            SELECTED_LUA="$candidate"; FALLBACK_USED=1
            printf 'lua_fallback_reason=primary Lua probe failed; candidate passed execution and syntax probes\n'
            break
        fi
    done
fi
if probe_fbink "$FBINK_PRIMARY"; then SELECTED_FBINK="$FBINK_PRIMARY"; fbink_result=ok
else
    fbink_result=failed
    for candidate in /var/local/kmc/bin/fbink /mnt/us/libkh/bin/fbink "$(command -v fbink 2>/dev/null || true)"; do
        [ "$candidate" = "$FBINK_PRIMARY" ] && continue
        if [ -x "$candidate" ] && probe_fbink "$candidate"; then
            SELECTED_FBINK="$candidate"; FALLBACK_USED=1
            printf 'fbink_fallback_reason=primary FBInk init probe failed; candidate passed framebuffer init\n'
            break
        fi
    done
fi
printf 'primary_probe_result=lua:%s,fbink:%s\nfallback_used=%s\n' "$lua_result" "$fbink_result" "$FALLBACK_USED"
[ "$SELECTED_LUA" != none ] || fail 32 'no Lua runtime passed execution and syntax probes'
[ "$SELECTED_FBINK" != none ] || fail 31 'no FBInk runtime passed framebuffer initialization probe'
printf 'selected_runtime=external-lua+external-fbink\nselected_lua=%s\nselected_fbink=%s\n' "$SELECTED_LUA" "$SELECTED_FBINK"

# The UI calls "lua"; prioritize the probed executable without changing UI logic.
PATH="${SELECTED_LUA%/*}:$PATH"; export PATH
READING_FBINK="$SELECTED_FBINK"; export READING_FBINK
READING_LAUNCHER_CAPTURE=1; export READING_LAUNCHER_CAPTURE
STAGE=ui
printf 'launch_command=%s\n' "$MAIN"
write_status 0 starting
UI_ENTERED=1
"$MAIN"
launch_code=$?
[ "$launch_code" -eq 0 ] || fail "$launch_code" 'UI process exited unexpectedly'
STAGE=complete
printf 'exit_code=0\nerror_stage=none\n'
write_status 0 ''
cp "$LOG" "$BASE/last-launch.stdout" 2>/dev/null || true
exit 0
