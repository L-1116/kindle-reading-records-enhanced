#!/bin/sh

ACTION="${1:-diagnostics}"
PACKAGE="/mnt/us/native-reading-time-package"
if [ "$ACTION" = uninstall-keep-data ]; then
    for CORE in /mnt/us/reading-time/bin/uninstall.sh "$PACKAGE/uninstall.sh"; do
        if [ -r "$CORE" ]; then
            TEMP_CORE="/tmp/reading-records-uninstall.$$"
            cp "$CORE" "$TEMP_CORE" 2>/dev/null && chmod 700 "$TEMP_CORE" 2>/dev/null || continue
            export READING_PACKAGE_DIR="$PACKAGE"
            export READING_UNINSTALL_TEMP="$TEMP_CORE"
            exec /bin/sh "$TEMP_CORE"
        fi
    done
fi
if [ -r "$PACKAGE/install.sh" ]; then
    exec /bin/sh "$PACKAGE/install.sh" "$ACTION"
fi

if [ "$ACTION" = diagnostics ] && [ -r /mnt/us/reading-time/bin/diagnostics.sh ]; then
    exec /bin/sh /mnt/us/reading-time/bin/diagnostics.sh
fi

printf 'timestamp=%s\naction=%s\nerror=installer payload not found at %s\n' "$(date)" "$ACTION" "$PACKAGE" > /mnt/us/documents/reading-records-kual-error.txt 2>/dev/null || true
exit 127
