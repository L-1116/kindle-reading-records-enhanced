#!/bin/sh
# Name: 安装阅读记录
# Author: Kindle Reading Records Enhanced
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)" || exit 1
PAYLOAD="$HERE/阅读记录安装数据.tar"
TMP="/tmp/reading-records-9.7.6-installer.$$"
LOG="/mnt/us/reading-time/install-last.log"
INSTALL_PID=
EXPECTED_CKSUM=@PAYLOAD_CKSUM@
EXPECTED_SIZE=@PAYLOAD_SIZE@
mkdir -p /mnt/us/reading-time || exit 1
: > "$LOG" || exit 1
log() { printf '%s
' "$1" >> "$LOG"; }
fail() { log "ERROR: $1"; lipc-set-prop com.lab126.system toasterMessage "$1" >/dev/null 2>&1 || true; exit 1; }
cleanup_tmp() {
    trap '' INT TERM HUP
    if [ -n "$INSTALL_PID" ]; then kill -TERM "$INSTALL_PID" 2>/dev/null || true; wait "$INSTALL_PID" 2>/dev/null || true; fi
    rm -f "$LOG.tar-list.$$"
    case "$TMP" in /tmp/reading-records-9.7.6-installer.[0-9]*) rm -rf "$TMP";; esac; }
trap cleanup_tmp EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
[ -f "$PAYLOAD" ] || fail "缺少阅读记录安装数据，请把两个文件一起复制到 Kindle。"
command -v cksum >/dev/null 2>&1 || fail "无法校验安装数据"
checksum="$(cksum < "$PAYLOAD")" || fail "无法校验安装数据"
set -- $checksum
[ "$1" = "$EXPECTED_CKSUM" ] && [ "$2" = "$EXPECTED_SIZE" ] || fail "阅读记录安装数据损坏，请重新复制两个文件。"
tar_run() {
    if command -v tar >/dev/null 2>&1; then tar "$@" && return 0; fi
    if command -v busybox >/dev/null 2>&1; then busybox tar "$@"; else return 1; fi
}
tar_run -tf "$PAYLOAD" > "$LOG.tar-list.$$" || fail "无法读取安装数据"
# The builder emits only regular files below one package directory.
while IFS= read -r member; do
    case "$member" in native-reading-time-package/*) :;; *) rm -f "$LOG.tar-list.$$"; fail "安装数据目录不正确";; esac
    case "/$member/" in *'/../'*|*'/./'*|*'//'*) rm -f "$LOG.tar-list.$$"; fail "安装数据路径不正确";; esac
done < "$LOG.tar-list.$$"
rm -f "$LOG.tar-list.$$"
umask 077
mkdir "$TMP" || fail "无法创建临时安装目录"
tar_run -xf "$PAYLOAD" -C "$TMP" || fail "安装数据解包失败"
INSTALLER="$TMP/native-reading-time-package/install.sh"
[ -f "$INSTALLER" ] || fail "安装数据缺少正式安装器"
/bin/sh "$INSTALLER" >> "$LOG" 2>&1 &
INSTALL_PID=$!
wait "$INSTALL_PID"; result=$?; INSTALL_PID=
[ "$result" -eq 0 ] || fail "阅读记录安装失败，原安装文件已保留。"
log 'SUCCESS: verified activation completed'
exit 0
