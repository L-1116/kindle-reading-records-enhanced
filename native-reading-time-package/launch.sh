#!/bin/sh
BASE="${READING_BASE:-/mnt/us/reading-time}"
PRODUCT_VERSION="9.8.1-5.20-vera-test1"
RELEASE="${READING_RELEASE:-$BASE/releases/$PRODUCT_VERSION}"
LOCK="${READING_UI_LOCK:-${READING_TMPDIR:-/tmp}/reading-records-ui.lock}"
LOCK_OWNED=0
[ -r "$BASE/compat/performance.sh" ] && . "$BASE/compat/performance.sh"
type rr_perf >/dev/null 2>&1 || rr_perf() { :; }
[ "${READING_PERF:-0}" != 1 ] || : > "$READING_PERF_LOG"
rr_perf entry
[ "${READING_PERF:-0}" != 1 ] || printf 'metric_origin=script_entry physical_display_completion=unverified\n' >> "$READING_PERF_LOG"
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
PROBE_PID=
PROBE_WORK=
[ ! -r "$BASE/compat/lifecycle.sh" ] || . "$BASE/compat/lifecycle.sh"
UI_PID=
UI_CHILD_PENDING=0

# Shared bounded check; faults are preserved before recovery. History UI remains usable.
if [ "${READING_SERVICE_CHECKED:-0}" != 1 ] && [ -r "$BASE/bin/service-manager.sh" ]; then
    READING_SERVICE_CHECKED=1; export READING_SERVICE_CHECKED
    rr_perf service_begin
    /bin/sh "$BASE/bin/service-manager.sh" launch >/dev/null 2>&1 || READING_PRESERVE_LAUNCH_LOGS=1
    rr_perf service_end
fi
[ -r "$BASE/compat/runtime-lock.sh" ] || { printf "runtime lock missing\n" >&2; exit 1; }
. "$BASE/compat/runtime-lock.sh" || exit 1
launcher_cleanup() {
    cleanup_probe
    release_runtime_lock
}
trap launcher_cleanup EXIT
acquire_runtime_lock || { release_runtime_lock; exit 75; }
# Exclude installs without taking the lifecycle mutex for a long-lived UI.
if [ -d "${READING_LIFECYCLE_LOCK:-${READING_TMPDIR:-/tmp}/reading-records-lifecycle.lock}" ]; then exit 75; fi
rr_perf lock_acquired
mkdir -p "$BASE" 2>/dev/null || exit 1
if [ "${READING_PRESERVE_LAUNCH_LOGS:-0}" = 1 ] || ! ( : > "$LOG" ) 2>/dev/null; then
    # A failed evidence write must not erase the original logs or prevent
    # a readable history UI. Emergency output is one fixed temporary file.
    READING_PRESERVE_LAUNCH_LOGS=1
    LOG="${READING_TMPDIR:-/tmp}/reading-records-emergency-launch.log"
    STATUS="${READING_TMPDIR:-/tmp}/reading-records-emergency-launch-status.txt"
    : > "$LOG" 2>/dev/null || exit 1
else
    : > "$BASE/last-launch.stdout" 2>/dev/null || true
    : > "$BASE/last-launch.stderr" 2>/dev/null || true
