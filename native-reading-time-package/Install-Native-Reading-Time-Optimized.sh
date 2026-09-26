#!/bin/sh

PKG="/mnt/us/native-reading-time-package"
BASE="/mnt/us/reading-time"
DATA="$BASE/reading-time.tsv"
LOG="$BASE/install.log"
JOB="native-reading-time"
CONF="/etc/upstart/${JOB}.conf"
DAEMON="$BASE/bin/native-reading-time-daemon.sh"
DOCS="/mnt/us/documents"
VIEWER="$DOCS/阅读记录.sh"
UNINSTALL_ENTRY="$DOCS/reading-records-uninstall.sh"
KUAL_DIR="/mnt/us/extensions/reading-records-installer"
KUAL_ACTION="$KUAL_DIR/bin/action.sh"
KUAL_CONFIG="$KUAL_DIR/config.xml"
KUAL_MENU="$KUAL_DIR/menu.json"
LAUNCHER="$BASE/bin/launch.sh"
DIAGNOSTICS="$BASE/bin/diagnostics.sh"
UNINSTALLER="$BASE/bin/uninstall.sh"
MANIFEST="$BASE/install-manifest.txt"
DETECTOR="$BASE/compat/detect_env.sh"
ASSET_DIR="$BASE/assets"
LAUNCHER_ICON="$ASSET_DIR/launcher-icon.png"
RELEASE="$BASE/releases/9.7.5-test"
RELEASE_ICON="$RELEASE/assets/launcher-icon.png"
RELEASE_APP="$RELEASE/bin/reading-records.sh"
COVER_CACHE_DIR="$BASE/book-covers"
STAGE="$BASE/.install-9.7.5-test.$$"
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
cleanup_stage() { case "$STAGE" in /mnt/us/reading-time/.install-9.7.5-test.[0-9]*) rm -rf "$STAGE";; esac; rm -f "$DATA.bak.new.$$"; }

backup_file() { backup_src="$1"; backup_key="$2"; if [ -f "$backup_src" ]; then cp "$backup_src" "$STAGE/rollback/$backup_key" || return 1; else : > "$STAGE/rollback/no-$backup_key"; fi; }
restore_file() { restore_key="$1"; restore_dst="$2"; restore_mode="$3"; if [ -f "$STAGE/rollback/$restore_key" ]; then cp "$STAGE/rollback/$restore_key" "$restore_dst.rollback-new" && chmod "$restore_mode" "$restore_dst.rollback-new" && mv "$restore_dst.rollback-new" "$restore_dst"; elif [ -f "$STAGE/rollback/no-$restore_key" ]; then rm -f "$restore_dst"; fi; }

