#!/bin/sh

# Kindle 原生阅读记录 9.6.4-ui-calendar.  This process exists only while the
# dashboard is open.  The tracker daemon and reading-time.tsv are untouched.
BASE="/mnt/us/reading-time"
DATA="$BASE/reading-time.tsv"
LOG="$BASE/dashboard-launch.log"
FBINK="/var/local/kmc/bin/fbink"
RELEASE="$BASE/releases/9.6.4-ui-calendar"
UI_DIR="$RELEASE/ui-calendar"
TOUCH_READER="$RELEASE/bin/reading-insights-touch-ui.lua"
RENDERER="$RELEASE/bin/reading-insights-render.lua"
RENDER_ASSETS="$RELEASE/render-assets"
CACHE_BUILDER="$RELEASE/bin/reading-insights-cache.awk"
LEGACY="$RELEASE/bin/reading-records-v9.6.3.sh"
TITLE_LAYOUT="$RELEASE/bin/reading-insights-titles.lua"
CC_DB="/var/local/cc.db"
SESSION_DIR="/tmp/native-reading-dashboard.$$"
SUMMARY="$SESSION_DIR/summary.tsv"; MONTHS="$SESSION_DIR/months.tsv"
DAYS="$SESSION_DIR/days.tsv"; DAY_BOOKS="$SESSION_DIR/day-books.tsv"
BOOKS="$SESSION_DIR/books.tsv"; PROGRESS_DB="$SESSION_DIR/cc-progress-viewer.db"
PROGRESS="$SESSION_DIR/book-progress.tsv"; SPEC="$SESSION_DIR/render-spec.tsv"
LOGICAL_W=1272; LOGICAL_H=1696; CLEAN_REFRESH_INTERVAL=6

exec >> "$LOG" 2>&1
echo "$(date): optimized dashboard launch, uid=$(id -u), pid=$$"

fail() { echo "$(date): ERROR: $1"; lipc-set-prop com.lab126.system toasterMessage "$1" >/dev/null 2>&1 || true; exit 1; }

detect_screen() {
    geometry="$(fbset 2>/dev/null | awk '/geometry/{print $2 " " $3;exit}')"; set -- $geometry
    SCREEN_W="${1:-0}"; SCREEN_H="${2:-0}"
    case "$SCREEN_W:$SCREEN_H" in *[!0-9:]*|0:*|*:0) SCREEN_W=0; SCREEN_H=0;; esac
    if [ "$SCREEN_W" -le 0 ] || [ "$SCREEN_H" -le 0 ]; then
        virtual="$(cat /sys/class/graphics/fb0/virtual_size 2>/dev/null)"; SCREEN_W="${virtual%%,*}"; vh="${virtual#*,}"
        case "$SCREEN_W:$vh" in *[!0-9:]*|0:*|*:0) SCREEN_W=0; vh=0;; esac
        if [ "$vh" -ge $((SCREEN_W*2)) ]; then SCREEN_H=$((vh/2)); else SCREEN_H="$vh"; fi
    fi
    [ "$SCREEN_W" -ge 600 ] && [ "$SCREEN_H" -ge 800 ] || fail "无法识别 Kindle 屏幕尺寸"
    [ "$SCREEN_H" -gt "$SCREEN_W" ] || fail "请将 Kindle 旋转为竖屏后再打开阅读记录"
    if [ $((SCREEN_W*LOGICAL_H)) -le $((SCREEN_H*LOGICAL_W)) ]; then SCALE_NUM="$SCREEN_W"; SCALE_DEN="$LOGICAL_W"; else SCALE_NUM="$SCREEN_H"; SCALE_DEN="$LOGICAL_H"; fi
    VIEW_W=$((LOGICAL_W*SCALE_NUM/SCALE_DEN)); VIEW_H=$((LOGICAL_H*SCALE_NUM/SCALE_DEN)); ORIGIN_X=$(((SCREEN_W-VIEW_W)/2)); ORIGIN_Y=$(((SCREEN_H-VIEW_H)/2))
}