fi
exec >> "$LOG" 2>&1
printf 'timestamp=%s\nui_entry=%s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z' 2>/dev/null || echo unknown)" "$MAIN"
printf 'firmware=unknown\nkernel=unknown\nmachine=unknown\narch=unknown\ndetected_env=unknown\nhard_float=unknown\n'
printf 'selected_runtime=none\nselected_lua=none\nselected_fbink=pending_actual_use\n'
printf 'screen_width=unknown\nscreen_height=unknown\norientation=unknown\n'
printf 'launch_command=pending\nprimary_probe_result=not_run\nfallback_used=0\nexit_code=pending\nerror_stage=none\n'

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
        case "$(lipc-get-prop com.lab126.powerd state 2>/dev/null)" in
            screenSaver|goingToScreenSaver|readyToSuspend|suspended) :;;
            *) lipc-set-prop com.lab126.appmgrd start 'app://com.lab126.KPPMainApp?view=KPP_LIBRARY' >/dev/null 2>&1 || true;;
        esac
    fi
    # Recovery never depends on FBInk. The native Library owns its refresh;
    # a failing runtime must not be invoked again here.
}
fail() {
    failure_code="$1"; shift
    trap - INT TERM HUP
    cleanup_probe
    if [ "$UI_CHILD_PENDING" = 1 ]; then UI_PID=$!; fi
    if [ -n "$UI_PID" ]; then
        kill -TERM "$UI_PID" 2>/dev/null || true
        wait "$UI_PID" 2>/dev/null || true
        UI_PID=
    fi
    printf 'error=%s\nerror_stage=%s\nexit_code=%s\n' "$*" "$STAGE" "$failure_code"
    write_status "$failure_code" "$*"
    restore_native
    command -v lipc-set-prop >/dev/null 2>&1 && \
        lipc-set-prop com.lab126.system toasterMessage '阅读记录启动失败，请查看 launch-last.log' >/dev/null 2>&1 || true
    [ "${READING_PRESERVE_LAUNCH_LOGS:-0}" != 1 ] && cp "$LOG" "$BASE/last-launch.stderr" 2>/dev/null || true
    [ -r "$DIAGNOSTICS" ] && READING_DIAGNOSTIC_INTERNAL=1 /bin/sh "$DIAGNOSTICS" >/dev/null 2>&1 || true
    exit "$failure_code"
}
cleanup_probe() {
    if type rr_cancel >/dev/null 2>&1; then rr_cancel; fi
    if [ -n "$PROBE_WORK" ]; then rm -f "$PROBE_WORK/timeout"; rmdir "$PROBE_WORK" 2>/dev/null || true; PROBE_WORK=; fi
    [ -n "$PROBE_PID" ] || return 0
    kill -TERM "$PROBE_PID" 2>/dev/null || true
    sleep 1
    kill -KILL "$PROBE_PID" 2>/dev/null || true
    wait "$PROBE_PID" 2>/dev/null || true
    PROBE_PID=
}
trap 'STAGE=interrupted; fail 70 "launcher interrupted"' INT TERM HUP

STAGE=environment
rr_perf environment_begin
[ -r "$DETECT_ENV" ] || fail 20 "missing environment detector: $DETECT_ENV"
. "$DETECT_ENV" || fail 21 'environment detection failed'
case "$HARD_FLOAT:$COMPAT_PROFILE:$ARCH" in
    0:default:*|1:default:*|0:fw518:*|1:fw518:*) :;;
    *) fail 21 'environment detector returned invalid ABI/profile';;
esac
printf 'firmware=%s\nkernel=%s\nmachine=%s\narch=%s\ndetected_env=%s\nhard_float=%s\n' \
    "$FIRMWARE_FULL" "${KERNEL:-unknown}" "${MACHINE:-unknown}" "$ARCH" "$COMPAT_PROFILE" "$HARD_FLOAT"

rr_perf environment_end
STAGE=preflight
rr_perf files_begin
for required_cmd in sh awk sed sort grep date cp mv mkdir sleep; do
    command -v "$required_cmd" >/dev/null 2>&1 || fail 30 "missing required command: $required_cmd"
done
[ -x "$MAIN" ] || fail 50 "UI entry is missing or not executable: $MAIN"
/bin/sh -n "$MAIN" || fail 53 "UI entry has a shell syntax error: $MAIN"
for required_file in "$RELEASE/ui-calendar/daily.png" "$RELEASE/ui-calendar/total.png" \
    "$RELEASE/ui-calendar/books.png" "$RELEASE/ui-calendar/day_detail.png" \
    "$RELEASE/ui-calendar/month_detail.png" "$RELEASE/ui-calendar/week_trend.png" \
    "$RELEASE/ui-calendar/book_detail.png" \
    "$RELEASE/ui-calendar/settings.png" "$RELEASE/ui-calendar/settings_custom.png" "$RELEASE/ui-calendar/settings-button.png" \
    "$RELEASE/bin/reading-config.sh" "$RELEASE/bin/reading-settings.sh" "$RELEASE/bin/reading-power.sh" \
    "$RELEASE/bin/reading-insights-touch-preflight.sh" "$RELEASE/bin/reading-insights-touch-probe.lua" "$RELEASE/bin/reading-insights-touch-ui.lua" "$RELEASE/bin/reading-insights-render.lua" \
    "$RELEASE/bin/reading-insights-cover.lua" "$RELEASE/bin/reading-insights-titles.lua" \
    "$RELEASE/bin/reading-insights-title-widths.lua" "$RELEASE/render-assets/dynamic-glyphs.pgm" \
    "$RELEASE/render-assets/dynamic-glyphs.tsv" "$BASE/fonts/NotoSansCJKsc-Regular.otf"; do
    [ -r "$required_file" ] || fail 51 "missing UI dependency: $required_file"