rollback() {
    [ "$ROLLBACK_DONE" -eq 0 ] || return; ROLLBACK_DONE=1
    echo "$(date): rolling back optimized installation"; /sbin/initctl stop "$JOB" >/dev/null 2>&1 || true
    if [ -f "$STAGE/rollback/daemon" ]; then cp "$STAGE/rollback/daemon" "$DAEMON.rollback-new" && chmod 755 "$DAEMON.rollback-new" && mv "$DAEMON.rollback-new" "$DAEMON"; elif [ -f "$STAGE/rollback/no-daemon" ]; then rm -f "$DAEMON"; fi
    if [ -f "$STAGE/rollback/release-launcher-icon.png" ]; then cp "$STAGE/rollback/release-launcher-icon.png" "$RELEASE_ICON.rollback-new" && chmod 644 "$RELEASE_ICON.rollback-new" && mv "$RELEASE_ICON.rollback-new" "$RELEASE_ICON"; elif [ -f "$STAGE/rollback/no-release-launcher-icon" ]; then rm -f "$RELEASE_ICON"; fi
    if [ -f "$STAGE/rollback/launcher-icon.png" ]; then cp "$STAGE/rollback/launcher-icon.png" "$LAUNCHER_ICON.rollback-new" && chmod 644 "$LAUNCHER_ICON.rollback-new" && mv "$LAUNCHER_ICON.rollback-new" "$LAUNCHER_ICON"; elif [ -f "$STAGE/rollback/no-launcher-icon" ]; then rm -f "$LAUNCHER_ICON"; fi
    if [ -f "$STAGE/rollback/viewer" ]; then cp "$STAGE/rollback/viewer" "$VIEWER.rollback-new" && chmod 755 "$VIEWER.rollback-new" && mv "$VIEWER.rollback-new" "$VIEWER"; elif [ -f "$STAGE/rollback/no-viewer" ]; then rm -f "$VIEWER"; fi
    restore_file launch "$LAUNCHER" 755
    restore_file diagnostics "$DIAGNOSTICS" 755
    restore_file uninstaller "$UNINSTALLER" 755
    restore_file manifest "$MANIFEST" 644
    restore_file detector "$DETECTOR" 644
    restore_file release-app "$RELEASE_APP" 755
    restore_file uninstall-entry "$UNINSTALL_ENTRY" 755
    restore_file kual-action "$KUAL_ACTION" 755
    restore_file kual-config "$KUAL_CONFIG" 644
    restore_file kual-menu "$KUAL_MENU" 644
    rmdir "$KUAL_DIR/bin" "$KUAL_DIR" 2>/dev/null || true
    if [ -f "$STAGE/rollback/conf" ]; then
        if root_rw; then cp "$STAGE/rollback/conf" "$CONF.rollback-new" && chmod 644 "$CONF.rollback-new" && mv "$CONF.rollback-new" "$CONF"; else echo "$(date): WARNING: could not remount rootfs during rollback"; fi
    elif [ -f "$STAGE/rollback/no-conf" ]; then
        if root_rw; then rm -f "$CONF"; else echo "$(date): WARNING: could not remount rootfs during rollback"; fi
    fi
    /sbin/initctl reload-configuration >/dev/null 2>&1 || true; root_ro
    lipc-set-prop com.lab126.scanner doFullScan 1 >/dev/null 2>&1 || lipc-set-prop com.lab126.scanner triggerUpdate 1 >/dev/null 2>&1 || true
    [ "$SERVICE_WAS_RUNNING" -eq 1 ] && /sbin/initctl start "$JOB" >/dev/null 2>&1 || true
}
fail() { echo "$(date): ERROR: $1"; [ "$ACTIVATED" -eq 1 ] && rollback; root_ro; cleanup_stage; toast "Installation failed: $1"; exit 1; }
trap 'fail "installer interrupted"' INT TERM HUP
trap 'root_ro' EXIT

atomic_file() { src="$1"; dst="$2"; mode="$3"; tmp="${dst}.new.$$"; cp "$src" "$tmp" || return 1; chmod "$mode" "$tmp" || { rm -f "$tmp"; return 1; }; mv "$tmp" "$dst"; }

[ "$(id -u)" -eq 0 ] || fail "not running as root; use ;log runme"
[ -x /sbin/initctl ] || fail "Upstart not found"; [ -f /lib/ld-linux-armhf.so.3 ] || fail "not a kindlehf device"
command -v cmp >/dev/null 2>&1 || fail "cmp unavailable"
for f in native-reading-time-daemon.sh native-reading-time.conf 阅读记录.sh 阅读记录-entry.sh 阅读记录-optimized.sh launch.sh diagnostics.sh uninstall.sh install-manifest.txt cleanup-manifest.txt compat/detect_env.sh reading-insights-touch.lua reading-insights-render.lua reading-insights-cache.awk reading-insights-cover.lua reading-insights-touch-ui.lua reading-insights-titles.lua reading-insights-title-widths.lua NotoSansCJKsc-Regular.otf FONT-LICENSE.txt launcher-icon.png; do [ -f "$PKG/$f" ] || fail "missing payload: $f"; done
for f in resources/reading-records-uninstall.sh resources/kual/reading-records-installer/bin/action.sh resources/kual/reading-records-installer/config.xml resources/kual/reading-records-installer/menu.json; do [ -f "$PKG/$f" ] || fail "missing lifecycle resource: $f"; done
for f in total.png daily.png books.png day-1.png day-31.png; do [ -f "$PKG/ui/$f" ] || fail "missing UI asset: $f"; done
for f in total.png daily.png books.png day_detail.png month_detail.png week_trend.png book_detail.png; do [ -f "$PKG/ui-calendar/$f" ] || fail "missing calendar UI: $f"; done
[ -f "$PKG/render-assets/dynamic-glyphs.pgm" ] && [ -f "$PKG/render-assets/dynamic-glyphs.tsv" ] || fail "missing optimized render assets"
[ -f "$DAEMON" ] || fail "original 9.6.3 daemon not found; optimized package supports in-place upgrade only"
cmp -s "$PKG/native-reading-time-daemon.sh" "$DAEMON" || fail "payload daemon differs from installed 9.6.3"
echo "$(date): payload daemon matches installed 9.6.3 byte-for-byte"

