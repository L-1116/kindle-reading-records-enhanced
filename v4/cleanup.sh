#!/bin/sh
# Name: 安装好之后，确认无误了再点这个
# Author: Kindle Reading Records
# READING_RECORDS_V4_CLEANUP
# Only installer artifacts are removed. This is never an app uninstaller.

MNT_US="${READING_MNT_US:-/mnt/us}"
DOCS="${READING_DOCUMENTS:-$MNT_US/documents}"
BASE="${READING_BASE:-$MNT_US/reading-time}"
LOG="$BASE/cleanup-last.log"
BOOT="$DOCS/点这个安装，然后确认插件正常之前不要删文件.sh"
PAYLOAD="$DOCS/阅读记录安装数据.tar"
SELF="$DOCS/安装好之后，确认无误了再点这个.sh"
PKG="$MNT_US/native-reading-time-package"
INVENTORY="$BASE/.v4-cleanup-inventory.$$"
ALLOWED="$BASE/.v4-cleanup-allowed.$$"
trap 'rm -f "$INVENTORY" "$ALLOWED"' EXIT

note() { printf '%s: %s\n' "$(date)" "$*" >> "$LOG" 2>/dev/null || true; }
abort() { note "ABORT $*"; printf 'ABORT: %s\n' "$*" >&2; exit 1; }
toast() { command -v lipc-set-prop >/dev/null 2>&1 && lipc-set-prop com.lab126.system toasterMessage "$1" >/dev/null 2>&1 || true; }
tar_cmd() { if command -v tar >/dev/null 2>&1; then tar "$@"; else busybox tar "$@"; fi; }
remove_file() { [ ! -e "$1" ] && [ ! -L "$1" ] && return 0; [ -f "$1" ] && [ ! -L "$1" ] || { note "SKIP non-file $1"; return 0; }; rm -f "$1" && note "REMOVED $1"; }
remove_owned() { [ ! -e "$1" ] && return 0; grep -Fq "$2" "$1" 2>/dev/null && remove_file "$1" || note "SKIP unowned $1"; }
tree_inventory_owned() {
    command -v find >/dev/null 2>&1 || return 1
    find "$1" -print > "$INVENTORY" || return 1
    while IFS= read -r entry; do
        relative=${entry#"$1"}
        case "$1:$relative" in
            "$MNT_US/extensions/reading-records-installer:"|"$MNT_US/extensions/reading-records-installer:/bin"|"$MNT_US/extensions/reading-records-installer:/bin/action.sh"|"$MNT_US/extensions/reading-records-installer:/config.xml"|"$MNT_US/extensions/reading-records-installer:/menu.json") :;;
            "$MNT_US/extensions/reading-records-cover-debug:"|"$MNT_US/extensions/reading-records-cover-debug:/bin"|"$MNT_US/extensions/reading-records-cover-debug:/bin/action.sh"|"$MNT_US/extensions/reading-records-cover-debug:/config.xml"|"$MNT_US/extensions/reading-records-cover-debug:/menu.json") :;;
            "$MNT_US/debug/cover-debug:"|"$MNT_US/debug/cover-debug:/README.txt"|"$MNT_US/debug/cover-debug:/cover-debug.sh"|"$MNT_US/debug/cover-debug:/build_debug_kit.py"|"$MNT_US/debug/cover-debug:/documents"|"$MNT_US/debug/cover-debug:/documents/阅读记录封面诊断.sh"|"$MNT_US/debug/cover-debug:/extensions"|"$MNT_US/debug/cover-debug:/extensions/reading-records-cover-debug"|"$MNT_US/debug/cover-debug:/extensions/reading-records-cover-debug/bin"|"$MNT_US/debug/cover-debug:/extensions/reading-records-cover-debug/bin/action.sh"|"$MNT_US/debug/cover-debug:/extensions/reading-records-cover-debug/config.xml"|"$MNT_US/debug/cover-debug:/extensions/reading-records-cover-debug/menu.json") :;;
            *) exit 1;;
        esac
        [ ! -L "$entry" ] || exit 1
    done < "$INVENTORY"
}
remove_tree() { [ ! -e "$1" ] && return 0; [ -d "$1" ] && [ ! -L "$1" ] && [ -f "$1/$2" ] && grep -Fq "$3" "$1/$2" && tree_inventory_owned "$1" || { note "SKIP unowned tree $1"; return 0; }; rm -rf "$1" && note "REMOVED $1"; }

