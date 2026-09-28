#!/bin/sh

BASE="${READING_BASE:-/mnt/us/reading-time}"
LOG="$BASE/reading_time_ks_debug.log"

note() { printf '%s [DIAG] %s\n' "$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date)" "$*" >> "$LOG" 2>/dev/null || true; }
note "begin"
note "model=$(sed -n '1p' /var/local/deviceType.txt 2>/dev/null || echo unavailable)"
note "firmware=$(sed -n '1p' /etc/prettyversion.txt 2>/dev/null || sed -n '1p' /etc/version.txt 2>/dev/null || echo unavailable)"
note "uname=$(uname -a 2>/dev/null || echo unavailable)"
note "orientation=$(lipc-get-prop com.lab126.winmgr accelerometer 2>/dev/null || echo unavailable)"
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
exit 0
