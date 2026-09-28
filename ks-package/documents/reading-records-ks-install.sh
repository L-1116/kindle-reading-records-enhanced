#!/bin/sh
# Name: 阅读统计 KS 安装
# Author: Kindle Reading Records Enhanced

RESULT="/mnt/us/documents/reading-records-ks-install-result.txt"
PACKAGE="/mnt/us/native-reading-time-package"
if [ -r "$PACKAGE/install.sh" ]; then
    READING_PACKAGE_DIR="$PACKAGE" /bin/sh "$PACKAGE/install.sh" install
    code=$?
    printf 'timestamp=%s\nexit_code=%s\npackage=%s\n' "$(date)" "$code" "$PACKAGE" > "$RESULT" 2>/dev/null || true
    exit "$code"
fi
printf 'timestamp=%s\nexit_code=127\nerror=KS payload not found\n' "$(date)" > "$RESULT" 2>/dev/null || true
exit 127
