#!/bin/sh
PKG="${READING_PACKAGE_DIR:-/mnt/us/native-reading-time-package}"
BASE="${READING_BASE:-/mnt/us/reading-time}"
INSTALL_LOG="$BASE/install.log"
. "$PKG/compat/lifecycle.sh" || exit 1
fail() { printf 'ERROR base install: %s\n' "$*" >> "$INSTALL_LOG"; exit 1; }
mkdir -p "$BASE/bin" || exit 1
rr_lock || fail "lifecycle busy"
trap 'rr_cancel; rr_root_restore || exit 1; rr_unlock' EXIT
trap 'exit 130' INT TERM HUP
[ "$(id -u)" = 0 ] || [ "${READING_ALLOW_NONROOT_TEST:-0}" = 1 ] || fail "not root"
rr_mount_capture && rr_root_rw && rr_root_restore || fail "mount preflight failed"
[ -r "$PKG/native-reading-time-daemon.sh" ] || fail "missing daemon"
cp "$PKG/native-reading-time-daemon.sh" "$BASE/bin/native-reading-time-daemon.sh.new.$$" && chmod 755 "$BASE/bin/native-reading-time-daemon.sh.new.$$" && mv "$BASE/bin/native-reading-time-daemon.sh.new.$$" "$BASE/bin/native-reading-time-daemon.sh" || fail "daemon staging failed"
rr_install_helpers || fail "service resource staging failed"
/bin/sh "$BASE/bin/service-manager.sh" ensure >> "$INSTALL_LOG" 2>&1 || fail "service startup failed"
for history_attempt in 1 2; do [ ! -r "$BASE/reading-time.tsv" ] || break; /bin/sleep 1; done
[ -r "$BASE/reading-time.tsv" ] || fail "history missing after service start"
printf 'Base service installed; timing_status=unverified\n' >> "$INSTALL_LOG"
exit 0
