#!/bin/sh

BASE="${READING_BASE:-/mnt/us/reading-time}"
LOG="$BASE/reading_time_ks_debug.log"
DOCS="${READING_DOCUMENTS:-/mnt/us/documents}"
if [ "${READING_DIAGNOSTIC_INTERNAL:-0}" = 1 ]; then
    REPORT="$BASE/last-launch-diagnostic.txt"
else
    REPORT="${READING_DIAGNOSTIC_PATH:-$DOCS/reading-records-ks-diagnostic.txt}"
fi

note() { printf '%s [DIAG] %s\n' "$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date)" "$*" >> "$LOG" 2>/dev/null || true; }
note "begin"
note "model=$(sed -n '1p' /var/local/deviceType.txt 2>/dev/null || echo unavailable)"
note "firmware=$(sed -n '1p' /etc/prettyversion.txt 2>/dev/null || sed -n '1p' /etc/version.txt 2>/dev/null || echo unavailable)"
note "uname=$(uname -a 2>/dev/null || echo unavailable)"
note "accelerometer=$(lipc-get-prop com.lab126.winmgr accelerometer 2>/dev/null || echo unavailable)"
note "orientation_lock=$(lipc-get-prop com.lab126.winmgr orientationLock 2>/dev/null || echo unavailable)"
note "framebuffer=$(fbset 2>/dev/null | tr '\n' ';' || echo unavailable)"
note "virtual_size=$(cat /sys/class/graphics/fb0/virtual_size 2>/dev/null || echo unavailable) rotate=$(cat /sys/class/graphics/fb0/rotate 2>/dev/null || echo unavailable)"
for ep in /sys/class/input/event*; do
    [ -r "$ep/device/name" ] || continue
    note "input=/dev/input/${ep##*/} name=$(sed -n '1p' "$ep/device/name" 2>/dev/null) readable=$([ -r "/dev/input/${ep##*/}" ] && echo yes || echo no)"
done
for file in "$BASE/bin/launch-ks.sh" "$BASE/bin/force-exit-ks.sh" "$BASE/releases/9.7.5-ks-test1/bin/reading-records-ks.sh" "$BASE/releases/9.7.5-ks-test1/bin/reading-insights-touch-ks.lua" "$BASE/reading-time.tsv"; do
    note "file=$file exists=$([ -e "$file" ] && echo yes || echo no) readable=$([ -r "$file" ] && echo yes || echo no) executable=$([ -x "$file" ] && echo yes || echo no)"
done
note "pid_file=$(sed -n '1p' "$BASE/reading-time-ks-ui.pid" 2>/dev/null || echo none)"
note "end"
case "$REPORT" in */*) REPORT_DIR="${REPORT%/*}";; *) REPORT_DIR=.;; esac
mkdir -p "$REPORT_DIR" 2>/dev/null || exit 1
REPORT_TMP="${REPORT}.new.$$"
{
    printf 'Kindle Reading Records KS diagnostic\ngenerated=%s\n' "$(date 2>/dev/null || echo unknown)"
    printf 'mode=%s\n' "${READING_DIAGNOSTIC_INTERNAL:-manual}"
    printf '\n[Last launch status]\n'
    if [ -r "$BASE/last-launch-status.txt" ]; then cat "$BASE/last-launch-status.txt"; else echo unavailable; fi
    printf '\n[KS debug log, last 200 lines]\n'
    if [ -r "$LOG" ]; then tail -n 200 "$LOG"; else echo unavailable; fi
    printf '\n[Last stderr, last 80 lines]\n'
    if [ -r "$BASE/last-launch.stderr" ]; then tail -n 80 "$BASE/last-launch.stderr"; else echo unavailable; fi
} > "$REPORT_TMP" 2>&1 || { rm -f "$REPORT_TMP"; exit 1; }
chmod 600 "$REPORT_TMP" 2>/dev/null || true
mv "$REPORT_TMP" "$REPORT" || exit 1
printf 'Diagnostic written: %s\n' "$REPORT"
exit 0
