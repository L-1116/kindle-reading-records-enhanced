#!/bin/sh
# Name: 阅读统计 KS
# Author: Kindle Reading Records Enhanced
# Icon: /mnt/us/reading-time/assets/launcher-icon.png

LAUNCHER="/mnt/us/reading-time/bin/launch-ks.sh"
if [ -x "$LAUNCHER" ]; then exec "$LAUNCHER"; fi
printf '%s\n' "Reading Records KS launcher missing: $LAUNCHER" > /mnt/us/documents/reading-records-ks-launch-error.txt 2>/dev/null || true
exit 127
