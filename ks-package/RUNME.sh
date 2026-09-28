#!/bin/sh

CORE="/mnt/us/native-reading-time-package/install.sh"
if [ -r "$CORE" ]; then exec /bin/sh "$CORE" install; fi
printf '%s\n' "Reading Records KS installer missing: $CORE" > /mnt/us/documents/reading-records-ks-install-result.txt 2>/dev/null || true
exit 127
