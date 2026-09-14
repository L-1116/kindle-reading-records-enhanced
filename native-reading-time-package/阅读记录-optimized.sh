#!/bin/sh
# Name: 阅读记录
# Author: Kindle Reading Records Enhanced
# Icon: /mnt/us/reading-time/assets/launcher-icon.png

# Kindle 原生阅读记录 9.7.4.  This process exists only while the
# dashboard is open.  The tracker daemon and reading-time.tsv are untouched.
BASE="/mnt/us/reading-time"
DATA="$BASE/reading-time.tsv"
LOG="$BASE/dashboard-launch.log"
FBINK="/var/local/kmc/bin/fbink"
RELEASE="$BASE/releases/9.7.4"
UI_DIR="$RELEASE/ui-calendar"
TOUCH_READER="$RELEASE/bin/reading-insights-touch-ui.lua"
RENDERER="$RELEASE/bin/reading-insights-render.lua"
RENDER_ASSETS="$RELEASE/render-assets"
CACHE_BUILDER="$RELEASE/bin/reading-insights-cache.awk"
LEGACY="$RELEASE/bin/reading-records-v9.6.3.sh"
TITLE_LAYOUT="$RELEASE/bin/reading-insights-titles.lua"
CC_DB="/var/local/cc.db"
COVER_CACHE="$BASE/book-cover-cache.tsv"
SESSION_DIR="/tmp/native-reading-dashboard.$$"
SUMMARY="$SESSION_DIR/summary.tsv"; MONTHS="$SESSION_DIR/months.tsv"; WEEKS="$SESSION_DIR/weeks.tsv"
DAYS="$SESSION_DIR/days.tsv"; DAY_BOOKS="$SESSION_DIR/day-books.tsv"; CALENDAR="$SESSION_DIR/calendar.tsv"
BOOKS="$SESSION_DIR/books.tsv"; BOOKS_7D="$SESSION_DIR/books-7d.tsv"
BOOKS_MONTH="$SESSION_DIR/books-month.tsv"; BOOKS_YEAR="$SESSION_DIR/books-year.tsv"
PROGRESS_DB="$SESSION_DIR/cc-progress-viewer.db"
CATALOG="$SESSION_DIR/book-catalog.tsv"; PROGRESS="$SESSION_DIR/book-progress.tsv"; SPEC="$SESSION_DIR/render-spec.tsv"
TOTAL_VALUES="$SESSION_DIR/total-values.tsv"; WEEK_VIEW="$SESSION_DIR/week-view.tsv"
DAY_DETAIL_ALL="$SESSION_DIR/day-detail-all.tsv"; DAY_DETAIL_VIEW="$SESSION_DIR/day-detail-view.tsv"
PERIOD_SUMMARY="$SESSION_DIR/period-summary.tsv"; PERIOD_DAILY="$SESSION_DIR/period-daily.tsv"
PERIOD_BOOKS="$SESSION_DIR/period-books.tsv"; MONTH_VALUES="$SESSION_DIR/month-values.tsv"
MONTH_TOP="$SESSION_DIR/month-top.tsv"; WEEK_TREND_VALUES="$SESSION_DIR/week-trend-values.tsv"
BOOK_DETAIL_SUMMARY="$SESSION_DIR/book-detail-summary.tsv"; BOOK_DETAIL_DAILY="$SESSION_DIR/book-detail-daily.tsv"
BOOK_DETAIL_TITLE="$SESSION_DIR/book-detail-title.tsv"; BOOK_DETAIL_TITLE_LAYOUT="$SESSION_DIR/book-detail-title-layout.tsv"
LOGICAL_W=1272; LOGICAL_H=1696; CLEAN_REFRESH_INTERVAL=6
CALENDAR_GRID_H=648; DETAIL_TOP=1222; DETAIL_H=406
DETAIL_ROWS_Y=65; DETAIL_ROW_H=96; DETAIL_PAGER_H=52
DAY_DETAIL_SUMMARY_TOP=205; DAY_DETAIL_SUMMARY_H=300
DAY_DETAIL_LIST_TOP=590; DAY_DETAIL_LIST_H=1035
DAY_DETAIL_ROWS_Y=100; DAY_DETAIL_ROW_H=275; DAY_DETAIL_PAGER_Y=930
MONTH_SUMMARY_TOP=205; MONTH_SUMMARY_H=450; MONTH_BODY_TOP=715; MONTH_BODY_H=900
WEEK_TREND_SUMMARY_TOP=205; WEEK_TREND_SUMMARY_H=420; WEEK_TREND_CHART_TOP=695; WEEK_TREND_CHART_H=920
BOOK_DETAIL_SUMMARY_TOP=205; BOOK_DETAIL_SUMMARY_H=500; BOOK_DETAIL_CHART_TOP=765; BOOK_DETAIL_CHART_H=860
BOOK_ROW_H=360; BOOK_PAGE_SIZE=3
COVER_BOOK_W=190; COVER_BOOK_H=285; COVER_DAY_W=140; COVER_DAY_H=210; COVER_DETAIL_W=200; COVER_DETAIL_H=300

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
chart_time_text() { cht_m="$1"; cht_h=$((cht_m/60)); cht_r=$((cht_m%60)); if [ "$cht_h" -eq 0 ]; then printf '%smin' "$cht_r"; elif [ "$cht_r" -eq 0 ]; then printf '%sh' "$cht_h"; else printf '%sh%smin' "$cht_h" "$cht_r"; fi; }
summary_time_text() { if [ "$1" -gt 0 ]; then time_text "$1"; else printf '0分钟'; fi; }
signed_time_text() { st_v="$1"; if [ "$st_v" -gt 0 ]; then printf '+'; time_text "$st_v"; elif [ "$st_v" -lt 0 ]; then printf '-'; time_text "$((-st_v))"; else printf '0分钟'; fi; }
calendar_time() { ct_s="$1"; ct_m=$((ct_s/60)); if [ "$ct_s" -le 0 ]; then return; elif [ "$ct_m" -eq 0 ]; then printf '%s秒' "$ct_s"; elif [ "$ct_m" -lt 60 ]; then printf '%s分' "$ct_m"; else printf '%s时%s分' "$((ct_m/60))" "$((ct_m%60))"; fi; }
calendar_heat_level() {
    ch_s="${1:-0}"
    if [ "$ch_s" -le 0 ]; then echo 0
    elif [ "$ch_s" -lt 1800 ]; then echo 1
    elif [ "$ch_s" -lt 3600 ]; then echo 2
    elif [ "$ch_s" -lt 7200 ]; then echo 3
    elif [ "$ch_s" -lt 10800 ]; then echo 4
    elif [ "$ch_s" -lt 14400 ]; then echo 5
    else echo 6
    fi
}
calendar_heat_gray() {
    case "$1" in 0) echo 255;; 1) echo 235;; 2) echo 210;; 3) echo 180;; 4) echo 145;; 5) echo 105;; 6) echo 70;; *) return 1;; esac
}
calendar_heat_ink() {
    case "$1" in 0|1|2|3|4) echo 0;; 5|6) echo 255;; *) return 1;; esac
}
days_in_month() { case "$2" in 1|3|5|7|8|10|12) echo 31;;4|6|9|11) echo 30;;2) if { [ $(($1%400)) -eq 0 ] || { [ $(($1%4)) -eq 0 ] && [ $(($1%100)) -ne 0 ]; }; }; then echo 29; else echo 28; fi;;esac; }
weekday_offset() { awk -v y="$1" -v m="$2" 'BEGIN{if(m<3){m+=12;y--}k=y%100;j=int(y/100);h=(1+int(13*(m+1)/5)+k+int(k/4)+int(j/4)+5*j)%7;print(h+5)%7}'; }
civil_date() {
    awk -v day="$1" 'BEGIN{
        l=day+68569; n=int(4*l/146097); l=l-int((146097*n+3)/4)
        i=int(4000*(l+1)/1461001); l=l-int(1461*i/4)+31
        j=int(80*l/2447); d=l-int(2447*j/80); l=int(j/11)
        m=j+2-12*l; y=100*(n-49)+i+l
        printf "%04d-%02d-%02d\n",y,m,d
    }'
}
date_parts() {
    parsed_date="$1"; parsed_y="${parsed_date%%-*}"; parsed_md="${parsed_date#*-}"
    parsed_m="${parsed_md%%-*}"; parsed_d="${parsed_date##*-}"
    parsed_m="${parsed_m#0}"; parsed_d="${parsed_d#0}"
}
valid_date() {
    case "$1" in ????-??-??) :;; *) return 1;; esac
    date_parts "$1"
    case "$parsed_y:$parsed_m:$parsed_d" in *[!0-9:]*) return 1;; esac
    [ "$parsed_y" -ge 1 ] && [ "$parsed_m" -ge 1 ] && [ "$parsed_m" -le 12 ] || return 1
    parsed_dim="$(days_in_month "$parsed_y" "$parsed_m")"
    [ "$parsed_d" -ge 1 ] && [ "$parsed_d" -le "$parsed_dim" ]
}
set_selected_date() { valid_date "$1" || return 1; selected_date="$(printf '%04d-%02d-%02d' "$parsed_y" "$parsed_m" "$parsed_d")"; }
shift_month() {
    daily_m=$((daily_m+$1))
    while [ "$daily_m" -lt 1 ]; do daily_m=$((daily_m+12)); daily_y=$((daily_y-1)); done
    while [ "$daily_m" -gt 12 ]; do daily_m=$((daily_m-12)); daily_y=$((daily_y+1)); done
    set_selected_date "$(printf '%04d-%02d-01' "$daily_y" "$daily_m")" || return 1
    detail_page=1
}

uptime_ms() { awk '{printf "%d\n",$1*1000}' /proc/uptime 2>/dev/null; }
metric_begin() { metric_name="$1"; metric_start="$(uptime_ms)"; case "$metric_start" in ''|*[!0-9]*) metric_start=0;;esac; metric_fb_start="$fbink_calls"; }
metric_end() { e="$(uptime_ms)"; case "$e" in ''|*[!0-9]*) e="$metric_start";;esac; echo "METRIC operation=$metric_name elapsed_ms=$((e-metric_start)) fbink_calls=$((fbink_calls-metric_fb_start)) renderer=$1 fallback=$2 redraw=$3"; }

cache_ok=0
build_cache() {
    today_date="$(date +%Y-%m-%d)"
    valid_date "$today_date" || return 1
    : > "$SUMMARY" && : > "$MONTHS" && : > "$DAYS" && : > "$DAY_BOOKS" && : > "$BOOKS.raw" && : > "$WEEKS.raw" && : > "$CALENDAR" || return 1
    for range in 7d month year; do : > "$SESSION_DIR/books-$range.raw" || return 1; done
    awk -F '\t' -v today="$today_date" -v calendar="$CALENDAR" -v summary="$SUMMARY" -v months="$MONTHS" -v weeks="$WEEKS.raw" -v days="$DAYS" -v daybooks="$DAY_BOOKS" -v books="$BOOKS.raw" -v books7="$SESSION_DIR/books-7d.raw" -v booksmonth="$SESSION_DIR/books-month.raw" -v booksyear="$SESSION_DIR/books-year.raw" -f "$CACHE_BUILDER" "$DATA" || return 1
    sort "$MONTHS" > "$MONTHS.sorted" && sort -n "$WEEKS.raw" > "$WEEKS" && sort "$DAYS" > "$DAYS.sorted" && sort "$DAY_BOOKS" > "$DAY_BOOKS.sorted" && sort -nr "$BOOKS.raw" > "$BOOKS" || return 1
    mv "$MONTHS.sorted" "$MONTHS" && mv "$DAYS.sorted" "$DAYS" && mv "$DAY_BOOKS.sorted" "$DAY_BOOKS" || return 1
    for range in 7d month year; do awk -F '\t' '$1 >= 300' "$SESSION_DIR/books-$range.raw" | sort -nr > "$SESSION_DIR/books-$range.tsv" || return 1; done
    rm -f "$BOOKS.raw" "$WEEKS.raw" "$SESSION_DIR"/books-*.raw; cache_ok=1
}

