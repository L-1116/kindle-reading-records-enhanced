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
PROBE_PID=
UI_PID=
UI_CHILD_PENDING=0

mkdir -p "$BASE" 2>/dev/null || exit 1
: > "$LOG" 2>/dev/null || exit 1
: > "$BASE/last-launch.stdout" 2>/dev/null || true
: > "$BASE/last-launch.stderr" 2>/dev/null || true
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
        lipc-set-prop com.lab126.powerd preventScreenSaver 0 >/dev/null 2>&1 || true
        lipc-set-prop com.lab126.appmgrd start 'app://com.lab126.KPPMainApp?view=KPP_LIBRARY' >/dev/null 2>&1 || true
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
    cp "$LOG" "$BASE/last-launch.stderr" 2>/dev/null || true
    [ -r "$DIAGNOSTICS" ] && READING_DIAGNOSTIC_INTERNAL=1 /bin/sh "$DIAGNOSTICS" >/dev/null 2>&1 || true
    exit "$failure_code"
}
cleanup_probe() {
    [ -n "$PROBE_PID" ] || return 0
    kill -TERM "$PROBE_PID" 2>/dev/null || true
    sleep 1
    kill -KILL "$PROBE_PID" 2>/dev/null || true
    wait "$PROBE_PID" 2>/dev/null || true
    PROBE_PID=
}
trap 'STAGE=interrupted; fail 70 "launcher interrupted"' INT TERM HUP

STAGE=environment
[ -r "$DETECT_ENV" ] || fail 20 "missing environment detector: $DETECT_ENV"
. "$DETECT_ENV" || fail 21 'environment detection failed'
case "$HARD_FLOAT:$COMPAT_PROFILE:$ARCH" in
    0:default:*|1:default:*|0:fw518:*|1:fw518:*) :;;
    *) fail 21 'environment detector returned invalid ABI/profile';;
esac
printf 'firmware=%s\nkernel=%s\nmachine=%s\narch=%s\ndetected_env=%s\nhard_float=%s\n' \
    "$FIRMWARE_FULL" "${KERNEL:-unknown}" "${MACHINE:-unknown}" "$ARCH" "$COMPAT_PROFILE" "$HARD_FLOAT"

STAGE=preflight
for required_cmd in sh awk sed sort grep date cp mv mkdir sleep; do
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

