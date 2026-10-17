#!/bin/sh
# Dashboard-only custom covers. Image directory is never enumerated on startup.
rr_cover_init() {
    COVER_IMAGES="$BASE/custom-covers"
    COVER_PREVIEWS="$BASE/custom-cover-previews"
    COVER_LINKS="$BASE/custom-cover-associations.tsv"
    COVER_IMAGE_HELPER="$SETTINGS_HELPERS/cover-image"
    COVER_LINK_HELPER="$SETTINGS_HELPERS/reading-custom-covers.lua"
    cover_page=1; cover_book_page=1; cover_count=0; cover_book_count=0
    [ -L "$COVER_IMAGES" ] || mkdir -p "$COVER_IMAGES" 2>/dev/null || true
}
rr_cover_storage() {
    [ ! -L "$COVER_IMAGES" ] && [ ! -L "$COVER_PREVIEWS" ] && [ ! -L "$COVER_LINKS" ] || return 1
    mkdir -p "$COVER_IMAGES" "$COVER_PREVIEWS" || return 1
    [ -d "$COVER_IMAGES" ] && [ -d "$COVER_PREVIEWS" ]
}
rr_cover_exec() {
    "$@" & rr_worker=$!
    rr_start="$(awk '{sub(/^.*\) /, ""); split($0,a," "); print a[20]}' "/proc/$rr_worker/stat" 2>/dev/null)"
    printf '%s %s\n' "$rr_worker" "$rr_start" > "$SESSION_DIR/cover-worker"
    wait "$rr_worker"; rr_worker_rc=$?
    rm -f "$SESSION_DIR/cover-worker"
    return "$rr_worker_rc"
}
rr_cover_stop() {
    [ -r "$SESSION_DIR/cover-worker" ] || return 0
    read -r rr_worker rr_start < "$SESSION_DIR/cover-worker"
    case "$rr_worker:$rr_start" in *[!0-9:]*|:*|*:) return 0;; esac
    rr_current="$(awk '{sub(/^.*\) /, ""); split($0,a," "); print a[20]}' "/proc/$rr_worker/stat" 2>/dev/null)"
    [ "$rr_current" = "$rr_start" ] || return 0
    kill -TERM "$rr_worker" 2>/dev/null || true
    kill -KILL "$rr_worker" 2>/dev/null || true
    rm -f "$SESSION_DIR/cover-worker"
}
rr_cover_cmd() {
    [ ! -L "$COVER_LINKS" ] && { [ ! -e "$COVER_LINKS" ] || [ -f "$COVER_LINKS" ]; } || return 1
    rr_cover_exec lua "$COVER_LINK_HELPER" "$BASE" "$@"
}
rr_cover_prepare() {
    rr_cover_storage || return 1
    rr_cover_exec "$COVER_IMAGE_HELPER" prepare "$COVER_IMAGES" "$1" "$COVER_PREVIEWS" 2>/dev/null
}
rr_cover_real() {
    [ ! -L "$COVER_PREVIEWS" ] && mkdir -p "$COVER_PREVIEWS" || return 1
    rr_cover_exec "$COVER_IMAGE_HELPER" real "$1" "$COVER_PREVIEWS" 2>/dev/null
}
rr_cover_fallback() {
    [ "${custom_cover_enabled:-0}" = 1 ] || return 1
    rr_specific="$(rr_cover_cmd get "$1" "$2")"
    if [ -n "$rr_specific" ]; then rr_cover_prepare "$rr_specific" && return 0; fi
    rr_generic="$(rr_cover_cmd generic)"
    [ -n "$rr_generic" ] && rr_cover_prepare "$rr_generic"
}
rr_cover_save() {
    rr_cover_storage || return 1
    # Refuse stale/injected paths before saving. Clearing never touches images.
    [ -z "$1" ] || rr_cover_prepare "$1" >/dev/null || return 1
    rr_cover_txn="$BASE/.custom-cover-save.$$"
    (umask 077; mkdir "$rr_cover_txn") || return 1
    [ "$cover_target_kind" = generic ] && rr_save_command=save-generic || rr_save_command=save
    rr_cover_cmd "$rr_save_command" "$cover_target_id" "$cover_target_title" "$1" "$rr_cover_txn"
    rr_cover_saved=$?
    rm -f "$rr_cover_txn/associations"; rmdir "$rr_cover_txn" 2>/dev/null || true
    return "$rr_cover_saved"
}
rr_cover_scan() {
    rr_cover_storage || { settings_error='图片目录不可用'; return 1; }
    rr_cover_exec "$COVER_IMAGE_HELPER" scan "$COVER_IMAGES" > "$SESSION_DIR/custom-images.new" 2>/dev/null || {
        rm -f "$SESSION_DIR/custom-images.new"; settings_error='扫描失败，请重试'; return 1;
    }
    LC_ALL=C sort "$SESSION_DIR/custom-images.new" > "$SESSION_DIR/custom-images.tsv" || return 1
    rm -f "$SESSION_DIR/custom-images.new"
    cover_count="$(wc -l < "$SESSION_DIR/custom-images.tsv")"; cover_page=1
}
rr_cover_history() {
    rr_cover_cmd history > "$SESSION_DIR/custom-books.tsv" || { settings_error='读取阅读历史失败'; return 1; }
    cover_book_count="$(wc -l < "$SESSION_DIR/custom-books.tsv")"; cover_book_page=1
}
rr_cover_text() { ot "$1" "$2" "$3" "$4" REGULAR "$(rr_cover_cmd text "$5" "$1" "$((1272-$3-$4))")"; }
rr_cover_preview() {
    rr_preview="$(rr_cover_prepare "$1")" || return 1
    rr_settings_image "$rr_preview" "$2" "$3" "$4" "$5"
}
rr_cover_draw() {
    case "$mode" in
    settings_cover)
        ot 34 232 80 80 REGULAR "$([ "$custom_cover_enabled" = 1 ] && printf 已开启 || printf 已关闭) · 只替代无法显示的真实封面"
        rr_generic="$(rr_cover_cmd generic)"
        if [ -n "$rr_generic" ]; then
            rr_cover_preview "$rr_generic" 948 354 140 210 || true
            rr_cover_text 32 510 104 350 "$rr_generic"
        else ot 34 510 104 350 REGULAR '尚未选择通用图片'; fi
        ot 34 790 104 104 REGULAR "已保存 $(rr_cover_cmd count) 本书籍的专属关联"
        ot 32 1330 104 104 REGULAR "上次扫描：$cover_count 张候选图片（最多 4096 张）";;
    settings_cover_manage)
        rr_cover_text 40 226 80 80 "${cover_target_title:-未知书籍}"
        if [ "$cover_target_kind" = book ]; then
            case "$cover_target_id" in ''|unknown) rr_cover_identity='无有效 ID · 按历史标题关联';;
                *) rr_cover_identity="书籍 ID：$cover_target_id";; esac
            rr_cover_text 28 282 80 80 "$rr_cover_identity"
        fi
        rr_choice="$(rr_cover_current)"
        if [ -n "$rr_choice" ]; then
            if ! rr_cover_preview "$rr_choice" 456 350 360 540; then
                ot 34 570 370 220 REGULAR '图片失效，已回退'
            fi
            rr_cover_text 34 942 104 104 "$rr_choice"
        else ot 38 570 350 180 REGULAR '尚未选择替代图片'; fi;;
    settings_cover_images|settings_cover_books)
        if [ "$mode" = settings_cover_images ]; then rr_total=$cover_count; rr_page=$cover_page; rr_size=4; rr_list="$SESSION_DIR/custom-images.tsv"
        else rr_total=$cover_book_count; rr_page=$cover_book_page; rr_size=6; rr_list="$SESSION_DIR/custom-books.tsv"; fi
        rr_pages=$(((rr_total+rr_size-1)/rr_size)); [ "$rr_pages" -gt 0 ] || rr_pages=1
        ot 32 226 80 80 REGULAR "第 $rr_page / $rr_pages 页 · 共 $rr_total 项"
        if [ "$rr_total" -eq 0 ]; then
            if [ "$mode" = settings_cover_images ]; then
                ot 36 510 104 104 REGULAR '没有可选图片'
                ot 32 590 104 104 REGULAR 'USB 复制 JPG / PNG 到 reading-time/custom-covers/'
                ot 32 660 104 104 REGULAR '然后轻触下方「重新扫描」。'
            else ot 36 510 104 104 REGULAR '暂无历史阅读书籍'; fi
        else
            rr_first=$(((rr_page-1)*rr_size+1)); rr_last=$((rr_first+rr_size-1))
            awk -v a="$rr_first" -v b="$rr_last" 'NR>=a&&NR<=b' "$rr_list" | while IFS= read -r rr_line; do
                rr_row=$((${rr_row:-0}+1))
                if [ "$mode" = settings_cover_images ]; then
                    rr_y=$((330+(rr_row-1)*260))
                    if ! rr_cover_preview "$rr_line" 104 "$rr_y" 132 198; then ot 30 $((rr_y+50)) 104 990 REGULAR '无效'; fi
                    rr_cover_text 36 $((rr_y+42)) 280 130 "$rr_line"
                    [ "$rr_line" != "$(rr_cover_current)" ] || ot 34 $((rr_y+118)) 280 130 REGULAR '● 当前选择'
                else
                    rr_y=$((330+(rr_row-1)*160)); rr_id="${rr_line%%	*}"; rr_title="${rr_line#*	}"
                    rr_cover_text 38 "$rr_y" 104 104 "${rr_title:-未知书籍}"
                    rr_selected="$(rr_cover_cmd get "${rr_id#book:}" "$rr_title")"
                    rr_status="$([ -n "$rr_selected" ] && printf 已指定专属图片 || printf 尚未指定)"
                    case "${rr_id#book:}" in ''|unknown) rr_status="$rr_status · 无 ID";;
                        *) rr_status="$rr_status · ID: ${rr_id#book:}";; esac
                    rr_cover_text 30 $((rr_y+62)) 104 104 "$rr_status"
                fi
            done || exit 31
        fi;;
    esac
}
rr_cover_current() {
    if [ "$cover_target_kind" = generic ]; then rr_cover_cmd generic
    else rr_cover_cmd get "$cover_target_id" "$cover_target_title"; fi
}
rr_cover_action() {
    case "$action" in
    settings_cover_generic) cover_target_kind=generic; cover_target_id=''; cover_target_title='通用替代封面'; cover_manage_return=settings_cover; mode=settings_cover_manage;;
    settings_cover_books) rr_cover_history; mode=settings_cover_books;;
    settings_cover_info) mode=settings_cover_info;;
    settings_cover_scan) rr_cover_scan;;
    settings_cover_choose) rr_cover_scan; mode=settings_cover_images;;
    settings_cover_clear) rr_cover_save '' || settings_error='保存失败，请重试';;
    settings_cover_back)
        case "$mode" in settings_cover_images) mode=settings_cover_manage;; settings_cover_manage) mode="$cover_manage_return";; *) mode=settings_cover;; esac;;
    settings_cover_prev|settings_cover_next)
        [ "$action" = settings_cover_next ] && rr_delta=1 || rr_delta=-1
        if [ "$mode" = settings_cover_images ]; then rr_max=$(((cover_count+3)/4)); cover_page=$((cover_page+rr_delta)); [ "$cover_page" -le "$rr_max" ] || cover_page=$rr_max; [ "$cover_page" -gt 0 ] || cover_page=1
        else rr_max=$(((cover_book_count+5)/6)); cover_book_page=$((cover_book_page+rr_delta)); [ "$cover_book_page" -le "$rr_max" ] || cover_book_page=$rr_max; [ "$cover_book_page" -gt 0 ] || cover_book_page=1; fi;;
    settings_cover_item_*)
        rr_slot="${action#settings_cover_item_}"
        case "$rr_slot" in 1|2|3|4|5|6) :;; *) return 1;; esac
        if [ "$mode" = settings_cover_images ]; then
            [ "$rr_slot" -le 4 ] || return 1
            rr_index=$(((cover_page-1)*4+rr_slot)); rr_name="$(sed -n "${rr_index}p" "$SESSION_DIR/custom-images.tsv")"
            [ -n "$rr_name" ] || return 0
            if rr_cover_save "$rr_name"; then mode=settings_cover_manage
            else settings_error='图片无效或保存失败，请重新选择'; fi
        elif [ "$mode" = settings_cover_books ]; then
            rr_index=$(((cover_book_page-1)*6+rr_slot)); rr_line="$(sed -n "${rr_index}p" "$SESSION_DIR/custom-books.tsv")"
            [ -n "$rr_line" ] || return 0
            cover_target_id="${rr_line%%	*}"; cover_target_id="${cover_target_id#book:}"; cover_target_title="${rr_line#*	}"
            cover_target_kind=book
            cover_manage_return=settings_cover_books; mode=settings_cover_manage
        fi;;
    esac
}