rm -rf "$STAGE"; mkdir -p "$STAGE/release/bin" "$STAGE/release/ui" "$STAGE/release/ui-calendar" "$STAGE/release/render-assets" "$STAGE/release/assets" "$STAGE/compat" "$STAGE/kual/bin" "$STAGE/rollback" || fail "cannot create staging directory"
cp "$PKG/阅读记录-entry.sh" "$STAGE/viewer" && cp "$PKG/阅读记录-optimized.sh" "$STAGE/release/bin/reading-records.sh" && cp "$PKG/launch.sh" "$STAGE/launch" && cp "$PKG/diagnostics.sh" "$STAGE/diagnostics" && cp "$PKG/uninstall.sh" "$STAGE/uninstaller" && cp "$PKG/install-manifest.txt" "$STAGE/install-manifest.txt" && cp "$PKG/compat/detect_env.sh" "$STAGE/compat/detect_env.sh" && cp "$PKG/native-reading-time-daemon.sh" "$STAGE/daemon" && cp "$PKG/native-reading-time.conf" "$STAGE/conf" || fail "cannot stage programs"
cmp -s "$PKG/阅读记录-optimized.sh" "$STAGE/release/bin/reading-records.sh" || fail "staged resolver differs from payload"
cp "$PKG/resources/reading-records-uninstall.sh" "$STAGE/uninstall-entry" && cp "$PKG/resources/kual/reading-records-installer/bin/action.sh" "$STAGE/kual/bin/action.sh" && cp "$PKG/resources/kual/reading-records-installer/config.xml" "$STAGE/kual/config.xml" && cp "$PKG/resources/kual/reading-records-installer/menu.json" "$STAGE/kual/menu.json" || fail "cannot stage lifecycle entries"
cp "$PKG/阅读记录.sh" "$STAGE/release/bin/reading-records-v9.6.3.sh" && cp "$PKG/reading-insights-touch.lua" "$STAGE/release/bin/" && cp "$PKG/reading-insights-render.lua" "$STAGE/release/bin/" && cp "$PKG/reading-insights-cache.awk" "$STAGE/release/bin/" && cp "$PKG/reading-insights-cover.lua" "$STAGE/release/bin/" || fail "cannot stage dashboard helpers"
cp "$PKG"/ui-calendar/*.png "$STAGE/release/ui-calendar/" || fail "cannot stage calendar UI"
for f in reading-insights-touch-ui.lua reading-insights-titles.lua reading-insights-title-widths.lua; do cp "$PKG/$f" "$STAGE/release/bin/$f" || fail "cannot stage calendar helper"; done
cp "$PKG"/ui/*.png "$STAGE/release/ui/" && cp "$PKG"/render-assets/* "$STAGE/release/render-assets/" || fail "cannot stage render assets"
cp "$PKG/launcher-icon.png" "$STAGE/release/assets/launcher-icon.png" || fail "cannot stage launcher icon"
cp "$PKG/NotoSansCJKsc-Regular.otf" "$STAGE/font" && cp "$PKG/FONT-LICENSE.txt" "$STAGE/font-license" || fail "cannot stage font"
chmod 755 "$STAGE/viewer" "$STAGE/uninstall-entry" "$STAGE/kual/bin/action.sh" "$STAGE/launch" "$STAGE/diagnostics" "$STAGE/uninstaller" "$STAGE/daemon" "$STAGE/release/bin/reading-records.sh" "$STAGE/release/bin/reading-records-v9.6.3.sh"; chmod 644 "$STAGE/kual/config.xml" "$STAGE/kual/menu.json" "$STAGE/install-manifest.txt" "$STAGE/compat/detect_env.sh" "$STAGE/conf" "$STAGE/release/bin/"*.lua "$STAGE/release/bin/"*.awk "$STAGE/release/ui/"*.png "$STAGE/release/ui-calendar/"*.png "$STAGE/release/render-assets/"* "$STAGE/release/assets/launcher-icon.png" "$STAGE/font" "$STAGE/font-license" || fail "cannot set staged permissions"
cmp -s "$STAGE/daemon" "$PKG/native-reading-time-daemon.sh" || fail "staged daemon differs from validated payload"
echo "$(date): staged daemon matches validated payload byte-for-byte"

/sbin/initctl status "$JOB" 2>/dev/null | grep -q 'start/running' && SERVICE_WAS_RUNNING=1
if [ -f "$DAEMON" ]; then cp "$DAEMON" "$STAGE/rollback/daemon" || fail "cannot back up current daemon"; else : > "$STAGE/rollback/no-daemon"; fi
if [ -f "$RELEASE_ICON" ]; then cp "$RELEASE_ICON" "$STAGE/rollback/release-launcher-icon.png" || fail "cannot back up current release launcher icon"; else : > "$STAGE/rollback/no-release-launcher-icon"; fi
if [ -f "$LAUNCHER_ICON" ]; then cp "$LAUNCHER_ICON" "$STAGE/rollback/launcher-icon.png" || fail "cannot back up current launcher icon"; else : > "$STAGE/rollback/no-launcher-icon"; fi
if [ -f "$VIEWER" ]; then cp "$VIEWER" "$STAGE/rollback/viewer" || fail "cannot back up current dashboard"; else : > "$STAGE/rollback/no-viewer"; fi
backup_file "$LAUNCHER" launch || fail "cannot back up core launcher"
backup_file "$DIAGNOSTICS" diagnostics || fail "cannot back up diagnostics"
backup_file "$UNINSTALLER" uninstaller || fail "cannot back up uninstaller"
backup_file "$MANIFEST" manifest || fail "cannot back up install manifest"
backup_file "$DETECTOR" detector || fail "cannot back up environment detector"
backup_file "$RELEASE_APP" release-app || fail "cannot back up UI entry"
backup_file "$UNINSTALL_ENTRY" uninstall-entry || fail "cannot back up uninstall Scriptlet"
backup_file "$KUAL_ACTION" kual-action || fail "cannot back up KUAL action"
backup_file "$KUAL_CONFIG" kual-config || fail "cannot back up KUAL config"
backup_file "$KUAL_MENU" kual-menu || fail "cannot back up KUAL menu"
if [ -f "$CONF" ]; then cp "$CONF" "$STAGE/rollback/conf" || fail "cannot back up current Upstart job"; else : > "$STAGE/rollback/no-conf"; fi

/sbin/initctl stop "$JOB" >/dev/null 2>&1 || true; ACTIVATED=1
if [ -f "$DATA" ]; then
    if [ ! -e "$DATA.bak" ]; then cp "$DATA" "$DATA.bak.new.$$" || fail "cannot create reading history backup"; mv "$DATA.bak.new.$$" "$DATA.bak" || fail "cannot publish reading history backup"; echo "$(date): created reading-time.tsv.bak"
    else echo "$(date): preserved existing reading-time.tsv.bak"; fi
fi
mkdir -p "$BASE/bin" "$BASE/compat" "$BASE/ui" "$BASE/fonts" "$ASSET_DIR" "$COVER_CACHE_DIR" "$RELEASE/bin" "$RELEASE/ui" "$RELEASE/ui-calendar" "$RELEASE/render-assets" "$RELEASE/assets" "$DOCS" "$KUAL_DIR/bin" || fail "cannot create installation directories"
chmod 700 "$COVER_CACHE_DIR" || fail "cannot set cover cache directory permissions"
for f in "$STAGE/release/ui-calendar/"*.png; do atomic_file "$f" "$RELEASE/ui-calendar/${f##*/}" 644 || fail "cannot install calendar UI"; done
for f in reading-insights-touch-ui.lua reading-insights-titles.lua reading-insights-title-widths.lua; do atomic_file "$STAGE/release/bin/$f" "$RELEASE/bin/$f" 644 || fail "cannot install calendar helper"; done
for f in "$STAGE/release/ui/"*.png; do atomic_file "$f" "$RELEASE/ui/${f##*/}" 644 || fail "cannot install optimized UI"; done
for f in "$STAGE/release/render-assets/"*; do atomic_file "$f" "$RELEASE/render-assets/${f##*/}" 644 || fail "cannot install render assets"; done
atomic_file "$STAGE/release/assets/launcher-icon.png" "$RELEASE_ICON" 644 || fail "cannot install release launcher icon"
atomic_file "$STAGE/release/bin/reading-records.sh" "$RELEASE_APP" 755 || fail "cannot install UI entry"
cmp -s "$PKG/阅读记录-optimized.sh" "$RELEASE_APP" || fail "installed resolver differs from payload"
if command -v cksum >/dev/null 2>&1; then
    echo "$(date): source resolver path=$PKG/阅读记录-optimized.sh checksum=$(cksum < "$PKG/阅读记录-optimized.sh")"
    echo "$(date): installed resolver path=$RELEASE_APP checksum=$(cksum < "$RELEASE_APP")"
