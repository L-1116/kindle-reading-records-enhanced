#!/bin/sh
# Name: 安装阅读记录
# Author: Kindle Reading Records Enhanced
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)" || exit 1
PAYLOAD="$HERE/reading-records-9.7.6-data.tar"
TMP="/tmp/reading-records-9.7.6-installer.$$"
LOG="/mnt/us/reading-time/install-last.log"
INSTALL_PID=; SPAWNING=0; SIGNAL_STATUS=0; CLEANING=0
INSTALL_LOCK="/tmp/reading-records-9.7.6-install.lock"
INSTALL_OWNER="$INSTALL_LOCK/owner.$$"
LOG_READY=0
EXPECTED_CKSUM=@PAYLOAD_CKSUM@
EXPECTED_SIZE=@PAYLOAD_SIZE@
log() { [ "$LOG_READY" -eq 1 ] || return 0; printf '%s\n' "$1" >> "$LOG"; }
fail() { log "ERROR: $1"; lipc-set-prop com.lab126.system toasterMessage "$1" >/dev/null 2>&1 || true; exit 1; }
cleanup_tmp() {
    CLEANING=1
    if [ -n "$INSTALL_PID" ]; then : > "$TMP/installer-cancel"; : > "$TMP/installer-start"; fi
    if [ -n "$INSTALL_PID" ]; then kill -TERM "$INSTALL_PID" 2>/dev/null || true; wait "$INSTALL_PID" 2>/dev/null || true; fi
    rm -f "$LOG.tar-list.$$"
    case "$TMP" in /tmp/reading-records-9.7.6-installer.[0-9]*) rm -rf "$TMP";; esac
    # Only our PID-specific empty directory can be released. rmdir never
    # removes another owner, including across stale-lock acquisition races.
    rmdir "$INSTALL_OWNER" 2>/dev/null || true
    rmdir "$INSTALL_LOCK" 2>/dev/null || true
}
on_signal() { [ "$CLEANING" -eq 0 ] || return 0; SIGNAL_STATUS=$1; [ "$SPAWNING" -eq 1 ] || exit "$1"; }
trap cleanup_tmp EXIT
trap 'on_signal 130' INT
trap 'on_signal 143' TERM
trap 'on_signal 129' HUP
umask 077
# Cover the entire public install, before touching the shared log or unpacking.
# PID encoded in an atomic directory avoids a mkdir -> PID-file write gap.
if ! mkdir "$INSTALL_LOCK" 2>/dev/null; then
    for owner in "$INSTALL_LOCK"/owner.*; do
        [ -d "$owner" ] || continue
        owner_pid="${owner##*.}"
        case "$owner_pid" in ''|0|*[!0-9]*) fail '安装正在进行，请稍后重试';; esac
        kill -0 "$owner_pid" 2>/dev/null && fail '安装正在进行，请稍后重试'
        rmdir "$owner" 2>/dev/null || fail '安装正在进行，请稍后重试'
    done
    rmdir "$INSTALL_LOCK" 2>/dev/null || fail '安装正在进行，请稍后重试'
    mkdir "$INSTALL_LOCK" 2>/dev/null || fail '安装正在进行，请稍后重试'
fi
mkdir "$INSTALL_OWNER" 2>/dev/null || fail '安装正在进行，请稍后重试'
# A contender recovering an empty lock may race its initial creator. At most
# one may proceed: every later claimant observes the existing owner and exits.
set -- "$INSTALL_LOCK"/owner.*
[ "$#" -eq 1 ] && [ "$1" = "$INSTALL_OWNER" ] || fail '安装正在进行，请稍后重试'
mkdir -p /mnt/us/reading-time || fail '存储空间不足或无法创建安装日志目录，安装已停止。'
printf '' > "$LOG" || fail '存储空间不足或无法写入安装日志，安装已停止。'
LOG_READY=1
[ -f "$PAYLOAD" ] || fail "缺少阅读记录安装数据，请把两个文件一起复制到 Kindle。"
command -v cksum >/dev/null 2>&1 || fail "无法校验安装数据"
checksum="$(cksum < "$PAYLOAD")" || fail "无法校验安装数据"
set -- $checksum
[ "$1" = "$EXPECTED_CKSUM" ] && [ "$2" = "$EXPECTED_SIZE" ] || fail "阅读记录安装数据损坏，请重新复制两个文件。"
# Uncompressed tar bytes plus 4 MiB for filesystem rounding/metadata. df -P -k
# fixes the row layout and units; unknown capacity is a failure, not permission.
space="$(LC_ALL=C df -Pk /tmp 2>/dev/null)" || fail '存储空间不足或无法确认临时空间，安装已停止。'
printf '%s\n' "$space" | awk -v need="$(( (EXPECTED_SIZE+1023)/1024+4096 ))" '
    NR==1 {if($0 !~ /(1024-blocks|1K-blocks)/)bad=1;next}
    NR==2 {if(NF!=6 || $2!~/^[0-9]+$/ || $3!~/^[0-9]+$/ || $4!~/^[0-9]+$/ || $5!~/^[0-9]+%$/)bad=1;
           if($2<=0 || $3>$2 || $4>$2 || $4<need || $5+0>100)bad=1;next}
    {bad=1} END {exit (bad || NR!=2)}' || fail '存储空间不足或无法确认临时空间，安装已停止。'
log "preflight tmp required_kib=$(( (EXPECTED_SIZE+1023)/1024+4096 ))"
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
SPAWNING=1
/bin/sh "$INSTALLER" "$TMP/installer-start" >> "$LOG" 2>&1 &
INSTALL_PID=$!
SPAWNING=0
[ "$SIGNAL_STATUS" -eq 0 ] || exit "$SIGNAL_STATUS"
: > "$TMP/installer-start" || fail "无法开始安装事务"
wait "$INSTALL_PID"; result=$?; INSTALL_PID=
if [ "$result" -ne 0 ]; then
    # Keep the internal installer's specific low-space/recovery toaster.
    log 'ERROR: 阅读记录安装失败，原安装文件已保留。'
    exit "$result"
fi
log 'SUCCESS: verified activation completed'
exit 0
