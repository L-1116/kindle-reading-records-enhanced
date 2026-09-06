#!/bin/sh

PKG="/mnt/us/native-reading-time-package"
BASE="/mnt/us/reading-time"
DATA="$BASE/reading-time.tsv"
LOG="$BASE/install.log"
JOB="native-reading-time"
CONF="/etc/upstart/${JOB}.conf"
DAEMON="$BASE/bin/native-reading-time-daemon.sh"
VIEWER="/mnt/us/documents/阅读记录.sh"
RELEASE="$BASE/releases/9.6.8-summary-sync-fix"
STAGE="$BASE/.install-9.6.8-summary-sync-fix.$$"
ROOT_RW=0; ACTIVATED=0; SERVICE_WAS_RUNNING=0; ROLLBACK_DONE=0

mkdir -p "$BASE" || exit 1
exec >> "$LOG" 2>&1
echo "$(date): optimized installer entered, uid=$(id -u), pid=$$"
toast() { lipc-set-prop com.lab126.system toasterMessage "$1" >/dev/null 2>&1 || true; }
root_ro() { if [ "$ROOT_RW" -eq 1 ]; then mntroot ro >/dev/null 2>&1 || /usr/sbin/mntroot ro >/dev/null 2>&1 || /sbin/mntroot ro >/dev/null 2>&1 || true; ROOT_RW=0; fi; }
root_rw() {
    [ "$ROOT_RW" -eq 1 ] && return 0
    if mntroot rw >/dev/null 2>&1 || /usr/sbin/mntroot rw >/dev/null 2>&1 || /sbin/mntroot rw >/dev/null 2>&1; then ROOT_RW=1; return 0; fi
    return 1
}
cleanup_stage() { case "$STAGE" in /mnt/us/reading-time/.install-9.6.8-summary-sync-fix.[0-9]*) rm -rf "$STAGE";; esac; rm -f "$DATA.bak.new.$$"; }

rollback() {
    [ "$ROLLBACK_DONE" -eq 0 ] || return; ROLLBACK_DONE=1
    echo "$(date): rolling back optimized installation"; /sbin/initctl stop "$JOB" >/dev/null 2>&1 || true
    if [ -f "$STAGE/rollback/daemon" ]; then cp "$STAGE/rollback/daemon" "$DAEMON.rollback-new" && chmod 755 "$DAEMON.rollback-new" && mv "$DAEMON.rollback-new" "$DAEMON"; elif [ -f "$STAGE/rollback/no-daemon" ]; then rm -f "$DAEMON"; fi
    if [ -f "$STAGE/rollback/viewer" ]; then cp "$STAGE/rollback/viewer" "$VIEWER.rollback-new" && chmod 755 "$VIEWER.rollback-new" && mv "$VIEWER.rollback-new" "$VIEWER"; elif [ -f "$STAGE/rollback/no-viewer" ]; then rm -f "$VIEWER"; fi
    if [ -f "$STAGE/rollback/conf" ]; then
        if root_rw; then cp "$STAGE/rollback/conf" "$CONF.rollback-new" && chmod 644 "$CONF.rollback-new" && mv "$CONF.rollback-new" "$CONF"; else echo "$(date): WARNING: could not remount rootfs during rollback"; fi
    elif [ -f "$STAGE/rollback/no-conf" ]; then
        if root_rw; then rm -f "$CONF"; else echo "$(date): WARNING: could not remount rootfs during rollback"; fi
    fi
    /sbin/initctl reload-configuration >/dev/null 2>&1 || true; root_ro
    [ "$SERVICE_WAS_RUNNING" -eq 1 ] && /sbin/initctl start "$JOB" >/dev/null 2>&1 || true
}
fail() { echo "$(date): ERROR: $1"; [ "$ACTIVATED" -eq 1 ] && rollback; root_ro; cleanup_stage; toast "Installation failed: $1"; exit 1; }
trap 'fail "installer interrupted"' INT TERM HUP
trap 'root_ro' EXIT

atomic_file() { src="$1"; dst="$2"; mode="$3"; tmp="${dst}.new.$$"; cp "$src" "$tmp" || return 1; chmod "$mode" "$tmp" || { rm -f "$tmp"; return 1; }; mv "$tmp" "$dst"; }

