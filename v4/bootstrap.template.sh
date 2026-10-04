#!/bin/sh
# Name: 安装阅读记录
# Author: Kindle Reading Records
# READING_RECORDS_V4_BOOTSTRAP

VARIANT='@VARIANT@'
PAYLOAD_SIZE='@SIZE@'
PAYLOAD_CKSUM='@CKSUM@'
MNT_US="${READING_MNT_US:-/mnt/us}"
DOCS="${READING_DOCUMENTS:-$MNT_US/documents}"
BASE="${READING_BASE:-$MNT_US/reading-time}"
TMP_ROOT="${READING_TMPDIR:-/tmp}"
TMP="$TMP_ROOT/reading-records-installer.$$"
SCRIPT_DIR=${0%/*}
[ "$SCRIPT_DIR" = "$0" ] && SCRIPT_DIR=.
PAYLOAD="$SCRIPT_DIR/阅读记录安装数据.tar"
RESULT="$DOCS/reading-records-v4-install-result.txt"
LOG="$DOCS/reading-records-v4-install.log"
CLEANUP="$DOCS/安装好之后，确认无误了再点这个.sh"
CREATED_TMP=0
ROLLBACK_DIR="$BASE/.v4-rollback.$$"
ROLLBACK_READY=0
COMMITTED=0

toast() { command -v lipc-set-prop >/dev/null 2>&1 && lipc-set-prop com.lab126.system toasterMessage "$1" >/dev/null 2>&1 || true; }
note() { printf '%s: %s\n' "$(date)" "$*" >> "$LOG" 2>/dev/null || true; }
result() { printf 'timestamp=%s\nexit_code=%s\nerror=%s\nvariant=%s\n' "$(date)" "$1" "$2" "$VARIANT" > "$RESULT" 2>/dev/null || true; }
fail() { note "ERROR exit_code=$1 error=$2"; result "$1" "$2"; toast "$3"; exit "$1"; }
save_path() { if [ -e "$1" ] || [ -L "$1" ]; then cp -R "$1" "$ROLLBACK_DIR/$2" || return 1; else : > "$ROLLBACK_DIR/no-$2" || return 1; fi; }
restore_path() {
    target="$1"; key="$2"
    if [ -e "$ROLLBACK_DIR/$key" ] || [ -L "$ROLLBACK_DIR/$key" ]; then
        rm -rf "$target" || return 1
        mv "$ROLLBACK_DIR/$key" "$target" || return 1
    elif [ -f "$ROLLBACK_DIR/no-$key" ]; then rm -rf "$target" || return 1; fi
}
rollback_runtime() {
    [ "$ROLLBACK_READY" -eq 1 ] || return 0
    note 'restoring pre-upgrade runtime snapshot'
    for item in bin releases compat ui fonts assets; do restore_path "$BASE/$item" "$item" || note "ROLLBACK ERROR $item"; done
    restore_path "$BASE/VERSION" VERSION || note 'ROLLBACK ERROR VERSION'
    restore_path "$BASE/release-info" release-info || note 'ROLLBACK ERROR release-info'
    restore_path "$BASE/install-manifest.txt" install-manifest || note 'ROLLBACK ERROR install-manifest'
    restore_path "$DOCS/阅读记录.sh" viewer || note 'ROLLBACK ERROR viewer'
    restore_path "$DOCS/reading-records-ks-force-exit.sh" force-entry || note 'ROLLBACK ERROR force-entry'
    restore_path "$DOCS/reading-records-uninstall.sh" uninstall-entry || note 'ROLLBACK ERROR uninstall-entry'
    restore_path "$MNT_US/extensions/reading-records-installer" kual || note 'ROLLBACK ERROR kual'
    if [ -e "$ROLLBACK_DIR/service" ] || [ -f "$ROLLBACK_DIR/no-service" ]; then
        mntroot rw >/dev/null 2>&1 || /usr/sbin/mntroot rw >/dev/null 2>&1 || /sbin/mntroot rw >/dev/null 2>&1 || true
        restore_path "${READING_UPSTART_DIR:-/etc/upstart}/native-reading-time.conf" service || note 'ROLLBACK ERROR service'
        command -v initctl >/dev/null 2>&1 && initctl reload-configuration >/dev/null 2>&1 || true
        mntroot ro >/dev/null 2>&1 || /usr/sbin/mntroot ro >/dev/null 2>&1 || /sbin/mntroot ro >/dev/null 2>&1 || true
    fi
    command -v initctl >/dev/null 2>&1 && initctl start native-reading-time >/dev/null 2>&1 || true
}
clean_temp() {
    [ "$COMMITTED" -eq 1 ] || rollback_runtime
    [ "$CREATED_TMP" -eq 1 ] && case "$TMP" in "$TMP_ROOT"/reading-records-installer.[0-9]*) rm -rf "$TMP";; esac
    case "$ROLLBACK_DIR" in "$BASE"/.v4-rollback.[0-9]*) [ -d "$ROLLBACK_DIR" ] && rm -rf "$ROLLBACK_DIR";; esac
    rm -f "$BASE/release-info.new.$$" "$BASE/VERSION.new.$$" "$CLEANUP.new.$$" 2>/dev/null || true
}
trap clean_temp EXIT
trap 'exit 130' HUP INT TERM
tar_cmd() { if command -v tar >/dev/null 2>&1; then tar "$@"; else busybox tar "$@"; fi; }

mkdir -p "$DOCS" 2>/dev/null || exit 1
note "V4 bootstrap started variant=$VARIANT"
cd "$SCRIPT_DIR" 2>/dev/null || fail 1 'installer directory unavailable' '无法读取安装文件夹'
PAYLOAD='./阅读记录安装数据.tar'
if [ -f "$CLEANUP" ] && grep -Fq '# READING_RECORDS_V4_CLEANUP' "$CLEANUP"; then rm -f "$CLEANUP" || fail 1 'old cleanup entry cannot be removed' '安装失败，请查看安装日志'; fi
[ -f "$PAYLOAD" ] || fail 127 'payload not found' '缺少阅读记录安装数据，请把两个文件一起复制到 Kindle'
if command -v tar >/dev/null 2>&1; then :
elif command -v busybox >/dev/null 2>&1 && busybox tar --help >/dev/null 2>&1; then :
else fail 126 'tar unavailable' '安装失败：设备缺少 tar'; fi

actual_size=$(wc -c < "$PAYLOAD" | tr -d '[:space:]') || fail 1 'cannot read payload size' '安装数据无法读取'
[ "$actual_size" = "$PAYLOAD_SIZE" ] || fail 1 'payload size mismatch' '安装数据损坏，请重新复制'
if command -v cksum >/dev/null 2>&1; then
    actual_cksum=$(cksum < "$PAYLOAD" | awk '{print $1}') || fail 1 'cksum failed' '安装数据校验失败'
    [ "$actual_cksum" = "$PAYLOAD_CKSUM" ] || fail 1 'payload checksum mismatch' '安装数据损坏，请重新复制'
else note 'cksum unavailable; size and archive checks remain active'; fi

device_file="${READING_DEVICETYPE_PATH:-/var/local/deviceType.txt}"
device_type=$(sed -n '1p' "$device_file" 2>/dev/null || true)
case "$device_type" in
    *[Ss]cribe*|*KS*) device_variant=ks;;
    '') fail 1 'device variant unknown' '无法识别设备型号，请使用完整兼容包';;
    *) device_variant=standard;;
esac
[ "$device_variant" = "$VARIANT" ] || fail 1 'device variant mismatch' '安装包与 Kindle 机型不符'

installed_variant=
if [ -f "$BASE/release-info" ]; then
    installed_variant=$(sed -n 's/^variant=//p' "$BASE/release-info" | sed -n '1p')
elif [ -f "$BASE/VERSION" ] && grep -Eiq '(^|[-_])ks([-_]|$)|scribe' "$BASE/VERSION"; then installed_variant=ks
elif [ -e "$BASE/bin/launch-ks.sh" ] || [ -d "$BASE/releases/9.7.5-ks-test1" ]; then installed_variant=ks
elif [ -f "$BASE/VERSION" ] || [ -e "$BASE/bin/launch.sh" ]; then installed_variant=standard
fi
case "$installed_variant" in
    ''|standard|ks) :;;
    *) fail 1 'installed variant invalid' '已有版本标识异常，请查看安装日志';;
esac
[ -z "$installed_variant" ] || [ "$installed_variant" = "$VARIANT" ] || fail 1 'cross-variant upgrade refused' '检测到另一机型版本，已停止安装'

mkdir "$TMP" 2>/dev/null || fail 1 'temporary directory creation failed' '无法创建安装临时目录'
CREATED_TMP=1
tar_cmd -tf "$PAYLOAD" > "$TMP/members" 2>> "$LOG" || fail 1 'tar listing failed' '安装数据无法解包'
awk 'BEGIN { bad=0 } /^\// || /(^|\/)\.\.($|\/)/ || /(^|\/)\.($|\/)/ || /\\/ { bad=1 } END { exit bad }' "$TMP/members" || fail 1 'unsafe tar path' '安装数据路径异常'
tar_cmd -xf "$PAYLOAD" -C "$TMP" >> "$LOG" 2>&1 || fail 1 'tar extraction failed' '安装数据无法解包'
PKG="$TMP/native-reading-time-package"
[ -r "$PKG/install.sh" ] && [ -r "$TMP/V4-PAYLOAD" ] && [ -r "$TMP/v4/cleanup.sh" ] || fail 1 'payload layout invalid' '安装数据不完整'
grep -Fqx 'release_family=V4' "$TMP/V4-PAYLOAD" && grep -Fqx "variant=$VARIANT" "$TMP/V4-PAYLOAD" || fail 1 'payload variant invalid' '安装数据版本不匹配'

if [ -e "$BASE/bin/native-reading-time-daemon.sh" ]; then mode=upgrade; else mode=fresh; fi
note "mode=$mode installed_variant=${installed_variant:-none}"
if [ -d "$BASE" ] && [ -n "$installed_variant" ]; then
    mkdir "$ROLLBACK_DIR" || fail 1 'runtime snapshot creation failed' '无法创建升级回滚区'
    for item in bin releases compat ui fonts assets; do save_path "$BASE/$item" "$item" || fail 1 'runtime snapshot failed' '无法备份现有版本'; done
    save_path "$BASE/VERSION" VERSION && save_path "$BASE/release-info" release-info && save_path "$BASE/install-manifest.txt" install-manifest && save_path "$DOCS/阅读记录.sh" viewer && save_path "$DOCS/reading-records-ks-force-exit.sh" force-entry && save_path "$DOCS/reading-records-uninstall.sh" uninstall-entry && save_path "$MNT_US/extensions/reading-records-installer" kual && save_path "${READING_UPSTART_DIR:-/etc/upstart}/native-reading-time.conf" service || fail 1 'runtime snapshot failed' '无法备份现有版本'
    ROLLBACK_READY=1
fi
READING_PACKAGE_DIR="$PKG" READING_BASE="$BASE" READING_DOCUMENTS="$DOCS" READING_MNT_US="$MNT_US" /bin/sh "$PKG/install.sh" install >> "$LOG" 2>&1
core_code=$?
[ "$core_code" -eq 0 ] || fail "$core_code" 'internal installer failed' '安装失败，请查看安装日志和诊断文件'

if [ "$VARIANT" = ks ]; then
    launcher="$BASE/bin/launch-ks.sh"; resolver="$BASE/releases/9.7.5-ks-test1/bin/reading-records-ks.sh"
    [ -x "$BASE/bin/force-exit-ks.sh" ] || fail 1 'verified activation failed: force exit' '安装验证失败，请查看安装日志'
else
    launcher="$BASE/bin/launch.sh"; resolver="$BASE/releases/9.7.5-test/bin/reading-records.sh"
fi
[ -x "$launcher" ] && [ -x "$resolver" ] && [ -x "$DOCS/阅读记录.sh" ] && [ -x "$BASE/bin/native-reading-time-daemon.sh" ] && [ -r "$BASE/reading-time.tsv" ] && [ -r "${READING_UPSTART_DIR:-/etc/upstart}/native-reading-time.conf" ] || fail 1 'verified activation failed' '安装验证失败，请查看安装日志'
if [ "$VARIANT" = ks ]; then version=V4-KS; else version=V4; fi
printf 'release_family=V4\nvariant=%s\nruntime_release=%s\n' "$VARIANT" "${resolver%/bin/*}" > "$TMP/release-info" || fail 1 'metadata staging failed' '安装版本标识写入失败'
printf '%s\n' "$version" > "$TMP/VERSION" || fail 1 'version staging failed' '安装版本标识写入失败'
cp "$TMP/release-info" "$BASE/release-info.new.$$" && mv "$BASE/release-info.new.$$" "$BASE/release-info" && cp "$TMP/VERSION" "$BASE/VERSION.new.$$" && mv "$BASE/VERSION.new.$$" "$BASE/VERSION" || fail 1 'version activation failed' '安装版本标识写入失败'
cp "$TMP/v4/cleanup.sh" "$CLEANUP.new.$$" && chmod 755 "$CLEANUP.new.$$" && mv "$CLEANUP.new.$$" "$CLEANUP" || fail 1 'cleanup entry creation failed' '安装清理入口创建失败'
COMMITTED=1
result 0 none
note "verified activation complete version=$version"
toast '安装完成，请打开阅读记录，确认正常后可清理安装文件'
exit 0
