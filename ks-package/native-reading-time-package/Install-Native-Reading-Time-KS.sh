#!/bin/sh

PKG="${READING_PACKAGE_DIR:-/mnt/us/native-reading-time-package}"
BASE="${READING_BASE:-/mnt/us/reading-time}"
DOCS="${READING_DOCUMENTS:-/mnt/us/documents}"
MNT_US="${READING_MNT_US:-/mnt/us}"
KUAL_DIR="$MNT_US/extensions/reading-records-installer"
RELEASE="$BASE/releases/9.7.5-ks-test1"
STAGE="$BASE/.install-9.7.5-ks-test1.$$"
LOG="$BASE/install.log"
VIEWER="$DOCS/阅读记录.sh"
FORCE_ENTRY="$DOCS/reading-records-ks-force-exit.sh"
LAUNCHER="$BASE/bin/launch-ks.sh"
FORCE_EXIT="$BASE/bin/force-exit-ks.sh"
DIAGNOSTICS="$BASE/bin/diagnostics-ks.sh"
DETECTOR="$BASE/compat/detect_env.sh"
ROLLBACK_DONE=0

mkdir -p "$BASE" "$DOCS" 2>/dev/null || exit 1
exec >> "$LOG" 2>&1
echo "$(date): KS installer entered uid=$(id -u) pid=$$"
toast() { lipc-set-prop com.lab126.system toasterMessage "$1" >/dev/null 2>&1 || true; }
atomic_file() { src="$1"; dst="$2"; mode="$3"; tmp="${dst}.new.$$"; cp "$src" "$tmp" && chmod "$mode" "$tmp" && mv "$tmp" "$dst"; }
backup_file() { src="$1"; name="$2"; if [ -f "$src" ]; then cp "$src" "$STAGE/rollback/$name" || return 1; else : > "$STAGE/rollback/no-$name"; fi; }
restore_file() { name="$1"; dst="$2"; mode="$3"; if [ -f "$STAGE/rollback/$name" ]; then atomic_file "$STAGE/rollback/$name" "$dst" "$mode" || true; elif [ -f "$STAGE/rollback/no-$name" ]; then rm -f "$dst"; fi; }
cleanup_stage() { case "$STAGE" in "$BASE"/.install-9.7.5-ks-test1.[0-9]*) rm -rf "$STAGE";; esac; }
rollback() {
    [ "$ROLLBACK_DONE" -eq 0 ] || return; ROLLBACK_DONE=1
    echo "$(date): rolling back KS activation"
    restore_file launcher "$LAUNCHER" 755
    restore_file viewer "$VIEWER" 755
    restore_file force-exit "$FORCE_EXIT" 755
    restore_file force-entry "$FORCE_ENTRY" 755
    restore_file diagnostics "$DIAGNOSTICS" 755
    restore_file detector "$DETECTOR" 644
    restore_file version "$BASE/VERSION" 644
    if [ -d "$STAGE/rollback/release" ]; then rm -rf "$RELEASE"; mv "$STAGE/rollback/release" "$RELEASE" || true
    elif [ -f "$STAGE/rollback/no-release" ]; then rm -rf "$RELEASE"; fi
}
fail() { echo "$(date): ERROR KS install: $*"; rollback; cleanup_stage; toast "KS 安装失败，请查看 install.log"; exit 1; }
trap 'fail "interrupted"' INT TERM HUP

[ "$(id -u)" -eq 0 ] || [ "${READING_ALLOW_NONROOT_TEST:-0}" = 1 ] || fail "installer must run as root"
[ -x "$BASE/bin/native-reading-time-daemon.sh" ] || fail "base tracker is missing"
[ -r "$BASE/reading-time.tsv" ] || fail "reading history is missing"
for cmd in sh awk sed grep cp mv mkdir chmod cmp lua; do command -v "$cmd" >/dev/null 2>&1 || fail "missing command: $cmd"; done
for file in 阅读记录-ks.sh 阅读记录-KS-entry.sh 阅读记录-KS-force-exit-entry.sh launch-ks.sh reading-insights-touch-ks.lua force-exit-ks.sh diagnostics-ks.sh compat/detect_env.sh reading-insights-render.lua reading-insights-cache.awk reading-insights-cover.lua reading-insights-titles.lua reading-insights-title-widths.lua NotoSansCJKsc-Regular.otf FONT-LICENSE.txt launcher-icon.png; do
    [ -f "$PKG/$file" ] || fail "missing payload: $file"
done
for image in total.png daily.png books.png day_detail.png month_detail.png week_trend.png book_detail.png; do [ -f "$PKG/ui-scribe/$image" ] || fail "missing KS UI: $image"; done
[ -r "$PKG/render-assets/dynamic-glyphs.pgm" ] && [ -r "$PKG/render-assets/dynamic-glyphs.tsv" ] || fail "missing render assets"
[ -r "$PKG/resources/kual/reading-records-installer/menu.json" ] && [ -r "$PKG/resources/kual/reading-records-installer/bin/action.sh" ] || fail "missing KUAL resources"