[ "$(id -u)" -eq 0 ] || fail "not running as root; use ;log runme"
[ -x /sbin/initctl ] || fail "Upstart not found"; [ -f /lib/ld-linux-armhf.so.3 ] || fail "not a kindlehf device"
command -v cmp >/dev/null 2>&1 || fail "cmp unavailable"
for f in native-reading-time-daemon.sh native-reading-time.conf 阅读记录.sh 阅读记录-optimized.sh reading-insights-touch.lua reading-insights-render.lua reading-insights-cache.awk reading-insights-touch-ui.lua reading-insights-titles.lua reading-insights-title-widths.lua NotoSansCJKsc-Regular.otf FONT-LICENSE.txt; do [ -f "$PKG/$f" ] || fail "missing payload: $f"; done
for f in total.png daily.png books.png day-1.png day-31.png; do [ -f "$PKG/ui/$f" ] || fail "missing UI asset: $f"; done
for f in total.png daily.png books.png; do [ -f "$PKG/ui-calendar/$f" ] || fail "missing calendar UI: $f"; done
[ -f "$PKG/render-assets/dynamic-glyphs.pgm" ] && [ -f "$PKG/render-assets/dynamic-glyphs.tsv" ] || fail "missing optimized render assets"
[ -f "$DAEMON" ] || fail "original 9.6.3 daemon not found; optimized package supports in-place upgrade only"
cmp -s "$PKG/native-reading-time-daemon.sh" "$DAEMON" || fail "payload daemon differs from installed 9.6.3"
echo "$(date): payload daemon matches installed 9.6.3 byte-for-byte"

