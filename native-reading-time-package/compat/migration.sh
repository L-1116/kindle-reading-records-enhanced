#!/bin/sh
# Exact historical path + content inventory. Never execute a historical remover.
rr_owned() {
    [ -f "$3" ] && [ ! -L "$3" ] && [ -r "$OWNERSHIP" ] || return 1
    rr_sum=$(cksum < "$3") || return 1
    set -- "$1" "$2" $rr_sum
    awk -F '\t' -v kind="$1" -v path="$2" -v sum="$3" -v size="$4" \
        '$1==kind && $2==path && $3==sum && $4==size {found=1} END {exit !found}' "$OWNERSHIP"
}
rr_entry_names() {
    printf '%s\n' reading-records.sh 阅读记录.sh 阅读记录-entry.sh 阅读记录-optimized.sh reading-records-uninstall.sh \
        reading-records-install.sh reading-records-9.7.6-install.sh reading-records-install-cleanup.sh \
        '安装好之后，确认无误了再点这个.sh' '点这个安装，然后确认插件正常之前不要删文件.sh'
}
rr_migration_preflight() {
    MIGRATION_PROTECTED=0
    rr_entry_names > "$TMP/entry-names"
    while IFS= read -r rr_name; do
        [ -e "$DOCS/$rr_name" ] || [ -L "$DOCS/$rr_name" ] || continue
        if ! rr_owned entry "$rr_name" "$DOCS/$rr_name"; then
            MIGRATION_PROTECTED=1
            note "PROTECTED unknown entry=$DOCS/$rr_name"
            # A conflicting formal entry cannot be safely replaced.
            case "$rr_name" in reading-records.sh|reading-records-install-cleanup.sh) return 1;; esac
        fi
    done < "$TMP/entry-names"
    for rr_other in "$DOCS/"*.sh; do
        [ -f "$rr_other" ] || continue
        grep -Fqx '# Name: 阅读记录' "$rr_other" || continue
        if ! rr_owned entry "${rr_other##*/}" "$rr_other"; then
            MIGRATION_PROTECTED=1
            note "PROTECTED unrecognized reading entry=$rr_other"
        fi
    done
    return 0
}
rr_migrate_entries() {
    while IFS= read -r rr_name; do
        [ "$rr_name" != reading-records.sh ] || continue
        [ "$rr_name" != reading-records-install-cleanup.sh ] || continue
        [ -e "$DOCS/$rr_name" ] || [ -L "$DOCS/$rr_name" ] || continue
        if rr_owned entry "$rr_name" "$DOCS/$rr_name"; then
            rm -f "$DOCS/$rr_name" || return 1
            note "REMOVED obsolete entry=$DOCS/$rr_name"
        else note "PROTECTED unknown entry=$DOCS/$rr_name"; fi
    done < "$TMP/entry-names"
}
rr_tree_owned() {
    [ -d "$3" ] && [ ! -L "$3" ] || return 1
    find "$3" -print > "$TMP/owned-tree" || return 1
    while IFS= read -r rr_file; do
        [ ! -L "$rr_file" ] || return 1
        if [ -d "$rr_file" ]; then
            [ "$rr_file" != "$3" ] || continue
            rr_relative=${rr_file#"$3/"}
            awk -F '\t' -v kind="$1" -v prefix="$2$rr_relative/" '$1==kind && index($2,prefix)==1 {found=1} END {exit !found}' "$OWNERSHIP" || return 1
            continue
        fi
        rr_relative=${rr_file#"$3/"}
        rr_owned "$1" "$2$rr_relative" "$rr_file" || return 1
    done < "$TMP/owned-tree"
}
rr_retire_releases() {
    # Only confirmed after the user has opened the new UI and chosen cleanup.
    # Every file must match known historical bytes and no live entry may reference it.
    rr_old_names=$(awk -F '\t' '$1=="release" {split($2,p,"/"); print p[1]}' "$OWNERSHIP" | sort -u) || return 1
    for rr_old in $rr_old_names; do
        case "$rr_old" in ''|*[!0-9A-Za-z.-]*|.|..) return 1;; esac
        rr_tree="$BASE/releases/$rr_old"
        [ "$rr_tree" != "$RELEASE" ] && [ -d "$rr_tree" ] || continue
        if ! rr_tree_owned release "$rr_old/" "$rr_tree"; then note "PROTECTED unknown release=$rr_tree"; continue; fi
        rr_referenced=0
        find "$DOCS" -type f -name '*.sh' -print > "$TMP/live-entries" || return 1
        while IFS= read -r rr_live; do
            if grep -Fq "$rr_old" "$rr_live"; then rr_referenced=1
            elif grep -Eq 'READING_RELEASE=|releases/.*\$' "$rr_live"; then
                if rr_owned entry "${rr_live##*/}" "$rr_live"; then :
                elif [ "$rr_live" = "$DOCS/reading-records-v4-install.sh" ] &&
                     grep -Fqx "PRODUCT_VERSION='$PRODUCT_VERSION'" "$rr_live" &&
                     grep -Fqx "BUILD_ID='$(sed -n 's/^build_id=//p' "$BASE/release-info")'" "$rr_live"; then :
                else rr_referenced=1; fi
            fi
        done < "$TMP/live-entries"
        for rr_live in "$BASE/bin/"*.sh; do
            [ -r "$rr_live" ] || continue
            if grep -Fq "$rr_old" "$rr_live"; then rr_referenced=1
            elif grep -Eq 'READING_RELEASE=|releases/.*\$' "$rr_live" && ! rr_owned payload "${rr_live##*/}" "$rr_live"; then rr_referenced=1; fi
        done
        if [ "$rr_referenced" = 0 ]; then rm -rf "$rr_tree" || return 1; note "REMOVED unreferenced release=$rr_tree"
        else note "PROTECTED referenced release=$rr_tree"; fi
    done
}

rr_retire_legacy_cleanup() {
    rr_helper="$BASE/bin/uninstall.sh"
    rr_owned payload uninstall.sh "$rr_helper" || return 0
    rr_helper_used=0
    find "$DOCS" -type f -name '*.sh' -print > "$TMP/live-entries" || return 1
    if [ -d "$MNT_US/extensions" ]; then find "$MNT_US/extensions" -type f -name '*.sh' -print >> "$TMP/live-entries" || return 1; fi
    while IFS= read -r rr_live; do
        grep -Fq '/uninstall.sh' "$rr_live" && rr_helper_used=1
    done < "$TMP/live-entries"
    if [ "$rr_helper_used" = 0 ]; then rm -f "$rr_helper" || return 1; note 'REMOVED obsolete safe cleanup helper'
    else note 'PROTECTED referenced safe cleanup helper'; fi
}
