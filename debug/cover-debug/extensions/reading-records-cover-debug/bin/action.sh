#!/bin/sh
/bin/sh /mnt/us/cover-debug.sh --latest
code=$?
printf 'timestamp=%s\nexit_code=%s\nlog=/mnt/us/reading-time/cover-debug.log\n' "$(date)" "$code" > /mnt/us/documents/reading-records-cover-debug-result.txt 2>/dev/null || true
exit "$code"