rm -rf "$STAGE"; mkdir -p "$STAGE/release/bin" "$STAGE/release/ui-scribe" "$STAGE/release/render-assets" "$STAGE/release/assets" "$STAGE/rollback" || fail "cannot create stage"
cp "$PKG/阅读记录-ks.sh" "$STAGE/release/bin/reading-records-ks.sh" || fail "cannot stage KS UI"
for file in reading-insights-touch-ks.lua reading-insights-render.lua reading-insights-cache.awk reading-insights-cover.lua reading-insights-titles.lua reading-insights-title-widths.lua; do cp "$PKG/$file" "$STAGE/release/bin/$file" || fail "cannot stage helper $file"; done
cp "$PKG"/ui-scribe/*.png "$STAGE/release/ui-scribe/" || fail "cannot stage UI assets"
cp "$PKG"/render-assets/* "$STAGE/release/render-assets/" || fail "cannot stage render assets"
cp "$PKG/launcher-icon.png" "$STAGE/release/assets/launcher-icon.png" || fail "cannot stage icon"
chmod 755 "$STAGE/release/bin/reading-records-ks.sh" || fail "cannot chmod KS UI"
chmod 644 "$STAGE/release/bin/"*.lua "$STAGE/release/bin/"*.awk "$STAGE/release/ui-scribe/"*.png "$STAGE/release/render-assets/"* "$STAGE/release/assets/launcher-icon.png" || fail "cannot chmod release"

backup_file "$LAUNCHER" launcher || fail "cannot back up launcher"
backup_file "$VIEWER" viewer || fail "cannot back up viewer"
backup_file "$FORCE_EXIT" force-exit || fail "cannot back up force exit"
backup_file "$FORCE_ENTRY" force-entry || fail "cannot back up force entry"
backup_file "$DIAGNOSTICS" diagnostics || fail "cannot back up diagnostics"
backup_file "$DETECTOR" detector || fail "cannot back up environment detector"
backup_file "$BASE/VERSION" version || fail "cannot back up version"
if [ -d "$RELEASE" ]; then mv "$RELEASE" "$STAGE/rollback/release" || fail "cannot back up KS release"; else : > "$STAGE/rollback/no-release"; fi

mkdir -p "$BASE/bin" "$BASE/compat" "$BASE/releases" "$BASE/fonts" "$BASE/assets" "$KUAL_DIR/bin" || fail "cannot create install directories"
mv "$STAGE/release" "$RELEASE" || fail "cannot activate KS release"
atomic_file "$PKG/launch-ks.sh" "$LAUNCHER" 755 || fail "cannot install KS launcher"
atomic_file "$PKG/阅读记录-KS-entry.sh" "$VIEWER" 755 || fail "cannot install KS entry"
atomic_file "$PKG/force-exit-ks.sh" "$FORCE_EXIT" 755 || fail "cannot install force exit"
atomic_file "$PKG/diagnostics-ks.sh" "$DIAGNOSTICS" 755 || fail "cannot install diagnostics"
atomic_file "$PKG/compat/detect_env.sh" "$DETECTOR" 644 || fail "cannot install environment detector"
atomic_file "$PKG/阅读记录-KS-force-exit-entry.sh" "$FORCE_ENTRY" 755 || fail "cannot install force-exit entry"
atomic_file "$PKG/NotoSansCJKsc-Regular.otf" "$BASE/fonts/NotoSansCJKsc-Regular.otf" 644 || fail "cannot install font"
atomic_file "$PKG/FONT-LICENSE.txt" "$BASE/fonts/FONT-LICENSE.txt" 644 || fail "cannot install font license"
atomic_file "$PKG/launcher-icon.png" "$BASE/assets/launcher-icon.png" 644 || fail "cannot install icon"
atomic_file "$PKG/resources/kual/reading-records-installer/bin/action.sh" "$KUAL_DIR/bin/action.sh" 755 || fail "cannot install KUAL action"
atomic_file "$PKG/resources/kual/reading-records-installer/menu.json" "$KUAL_DIR/menu.json" 644 || fail "cannot install KUAL menu"
atomic_file "$PKG/resources/kual/reading-records-installer/config.xml" "$KUAL_DIR/config.xml" 644 || fail "cannot install KUAL config"
printf '9.7.5-ks-test1\n' > "$STAGE/VERSION" || fail "cannot stage version"
atomic_file "$STAGE/VERSION" "$BASE/VERSION" 644 || fail "cannot install version"

[ -x "$LAUNCHER" ] && [ -x "$RELEASE/bin/reading-records-ks.sh" ] && [ -x "$FORCE_EXIT" ] || fail "installed executable validation failed"
[ -r "$BASE/reading-time.tsv" ] || fail "reading history changed during install"
grep -Fq 'LAYOUT_PROFILE=scribe' "$RELEASE/bin/reading-records-ks.sh" || fail "KS layout marker missing"
lipc-set-prop com.lab126.scanner doFullScan 1 >/dev/null 2>&1 || lipc-set-prop com.lab126.scanner triggerUpdate 1 >/dev/null 2>&1 || true
cleanup_stage; trap - INT TERM HUP; sync
echo "$(date): KS test1 installed; reading history preserved"
toast "阅读统计 KS 测试版安装完成"
exit 0
