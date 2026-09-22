#!/bin/sh
# Name: 阅读记录
# Author: Kindle Reading Records Enhanced
# Icon: /mnt/us/reading-time/assets/launcher-icon.png

LAUNCHER="/mnt/us/reading-time/bin/launch.sh"
if [ -x "$LAUNCHER" ]; then
    exec "$LAUNCHER"
fi

printf '%s\n' "Reading Records launcher missing: $LAUNCHER" > /mnt/us/documents/reading-records-launch-error.txt 2>/dev/null || true
if [ -r /mnt/us/native-reading-time-package/diagnostics.sh ]; then
    /bin/sh /mnt/us/native-reading-time-package/diagnostics.sh >/dev/null 2>&1 || true
fi
exit 127
