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
ROOT_RW=0; ACTIVATED=0; COMMITTED=0; LOCK_OWNED=0; SERVICE_WAS_RUNNING=0; HAD_RELEASE=0; ROLLBACK_FAILED=0
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
rollback() {
    log 'rolling back runtime transaction'
    /sbin/initctl stop native-reading-time >/dev/null 2>&1 || true
    if [ -d "$STAGE/old-release" ]; then
        rm -rf "$RELEASE"; mv "$STAGE/old-release" "$RELEASE" || { log 'ERROR: release rollback failed'; ROLLBACK_FAILED=1; }
    elif [ "$HAD_RELEASE" -eq 0 ]; then rm -rf "$RELEASE"; fi
    root_rw || { log 'ERROR: rootfs unavailable during rollback'; ROLLBACK_FAILED=1; }
    while IFS="$(printf '\t')" read -r slot dst; do
        rm -f "$dst.new.$$"
        if [ -f "$STAGE/backup/$slot" ]; then
            cp -p "$STAGE/backup/$slot" "$dst.rollback.$$" && mv "$dst.rollback.$$" "$dst" || { log "ERROR: rollback failed: $dst"; ROLLBACK_FAILED=1; }
        else rm -f "$dst"; fi
    done < "$STAGE/journal"
    /sbin/initctl reload-configuration >/dev/null 2>&1 || true
    root_ro || ROLLBACK_FAILED=1
    [ "$SERVICE_WAS_RUNNING" -eq 0 ] || /sbin/initctl start native-reading-time >/dev/null 2>&1 || true
    scan
}
finish() {
    trap '' INT TERM HUP
    if [ "$ACTIVATED" -eq 1 ] && [ "$COMMITTED" -eq 0 ]; then rollback; fi
    root_ro || log "ERROR: manual rootfs recovery required"
    if [ "$ROLLBACK_FAILED" -eq 1 ]; then
        log "ERROR: retained recovery backup: $STAGE"
    else
        case "$STAGE" in /mnt/us/reading-time/.install-9.7.6-normal.[0-9]*) rm -rf "$STAGE";; esac
    fi
    if [ "$LOCK_OWNED" -eq 1 ]; then rm -f "$LOCK/pid"; rmdir "$LOCK" 2>/dev/null || true; fi
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
[ "$(id -u)" -eq 0 ] || fail '安装需要 Scriptlet 的系统权限'
# Extract a dotted version, never confuse the build number with firmware.
firmware="$(cat /etc/prettyversion.txt /etc/version.txt 2>/dev/null | awk '
    {for(i=1;i<=NF;i++){v=$i;gsub(/^[^0-9]+|[^0-9.]+$/, "", v);n=split(v,a,".");
     if(n>=3 && a[1]==5){valid=1;for(j=1;j<=n;j++)if(a[j]!~/^[0-9]+$/)valid=0;if(valid){print v;exit}}}}')"
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
if ! mkdir "$LOCK" 2>/dev/null; then
    old_pid="$(cat "$LOCK/pid" 2>/dev/null)"
    case "$old_pid" in ''|*[!0-9]*) fail '安装已经开始，请稍后重试';; esac
    kill -0 "$old_pid" 2>/dev/null && fail '安装已经开始，请稍后重试'
    rm -f "$LOCK/pid" "$LOCK/ui-start" "$LOCK/ui-cancel"; rmdir "$LOCK" 2>/dev/null || fail '无法清理旧安装锁'
    mkdir "$LOCK" || fail '安装已经开始，请稍后重试'
fi
LOCK_OWNED=1; printf '%s\n' "$$" > "$LOCK/pid" || fail '无法写安装锁'
[ -s "$PKG/payload-manifest.tsv" ] && [ -s "$PKG/install-manifest.txt" ] || fail '缺少安装清单'
while IFS="$(printf '\t')" read -r expected size file; do
    case "$file" in ''|/*|*'..'*) fail '非法 payload 路径';; esac
    [ -f "$PKG/$file" ] && [ ! -L "$PKG/$file" ] || fail "缺少安装资源: $file"
    actual="$(cksum < "$PKG/$file")" || fail '资源校验失败'
    set -- $actual
    [ "$1" = "$expected" ] && [ "$2" = "$size" ] || fail "安装资源损坏: $file"
done < "$PKG/payload-manifest.tsv"
mkdir -p "$BASE" "$DOCS" "$BASE/releases" || fail '无法创建运行目录'
umask 077
mkdir "$STAGE" && mkdir "$STAGE/release" "$STAGE/backup" || fail '无法创建安装暂存目录'
: > "$STAGE/journal"; : > "$STAGE/deploy"
slot=0
snapshot() {
    slot=$((slot+1))
    if [ -e "$1" ] || [ -L "$1" ]; then
        [ -f "$1" ] && [ ! -L "$1" ] || fail "目标类型异常: $1"
        cp -p "$1" "$STAGE/backup/$slot" || fail '无法备份旧运行文件'
    fi
    printf '%s\t%s\n' "$slot" "$1" >> "$STAGE/journal" || fail '无法记录回滚清单'
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
[ ! -d "$RELEASE" ] || HAD_RELEASE=1
/sbin/initctl status native-reading-time 2>/dev/null | grep -q 'start/running' && SERVICE_WAS_RUNNING=1
# Validate rootfs access BEFORE stopping the known-good daemon or publishing UI.
root_rw || fail '无法更新系统服务'
ACTIVATED=1
/sbin/initctl stop native-reading-time >/dev/null 2>&1 || true
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
/sbin/initctl status native-reading-time 2>/dev/null | grep -q 'start/running' || fail '阅读记录服务未运行'
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
