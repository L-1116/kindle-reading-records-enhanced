#!/bin/sh

PKG="${READING_PACKAGE_DIR:-/mnt/us/native-reading-time-package}"
BASE="${READING_BASE:-/mnt/us/reading-time}"
ACTION="${1:-install}"

case "$ACTION" in
    diagnostics)
        if [ -x "$BASE/bin/diagnostics-ks.sh" ]; then exec "$BASE/bin/diagnostics-ks.sh"; fi
        exec /bin/sh "$PKG/diagnostics-ks.sh"
        ;;
    force-exit)
        if [ -x "$BASE/bin/force-exit-ks.sh" ]; then exec "$BASE/bin/force-exit-ks.sh"; fi
        exec /bin/sh "$PKG/force-exit-ks.sh"
        ;;
    cleanup|uninstall-keep-data)
        echo "KS test package does not expose an active-app uninstall action."
        echo "Reinstall/upgrade in place; reading-time.tsv is preserved."
        exit 2
        ;;
    install|upgrade|repair) :;;
    *) printf 'unknown KS action: %s\n' "$ACTION" >&2; exit 2;;
esac

[ "$(id -u)" -eq 0 ] || { printf 'KS installer must run as root\n' >&2; exit 1; }
if [ ! -x "$BASE/bin/native-reading-time-daemon.sh" ]; then
    READING_PACKAGE_DIR="$PKG" /bin/sh "$PKG/Install-Native-Reading-Time.sh" || exit $?
fi
READING_PACKAGE_DIR="$PKG" /bin/sh "$PKG/Install-Native-Reading-Time-KS.sh"