# Keep the historical KMC -> libkh -> PATH preference. ABI-specific KMC is
# an additional fallback, after the previously preferred libkh executable.
LUA_PRIMARY="$(command -v lua 2>/dev/null || true)"
READING_FBINK_CANDIDATES=
FBINK_IDENTITIES=
fbink_candidate_add() {
    fc_path=$1
    [ -n "$fc_path" ] || return 0
    [ -f "$fc_path" ] && [ -x "$fc_path" ] || {
        printf 'fbink_candidate=%s result=not_executable\n' "$fc_path"; return 0;
    }
    fc_real=$(realpath "$fc_path" 2>/dev/null || readlink -f "$fc_path" 2>/dev/null || printf '%s' "$fc_path")
    fc_inode=$(stat -Lc '%d:%i' "$fc_path" 2>/dev/null || true)
    fc_sum=$(cksum < "$fc_path" 2>/dev/null || true)
    while IFS="$(printf '\t')" read -r fc_old fc_old_real fc_old_inode fc_old_sum; do
        [ -n "$fc_old" ] || continue
        if [ "$fc_path" = "$fc_old" ] || [ "$fc_real" = "$fc_old_real" ] ||
            { [ "$fc_inode" != - ] && [ -n "$fc_inode" ] && [ "$fc_inode" = "$fc_old_inode" ]; } ||
            { [ "$fc_sum" != - ] && [ -n "$fc_sum" ] && [ "$fc_sum" = "$fc_old_sum" ] &&
                { ! command -v cmp >/dev/null 2>&1 || cmp -s "$fc_path" "$fc_old"; }; } ||
            { [ -z "$fc_sum" ] && command -v cmp >/dev/null 2>&1 && cmp -s "$fc_path" "$fc_old"; }; then
            printf 'fbink_candidate=%s duplicate_of=%s\n' "$fc_path" "$fc_old"
            return 0
        fi
    done <<EOF
$FBINK_IDENTITIES
EOF
    printf 'fbink_candidate=%s identity_real=%s identity_inode=%s identity_cksum=%s\n' "$fc_path" "$fc_real" "${fc_inode:--}" "${fc_sum:--}"
    if [ -z "$READING_FBINK_CANDIDATES" ]; then READING_FBINK_CANDIDATES=$fc_path
    else READING_FBINK_CANDIDATES="$READING_FBINK_CANDIDATES
$fc_path"; fi
    fc_identity=$(printf '%s\t%s\t%s\t%s' "$fc_path" "$fc_real" "${fc_inode:--}" "${fc_sum:--}")
    FBINK_IDENTITIES="$FBINK_IDENTITIES
$fc_identity"
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
# The launcher is the watchdog. No separate timer process can outlive it.
# A direct background child makes $! the exact runtime PID, never a process group.
if sleep 0.1 2>/dev/null; then PROBE_SLEEP=0.2; PROBE_MAX_TICKS=15
else PROBE_SLEEP=1; PROBE_MAX_TICKS=3; fi
printf 'probe_timeout_seconds=3\n'
probe_process() {
    PROBE_EXIT_CODE=none
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
        printf 'lua_probe_basic_begin=%s\n' "$probe_candidate"
        probe_process "$probe_candidate" -e 'assert(type(loadfile)=="function")'
        printf 'lua_probe_basic_result=%s\nlua_probe_basic_exit_code=%s\n' "$PROBE_RESULT" "${PROBE_EXIT_CODE:-none}"
        if [ "$PROBE_RESULT" = ok ]; then
            for source in "$RELEASE/bin/reading-insights-touch-ui.lua" \
                "$RELEASE/bin/reading-insights-render.lua" "$RELEASE/bin/reading-insights-cover.lua" \
                "$RELEASE/bin/reading-insights-titles.lua" "$RELEASE/bin/reading-insights-title-widths.lua"; do
                printf 'lua_probe_source_begin=%s\n' "$source"
                READING_PROBE_SOURCE="$source"; export READING_PROBE_SOURCE
                probe_process "$probe_candidate" -e 'assert(loadfile(os.getenv("READING_PROBE_SOURCE")))'
                printf 'lua_probe_source_result=%s\nlua_probe_source_exit_code=%s\n' "$PROBE_RESULT" "${PROBE_EXIT_CODE:-none}"
                [ "$PROBE_RESULT" = ok ] || { [ "$PROBE_RESULT" != nonzero_exit ] || PROBE_RESULT=syntax_probe_failed; break; }
            done
            unset READING_PROBE_SOURCE
        fi
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
fbink_result=deferred_actual_use
printf 'primary_probe_result=lua:%s,fbink:%s\nfallback_used=%s\n' "$lua_result" "$fbink_result" "$FALLBACK_USED"
printf 'selected_lua=%s\n' "$SELECTED_LUA"
[ "$SELECTED_LUA" != none ] || fail 32 'no Lua runtime passed execution and syntax probes'
[ -n "$READING_FBINK_CANDIDATES" ] || fail 31 'no executable FBInk candidate found'
printf 'selected_runtime=external-lua+external-fbink\nselected_lua=%s\nfbink_selection=deferred_actual_use\n' "$SELECTED_LUA"

# The UI calls "lua"; prioritize the probed executable without changing UI logic.
PATH="${SELECTED_LUA%/*}:$PATH"; export PATH
READING_FBINK="$FBINK_PRIMARY"; export READING_FBINK
READING_LAUNCHER_CAPTURE=1; export READING_LAUNCHER_CAPTURE
STAGE=ui
printf 'launch_command=%s\n' "$MAIN"
write_status 0 starting
UI_ENTERED=1
UI_CHILD_PENDING=1
"$MAIN" & UI_PID=$!; UI_CHILD_PENDING=0
wait "$UI_PID"; launch_code=$?; UI_PID=
[ "$launch_code" -eq 0 ] || fail "$launch_code" 'UI process exited unexpectedly'
STAGE=complete
printf 'exit_code=0\nerror_stage=none\n'
write_status 0 ''
cp "$LOG" "$BASE/last-launch.stdout" 2>/dev/null || true
exit 0