fi
atomic_file "$STAGE/release/bin/reading-records-v9.6.3.sh" "$RELEASE/bin/reading-records-v9.6.3.sh" 755 || fail "cannot install legacy fallback"
atomic_file "$STAGE/release/bin/reading-insights-touch.lua" "$RELEASE/bin/reading-insights-touch.lua" 644 || fail "cannot install touch reader"
atomic_file "$STAGE/release/bin/reading-insights-render.lua" "$RELEASE/bin/reading-insights-render.lua" 644 || fail "cannot install renderer"
atomic_file "$STAGE/release/bin/reading-insights-cache.awk" "$RELEASE/bin/reading-insights-cache.awk" 644 || fail "cannot install cache builder"
atomic_file "$STAGE/release/bin/reading-insights-cover.lua" "$RELEASE/bin/reading-insights-cover.lua" 644 || fail "cannot install cover helper"
[ -r "$RELEASE/bin/reading-insights-cover.lua" ] || fail "cover helper is not readable after installation"
[ -d "$COVER_CACHE_DIR" ] && [ -w "$COVER_CACHE_DIR" ] || fail "cover cache directory is not writable after installation"
cover_write_probe="$COVER_CACHE_DIR/.install-write-test.$$"
: > "$cover_write_probe" || fail "cover cache write probe failed"
rm -f "$cover_write_probe" || fail "cover cache write probe cleanup failed"
echo "$(date): cover sanity helper=ok cache_dir=ok cache_mode=700"
for f in "$STAGE/release/ui/"*.png; do atomic_file "$f" "$BASE/ui/${f##*/}" 644 || fail "cannot install legacy UI assets"; done
atomic_file "$STAGE/release/bin/reading-insights-touch.lua" "$BASE/bin/reading-insights-touch.lua" 644 || fail "cannot install legacy touch reader"
atomic_file "$STAGE/font" "$BASE/fonts/NotoSansCJKsc-Regular.otf" 644 || fail "cannot install CJK font"
atomic_file "$STAGE/font-license" "$BASE/fonts/FONT-LICENSE.txt" 644 || fail "cannot install font license"
atomic_file "$STAGE/daemon" "$DAEMON" 755 || fail "cannot install tracker daemon"
atomic_file "$STAGE/launch" "$LAUNCHER" 755 || fail "cannot install core launcher"
atomic_file "$STAGE/diagnostics" "$DIAGNOSTICS" 755 || fail "cannot install diagnostics"
atomic_file "$STAGE/uninstaller" "$UNINSTALLER" 755 || fail "cannot install uninstaller"
atomic_file "$STAGE/install-manifest.txt" "$MANIFEST" 644 || fail "cannot install manifest"
atomic_file "$STAGE/compat/detect_env.sh" "$DETECTOR" 644 || fail "cannot install environment detector"

