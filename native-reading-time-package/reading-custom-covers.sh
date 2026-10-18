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
# Shared modal/pagination state. The reader receives only small numeric values;
# all selection bounds are checked again here before changing either list.
rr_pager_open() {
    case "$1" in books|settings_cover_books) :;; *) return 1;; esac
    case "$2:$3" in *[!0-9:]*|:*|*:) return 1;; esac
    [ "$2" -gt 1 ] || return 0
    rr_pager_return="$1"; RR_PAGER_TOTAL="$2"; RR_PAGER_CURRENT="$3"
    [ "$RR_PAGER_CURRENT" -ge 1 ] && [ "$RR_PAGER_CURRENT" -le "$RR_PAGER_TOTAL" ] || RR_PAGER_CURRENT=1
    RR_PAGER_START=$(((RR_PAGER_CURRENT-1)/20*20+1))
    export RR_PAGER_TOTAL RR_PAGER_CURRENT RR_PAGER_START
    mode=settings_cover_picker
}
rr_pager_action() {
    [ "$mode" = settings_cover_picker ] || return 1
    case "$action" in
        settings_cover_pager_back) mode="$rr_pager_return";;
        settings_cover_pager_prev) [ "$RR_PAGER_START" -le 20 ] || RR_PAGER_START=$((RR_PAGER_START-20));;
        settings_cover_pager_next) [ "$((RR_PAGER_START+20))" -gt "$RR_PAGER_TOTAL" ] || RR_PAGER_START=$((RR_PAGER_START+20));;
        settings_cover_pager_pick_*)
            rr_pick="${action#settings_cover_pager_pick_}"
            case "$rr_pick" in ''|*[!0-9]*|0*) return 1;; esac
            [ "${#rr_pick}" -le 9 ] && [ "$rr_pick" -ge "$RR_PAGER_START" ] && [ "$rr_pick" -lt "$((RR_PAGER_START+20))" ] && [ "$rr_pick" -le "$RR_PAGER_TOTAL" ] || return 1
            case "$rr_pager_return" in books) book_page="$rr_pick";; settings_cover_books) cover_book_page="$rr_pick";; *) return 1;; esac
            mode="$rr_pager_return";;
    esac
}
rr_pager_render() {
    rr_cover_exec lua "$SETTINGS_HELPERS/reading-insights-render.lua" "${RENDER_ASSETS:-$SETTINGS_HELPERS/../render-assets}" "$SESSION_DIR/pager.spec" || return 1
    rr_settings_image "$SESSION_DIR/pager.pgm" "$1" "$2" "$3" "$4"
}
rr_pager_label() {
    printf 'canvas\tpage\t452\t100\t%s/pager.pgm\ntextcenter\tpage\tB\t30\t226\t50\t0\t第 %s 页，共 %s 页\nrect\tpage\t64\t78\t324\t1\t96\nwrite\tpage\n' "$SESSION_DIR" "$1" "$2" > "$SESSION_DIR/pager.spec"
    rr_pager_render 410 "$3" 452 100
}
rr_pager_draw() {
    # The static white modal background also clears every old book/cover pixel.
    printf 'canvas\tpicker\t904\t700\t%s/pager.pgm\n' "$SESSION_DIR" > "$SESSION_DIR/pager.spec"
    rr_n=0
    while [ "$rr_n" -lt 20 ] && [ "$((RR_PAGER_START+rr_n))" -le "$RR_PAGER_TOTAL" ]; do
        rr_number=$((RR_PAGER_START+rr_n)); rr_x=$(((rr_n%5)*180)); rr_y=$(((rr_n/5)*140))
        if [ "$rr_number" = "$RR_PAGER_CURRENT" ]; then rr_bg=20; rr_ink=255; else rr_bg=255; rr_ink=0; fi
        printf 'round\tpicker\t%s\t%s\t160\t112\t14\t20\nround\tpicker\t%s\t%s\t156\t108\t12\t%s\ntextcenter\tpicker\tB\t36\t%s\t%s\t%s\t%s\n' "$rr_x" "$rr_y" "$((rr_x+2))" "$((rr_y+2))" "$rr_bg" "$((rr_x+80))" "$((rr_y+56))" "$rr_ink" "$rr_number" >> "$SESSION_DIR/pager.spec"
        rr_n=$((rr_n+1))
    done
    rr_end=$((RR_PAGER_START+19)); [ "$rr_end" -le "$RR_PAGER_TOTAL" ] || rr_end=$RR_PAGER_TOTAL
    printf 'textcenter\tpicker\tR\t28\t440\t625\t0\t%s - %s / %s\n' "$RR_PAGER_START" "$rr_end" "$RR_PAGER_TOTAL" >> "$SESSION_DIR/pager.spec"
    [ "$RR_PAGER_START" -le 20 ] || printf 'textcenter\tpicker\tB\t44\t100\t625\t0\t‹\n' >> "$SESSION_DIR/pager.spec"
    [ "$rr_end" -ge "$RR_PAGER_TOTAL" ] || printf 'textcenter\tpicker\tB\t44\t780\t625\t0\t›\n' >> "$SESSION_DIR/pager.spec"
    printf 'write\tpicker\n' >> "$SESSION_DIR/pager.spec"
    rr_pager_render 196 600 904 700
}
rr_cover_status() {
    rr_status='暂无封面'
    # Main UI supplies the exact original resolver, in non-extracting mode.
    # Legacy fallback cannot safely extract originals; retain its safe renderer.
    if type resolveOriginalBookCover >/dev/null 2>&1 && resolveOriginalBookCover "$1" "$2" cached "${rr_status_catalog:-$CATALOG}" >/dev/null; then
        rr_status='原始封面'
        if [ -n "$3" ]; then
            if [ "${custom_cover_enabled:-0}" = 1 ]; then rr_status="$rr_status · 已设专属"
            else rr_status="$rr_status · 专属未启用"; fi
        fi
    elif [ "${custom_cover_enabled:-0}" != 1 ]; then
        [ -z "$3" ] || rr_status="$rr_status · 专属未启用"
    elif [ -n "$3" ] && rr_cover_prepare "$3" >/dev/null; then rr_status='专属封面'
    else
        if [ "${rr_generic_checked:-0}" = 0 ]; then
            rr_generic_checked=1; rr_generic_valid=0
            [ -z "$rr_generic" ] || ! rr_cover_prepare "$rr_generic" >/dev/null || rr_generic_valid=1
        fi
        [ "${rr_generic_valid:-0}" != 1 ] || rr_status='通用封面'
    fi
}
rr_cover_draw_books() {
    rr_pages=$(((cover_book_count+9)/10)); [ "$rr_pages" -gt 0 ] || rr_pages=1
    [ "$cover_book_page" -le "$rr_pages" ] || cover_book_page=$rr_pages
    [ "$cover_book_page" -ge 1 ] || cover_book_page=1
    ot 32 226 80 80 REGULAR "共 $cover_book_count 本历史书籍"
    if [ "$cover_book_count" -eq 0 ]; then ot 36 510 104 104 REGULAR '暂无历史阅读书籍'
    else
        rr_first=$(((cover_book_page-1)*10+1)); rr_last=$((rr_first+9))
        awk -v a="$rr_first" -v b="$rr_last" 'NR>=a&&NR<=b' "$SESSION_DIR/custom-books.tsv" > "$SESSION_DIR/custom-page.tsv"
        rr_cover_cmd cards "$SESSION_DIR/custom-page.tsv" > "$SESSION_DIR/custom-cards.tsv" || return 1
        # Reuse the existing snapshot, or query only these ten identities.
        # Do not initialize the full progress/catalog snapshot from Settings.
        rr_status_catalog="$CATALOG"
        if [ ! -r "$rr_status_catalog" ]; then
            rr_status_catalog="$SESSION_DIR/history-catalog.tsv"; : > "$rr_status_catalog"
            if command -v sqlite3 >/dev/null 2>&1 && [ -r "$CC_DB" ]; then
                rr_query="$(rr_cover_cmd catalog-query "$SESSION_DIR/custom-page.tsv")" || return 1
                sqlite3 -readonly -separator "$(printf '\t')" "$CC_DB" "$rr_query" > "$rr_status_catalog" 2>/dev/null || : > "$rr_status_catalog"
            fi
        fi
        rr_generic="$(rr_cover_cmd generic)"; rr_generic_checked=0; rr_generic_valid=0; rr_row=0
        while IFS="$(printf '\t')" read -r rr_id rr_title rr_specific rr_line1 rr_line2; do
            rr_x=$((104+(rr_row%2)*568)); rr_y=$((330+(rr_row/2)*204))
            ot 34 "$rr_y" "$rr_x" "$((1272-rr_x-500))" REGULAR "${rr_line1#line:}" || return 1
            [ "$rr_line2" = line: ] || ot 34 "$((rr_y+48))" "$rr_x" "$((1272-rr_x-500))" REGULAR "${rr_line2#line:}" || return 1
            rr_cover_status "${rr_id#book:}" "${rr_title#title:}" "${rr_specific#name:}"
            ot 28 "$((rr_y+116))" "$rr_x" "$((1272-rr_x-500))" REGULAR "$rr_status" || return 1
            rr_row=$((rr_row+1))
        done < "$SESSION_DIR/custom-cards.tsv"
    fi
    rr_pager_label "$cover_book_page" "$rr_pages" 1410
}
rr_cover_draw() {
    case "$mode" in
    settings_cover_picker) rr_pager_draw;;
    settings_cover_books) rr_cover_draw_books;;
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
    settings_cover_images)
        rr_total=$cover_count; rr_page=$cover_page; rr_size=4; rr_list="$SESSION_DIR/custom-images.tsv"
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
            rr_row=0
            awk -v a="$rr_first" -v b="$rr_last" 'NR>=a&&NR<=b' "$rr_list" | while IFS= read -r rr_line; do
                rr_row=$((${rr_row:-0}+1))
                rr_y=$((330+(rr_row-1)*260))
                if ! rr_cover_preview "$rr_line" 104 "$rr_y" 132 198; then ot 30 $((rr_y+50)) 104 990 REGULAR '无效'; fi
                rr_cover_text 36 $((rr_y+42)) 280 130 "$rr_line"
                [ "$rr_line" != "$(rr_cover_current)" ] || ot 34 $((rr_y+118)) 280 130 REGULAR '● 当前选择'
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
    settings_cover_pager_*) rr_pager_action;;
    settings_cover_page) rr_pager_open settings_cover_books "$(((cover_book_count+9)/10))" "$cover_book_page";;
    settings_cover_generic) cover_target_kind=generic; cover_target_id=''; cover_target_title='通用替代封面'; cover_manage_return=settings_cover; mode=settings_cover_manage;;
    settings_cover_books) rr_cover_history; mode=settings_cover_books;;
    settings_cover_info) mode=settings_cover_info;;
    settings_cover_scan) rr_cover_scan;;
    settings_cover_choose) rr_cover_scan; mode=settings_cover_images;;
    settings_cover_clear) rr_cover_save '' || settings_error='保存失败，请重试';;
    settings_cover_back)
        case "$mode" in settings_cover_picker) mode="$rr_pager_return";; settings_cover_images) mode=settings_cover_manage;; settings_cover_manage) mode="$cover_manage_return";; *) mode=settings_cover;; esac;;
    settings_cover_prev|settings_cover_next)
        [ "$action" = settings_cover_next ] && rr_delta=1 || rr_delta=-1
        if [ "$mode" = settings_cover_images ]; then rr_max=$(((cover_count+3)/4)); cover_page=$((cover_page+rr_delta)); [ "$cover_page" -le "$rr_max" ] || cover_page=$rr_max; [ "$cover_page" -gt 0 ] || cover_page=1
        else rr_max=$(((cover_book_count+9)/10)); cover_book_page=$((cover_book_page+rr_delta)); [ "$cover_book_page" -le "$rr_max" ] || cover_book_page=$rr_max; [ "$cover_book_page" -gt 0 ] || cover_book_page=1; fi;;
    settings_cover_item_*)
        rr_slot="${action#settings_cover_item_}"
        case "$rr_slot" in 1|2|3|4|5|6|7|8|9|10) :;; *) return 1;; esac
        if [ "$mode" = settings_cover_images ]; then
            [ "$rr_slot" -le 4 ] || return 1
            rr_index=$(((cover_page-1)*4+rr_slot)); rr_name="$(sed -n "${rr_index}p" "$SESSION_DIR/custom-images.tsv")"
            [ -n "$rr_name" ] || return 0
            if rr_cover_save "$rr_name"; then mode=settings_cover_manage
            else settings_error='图片无效或保存失败，请重新选择'; fi
        elif [ "$mode" = settings_cover_books ]; then
            rr_index=$(((cover_book_page-1)*10+rr_slot)); rr_line="$(sed -n "${rr_index}p" "$SESSION_DIR/custom-books.tsv")"
            [ -n "$rr_line" ] || return 0
            cover_target_id="${rr_line%%	*}"; cover_target_id="${cover_target_id#book:}"; cover_target_title="${rr_line#*	}"
            cover_target_kind=book
            cover_manage_return=settings_cover_books; mode=settings_cover_manage
        fi;;
    esac
}
