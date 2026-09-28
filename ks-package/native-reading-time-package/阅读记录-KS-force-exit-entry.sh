#!/bin/sh
# Name: 阅读统计 - 强制退出
# Author: Kindle Reading Records Enhanced

CORE="/mnt/us/reading-time/bin/force-exit-ks.sh"
if [ -x "$CORE" ]; then exec "$CORE"; fi
printf '%s\n' "Reading Records KS force-exit helper missing: $CORE" > /mnt/us/documents/reading-records-ks-force-exit-error.txt 2>/dev/null || true
exit 127