root_rw || fail "cannot remount rootfs"
atomic_file "$STAGE/conf" "$CONF" 644 || fail "cannot install Upstart job"
/sbin/initctl reload-configuration >/dev/null 2>&1 || true; root_ro
atomic_file "$STAGE/release/assets/launcher-icon.png" "$LAUNCHER_ICON" 644 || fail "cannot install launcher icon"
atomic_file "$STAGE/uninstall-entry" "$UNINSTALL_ENTRY" 755 || fail "cannot install uninstall Scriptlet"
atomic_file "$STAGE/kual/bin/action.sh" "$KUAL_ACTION" 755 || fail "cannot install KUAL action"
atomic_file "$STAGE/kual/config.xml" "$KUAL_CONFIG" 644 || fail "cannot install KUAL config"
atomic_file "$STAGE/kual/menu.json" "$KUAL_MENU" 644 || fail "cannot install KUAL menu"
atomic_file "$STAGE/viewer" "$VIEWER" 755 || fail "cannot activate optimized dashboard"
lipc-set-prop com.lab126.scanner doFullScan 1 >/dev/null 2>&1 || lipc-set-prop com.lab126.scanner triggerUpdate 1 >/dev/null 2>&1 || true
/sbin/initctl start "$JOB" >/dev/null 2>&1 || true; sleep 2
/sbin/initctl status "$JOB" 2>/dev/null | grep -q 'start/running' || fail "tracker service did not start"
cmp -s "$DAEMON" "$PKG/native-reading-time-daemon.sh" || fail "installed daemon differs from validated payload"
[ -r "$DATA" ] || fail "reading history is missing or unreadable after service start"
[ -x "$RELEASE_APP" ] && cmp -s "$RELEASE_APP" "$PKG/阅读记录-optimized.sh" || fail "active resolver is missing, non-executable, or differs from payload"
[ -x "$LAUNCHER" ] && cmp -s "$LAUNCHER" "$PKG/launch.sh" || fail "active launcher is missing, non-executable, or differs from payload"
[ -x "$VIEWER" ] && cmp -s "$VIEWER" "$PKG/阅读记录-entry.sh" || fail "library entry is missing, non-executable, or differs from payload"
grep -Fqx 'RELEASE="$BASE/releases/9.7.5-test"' "$LAUNCHER" && grep -Fqx 'MAIN="$RELEASE/bin/reading-records.sh"' "$LAUNCHER" || fail "launcher does not target the active release resolver"
for required_helper in reading-insights-cover.lua reading-insights-cache.awk reading-insights-render.lua reading-insights-touch-ui.lua; do
    [ -r "$RELEASE/bin/$required_helper" ] || fail "installed helper is missing or unreadable: $required_helper"
done
[ -d "$COVER_CACHE_DIR" ] && [ -w "$COVER_CACHE_DIR" ] || fail "cover cache is not writable after service start"
echo "$(date): final sanity resolver=ok launcher=ok entry=ok helpers=ok history=ok cover_cache=ok"
printf '9.7.5-test\n' > "$STAGE/VERSION"; atomic_file "$STAGE/VERSION" "$BASE/VERSION" 644 || fail "cannot write version marker"

ACTIVATED=0; cleanup_stage; trap - INT TERM HUP; root_ro; sync
echo "$(date): 9.7.5 test installed and running, daemon_cmp=identical"
toast "Reading records 9.7.5 test installed"; exit 0
