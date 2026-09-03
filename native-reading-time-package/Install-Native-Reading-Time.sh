#!/bin/sh

PKG="/mnt/us/native-reading-time-package"
BASE="/mnt/us/reading-time"
INSTALL_LOG="$BASE/install.log"
JOB="native-reading-time"
CONF="/etc/upstart/${JOB}.conf"
DAEMON="$BASE/bin/native-reading-time-daemon.sh"
VIEWER="/mnt/us/documents/阅读记录.sh"
TOUCH_READER="$BASE/bin/reading-insights-touch.lua"
UI_DIR="$BASE/ui"
FONT_DIR="$BASE/fonts"

toast() { lipc-set-prop com.lab126.system toasterMessage "$1" >/dev/null 2>&1 || true; }
fail() { echo "$(date): ERROR: $1" | tee -a "$INSTALL_LOG"; toast "Installation failed: $1"; exit 1; }

mkdir -p "$BASE"
echo "$(date): installer entered, uid=$(id -u), args=$*" >> "$INSTALL_LOG"

# ;log runme must invoke this as root. Do not try a second su invocation here.
[ "$(id -u)" -eq 0 ] || fail "not running as root; use ;log runme"
echo "$(date): root invocation confirmed" >> "$INSTALL_LOG"

# Repair input state left behind by any older dashboard version.
lipc-set-prop com.lab126.winmgr eatTapMode 0 >/dev/null 2>&1 || true
lipc-set-prop com.lab126.powerd preventScreenSaver 0 >/dev/null 2>&1 || true

[ -x /sbin/initctl ] || fail "Upstart not found"
[ -f /lib/ld-linux-armhf.so.3 ] || fail "not a kindlehf device"
[ -f "$PKG/native-reading-time-daemon.sh" ] || fail "missing daemon payload"
[ -f "$PKG/native-reading-time.conf" ] || fail "missing Upstart payload"
[ -f "$PKG/阅读记录.sh" ] || fail "missing dashboard launcher"
[ -f "$PKG/reading-insights-touch.lua" ] || fail "missing dashboard touch reader"
[ -f "$PKG/ui/total.png" ] || fail "missing total UI background"
[ -f "$PKG/ui/daily.png" ] || fail "missing daily UI background"
[ -f "$PKG/ui/books.png" ] || fail "missing books UI background"
[ -f "$PKG/NotoSansCJKsc-Regular.otf" ] || fail "missing bundled CJK font"
[ -f "$PKG/FONT-LICENSE.txt" ] || fail "missing bundled font license"

mkdir -p "$BASE/bin" || fail "cannot create data directory"
cp "$PKG/native-reading-time-daemon.sh" "$DAEMON.new" || fail "cannot stage daemon"
chmod 755 "$DAEMON.new" || fail "cannot chmod daemon"
mv "$DAEMON.new" "$DAEMON" || fail "cannot install daemon"
rm -f "$BASE/bin/reading-insights-server.sh"
killall reading-insights-server.sh >/dev/null 2>&1 || true
cp "$PKG/阅读记录.sh" "$VIEWER" || fail "cannot install dashboard launcher"
chmod 755 "$VIEWER" || fail "cannot chmod dashboard launcher"
rm -f "/mnt/us/documents/书籍进度探测.sh"
rm -f "/mnt/us/documents/阅读页数探测.sh"
rm -f "$BASE/bin/page-turn-probe-worker.sh" "$BASE/bin/page-turn-probe.lua" "$BASE/page-turn-probe.pid"
rm -f "/mnt/us/documents/阅读洞察.sh"
cp "$PKG/reading-insights-touch.lua" "$TOUCH_READER" || fail "cannot install dashboard touch reader"
chmod 644 "$TOUCH_READER" || fail "cannot chmod dashboard touch reader"
mkdir -p "$UI_DIR" || fail "cannot create UI directory"
cp "$PKG"/ui/*.png "$UI_DIR/" || fail "cannot install UI assets"
chmod 644 "$UI_DIR"/*.png || fail "cannot chmod UI assets"
mkdir -p "$FONT_DIR" || fail "cannot create font directory"
cp "$PKG/NotoSansCJKsc-Regular.otf" "$FONT_DIR/NotoSansCJKsc-Regular.otf" || fail "cannot install CJK font"
rm -f "$FONT_DIR/DroidSansFallback.ttf"
cp "$PKG/FONT-LICENSE.txt" "$FONT_DIR/FONT-LICENSE.txt" || fail "cannot install font license"
chmod 644 "$FONT_DIR"/* || fail "cannot chmod font files"
lipc-set-prop com.lab126.scanner doFullScan 1 >/dev/null 2>&1 || lipc-set-prop com.lab126.scanner triggerUpdate 1 >/dev/null 2>&1 || true

/sbin/initctl stop "$JOB" >/dev/null 2>&1 || true

ROOT_RW=0
root_ro() {
    if [ "$ROOT_RW" -eq 1 ]; then
        mntroot ro >/dev/null 2>&1 || /usr/sbin/mntroot ro >/dev/null 2>&1 || /sbin/mntroot ro >/dev/null 2>&1 || true
        ROOT_RW=0
    fi
}
trap root_ro EXIT INT TERM HUP

if mntroot rw >/dev/null 2>&1 || /usr/sbin/mntroot rw >/dev/null 2>&1 || /sbin/mntroot rw >/dev/null 2>&1; then
    ROOT_RW=1
else
    fail "cannot remount rootfs"
fi

cp "$PKG/native-reading-time.conf" "$CONF.new" || fail "cannot stage Upstart job"
chmod 644 "$CONF.new" || fail "cannot chmod Upstart job"
mv "$CONF.new" "$CONF" || fail "cannot install Upstart job"
/sbin/initctl reload-configuration >/dev/null 2>&1 || true
root_ro
trap - EXIT INT TERM HUP

/sbin/initctl start "$JOB" >/dev/null 2>&1 || true
sleep 2
if /sbin/initctl status "$JOB" 2>/dev/null | grep -q 'start/running'; then
    echo "$(date): installed and running" | tee -a "$INSTALL_LOG"
    toast "Native reading time tracker installed"
    sync
    exit 0
fi

echo "$(date): installation completed, but service did not start" | tee -a "$INSTALL_LOG"
echo "See /mnt/us/reading-time/upstart.log" | tee -a "$INSTALL_LOG"
toast "Tracker installed but did not start; check install.log"
sync
exit 1
