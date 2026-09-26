#!/bin/sh
# READING_RECORDS_CLEANUP_CORE_V1
# Legacy filename is retained only to replace old destructive copies safely.
# This script never stops the service or removes the active app, data or cache.

MNT_US="/mnt/us"
BASE="$MNT_US/reading-time"
DOCS="$MNT_US/documents"
PKG="$MNT_US/native-reading-time-package"
RELEASE="$BASE/releases/9.7.5-test"
RESOLVER="$RELEASE/bin/reading-records.sh"
LAUNCHER="$BASE/bin/launch.sh"
VIEWER="$DOCS/阅读记录.sh"
LOG="$BASE/cleanup-last.log"
TMP_ROOT="${READING_TMPDIR:-/tmp}"
SELF_TMP=
TARGETS_FILE="$BASE/.cleanup-targets.$$"
INVENTORY_FILE="$BASE/.cleanup-inventory.$$"
REMOVED=0
SKIPPED=0
PROTECTED=0
FAILURES=0
BLOCKED=0

case "$0" in
    "$BASE/bin/uninstall.sh"|"$PKG/uninstall.sh")
        handoff="$TMP_ROOT/reading-records-cleanup.$$"
        cp "$0" "$handoff" && chmod 700 "$handoff" || exit 1
        exec /bin/sh "$handoff"
        ;;
    "$TMP_ROOT"/reading-records-cleanup.[0-9]*) SELF_TMP="$0";;
esac

cleanup_temp() {
    rm -f "$TARGETS_FILE" 2>/dev/null || true
    rm -f "$INVENTORY_FILE" 2>/dev/null || true
    [ -n "$SELF_TMP" ] && rm -f "$SELF_TMP" 2>/dev/null || true
}
trap cleanup_temp EXIT

note() { printf '%s\n' "$*" >> "$LOG" 2>/dev/null || true; }
abort() {
    if [ -d "$BASE" ]; then
        printf 'timestamp=%s\ncleanup_version=1\nresult=ABORT\nreason=active Reading Time installation not verified: %s\n' "$(date)" "$1" > "$LOG" 2>/dev/null || true
    fi
    printf 'ABORT: active Reading Time installation not verified: %s\n' "$1" >&2
    exit 1
}
toast() { command -v lipc-set-prop >/dev/null 2>&1 && lipc-set-prop com.lab126.system toasterMessage "$1" >/dev/null 2>&1 || true; }
scan_documents() {
    command -v lipc-set-prop >/dev/null 2>&1 || return 0
    lipc-set-prop com.lab126.scanner doFullScan 1 >/dev/null 2>&1 || lipc-set-prop com.lab126.scanner triggerUpdate 1 >/dev/null 2>&1 || true
}

# No installed-version checksum is hard-coded: verify the active launcher and
# resolver, and compare with the staged package only if that package exists.
[ -d "$BASE" ] && [ -w "$BASE" ] || abort "plugin directory unavailable"
[ -x "$VIEWER" ] && [ -x "$LAUNCHER" ] && [ -x "$RESOLVER" ] || abort "entry, launcher or resolver missing"
[ -x "$BASE/bin/native-reading-time-daemon.sh" ] && [ -r "$BASE/reading-time.tsv" ] || abort "tracker or reading history missing"
[ -r /etc/upstart/native-reading-time.conf ] || abort "tracker service configuration missing"
[ -r "$RELEASE/bin/reading-insights-cover.lua" ] && [ -r "$BASE/compat/detect_env.sh" ] || abort "installed helpers missing"
grep -Fqx 'LAUNCHER="/mnt/us/reading-time/bin/launch.sh"' "$VIEWER" || abort "library entry targets another launcher"
grep -Fqx 'RELEASE="$BASE/releases/9.7.5-test"' "$LAUNCHER" || abort "launcher targets another release"
grep -Fqx 'MAIN="$RELEASE/bin/reading-records.sh"' "$LAUNCHER" || abort "launcher does not execute the resolver"
if [ -e "$PKG" ] || [ -L "$PKG" ]; then
    [ -d "$PKG" ] && [ ! -L "$PKG" ] && [ -f "$PKG/install.sh" ] && [ -f "$PKG/阅读记录-optimized.sh" ] || abort "installer payload is not a recognized directory"
    cmp -s "$PKG/阅读记录-optimized.sh" "$RESOLVER" || abort "installer payload differs from installed resolver"
fi