find_touch_device() {
    if [ -n "${READING_TOUCH_DEVICE:-}" ] && [ -r "$READING_TOUCH_DEVICE" ]; then TOUCH="$READING_TOUCH_DEVICE"; return; fi
    for ep in /sys/class/input/event*; do
        [ -r "$ep/device/name" ] || continue; en="$(tr '[:upper:]' '[:lower:]' < "$ep/device/name" 2>/dev/null)"
        case "$en" in *touch*|*zforce*|*cyttsp*|*fts*|*_ts*) c="/dev/input/${ep##*/}"; [ -r "$c" ] && { TOUCH="$c"; return; };; esac
    done
    TOUCH="/dev/input/event1"
}

scale_len() { n=$(( $1*SCALE_NUM/SCALE_DEN )); [ "$n" -gt 0 ] || n=1; echo "$n"; }
scale_x() { echo $((ORIGIN_X+$1*SCALE_NUM/SCALE_DEN)); }
scale_y() { echo $((ORIGIN_Y+$1*SCALE_NUM/SCALE_DEN)); }
scale_right() { echo $((SCREEN_W-ORIGIN_X-VIEW_W+$1*SCALE_NUM/SCALE_DEN)); }
fbink_calls=0
fb() { fbink_calls=$((fbink_calls+1)); "$FBINK" "$@"; }
ot() {
    s="$(scale_len "$1")"; t="$(scale_y "$2")"; l="$(scale_x "$3")"; r="$(scale_right "$4")"; st="$5"; msg="$6"
    fb -q -b -t "regular=$RFONT,bold=$RFONT,px=$s,top=$t,left=$l,right=$r,style=$st" "$msg"
}
rect() {
    t="$(scale_y "$1")"; l="$(scale_x "$2")"; w="$(scale_len "$3")"; h="$(scale_len "$4")"
    fb -q -b -B "$5" -k "top=$t,left=$l,width=$w,height=$h"
}
image() {
    p="$1"; x="$(scale_x "$2")"; y="$(scale_y "$3")"; w="$(scale_len "$4")"; h="$(scale_len "$5")"
    fb -q -b -g "file=$p,x=$x,y=$y,w=$w,h=$h"
}

time_text() { v="$1"; h=$((v/3600)); m=$(((v%3600)/60)); s=$((v%60)); if [ "$h" -gt 0 ]; then printf '%s小时%s分钟' "$h" "$m"; elif [ "$m" -gt 0 ]; then printf '%s分钟%s秒' "$m" "$s"; else printf '%s秒' "$s"; fi; }
# Display helpers only: raw seconds in the caches remain unchanged.
minute_text() { mt_m=$(($1/60)); if [ "$mt_m" -ge 60 ]; then printf '%s小时%s分钟' "$((mt_m/60))" "$((mt_m%60))"; else printf '%s分钟' "$mt_m"; fi; }
calendar_time() { ct_s="$1"; ct_m=$((ct_s/60)); if [ "$ct_s" -le 0 ]; then return; elif [ "$ct_m" -eq 0 ]; then printf '%s秒' "$ct_s"; elif [ "$ct_m" -lt 60 ]; then printf '%s分' "$ct_m"; else printf '%s时%s分' "$((ct_m/60))" "$((ct_m%60))"; fi; }
days_in_month() { case "$2" in 1|3|5|7|8|10|12) echo 31;;4|6|9|11) echo 30;;2) if { [ $(($1%400)) -eq 0 ] || { [ $(($1%4)) -eq 0 ] && [ $(($1%100)) -ne 0 ]; }; }; then echo 29; else echo 28; fi;;esac; }
weekday_offset() { awk -v y="$1" -v m="$2" 'BEGIN{if(m<3){m+=12;y--}k=y%100;j=int(y/100);h=(1+int(13*(m+1)/5)+k+int(k/4)+int(j/4)+5*j)%7;print(h+5)%7}'; }
shift_month() { daily_m=$((daily_m+$1)); while [ "$daily_m" -lt 1 ]; do daily_m=$((daily_m+12)); daily_y=$((daily_y-1)); done; while [ "$daily_m" -gt 12 ]; do daily_m=$((daily_m-12)); daily_y=$((daily_y+1)); done; selected_day=1; }

uptime_ms() { awk '{printf "%d\n",$1*1000}' /proc/uptime 2>/dev/null; }
metric_begin() { metric_name="$1"; metric_start="$(uptime_ms)"; case "$metric_start" in ''|*[!0-9]*) metric_start=0;;esac; metric_fb_start="$fbink_calls"; }
metric_end() { e="$(uptime_ms)"; case "$e" in ''|*[!0-9]*) e="$metric_start";;esac; echo "METRIC operation=$metric_name elapsed_ms=$((e-metric_start)) fbink_calls=$((fbink_calls-metric_fb_start)) renderer=$1 fallback=$2 redraw=$3"; }

