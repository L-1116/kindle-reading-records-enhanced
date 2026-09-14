#!/bin/sh

# Executed as root by typing ;log runme in the Kindle search bar.
PKG="/mnt/us/native-reading-time-package"
BASE="/mnt/us/reading-time"
DAEMON="$BASE/bin/native-reading-time-daemon.sh"
BASE_INSTALLER="$PKG/Install-Native-Reading-Time.sh"
OPTIMIZED_INSTALLER="$PKG/Install-Native-Reading-Time-Optimized.sh"
LOG="$BASE/install.log"

toast() { lipc-set-prop com.lab126.system toasterMessage "$1" >/dev/null 2>&1 || true; }
log() { echo "$(date): $1" >> "$LOG"; }
fail() { log "ERROR: $1"; toast "Installation failed: $1"; exit 1; }

mkdir -p "$BASE" || { toast "Installation failed: cannot create reading-time directory"; exit 1; }
log "RUNME entry, uid=$(id -u)"

[ -d "$PKG" ] || fail "installer payload directory not found: $PKG"
[ -f "$BASE_INSTALLER" ] || fail "installer not found: $BASE_INSTALLER"
[ -f "$OPTIMIZED_INSTALLER" ] || fail "installer not found: $OPTIMIZED_INSTALLER"

if [ ! -f "$DAEMON" ]; then
    log "fresh install detected; using base installation path"
    /bin/sh "$BASE_INSTALLER"
    status=$?
    if [ "$status" -ne 0 ]; then
        fail "base installation failed with exit code $status; optimized installation not started"
    fi
    [ -f "$DAEMON" ] || fail "base installation completed without installing daemon; optimized installation not started"
    log "base installation completed; continuing to optimized 9.7.4 installation"
else
    log "existing installation detected; using optimized upgrade path"
fi

/bin/sh "$OPTIMIZED_INSTALLER"
status=$?
if [ "$status" -ne 0 ]; then
    fail "optimized installation failed with exit code $status"
fi

log "RUNME completed successfully"
exit 0
