#!/bin/sh

BASE="${READING_BASE:-/mnt/us/reading-time}"
RELEASE="$BASE/releases/9.7.5-test"
MAIN="$RELEASE/bin/reading-records.sh"
DETECT_ENV="$BASE/compat/detect_env.sh"
DIAGNOSTICS="$BASE/bin/diagnostics.sh"
STATUS="$BASE/last-launch-status.txt"
STDOUT="$BASE/last-launch.stdout"
STDERR="$BASE/last-launch.stderr"
LAUNCH_LOG="$BASE/dashboard-launch.log"
STAGE=launcher

mkdir -p "$BASE" 2>/dev/null || exit 1
: > "$STDOUT" 2>/dev/null || exit 1
: > "$STDERR" 2>/dev/null || exit 1

write_status() {
    status_tmp="${STATUS}.new.$$"
    {
        printf 'timestamp=%s\n' "$(date 2>/dev/null || echo unknown)"
        printf 'stage=%s\nexit_code=%s\n' "$STAGE" "$1"
        printf 'firmware=%s\ndevice=%s\narch=%s\nhard_float=%s\nprofile=%s\n' \
            "${FIRMWARE_FULL:-unknown}" "${DEVICE_TYPE:-unknown}" "${ARCH:-unknown}" \
            "${HARD_FLOAT:-unknown}" "${COMPAT_PROFILE:-default}"
        [ -n "$2" ] && printf 'error=%s\n' "$2"
        :
    } > "$status_tmp" && mv "$status_tmp" "$STATUS"
}

run_diagnostics() {
    [ -r "$DIAGNOSTICS" ] && /bin/sh "$DIAGNOSTICS" >> "$STDOUT" 2>> "$STDERR" || true
}

fail() {
    failure_code="$1"; shift
    failure_message="$*"
    printf '%s: ERROR stage=%s code=%s %s\n' "$(date)" "$STAGE" "$failure_code" "$failure_message" >> "$STDERR"
    write_status "$failure_code" "$failure_message"
    command -v lipc-set-prop >/dev/null 2>&1 && lipc-set-prop com.lab126.system toasterMessage "阅读记录启动失败，请查看诊断文件" >/dev/null 2>&1 || true
    run_diagnostics
    exit "$failure_code"
}
trap 'STAGE=launcher; fail 70 "launcher interrupted"' INT TERM HUP

STAGE=environment
[ -r "$DETECT_ENV" ] || fail 20 "missing environment detector: $DETECT_ENV"
# shellcheck disable=SC1090
. "$DETECT_ENV" || fail 21 "environment detection failed"
if [ "$COMPAT_PROFILE" = fw518 ] && [ "$HARD_FLOAT" != 1 ]; then
    fail 22 "firmware 5.18.x requires kindlehf/hard-float runtime"
fi

STAGE=dependency
for required_cmd in sh awk sed sort grep date cp mv mkdir lua; do
    command -v "$required_cmd" >/dev/null 2>&1 || fail 30 "missing required command: $required_cmd"
done
FBINK="${READING_FBINK:-}"
if [ -z "$FBINK" ]; then
    for fbink_candidate in /var/local/kmc/bin/fbink /mnt/us/libkh/bin/fbink; do
        if [ -x "$fbink_candidate" ]; then FBINK="$fbink_candidate"; break; fi
    done
fi
if [ -z "$FBINK" ] && command -v fbink >/dev/null 2>&1; then FBINK="$(command -v fbink)"; fi
[ -n "$FBINK" ] && [ -x "$FBINK" ] || fail 31 "compatible FBInk executable not found"
export READING_FBINK="$FBINK"

STAGE=data
[ -d "$BASE" ] && [ -w "$BASE" ] || fail 40 "plugin directory is not writable: $BASE"
[ -r "$BASE/reading-time.tsv" ] || fail 41 "reading history is missing or unreadable"

STAGE=ui
[ -x "$MAIN" ] || fail 50 "UI entry is missing or not executable: $MAIN"
[ -r "$RELEASE/ui-calendar/daily.png" ] || fail 51 "UI assets are incomplete"
[ -r "$BASE/fonts/NotoSansCJKsc-Regular.otf" ] || fail 52 "font is missing"

export READING_LAUNCHER_CAPTURE=1
write_status 0 "starting"
"$MAIN" > "$STDOUT" 2> "$STDERR"
launch_code=$?
{
    printf '%s: launcher stage=%s exit_code=%s firmware=%s profile=%s\n' "$(date)" "$STAGE" "$launch_code" "$FIRMWARE_FULL" "$COMPAT_PROFILE"
    [ -s "$STDOUT" ] && cat "$STDOUT"
    [ -s "$STDERR" ] && cat "$STDERR"
} >> "$LAUNCH_LOG" 2>/dev/null || true
if [ "$launch_code" -ne 0 ]; then
    fail "$launch_code" "UI process exited unexpectedly"
fi

STAGE=complete
write_status 0 ""
exit 0
