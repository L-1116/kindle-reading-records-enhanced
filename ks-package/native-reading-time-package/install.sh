#!/bin/sh
READING_VARIANT=ks; export READING_VARIANT

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
        echo "KS package does not expose an active-app uninstall action."
        echo "Reinstall/upgrade in place; reading-time.tsv is preserved."
        exit 2
        ;;
    install|upgrade|repair) :;;
    *) printf 'unknown KS action: %s\n' "$ACTION" >&2; exit 2;;
esac

[ "$(id -u)" -eq 0 ] || [ "${READING_ALLOW_NONROOT_TEST:-0}" = 1 ] || { printf 'KS installer must run as root\n' >&2; exit 1; }
. "$PKG/compat/lifecycle.sh" || exit 1
rr_device_log() { printf "%s\n" "$*" >&2; }
. "$PKG/compat/device_variant.sh" && . "$PKG/compat/ks_guard.sh" || exit 1
rr_ks_install_guard || { printf "%s\n" "$RR_DEVICE_ERROR" >&2; exit 1; }
[ -r "$PKG/compat/detect_env.sh" ] && . "$PKG/compat/detect_env.sh" || exit 1
for required_cmd in sh awk sed sort grep date cp mv mkdir chmod cmp lipc-get-prop lipc-set-prop; do
    command -v "$required_cmd" >/dev/null 2>&1 || { printf 'missing required command: %s\n' "$required_cmd" >&2; exit 1; }
done
[ -x "${READING_INITCTL:-/sbin/initctl}" ] || { printf 'Upstart unavailable\n' >&2; exit 1; }
fbink_found=0
if [ "$HARD_FLOAT" = 1 ]; then fbink_abi_path=/var/local/kmc/armhf/bin/fbink; else fbink_abi_path=/var/local/kmc/armel/bin/fbink; fi
for candidate in "${READING_FBINK:-}" /var/local/kmc/bin/fbink /mnt/us/libkh/bin/fbink "$fbink_abi_path" "$(command -v fbink 2>/dev/null)"; do [ ! -x "$candidate" ] || fbink_found=1; done
[ "$fbink_found" = 1 ] || { printf 'FBInk executable unavailable\n' >&2; exit 1; }
lua_found=0
for candidate in "${READING_LUA:-}" /mnt/us/libkh/bin/lua /usr/bin/lua /usr/local/bin/lua "$(command -v lua 2>/dev/null)"; do [ ! -x "$candidate" ] || lua_found=1; done
[ "$lua_found" = 1 ] || { printf 'Lua executable unavailable\n' >&2; exit 1; }
rr_lock || exit 75
trap 'rr_cancel; rr_root_restore || exit 1; rr_unlock' EXIT
trap 'rr_cancel; exit 130' INT TERM HUP
rr_mount_capture && rr_root_rw && rr_root_restore || exit 1
if [ ! -x "$BASE/bin/native-reading-time-daemon.sh" ]; then
    READING_PACKAGE_DIR="$PKG" rr_run 120 /bin/sh "$PKG/Install-Native-Reading-Time.sh" || exit $?
fi
READING_PACKAGE_DIR="$PKG" rr_run 120 /bin/sh "$PKG/Install-Native-Reading-Time-KS.sh"
