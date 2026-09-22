#!/bin/sh

# Lightweight, sourceable Kindle environment detection.  Tests may redirect
# the three input files without changing production defaults.
PRETTYVERSION_PATH="${READING_PRETTYVERSION_PATH:-/etc/prettyversion.txt}"
VERSION_PATH="${READING_VERSION_PATH:-/etc/version.txt}"
DEVICETYPE_PATH="${READING_DEVICETYPE_PATH:-/var/local/deviceType.txt}"
ARMHF_LOADER_PATH="${READING_ARMHF_LOADER_PATH:-/lib/ld-linux-armhf.so.3}"

read_first_line() {
    [ -r "$1" ] && sed -n '1p' "$1" 2>/dev/null || true
}

extract_firmware_version() {
    printf '%s\n' "$1" | awk '
        {
            for (i = 1; i <= NF; i++) {
                value = $i
                sub(/^[^0-9]*/, "", value)
                sub(/[^0-9.].*$/, "", value)
                sub(/\.$/, "", value)
                if (value ~ /^5\.[0-9]+(\.[0-9]+)*$/) {
                    print value
                    exit
                }
            }
        }'
}

# Print -1, 0 or 1.  Every dot-separated field is compared numerically, so
# 5.18.10 correctly sorts after 5.18.2.
version_compare() {
    awk -v left="$1" -v right="$2" 'BEGIN {
        ln = split(left, l, "."); rn = split(right, r, ".")
        n = ln > rn ? ln : rn
        for (i = 1; i <= n; i++) {
            lv = (i <= ln ? l[i] + 0 : 0)
            rv = (i <= rn ? r[i] + 0 : 0)
            if (lv < rv) { print -1; exit }
            if (lv > rv) { print 1; exit }
        }
        print 0
    }'
}

version_ge() { [ "$(version_compare "$1" "$2")" -ge 0 ]; }
version_gt() { [ "$(version_compare "$1" "$2")" -gt 0 ]; }
version_le() { [ "$(version_compare "$1" "$2")" -le 0 ]; }
version_lt() { [ "$(version_compare "$1" "$2")" -lt 0 ]; }

detect_reading_environment() {
    PRETTYVERSION_RAW="$(read_first_line "$PRETTYVERSION_PATH")"
    VERSION_RAW="$(read_first_line "$VERSION_PATH")"
    DEVICE_TYPE="$(read_first_line "$DEVICETYPE_PATH")"
    [ -n "$DEVICE_TYPE" ] || DEVICE_TYPE="unknown"

    FIRMWARE_FULL="$(extract_firmware_version "$PRETTYVERSION_RAW")"
    [ -n "$FIRMWARE_FULL" ] || FIRMWARE_FULL="$(extract_firmware_version "$VERSION_RAW")"
    [ -n "$FIRMWARE_FULL" ] || FIRMWARE_FULL="unknown"

    FIRMWARE_MAJOR="unknown"
    FIRMWARE_MINOR="unknown"
    case "$FIRMWARE_FULL" in
        [0-9]*.[0-9]*)
            FIRMWARE_MAJOR="${FIRMWARE_FULL%%.*}"
            firmware_tail="${FIRMWARE_FULL#*.}"
            FIRMWARE_MINOR="${firmware_tail%%.*}"
            ;;
    esac

    ARCH="${READING_ARCH_OVERRIDE:-$(uname -m 2>/dev/null)}"
    [ -n "$ARCH" ] || ARCH="unknown"
    HARD_FLOAT=0
    if [ -e "$ARMHF_LOADER_PATH" ]; then
        HARD_FLOAT=1
    else
        case "$ARCH" in armv7*hf|armv8*hf|armhf) HARD_FLOAT=1;; esac
    fi

    COMPAT_PROFILE=default
    if [ "$FIRMWARE_MAJOR" = 5 ] && [ "$FIRMWARE_MINOR" = 18 ]; then
        COMPAT_PROFILE=fw518
    fi

    export FIRMWARE_FULL FIRMWARE_MAJOR FIRMWARE_MINOR DEVICE_TYPE ARCH HARD_FLOAT COMPAT_PROFILE
}

detect_reading_environment
