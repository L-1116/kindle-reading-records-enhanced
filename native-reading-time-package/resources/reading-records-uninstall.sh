#!/bin/sh
# Name: 阅读记录卸载
# Author: Kindle Reading Records Enhanced

DOCS="${READING_DOCUMENTS:-/mnt/us/documents}"
TMP_ROOT="${READING_TMPDIR:-/tmp}"
RESULT="${READING_UNINSTALL_RESULT:-$DOCS/reading-records-uninstall-result.txt}"
for CORE in /mnt/us/reading-time/bin/uninstall.sh "${READING_PACKAGE_DIR:-/mnt/us/native-reading-time-package}/uninstall.sh" "$(dirname "$0")/../native-reading-time-package/uninstall.sh"; do
    if [ -r "$CORE" ]; then
        TEMP_CORE="$TMP_ROOT/reading-records-uninstall.$$"
        cp "$CORE" "$TEMP_CORE" 2>/dev/null && chmod 700 "$TEMP_CORE" 2>/dev/null || continue
        export READING_PACKAGE_DIR="${READING_PACKAGE_DIR:-/mnt/us/native-reading-time-package}"
        export READING_UNINSTALL_ENTRY="$0"
        export READING_UNINSTALL_TEMP="$TEMP_CORE"
        exec /bin/sh "$TEMP_CORE"
    fi
done
printf 'TIMESTAMP=%s\nSTAGE=uninstall\nSTATUS=failed\nEXIT_CODE=127\nERROR=uninstaller_missing\nPATH=/mnt/us/native-reading-time-package/uninstall.sh\n' "$(date)" > "$RESULT" 2>/dev/null || true
command -v lipc-set-prop >/dev/null 2>&1 && lipc-set-prop com.lab126.system toasterMessage "阅读记录卸载失败：找不到卸载程序" >/dev/null 2>&1 || true
exit 127