# This literal list is the deletion allowlist. The companion
# cleanup-manifest.txt documents the origin and reason for every entry.
targets() {
    sed '/^#/d' <<'CLEANUP_TARGETS'
REPORT|FILE|DOCS|reading-records-install-result.txt|Compatibility V1-V3|Scriptlet installation result
REPORT|FILE|DOCS|reading-records-cover-debug-result.txt|Cover Debug V1-V3|cover replay result
REPORT|FILE|DOCS|reading-records-uninstall-result.txt|Compatibility V1-V3|old uninstaller result
REPORT|FILE|DOCS|reading-records-uninstall-diagnostic.txt|Compatibility V1-V3|old uninstaller diagnostic
REPORT|FILE|DOCS|reading-records-kual-error.txt|Compatibility V1-V3|installer KUAL error
REPORT|FILE|DOCS|reading-records-diagnostic.txt|Compatibility V1-V3|external diagnostic report
REPORT|FILE|DOCS|阅读记录诊断.txt|Compatibility V1-V3|external diagnostic report
REPORT|FILE|DOCS|reading-records-launch-error.txt|Compatibility V1-V3|stale launcher error report
REPORT|FILE|BASE|cover-debug.log|Cover Debug V1-V3|temporary cover replay log
DEBUG|FILE|DOCS|阅读记录封面诊断.sh|Cover Debug V1-V3|visible debug Scriptlet
DEBUG|FILE|MNT_US|cover-debug.sh|Cover Debug V1-V3|one-shot debug runner
DEBUG|FILE|MNT_US|COVER-DEBUG-README.txt|Cover Debug V1-V3|debug kit instructions
DEBUG|FILE|MNT_US|COVER-V3-TEST-README.txt|Compatibility V3 test|test-only instructions
DEBUG|FILE|MNT_US|debug/cover-v3-test-README.txt|Compatibility V3 development|manually copied test instructions
DEBUG|TREE|MNT_US|debug/cover-debug|Cover Debug development|manually copied debug kit
DEBUG|RMDIR|MNT_US|debug|Cover Debug development|remove only if empty
ENTRY|TREE|MNT_US|extensions/reading-records-cover-debug|Cover Debug V1-V3|debug KUAL extension
ENTRY|FILE|DOCS|reading-records-install.sh|Compatibility V1-V3|visible install Scriptlet
ENTRY|TREE|MNT_US|extensions/reading-records-installer|Compatibility V1-V3|installer KUAL extension
PACKAGE|FILE|MNT_US|RUNME.sh|9.7.4 and Compatibility V1-V3|one-shot root installer entry
PACKAGE|FILE|MNT_US|README.txt|Compatibility V1-V3|installer package instructions
PACKAGE|TREE|MNT_US|native-reading-time-package|9.7.4 and Compatibility V1-V3|installer payload after verified activation
PACKAGE|FILE|MNT_US|PACKAGE-MANIFEST.json|Compatibility V3|package integrity manifest
PACKAGE|FILE|BASE|bin/uninstall.sh|Compatibility V1-V3|now-safe legacy cleanup core copy
SELF|FILE|DOCS|reading-records-uninstall.sh|Compatibility V1-V3|cleanup Scriptlet self-removal
CLEANUP_TARGETS
}

