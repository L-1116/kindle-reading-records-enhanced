#!/bin/sh
# Name: 安装文件清理
# Author: Kindle Reading Records Enhanced

# The legacy filename supersedes old "阅读记录卸载" Scriptlets in place. Prefer
# the freshly extracted safe core so an old installed uninstaller is never run.
PKG="${READING_PACKAGE_DIR:-/mnt/us/native-reading-time-package}"
BASE="${READING_BASE:-/mnt/us/reading-time}"
TMP_ROOT="${READING_TMPDIR:-/tmp}"
for CORE in "$PKG/uninstall.sh" "$BASE/bin/uninstall.sh"; do
    [ -r "$CORE" ] && grep -Fq '# READING_RECORDS_CLEANUP_CORE_V1' "$CORE" || continue
    TEMP_CORE="$TMP_ROOT/reading-records-cleanup.$$"
    cp "$CORE" "$TEMP_CORE" 2>/dev/null && chmod 700 "$TEMP_CORE" 2>/dev/null || continue
    exec /bin/sh "$TEMP_CORE"
done
printf 'ABORT: safe Reading Records cleanup core not found\n' >&2
command -v lipc-set-prop >/dev/null 2>&1 && lipc-set-prop com.lab126.system toasterMessage "安装文件清理失败：缺少安全清理程序" >/dev/null 2>&1 || true
exit 127
