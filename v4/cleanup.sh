#!/bin/sh
# Name: 确认无误之后，再点这个
# Author: Kindle Reading Records
# READING_RECORDS_V4_CLEANUP -- historical ownership marker only
# READING_RECORDS_INSTALL_CLEANUP_V1
MNT_US="${READING_MNT_US:-/mnt/us}"
DOCS="${READING_DOCUMENTS:-$MNT_US/documents}"
BASE="${READING_BASE:-$MNT_US/reading-time}"
PRODUCT_VERSION=9.7.6-5.20.1-vera-test2
RUNTIME_VERSION=9.7.6-5.20.1-vera
RELEASE="$BASE/releases/$RUNTIME_VERSION"
SELF="$DOCS/reading-records-install-cleanup.sh"
BOOT="$DOCS/reading-records-v4-install.sh"
PAYLOAD="$DOCS/阅读记录安装数据.tar"
LOG="$BASE/cleanup-last.log"
TMP="${READING_TMPDIR:-/tmp}/reading-records-cleanup.$$"
OWNERSHIP="$BASE/migration-manifest.tsv"
note() { printf '%s: %s\n' "$(date)" "$*" >> "$LOG" 2>/dev/null || true; }
abort() { note "ABORT $*"; printf 'ABORT %s\n' "$*" >&2; exit 1; }
. "$BASE/compat/lifecycle.sh" || exit 1
. "$BASE/compat/migration.sh" || exit 1
. "$BASE/compat/scanner.sh" || exit 1
. "$BASE/compat/runtime-lock.sh" || exit 1
LOCK="${READING_UI_LOCK:-${READING_TMPDIR:-/tmp}/reading-records-ui.lock}"
LOCK_OWNED=0
mkdir "$TMP" || exit 1
finish() { rr_cancel; rr_unlock; release_runtime_lock; rm -f "$TMP/entry-names" "$TMP/owned-tree" "$TMP/live-entries" "$TMP/snapshot-files"; rmdir "$TMP" 2>/dev/null || true; }
trap finish EXIT
trap 'exit 130' INT TERM HUP
rr_lock && acquire_runtime_lock || abort 'another install or UI is active'
[ ! -L "$BASE/release-info" ] && [ -r "$BASE/release-info" ] || abort 'metadata missing'
grep -Fqx "product_version=$PRODUCT_VERSION" "$BASE/release-info" && grep -Fqx 'variant=standard' "$BASE/release-info" || abort 'version or variant mismatch'
grep -Fqx "runtime_release=$RELEASE" "$BASE/release-info" && grep -Fqx "formal_entry=$DOCS/reading-records.sh" "$BASE/release-info" || abort 'activation target mismatch'
[ -x "$BASE/bin/launch.sh" ] && [ -x "$RELEASE/bin/reading-records.sh" ] && [ -r "$BASE/reading-time.tsv" ] && [ -x "$BASE/bin/native-reading-time-daemon.sh" ] && [ -r "$BASE/service/native-reading-time.conf" ] && [ -r "${READING_UPSTART_DIR:-/etc/upstart}/native-reading-time.conf" ] || abort 'active runtime missing'
rr_owned entry reading-records.sh "$DOCS/reading-records.sh" || abort 'formal entry differs from verified installation'
[ "$(cksum < "$OWNERSHIP")" = "$(sed -n 's/^ownership_cksum=//p' "$BASE/release-info")" ] || abort 'ownership inventory changed'
# Detect old payload ownership before removing any install artifact.
PKG="$MNT_US/native-reading-time-package"
if [ -e "$PKG" ] || [ -L "$PKG" ]; then
    rr_tree_owned payload '' "$PKG" || abort 'old payload contains unknown files; preserved'
fi
rr_entry_names > "$TMP/entry-names"
rr_migrate_entries || abort 'entry migration failed'
if [ -d "$PKG" ]; then rm -rf "$PKG" || abort 'old payload removal failed'; note "REMOVED old payload=$PKG"; fi
if rr_owned archive reading-records-9.7.6-data.tar "$DOCS/reading-records-9.7.6-data.tar"; then
    rm -f "$DOCS/reading-records-9.7.6-data.tar" || exit 1
    note 'REMOVED verified 5.19 installer archive'
fi
# Root compatibility artifacts are removed only by exact historical contents.
for rr_root in RUNME.sh README.txt PACKAGE-MANIFEST.json V4-PAYLOAD; do
    if rr_owned root "$rr_root" "$MNT_US/$rr_root"; then rm -f "$MNT_US/$rr_root" || exit 1; note "REMOVED $MNT_US/$rr_root"
    elif [ -e "$MNT_US/$rr_root" ]; then note "PROTECTED unrecognized root artifact=$MNT_US/$rr_root"; fi
 done
