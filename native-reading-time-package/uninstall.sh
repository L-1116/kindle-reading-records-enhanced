#!/bin/sh

# Safe, manifest-driven Reading Records uninstaller. It intentionally has no
# "delete all data" mode.
PKG="${READING_PACKAGE_DIR:-/mnt/us/native-reading-time-package}"
BASE="${READING_BASE:-/mnt/us/reading-time}"
DOCS="${READING_DOCUMENTS:-/mnt/us/documents}"
MNT_US="${READING_MNT_US:-/mnt/us}"
UPSTART="${READING_UPSTART_DIR:-/etc/upstart}"
TMP_ROOT="${READING_TMPDIR:-/tmp}"
MANIFEST="${READING_INSTALL_MANIFEST:-$BASE/install-manifest.txt}"
[ -r "$MANIFEST" ] || MANIFEST="$PKG/install-manifest.txt"
RESULT="${READING_UNINSTALL_RESULT:-$DOCS/reading-records-uninstall-result.txt}"
DIAGNOSTIC="${READING_UNINSTALL_DIAGNOSTIC:-$DOCS/reading-records-uninstall-diagnostic.txt}"
JOB=native-reading-time
STAGE=initialize
ERROR=none
ERROR_PATH=
FAILURES=0
LAST_FAILURE_STAGE=
REMOVED=0
FOUND=0
ROOT_RW=0

