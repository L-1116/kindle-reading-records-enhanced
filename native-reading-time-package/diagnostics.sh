#!/bin/sh

BASE="${READING_BASE:-/mnt/us/reading-time}"
DOCS="${READING_DOCUMENTS:-/mnt/us/documents}"
MNT_US="${READING_MNT_US:-/mnt/us}"
DETECT_ENV="${READING_DETECT_ENV:-$BASE/compat/detect_env.sh}"
[ -r "$DETECT_ENV" ] || DETECT_ENV="${READING_PACKAGE_DIR:-/mnt/us/native-reading-time-package}/compat/detect_env.sh"

ASCII_REPORT="${READING_DIAGNOSTIC_PATH:-$DOCS/reading-records-diagnostic.txt}"
CHINESE_REPORT="$DOCS/阅读记录诊断.txt"
REPORT_TMP="${ASCII_REPORT}.new.$$"

if [ -r "$DETECT_ENV" ]; then
    # shellcheck disable=SC1090
    . "$DETECT_ENV"
else
    FIRMWARE_FULL=unknown; FIRMWARE_MAJOR=unknown; FIRMWARE_MINOR=unknown
    DEVICE_TYPE=unknown; ARCH="$(uname -m 2>/dev/null || echo unknown)"
    HARD_FLOAT=unknown; COMPAT_PROFILE=default
    PRETTYVERSION_PATH="${READING_PRETTYVERSION_PATH:-/etc/prettyversion.txt}"
    VERSION_PATH="${READING_VERSION_PATH:-/etc/version.txt}"
    DEVICETYPE_PATH="${READING_DEVICETYPE_PATH:-/var/local/deviceType.txt}"
fi

present() { [ -e "$1" ] && printf 'present: %s\n' "$1" || printf 'missing: %s\n' "$1"; }
command_status() {
    if command -v "$1" >/dev/null 2>&1; then printf '%-18s available (%s)\n' "$1" "$(command -v "$1")"
    else printf '%-18s missing\n' "$1"; fi
}
permission_status() {
    diagnostic_path="$1"
    printf '%s: exists=%s readable=%s writable=%s executable=%s\n' "$diagnostic_path" \
        "$([ -e "$diagnostic_path" ] && echo yes || echo no)" \
        "$([ -r "$diagnostic_path" ] && echo yes || echo no)" \
        "$([ -w "$diagnostic_path" ] && echo yes || echo no)" \
        "$([ -x "$diagnostic_path" ] && echo yes || echo no)"
}