rr_kual="$MNT_US/extensions/reading-records-installer"
if [ -d "$rr_kual" ] && rr_tree_owned root 'extensions/reading-records-installer/' "$rr_kual"; then rm -rf "$rr_kual" || exit 1; note "REMOVED $rr_kual"
elif [ -e "$rr_kual" ]; then note "PROTECTED unrecognized KUAL tree=$rr_kual"; fi
rr_retire_legacy_cleanup || abort 'legacy helper retirement failed'
rr_retire_releases || abort 'release retirement failed'
# One owned pre-upgrade snapshot is retained until this explicit confirmation.
rr_backup="$BASE/.previous-install"
if [ -d "$rr_backup" ] && [ ! -L "$rr_backup" ] && grep -Fqx 'READING_RECORDS_ROLLBACK_V1' "$rr_backup/owned"; then
    rr_backup_safe=1
    [ "$(cksum < "$rr_backup/snapshot-files")" = "$(cat "$rr_backup/snapshot-cksum")" ] || rr_backup_safe=0
    if [ "$rr_backup_safe" = 1 ]; then
        while IFS='|' read -r rr_checksum rr_path; do
            [ -f "$rr_backup/$rr_path" ] && [ ! -L "$rr_backup/$rr_path" ] && [ "$(cksum < "$rr_backup/$rr_path")" = "$rr_checksum" ] || rr_backup_safe=0
        done < "$rr_backup/snapshot-files"
        find "$rr_backup" -print > "$TMP/snapshot-files" || rr_backup_safe=0
        while IFS= read -r rr_path; do
            [ ! -L "$rr_path" ] || rr_backup_safe=0
            [ -d "$rr_path" ] && continue
            rr_relative=${rr_path#"$rr_backup/"}
            case "$rr_relative" in snapshot-files|snapshot-cksum) continue;; esac
            awk -F '|' -v path="$rr_relative" '$2==path {found=1} END {exit !found}' "$rr_backup/snapshot-files" || rr_backup_safe=0
        done < "$TMP/snapshot-files"
    fi
    if [ "$rr_backup_safe" = 1 ]; then rm -rf "$rr_backup" || exit 1; note 'REMOVED confirmed rollback snapshot'
    else note 'PROTECTED changed rollback snapshot'; fi
fi
# The archive is tied to the still-present, signed bootstrap checksum.
if [ -f "$BOOT" ] && [ ! -L "$BOOT" ] && grep -Fq '# READING_RECORDS_V4_BOOTSTRAP' "$BOOT" && grep -Fqx "PRODUCT_VERSION='$PRODUCT_VERSION'" "$BOOT"; then
    rr_expected=$(sed -n "s/^PAYLOAD_CKSUM='\([0-9]*\)'$/\1/p" "$BOOT")
    if [ -f "$PAYLOAD" ] && [ ! -L "$PAYLOAD" ] && [ "$(cksum < "$PAYLOAD" | awk '{print $1}')" = "$rr_expected" ]; then rm -f "$PAYLOAD" || exit 1; fi
    rm -f "$BOOT" || exit 1
fi
# Keep installation evidence outside the scanned library, with byte verification.
rr_result="$DOCS/reading-records-v4-install-result.txt"
rr_install_log="$DOCS/reading-records-v4-install.log"
if [ -f "$rr_result" ] && [ ! -L "$rr_result" ] && grep -Fqx "product_version=$PRODUCT_VERSION" "$rr_result"; then
    rr_archive="$BASE/install-logs"
    if [ ! -L "$rr_archive" ] && mkdir -p "$rr_archive"; then
        for rr_report in "$rr_result" "$rr_install_log"; do
            [ -f "$rr_report" ] && [ ! -L "$rr_report" ] || continue
            rr_saved="$rr_archive/${rr_report##*/}.$PRODUCT_VERSION.$$"
            if [ ! -e "$rr_saved" ] && cp "$rr_report" "$rr_saved" && cmp -s "$rr_report" "$rr_saved"; then
                rm -f "$rr_report" || exit 1; note "ARCHIVED $rr_report to $rr_saved"
            else note "PROTECTED install report=$rr_report"; fi
        done
    else note 'PROTECTED install reports; archive directory unavailable'; fi
fi
if rr_owned entry reading-records-install-cleanup.sh "$SELF"; then rm -f "$SELF" || exit 1; fi
sync
rr_scan_documents
note 'result=SUCCESS; runtime history configuration covers services logs preserved'
rr_run 1 lipc-set-prop com.lab126.system toasterMessage '安装文件清理完成' >/dev/null 2>&1 || true
exit 0
