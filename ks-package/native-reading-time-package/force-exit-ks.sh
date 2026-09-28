#!/bin/sh

BASE="${READING_BASE:-/mnt/us/reading-time}"
LOG="$BASE/reading_time_ks_debug.log"
PID_FILE="$BASE/reading-time-ks-ui.pid"

note() { printf '%s [EXIT] force-exit %s\n' "$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date)" "$*" >> "$LOG" 2>/dev/null || true; }
is_ks_process() {
    [ -r "/proc/$1/cmdline" ] || return 1
    tr '\000' ' ' < "/proc/$1/cmdline" 2>/dev/null | grep -Fq '/reading-records-ks.sh'
}

note "requested"
targets=""
if [ -r "$PID_FILE" ]; then
    main_pid="$(sed -n '1p' "$PID_FILE" 2>/dev/null)"
    case "$main_pid" in ''|*[!0-9]*) :;; *) is_ks_process "$main_pid" && targets="$targets $main_pid";; esac
fi
for proc in /proc/[0-9]*; do
    pid="${proc##*/}"
    [ -r "$proc/cmdline" ] || continue
    command_line="$(tr '\000' ' ' < "$proc/cmdline" 2>/dev/null)"
    case "$command_line" in
        *'/reading-records-ks.sh'*|*'/reading-insights-touch-ks.lua'*) targets="$targets $pid";;
    esac
done

for pid in $targets; do kill -TERM "$pid" 2>/dev/null || true; done
sleep 1
for pid in $targets; do [ -d "/proc/$pid" ] && kill -KILL "$pid" 2>/dev/null || true; done
rm -f "$PID_FILE" 2>/dev/null || true

lipc-set-prop com.lab126.winmgr eatTapMode 0 >/dev/null 2>&1 || true
lipc-set-prop com.lab126.powerd preventScreenSaver 0 >/dev/null 2>&1 || true
lipc-set-prop com.lab126.appmgrd start 'app://com.lab126.KPPMainApp?view=KPP_LIBRARY' >/dev/null 2>&1 || true
sleep 1
FBINK="${READING_FBINK:-}"
[ -x "$FBINK" ] || FBINK=/var/local/kmc/bin/fbink
[ -x "$FBINK" ] || FBINK=/mnt/us/libkh/bin/fbink
[ -x "$FBINK" ] && "$FBINK" -q -f -W GC16 -s >/dev/null 2>&1 || true
note "finished targets=${targets:-none}"
lipc-set-prop com.lab126.system toasterMessage "阅读统计 KS 已退出" >/dev/null 2>&1 || true
exit 0
