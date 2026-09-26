#!/bin/sh

ACTION="${1:-diagnostics}"
PACKAGE="/mnt/us/native-reading-time-package"
case "$ACTION" in
    cleanup|uninstall-keep-data)
        for CORE in "$PACKAGE/uninstall.sh" /mnt/us/reading-time/bin/uninstall.sh; do
            [ -r "$CORE" ] && grep -Fq '# READING_RECORDS_CLEANUP_CORE_V1' "$CORE" || continue
            TEMP_CORE="/tmp/reading-records-cleanup.$$"
            cp "$CORE" "$TEMP_CORE" 2>/dev/null && chmod 700 "$TEMP_CORE" 2>/dev/null || continue
            exec /bin/sh "$TEMP_CORE"
        done
        printf 'ABORT: safe Reading Records cleanup core not found\n' >&2
        exit 127
        ;;
esac
if [ -r "$PACKAGE/install.sh" ]; then
    exec /bin/sh "$PACKAGE/install.sh" "$ACTION"
fi

if [ "$ACTION" = diagnostics ] && [ -r /mnt/us/reading-time/bin/diagnostics.sh ]; then
    exec /bin/sh /mnt/us/reading-time/bin/diagnostics.sh
fi

printf 'timestamp=%s\naction=%s\nerror=installer payload not found at %s\n' "$(date)" "$ACTION" "$PACKAGE" > /mnt/us/documents/reading-records-kual-error.txt 2>/dev/null || true
exit 127