cache_ok=0
build_cache() {
    : > "$SUMMARY" && : > "$MONTHS" && : > "$DAYS" && : > "$DAY_BOOKS" && : > "$BOOKS.raw" || return 1
    awk -F '\t' -v summary="$SUMMARY" -v months="$MONTHS" -v days="$DAYS" -v daybooks="$DAY_BOOKS" -v books="$BOOKS.raw" -f "$CACHE_BUILDER" "$DATA" || return 1
    sort "$MONTHS" > "$MONTHS.sorted" && sort "$DAYS" > "$DAYS.sorted" && sort "$DAY_BOOKS" > "$DAY_BOOKS.sorted" && sort -nr "$BOOKS.raw" > "$BOOKS" || return 1
    mv "$MONTHS.sorted" "$MONTHS" && mv "$DAYS.sorted" "$DAYS" && mv "$DAY_BOOKS.sorted" "$DAY_BOOKS" || return 1
    rm -f "$BOOKS.raw"; cache_ok=1
}

progress_loaded=0
ensure_progress() {
    [ "$progress_loaded" -eq 0 ] || return 0; progress_loaded=1; rm -f "$PROGRESS_DB" "$PROGRESS" "$PROGRESS.new"
    if command -v sqlite3 >/dev/null 2>&1 && [ -r "$CC_DB" ] && cp "$CC_DB" "$PROGRESS_DB" 2>/dev/null; then
        sqlite3 -readonly -separator "$(printf '\t')" "$PROGRESS_DB" "SELECT CAST(p_percentFinished + 0.5 AS INTEGER),replace(replace(p_titles_0_nominal,char(9),' '),char(10),' ') FROM Entries WHERE p_titles_0_nominal IS NOT NULL AND p_percentFinished>=0 AND p_percentFinished<=100 ORDER BY p_lastAccess DESC;" > "$PROGRESS.new" 2>/dev/null || true
        [ -s "$PROGRESS.new" ] && mv "$PROGRESS.new" "$PROGRESS"
    fi
    rm -f "$PROGRESS_DB" "$PROGRESS.new"
}