catalog_loaded=0; progress_loaded=0
ensure_catalog() {
    [ "$catalog_loaded" -eq 0 ] || return 0
    catalog_loaded=1; rm -f "$PROGRESS_DB" "$CATALOG" "$CATALOG.new" "$PROGRESS.new"
    [ "${progress_loaded:-0}" -eq 1 ] || rm -f "$PROGRESS"
    if command -v sqlite3 >/dev/null 2>&1 && [ -r "$CC_DB" ] && cp "$CC_DB" "$PROGRESS_DB" 2>/dev/null; then
        if [ "${progress_loaded:-0}" -ne 1 ]; then
            sqlite3 -readonly -separator "$(printf '\t')" "$PROGRESS_DB" "SELECT CAST(p_percentFinished + 0.5 AS INTEGER),replace(replace(COALESCE(p_titles_0_nominal,''),char(9),' '),char(10),' '),replace(replace(COALESCE(p_cdeKey,''),char(9),' '),char(10),' ') FROM Entries WHERE p_percentFinished>=0 AND p_percentFinished<=100 AND (p_titles_0_nominal IS NOT NULL OR p_cdeKey IS NOT NULL) ORDER BY p_lastAccess DESC;" > "$PROGRESS.new" 2>/dev/null || true
            [ -s "$PROGRESS.new" ] && mv "$PROGRESS.new" "$PROGRESS"
        fi
        sqlite3 -readonly -separator "$(printf '\t')" "$PROGRESS_DB" "SELECT -1,replace(replace(COALESCE(p_titles_0_nominal,''),char(9),' '),char(10),' '),replace(replace(COALESCE(p_cdeKey,''),char(9),' '),char(10),' '),replace(replace(COALESCE(p_thumbnail,''),char(9),' '),char(10),' ') FROM Entries WHERE p_cdeKey IS NOT NULL ORDER BY p_lastAccess DESC;" > "$CATALOG.new" 2>/dev/null || true
        [ -s "$CATALOG.new" ] && mv "$CATALOG.new" "$CATALOG"
    fi
    rm -f "$PROGRESS_DB" "$CATALOG.new" "$PROGRESS.new"
}

ensure_progress() { [ "${progress_loaded:-0}" -eq 1 ] && return 0; ensure_catalog; progress_loaded=1; }

progress_for_book() {
    [ -f "$PROGRESS" ] || return 0
    awk -F '\t' -v t="$1" -v id="$2" '
        id!="" && id!="unknown" && $3==id { print $1; found=1; exit }
        $2==t && fallback=="" { fallback=$1 }
        END { if(!found && fallback!="") print fallback }
    ' "$PROGRESS"
}