rm -rf "$STAGE"; mkdir -p "$STAGE/release/bin" "$STAGE/release/ui" "$STAGE/release/ui-calendar" "$STAGE/release/render-assets" "$STAGE/rollback" || fail "cannot create staging directory"
cp "$PKG/阅读记录-optimized.sh" "$STAGE/viewer" && cp "$PKG/native-reading-time-daemon.sh" "$STAGE/daemon" && cp "$PKG/native-reading-time.conf" "$STAGE/conf" || fail "cannot stage programs"
cp "$PKG/阅读记录.sh" "$STAGE/release/bin/reading-records-v9.6.3.sh" && cp "$PKG/reading-insights-touch.lua" "$STAGE/release/bin/" && cp "$PKG/reading-insights-render.lua" "$STAGE/release/bin/" && cp "$PKG/reading-insights-cache.awk" "$STAGE/release/bin/" || fail "cannot stage dashboard helpers"
cp "$PKG"/ui-calendar/*.png "$STAGE/release/ui-calendar/" || fail "cannot stage calendar UI"
for f in reading-insights-touch-ui.lua reading-insights-titles.lua reading-insights-title-widths.lua; do cp "$PKG/$f" "$STAGE/release/bin/$f" || fail "cannot stage calendar helper"; done
cp "$PKG"/ui/*.png "$STAGE/release/ui/" && cp "$PKG"/render-assets/* "$STAGE/release/render-assets/" || fail "cannot stage render assets"
cp "$PKG/NotoSansCJKsc-Regular.otf" "$STAGE/font" && cp "$PKG/FONT-LICENSE.txt" "$STAGE/font-license" || fail "cannot stage font"
chmod 755 "$STAGE/viewer" "$STAGE/daemon" "$STAGE/release/bin/reading-records-v9.6.3.sh"; chmod 644 "$STAGE/conf" "$STAGE/release/bin/"*.lua "$STAGE/release/bin/"*.awk "$STAGE/release/ui/"*.png "$STAGE/release/ui-calendar/"*.png "$STAGE/release/render-assets/"* "$STAGE/font" "$STAGE/font-license" || fail "cannot set staged permissions"
cmp -s "$STAGE/daemon" "$PKG/native-reading-time-daemon.sh" || fail "staged daemon differs from validated payload"
echo "$(date): staged daemon matches validated payload byte-for-byte"

/sbin/initctl status "$JOB" 2>/dev/null | grep -q 'start/running' && SERVICE_WAS_RUNNING=1
if [ -f "$DAEMON" ]; then cp "$DAEMON" "$STAGE/rollback/daemon" || fail "cannot back up current daemon"; else : > "$STAGE/rollback/no-daemon"; fi
if [ -f "$VIEWER" ]; then cp "$VIEWER" "$STAGE/rollback/viewer" || fail "cannot back up current dashboard"; else : > "$STAGE/rollback/no-viewer"; fi
if [ -f "$CONF" ]; then cp "$CONF" "$STAGE/rollback/conf" || fail "cannot back up current Upstart job"; else : > "$STAGE/rollback/no-conf"; fi

/sbin/initctl stop "$JOB" >/dev/null 2>&1 || true; ACTIVATED=1
if [ -f "$DATA" ]; then
    if [ ! -e "$DATA.bak" ]; then cp "$DATA" "$DATA.bak.new.$$" || fail "cannot create reading history backup"; mv "$DATA.bak.new.$$" "$DATA.bak" || fail "cannot publish reading history backup"; echo "$(date): created reading-time.tsv.bak"
    else echo "$(date): preserved existing reading-time.tsv.bak"; fi
fi
mkdir -p "$BASE/bin" "$BASE/ui" "$BASE/fonts" "$RELEASE/bin" "$RELEASE/ui" "$RELEASE/ui-calendar" "$RELEASE/render-assets" || fail "cannot create installation directories"
for f in "$STAGE/release/ui-calendar/"*.png; do atomic_file "$f" "$RELEASE/ui-calendar/${f##*/}" 644 || fail "cannot install calendar UI"; done
for f in reading-insights-touch-ui.lua reading-insights-titles.lua reading-insights-title-widths.lua; do atomic_file "$STAGE/release/bin/$f" "$RELEASE/bin/$f" 644 || fail "cannot install calendar helper"; done
for f in "$STAGE/release/ui/"*.png; do atomic_file "$f" "$RELEASE/ui/${f##*/}" 644 || fail "cannot install optimized UI"; done
for f in "$STAGE/release/render-assets/"*; do atomic_file "$f" "$RELEASE/render-assets/${f##*/}" 644 || fail "cannot install render assets"; done
atomic_file "$STAGE/release/bin/reading-records-v9.6.3.sh" "$RELEASE/bin/reading-records-v9.6.3.sh" 755 || fail "cannot install legacy fallback"
atomic_file "$STAGE/release/bin/reading-insights-touch.lua" "$RELEASE/bin/reading-insights-touch.lua" 644 || fail "cannot install touch reader"
atomic_file "$STAGE/release/bin/reading-insights-render.lua" "$RELEASE/bin/reading-insights-render.lua" 644 || fail "cannot install renderer"
atomic_file "$STAGE/release/bin/reading-insights-cache.awk" "$RELEASE/bin/reading-insights-cache.awk" 644 || fail "cannot install cache builder"
for f in "$STAGE/release/ui/"*.png; do atomic_file "$f" "$BASE/ui/${f##*/}" 644 || fail "cannot install legacy UI assets"; done
atomic_file "$STAGE/release/bin/reading-insights-touch.lua" "$BASE/bin/reading-insights-touch.lua" 644 || fail "cannot install legacy touch reader"
atomic_file "$STAGE/font" "$BASE/fonts/NotoSansCJKsc-Regular.otf" 644 || fail "cannot install CJK font"
atomic_file "$STAGE/font-license" "$BASE/fonts/FONT-LICENSE.txt" 644 || fail "cannot install font license"
atomic_file "$STAGE/daemon" "$DAEMON" 755 || fail "cannot install tracker daemon"

root_rw || fail "cannot remount rootfs"
atomic_file "$STAGE/conf" "$CONF" 644 || fail "cannot install Upstart job"
/sbin/initctl reload-configuration >/dev/null 2>&1 || true; root_ro
atomic_file "$STAGE/viewer" "$VIEWER" 755 || fail "cannot activate optimized dashboard"
lipc-set-prop com.lab126.scanner doFullScan 1 >/dev/null 2>&1 || lipc-set-prop com.lab126.scanner triggerUpdate 1 >/dev/null 2>&1 || true
/sbin/initctl start "$JOB" >/dev/null 2>&1 || true; sleep 2
/sbin/initctl status "$JOB" 2>/dev/null | grep -q 'start/running' || fail "tracker service did not start"
cmp -s "$DAEMON" "$PKG/native-reading-time-daemon.sh" || fail "installed daemon differs from validated payload"
printf '9.6.8-summary-sync-fix\n' > "$STAGE/VERSION"; atomic_file "$STAGE/VERSION" "$BASE/VERSION" 644 || fail "cannot write version marker"

ACTIVATED=0; cleanup_stage; trap - INT TERM HUP; root_ro; sync
echo "$(date): 9.6.8-summary-sync-fix installed and running, daemon_cmp=identical"
toast "Reading records 9.6.8-summary-sync-fix installed"; exit 0