mkdir -p "$DOCS" 2>/dev/null || exit 1
{
    echo "Kindle Reading Records diagnostic"
    echo "generated=$(date 2>/dev/null || echo unknown)"
    echo
    echo "[Device]"
    printf 'prettyversion=%s\n' "$(sed -n '1p' "$PRETTYVERSION_PATH" 2>/dev/null || echo unavailable)"
    printf 'version.txt=%s\n' "$(sed -n '1p' "$VERSION_PATH" 2>/dev/null || echo unavailable)"
    printf 'deviceType=%s\n' "$(sed -n '1p' "$DEVICETYPE_PATH" 2>/dev/null || echo unavailable)"
    printf 'uname=%s\n' "$(uname -a 2>/dev/null || echo unavailable)"
    printf 'architecture=%s\n' "$ARCH"
    echo
    echo "[Compatibility]"
    printf 'firmware_full=%s\nfirmware_major=%s\nfirmware_minor=%s\n' "$FIRMWARE_FULL" "$FIRMWARE_MAJOR" "$FIRMWARE_MINOR"
    printf 'hard_float=%s\ncompat_profile=%s\n' "$HARD_FLOAT" "$COMPAT_PROFILE"
    echo
    echo "[Jailbreak]"
    present /var/local/kmc
    present "$MNT_US/libkh"
    present /var/local/mkk
    present "$MNT_US/linkjail"
    present /var/local/kmc/bin/sh_integration_launcher
    present /usr/bin/logThis.sh
    present "$MNT_US/RUNME.sh"
    echo "Note: marker presence is evidence only; this tool does not modify or emulate jailbreak/hotfix components."
    echo
    echo "[KUAL/MRPI]"
    present "$MNT_US/extensions"
    present "$MNT_US/extensions/MRInstaller"
    present "$MNT_US/mrpackages"
    echo
    echo "[Plugin]"
    permission_status "$BASE"
    permission_status "$BASE/bin/launch.sh"
    permission_status "$BASE/releases/9.7.5-test/bin/reading-records.sh"
    permission_status "$BASE/releases/9.7.5-test/bin/reading-insights-cover.lua"
    permission_status "$BASE/reading-time.tsv"
    permission_status "$BASE/book-covers"
    permission_status "$DOCS/阅读记录.sh"
    echo
    echo "[Dependencies]"
    for diagnostic_cmd in sh awk sed sort grep head tail date uname id cat tr stat cksum cp mv rm mkdir chmod sleep sync killall tee lua sqlite3 unzip fbset mntroot lipc-get-prop lipc-set-prop lipc-wait-event file readelf; do
        command_status "$diagnostic_cmd"
    done
    permission_status /var/local/kmc/bin/fbink
    permission_status "$MNT_US/libkh/bin/fbink"
    permission_status /sbin/initctl
    echo
    echo "[Native ABI]"
    echo "The Reading Records payload ships no ELF executable or shared library."
    for native_candidate in /var/local/kmc/bin/fbink "$MNT_US/libkh/bin/fbink"; do
        [ -x "$native_candidate" ] || continue
        printf 'external_binary=%s\n' "$native_candidate"
        command -v file >/dev/null 2>&1 && file "$native_candidate" 2>&1 || echo "file: unavailable"
        if command -v readelf >/dev/null 2>&1; then
            readelf -h "$native_candidate" 2>&1 | sed -n '1,40p'
            readelf -A "$native_candidate" 2>&1 | sed -n '1,80p'
            readelf -l "$native_candidate" 2>&1 | grep 'Requesting program interpreter' || true
            readelf -d "$native_candidate" 2>&1 | grep 'NEEDED' || true
        else
            echo "readelf: unavailable"
        fi
    done
    echo
    echo "[Last Launch]"
    if [ -r "$BASE/last-launch-status.txt" ]; then sed -n '1,80p' "$BASE/last-launch-status.txt"; else echo "status unavailable"; fi
    echo "-- stdout (last 80 lines) --"
    if [ -r "$BASE/last-launch.stdout" ]; then tail -n 80 "$BASE/last-launch.stdout"; else echo "unavailable"; fi
    echo "-- stderr (last 80 lines) --"
    if [ -r "$BASE/last-launch.stderr" ]; then tail -n 80 "$BASE/last-launch.stderr"; else echo "unavailable"; fi
    echo
    echo "[Cover]"
    printf 'debug=%s\n' "$([ -e "$BASE/cover-debug.enabled" ] && echo enabled || echo disabled)"
    permission_status "$BASE/book-cover-cache.tsv"
    permission_status "$BASE/book-cover-misses.tsv"
    if [ -r "$BASE/cover-debug.log" ]; then tail -n 120 "$BASE/cover-debug.log"; else echo "cover debug log unavailable"; fi
} > "$REPORT_TMP" 2>&1 || { rm -f "$REPORT_TMP"; exit 1; }

chmod 600 "$REPORT_TMP" 2>/dev/null || true
mv "$REPORT_TMP" "$ASCII_REPORT" || exit 1
if [ "$CHINESE_REPORT" != "$ASCII_REPORT" ]; then
    cp "$ASCII_REPORT" "${CHINESE_REPORT}.new.$$" 2>/dev/null && chmod 600 "${CHINESE_REPORT}.new.$$" 2>/dev/null && mv "${CHINESE_REPORT}.new.$$" "$CHINESE_REPORT" 2>/dev/null || true
fi
printf 'Diagnostic written: %s\n' "$ASCII_REPORT"
exit 0
