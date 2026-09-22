#!/bin/sh

PKG="${READING_PACKAGE_DIR:-/mnt/us/native-reading-time-package}"
BASE="${READING_BASE:-/mnt/us/reading-time}"
DOCS="${READING_DOCUMENTS:-/mnt/us/documents}"
ACTION="${1:-install}"
LOG="$BASE/install.log"
DETECT_ENV="$PKG/compat/detect_env.sh"
DIAGNOSTICS="$PKG/diagnostics.sh"
VIEWER="$DOCS/阅读记录.sh"
JOB=native-reading-time
CONF="${READING_UPSTART_DIR:-/etc/upstart}/$JOB.conf"
ROOT_RW=0

# Compatibility route for the existing KUAL action name. All uninstall entry
# points execute the same standalone core from /tmp; no uninstall logic lives
# in this installer.
if [ "$ACTION" = uninstall-keep-data ]; then
    for UNINSTALL_CORE in "$BASE/bin/uninstall.sh" "$PKG/uninstall.sh"; do
        if [ -r "$UNINSTALL_CORE" ]; then
            UNINSTALL_TMP="${READING_TMPDIR:-/tmp}/reading-records-uninstall.$$"
            cp "$UNINSTALL_CORE" "$UNINSTALL_TMP" 2>/dev/null && chmod 700 "$UNINSTALL_TMP" 2>/dev/null || continue
            export READING_PACKAGE_DIR="$PKG"
            export READING_UNINSTALL_TEMP="$UNINSTALL_TMP"
            exec /bin/sh "$UNINSTALL_TMP"
        fi
    done
    printf 'STAGE=uninstall\nSTATUS=failed\nERROR=uninstaller_missing\n' > "$DOCS/reading-records-uninstall-result.txt" 2>/dev/null || true
    exit 127
fi

toast() { command -v lipc-set-prop >/dev/null 2>&1 && lipc-set-prop com.lab126.system toasterMessage "$1" >/dev/null 2>&1 || true; }
log() { mkdir -p "$BASE" 2>/dev/null || true; printf '%s: %s\n' "$(date)" "$*" >> "$LOG" 2>/dev/null || true; }
diagnose() { READING_PACKAGE_DIR="$PKG" READING_BASE="$BASE" READING_DOCUMENTS="$DOCS" /bin/sh "$DIAGNOSTICS" >/dev/null 2>&1 || true; }
fail() { log "ERROR action=$ACTION stage=${STAGE:-unknown}: $*"; toast "阅读记录操作失败，请查看诊断文件"; diagnose; exit 1; }
root_ro() {
    [ "$ROOT_RW" -eq 1 ] || return 0
    mntroot ro >/dev/null 2>&1 || /usr/sbin/mntroot ro >/dev/null 2>&1 || /sbin/mntroot ro >/dev/null 2>&1 || true
    ROOT_RW=0
}
root_rw() {
    [ "$ROOT_RW" -eq 1 ] && return 0
    if mntroot rw >/dev/null 2>&1 || /usr/sbin/mntroot rw >/dev/null 2>&1 || /sbin/mntroot rw >/dev/null 2>&1; then ROOT_RW=1; return 0; fi
    return 1
}
trap 'root_ro' EXIT
trap 'root_ro; exit 130' INT TERM HUP
scan_documents() {
    command -v lipc-set-prop >/dev/null 2>&1 || return 0
    lipc-set-prop com.lab126.scanner doFullScan 1 >/dev/null 2>&1 || lipc-set-prop com.lab126.scanner triggerUpdate 1 >/dev/null 2>&1 || true
}
atomic_copy() {
    source_file="$1"; target_file="$2"; target_mode="$3"; temporary_file="${target_file}.new.$$"
    cp "$source_file" "$temporary_file" && chmod "$target_mode" "$temporary_file" && mv "$temporary_file" "$target_file"
}