done
[ -r "$BASE/reading-time.tsv" ] || fail 41 'reading history is missing or unreadable'
[ -w "$BASE" ] || fail 40 'plugin directory is not writable'

rr_perf files_end
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

# Keep the historical KMC -> libkh -> PATH preference. ABI-specific KMC is
# an additional fallback, after the previously preferred libkh executable.
LUA_PRIMARY="$(command -v lua 2>/dev/null || true)"
READING_FBINK_CANDIDATES=
FBINK_IDENTITIES=
FBINK_TAB='	'
fbink_candidate_add() {
    fc_path=$1
    [ -n "$fc_path" ] || return 0
    [ -f "$fc_path" ] && [ -x "$fc_path" ] || {
        printf 'fbink_candidate=%s result=not_executable\n' "$fc_path"; return 0;
    }
    fc_real=$(realpath "$fc_path" 2>/dev/null || readlink -f "$fc_path" 2>/dev/null || printf '%s' "$fc_path")
    fc_stat=$(stat -Lc '%d:%i %s' "$fc_path" 2>/dev/null || true)
    fc_inode=${fc_stat% *}; fc_bytes=${fc_stat##* }; fc_sum=
    # Identity/size are enough for unique binaries. Read content only when a
    # second candidate could be an exact copy; never hash the sole runtime.
    while IFS="$FBINK_TAB" read -r fc_old fc_old_real fc_old_inode fc_old_bytes; do
        [ -n "$fc_old" ] || continue
        if [ "$fc_path" = "$fc_old" ] || [ "$fc_real" = "$fc_old_real" ] ||
           { [ -n "$fc_inode" ] && [ "$fc_inode" != - ] && [ "$fc_inode" = "$fc_old_inode" ]; }; then
            printf 'fbink_candidate=%s duplicate_of=%s\n' "$fc_path" "$fc_old"; return 0
        fi
        if [ -n "$fc_bytes" ] && [ "$fc_bytes" != - ] && [ "$fc_old_bytes" != - ] && [ "$fc_bytes" != "$fc_old_bytes" ]; then continue; fi
        fc_equal=0
        if command -v cmp >/dev/null 2>&1; then
            cmp -s "$fc_path" "$fc_old" && fc_equal=1
        else
            [ -n "$fc_sum" ] || fc_sum=$(cksum < "$fc_path" 2>/dev/null || true)
            fc_old_sum=$(cksum < "$fc_old" 2>/dev/null || true)
            [ -z "$fc_sum" ] || [ "$fc_sum" != "$fc_old_sum" ] || fc_equal=1
        fi
        if [ "$fc_equal" = 1 ]; then
            printf 'fbink_candidate=%s duplicate_of=%s\n' "$fc_path" "$fc_old"; return 0
        fi
    done <<EOF
$FBINK_IDENTITIES
EOF
    printf 'fbink_candidate=%s identity_real=%s identity_inode=%s identity_size=%s\n' "$fc_path" "$fc_real" "${fc_inode:--}" "${fc_bytes:--}"
    if [ -z "$READING_FBINK_CANDIDATES" ]; then READING_FBINK_CANDIDATES=$fc_path
    else READING_FBINK_CANDIDATES="$READING_FBINK_CANDIDATES
$fc_path"; fi
    FBINK_IDENTITIES="$FBINK_IDENTITIES
$fc_path$FBINK_TAB$fc_real$FBINK_TAB${fc_inode:--}$FBINK_TAB${fc_bytes:--}"
}
fbink_candidate_add "${READING_FBINK:-}"
fbink_candidate_add /var/local/kmc/bin/fbink
fbink_candidate_add /mnt/us/libkh/bin/fbink
if [ "$HARD_FLOAT" = 1 ]; then fbink_candidate_add /var/local/kmc/armhf/bin/fbink
else fbink_candidate_add /var/local/kmc/armel/bin/fbink; fi
fbink_candidate_add "$(command -v fbink 2>/dev/null || true)"
export READING_FBINK_CANDIDATES
FBINK_PRIMARY=${READING_FBINK_CANDIDATES%%
*}
printf 'primary_lua=%s\nprimary_fbink=%s\n' "${LUA_PRIMARY:-missing}" "${FBINK_PRIMARY:-missing}"

STAGE=runtime_probe
rr_perf lua_begin
# Normal probes use the lifecycle bound and reap their timer; the inline
# watchdog below also supports a damaged installation missing that library.
# A direct background child makes $! the exact runtime PID, never a process group.
if sleep 0.01 2>/dev/null; then PROBE_SLEEP=0.05; PROBE_MAX_TICKS=60
else PROBE_SLEEP=1; PROBE_MAX_TICKS=3; fi
printf 'probe_timeout_seconds=3\n'
probe_process() {
    PROBE_EXIT_CODE=none
    if type rr_run >/dev/null 2>&1; then
        PROBE_WORK="${READING_TMPDIR:-/tmp}/reading-records-lua.$$"
        mkdir "$PROBE_WORK" || { PROBE_WORK=; PROBE_RESULT=nonzero_exit; return 1; }
        RR_TIMEOUT_MARKER="$PROBE_WORK/timeout"; RR_PROBE_TRACK=1
        rr_run 3 "$@"; PROBE_EXIT_CODE=$?
        RR_PROBE_TRACK=0; RR_TIMEOUT_MARKER=
        if [ -f "$PROBE_WORK/timeout" ]; then PROBE_RESULT=timeout
        elif [ "$PROBE_EXIT_CODE" = 0 ]; then PROBE_RESULT=ok
        elif [ "$PROBE_EXIT_CODE" -ge 128 ]; then PROBE_RESULT=signal
        else PROBE_RESULT=nonzero_exit; fi
        rm -f "$PROBE_WORK/timeout"; rmdir "$PROBE_WORK"; PROBE_WORK=
        [ "$PROBE_RESULT" = ok ]; return $?
    fi
    "$@" & PROBE_PID=$!
    printf 'probe_child_pid=%s\n' "$PROBE_PID"
    probe_ticks=0
    while kill -0 "$PROBE_PID" 2>/dev/null; do
        if [ "$probe_ticks" -ge "$PROBE_MAX_TICKS" ]; then
            kill -TERM "$PROBE_PID" 2>/dev/null || true
            sleep 1
            kill -KILL "$PROBE_PID" 2>/dev/null || true
            wait "$PROBE_PID" 2>/dev/null || true
            PROBE_PID=
            PROBE_RESULT=timeout
            return 1
        fi
        sleep "$PROBE_SLEEP"
        probe_ticks=$((probe_ticks + 1))
    done
    wait "$PROBE_PID"; probe_rc=$?
    PROBE_PID=
    if [ "$probe_rc" -eq 0 ]; then PROBE_RESULT=ok
    elif [ "$probe_rc" -ge 128 ]; then PROBE_RESULT=signal
    else PROBE_RESULT=nonzero_exit; fi
    PROBE_EXIT_CODE=$probe_rc
    [ "$probe_rc" -eq 0 ]
}
probe_lua() {
    probe_candidate=$1; probe_label=$2
    printf 'probe_phase=lua_%s_begin\nprobe_candidate=%s\n' "$probe_label" "${probe_candidate:-missing}"
    if [ -z "$probe_candidate" ]; then PROBE_RESULT=missing
    elif [ ! -x "$probe_candidate" ]; then PROBE_RESULT=not_executable
    else
        # One bounded Lua process checks capability and every source. The checks
        # are unchanged; seven interpreter launches/polling waits become one.
        READING_PROBE_SOURCE="$RELEASE/bin/reading-insights-touch-probe.lua"
        READING_PROBE_SOURCES=
        for source in "$RELEASE/bin/reading-insights-touch-probe.lua" "$RELEASE/bin/reading-insights-touch-ui.lua" \
            "$RELEASE/bin/reading-insights-render.lua" "$RELEASE/bin/reading-insights-cover.lua" \
            "$RELEASE/bin/reading-insights-titles.lua" "$RELEASE/bin/reading-insights-title-widths.lua"; do
            printf 'lua_probe_source_begin=%s\n' "$source"
            READING_PROBE_SOURCES="$READING_PROBE_SOURCES
$source"
        done
        export READING_PROBE_SOURCE READING_PROBE_SOURCES
        probe_process "$probe_candidate" -e 'if type(loadfile)~="function" then os.exit(6) end; assert(io.open and os.rename and os.exit); for path in os.getenv("READING_PROBE_SOURCES"):gmatch("[^\n]+") do assert(loadfile(path)) end'
        printf 'lua_probe_basic_result=%s\nlua_probe_basic_exit_code=%s\n' "$PROBE_RESULT" "$PROBE_EXIT_CODE"
        [ "$PROBE_EXIT_CODE" != 2 ] || PROBE_RESULT=syntax_probe_failed
        printf 'lua_probe_source_result=%s\n' "$PROBE_RESULT"
        unset READING_PROBE_SOURCE READING_PROBE_SOURCES
    fi
    printf 'probe_phase=lua_%s_end\nlua_%s_result=%s\n' "$probe_label" "$probe_label" "$PROBE_RESULT"
    [ "$PROBE_RESULT" = ok ]
}

lua_result=not_run; fbink_result=not_run
if probe_lua "$LUA_PRIMARY" primary; then SELECTED_LUA=$LUA_PRIMARY; lua_result=ok
else
    lua_result=$PROBE_RESULT
    seen_lua=":$LUA_PRIMARY:"
    lua_fallback=0
    for candidate in /mnt/us/libkh/bin/lua /usr/bin/lua /usr/local/bin/lua; do
        case "$seen_lua" in *:"$candidate":*) continue;; esac
        seen_lua="$seen_lua$candidate:"
        lua_fallback=$((lua_fallback + 1))
        if probe_lua "$candidate" "fallback_$lua_fallback"; then
            SELECTED_LUA=$candidate; FALLBACK_USED=1
            printf 'lua_fallback_reason=primary Lua probe failed; candidate passed execution and syntax probes\n'
            break
        fi
    done
