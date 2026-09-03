#!/bin/sh

BASE="/mnt/us/reading-time"
DATA="$BASE/reading-time.tsv"
STATE="$BASE/state"
REPORT="$BASE/阅读时长统计.txt"
LOG="$BASE/service.log"
READING_INTERVAL=5
ACTIVE_INTERVAL=5
LOCKED_INTERVAL=60
SAVE_INTERVAL=90
STATE_INTERVAL=90
EDGE_CREDIT_MAX=5

mkdir -p "$BASE"
umask 077
[ -f "$DATA" ] || printf 'date\tbook_id\tseconds\ttitle\n' > "$DATA"

prop() { lipc-get-prop "$1" "$2" 2>/dev/null; }

decode_url() {
    printf '%s\n' "$1" | awk '
    function hex(c) { return index("0123456789ABCDEF", toupper(c)) - 1 }
    { out=""; for(i=1;i<=length($0);i++){ c=substr($0,i,1); if(c=="%"&&i+2<=length($0)){h1=hex(substr($0,i+1,1));h2=hex(substr($0,i+2,1));if(h1>=0&&h2>=0){out=out sprintf("%c",h1*16+h2);i+=2}else out=out c}else if(c=="+")out=out " ";else out=out c} print out }'
}

read_book() {
    context="$1"
    metadata="$2"
    book_id="$(printf '%s' "$metadata" | sed -n 's/.*"cdeKey":"\([^"]*\)".*/\1/p')"
    [ -n "$book_id" ] || book_id="$(printf '%s' "$context" | sed -n 's/.*_\([A-Fa-f0-9][A-Fa-f0-9]*\)\.kfx.*/\1/p')"
    [ -n "$book_id" ] || book_id="unknown"
    encoded="$(printf '%s' "$context" | sed -n 's|.*file://\([^?]*\).*|\1|p')"
    decoded="$(decode_url "$encoded")"
    book_title="${decoded##*/}"
    book_title="$(printf '%s' "$book_title" | sed "s/_${book_id}\.kfx$//;s/\.kfx$//;s/[\t\r\n]/ /g")"
    [ -n "$book_title" ] || book_title="$book_id"
}

format_time() {
    n="$1"; h=$((n/3600)); m=$(((n%3600)/60)); s=$((n%60))
    if [ "$h" -gt 0 ]; then printf '%dh %dm' "$h" "$m"; elif [ "$m" -gt 0 ]; then printf '%dm %ds' "$m" "$s"; else printf '%ds' "$s"; fi
}


write_report() {
    report_total="$(awk -F '\t' 'NR>1{s+=$3}END{print s+0}' "$DATA")"
    report_today="$(awk -F '\t' -v d="$(date +%Y-%m-%d)" 'NR>1&&$1==d{s+=$3}END{print s+0}' "$DATA")"
    {
        echo "Kindle 原生阅读时长统计"
        echo "更新时间：$(date)"
        echo "服务状态：运行中（PID $$）"
        echo "当前状态：$service_state"
        echo "计时方式：原生阅读器前台且屏幕亮起"
        echo "今日阅读：$(format_time "$report_today")"
        echo "累计阅读：$(format_time "$report_total")"
        echo
        echo "按书籍统计："
        awk -F '\t' '
            function is_code(t) { return length(t) >= 16 && t !~ /[^0-9A-Fa-f]/ }
            function usable(t, id) { return t != "" && t != "unknown" && t != id && !is_code(t) }
            NR > 1 {
                id = $2
                key = (id == "" || id == "unknown") ? id SUBSEP $4 : id
                seconds[key] += $3
                book_id[key] = id
                if (!(key in title) || (!usable(title[key], id) && usable($4, id))) title[key] = $4
            }
            END {
                for (key in seconds) {
                    name = title[key]
                    if (!usable(name, book_id[key])) name = book_id[key]
                    print seconds[key] "\t" name "\t" book_id[key]
                }
            }' "$DATA" | sort -nr | awk -F '\t' '{h=int($1/3600);m=int(($1%3600)/60);s=$1%60;if(h>0)t=h"h "m"m";else if(m>0)t=m"m "s"s";else t=s"s";print "- "$2": "t" ("$3")"}'
    } > "$REPORT.tmp" && mv "$REPORT.tmp" "$REPORT"
}

bucket=0; bucket_id=""; bucket_title=""; bucket_date=""
flush() {
    if [ "$bucket" -gt 0 ] && [ -n "$bucket_id" ]; then
        printf '%s\t%s\t%s\t%s\n' "$bucket_date" "$bucket_id" "$bucket" "$bucket_title" >> "$DATA"
    fi
    bucket=0; bucket_id=""; bucket_title=""; bucket_date=""
}
cleanup() { flush; service_state="已停止"; write_report; }
trap 'cleanup; trap - INT TERM HUP EXIT; exit 0' INT TERM HUP
trap cleanup EXIT

write_state() {
    state_now="$1"
    printf 'state=%s\npid=%s\napp=%s\npower=%s\nbook_id=%s\ntitle=%s\nlast_update=%s\n' "$service_state" "$$" "$app" "$power" "$current_id" "$current_title" "$state_now" > "$STATE.tmp" && mv "$STATE.tmp" "$STATE"
    last_state_write="$state_now"
}

add_edge_credit() {
    edge_delta="$1"
    edge_id="$2"
    edge_title="$3"
    edge_date="$4"
    edge_credit=$((edge_delta/2))
    [ "$edge_credit" -gt "$EDGE_CREDIT_MAX" ] && edge_credit="$EDGE_CREDIT_MAX"
    if [ "$edge_credit" -gt 0 ] && [ -n "$edge_id" ]; then
        bucket_id="$edge_id"; bucket_title="$edge_title"; bucket_date="$edge_date"
        bucket=$((bucket+edge_credit))
    fi
}

wait_next() {
    wait_mode="$1"
    wait_seconds="$2"
    if [ "$wait_mode" = "locked" ] && command -v lipc-wait-event >/dev/null 2>&1; then
        # Wake immediately with the framework instead of waiting for the full
        # locked interval. Timeout remains a low-frequency safety fallback.
        # If this firmware rejects the event syntax, sleep the remaining time
        # so a failed command can never turn into a battery-draining busy loop.
        wait_started="$(date +%s)"
        if ! lipc-wait-event -s "$wait_seconds" com.lab126.powerd outOfScreenSaver >/dev/null 2>&1; then
            wait_ended="$(date +%s)"
            wait_remaining=$((wait_seconds-(wait_ended-wait_started)))
            [ "$wait_remaining" -gt 0 ] && sleep "$wait_remaining"
        fi
    else
        sleep "$wait_seconds"
    fi
}

previous="$(date +%s)"; was_reader=0; current_id=""; current_title=""; service_state="等待阅读"; last_state=""; last_state_write=0
echo "$(date): upstart service started, pid=$$, timing=foreground-reader-active-screen" >> "$LOG"
write_report

while :; do
    now="$(date +%s)"; today="$(date +%Y-%m-%d)"
    delta=$((now-previous))
    app="$(prop com.lab126.appmgrd activeApp)"; power="$(prop com.lab126.powerd state)"
    reader=0; interval="$ACTIVE_INTERVAL"; wait_mode="active"
    [ "$app" = "com.lab126.booklet.reader" ] && [ "$power" = "active" ] && reader=1

    # Detailed book properties are intentionally skipped outside an active
    # reading session. A sleeping Kindle only gets the two lightweight
    # app/power checks above.
    if [ "$reader" -eq 1 ]; then
        interval="$READING_INTERVAL"
        context="$(prop com.lab126.appmgrd activeContext)"; metadata="$(prop com.lab126.yjr.annotations getCurrentBookMetadata)"
        read_book "$context" "$metadata"
        if [ "$was_reader" -eq 1 ] && [ -n "$current_id" ] && [ "$current_id" != "$book_id" ]; then
            # A book switch is a persistence boundary: never mix two books in
            # one bucket, and save the old book immediately.
            flush; service_state="切换书籍"; write_report
        fi
        if [ "$was_reader" -eq 0 ] || [ "$current_id" != "$book_id" ]; then
            current_id="$book_id"; current_title="$book_title"
        fi
        if [ "$was_reader" -eq 0 ]; then
            # Sampling can observe an app transition only after it happened.
            # Attribute half of the bounded interval to the new session; this
            # avoids dropping the whole leading edge without overcounting it.
            add_edge_credit "$delta" "$current_id" "$current_title" "$today"
        fi
    elif [ "$power" != "active" ]; then
        interval="$LOCKED_INTERVAL"
        wait_mode="locked"
    fi
    service_state="等待阅读"
    if [ "$was_reader" -eq 1 ] && [ "$reader" -eq 1 ] && [ "$delta" -gt 0 ] && [ "$delta" -le 15 ]; then
        # Foreground timing rule: while the native book reader is in front and
        # the screen is active, the whole interval counts as reading. This is
        # deliberately independent of page-turn, PC:TS, dialog, or touch
        # signals because those are not consistent across books and firmware.
        # Split the bucket at midnight so time lands on the correct day.
        if [ -n "$bucket_date" ] && [ "$bucket_date" != "$today" ]; then
            flush; write_report
        fi
        service_state="正在阅读"; bucket_id="$current_id"; bucket_title="$current_title"; bucket_date="$today"; bucket=$((bucket+delta))
        if [ "$bucket" -ge "$SAVE_INTERVAL" ]; then flush; write_report; fi
    elif [ "$was_reader" -eq 1 ] && [ "$reader" -eq 0 ]; then
        # Leaving the reader or locking the screen saves immediately.
        add_edge_credit "$delta" "$current_id" "$current_title" "$today"
        flush
        [ "$power" = "active" ] && service_state="已退出阅读" || service_state="锁屏暂停"
        write_report
    elif [ "$power" != "active" ]; then
        service_state="锁屏暂停"
    fi

    # Avoid the old two-second state-file write.  Persist periodically or
    # whenever the visible service state changes.
    if [ "$service_state" != "$last_state" ] || [ $((now-last_state_write)) -ge "$STATE_INTERVAL" ]; then
        write_state "$now"
        last_state="$service_state"
    fi
    previous="$now"; was_reader="$reader"; wait_next "$wait_mode" "$interval"
done