[ -r "$BASE/release-info" ] || abort 'V4 activation metadata missing'
[ -w "$BASE" ] || abort 'plugin directory not writable'
grep -Fqx 'release_family=V4' "$BASE/release-info" || abort 'release family mismatch'
variant=$(sed -n 's/^variant=//p' "$BASE/release-info" | sed -n '1p')
case "$variant" in
    standard) version=V4; launcher="$BASE/bin/launch.sh"; resolver="$BASE/releases/9.7.5-test/bin/reading-records.sh";;
    ks) version=V4-KS; launcher="$BASE/bin/launch-ks.sh"; resolver="$BASE/releases/9.7.5-ks-test1/bin/reading-records-ks.sh";;
    *) abort 'unknown installed variant';;
esac
[ -r "$BASE/VERSION" ] && grep -Fqx "$version" "$BASE/VERSION" || abort 'version mismatch'
[ -x "$launcher" ] && [ -x "$resolver" ] && [ -x "$DOCS/阅读记录.sh" ] && [ -x "$BASE/bin/native-reading-time-daemon.sh" ] && [ -r "$BASE/reading-time.tsv" ] && [ -r "${READING_UPSTART_DIR:-/etc/upstart}/native-reading-time.conf" ] || abort 'active runtime not verified'
[ "$variant" != ks ] || [ -x "$BASE/bin/force-exit-ks.sh" ] || abort 'KS helper missing'
note "verified activation $version"