fi
rr_perf lua_end
fbink_result=deferred_actual_use
printf 'primary_probe_result=lua:%s,fbink:%s\nfallback_used=%s\n' "$lua_result" "$fbink_result" "$FALLBACK_USED"
printf 'selected_lua=%s\n' "$SELECTED_LUA"
[ "$SELECTED_LUA" != none ] || fail 32 'no Lua runtime passed execution and syntax probes'
[ -n "$READING_FBINK_CANDIDATES" ] || fail 31 'no executable FBInk candidate found'
printf 'selected_runtime=external-lua+external-fbink\nselected_lua=%s\nfbink_selection=deferred_actual_use\n' "$SELECTED_LUA"

# The UI calls "lua"; prioritize the probed executable without changing UI logic.
PATH="${SELECTED_LUA%/*}:$PATH"; export PATH
READING_FBINK="$FBINK_PRIMARY"; export READING_FBINK
READING_LUA_PREFLIGHT="$RELEASE/bin/reading-insights-touch-ui.lua"; export READING_LUA_PREFLIGHT
READING_LAUNCHER_CAPTURE=1; export READING_LAUNCHER_CAPTURE
READING_RELEASE="$RELEASE"; export READING_RELEASE
printf 'product_version=%s\nvariant=standard\nruntime_release=%s\nformal_entry=%s\n' "$PRODUCT_VERSION" "$RELEASE" "${READING_DOCUMENTS:-/mnt/us/documents}/reading-records.sh"
[ ! -r "$BASE/release-info" ] || cat "$BASE/release-info"
STAGE=power_snapshot
READING_ORIGINAL_POWER=$(lipc-get-prop com.lab126.powerd preventScreenSaver 2>/dev/null) || fail 33 'cannot save power state'
case "$READING_ORIGINAL_POWER" in ''|*[!0-9]*) fail 33 'invalid saved power state';; esac
POWER_SAVED=1; export READING_ORIGINAL_POWER
STAGE=ui
printf 'launch_command=%s\n' "$MAIN"
write_status 0 starting
rr_perf ui_dispatch
UI_ENTERED=1
UI_CHILD_PENDING=1
"$MAIN" & UI_PID=$!; UI_CHILD_PENDING=0
wait "$UI_PID"; launch_code=$?; UI_PID=
[ "$launch_code" -ne 90 ] || { printf 'frontend_exit=sleep_request\n'; launch_code=0; }
[ "$launch_code" -eq 0 ] || fail "$launch_code" 'UI process exited unexpectedly'
STAGE=complete
printf 'exit_code=0\nerror_stage=none\n'
write_status 0 ''
[ "${READING_PRESERVE_LAUNCH_LOGS:-0}" != 1 ] && cp "$LOG" "$BASE/last-launch.stdout" 2>/dev/null || true
exit 0
