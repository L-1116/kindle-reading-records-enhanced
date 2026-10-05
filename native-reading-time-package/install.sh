#!/bin/sh
# Internal transactional installer: the document Scriptlet is only a bootstrap.
# A private bootstrap handoff: do no work until the owner has saved our PID
# and processed any signal received during fork. Direct internal use has no gate.
if [ -n "${1:-}" ]; then
    case "$1" in /tmp/reading-records-9.7.6-installer.[0-9]*/installer-start) :;; *) exit 1;; esac
    while [ ! -f "$1" ]; do sleep 1; done
    [ ! -f "${1%-start}-cancel" ] || exit 143
fi
PKG="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)" || exit 1
BASE="/mnt/us/reading-time"
DOCS="/mnt/us/documents"
RELEASE="$BASE/releases/9.7.6-5.19-normal"
CONF="/etc/upstart/native-reading-time.conf"
STAGE="$BASE/.install-9.7.6-normal.$$"
LOCK="/tmp/reading-records-ui.lock"
ROOT_RW=0; ACTIVATED=0; COMMITTED=0; LOCK_OWNED=0; STAGE_OWNED=0; SERVICE_WAS_RUNNING=0; HAD_RELEASE=0; ROLLBACK_FAILED=0
JOURNAL_CKSUM=; SNAPSHOT_COUNT=0; DAEMON_PID=
log() { echo "$(date): $*"; }
toast() { lipc-set-prop com.lab126.system toasterMessage "$1" >/dev/null 2>&1 || true; }
fail() { log "ERROR: $1"; toast "$1"; exit 1; }
root_rw() { [ "$ROOT_RW" -eq 1 ] && return 0; ROOT_RW=1; mntroot rw >/dev/null 2>&1; }
root_ro() { if [ "$ROOT_RW" -eq 1 ]; then if mntroot ro >/dev/null 2>&1; then ROOT_RW=0; else log 'ERROR: rootfs restore failed'; return 1; fi; fi; }
scan() { lipc-set-prop com.lab126.scanner doFullScan 1 >/dev/null 2>&1 || lipc-set-prop com.lab126.scanner triggerUpdate 1 >/dev/null 2>&1 || true; }
atomic_file() {
    af_src="$1"; af_dst="$2"; af_mode="$3"; af_tmp="$2.new.$$"
    mkdir -p "$(dirname "$af_dst")" || return 1
    cp "$af_src" "$af_tmp" && chmod "$af_mode" "$af_tmp" && mv "$af_tmp" "$af_dst" && return 0
    rm -f "$af_tmp"; return 1
}
remember_daemon_pid() {
    # Only this exact Upstart job may supply a PID. Never search by name or
    # kill an unrelated process; PID reuse conservatively refuses deployment.
    case "$1" in 'native-reading-time start/running, process '*) DAEMON_PID="${1#native-reading-time start/running, process }";; *) return 1;; esac
    case "$DAEMON_PID" in ''|0|*[!0-9]*) return 1;; esac
    [ "$DAEMON_PID" -gt 0 ] 2>/dev/null
}
verify_running_daemon() {
    running_state="$(/sbin/initctl status native-reading-time 2>/dev/null)" || return 1
    remember_daemon_pid "$running_state" || return 1
    kill -0 "$DAEMON_PID" 2>/dev/null
}
stop_daemon() {
    daemon_before_stopped=0
    daemon_before="$(/sbin/initctl status native-reading-time 2>/dev/null)" || daemon_before=
    case "$daemon_before" in
        'native-reading-time start/running, process '*) remember_daemon_pid "$daemon_before" || return 1;;
        'native-reading-time stop/waiting') daemon_before_stopped=1;;
        '') :;;
        *) return 1;;
    esac
    if ! /sbin/initctl stop native-reading-time >/dev/null 2>&1; then
        [ "$daemon_before_stopped" -eq 1 ] || [ "$SERVICE_WAS_RUNNING" -eq 0 ] || return 1
    fi
    stopped_state="$(/sbin/initctl status native-reading-time 2>/dev/null)" || {
        # A fresh install can have no Upstart job yet. An existing job with
        # unknown status must never be assumed stopped.
        [ "$SERVICE_WAS_RUNNING" -eq 0 ] && [ ! -e "$CONF" ] && return 0
        return 1
    }
    case "$stopped_state" in 'native-reading-time stop/waiting') :;; *) return 1;; esac
    # A successful stop and stop/waiting alone cannot prove a previously
    # reported process has exited (including on rollback after activation).
    [ -z "$DAEMON_PID" ] || ! kill -0 "$DAEMON_PID" 2>/dev/null || return 1
    return 0
}
rollback() {
    log 'rolling back runtime transaction'
    if ! stop_daemon; then
        log 'ERROR: daemon stop unverified; refusing runtime rollback'; ROLLBACK_FAILED=1; return 1
    fi
    rollback_cksum="$(cksum < "$STAGE/journal" 2>/dev/null)" || rollback_cksum=
    if [ -z "$JOURNAL_CKSUM" ] || [ "$rollback_cksum" != "$JOURNAL_CKSUM" ]; then
        log 'ERROR: rollback journal missing or changed'; ROLLBACK_FAILED=1; return 1
    fi
    if [ -d "$STAGE/old-release" ]; then
        rm -rf "$RELEASE" && mv "$STAGE/old-release" "$RELEASE" || { log 'ERROR: release rollback failed'; ROLLBACK_FAILED=1; }
    elif [ "$HAD_RELEASE" -eq 0 ]; then
        rm -rf "$RELEASE" || { log 'ERROR: new release removal failed'; ROLLBACK_FAILED=1; }
    fi
    root_rw || { log 'ERROR: rootfs unavailable during rollback'; ROLLBACK_FAILED=1; }
    rollback_records=0
    while IFS="$(printf '\t')" read -r slot dst had_file; do
        rollback_records=$((rollback_records+1))
        rm -f "$dst.new.$$" || ROLLBACK_FAILED=1
        if [ "$had_file" = 1 ]; then
            # A missing/unreadable backup is never interpreted as a new file.
            cp -p "$STAGE/backup/$slot" "$dst.rollback.$$" && cmp -s "$STAGE/backup/$slot" "$dst.rollback.$$" && mv "$dst.rollback.$$" "$dst" || { log "ERROR: rollback failed: $dst"; ROLLBACK_FAILED=1; }
        elif [ "$had_file" = 0 ]; then
            rm -f "$dst" || { log "ERROR: rollback removal failed: $dst"; ROLLBACK_FAILED=1; }
        else log 'ERROR: invalid rollback journal'; ROLLBACK_FAILED=1; fi
    done < "$STAGE/journal"
    rollback_cksum="$(cksum < "$STAGE/journal" 2>/dev/null)" || rollback_cksum=
    if [ "$rollback_records" -ne "$SNAPSHOT_COUNT" ] || [ "$rollback_cksum" != "$JOURNAL_CKSUM" ]; then
        log 'ERROR: incomplete rollback journal read'; ROLLBACK_FAILED=1
    fi
    /sbin/initctl reload-configuration >/dev/null 2>&1 || { log 'ERROR: rollback service reload failed'; ROLLBACK_FAILED=1; }
    root_ro || ROLLBACK_FAILED=1
    if [ "$SERVICE_WAS_RUNNING" -eq 1 ] && [ "$ROLLBACK_FAILED" -eq 0 ]; then
        /sbin/initctl start native-reading-time >/dev/null 2>&1 || ROLLBACK_FAILED=1
        verify_running_daemon || { log 'ERROR: old daemon recovery failed'; ROLLBACK_FAILED=1; }
    fi
    scan
}
finish() {
    finish_status=$?
    trap '' INT TERM HUP
    if [ "$ACTIVATED" -eq 1 ] && [ "$COMMITTED" -eq 0 ]; then rollback; fi
    root_ro || { log "ERROR: manual rootfs recovery required"; ROLLBACK_FAILED=1; }
    if [ "$ROLLBACK_FAILED" -eq 1 ]; then
        log "RECOVERY_REQUIRED snapshot=$STAGE"
        toast '安装恢复失败，已保留恢复快照，请保留安装文件。'
    elif [ "$STAGE_OWNED" -eq 1 ]; then
        case "$STAGE" in /mnt/us/reading-time/.install-9.7.6-normal.[0-9]*) rm -rf "$STAGE";; esac
    fi
    if [ "$LOCK_OWNED" -eq 1 ]; then release_runtime_lock; fi
    [ "$ROLLBACK_FAILED" -eq 0 ] || { [ "$finish_status" -ne 0 ] || exit 1; }
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
[ "$(id -u)" -eq 0 ] || fail '安装需要 Scriptlet 的系统权限'
# Prefer prettyversion; the independent fallback is not a consensus vote.
# A readable source containing conflicting versions must never be bypassed.
read_firmware() {
    firmware_text="$(cat "$1" 2>/dev/null)" || return 1
    printf '%s\n' "$firmware_text" | awk '
        {gsub(/[^[:alnum:].]+/, " ");for(i=1;i<=NF;i++)if($i~/^[0-9]+(\.[0-9]+)+$/ && !seen[$i]++){version=$i;count++}}
        END {if(count>1)exit 2;if(count==1)print version;else exit 1}'
}
firmware="$(read_firmware /etc/prettyversion.txt)"; firmware_status=$?
[ "$firmware_status" -ne 2 ] || fail '系统固件版本信息不明确，安装已停止。'
if [ "$firmware_status" -ne 0 ]; then
    firmware="$(read_firmware /etc/version.txt)" || fail '此安装包仅适用于 Kindle firmware 5.19.x，无法唯一确认系统固件版本，安装已停止。'