pgm_valid() { [ -s "$1" ] || return 1; head="$(head -n 2 "$1" 2>/dev/null)"; [ "$head" = "P5
$2 $3" ] || return 1; bytes="$(wc -c < "$1")"; case "$bytes" in ''|*[!0-9]*) return 1;;esac; [ "$bytes" -ge $(($2*$3)) ]; }
renderer_available=0; forced_failure_used=0
[ -f "$RENDERER" ] && [ -r "$CACHE_BUILDER" ] && [ -r "$RENDER_ASSETS/dynamic-glyphs.pgm" ] && [ -r "$RENDER_ASSETS/dynamic-glyphs.tsv" ] && renderer_available=1
run_renderer() {
    [ "$renderer_available" -eq 1 ] && [ "$cache_ok" -eq 1 ] || return 1
    if [ "${DASHBOARD_RENDERER_FORCE_FAIL:-0}" = 1 ] && [ "$forced_failure_used" -eq 0 ]; then forced_failure_used=1; echo "$(date): forced renderer failure"; return 1; fi
    lua "$RENDERER" "$RENDER_ASSETS" "$SPEC" || return 1
}
canvas() { printf 'canvas\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" >> "$SPEC"; }
srect() { printf 'rect\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" >> "$SPEC"; }
sround() { printf 'round\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$SPEC"; }
stext() { printf 'text\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" "$8" >> "$SPEC"; }
swrite() { printf 'write\t%s\n' "$1" >> "$SPEC"; }

render_total() {
    set -- $(cat "$SUMMARY"); total="${1:-0}"; read_days="${2:-0}"; [ "$read_days" -gt 0 ] && average=$(((total+read_days*30)/(read_days*60)*60)) || average=0
    set -- $(awk -F '\t' -v y="$view_year" 'BEGIN{for(i=1;i<=12;i++)v[i]=0}$1~("^"y"-"){m=substr($1,6,2)+0;v[m]+=$2}END{for(i=1;i<=12;i++)printf "%d%s",int(v[i]/60),(i<12?" ":"\n")}' "$MONTHS")
    max=0; for mins in "$@"; do [ "$mins" -gt "$max" ] && max="$mins"; done
    if [ "$max" -le 60 ]; then scale=60; elif [ "$max" -le 120 ]; then scale=120; else scale=$((((max+59)/60)*60)); fi
    a="$SESSION_DIR/total-summary.pgm.new"; b="$SESSION_DIR/total-year.pgm.new"; c="$SESSION_DIR/total-chart.pgm.new"; : > "$SPEC"
    canvas summary 1102 180 "$a"; srect summary 0 110 1102 2 190
    stext summary B 70 10 5 left 0 "$(time_text "$total")"; stext summary B 32 40 137 left 0 "阅读天数  ${read_days}天"; stext summary B 32 645 137 left 0 "日均  $(minute_text "$average")"; swrite summary
    canvas year 272 70 "$b"; stext year B 39 136 10 center 0 "${view_year}年"; swrite year
    canvas chart 1122 690 "$c"; srect chart 0 40 1122 2 190; srect chart 0 237 1122 2 190; srect chart 0 434 1122 2 190; srect chart 0 630 1122 3 20
    grid=1; while [ "$grid" -le 3 ]; do gy=$((630-590*grid/3)); gl=$((scale*grid/3)); stext chart R 20 7 $((gy-26)) left 0 "${gl}分"; grid=$((grid+1)); done
    mon=1; cy="$(date +%Y)"; cm="$(date +%m | sed 's/^0//')"
    for mins in "$@"; do x=$((7+(mon-1)*94)); bh=$((mins*590/scale)); [ "$mins" -gt 0 ] && [ "$bh" -lt 8 ] && bh=8; color=125; [ "$view_year" = "$cy" ] && [ "$mon" -eq "$cm" ] && color=0; [ "$bh" -gt 0 ] && srect chart "$x" $((630-bh)) 48 "$bh" "$color"; stext chart B 24 $((x+24)) 650 center 0 "${mon}月"; [ "$mins" -gt 0 ] && stext chart B 22 $((x+24)) $((630-bh-34)) center 0 "$mins"; mon=$((mon+1)); done
    swrite chart; run_renderer || return 1
    pgm_valid "$a" 1102 180 && pgm_valid "$b" 272 70 && pgm_valid "$c" 1122 690 || return 1
    mv "$a" "$SESSION_DIR/total-summary.pgm" && mv "$b" "$SESSION_DIR/total-year.pgm" && mv "$c" "$SESSION_DIR/total-chart.pgm" || return 1
    image "$SESSION_DIR/total-summary.pgm" 85 380 1102 180 && image "$SESSION_DIR/total-year.pgm" 500 650 272 70 && image "$SESSION_DIR/total-chart.pgm" 75 760 1122 690
}

prepare_daily_view() { selected_date="$(printf '%04d-%02d-%02d' "$daily_y" "$daily_m" "$selected_day")"; awk -F '\t' -v d="$selected_date" '$1==d{print $2 "\t" $3}' "$DAY_BOOKS" | sort -nr | head -3 > "$SESSION_DIR/daily-view.tsv"; }

render_daily() {
    with_labels="$1"; dim="$(days_in_month "$daily_y" "$daily_m")"; offset="$(weekday_offset "$daily_y" "$daily_m")"
    rows=$(((offset+dim+6)/7)); cell_h=$((576/rows))
    set -- $(awk -F '\t' -v y="$daily_y" -v m="$daily_m" -v n="$dim" 'BEGIN{for(i=1;i<=n;i++)v[i]=0}$1~sprintf("^%04d-%02d-",y,m){d=substr($1,9,2)+0;v[d]+=$2}END{for(i=1;i<=n;i++)printf "%d%s",v[i]+0,(i<n?" ":"\n")}' "$DAYS")
    a="$SESSION_DIR/daily-calendar.pgm.new"; b="$SESSION_DIR/daily-detail.pgm.new"; : > "$SPEC"; canvas calendar 1122 650 "$a"
    day=1; month_read_days=0; month_total=0; day_total=0
    for sec in "$@"; do
        idx=$((offset+day-1)); row=$((idx/7)); col=$((idx%7)); x=$((col*160)); y=$((row*cell_h))
        [ "$sec" -gt 0 ] && month_read_days=$((month_read_days+1)); month_total=$((month_total+sec))
        # Whole rectangular cell is interactive; blank leading/trailing slots are not.
        srect calendar "$x" "$y" 154 $((cell_h-6)) 20
        ink=0
        if [ "$day" -eq "$selected_day" ]; then day_total="$sec"; ink=255
        else srect calendar $((x+2)) $((y+2)) 150 $((cell_h-10)) 255; fi
        stext calendar B 36 $((x+77)) $((y+10)) center "$ink" "$day"
        [ "$sec" -gt 0 ] && stext calendar R 24 $((x+77)) $((y+cell_h-39)) center "$ink" "$(calendar_time "$sec")"
        day=$((day+1))
    done
    srect calendar 0 590 1122 2 190
    stext calendar R 27 20 612 left 0 "本月阅读 ${month_read_days} 天  共 $(minute_text "$month_total")"
    swrite calendar; prepare_daily_view
    canvas detail 1132 420 "$b"; stext detail B 34 20 5 left 0 "${daily_m}月${selected_day}日 阅读详情"
    if [ "$day_total" -gt 0 ]; then
        stext detail B 36 20 60 left 0 "共 $(time_text "$day_total")"; line=0
        while IFS="$(printf '\t')" read -r book_sec book_title; do
            [ -n "$book_title" ] || continue
            stext detail R 24 1100 $((135+line*96)) right 0 "$(time_text "$book_sec")"; line=$((line+1))
        done < "$SESSION_DIR/daily-view.tsv"
    else stext detail R 34 20 100 left 0 "当日无阅读记录"; fi
    swrite detail; run_renderer || return 1
    pgm_valid "$a" 1122 650 && pgm_valid "$b" 1132 420 || return 1
    mv "$a" "$SESSION_DIR/daily-calendar.pgm" && mv "$b" "$SESSION_DIR/daily-detail.pgm" || return 1
    image "$SESSION_DIR/daily-calendar.pgm" 75 460 1122 650 && image "$SESSION_DIR/daily-detail.pgm" 70 1150 1132 420 || return 1
    if [ "$with_labels" = 1 ]; then
        rect 320 450 372 80 WHITE && ot 44 342 480 460 BOLD "${daily_y}年${daily_m}月" || return 1
    fi
    lua "$TITLE_LAYOUT" "$SESSION_DIR/daily-view.tsv" 800 40 0 96 > "$SESSION_DIR/daily-titles.tsv" || return 1
    while IFS="$(printf '\t')" read -r title_y title_line; do
        [ -n "$title_line" ] || continue
        ot 40 "$((1280+title_y))" 90 360 REGULAR "$title_line" || return 1
    done < "$SESSION_DIR/daily-titles.tsv"
}

book_pages() { count="$(awk 'NF{n++}END{print n+0}' "$BOOKS")"; pages=$(((count+4)/5)); [ "$pages" -gt 0 ] || pages=1; echo "$pages"; }
prepare_book_view() { start=$(((book_page-1)*5+1)); awk -v a="$start" -v b="$((start+4))" 'NR>=a&&NR<=b' "$BOOKS" > "$SESSION_DIR/book-view.tsv"; }

render_books() {
    ensure_progress; pages="$(book_pages)"; [ "$book_page" -gt "$pages" ] && book_page="$pages"; prepare_book_view
    a="$SESSION_DIR/books-content.pgm.new"; b="$SESSION_DIR/books-page.pgm.new"; : > "$SPEC"; canvas books 1132 1080 "$a"
    srect books 25 217 1082 2 190; srect books 25 434 1082 2 190; srect books 25 651 1082 2 190; srect books 25 868 1082 2 190
    row=0; while IFS="$(printf '\t')" read -r sec title id index; do
        [ -n "$title" ] || continue; y=$((15+row*217)); stext books R 27 35 $((y+126)) left 0 "阅读 $(time_text "$sec")"; progress=""; [ -f "$PROGRESS" ] && progress="$(awk -F '\t' -v t="$title" '$2==t{print $1;exit}' "$PROGRESS")"; case "$progress" in ''|*[!0-9]*) progress="";;esac
        if [ -n "$progress" ]; then [ "$progress" -gt 100 ] && progress=100; stext books R 24 1090 $((y+126)) right 0 "${progress}%"; srect books 35 $((y+164)) 1030 20 185; [ "$progress" -gt 0 ] && srect books 35 $((y+164)) $((1030*progress/100)) 20 0; else stext books R 24 815 $((y+126)) left 0 "暂无进度"; fi; row=$((row+1))
    done < "$SESSION_DIR/book-view.tsv"
    swrite books; canvas page 452 60 "$b"; stext page B 30 226 10 center 0 "第 ${book_page} 页，共 ${pages} 页"; swrite page; run_renderer || return 1
    pgm_valid "$a" 1132 1080 && pgm_valid "$b" 452 60 || return 1; mv "$a" "$SESSION_DIR/books-content.pgm" && mv "$b" "$SESSION_DIR/books-page.pgm" || return 1
    image "$SESSION_DIR/books-content.pgm" 70 345 1132 1080 && image "$SESSION_DIR/books-page.pgm" 410 1480 452 60 || return 1
    number=$(((book_page-1)*5+1))
    lua "$TITLE_LAYOUT" "$SESSION_DIR/book-view.tsv" 1020 44 "$number" 217 > "$SESSION_DIR/book-titles.tsv" || return 1
    while IFS="$(printf '\t')" read -r title_y title_line; do
        [ -n "$title_line" ] || continue
        ot 44 "$((375+title_y))" 100 120 BOLD "$title_line" || return 1
    done < "$SESSION_DIR/book-titles.tsv"
}

draw_background() { image "$UI_DIR/${mode}.png" 0 0 1272 1696; }
draw_dynamic() { case "$mode" in total) render_total;; daily) render_daily "$1";; books) render_books;; esac; }

draw_count=0; refresh_kind=none
refresh_region() {
    rx="$1"; ry="$2"; rw="$3"; rh="$4"; draw_count=$((draw_count+1))
    if [ "$draw_count" -eq 1 ] || [ $((draw_count%CLEAN_REFRESH_INTERVAL)) -eq 0 ]; then fb -q -f -W GC16 -s; refresh_kind=GC16
    else px="$(scale_x "$rx")"; py="$(scale_y "$ry")"; pw="$(scale_len "$rw")"; ph="$(scale_len "$rh")"; fb -q -W GC16_FAST -s "top=$py,left=$px,width=$pw,height=$ph" || fb -q -W GC16 -s "top=$py,left=$px,width=$pw,height=$ph"; refresh_kind=GC16_FAST; fi
}

dashboard_active=0
remove_session() { case "$SESSION_DIR" in /tmp/native-reading-dashboard.[0-9]*) rm -rf "$SESSION_DIR";; esac; }
cleanup() {
    lipc-set-prop com.lab126.winmgr eatTapMode 0 >/dev/null 2>&1 || true; lipc-set-prop com.lab126.powerd preventScreenSaver 0 >/dev/null 2>&1 || true; remove_session
    if [ "$dashboard_active" -eq 1 ]; then lipc-set-prop com.lab126.appmgrd start 'app://com.lab126.KPPMainApp?view=KPP_LIBRARY' >/dev/null 2>&1 || true; sleep 1; "$FBINK" -q -f -W GC16 -s >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT INT TERM HUP

fallback_to_legacy() {
    echo "$(date): renderer failed; switching to byte-preserved 9.6.3 dashboard"
    lipc-set-prop com.lab126.system toasterMessage "优化渲染异常，已切换兼容模式" >/dev/null 2>&1 || true
    metric_end legacy 1 1; remove_session; trap - EXIT INT TERM HUP
    exec /bin/sh "$LEGACY"
    trap cleanup EXIT INT TERM HUP; fail "无法启动原始 9.6.3 后备界面"
}

perform_draw() {
    op="$1"; background="$2"; labels="$3"; rx="$4"; ry="$5"; rw="$6"; rh="$7"; metric_begin "$op"
    [ "$background" = 1 ] && draw_background || [ "$background" = 0 ] || fallback_to_legacy
    draw_dynamic "$labels" || fallback_to_legacy
    refresh_region "$rx" "$ry" "$rw" "$rh"; metric_end optimized 0 1
}

detect_screen; find_touch_device
mkdir -p "$SESSION_DIR" || fail "无法创建阅读记录会话缓存"; chmod 700 "$SESSION_DIR" 2>/dev/null || true
[ -x "$FBINK" ] || fail "未找到 Véra/KPM 系统级 FBInk"; [ -f "$UI_DIR/total.png" ] || fail "缺少优化版界面资源"; [ -f "$DATA" ] || fail "尚无阅读统计数据"; [ -r "$TOUCH" ] || fail "无法读取触摸设备"; [ -f "$TOUCH_READER" ] || fail "缺少安全触摸监听器"; [ -f "$LEGACY" ] || fail "缺少原始 9.6.3 后备界面"; command -v lua >/dev/null 2>&1 || fail "未找到 Lua 运行环境"
RFONT="$BASE/fonts/NotoSansCJKsc-Regular.otf"; [ -f "$RFONT" ] || fail "缺少阅读记录中文字体"
printf 'screen=%sx%s\nviewport=%sx%s+%s+%s\nlogical=%sx%s\ntouch=%s\nrelease=9.6.4-ui-calendar\n' "$SCREEN_W" "$SCREEN_H" "$VIEW_W" "$VIEW_H" "$ORIGIN_X" "$ORIGIN_Y" "$LOGICAL_W" "$LOGICAL_H" "$TOUCH" > "$BASE/display-layout.txt"
echo "$(date): screen=${SCREEN_W}x${SCREEN_H}, viewport=${VIEW_W}x${VIEW_H}+${ORIGIN_X}+${ORIGIN_Y}, renderer=$renderer_available"
lipc-set-prop com.lab126.winmgr eatTapMode 0 >/dev/null 2>&1 || true; lipc-set-prop com.lab126.powerd preventScreenSaver 1 >/dev/null 2>&1 || true; dashboard_active=1

mode=daily; view_year="$(date +%Y)"; daily_y="$(date +%Y)"; daily_m="$(date +%m | sed 's/^0//')"; selected_day="$(date +%d | sed 's/^0//')"; book_page=1
metric_begin first_open; build_cache || fallback_to_legacy; draw_background || fallback_to_legacy; draw_dynamic 1 || fallback_to_legacy; refresh_region 0 0 1272 1696; metric_end optimized 0 1

while :; do
    offset="$(weekday_offset "$daily_y" "$daily_m")"; dim="$(days_in_month "$daily_y" "$daily_m")"
    action="$(lua "$TOUCH_READER" "$TOUCH" "$BASE/dashboard-touch.log" "$mode" "$offset" "$dim" "$ORIGIN_X" "$ORIGIN_Y" "$VIEW_W" "$VIEW_H")" || action=exit
    echo "$(date): dashboard action=$action mode=$mode"
    case "$action" in
      exit) break;;
      tab_total) if [ "$mode" = total ]; then metric_begin tab_total_noop; metric_end none 0 0; else mode=total; perform_draw tab_to_total 1 1 0 0 1272 1696; fi;;
      tab_daily) if [ "$mode" = daily ]; then metric_begin tab_daily_noop; metric_end none 0 0; else mode=daily; perform_draw tab_to_daily 1 1 0 0 1272 1696; fi;;
      tab_books) if [ "$mode" = books ]; then metric_begin tab_books_noop; metric_end none 0 0; else mode=books; perform_draw tab_to_books 1 1 0 0 1272 1696; fi;;
      year_prev) view_year=$((view_year-1)); perform_draw year_previous 0 0 55 380 1162 1070;;
      year_next) view_year=$((view_year+1)); perform_draw year_next 0 0 55 380 1162 1070;;
      month_prev) shift_month -1; perform_draw month_previous 0 1 55 320 1162 1250;;
      month_next) shift_month 1; perform_draw month_next 0 1 55 320 1162 1250;;
      day_*) new_day="${action#day_}"; if [ "$new_day" = "$selected_day" ]; then metric_begin date_noop; metric_end none 0 0; else selected_day="$new_day"; perform_draw date_select 0 0 55 460 1162 1110; fi;;
      page_prev) if [ "$book_page" -gt 1 ]; then book_page=$((book_page-1)); perform_draw book_page_previous 0 0 70 345 1132 1215; else metric_begin page_previous_noop; metric_end none 0 0; fi;;
      page_next) pages="$(book_pages)"; if [ "$book_page" -lt "$pages" ]; then book_page=$((book_page+1)); perform_draw book_page_next 0 0 70 345 1132 1215; else metric_begin page_next_noop; metric_end none 0 0; fi;;
      *) metric_begin unknown_action; metric_end none 0 0;;
    esac
done

echo "$(date): optimized dashboard closed"
exit 0