resolve_target() {
    relative="$3"
    case "$relative" in ''|/*|*'..'*|*'*'*|*'?'*|*'['*) return 1;; esac
    case "$2" in
        BASE) TARGET="$BASE/$relative";;
        DOCS) TARGET="$DOCS/$relative";;
        MNT_US) TARGET="$MNT_US/$relative";;
        *) return 1;;
    esac
    return 0
}
exists_target() { [ -e "$TARGET" ] || [ -L "$TARGET" ]; }

package_tree_owned() {
    [ -r "$MNT_US/PACKAGE-MANIFEST.json" ] && command -v find >/dev/null 2>&1 || return 1
    find "$PKG" -print > "$INVENTORY_FILE" 2>/dev/null || return 1
    while IFS= read -r payload_path; do
        [ "$payload_path" = "$PKG" ] && continue
        payload_relative="${payload_path#"$MNT_US/"}"
        if [ -d "$payload_path" ] && [ ! -L "$payload_path" ]; then
            grep -Fq "\"path\": \"$payload_relative/" "$MNT_US/PACKAGE-MANIFEST.json" || return 1
        else
            grep -Fq "\"path\": \"$payload_relative\"" "$MNT_US/PACKAGE-MANIFEST.json" || return 1
        fi
    done < "$INVENTORY_FILE"
}

# Generic root filenames require an ownership signature before removal.
# Never follow links to directories or delete an unrecognized payload tree.
owned_target() {
    [ -L "$TARGET" ] && case "$2" in TREE|RMDIR) return 1;; esac
    case "$TARGET" in
        "$MNT_US/RUNME.sh") grep -Fq 'native-reading-time-package' "$TARGET" 2>/dev/null;;
        "$MNT_US/README.txt") grep -q '^Kindle 阅读记录' "$TARGET" 2>/dev/null;;
        "$MNT_US/PACKAGE-MANIFEST.json") grep -Fq 'native-reading-time-package/' "$TARGET" 2>/dev/null;;
        "$MNT_US/cover-debug.sh") grep -Fq 'cover-debug.log' "$TARGET" 2>/dev/null;;
        "$MNT_US/COVER-DEBUG-README.txt") grep -Fq 'Cover Debug' "$TARGET" 2>/dev/null;;
        "$MNT_US/COVER-V3-TEST-README.txt") grep -Fq 'Compatibility V3' "$TARGET" 2>/dev/null;;
        "$MNT_US/debug/cover-debug") [ -f "$TARGET/cover-debug.sh" ] && grep -Fq 'cover-debug.log' "$TARGET/cover-debug.sh";;
        "$MNT_US/extensions/reading-records-cover-debug") [ -f "$TARGET/config.xml" ] && grep -Fq 'reading-records-cover-debug' "$TARGET/config.xml";;
        "$MNT_US/extensions/reading-records-installer") [ -f "$TARGET/config.xml" ] && grep -Fq 'reading-records-installer' "$TARGET/config.xml";;
        "$MNT_US/native-reading-time-package") [ -d "$TARGET" ] && [ -f "$TARGET/install.sh" ] && cmp -s "$TARGET/阅读记录-optimized.sh" "$RESOLVER" && package_tree_owned;;
        *) return 0;;
    esac
}

targets > "$TARGETS_FILE" || abort "cannot create target list"
{
    printf 'timestamp=%s\ncleanup_version=1\n' "$(date)"
    printf 'phase=detect\n'
} > "$LOG" || abort "cannot write internal cleanup log"

# Phase 1: inspect every exact target before deleting anything.
while IFS='|' read -r target_phase target_type target_root target_relative target_origin target_reason; do
    resolve_target "$target_phase" "$target_root" "$target_relative" || abort "invalid built-in target"
    if exists_target; then
        if owned_target "$target_phase" "$target_type"; then note "DETECT FOUND $TARGET ($target_origin)"
        else
            note "DETECT PROTECTED $TARGET (ownership signature mismatch)"
            PROTECTED=$((PROTECTED+1))
            [ "$TARGET" = "$PKG" ] && BLOCKED=1
        fi
    else
        note "DETECT NOT_FOUND $TARGET"
    fi
done < "$TARGETS_FILE"
for protected_path in "$VIEWER" "$LAUNCHER" "$RESOLVER" "$BASE/bin/native-reading-time-daemon.sh" "$BASE/reading-time.tsv" "$BASE/reading-time.tsv.bak" "$BASE/阅读时长统计.txt" "$BASE/user.conf" "$BASE/book-cover-cache.tsv" "$BASE/book-cover-misses.tsv" "$BASE/book-covers" "$BASE/releases" "$BASE/install-manifest.txt" "$BASE/compat/detect_env.sh" "$RELEASE/bin/reading-insights-cover.lua"; do
    note "DETECT PROTECTED $protected_path"
    PROTECTED=$((PROTECTED+1))
done
if [ "$BLOCKED" -ne 0 ]; then
    note "result=ABORT"
    printf 'ABORT: installer payload contains unrecognized files; nothing removed\n' >&2
    exit 1
fi

remove_phase() {
    selected_phase="$1"
    while IFS='|' read -r target_phase target_type target_root target_relative target_origin target_reason; do
        [ "$target_phase" = "$selected_phase" ] || continue
        resolve_target "$target_phase" "$target_root" "$target_relative" || { FAILURES=$((FAILURES+1)); continue; }
        if ! exists_target; then note "SKIP NOT_FOUND $TARGET"; SKIPPED=$((SKIPPED+1)); continue; fi
        if ! owned_target "$target_phase" "$target_type"; then note "SKIP PROTECTED $TARGET"; SKIPPED=$((SKIPPED+1)); continue; fi
        case "$target_type" in
            FILE) [ ! -d "$TARGET" ] || [ -L "$TARGET" ] || { note "SKIP PROTECTED_DIRECTORY $TARGET"; SKIPPED=$((SKIPPED+1)); continue; }
                  rm -f "$TARGET" 2>/dev/null;;
            TREE) rm -rf "$TARGET" 2>/dev/null;;
            RMDIR) rmdir "$TARGET" 2>/dev/null;;
            *) false;;
        esac
        if [ "$?" -eq 0 ]; then note "REMOVED $TARGET"; REMOVED=$((REMOVED+1))
        elif [ "$target_type" = RMDIR ]; then note "SKIP NONEMPTY $TARGET"; SKIPPED=$((SKIPPED+1))
        else note "FAILED $TARGET"; FAILURES=$((FAILURES+1)); fi
    done < "$TARGETS_FILE"
}

# The package directory and finally the visible cleanup entry are last.
remove_phase REPORT
remove_phase DEBUG
remove_phase ENTRY
remove_phase PACKAGE
if [ "$FAILURES" -ne 0 ]; then
    note "removed=$REMOVED"
    note "skipped=$SKIPPED"
    note "protected=$PROTECTED"
    note "result=FAILED"
    toast "安装文件清理未完成，请查看内部日志"
    exit 1
fi
remove_phase SELF
sync >/dev/null 2>&1 || true
scan_documents
note "removed=$REMOVED"
note "skipped=$SKIPPED"
note "protected=$PROTECTED"
if [ "$FAILURES" -eq 0 ]; then
    note "result=SUCCESS"
    toast "安装文件清理完成"
    exit 0
fi
note "result=FAILED"
exit 1