fi
case "$firmware" in 5.19.*) :;; *) fail '此安装包仅适用于 Kindle firmware 5.19.x，请使用对应版本安装包。';; esac
# Exclude pen devices by capabilities and display class, without a Standard
# serial/model allowlist. Unknown Standard marketing names are accepted.
device="$(cat /var/local/deviceType.txt /proc/device-tree/model 2>/dev/null | tr '[:upper:]' '[:lower:]')"
case "$device" in *scribe*|ks|*'kindle ks'*) fail '这是普通 Kindle 5.19 安装包，Kindle Scribe 请使用 KS 版本。';; esac
for input in /sys/class/input/event*/device/name; do
    name="$(cat "$input" 2>/dev/null | tr '[:upper:]' '[:lower:]')"
    case "$name" in *wacom*|*stylus*|*digitizer*|*hanvon*) fail '这是普通 Kindle 5.19 安装包，Kindle Scribe 请使用 KS 版本。';; esac
done
geometry="$(fbset 2>/dev/null | awk '/geometry/{print $2 " " $3;exit}')"
set -- $geometry; width="${1:-0}"; height="${2:-0}"
case "$width:$height" in *[!0-9:]*|0:*|*:0)
    virtual="$(cat /sys/class/graphics/fb0/virtual_size 2>/dev/null)"
    width="${virtual%%,*}"; height="${virtual#*,}"
    case "$width:$height" in *[!0-9:]*|0:*|*:0) fail '无法确认设备屏幕，请稍后重试安装';; esac
    [ "$height" -lt $((width*2)) ] || height=$((height/2));;
