#!/bin/sh
# Name: 安装好之后，确认无误了再点这个
# Author: Kindle Reading Records Enhanced
BASE="/mnt/us/reading-time"
# Literal child paths must not traverse a substituted parent into user data.
[ ! -L /mnt/us ] && [ ! -L /mnt/us/documents ] && [ ! -L /mnt/us/extensions ] && [ ! -L /mnt/us/v4 ] || exit 1
[ "$(cat "$BASE/VERSION" 2>/dev/null)" = 9.7.6-5.19-normal ] && [ -f "$BASE/activation-verified" ] || exit 1
remove_owned() {
    [ -f "$1" ] && [ ! -L "$1" ] || return 0
    grep -Eq "$2" "$1" || return 0
    case "$1" in
        /mnt/us/RUNME.sh) rm -f "/mnt/us/RUNME.sh";;
        /mnt/us/README.txt) rm -f "/mnt/us/README.txt";;
        /mnt/us/PACKAGE-MANIFEST.json) rm -f "/mnt/us/PACKAGE-MANIFEST.json";;
        *) return 1;;
    esac
}
# Deliberately literal, reviewable paths. No globs and no runtime/data removal.
rm -f "/mnt/us/documents/reading-records-9.7.6-install.sh" || exit 1
rm -f "/mnt/us/documents/reading-records-9.7.6-data.tar" || exit 1
rm -f "/mnt/us/documents/阅读记录安装数据.tar" || exit 1
remove_owned "/mnt/us/RUNME.sh" "native-reading-time-package|READING_RECORDS_V4_RUNME" || exit 1
remove_owned "/mnt/us/README.txt" "Kindle 阅读记录|Kindle Reading Time|Kindle Reading Records" || exit 1
remove_owned "/mnt/us/PACKAGE-MANIFEST.json" "native-reading-time-package/" || exit 1
rm -rf "/mnt/us/native-reading-time-package" || exit 1
rm -f "/mnt/us/documents/reading-records-install.sh" || exit 1
rm -f "/mnt/us/documents/reading-records-v4-install.sh" || exit 1
rm -f "/mnt/us/documents/reading-records-uninstall.sh" || exit 1
rm -f "/mnt/us/documents/reading-records-diagnostic.sh" || exit 1
rm -f "/mnt/us/documents/reading-records-force-exit.sh" || exit 1
rm -f "/mnt/us/documents/reading-records-cover-debug.sh" || exit 1
rm -rf "/mnt/us/extensions/reading-records-installer" || exit 1
rm -f "/mnt/us/install-reading-records.log" || exit 1
rm -f "/mnt/us/documents/点这个安装，然后确认插件正常之前不要删文件.sh" || exit 1
rm -f "/mnt/us/documents/安装好之后，确认无误了再点这个.sh" || exit 1
rm -f "/mnt/us/documents/阅读记录封面诊断.sh" || exit 1
rm -f "/mnt/us/documents/reading-records-install-result.txt" || exit 1
rm -f "/mnt/us/documents/reading-records-cover-debug-result.txt" || exit 1
rm -f "/mnt/us/documents/reading-records-uninstall-result.txt" || exit 1
rm -f "/mnt/us/documents/reading-records-uninstall-diagnostic.txt" || exit 1
rm -f "/mnt/us/documents/reading-records-kual-error.txt" || exit 1
rm -f "/mnt/us/documents/reading-records-diagnostic.txt" || exit 1
rm -f "/mnt/us/documents/阅读记录诊断.txt" || exit 1
rm -f "/mnt/us/documents/reading-records-launch-error.txt" || exit 1
rm -f "/mnt/us/documents/reading-records-v4-install-result.txt" || exit 1
rm -f "/mnt/us/documents/reading-records-v4-install.log" || exit 1
rm -rf "/mnt/us/extensions/reading-records-cover-debug" || exit 1
rm -f "/mnt/us/cover-debug.sh" || exit 1
rm -f "/mnt/us/COVER-DEBUG-README.txt" || exit 1
rm -f "/mnt/us/COVER-V3-TEST-README.txt" || exit 1
rm -f "/mnt/us/V4-PAYLOAD" || exit 1
rm -f "/mnt/us/v4/cleanup.sh" || exit 1
# Self-removal is the final deletion. Then rescan the remaining formal entry.
rm -f /mnt/us/documents/reading-records-install-cleanup.sh || exit 1
lipc-set-prop com.lab126.scanner doFullScan 1 >/dev/null 2>&1 || true