toast() { command -v lipc-set-prop >/dev/null 2>&1 && lipc-set-prop com.lab126.system toasterMessage "$1" >/dev/null 2>&1 || true; }
now() { date 2>/dev/null || echo unknown; }
write_result() {
    result_status="$1"; result_code="$2"
    mkdir -p "$DOCS" 2>/dev/null || true
    result_tmp="${RESULT}.new.$$"
    {
        printf 'TIMESTAMP=%s\nSTAGE=%s\nSTATUS=%s\nEXIT_CODE=%s\n' "$(now)" "$STAGE" "$result_status" "$result_code"
        printf 'REMOVED=%s\nUSER_DATA=preserved\n' "$REMOVED"
        [ "$ERROR" != none ] && printf 'ERROR=%s\nPATH=%s\n' "$ERROR" "$ERROR_PATH"
        printf 'REINSTALL=reading-records-install.sh\n'
    } > "$result_tmp" 2>/dev/null && mv "$result_tmp" "$RESULT" 2>/dev/null || true
}
record_failure() {
    failure_error="$1"; failure_path="$2"
    FAILURES=$((FAILURES+1))
    LAST_FAILURE_STAGE="$STAGE"
    ERROR="$failure_error"; ERROR_PATH="$failure_path"
    mkdir -p "$DOCS" 2>/dev/null || true
    {
        printf 'TIMESTAMP=%s\nSTAGE=%s\nERROR=%s\nPATH=%s\n' "$(now)" "$STAGE" "$failure_error" "$failure_path"
        printf 'NOTE=Safe uninstall continued; run the uninstaller again after correcting this error.\n\n'
    } >> "$DIAGNOSTIC" 2>/dev/null || true
}
root_ro() {
    [ "$ROOT_RW" -eq 1 ] || return 0
    mntroot ro >/dev/null 2>&1 || /usr/sbin/mntroot ro >/dev/null 2>&1 || /sbin/mntroot ro >/dev/null 2>&1 || true
    ROOT_RW=0
}
root_rw() {
    [ "$ROOT_RW" -eq 1 ] && return 0
    if mntroot rw >/dev/null 2>&1 || /usr/sbin/mntroot rw >/dev/null 2>&1 || /sbin/mntroot rw >/dev/null 2>&1; then ROOT_RW=1; return 0; fi
    return 1
}
scan_documents() {
    command -v lipc-set-prop >/dev/null 2>&1 || return 0
    lipc-set-prop com.lab126.scanner doFullScan 1 >/dev/null 2>&1 || lipc-set-prop com.lab126.scanner triggerUpdate 1 >/dev/null 2>&1 || true
}
resolve_path() {
    resolve_root="$1"; resolve_relative="$2"
    case "$resolve_relative" in ''|/*|*'..'*) return 1;; esac
    case "$resolve_root" in
        BASE) printf '%s/%s\n' "$BASE" "$resolve_relative";;
        DOCS) printf '%s/%s\n' "$DOCS" "$resolve_relative";;
        MNT_US) printf '%s/%s\n' "$MNT_US" "$resolve_relative";;
        UPSTART) printf '%s/%s\n' "$UPSTART" "$resolve_relative";;
        TMP) printf '%s/%s\n' "$TMP_ROOT" "$resolve_relative";;
        *) return 1;;
    esac
}
remove_file() {
    remove_path="$1"
    [ -e "$remove_path" ] || [ -L "$remove_path" ] || return 0
    FOUND=$((FOUND+1))
    if rm -f "$remove_path" 2>/dev/null; then REMOVED=$((REMOVED+1)); else record_failure permission_denied "$remove_path"; fi
}
remove_tree() {
    remove_path="$1"
    [ -e "$remove_path" ] || [ -L "$remove_path" ] || return 0
    FOUND=$((FOUND+1))
    if rm -rf "$remove_path" 2>/dev/null; then REMOVED=$((REMOVED+1)); else record_failure permission_denied "$remove_path"; fi
}
remove_pattern() {
    pattern_root="$1"; pattern_name="$2"
    case "$pattern_name" in
        .install-9.7.5-test.*) pattern_prefix="$BASE/.install-9.7.5-test.";;
        reading-time.tsv.bak.new.*) pattern_prefix="$BASE/reading-time.tsv.bak.new.";;
        book-cover-cache.tsv.new.*) pattern_prefix="$BASE/book-cover-cache.tsv.new.";;
        book-cover-misses.tsv.new.*) pattern_prefix="$BASE/book-cover-misses.tsv.new.";;
        native-reading-dashboard.*) pattern_prefix="$TMP_ROOT/native-reading-dashboard.";;
        *) record_failure invalid_manifest_pattern "$pattern_name"; return;;
    esac
    for pattern_path in "${pattern_prefix}"*; do
        [ -e "$pattern_path" ] || [ -L "$pattern_path" ] || continue
        remove_tree "$pattern_path"
    done
}
manifest_pass() {
    wanted="$1"
    while IFS='|' read -r item_class item_root item_relative item_purpose; do
        case "$item_class" in ''|'#'*) continue;; esac
        [ "$item_class" = "$wanted" ] || continue
        item_path="$(resolve_path "$item_root" "$item_relative")" || { record_failure invalid_manifest_path "$item_root/$item_relative"; continue; }
        case "$item_class" in
            PROGRAM_TREE|CACHE_TREE|KUAL_TREE) remove_tree "$item_path";;
            TEMP_PATTERN) remove_pattern "$item_root" "$item_relative";;
            PERSISTENT_FILE) :;;
            *) remove_file "$item_path";;
        esac
    done < "$MANIFEST"
}
stop_owned_processes() {
    STAGE=stop_service
    if [ -x /sbin/initctl ]; then /sbin/initctl stop "$JOB" >/dev/null 2>&1 || true
    elif command -v initctl >/dev/null 2>&1; then initctl stop "$JOB" >/dev/null 2>&1 || true
    fi
    [ -r "$BASE/state" ] || return 0
    owned_pid="$(sed -n 's/^pid=\([0-9][0-9]*\)$/\1/p' "$BASE/state" 2>/dev/null | sed -n '1p')"
    [ -n "$owned_pid" ] || return 0
    [ -r "/proc/$owned_pid/cmdline" ] || return 0
    owned_cmd="$(tr '\000' ' ' < "/proc/$owned_pid/cmdline" 2>/dev/null)"
    case "$owned_cmd" in
        *"$BASE/bin/native-reading-time-daemon.sh"*) kill -TERM "$owned_pid" 2>/dev/null || record_failure process_stop_failed "$BASE/bin/native-reading-time-daemon.sh:$owned_pid";;
    esac
}

trap 'root_ro' EXIT
trap 'STAGE=interrupted; record_failure interrupted "${ERROR_PATH:-unknown}"; root_ro; write_result failed 130; exit 130' INT TERM HUP
mkdir -p "$DOCS" 2>/dev/null || true
: > "$DIAGNOSTIC" 2>/dev/null || true
[ "${READING_SKIP_ROOT_CHECK:-0}" = 1 ] || [ "$(id -u)" -eq 0 ] || {
    STAGE=initialize; ERROR=permission_denied; ERROR_PATH=root
    record_failure "$ERROR" "$ERROR_PATH"; write_result failed 1; toast "阅读记录卸载失败，请查看诊断文件"; exit 1
}
[ -r "$MANIFEST" ] || {
    STAGE=manifest; ERROR=manifest_missing; ERROR_PATH="$MANIFEST"
    record_failure "$ERROR" "$ERROR_PATH"; write_result failed 1; toast "阅读记录卸载失败：缺少安装清单"; exit 1
}

toast "正在安全卸载阅读记录，阅读数据会保留"
stop_owned_processes

STAGE=remove_startup
if [ -e "$UPSTART/$JOB.conf" ]; then
    FOUND=$((FOUND+1))
    if root_rw; then
        # FOUND was counted before the remount; avoid counting the same entry twice.
        FOUND=$((FOUND-1))
        manifest_pass SYSTEM_FILE
        command -v /sbin/initctl >/dev/null 2>&1 && /sbin/initctl reload-configuration >/dev/null 2>&1 || true
        root_ro
    else
        record_failure permission_denied "$UPSTART/$JOB.conf"
    fi
fi
manifest_pass SCRIPTLET_FILE

STAGE=remove_runtime
manifest_pass RUNTIME_FILE
manifest_pass TEMP_PATTERN

STAGE=remove_program
manifest_pass PROGRAM_FILE
manifest_pass PROGRAM_TREE

STAGE=remove_cache
manifest_pass CACHE_FILE
manifest_pass CACHE_TREE

STAGE=remove_logs
manifest_pass LOG_FILE

STAGE=remove_kual
manifest_pass KUAL_TREE

STAGE=remove_manifest
manifest_pass MANIFEST_FILE

# Remove only now-empty application directories. Unknown files are preserved.
rmdir "$BASE/bin" "$BASE/compat" "$BASE/assets" "$BASE/ui" "$BASE/fonts" "$BASE/releases" "$BASE" 2>/dev/null || true

sync >/dev/null 2>&1 || true
scan_documents

STAGE=complete
if [ "$FAILURES" -gt 0 ]; then
    STAGE="$LAST_FAILURE_STAGE"
    write_result failed 1
    toast "阅读记录卸载未完成，请查看卸载诊断"
    exit 1
fi

if [ "$FOUND" -eq 0 ]; then uninstall_status=already_removed; else uninstall_status=uninstalled; fi
write_result "$uninstall_status" 0
toast "阅读记录已卸载，用户阅读数据已保留；可点击阅读记录安装重装"

# The caller executes this core from /tmp, so unlinking the Scriptlet is safe.
# Validate the exact expected filename; never honor an arbitrary deletion path.
STAGE=self_remove
if [ -n "${READING_UNINSTALL_ENTRY:-}" ]; then
    case "$READING_UNINSTALL_ENTRY" in
        "$DOCS/reading-records-uninstall.sh") remove_file "$READING_UNINSTALL_ENTRY";;
        *) record_failure invalid_self_path "$READING_UNINSTALL_ENTRY";;
    esac
fi
sync >/dev/null 2>&1 || true
scan_documents
[ -n "${READING_UNINSTALL_TEMP:-}" ] && case "$READING_UNINSTALL_TEMP" in "$TMP_ROOT"/reading-records-uninstall.*) rm -f "$READING_UNINSTALL_TEMP" 2>/dev/null || true;; esac

if [ "$FAILURES" -gt 0 ]; then
    STAGE="$LAST_FAILURE_STAGE"; write_result failed 1; toast "阅读记录卸载未完成，请查看卸载诊断"; exit 1
fi
exit 0