esac
[ "$width" -lt "$height" ] && short="$width" || short="$height"
[ "$short" -lt 1500 ] || fail '这是普通 Kindle 5.19 安装包，Kindle Scribe 请使用 KS 版本。'
existing="$(cat "$BASE/VERSION" "$BASE/PACKAGE_VARIANT" "$BASE/release-info" 2>/dev/null | tr '[:upper:]' '[:lower:]')"
if printf '%s\n' "$existing" | grep -Eq '(^|[^[:alnum:]])(ks|scribe)([^[:alnum:]]|$)'; then fail '检测到 KS 安装，请使用 KS 版本，禁止混装。'; fi
[ -x /sbin/initctl ] || fail '缺少 Kindle Upstart 服务'
. "$PKG/runtime-lock.sh" || fail '缺少安装锁模块'
acquire_runtime_lock || fail '阅读记录正在运行，请先退出后再安装'
[ -s "$PKG/payload-manifest.tsv" ] && [ -s "$PKG/install-manifest.txt" ] || fail '缺少安装清单'
while IFS="$(printf '\t')" read -r expected size file; do
    case "$file" in ''|/*|*'..'*) fail '非法 payload 路径';; esac
    [ -f "$PKG/$file" ] && [ ! -L "$PKG/$file" ] || fail "缺少安装资源: $file"
    actual="$(cksum < "$PKG/$file")" || fail '资源校验失败'
    set -- $actual
    [ "$1" = "$expected" ] && [ "$2" = "$size" ] || fail "安装资源损坏: $file"
done < "$PKG/payload-manifest.tsv"
# Before staging, snapshots, rootfs writes or daemon stop. Budget two payload
# copies (staging/publication), every replaced old file/release, and 8 MiB slack.
disk_kib() {
    disk_usage="$(du -sk "$1" 2>/dev/null)" || return 1
    printf '%s\n' "$disk_usage" | awk 'NR==1 && $1~/^[0-9]+$/ && $1<1073741824 {n=$1;ok=1} END {if(ok && NR==1)printf "%.0f\n",n;else exit 1}'
}
payload_kib="$(disk_kib "$PKG")" || fail '存储空间不足或无法确认安装大小，安装已停止。'
[ "$payload_kib" -gt 0 ] || fail '存储空间不足或无法确认安装大小，安装已停止。'
needed_kib=$((payload_kib*2+8192))
for old in "$RELEASE" "$BASE/bin/native-reading-time-daemon.sh" "$BASE/fonts/NotoSansCJKsc-Regular.otf" "$BASE/fonts/FONT-LICENSE.txt" "$BASE/assets/launcher-icon.png" "$BASE/VERSION" "$BASE/activation-verified" "$DOCS/reading-records.sh" "$DOCS/reading-records-install-cleanup.sh" "$DOCS/阅读记录.sh" "$DOCS/阅读记录-optimized.sh" "$CONF"; do
    [ -e "$old" ] || [ -L "$old" ] || continue
    old_kib="$(disk_kib "$old")" || fail '存储空间不足或无法确认备份大小，安装已停止。'
    needed_kib=$((needed_kib+old_kib))
done
space="$(LC_ALL=C df -Pk /mnt/us 2>/dev/null)" || fail '存储空间不足或无法确认 Kindle 安装空间，安装已停止。'
printf '%s\n' "$space" | awk -v need="$needed_kib" '
    NR==1 {if($0 !~ /(1024-blocks|1K-blocks)/)bad=1;next}
    NR==2 {if(NF!=6 || $2!~/^[0-9]+$/ || $3!~/^[0-9]+$/ || $4!~/^[0-9]+$/ || $5!~/^[0-9]+%$/)bad=1;
           if($2<=0 || $3>$2 || $4>$2 || $4<need || $5+0>100)bad=1;next}
    {bad=1} END {exit (bad || NR!=2)}' || fail '存储空间不足或无法确认 Kindle 安装空间，安装已停止。'
log "preflight us required_kib=$needed_kib"
mkdir -p "$BASE" "$DOCS" "$BASE/releases" || fail '无法创建运行目录'
umask 077
mkdir "$STAGE" || fail '无法创建安装暂存目录，已有恢复材料未被覆盖'
STAGE_OWNED=1
mkdir "$STAGE/release" "$STAGE/backup" || fail '无法创建安装暂存目录'
: > "$STAGE/journal"; : > "$STAGE/deploy"
slot=0
snapshot() {
    slot=$((slot+1))
    had_file=0
    if [ -e "$1" ] || [ -L "$1" ]; then
        [ -f "$1" ] && [ ! -L "$1" ] || fail "目标类型异常: $1"
        cp -p "$1" "$STAGE/backup/$slot" || fail '无法备份旧运行文件'
        cmp -s "$1" "$STAGE/backup/$slot" || fail '旧运行文件备份校验失败'
        had_file=1
    fi
    printf '%s\t%s\t%s\n' "$slot" "$1" "$had_file" >> "$STAGE/journal" || fail '无法记录回滚清单'
}
while IFS="$(printf '\t')" read -r src category dst mode; do
    case "$src:$dst" in *'..'*|/*|*':/'*) fail '非法部署路径';; esac
    case "$mode" in 644|755) :;; *) fail '非法文件权限';; esac
    case "$category:$dst" in
      release:bin/*|release:ui/*|release:ui-calendar/*|release:render-assets/*)
        mkdir -p "$(dirname "$STAGE/release/$dst")" || fail '无法暂存运行目录'
        cp "$PKG/$src" "$STAGE/release/$dst" && chmod "$mode" "$STAGE/release/$dst" || fail '无法暂存运行文件'
        cmp -s "$PKG/$src" "$STAGE/release/$dst" || fail '暂存文件校验失败'
        continue;;
      base:bin/native-reading-time-daemon.sh|base:fonts/NotoSansCJKsc-Regular.otf|base:fonts/FONT-LICENSE.txt|base:assets/launcher-icon.png) target="$BASE/$dst";;
      docs:reading-records.sh) target="$DOCS/$dst";;
      service:native-reading-time.conf) target="$CONF";;
      *) fail '安装清单含未授权的目标';;
    esac
    snapshot "$target"
    printf '%s\t%s\t%s\n' "$src" "$target" "$mode" >> "$STAGE/deploy" || fail '无法记录部署清单'
done < "$PKG/install-manifest.txt"
for dst in "$BASE/VERSION" "$BASE/activation-verified" "$DOCS/reading-records-install-cleanup.sh" "$DOCS/阅读记录.sh" "$DOCS/阅读记录-optimized.sh"; do snapshot "$dst"; done
SNAPSHOT_COUNT=$slot
JOURNAL_CKSUM="$(cksum < "$STAGE/journal")" || fail '无法校验回滚清单'
[ ! -d "$RELEASE" ] || HAD_RELEASE=1
prior_state="$(/sbin/initctl status native-reading-time 2>/dev/null)" || {
    [ ! -e "$CONF" ] || fail '无法确认原阅读记录服务状态，安装已停止'
    prior_state=absent
}
case "$prior_state" in
    *start/running*) SERVICE_WAS_RUNNING=1; remember_daemon_pid "$prior_state" || fail '无法确认原阅读记录服务 PID，安装已停止';;
    *stop/waiting*|absent) :;;
    *) fail '无法确认原阅读记录服务状态，安装已停止';;
esac
# Validate rootfs access BEFORE stopping the known-good daemon or publishing UI.
root_rw || fail '无法更新系统服务'
ACTIVATED=1
stop_daemon || fail '无法停止或确认原阅读记录服务状态，安装已停止'
if [ "$HAD_RELEASE" -eq 1 ]; then mv "$RELEASE" "$STAGE/old-release" || fail '无法备份原运行版本'; fi
mv "$STAGE/release" "$RELEASE" || fail '无法发布运行版本'
while IFS="$(printf '\t')" read -r src dst mode; do
    atomic_file "$PKG/$src" "$dst" "$mode" || fail "无法部署: $dst"
    cmp -s "$PKG/$src" "$dst" || fail "部署后校验失败: $dst"
done < "$STAGE/deploy"
/sbin/initctl reload-configuration >/dev/null 2>&1 || fail '无法加载系统服务'
root_ro || fail '无法恢复系统只读状态'
/sbin/initctl start native-reading-time >/dev/null 2>&1 || fail '阅读记录服务启动失败'
sleep 2
verify_running_daemon || fail '阅读记录服务未运行'
# Activation checks code, resources and service; actual UI interaction is the
# user's next step, never falsely treated as on-device UI verification here.
[ -s "$BASE/reading-time.tsv" ] || fail '阅读记录服务未初始化数据'
cmp -s "$BASE/bin/native-reading-time-daemon.sh" "$PKG/native-reading-time-daemon.sh" || fail '服务部署校验失败'
printf '9.7.6-5.19-normal\n' > "$STAGE/VERSION"
atomic_file "$STAGE/VERSION" "$BASE/VERSION" 644 || fail '无法写入版本标识'
printf 'version=9.7.6-5.19-normal firmware=%s verified=files-and-service\n' "$firmware" > "$STAGE/verified"
atomic_file "$STAGE/verified" "$BASE/activation-verified" 644 || fail '无法记录安装校验'
atomic_file "$PKG/resources/reading-records-install-cleanup.sh" "$DOCS/reading-records-install-cleanup.sh" 755 || fail '无法生成安装清理入口'
# Old formal launchers are exact known paths, removed inside the transaction.
rm -f "$DOCS/阅读记录.sh" "$DOCS/阅读记录-optimized.sh" || fail '无法更新旧入口'
COMMITTED=1
scan; sync
log 'SUCCESS: 9.7.6-5.19-normal files and daemon verified; user data preserved'
toast '阅读记录安装完成，请先打开阅读记录确认正常，再清理安装文件。'
exit 0
