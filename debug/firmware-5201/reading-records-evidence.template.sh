#!/bin/sh
# Name: 保存阅读记录升级现场（不修复）
# Author: Kindle Reading Records
# DontUseFBInk
# READING_RECORDS_READ_ONLY_EVIDENCE_V1

# Developer-only collector: never invokes ensure, remount, start, stop or repair.
@LIFECYCLE@
BASE="${READING_BASE:-/mnt/us/reading-time}"
DOCS="${READING_DOCUMENTS:-/mnt/us/documents}"
SELF=$0
PROC="${READING_PROC_ROOT:-/proc}"
rr_initctl() { rr_run 2 "${READING_INITCTL:-/sbin/initctl}" "$@"; }
umask 077
if [ "${1:-}" = --bounded-worker ]; then
    trap 'rr_cancel' EXIT
    trap 'rr_cancel; exit 130' INT TERM HUP
    rr_run 179 /bin/sh "$SELF" --worker
    exit $?
fi
if [ "${1:-}" != --worker ]; then
    mkdir -p "$DOCS" || exit 1
    REPORT="$DOCS/reading-records-evidence-$(date +%Y%m%d-%H%M%S)-$$.txt"
    export REPORT
    printf '只读采证已开始。请打开原生阅读器阅读两分钟，然后退出阅读；约三分钟后保存完成。\n此脚本不安装、不修复服务，也不修改阅读历史。\n' > "$REPORT" || exit 1
    nohup /bin/sh "$SELF" --bounded-worker >/dev/null 2>&1 < /dev/null &
    rr_run 1 lipc-set-prop com.lab126.system toasterMessage '只读采证已开始，请阅读两分钟后退出' >/dev/null 2>&1 || true
    exit 0
fi
WORK="${READING_TMPDIR:-/tmp}/reading-records-evidence.$$"
mkdir "$WORK" || exit 1
cleanup() { rr_cancel; rm -f "$WORK/status" "$WORK/app" "$WORK/power" "$WORK/checksum"; rmdir "$WORK" 2>/dev/null || true; }
trap cleanup EXIT
trap 'exit 130' TERM INT HUP
sample() {
    printf '\n[sample=%s timestamp=%s]\n' "$1" "$(date +%s)"
    for f in "${READING_PRETTYVERSION_PATH:-/etc/prettyversion.txt}" "${READING_VERSION_PATH:-/etc/version.txt}" "$BASE/VERSION" "$BASE/release-info"; do
        printf 'source=%s\n' "$f"; [ ! -r "$f" ] || head -c 1024 "$f"
    done
    printf '\n[service configuration]\n'
    f="${READING_UPSTART_DIR:-/etc/upstart}/native-reading-time.conf"
    printf 'config_exists=%s\nconfig_readable=%s\n' "$([ -e "$f" ] && echo yes || echo no)" "$([ -r "$f" ] && echo yes || echo no)"
    if [ -r "$f" ]; then head -c 8192 "$f"; else printf 'missing_or_unreadable=%s\n' "$f"; fi
    rr_initctl status native-reading-time > "$WORK/status" 2>&1
    printf '\nservice_query_exit=%s\n' "$?"; cat "$WORK/status"
    evidence_pid=$(sed -n 's/.*start\/running, process \([0-9][0-9]*\).*/\1/p' "$WORK/status")
    case "$evidence_pid" in ''|*[!0-9]*) :;; *)
        printf '\n[process identity]\n'
        [ ! -r "$PROC/$evidence_pid/cmdline" ] || tr '\000' '\n' < "$PROC/$evidence_pid/cmdline"
        [ ! -r "$PROC/$evidence_pid/stat" ] || head -c 2048 "$PROC/$evidence_pid/stat";;
    esac
    rr_run 2 lipc-get-prop com.lab126.appmgrd activeApp > "$WORK/app" 2>&1
    printf '\nactiveApp_exit=%s\n' "$?"; cat "$WORK/app"
    rr_run 2 lipc-get-prop com.lab126.powerd state > "$WORK/power" 2>&1
    printf '\npower_state_exit=%s\n' "$?"; cat "$WORK/power"
    printf '\n[daemon state]\n'; [ ! -r "$BASE/state" ] || head -c 8192 "$BASE/state"
    printf '\n[TSV metadata and checksum; checksum is not proof of timing]\n'
    ls -ld "$BASE" "$BASE/reading-time.tsv" 2>&1
    rr_run 2 cksum "$BASE/reading-time.tsv" > "$WORK/checksum" 2>&1
    printf 'checksum_exit=%s\n' "$?"; cat "$WORK/checksum"
    printf '\n[TSV last records]\n'; [ ! -f "$BASE/reading-time.tsv" ] || tail -c 8192 "$BASE/reading-time.tsv"
    for f in upstart.log service.log install.log launch-last.log service-status.txt; do
        printf '\n[%s]\n' "$f"; [ ! -r "$BASE/$f" ] || tail -c 8192 "$BASE/$f"
    done
    printf '\nactual_timing_verdict=requires_controlled_session_review\n'
}
# Four sparse samples, bounded to <180s including command timeouts. The
# launcher sample is explicitly not evidence that the book reader is active.
sample launcher_not_reading >> "$REPORT" 2>&1
/bin/sleep 35
sample reading_window_1 >> "$REPORT" 2>&1
/bin/sleep 55
sample reading_window_2 >> "$REPORT" 2>&1
/bin/sleep 35
sample after_reading_exit >> "$REPORT" 2>&1
printf '\ncollector_complete=yes\nrecovery_triggered=no\n' >> "$REPORT"
exit 0
