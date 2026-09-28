#!/bin/sh

ACTION="${1:-diagnostics}"
PACKAGE="/mnt/us/native-reading-time-package"
if [ -r "$PACKAGE/install.sh" ]; then exec /bin/sh "$PACKAGE/install.sh" "$ACTION"; fi
printf 'timestamp=%s\naction=%s\nerror=KS installer payload not found\n' "$(date)" "$ACTION" > /mnt/us/documents/reading-records-ks-kual-error.txt 2>/dev/null || true
exit 127