# Detect ownership before any deletion. A copied personal file with a familiar
# name stays untouched unless it has the known installer signature.
if [ -e "$BOOT" ]; then grep -Fq '# READING_RECORDS_V4_BOOTSTRAP' "$BOOT" || abort 'bootstrap name occupied by unknown file'; fi
if [ -e "$PKG" ]; then
    command -v find >/dev/null 2>&1 || abort 'find unavailable for package inventory'
    [ -d "$PKG" ] && [ ! -L "$PKG" ] || abort 'old package tree has unknown ownership'
    case "$variant" in
        standard) [ -f "$PKG/阅读记录-optimized.sh" ] && [ -f "$PKG/Install-Native-Reading-Time.sh" ] && grep -Fq 'native-reading-time-daemon.sh' "$PKG/Install-Native-Reading-Time.sh" || abort 'old standard package signature missing';;
        ks) [ -f "$PKG/阅读记录-ks.sh" ] && [ -f "$PKG/Install-Native-Reading-Time-KS.sh" ] && grep -Fq 'reading-records-ks.sh' "$PKG/Install-Native-Reading-Time-KS.sh" || abort 'old KS package signature missing';;
    esac
    [ -f "$BOOT" ] && [ -r "$PAYLOAD" ] || abort 'cannot verify old package without V4 payload'
    if command -v cksum >/dev/null 2>&1; then
        expected=$(sed -n "s/^PAYLOAD_CKSUM='\([0-9]*\)'$/\1/p" "$BOOT" | sed -n '1p')
        actual=$(cksum < "$PAYLOAD" | awk '{print $1}')
        [ -n "$expected" ] && [ "$expected" = "$actual" ] || abort 'V4 payload checksum changed'
    fi
    (cd "$DOCS" && tar_cmd -tf './阅读记录安装数据.tar') > "$ALLOWED" 2>/dev/null || abort 'cannot list V4 payload'
    find "$PKG" -print > "$INVENTORY" || abort 'old package inventory failed'
    while IFS= read -r path; do
        [ "$path" = "$PKG" ] && continue
        relative=${path#"$MNT_US/"}
        if [ -d "$path" ] && [ ! -L "$path" ]; then
            grep -Fq "$relative/" "$ALLOWED" || exit 1
        else
            grep -Fqx "$relative" "$ALLOWED" || exit 1
        fi
    done < "$INVENTORY" || abort 'old package contains unknown files'
fi

for name in reading-records-install-result.txt reading-records-ks-install-result.txt reading-records-cover-debug-result.txt reading-records-uninstall-result.txt reading-records-uninstall-diagnostic.txt reading-records-kual-error.txt reading-records-ks-kual-error.txt reading-records-diagnostic.txt reading-records-ks-diagnostic.txt 阅读记录诊断.txt reading-records-launch-error.txt reading-records-v4-install-result.txt reading-records-v4-install.log; do remove_file "$DOCS/$name" || exit 1; done
remove_file "$BASE/cover-debug.log" || exit 1
remove_owned "$DOCS/阅读记录封面诊断.sh" 'Cover Debug' || exit 1
remove_owned "$MNT_US/cover-debug.sh" 'cover-debug.log' || exit 1
remove_owned "$MNT_US/COVER-DEBUG-README.txt" 'Cover Debug' || exit 1
remove_owned "$MNT_US/COVER-V3-TEST-README.txt" 'Compatibility V3' || exit 1
remove_tree "$MNT_US/debug/cover-debug" 'cover-debug.sh' 'cover-debug.log' || exit 1
rmdir "$MNT_US/debug" 2>/dev/null || true
remove_tree "$MNT_US/extensions/reading-records-cover-debug" 'config.xml' 'reading-records-cover-debug' || exit 1
remove_owned "$DOCS/reading-records-install.sh" 'native-reading-time-package' || exit 1
remove_owned "$DOCS/reading-records-ks-install.sh" 'native-reading-time-package' || exit 1
remove_owned "$DOCS/reading-records-uninstall.sh" '# Name: 安装文件清理' || exit 1
remove_tree "$MNT_US/extensions/reading-records-installer" 'config.xml' 'reading-records-installer' || exit 1
remove_owned "$MNT_US/RUNME.sh" 'native-reading-time-package' || exit 1
remove_owned "$MNT_US/RUNME.sh" 'READING_RECORDS_V4_RUNME' || exit 1
remove_owned "$MNT_US/README.txt" 'Kindle 阅读记录' || exit 1
remove_owned "$MNT_US/README.txt" 'Kindle Reading Time' || exit 1
if [ -d "$PKG" ]; then rm -rf "$PKG" || exit 1; note "REMOVED $PKG"; fi
remove_owned "$MNT_US/PACKAGE-MANIFEST.json" 'native-reading-time-package/' || exit 1
remove_owned "$MNT_US/PACKAGE-MANIFEST-KS.json" 'native-reading-time-package/' || exit 1
remove_owned "$MNT_US/V4-PAYLOAD" 'release_family=V4' || exit 1
remove_owned "$MNT_US/v4/cleanup.sh" '# READING_RECORDS_V4_CLEANUP' || exit 1
rmdir "$MNT_US/v4" 2>/dev/null || true
had_boot=0
if [ -f "$BOOT" ]; then had_boot=1; fi
remove_owned "$BOOT" '# READING_RECORDS_V4_BOOTSTRAP' || exit 1
if [ "$had_boot" -eq 1 ] && [ ! -e "$BOOT" ]; then remove_file "$PAYLOAD" || exit 1; fi
note 'result=SUCCESS'
toast '安装文件清理完成'
remove_owned "$SELF" '# READING_RECORDS_V4_CLEANUP' || exit 1
exit 0