mkdir -p "$BASE" "$DOCS" 2>/dev/null || exit 1
[ -r "$DETECT_ENV" ] || fail "environment detector missing"
# shellcheck disable=SC1090
. "$DETECT_ENV" || fail "environment detection failed"
log "core action=$ACTION uid=$(id -u) firmware=$FIRMWARE_FULL profile=$COMPAT_PROFILE arch=$ARCH hard_float=$HARD_FLOAT"

case "$ACTION" in
    diagnostics)
        STAGE=diagnostics
        exec /bin/sh "$DIAGNOSTICS"
        ;;
    repair)
        STAGE=repair
        [ -f "$PKG/阅读记录-entry.sh" ] || fail "launcher entry payload missing"
        [ -f "$PKG/launch.sh" ] || fail "launcher payload missing"
        mkdir -p "$BASE/bin" "$BASE/compat" || fail "cannot create launcher directories"
        atomic_copy "$PKG/launch.sh" "$BASE/bin/launch.sh" 755 || fail "cannot repair core launcher"
        atomic_copy "$PKG/diagnostics.sh" "$BASE/bin/diagnostics.sh" 755 || fail "cannot repair diagnostics"
        atomic_copy "$PKG/compat/detect_env.sh" "$BASE/compat/detect_env.sh" 644 || fail "cannot repair environment detector"
        atomic_copy "$PKG/阅读记录-entry.sh" "$VIEWER" 755 || fail "cannot repair library launcher"
        scan_documents
        log "launcher repair completed"
        toast "阅读记录启动器已修复"
        exit 0
        ;;
    install|upgrade) :;;
    *) fail "unknown action: $ACTION";;
esac

STAGE=environment
[ "$(id -u)" -eq 0 ] || fail "installer must run as root (Scriptlet, KUAL or ;log runme)"
if [ "$COMPAT_PROFILE" = fw518 ] && [ "$HARD_FLOAT" != 1 ]; then fail "5.18.x detected without kindlehf loader"; fi
[ "$HARD_FLOAT" = 1 ] || fail "9.7.5 requires a kindlehf runtime"
[ -x /sbin/initctl ] || fail "Upstart initctl not found; service backend requires true-device verification"

STAGE=dependency
for install_cmd in sh awk sed sort grep date cp mv mkdir chmod cmp lua lipc-get-prop lipc-set-prop; do
    command -v "$install_cmd" >/dev/null 2>&1 || fail "missing required command: $install_cmd"
done
fbink_found=0
for fbink_candidate in /var/local/kmc/bin/fbink /mnt/us/libkh/bin/fbink; do
    [ -x "$fbink_candidate" ] && fbink_found=1
done
if [ "$fbink_found" -eq 0 ] && command -v fbink >/dev/null 2>&1; then fbink_found=1; fi
[ "$fbink_found" -eq 1 ] || fail "FBInk not found; install a kindlehf-compatible KMC/hotfix environment"

STAGE=payload
for required_file in Install-Native-Reading-Time.sh Install-Native-Reading-Time-Optimized.sh launch.sh diagnostics.sh uninstall.sh install-manifest.txt 阅读记录-entry.sh resources/reading-records-uninstall.sh resources/kual/reading-records-installer/bin/action.sh resources/kual/reading-records-installer/config.xml resources/kual/reading-records-installer/menu.json; do
    [ -f "$PKG/$required_file" ] || fail "missing payload: $required_file"
done

STAGE=install
if [ ! -f "$BASE/bin/native-reading-time-daemon.sh" ]; then
    log "fresh install: running base installer"
    /bin/sh "$PKG/Install-Native-Reading-Time.sh" || fail "base installer failed with exit code $?"
fi
log "running optimized 9.7.5 installer"
/bin/sh "$PKG/Install-Native-Reading-Time-Optimized.sh" || fail "optimized installer failed with exit code $?"

STAGE=complete
log "core installation completed"
toast "阅读记录 9.7.5 安装完成"
exit 0
