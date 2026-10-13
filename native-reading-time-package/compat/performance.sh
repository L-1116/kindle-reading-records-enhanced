#!/bin/sh
# Bounded monotonic stage timing. Disable with startup-profile.disabled.
# No wall clock, resident monitor or history scan.
READING_PERF="${READING_PERF:-1}"
[ ! -e "$BASE/startup-profile.disabled" ] || READING_PERF=0
[ ! -L "${READING_PERF_LOG:-$BASE/startup-performance.log}" ] || READING_PERF=0
READING_PERF_LOG="${READING_PERF_LOG:-$BASE/startup-performance.log}"
export READING_PERF READING_PERF_LOG
rr_perf() {
    [ "${READING_PERF:-0}" = 1 ] || return 0
    IFS=' ' read -r rr_uptime rr_idle < "${READING_UPTIME_PATH:-/proc/uptime}" || return 0
    printf 'stage=%s uptime=%s pid=%s\n' "$1" "$rr_uptime" "$$" >> "${READING_PERF_LOG:-$BASE/startup-performance.log}" 2>/dev/null || true
}