cover_path_allowed() {
    case "$1" in /mnt/us/system/thumbnails/*|/mnt/us/system/bookcovers/*) [ -f "$1" ];; *) return 1;; esac
}

cover_cache_lookup() {
    [ -r "$COVER_CACHE" ] || return 0
    awk -F '\t' -v id="$1" '$1==id{print substr($0,index($0,"\t")+1);exit}' "$COVER_CACHE"
}

cover_cache_forget() {
    [ -f "$COVER_CACHE" ] || return 0
    cover_tmp="$COVER_CACHE.new.$$"
    awk -F '\t' -v id="$1" '$1!=id' "$COVER_CACHE" > "$cover_tmp" && mv "$cover_tmp" "$COVER_CACHE"
}

cover_cache_remember() {
    cover_id="$1"; cover_path="$2"
    [ -n "$cover_id" ] && [ "$cover_id" != unknown ] && cover_path_allowed "$cover_path" || return 1
    cover_tmp="$COVER_CACHE.new.$$"
    if [ -r "$COVER_CACHE" ]; then awk -F '\t' -v id="$cover_id" '$1!=id' "$COVER_CACHE" > "$cover_tmp" || return 1; else : > "$cover_tmp" || return 1; fi
    printf '%s\t%s\n' "$cover_id" "$cover_path" >> "$cover_tmp" || { rm -f "$cover_tmp"; return 1; }
    chmod 600 "$cover_tmp" 2>/dev/null || true
    mv "$cover_tmp" "$COVER_CACHE"
}

# The only cover lookup entry point. Persistent last-known-good mapping comes
# first; cc.db is snapshotted at most once per dashboard session; a known EBOK
# filename is the sole path fallback. No thumbnail directory is ever scanned.
resolveBookCover() {
    resolve_id="$1"
    [ -n "$resolve_id" ] && [ "$resolve_id" != unknown ] || return 1
    resolve_path="$(cover_cache_lookup "$resolve_id")"
    if [ -n "$resolve_path" ]; then
        if cover_path_allowed "$resolve_path"; then printf '%s\n' "$resolve_path"; return 0; fi
        cover_cache_forget "$resolve_id" || true
    fi
    ensure_catalog
    if [ -r "$CATALOG" ]; then
        resolve_path="$(awk -F '\t' -v id="$resolve_id" '$3==id&&$4!=""{print $4;exit}' "$CATALOG")"
        if [ -n "$resolve_path" ] && cover_path_allowed "$resolve_path"; then
            cover_cache_remember "$resolve_id" "$resolve_path" || true
            printf '%s\n' "$resolve_path"; return 0
        fi
    fi
    case "$resolve_id" in *[!A-Za-z0-9_-]*|'') :;; *)
        resolve_path="/mnt/us/system/thumbnails/thumbnail_${resolve_id}_EBOK_portrait.jpg"
        if cover_path_allowed "$resolve_path"; then cover_cache_remember "$resolve_id" "$resolve_path" || true; printf '%s\n' "$resolve_path"; return 0; fi
    esac
    return 1
}

render_cover_placeholder() {
    cover_canvas="$1"; cover_x="$2"; cover_y="$3"; cover_w="$4"; cover_h="$5"
    srect "$cover_canvas" "$cover_x" "$cover_y" "$cover_w" "$cover_h" 35
    srect "$cover_canvas" $((cover_x+3)) $((cover_y+3)) $((cover_w-6)) $((cover_h-6)) 245
    stext "$cover_canvas" B 24 $((cover_x+cover_w/2)) $((cover_y+cover_h/2-34)) center 90 "暂无"
    stext "$cover_canvas" B 24 $((cover_x+cover_w/2)) $((cover_y+cover_h/2+4)) center 90 "封面"
}

renderBookCover() {
    render_cover_path="$(resolveBookCover "$1")" || return 0
    image "$render_cover_path" "$2" "$3" "$4" "$5"
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
slabel() { printf 'text\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t255\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" "$8" >> "$SPEC"; }
sfitlabel() { printf 'textfit\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t255\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" "$8" "$9" "${10}" >> "$SPEC"; }
swrite() { printf 'write\t%s\n' "$1" >> "$SPEC"; }

prepare_week_view() {
    awk -F '\t' -v today_day="$(cat "$CALENDAR")" -v offset="$week_offset" '
    function day_number(date,    y,m,d,a,yy,mm) {
        y=substr(date,1,4)+0; m=substr(date,6,2)+0; d=substr(date,9,2)+0
        a=int((14-m)/12); yy=y+4800-a; mm=m+12*a-3
        return d+int((153*mm+2)/5)+365*yy+int(yy/4)-int(yy/100)+int(yy/400)-32045
    }
    function civil(day,    l,n,i,j,d,m,y) {
        l=day+68569; n=int(4*l/146097); l=l-int((146097*n+3)/4)
        i=int(4000*(l+1)/1461001); l=l-int(1461*i/4)+31
        j=int(80*l/2447); d=l-int(2447*j/80); l=int(j/11)
        m=j+2-12*l; y=100*(n-49)+i+l
        return sprintf("%04d-%02d-%02d",y,m,d)
    }
    BEGIN { first=today_day-(today_day%7)+offset*7 }
    { day=day_number($1); if(offset<0 || day<=today_day) value[day]+=$2+0 }
    END { for(i=0;i<7;i++){ day=first+i; print civil(day) "\t" value[day]+0 "\t" (day==today_day?0:125) } }
    ' "$DAYS" > "$WEEK_VIEW"
}

prepare_total_values() {
    if [ "$total_period" = week ]; then
        prepare_week_view || return 1
        awk -F '\t' 'BEGIN{split("周一 周二 周三 周四 周五 周六 周日",label," ")}{print label[NR] "\t" int($2/60) "\t" $3}' "$WEEK_VIEW" > "$TOTAL_VALUES"
        first_date="$(awk -F '\t' 'NR==1{print $1}' "$WEEK_VIEW")"; last_date="$(awk -F '\t' 'END{print $1}' "$WEEK_VIEW")"
        first_md="${first_date#*-}"; first_m="${first_md%%-*}"; first_d="${first_md##*-}"
        last_md="${last_date#*-}"; last_m="${last_md%%-*}"; last_d="${last_md##*-}"
        first_m="${first_m#0}"; first_d="${first_d#0}"; last_m="${last_m#0}"; last_d="${last_d#0}"
        period_title="${first_m}月${first_d}日 - ${last_m}月${last_d}日"
    else
        cy="$(date +%Y)"; cm="$(date +%m | sed 's/^0//')"; chart_today="$(date +%Y-%m-%d)"
        awk -F '\t' -v y="$view_year" -v cy="$cy" -v cm="$cm" -v today="$chart_today" 'BEGIN{for(i=1;i<=12;i++)v[i]=0}substr($1,1,4)==y && (y<cy || $1<=today){m=substr($1,6,2)+0;v[m]+=$2}END{for(i=1;i<=12;i++)print i "月\t" int(v[i]/60) "\t" (y==cy&&i==cm?0:125)}' "$DAYS" > "$TOTAL_VALUES"
        period_title="${view_year}年"
    fi
}

prepare_period_summary() {
    if [ "$total_period" = week ]; then
        set -- $(awk -F '\t' '$2>0{total+=$2;days++}END{print total+0,days+0}' "$WEEK_VIEW")
    else
        summary_today="$(date +%Y-%m-%d)"
        set -- $(awk -F '\t' -v y="$view_year" -v today="$summary_today" 'substr($1,1,4)==y && (y<substr(today,1,4) || $1<=today) && $2>0{total+=$2;days++}END{print total+0,days+0}' "$DAYS")
    fi
    total="${1:-0}"; read_days="${2:-0}"
    [ "$read_days" -gt 0 ] && average=$(((total+read_days*30)/(read_days*60)*60)) || average=0
}

spec_toggle_button() {
    toggle_canvas="$1"; toggle_x="$2"; toggle_w="$3"; toggle_text="$4"; toggle_selected="$5"
    sround "$toggle_canvas" "$toggle_x" 2 "$toggle_w" 54 16 20
    if [ "$toggle_selected" -eq 1 ]; then toggle_ink=255; else sround "$toggle_canvas" $((toggle_x+2)) 4 $((toggle_w-4)) 50 14 255; toggle_ink=0; fi
    stext "$toggle_canvas" B 28 $((toggle_x+toggle_w/2)) 10 center "$toggle_ink" "$toggle_text"
}

render_total() {
    prepare_total_values || return 1
    prepare_period_summary || return 1
    max="$(awk -F '\t' '$2>m{m=$2}END{print m+0}' "$TOTAL_VALUES")"
    scale_hours=$(((max*112+5999)/6000)); [ "$scale_hours" -ge 1 ] || scale_hours=1; scale=$((scale_hours*60))
    if [ "$total_period" = week ]; then
        if [ "$scale_hours" -le 3 ]; then tick_hours=1; elif [ "$scale_hours" -le 8 ]; then tick_hours=2; elif [ "$scale_hours" -le 15 ]; then tick_hours=3; else tick_hours=5; fi
    else
        tick_hours="$(awk -v upper="$scale_hours" 'BEGIN{v=upper/5;p=1;while(v>=10){v/=10;p*=10}if(v<1.5)n=1;else if(v<3.5)n=2;else if(v<7.5)n=5;else n=10;print n*p}')"
    fi
    a="$SESSION_DIR/total-summary.pgm.new"; b="$SESSION_DIR/total-year.pgm.new"; c="$SESSION_DIR/total-chart.pgm.new"; d="$SESSION_DIR/total-toggle.pgm.new"; : > "$SPEC"
    canvas summary 1102 180 "$a"; srect summary 0 110 1102 2 190
    stext summary B 70 10 5 left 0 "$(summary_time_text "$total")"; stext summary B 32 40 137 left 0 "阅读天数  ${read_days}天"; stext summary B 32 645 137 left 0 "阅读日均  $(minute_text "$average")"; swrite summary
    canvas toggle 210 58 "$d"; [ "$total_period" = week ] && week_selected=1 || week_selected=0; [ "$total_period" = year ] && year_selected=1 || year_selected=0
    spec_toggle_button toggle 0 95 "本周" "$week_selected"; spec_toggle_button toggle 115 95 "今年" "$year_selected"; swrite toggle
    canvas year 360 70 "$b"; [ "$total_period" = week ] && title_size=30 || title_size=39; stext year B "$title_size" 180 10 center 0 "$period_title"; swrite year
    canvas chart 1122 690 "$c"
    # Reserve a measured Y-axis gutter and a separate safety gap before the
    # plot.  Bar centers are then derived uniformly from the remaining area.
    chart_w=1122; chart_base=630; chart_height=590; axis_text_left=7; axis_gap=28; right_margin=16; plot_right=$((chart_w-right_margin))
    set --; gl="$tick_hours"; while [ "$gl" -le "$scale_hours" ]; do set -- "$@" "${gl}h"; gl=$((gl+tick_hours)); done
    [ "$#" -gt 0 ] || set -- "${scale_hours}h"
    axis_label_w="$(lua "$RENDERER" "$RENDER_ASSETS" --measure R 20 "$@")" || return 1
    case "$axis_label_w" in ''|*[!0-9]*) return 1;; esac
    axis_text_right=$((axis_text_left+axis_label_w)); plot_left=$((axis_text_right+axis_gap)); plot_width=$((plot_right-plot_left))
    [ "$plot_width" -gt 0 ] || return 1
    srect chart "$plot_left" "$chart_base" "$plot_width" 3 20
    gl="$tick_hours"; while [ "$gl" -le "$scale_hours" ]; do gy=$((chart_base-chart_height*gl/scale_hours)); srect chart "$plot_left" "$gy" "$plot_width" 2 190; stext chart R 20 "$axis_text_right" $((gy-26)) right 0 "${gl}h"; gl=$((gl+tick_hours)); done
    count="$(awk 'NF{n++}END{print n+0}' "$TOTAL_VALUES")"; if [ "$count" -eq 7 ]; then bar_w=76; axis_size=24; else bar_w=48; axis_size=24; fi
    [ "$count" -gt 0 ] || return 1
    pos=0; while IFS="$(printf '\t')" read -r axis_label mins color; do
        center=$((plot_left+plot_width*(2*pos+1)/(2*count))); x=$((center-bar_w/2)); bh=$((mins*chart_height/scale)); [ "$mins" -gt 0 ] && [ "$bh" -lt 8 ] && bh=8
        [ "$bh" -gt 0 ] && srect chart "$x" $((chart_base-bh)) "$bar_w" "$bh" "$color"
        stext chart B "$axis_size" "$center" 650 center 0 "$axis_label"
        [ "$mins" -gt 0 ] && sfitlabel chart B 20 "$center" $((chart_base-bh-32)) center 0 "$(chart_time_text "$mins")" "$plot_left" "$plot_right"
        pos=$((pos+1))
    done < "$TOTAL_VALUES"
    swrite chart; run_renderer || return 1
    pgm_valid "$a" 1102 180 && pgm_valid "$b" 360 70 && pgm_valid "$c" 1122 690 && pgm_valid "$d" 210 58 || return 1
    mv "$a" "$SESSION_DIR/total-summary.pgm" && mv "$b" "$SESSION_DIR/total-year.pgm" && mv "$c" "$SESSION_DIR/total-chart.pgm" && mv "$d" "$SESSION_DIR/total-toggle.pgm" || return 1
    image "$SESSION_DIR/total-summary.pgm" 85 380 1102 180 && image "$SESSION_DIR/total-toggle.pgm" 65 638 210 58 && image "$SESSION_DIR/total-year.pgm" 456 650 360 70 && image "$SESSION_DIR/total-chart.pgm" 75 760 1122 690
}

# Reusable on-demand interval aggregation.  It reads the launch-time caches
# once each, never the raw log.  Callers that do not display books may pass 0
# as the third argument and avoid even reading DAY_BOOKS.
get_period_stats() {
    period_start="$1"; period_end="$2"; period_need_books="${3:-1}"
    valid_date "$period_start" || return 1; valid_date "$period_end" || return 1
    awk -v s="$period_start" -v e="$period_end" 'BEGIN{exit !(s<=e)}' || return 1
    : > "$PERIOD_SUMMARY" && : > "$PERIOD_DAILY" && : > "$PERIOD_BOOKS.raw" && : > "$PERIOD_BOOKS" || return 1
    set -- "$DAYS"
    [ "$period_need_books" = 1 ] && set -- "$DAYS" phase=books "$DAY_BOOKS"
    awk -F '\t' -v start="$period_start" -v finish="$period_end" -v need_books="$period_need_books" \
        -v summary="$PERIOD_SUMMARY" -v daily="$PERIOD_DAILY" -v books="$PERIOD_BOOKS.raw" '
        phase!="books" && $1>=start && $1<=finish {
            seconds=$2+0
            print $1 "\t" seconds > daily
            if(seconds>0) {
                total+=seconds; days++
                if(peak_date=="" || seconds>peak || (seconds==peak && $1<peak_date)) {
                    peak=seconds; peak_date=$1
                }
            }
            next
        }
        phase=="books" && need_books && $1>=start && $1<=finish && $2>0 {
            book[$3]+=$2+0
        }
        END {
            count=0
            if(need_books) for(title in book) if(book[title]>0) {
                count++; print book[title] "\t" title > books
            }
            average=(days>0 ? int((total+days*30)/(days*60))*60 : 0)
            if(peak_date=="") peak_date="-"
            print total+0 "\t" days+0 "\t" average+0 "\t" count+0 "\t" peak_date "\t" peak+0 > summary
        }
    ' "$@" || return 1
    if [ "$period_need_books" = 1 ]; then LC_ALL=C sort -nr "$PERIOD_BOOKS.raw" > "$PERIOD_BOOKS" || return 1; fi
    rm -f "$PERIOD_BOOKS.raw"
    IFS="$(printf '\t')" read -r period_total period_read_days period_average period_book_count period_peak_date period_peak_seconds < "$PERIOD_SUMMARY" || return 1
}

# Unified lazy per-book boundary. One pass over the launch-time DAY_BOOKS
# cache produces every summary value. Month heatmap buckets are prepared only
# for the visible month; the raw reading-time.tsv is intentionally untouched.
get_book_detail() {
    book_detail_book_no="$1"; book_detail_title="$2"; book_detail_id="$3"
    case "$book_detail_book_no" in ''|*[!0-9]*) return 1;; esac
    [ "$book_detail_book_no" -gt 0 ] && [ -n "$book_detail_title" ] || return 1
    book_detail_today_day="$(cat "$CALENDAR")"; case "$book_detail_today_day" in ''|*[!0-9]*) return 1;; esac
    : > "$BOOK_DETAIL_SUMMARY" && : > "$BOOK_DETAIL_DAILY" || return 1
    awk -F '\t' -v target="$book_detail_book_no" -v today_day="$book_detail_today_day" -v today="$today_date" \
        -v summary="$BOOK_DETAIL_SUMMARY" '
        function day_number(date,    y,m,d,a,yy,mm) {
            if(date !~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$/) return -1
            y=substr(date,1,4)+0;m=substr(date,6,2)+0;d=substr(date,9,2)+0
            if(m<1||m>12||d<1||d>31)return -1
            a=int((14-m)/12);yy=y+4800-a;mm=m+12*a-3
            return d+int((153*mm+2)/5)+365*yy+int(yy/4)-int(yy/100)+int(yy/400)-32045
        }
        function civil(day,    l,n,i,j,d,m,y) {
            l=day+68569;n=int(4*l/146097);l=l-int((146097*n+3)/4)
            i=int(4000*(l+1)/1461001);l=l-int(1461*i/4)+31
            j=int(80*l/2447);d=l-int(2447*j/80);l=int(j/11)
            m=j+2-12*l;y=100*(n-49)+i+l
            return sprintf("%04d-%02d-%02d",y,m,d)
        }
        BEGIN { month=substr(today,1,7) }
        ($5+0)==target {
            seconds=$2+0; date=$1; day=day_number(date)
            total+=seconds; by_date[date]+=seconds
            if(substr(date,1,7)==month) month_total+=seconds
            if(day>=today_day-6&&day<=today_day) recent7+=seconds
        }
        END {
            for(date in by_date) if(by_date[date]>0) {
                read_days++
                if(first_date==""||date<first_date)first_date=date
                if(last_date==""||date>last_date)last_date=date
            }
            if(first_date=="")first_date="-"
            if(last_date=="")last_date="-"
            average=(read_days>0?int((total+read_days/2)/read_days):0)
            print total+0 "\t" read_days+0 "\t" first_date "\t" last_date "\t" average+0 "\t" month_total+0 "\t" recent7+0 > summary
        }
    ' "$DAY_BOOKS" || return 1
    IFS="$(printf '\t')" read -r book_detail_total book_detail_read_days book_detail_first_date book_detail_last_date book_detail_active_average book_detail_month_total book_detail_7d_total < "$BOOK_DETAIL_SUMMARY" || return 1
    ensure_progress
    book_detail_progress="$(progress_for_book "$book_detail_title" "$book_detail_id")"
    case "$book_detail_progress" in ''|*[!0-9]*) book_detail_progress="";; esac
    [ -z "$book_detail_progress" ] || [ "$book_detail_progress" -le 100 ] || book_detail_progress=100
    printf '0\t%s\n' "$book_detail_title" > "$BOOK_DETAIL_TITLE"
    lua "$TITLE_LAYOUT" "$BOOK_DETAIL_TITLE" 790 42 0 54 > "$BOOK_DETAIL_TITLE_LAYOUT" || return 1
    if [ "$book_detail_last_date" != - ]; then date_parts "$book_detail_last_date"; book_calendar_y="$parsed_y"; book_calendar_m="$parsed_m"
    else date_parts "$today_date"; book_calendar_y="$parsed_y"; book_calendar_m="$parsed_m"; fi
    book_calendar_selected_date=""
    prepare_book_calendar
}

prepare_book_calendar() {
    book_calendar_dim="$(days_in_month "$book_calendar_y" "$book_calendar_m")" || return 1
    book_calendar_offset="$(weekday_offset "$book_calendar_y" "$book_calendar_m")" || return 1
    awk -F '\t' -v target="$book_detail_book_no" -v y="$book_calendar_y" -v m="$book_calendar_m" -v n="$book_calendar_dim" '
        BEGIN{for(i=1;i<=n;i++)value[i]=0}
        ($5+0)==target && $1~sprintf("^%04d-%02d-",y,m){d=substr($1,9,2)+0;value[d]+=$2+0}
        END{for(i=1;i<=n;i++)printf "%d\t%d\n",i,value[i]+0}
    ' "$DAY_BOOKS" > "$BOOK_DETAIL_DAILY" || return 1
}

shift_book_month() {
    book_calendar_m=$((book_calendar_m+$1))
    while [ "$book_calendar_m" -lt 1 ]; do book_calendar_m=$((book_calendar_m+12)); book_calendar_y=$((book_calendar_y-1)); done
    while [ "$book_calendar_m" -gt 12 ]; do book_calendar_m=$((book_calendar_m-12)); book_calendar_y=$((book_calendar_y+1)); done
    book_calendar_selected_date=""
    prepare_book_calendar
}

weekday_text() {
    case "$1" in 0) echo "星期一";; 1) echo "星期二";; 2) echo "星期三";; 3) echo "星期四";; 4) echo "星期五";; 5) echo "星期六";; 6) echo "星期日";; *) return 1;; esac
}

# Unified day-detail data boundary. It reads only the launch-time aggregate
# caches; the original reading-time.tsv is never rescanned during navigation.
get_day_detail() {
    day_detail_date="$1"; valid_date "$day_detail_date" || return 1
    day_detail_y="$parsed_y"; day_detail_m="$parsed_m"; day_detail_d="$parsed_d"
    day_detail_weekday="$(weekday_text $((( $(weekday_offset "$day_detail_y" "$day_detail_m") + day_detail_d - 1) % 7)))" || return 1
    day_detail_total="$(awk -F '\t' -v d="$day_detail_date" '$1==d{s+=$2}END{print s+0}' "$DAYS")" || return 1
    LC_ALL=C awk -F '\t' -v d="$day_detail_date" '
        $1==d && $2>0 { n++; seconds[n]=$2+0; title[n]=$3; id[n]=$4; book_no[n]=$5 }
        END {
            for(i=2;i<=n;i++) {
                s=seconds[i]; t=title[i]; k=id[i]; b=book_no[i]; j=i-1
                while(j>=1 && (seconds[j]<s || (seconds[j]==s && title[j]>t))) {
                    seconds[j+1]=seconds[j]; title[j+1]=title[j]; id[j+1]=id[j]; book_no[j+1]=book_no[j]; j--
                }
                seconds[j+1]=s; title[j+1]=t; id[j+1]=k; book_no[j+1]=b
            }
            for(i=1;i<=n;i++) print seconds[i] "\t" title[i] "\t" id[i] "\t" book_no[i]
        }
    ' "$DAY_BOOKS" > "$DAY_DETAIL_ALL.raw" || return 1
    awk -F '\t' -v total="$day_detail_total" 'BEGIN{OFS="\t"}{ratio=(total>0?int(($1*100+total/2)/total):0);if(ratio>100)ratio=100;print $1,ratio,$2,$3,$4}' "$DAY_DETAIL_ALL.raw" > "$DAY_DETAIL_ALL" || return 1
    rm -f "$DAY_DETAIL_ALL.raw"
    day_detail_count="$(awk 'NF{n++}END{print n+0}' "$DAY_DETAIL_ALL")"
    day_detail_capacity=3
    day_detail_pages=$(((day_detail_count+day_detail_capacity-1)/day_detail_capacity)); [ "$day_detail_pages" -ge 1 ] || day_detail_pages=1
    day_detail_page=1
}

prepare_day_detail_page() {
    day_detail_page="${day_detail_page:-1}"; [ "$day_detail_page" -ge 1 ] || day_detail_page=1
    [ "$day_detail_page" -le "$day_detail_pages" ] || day_detail_page="$day_detail_pages"
    day_detail_start=$(((day_detail_page-1)*day_detail_capacity+1))
    awk -v a="$day_detail_start" -v b="$((day_detail_start+day_detail_capacity-1))" 'NR>=a&&NR<=b' "$DAY_DETAIL_ALL" > "$DAY_DETAIL_VIEW"
}

prepare_daily_view() {
    date_parts "$selected_date"; selected_y="$parsed_y"; selected_m="$parsed_m"; selected_d="$parsed_d"
    # Keep EVERY book in the selected day. Pagination is a view of this list.
    awk -F '\t' -v d="$selected_date" '$1==d{print $2 "\t" $3}' "$DAY_BOOKS" | sort -nr > "$SESSION_DIR/daily-all.tsv"
    detail_count="$(awk 'NF{n++}END{print n+0}' "$SESSION_DIR/daily-all.tsv")"
    detail_capacity=$(((DETAIL_H-DETAIL_ROWS_Y)/DETAIL_ROW_H))
    [ "$detail_capacity" -ge 1 ] || detail_capacity=1
    if [ "$detail_count" -gt "$detail_capacity" ]; then detail_capacity=$(((DETAIL_H-DETAIL_ROWS_Y-DETAIL_PAGER_H)/DETAIL_ROW_H)); fi
    [ "$detail_capacity" -ge 1 ] || detail_capacity=1
    detail_pages=$(((detail_count+detail_capacity-1)/detail_capacity)); [ "$detail_pages" -ge 1 ] || detail_pages=1
    detail_page="${detail_page:-1}"; [ "$detail_page" -ge 1 ] || detail_page=1
    [ "$detail_page" -le "$detail_pages" ] || detail_page="$detail_pages"
    detail_start=$(((detail_page-1)*detail_capacity+1))
    awk -v a="$detail_start" -v b="$((detail_start+detail_capacity-1))" 'NR>=a&&NR<=b' "$SESSION_DIR/daily-all.tsv" > "$SESSION_DIR/daily-view.tsv"
    day_total="$(awk -F '\t' -v d="$selected_date" '$1==d{s+=$2}END{print s+0}' "$DAYS")"
}

spec_daily_detail() {
    prepare_daily_view
    b="$SESSION_DIR/daily-detail.pgm.new"; canvas detail 1132 "$DETAIL_H" "$b"
    stext detail B 34 20 5 left 0 "${selected_m}月${selected_d}日 阅读详情  ›"
    if [ "$day_total" -gt 0 ]; then
        stext detail B 32 1100 5 right 0 "共 $(time_text "$day_total")"; line=0
        while IFS="$(printf '\t')" read -r book_sec book_title; do
            [ -n "$book_title" ] || continue
            stext detail R 24 1100 $((DETAIL_ROWS_Y+5+line*DETAIL_ROW_H)) right 0 "$(time_text "$book_sec")"; line=$((line+1))
        done < "$SESSION_DIR/daily-view.tsv"
    else stext detail R 34 20 "$DETAIL_ROWS_Y" left 0 "当日无阅读记录"; fi
    if [ "$detail_pages" -gt 1 ]; then
        pager_y=$((DETAIL_H-DETAIL_PAGER_H))
        srect detail 320 "$pager_y" 140 48 20; srect detail 322 $((pager_y+2)) 136 44 255
        srect detail 672 "$pager_y" 140 48 20; srect detail 674 $((pager_y+2)) 136 44 255
        stext detail B 31 390 $((pager_y+7)) center 0 "<"
        stext detail R 27 566 $((pager_y+9)) center 0 "${detail_page} / ${detail_pages}"
        stext detail B 31 742 $((pager_y+7)) center 0 ">"
    fi
    swrite detail
}

spec_day_detail_summary() {
    a="$SESSION_DIR/day-detail-summary.pgm.new"; canvas day_summary 1132 "$DAY_DETAIL_SUMMARY_H" "$a"
    stext day_summary B 44 25 18 left 0 "${day_detail_y}年${day_detail_m}月${day_detail_d}日"
    stext day_summary R 30 20 92 left 0 "$day_detail_weekday"
    srect day_summary 20 145 1092 2 190
    stext day_summary R 27 80 180 left 0 "当日总时长"
    stext day_summary R 27 650 180 left 0 "阅读书籍"
    stext day_summary B 44 80 235 left 0 "$(summary_time_text "$day_detail_total")"
    stext day_summary B 44 650 235 left 0 "${day_detail_count}本"
    swrite day_summary
}

spec_day_detail_list() {
    prepare_day_detail_page
    b="$SESSION_DIR/day-detail-list.pgm.new"; canvas day_list 1132 "$DAY_DETAIL_LIST_H" "$b"
    stext day_list B 34 20 15 left 0 "阅读书籍明细"
    srect day_list 20 70 1092 2 190
    if [ "$day_detail_count" -eq 0 ]; then
        stext day_list R 34 566 430 center 0 "当日暂无阅读记录"
    else
        row=0
        while IFS="$(printf '\t')" read -r book_sec book_ratio book_title book_id book_no; do
            [ -n "$book_title" ] || continue
            row_y=$((DAY_DETAIL_ROWS_Y+row*DAY_DETAIL_ROW_H))
            render_cover_placeholder day_list 20 $((row_y+14)) "$COVER_DAY_W" "$COVER_DAY_H"
            stext day_list B 30 1100 $((row_y+75)) right 0 "$(time_text "$book_sec")"
            stext day_list R 24 1100 $((row_y+125)) right 0 "${book_ratio}%"
            srect day_list 190 $((row_y+190)) 900 16 210
            [ "$book_ratio" -gt 0 ] && srect day_list 190 $((row_y+190)) $((900*book_ratio/100)) 16 20
            srect day_list 20 $((row_y+258)) 1092 2 220
            row=$((row+1))
        done < "$DAY_DETAIL_VIEW"
    fi
    if [ "$day_detail_pages" -gt 1 ]; then
        srect day_list 320 "$DAY_DETAIL_PAGER_Y" 140 54 20; srect day_list 322 $((DAY_DETAIL_PAGER_Y+2)) 136 50 255
        srect day_list 672 "$DAY_DETAIL_PAGER_Y" 140 54 20; srect day_list 674 $((DAY_DETAIL_PAGER_Y+2)) 136 50 255
        stext day_list B 31 390 $((DAY_DETAIL_PAGER_Y+8)) center 0 "‹"
        stext day_list R 27 566 $((DAY_DETAIL_PAGER_Y+11)) center 0 "${day_detail_page} / ${day_detail_pages}"
        stext day_list B 31 742 $((DAY_DETAIL_PAGER_Y+8)) center 0 "›"
    fi
    swrite day_list
}

publish_day_detail_list() {
    pgm_valid "$SESSION_DIR/day-detail-list.pgm.new" 1132 "$DAY_DETAIL_LIST_H" || return 1
    mv "$SESSION_DIR/day-detail-list.pgm.new" "$SESSION_DIR/day-detail-list.pgm" || return 1
    image "$SESSION_DIR/day-detail-list.pgm" 70 "$DAY_DETAIL_LIST_TOP" 1132 "$DAY_DETAIL_LIST_H" || return 1
    awk -F '\t' 'BEGIN{OFS="\t"}{print $1,$3}' "$DAY_DETAIL_VIEW" > "$SESSION_DIR/day-detail-titles.tsv"
    lua "$TITLE_LAYOUT" "$SESSION_DIR/day-detail-titles.tsv" 640 38 0 "$DAY_DETAIL_ROW_H" > "$SESSION_DIR/day-detail-title-layout.tsv" || return 1
    while IFS="$(printf '\t')" read -r title_y title_line; do
        [ -n "$title_line" ] || continue
        ot 38 "$((DAY_DETAIL_LIST_TOP+DAY_DETAIL_ROWS_Y+14+title_y))" 280 330 BOLD "$title_line" || return 1
    done < "$SESSION_DIR/day-detail-title-layout.tsv"
    cover_row=0
    while IFS="$(printf '\t')" read -r book_sec book_ratio book_title book_id book_no; do
        [ -n "$book_title" ] || continue
        renderBookCover "$book_id" 90 "$((DAY_DETAIL_LIST_TOP+DAY_DETAIL_ROWS_Y+cover_row*DAY_DETAIL_ROW_H+14))" "$COVER_DAY_W" "$COVER_DAY_H" || return 1
        cover_row=$((cover_row+1))
    done < "$DAY_DETAIL_VIEW"
}

render_day_detail() {
    : > "$SPEC"; spec_day_detail_summary; spec_day_detail_list; run_renderer || return 1
    pgm_valid "$SESSION_DIR/day-detail-summary.pgm.new" 1132 "$DAY_DETAIL_SUMMARY_H" || return 1
    mv "$SESSION_DIR/day-detail-summary.pgm.new" "$SESSION_DIR/day-detail-summary.pgm" || return 1
    image "$SESSION_DIR/day-detail-summary.pgm" 70 "$DAY_DETAIL_SUMMARY_TOP" 1132 "$DAY_DETAIL_SUMMARY_H" || return 1
    publish_day_detail_list
}

render_day_detail_page() {
    : > "$SPEC"; spec_day_detail_list; run_renderer || return 1
    publish_day_detail_list
}

prepare_month_detail() {
    month_dim="$(days_in_month "$month_detail_y" "$month_detail_m")"
    month_start="$(printf '%04d-%02d-01' "$month_detail_y" "$month_detail_m")"
    month_end="$(printf '%04d-%02d-%02d' "$month_detail_y" "$month_detail_m" "$month_dim")"
    get_period_stats "$month_start" "$month_end" 1 || return 1
    awk -F '\t' -v y="$month_detail_y" -v m="$month_detail_m" -v n="$month_dim" '
        BEGIN{for(i=1;i<=n;i++)v[i]=0}
        $1~sprintf("^%04d-%02d-",y,m){d=substr($1,9,2)+0;v[d]+=$2}
        END{for(i=1;i<=n;i++)print i "\t" int(v[i]/60)}
    ' "$PERIOD_DAILY" > "$MONTH_VALUES" || return 1
    awk 'NR<=3' "$PERIOD_BOOKS" > "$MONTH_TOP" || return 1
    if [ "$period_peak_date" != - ]; then
        date_parts "$period_peak_date"; month_peak_label="${parsed_m}月${parsed_d}日"
    else month_peak_label="暂无"; fi
}

spec_month_summary() {
    a="$SESSION_DIR/month-summary.pgm.new"; canvas month_summary 1132 "$MONTH_SUMMARY_H" "$a"
    stext month_summary B 44 566 15 center 0 "${month_detail_y}年${month_detail_m}月"
    srect month_summary 20 80 1092 2 190
    if [ "$period_read_days" -eq 0 ]; then
        stext month_summary R 36 566 220 center 0 "本月暂无阅读记录"
    else
        stext month_summary R 24 60 112 left 0 "总阅读"
        stext month_summary R 24 410 112 left 0 "阅读天数"
        stext month_summary R 24 790 112 left 0 "阅读日均"
        stext month_summary B 36 60 154 left 0 "$(summary_time_text "$period_total")"
        stext month_summary B 36 410 154 left 0 "${period_read_days}天"
        stext month_summary B 36 790 154 left 0 "$(summary_time_text "$period_average")"
        srect month_summary 20 225 1092 2 210
        stext month_summary R 24 60 260 left 0 "阅读书籍"
        stext month_summary R 24 600 260 left 0 "最高一天"
        stext month_summary B 36 60 305 left 0 "${period_book_count}本"
        stext month_summary B 34 600 305 left 0 "$month_peak_label"
        stext month_summary R 27 600 360 left 0 "$(summary_time_text "$period_peak_seconds")"
    fi
    swrite month_summary
}

spec_month_body() {
    b="$SESSION_DIR/month-body.pgm.new"; canvas month_body 1132 "$MONTH_BODY_H" "$b"
    if [ "$period_read_days" -eq 0 ]; then
        stext month_body B 34 20 18 left 0 "每日阅读趋势"
        srect month_body 20 72 1092 2 190
        swrite month_body; return
    fi
    stext month_body B 34 20 12 left 0 "本月阅读最多"
    srect month_body 20 65 1092 2 190
    row=0
    while IFS="$(printf '\t')" read -r top_seconds top_title; do
        [ -n "$top_title" ] || continue
        row_y=$((88+row*86)); stext month_body B 27 1090 "$row_y" right 0 "$(summary_time_text "$top_seconds")"
        row=$((row+1))
    done < "$MONTH_TOP"
    stext month_body B 34 20 355 left 0 "每日阅读趋势"
    srect month_body 20 405 1092 2 190
    max="$(awk -F '\t' '$2>m{m=$2}END{print m+0}' "$MONTH_VALUES")"
    scale_hours=$(((max*112+5999)/6000)); [ "$scale_hours" -ge 1 ] || scale_hours=1; scale=$((scale_hours*60))
    if [ "$scale_hours" -le 3 ]; then tick_hours=1; elif [ "$scale_hours" -le 8 ]; then tick_hours=2; elif [ "$scale_hours" -le 15 ]; then tick_hours=3; else tick_hours=5; fi
    chart_base=840; chart_height=360; axis_text_left=7; axis_gap=24; plot_right=1114
    set --; gl="$tick_hours"; while [ "$gl" -le "$scale_hours" ]; do set -- "$@" "${gl}h"; gl=$((gl+tick_hours)); done
    [ "$#" -gt 0 ] || set -- "${scale_hours}h"
    axis_label_w="$(lua "$RENDERER" "$RENDER_ASSETS" --measure R 20 "$@")" || return 1
    case "$axis_label_w" in ''|*[!0-9]*) return 1;; esac
    axis_text_right=$((axis_text_left+axis_label_w)); plot_left=$((axis_text_right+axis_gap)); plot_width=$((plot_right-plot_left))
    srect month_body "$plot_left" "$chart_base" "$plot_width" 3 20
    gl="$tick_hours"; while [ "$gl" -le "$scale_hours" ]; do gy=$((chart_base-chart_height*gl/scale_hours)); srect month_body "$plot_left" "$gy" "$plot_width" 2 205; stext month_body R 20 "$axis_text_right" $((gy-24)) right 0 "${gl}h"; gl=$((gl+tick_hours)); done
    count="$month_dim"; bar_w=$((plot_width/count-7)); [ "$bar_w" -gt 24 ] && bar_w=24; [ "$bar_w" -ge 8 ] || bar_w=8
    pos=0
    while IFS="$(printf '\t')" read -r day_label mins; do
        center=$((plot_left+plot_width*(2*pos+1)/(2*count))); x=$((center-bar_w/2)); bh=$((mins*chart_height/scale)); [ "$mins" -gt 0 ] && [ "$bh" -lt 6 ] && bh=6
        [ "$bh" -gt 0 ] && srect month_body "$x" $((chart_base-bh)) "$bar_w" "$bh" 90
        case "$day_label" in 1|5|10|15|20|25|"$month_dim") stext month_body B 20 "$center" 858 center 0 "$day_label";; esac
        pos=$((pos+1))
    done < "$MONTH_VALUES"
    swrite month_body
}

publish_month_detail() {
    pgm_valid "$SESSION_DIR/month-summary.pgm.new" 1132 "$MONTH_SUMMARY_H" && pgm_valid "$SESSION_DIR/month-body.pgm.new" 1132 "$MONTH_BODY_H" || return 1
    mv "$SESSION_DIR/month-summary.pgm.new" "$SESSION_DIR/month-summary.pgm" && mv "$SESSION_DIR/month-body.pgm.new" "$SESSION_DIR/month-body.pgm" || return 1
    image "$SESSION_DIR/month-summary.pgm" 70 "$MONTH_SUMMARY_TOP" 1132 "$MONTH_SUMMARY_H" && image "$SESSION_DIR/month-body.pgm" 70 "$MONTH_BODY_TOP" 1132 "$MONTH_BODY_H" || return 1
    [ -s "$MONTH_TOP" ] || return 0
    lua "$TITLE_LAYOUT" "$MONTH_TOP" 760 30 1 86 > "$SESSION_DIR/month-top-titles.tsv" || return 1
    while IFS="$(printf '\t')" read -r title_y title_line; do
        [ -n "$title_line" ] || continue
        ot 30 "$((MONTH_BODY_TOP+90+title_y))" 100 360 BOLD "$title_line" || return 1
    done < "$SESSION_DIR/month-top-titles.tsv"
}

render_month_detail() {
    : > "$SPEC"; spec_month_summary; spec_month_body; run_renderer || return 1
    publish_month_detail
}

prepare_week_trend() {
    trend_today_day="$(cat "$CALENDAR")"; case "$trend_today_day" in ''|*[!0-9]*) return 1;; esac
    trend_current_monday=$((trend_today_day-trend_today_day%7)); trend_start_day=$((trend_current_monday-49))
    trend_start_date="$(civil_date "$trend_start_day")" || return 1
    trend_current_date="$(civil_date "$trend_current_monday")" || return 1
    get_period_stats "$trend_start_date" "$today_date" 0 || return 1
    awk -F '\t' -v first="$trend_start_day" '
        function day_number(date,    y,m,d,a,yy,mm) {
            y=substr(date,1,4)+0;m=substr(date,6,2)+0;d=substr(date,9,2)+0
            a=int((14-m)/12);yy=y+4800-a;mm=m+12*a-3
            return d+int((153*mm+2)/5)+365*yy+int(yy/4)-int(yy/100)+int(yy/400)-32045
        }
        function civil(day,    l,n,i,j,d,m,y) {
            l=day+68569;n=int(4*l/146097);l=l-int((146097*n+3)/4)
            i=int(4000*(l+1)/1461001);l=l-int(1461*i/4)+31
            j=int(80*l/2447);d=l-int(2447*j/80);l=int(j/11)
            m=j+2-12*l;y=100*(n-49)+i+l
            return sprintf("%04d-%02d-%02d",y,m,d)
        }
        {day=day_number($1);bucket=int((day-first)/7);if(bucket>=0&&bucket<8)value[bucket]+=$2}
        END{for(i=0;i<8;i++){date=civil(first+i*7);m=substr(date,6,2)+0;d=substr(date,9,2)+0;print m "/" d "\t" value[i]+0 "\t" (i==7?1:0)}}
    ' "$PERIOD_DAILY" > "$WEEK_TREND_VALUES" || return 1
    week_current="$(awk -F '\t' 'NR==8{print $2+0}' "$WEEK_TREND_VALUES")"
    week_previous="$(awk -F '\t' 'NR==7{print $2+0}' "$WEEK_TREND_VALUES")"
    week_total="$(awk -F '\t' '{s+=$2}END{print s+0}' "$WEEK_TREND_VALUES")"
    week_best="$(awk -F '\t' '$2>m{m=$2}END{print m+0}' "$WEEK_TREND_VALUES")"
    week_average=$(((week_total+4*60)/(8*60)*60)); week_difference=$((week_current-week_previous))
    week_current_days="$(awk -F '\t' -v start="$trend_current_date" '$1>=start&&$2>0{n++}END{print n+0}' "$PERIOD_DAILY")"
}

render_week_trend() {
    a="$SESSION_DIR/week-trend-summary.pgm.new"; b="$SESSION_DIR/week-trend-chart.pgm.new"; : > "$SPEC"
    canvas trend_summary 1132 "$WEEK_TREND_SUMMARY_H" "$a"
    # Keep the two-row metric group vertically centered in the summary card.
    for item in "本周:$week_current:202" "上周:$week_previous:566" "较上周:$week_difference:930"; do
        label="${item%%:*}"; rest="${item#*:}"; value="${rest%%:*}"; x="${rest##*:}"
        stext trend_summary R 24 "$x" 80 center 0 "$label"
        if [ "$label" = "较上周" ]; then display="$(signed_time_text "$value")"; else display="$(summary_time_text "$value")"; fi
        stext trend_summary B 32 "$x" 127 center 0 "$display"
    done
    srect trend_summary 20 210 1092 2 205
    stext trend_summary R 24 202 250 center 0 "8周平均"; stext trend_summary B 32 202 297 center 0 "$(summary_time_text "$week_average")"
    stext trend_summary R 24 566 250 center 0 "最佳一周"; stext trend_summary B 32 566 297 center 0 "$(summary_time_text "$week_best")"
    stext trend_summary R 24 930 250 center 0 "本周阅读"; stext trend_summary B 32 930 297 center 0 "${week_current_days}天"
    swrite trend_summary
    canvas trend_chart 1132 "$WEEK_TREND_CHART_H" "$b"; stext trend_chart B 34 20 18 left 0 "每周阅读趋势"; srect trend_chart 20 72 1092 2 190
    max="$(awk -F '\t' '$2>m{m=$2}END{print int(m/60)+0}' "$WEEK_TREND_VALUES")"
    scale_hours=$(((max*112+5999)/6000)); [ "$scale_hours" -ge 1 ] || scale_hours=1; scale=$((scale_hours*60))
    if [ "$scale_hours" -le 3 ]; then tick_hours=1; elif [ "$scale_hours" -le 8 ]; then tick_hours=2; elif [ "$scale_hours" -le 15 ]; then tick_hours=3; else tick_hours=5; fi
    chart_base=820; chart_height=660; axis_text_left=7; axis_gap=28; plot_right=1114
    set --; gl="$tick_hours"; while [ "$gl" -le "$scale_hours" ]; do set -- "$@" "${gl}h"; gl=$((gl+tick_hours)); done
    [ "$#" -gt 0 ] || set -- "${scale_hours}h"
    axis_label_w="$(lua "$RENDERER" "$RENDER_ASSETS" --measure R 20 "$@")" || return 1
    case "$axis_label_w" in ''|*[!0-9]*) return 1;; esac
    axis_text_right=$((axis_text_left+axis_label_w)); plot_left=$((axis_text_right+axis_gap)); plot_width=$((plot_right-plot_left)); srect trend_chart "$plot_left" "$chart_base" "$plot_width" 3 20
    gl="$tick_hours"; while [ "$gl" -le "$scale_hours" ]; do gy=$((chart_base-chart_height*gl/scale_hours)); srect trend_chart "$plot_left" "$gy" "$plot_width" 2 205; stext trend_chart R 20 "$axis_text_right" $((gy-26)) right 0 "${gl}h"; gl=$((gl+tick_hours)); done
    pos=0; count=8; bar_w=72
    while IFS="$(printf '\t')" read -r week_label seconds current; do
        mins=$((seconds/60)); center=$((plot_left+plot_width*(2*pos+1)/(2*count))); x=$((center-bar_w/2)); bh=$((mins*chart_height/scale)); [ "$mins" -gt 0 ] && [ "$bh" -lt 8 ] && bh=8
        [ "$bh" -gt 0 ] && srect trend_chart "$x" $((chart_base-bh)) "$bar_w" "$bh" 125
        stext trend_chart B 22 "$center" 846 center 0 "$week_label"
        [ "$mins" -gt 0 ] && sfitlabel trend_chart B 20 "$center" $((chart_base-bh-34)) center 0 "$(chart_time_text "$mins")" "$plot_left" "$plot_right"
        pos=$((pos+1))
    done < "$WEEK_TREND_VALUES"
    swrite trend_chart; run_renderer || return 1
    pgm_valid "$a" 1132 "$WEEK_TREND_SUMMARY_H" && pgm_valid "$b" 1132 "$WEEK_TREND_CHART_H" || return 1
    mv "$a" "$SESSION_DIR/week-trend-summary.pgm" && mv "$b" "$SESSION_DIR/week-trend-chart.pgm" || return 1
    image "$SESSION_DIR/week-trend-summary.pgm" 70 "$WEEK_TREND_SUMMARY_TOP" 1132 "$WEEK_TREND_SUMMARY_H" && image "$SESSION_DIR/week-trend-chart.pgm" 70 "$WEEK_TREND_CHART_TOP" 1132 "$WEEK_TREND_CHART_H"
}

spec_book_detail_summary() {
    a="$SESSION_DIR/book-detail-summary.pgm.new"; canvas book_summary 1132 "$BOOK_DETAIL_SUMMARY_H" "$a"
    render_cover_placeholder book_summary 35 145 "$COVER_DETAIL_W" "$COVER_DETAIL_H"
    srect book_summary 265 125 2 340 205
    srect book_summary 285 118 807 2 190
    if [ "$book_detail_first_date" = - ]; then first_display="暂无"; else first_display="$book_detail_first_date"; fi
    if [ "$book_detail_last_date" = - ]; then last_display="暂无"; else last_display="$book_detail_last_date"; fi
    if [ -n "$book_detail_progress" ]; then progress_display="${book_detail_progress}%"; else progress_display="暂无进度"; fi
    stext book_summary R 22 300 142 left 0 "累计阅读"; stext book_summary R 22 700 142 left 0 "阅读天数"
    stext book_summary B 34 300 178 left 0 "$(summary_time_text "$book_detail_total")"; stext book_summary B 34 700 178 left 0 "${book_detail_read_days}天"
    stext book_summary R 22 300 247 left 0 "首次阅读"; stext book_summary R 22 700 247 left 0 "最近阅读"
    stext book_summary B 28 300 283 left 0 "$first_display"; stext book_summary B 28 700 283 left 0 "$last_display"
    stext book_summary R 22 300 352 left 0 "本月阅读"; stext book_summary R 22 700 352 left 0 "阅读进度"
    stext book_summary B 34 300 388 left 0 "$(summary_time_text "$book_detail_month_total")"; stext book_summary B 34 700 388 left 0 "$progress_display"
    swrite book_summary
}

spec_book_detail_chart() {
    b="$SESSION_DIR/book-detail-chart.pgm.new"; canvas book_chart 1132 "$BOOK_DETAIL_CHART_H" "$b"
    stext book_chart B 34 20 18 left 0 "阅读日历"
    stext book_chart B 34 320 18 center 0 "‹"
    stext book_chart B 36 566 16 center 0 "${book_calendar_y}年${book_calendar_m}月"
    stext book_chart B 34 812 18 center 0 "›"
    srect book_chart 20 72 1092 2 190
    calendar_col=0
    for calendar_weekday in 一 二 三 四 五 六 日; do
        stext book_chart R 24 $((86+calendar_col*160)) 92 center 0 "$calendar_weekday"
        calendar_col=$((calendar_col+1))
    done
    calendar_rows=$(((book_calendar_offset+book_calendar_dim+6)/7)); calendar_cell_h=$((520/calendar_rows))
    while IFS="$(printf '\t')" read -r calendar_day calendar_seconds; do
        calendar_index=$((book_calendar_offset+calendar_day-1)); calendar_col=$((calendar_index%7)); calendar_row=$((calendar_index/7))
        calendar_x=$((6+calendar_col*160)); calendar_y=$((130+calendar_row*calendar_cell_h)); calendar_center=$((calendar_x+80))
        stext book_chart B 27 "$calendar_center" $((calendar_y+3)) center 0 "$calendar_day"
        heat_level="$(calendar_heat_level "$calendar_seconds")" || return 1; heat_gray="$(calendar_heat_gray "$heat_level")" || return 1
        heat_x=$((calendar_center-34)); heat_y=$((calendar_y+39)); srect book_chart "$heat_x" "$heat_y" 68 46 "$heat_gray"
        calendar_date="$(printf '%04d-%02d-%02d' "$book_calendar_y" "$book_calendar_m" "$calendar_day")"
        if [ "$calendar_date" = "$book_calendar_selected_date" ]; then
            srect book_chart $((heat_x-3)) $((heat_y-3)) 74 3 20; srect book_chart $((heat_x-3)) $((heat_y+46)) 74 3 20
            srect book_chart $((heat_x-3)) $((heat_y-3)) 3 52 20; srect book_chart $((heat_x+68)) $((heat_y-3)) 3 52 20
        fi
    done < "$BOOK_DETAIL_DAILY"
    srect book_chart 20 690 1092 2 205
    if [ -n "$book_calendar_selected_date" ]; then
        selected_calendar_day="${book_calendar_selected_date##*-}"; selected_calendar_day="${selected_calendar_day#0}"
        selected_calendar_seconds="$(awk -F '\t' -v d="$selected_calendar_day" '$1==d{print $2;exit}' "$BOOK_DETAIL_DAILY")"; selected_calendar_seconds="${selected_calendar_seconds:-0}"
        if [ "$selected_calendar_seconds" -gt 0 ]; then selected_calendar_text="阅读 $(time_text "$selected_calendar_seconds")"; else selected_calendar_text="未阅读"; fi
        stext book_chart B 28 566 730 center 0 "${book_calendar_y}年${book_calendar_m}月${selected_calendar_day}日 · ${selected_calendar_text}"
    else
        stext book_chart R 24 566 732 center 110 "点击日期查看当日阅读时长"
    fi
    swrite book_chart
}

publish_book_detail() {
    pgm_valid "$SESSION_DIR/book-detail-summary.pgm.new" 1132 "$BOOK_DETAIL_SUMMARY_H" && pgm_valid "$SESSION_DIR/book-detail-chart.pgm.new" 1132 "$BOOK_DETAIL_CHART_H" || return 1
    mv "$SESSION_DIR/book-detail-summary.pgm.new" "$SESSION_DIR/book-detail-summary.pgm" && mv "$SESSION_DIR/book-detail-chart.pgm.new" "$SESSION_DIR/book-detail-chart.pgm" || return 1
    image "$SESSION_DIR/book-detail-summary.pgm" 70 "$BOOK_DETAIL_SUMMARY_TOP" 1132 "$BOOK_DETAIL_SUMMARY_H" && image "$SESSION_DIR/book-detail-chart.pgm" 70 "$BOOK_DETAIL_CHART_TOP" 1132 "$BOOK_DETAIL_CHART_H" || return 1
    while IFS="$(printf '\t')" read -r title_y title_line; do
        [ -n "$title_line" ] || continue
        ot 42 "$((BOOK_DETAIL_SUMMARY_TOP+18+title_y))" 370 90 BOLD "$title_line" || return 1
    done < "$BOOK_DETAIL_TITLE_LAYOUT"
    renderBookCover "$book_detail_id" 105 "$((BOOK_DETAIL_SUMMARY_TOP+145))" "$COVER_DETAIL_W" "$COVER_DETAIL_H" || return 1
}

publish_book_calendar() {
    pgm_valid "$SESSION_DIR/book-detail-chart.pgm.new" 1132 "$BOOK_DETAIL_CHART_H" || return 1
    mv "$SESSION_DIR/book-detail-chart.pgm.new" "$SESSION_DIR/book-detail-chart.pgm" || return 1
    image "$SESSION_DIR/book-detail-chart.pgm" 70 "$BOOK_DETAIL_CHART_TOP" 1132 "$BOOK_DETAIL_CHART_H"
}

render_book_detail() {
    : > "$SPEC"; spec_book_detail_summary; spec_book_detail_chart; run_renderer || return 1
    publish_book_detail
}

render_book_calendar() {
    : > "$SPEC"; spec_book_detail_chart; run_renderer || return 1
    publish_book_calendar
}

publish_daily_detail() {
    pgm_valid "$SESSION_DIR/daily-detail.pgm.new" 1132 "$DETAIL_H" || return 1
    mv "$SESSION_DIR/daily-detail.pgm.new" "$SESSION_DIR/daily-detail.pgm" || return 1
    image "$SESSION_DIR/daily-detail.pgm" 70 "$DETAIL_TOP" 1132 "$DETAIL_H" || return 1
    lua "$TITLE_LAYOUT" "$SESSION_DIR/daily-view.tsv" 800 40 0 "$DETAIL_ROW_H" > "$SESSION_DIR/daily-titles.tsv" || return 1
    while IFS="$(printf '\t')" read -r title_y title_line; do
        [ -n "$title_line" ] || continue
        ot 40 "$((DETAIL_TOP+DETAIL_ROWS_Y+title_y))" 90 360 REGULAR "$title_line" || return 1
    done < "$SESSION_DIR/daily-titles.tsv"
}

render_detail_page() {
    : > "$SPEC"; spec_daily_detail; run_renderer || return 1
    publish_daily_detail
}

render_daily() {
    with_labels="$1"; dim="$(days_in_month "$daily_y" "$daily_m")"; offset="$(weekday_offset "$daily_y" "$daily_m")"
    rows=$(((offset+dim+6)/7)); cell_h=$((CALENDAR_GRID_H/rows))
    set -- $(awk -F '\t' -v y="$daily_y" -v m="$daily_m" -v n="$dim" 'BEGIN{for(i=1;i<=n;i++)v[i]=0}$1~sprintf("^%04d-%02d-",y,m){d=substr($1,9,2)+0;v[d]+=$2}END{for(i=1;i<=n;i++)printf "%d%s",v[i]+0,(i<n?" ":"\n")}' "$DAYS")
    a="$SESSION_DIR/daily-calendar.pgm.new"; : > "$SPEC"; canvas calendar 1122 722 "$a"
    # Render the complete rectangle, including all leading/trailing empty slots.
    idx=0; while [ "$idx" -lt $((rows*7)) ]; do
        x=$((idx%7*160)); y=$((idx/7*cell_h))
        srect calendar "$x" "$y" 154 $((cell_h-6)) 20
        srect calendar $((x+2)) $((y+2)) 150 $((cell_h-10)) 255
        idx=$((idx+1))
    done
    day=1; month_read_days=0; month_total=0
    for sec in "$@"; do
        idx=$((offset+day-1)); row=$((idx/7)); col=$((idx%7)); x=$((col*160)); y=$((row*cell_h))
        [ "$sec" -gt 0 ] && month_read_days=$((month_read_days+1)); month_total=$((month_total+sec))
        heat_level="$(calendar_heat_level "$sec")" || return 1
        heat_gray="$(calendar_heat_gray "$heat_level")" || return 1
        ink="$(calendar_heat_ink "$heat_level")" || return 1
        srect calendar $((x+2)) $((y+2)) 150 $((cell_h-10)) "$heat_gray"
        cell_date="$(printf '%04d-%02d-%02d' "$daily_y" "$daily_m" "$day")"
        if [ "$cell_date" = "$selected_date" ]; then
            # The normal border is 2 px. Draw the selected date's 4 px border
            # inward so heat fill and neighboring geometry remain unchanged.
            cell_box_h=$((cell_h-6)); selected_border=4
            srect calendar "$x" "$y" 154 "$selected_border" 20
            srect calendar "$x" "$y" "$selected_border" "$cell_box_h" 20
            srect calendar $((x+154-selected_border)) "$y" "$selected_border" "$cell_box_h" 20
            srect calendar "$x" $((y+cell_box_h-selected_border)) 154 "$selected_border" 20
        fi
        stext calendar B 36 $((x+77)) $((y+10)) center "$ink" "$day"
        [ "$sec" -gt 0 ] && stext calendar R 27 $((x+77)) $((y+cell_h-43)) center "$ink" "$(calendar_time "$sec")"
        day=$((day+1))
    done
    srect calendar 0 662 1122 2 190
    stext calendar R 27 20 684 left 0 "本月阅读 ${month_read_days} 天  共 $(minute_text "$month_total")"
    swrite calendar
    if [ "$with_labels" = 1 ]; then
        canvas month 372 80 "$SESSION_DIR/daily-month.pgm.new"
        # 450 + 186 = 636: the calendar's center, independent of either arrow.
        stext month B 44 186 17 center 0 "${daily_y}年${daily_m}月"; swrite month
    fi
    spec_daily_detail; run_renderer || return 1
    pgm_valid "$a" 1122 722 || return 1
    mv "$a" "$SESSION_DIR/daily-calendar.pgm" || return 1
    image "$SESSION_DIR/daily-calendar.pgm" 75 460 1122 722 || return 1
    if [ "$with_labels" = 1 ]; then
        pgm_valid "$SESSION_DIR/daily-month.pgm.new" 372 80 || return 1
        mv "$SESSION_DIR/daily-month.pgm.new" "$SESSION_DIR/daily-month.pgm" || return 1
        image "$SESSION_DIR/daily-month.pgm" 450 320 372 80 || return 1
    fi
    publish_daily_detail
}

active_books() { case "$book_filter" in 7d) echo "$BOOKS_7D";; month) echo "$BOOKS_MONTH";; year) echo "$BOOKS_YEAR";; *) return 1;; esac; }
book_pages() { book_source="$(active_books)" || return 1; count="$(awk 'NF{n++}END{print n+0}' "$book_source")"; pages=$(((count+BOOK_PAGE_SIZE-1)/BOOK_PAGE_SIZE)); [ "$pages" -gt 0 ] || pages=1; echo "$pages"; }
prepare_book_view() { book_source="$(active_books)" || return 1; start=$(((book_page-1)*BOOK_PAGE_SIZE+1)); awk -v a="$start" -v b="$((start+BOOK_PAGE_SIZE-1))" 'NR>=a&&NR<=b' "$book_source" > "$SESSION_DIR/book-view.tsv"; }

spec_book_filters() {
    canvas filters 1132 58 "$SESSION_DIR/books-filters.pgm.new"
    for filter_item in '7d:0:354:近7日' 'month:389:354:本月' 'year:778:354:今年'; do
        filter_key="${filter_item%%:*}"; filter_rest="${filter_item#*:}"; filter_x="${filter_rest%%:*}"; filter_rest="${filter_rest#*:}"; filter_w="${filter_rest%%:*}"; filter_text="${filter_rest#*:}"
        [ "$book_filter" = "$filter_key" ] && filter_selected=1 || filter_selected=0
        spec_toggle_button filters "$filter_x" "$filter_w" "$filter_text" "$filter_selected"
    done
    swrite filters
}

render_books() {
    ensure_progress; pages="$(book_pages)"; [ "$book_page" -gt "$pages" ] && book_page="$pages"; prepare_book_view
    a="$SESSION_DIR/books-content.pgm.new"; b="$SESSION_DIR/books-page.pgm.new"; : > "$SPEC"; spec_book_filters; canvas books 1132 1080 "$a"
    srect books 25 359 1082 2 190; srect books 25 719 1082 2 190
    row=0; while IFS="$(printf '\t')" read -r sec title id index; do
        [ -n "$title" ] || continue; y=$((row*BOOK_ROW_H)); render_cover_placeholder books 25 $((y+34)) "$COVER_BOOK_W" "$COVER_BOOK_H"
        stext books R 28 255 $((y+195)) left 0 "阅读 $(time_text "$sec")"; progress="$(progress_for_book "$title" "$id")"; case "$progress" in ''|*[!0-9]*) progress="";;esac
        if [ -n "$progress" ]; then [ "$progress" -gt 100 ] && progress=100; stext books B 27 1090 $((y+195)) right 0 "阅读进度  ${progress}%"; srect books 255 $((y+252)) 830 18 205; [ "$progress" -gt 0 ] && srect books 255 $((y+252)) $((830*progress/100)) 18 20; else stext books R 24 1090 $((y+195)) right 0 "暂无进度"; fi; row=$((row+1))
    done < "$SESSION_DIR/book-view.tsv"
    if [ ! -s "$SESSION_DIR/book-view.tsv" ]; then stext books R 32 566 450 center 0 "当前范围暂无满5分钟的书籍"; fi
    swrite books; canvas page 452 60 "$b"; stext page B 30 226 10 center 0 "第 ${book_page} 页，共 ${pages} 页"; swrite page; run_renderer || return 1
    pgm_valid "$a" 1132 1080 && pgm_valid "$b" 452 60 && pgm_valid "$SESSION_DIR/books-filters.pgm.new" 1132 58 || return 1; mv "$a" "$SESSION_DIR/books-content.pgm" && mv "$b" "$SESSION_DIR/books-page.pgm" && mv "$SESSION_DIR/books-filters.pgm.new" "$SESSION_DIR/books-filters.pgm" || return 1
    image "$SESSION_DIR/books-filters.pgm" 70 285 1132 58 && image "$SESSION_DIR/books-content.pgm" 70 345 1132 1080 && image "$SESSION_DIR/books-page.pgm" 410 1480 452 60 || return 1
    lua "$TITLE_LAYOUT" "$SESSION_DIR/book-view.tsv" 780 42 0 "$BOOK_ROW_H" > "$SESSION_DIR/book-titles.tsv" || return 1
    while IFS="$(printf '\t')" read -r title_y title_line; do
        [ -n "$title_line" ] || continue
        ot 42 "$((375+title_y))" 340 100 BOLD "$title_line" || return 1
    done < "$SESSION_DIR/book-titles.tsv"
    cover_row=0
    while IFS="$(printf '\t')" read -r sec title id index; do
        [ -n "$title" ] || continue
        renderBookCover "$id" 95 "$((345+cover_row*BOOK_ROW_H+34))" "$COVER_BOOK_W" "$COVER_BOOK_H" || return 1
        cover_row=$((cover_row+1))
    done < "$SESSION_DIR/book-view.tsv"
}

draw_background() { image "$UI_DIR/${mode}.png" 0 0 1272 1696; }
draw_dynamic() { case "$mode" in total) render_total;; daily) if [ "$1" = 2 ]; then render_detail_page; else render_daily "$1"; fi;; books) render_books;; day_detail) if [ "$1" = 2 ]; then render_day_detail_page; else render_day_detail; fi;; month_detail) render_month_detail;; week_trend) render_week_trend;; book_detail) if [ "$1" = 3 ]; then render_book_calendar; else render_book_detail; fi;; *) return 1;; esac; }

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

# Both calendar and weekly chart drill into this single renderer/data path.
open_day_detail() {
    open_date="$1"; open_source="$2"
    get_day_detail "$open_date" || return 1
    case "$open_source" in daily|total) day_detail_source="$open_source";; *) return 1;; esac
    mode=day_detail
    perform_draw day_detail_open 1 0 0 0 1272 1696
}

# Calendar titles and annual bars share this single month-detail destination.
open_month_detail() {
    month_detail_y="$1"; month_detail_m="$2"; month_detail_source="$3"
    case "$month_detail_y:$month_detail_m" in *[!0-9:]*) return 1;; esac
    [ "$month_detail_y" -ge 1 ] && [ "$month_detail_m" -ge 1 ] && [ "$month_detail_m" -le 12 ] || return 1
    case "$month_detail_source" in daily|total) :;; *) return 1;; esac
    prepare_month_detail || return 1
    mode=month_detail; perform_draw month_detail_open 1 0 0 0 1272 1696
}

open_week_trend() {
    prepare_week_trend || return 1
    mode=week_trend; perform_draw week_trend_open 1 0 0 0 1272 1696
}

open_book_detail() {
    open_row="$1"; case "$open_row" in 1|2|3) :;; *) return 1;; esac
    prepare_book_view || return 1
    selected_book="$(awk -v n="$open_row" 'NR==n{print;exit}' "$SESSION_DIR/book-view.tsv")"
    [ -n "$selected_book" ] || return 2
    IFS="$(printf '\t')" read -r selected_seconds selected_title selected_id selected_book_no <<EOF
$selected_book
EOF
    [ -n "$selected_title" ] || return 2
    get_book_detail "$selected_book_no" "$selected_title" "$selected_id" || return 1
    book_detail_filter="$book_filter"; book_detail_page="$book_page"; mode=book_detail
    perform_draw book_detail_open 1 0 0 0 1272 1696
}

detect_screen; find_touch_device
mkdir -p "$SESSION_DIR" || fail "无法创建阅读记录会话缓存"; chmod 700 "$SESSION_DIR" 2>/dev/null || true
    [ -x "$FBINK" ] || fail "未找到 Véra/KPM 系统级 FBInk"; [ -f "$UI_DIR/total.png" ] && [ -f "$UI_DIR/day_detail.png" ] && [ -f "$UI_DIR/month_detail.png" ] && [ -f "$UI_DIR/week_trend.png" ] && [ -f "$UI_DIR/book_detail.png" ] || fail "缺少优化版界面资源"; [ -f "$DATA" ] || fail "尚无阅读统计数据"; [ -r "$TOUCH" ] || fail "无法读取触摸设备"; [ -f "$TOUCH_READER" ] || fail "缺少安全触摸监听器"; [ -f "$LEGACY" ] || fail "缺少原始 9.6.3 后备界面"; command -v lua >/dev/null 2>&1 || fail "未找到 Lua 运行环境"
RFONT="$BASE/fonts/NotoSansCJKsc-Regular.otf"; [ -f "$RFONT" ] || fail "缺少阅读记录中文字体"
    printf 'screen=%sx%s\nviewport=%sx%s+%s+%s\nlogical=%sx%s\ntouch=%s\nrelease=9.7.4\n' "$SCREEN_W" "$SCREEN_H" "$VIEW_W" "$VIEW_H" "$ORIGIN_X" "$ORIGIN_Y" "$LOGICAL_W" "$LOGICAL_H" "$TOUCH" > "$BASE/display-layout.txt"
echo "$(date): screen=${SCREEN_W}x${SCREEN_H}, viewport=${VIEW_W}x${VIEW_H}+${ORIGIN_X}+${ORIGIN_Y}, renderer=$renderer_available"
lipc-set-prop com.lab126.winmgr eatTapMode 0 >/dev/null 2>&1 || true; lipc-set-prop com.lab126.powerd preventScreenSaver 1 >/dev/null 2>&1 || true; dashboard_active=1

mode=daily; view_year="$(date +%Y)"; total_period=week; week_offset=0; book_filter=7d; daily_y="$(date +%Y)"; daily_m="$(date +%m | sed 's/^0//')"; today_date="$(date +%Y-%m-%d)"; selected_date="$today_date"; book_page=1; detail_page=1; detail_pages=1; day_detail_page=1; day_detail_pages=1; day_detail_source=daily; month_detail_source=daily; book_detail_filter=7d; book_detail_page=1
metric_begin first_open; build_cache || fallback_to_legacy; selected_date="$today_date"; draw_background || fallback_to_legacy; draw_dynamic 1 || fallback_to_legacy; refresh_region 0 0 1272 1696; metric_end optimized 0 1

while :; do
    if [ "$mode" = book_detail ]; then offset="$book_calendar_offset"; dim="$book_calendar_dim"; else offset="$(weekday_offset "$daily_y" "$daily_m")"; dim="$(days_in_month "$daily_y" "$daily_m")"; fi
    if [ "$mode" = day_detail ]; then touch_pages="$day_detail_pages"; touch_page="$day_detail_page"; touch_pager_y=$((DAY_DETAIL_LIST_TOP+DAY_DETAIL_PAGER_Y)); else touch_pages="$detail_pages"; touch_page="$detail_page"; touch_pager_y=$((DETAIL_TOP+DETAIL_H-DETAIL_PAGER_H)); fi
    action="$(lua "$TOUCH_READER" "$TOUCH" "$BASE/dashboard-touch.log" "$mode" "$offset" "$dim" "$ORIGIN_X" "$ORIGIN_Y" "$VIEW_W" "$VIEW_H" "$touch_pages" "$touch_page" "$touch_pager_y" "$total_period" "$book_filter")" || action=exit
    echo "$(date): dashboard action=$action mode=$mode"
    case "$action" in
      exit) break;;
      tab_total) if [ "$mode" = total ]; then metric_begin tab_total_noop; metric_end none 0 0; else mode=total; perform_draw tab_to_total 1 1 0 0 1272 1696; fi;;
      tab_daily) if [ "$mode" = daily ]; then metric_begin tab_daily_noop; metric_end none 0 0; else mode=daily; perform_draw tab_to_daily 1 1 0 0 1272 1696; fi;;
      tab_books) if [ "$mode" = books ]; then metric_begin tab_books_noop; metric_end none 0 0; else mode=books; perform_draw tab_to_books 1 1 0 0 1272 1696; fi;;
      total_week) if [ "$total_period" = week ]; then metric_begin total_week_noop; metric_end none 0 0; else total_period=week; week_offset=0; perform_draw total_to_week 0 0 55 380 1162 1070; fi;;
      total_year) if [ "$total_period" = year ]; then metric_begin total_year_noop; metric_end none 0 0; else total_period=year; perform_draw total_to_year 0 0 55 380 1162 1070; fi;;
      total_prev) if [ "$total_period" = week ]; then week_offset=$((week_offset-1)); perform_draw week_previous 0 0 55 380 1162 1070; else view_year=$((view_year-1)); perform_draw year_previous 0 0 55 380 1162 1070; fi;;
      total_next) if [ "$total_period" = week ]; then if [ "$week_offset" -lt 0 ]; then week_offset=$((week_offset+1)); perform_draw week_next 0 0 55 380 1162 1070; else metric_begin week_next_noop; metric_end none 0 0; fi; else current_year="$(date +%Y)"; if [ "$view_year" -lt "$current_year" ]; then view_year=$((view_year+1)); perform_draw year_next 0 0 55 380 1162 1070; else metric_begin year_next_noop; metric_end none 0 0; fi; fi;;
      week_trend_open) open_week_trend || fallback_to_legacy;;
      week_trend_back) mode=total; perform_draw week_trend_back 1 1 0 0 1272 1696;;
      month_detail_open) open_month_detail "$daily_y" "$daily_m" daily || fallback_to_legacy;;
      year_month_*) open_month="${action#year_month_}"; open_month_detail "$view_year" "$open_month" total || fallback_to_legacy;;
      month_detail_back) mode="$month_detail_source"; perform_draw month_detail_back 1 1 0 0 1272 1696;;
      book_detail_back) book_filter="$book_detail_filter"; book_page="$book_detail_page"; mode=books; perform_draw book_detail_back 1 1 0 0 1272 1696;;
      book_month_prev) shift_book_month -1 || fallback_to_legacy; perform_draw book_month_previous 0 3 55 "$BOOK_DETAIL_CHART_TOP" 1162 "$BOOK_DETAIL_CHART_H";;
      book_month_next) shift_book_month 1 || fallback_to_legacy; perform_draw book_month_next 0 3 55 "$BOOK_DETAIL_CHART_TOP" 1162 "$BOOK_DETAIL_CHART_H";;
      book_day_*) book_calendar_day="${action#book_day_}"; book_calendar_selected_date="$(printf '%04d-%02d-%02d' "$book_calendar_y" "$book_calendar_m" "$book_calendar_day")"; perform_draw book_calendar_select 0 3 55 "$BOOK_DETAIL_CHART_TOP" 1162 "$BOOK_DETAIL_CHART_H";;
      book_calendar_clear) if [ -n "$book_calendar_selected_date" ]; then book_calendar_selected_date=""; perform_draw book_calendar_clear 0 3 55 "$BOOK_DETAIL_CHART_TOP" 1162 "$BOOK_DETAIL_CHART_H"; else metric_begin book_calendar_clear_noop; metric_end none 0 0; fi;;
      month_prev) shift_month -1; perform_draw month_previous 0 1 55 320 1162 1308;;
      month_next) shift_month 1; perform_draw month_next 0 1 55 320 1162 1308;;
      day_detail_open) open_day_detail "$selected_date" daily || fallback_to_legacy;;
      day_detail_prev) if [ "$day_detail_page" -gt 1 ]; then day_detail_page=$((day_detail_page-1)); perform_draw day_detail_previous 0 2 55 560 1162 1080; else metric_begin day_detail_previous_noop; metric_end none 0 0; fi;;
      day_detail_next) if [ "$day_detail_page" -lt "$day_detail_pages" ]; then day_detail_page=$((day_detail_page+1)); perform_draw day_detail_next 0 2 55 560 1162 1080; else metric_begin day_detail_next_noop; metric_end none 0 0; fi;;
      day_detail_back) mode="$day_detail_source"; perform_draw day_detail_back 1 1 0 0 1272 1696;;
      day_*) new_day="${action#day_}"; new_date="$(printf '%04d-%02d-%02d' "$daily_y" "$daily_m" "$new_day")"; if [ "$new_date" = "$selected_date" ]; then open_day_detail "$selected_date" daily || fallback_to_legacy; else set_selected_date "$new_date" || fallback_to_legacy; detail_page=1; perform_draw date_select 0 0 55 460 1162 1168; fi;;
      week_day_*) week_index="${action#week_day_}"; week_date="$(awk -F '\t' -v n="$((week_index+1))" 'NR==n{print $1;exit}' "$WEEK_VIEW")"; [ -n "$week_date" ] && open_day_detail "$week_date" total || { metric_begin week_day_invalid; metric_end none 0 0; };;
      detail_prev) if [ "$detail_page" -gt 1 ]; then detail_page=$((detail_page-1)); perform_draw detail_previous 0 2 70 "$DETAIL_TOP" 1132 "$DETAIL_H"; else metric_begin detail_previous_noop; metric_end none 0 0; fi;;
      detail_next) if [ "$detail_page" -lt "$detail_pages" ]; then detail_page=$((detail_page+1)); perform_draw detail_next 0 2 70 "$DETAIL_TOP" 1132 "$DETAIL_H"; else metric_begin detail_next_noop; metric_end none 0 0; fi;;
      books_7d|books_month|books_year) new_filter="${action#books_}"; if [ "$book_filter" = "$new_filter" ]; then metric_begin book_filter_noop; metric_end none 0 0; else book_filter="$new_filter"; book_page=1; perform_draw book_filter_change 0 0 55 285 1162 1275; fi;;
      page_prev) if [ "$book_page" -gt 1 ]; then book_page=$((book_page-1)); perform_draw book_page_previous 0 0 70 345 1132 1215; else metric_begin page_previous_noop; metric_end none 0 0; fi;;
      page_next) pages="$(book_pages)"; if [ "$book_page" -lt "$pages" ]; then book_page=$((book_page+1)); perform_draw book_page_next 0 0 70 345 1132 1215; else metric_begin page_next_noop; metric_end none 0 0; fi;;
      book_row_*) open_row="${action#book_row_}"; open_book_detail "$open_row"; open_result=$?; if [ "$open_result" -eq 1 ]; then fallback_to_legacy; elif [ "$open_result" -eq 2 ]; then metric_begin book_row_empty; metric_end none 0 0; fi;;
      *) metric_begin unknown_action; metric_end none 0 0;;
    esac
done

echo "$(date): optimized dashboard closed"
exit 0
