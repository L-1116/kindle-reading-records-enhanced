#!/bin/sh
# Name: 阅读记录安装
# Author: Kindle Reading Records Enhanced

RESULT="/mnt/us/documents/reading-records-install-result.txt"
for PACKAGE_DIR in /mnt/us/native-reading-time-package "$(dirname "$0")/../native-reading-time-package"; do
    if [ -r "$PACKAGE_DIR/install.sh" ]; then
        export READING_PACKAGE_DIR="$PACKAGE_DIR"
        /bin/sh "$PACKAGE_DIR/install.sh" install
        code=$?
        printf 'timestamp=%s\nexit_code=%s\npackage=%s\n' "$(date)" "$code" "$PACKAGE_DIR" > "$RESULT" 2>/dev/null || true
        exit "$code"
    fi
done
printf 'timestamp=%s\nexit_code=127\nerror=payload not found\n' "$(date)" > "$RESULT" 2>/dev/null || true
exit 127
