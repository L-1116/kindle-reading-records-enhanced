#!/bin/sh
# Optional path around the unchanged foreground sampler; all hot state is /tmp.
idle_pid=''; idle_birth=''; idle_dir=''; idle_active=0; idle_failed=0; idle_seen=0; idle_paused=0; idle_launch=0
idle_remove_files() {
    if [ -n "$idle_dir" ]; then rm -f "$idle_dir/snapshot" "$idle_dir/snapshot.new" "$idle_dir/touch-last.log" "$idle_dir/events" "$idle_dir/probe" "$idle_dir/error" "$idle_dir/owner-pipe" "$idle_dir/listener.pid"; rmdir "$idle_dir" 2>/dev/null || true; fi
}
idle_guard_stat() {
    [ -n "$idle_pid" ] && IFS= read -r idle_stat 2>/dev/null < "/proc/$idle_pid/stat" || return 1
    idle_stat="${idle_stat##*) }"; set -- $idle_stat
    [ "$1" != Z ] && [ "$2" = "$$" ] || return 1
    idle_stat_birth="${20}"
}
idle_guard_alive() {
    idle_guard_stat && [ -n "$idle_birth" ] && [ "$idle_birth" = "$idle_stat_birth" ]
}
idle_stop_orphan() {
    # If only the guard was killed, retain enough private identity to stop its
    # reader without targeting a reused PID. No full process census is needed.
    [ -n "$idle_dir" ] && IFS=' ' read -r idle_orphan idle_orphan_birth 2>/dev/null < "$idle_dir/listener.pid" || return 0
    case "$idle_orphan:$idle_orphan_birth" in *[!0-9:]*|:*|*:) return 0;; esac
    IFS= read -r idle_stat 2>/dev/null < "/proc/$idle_orphan/stat" || return 0
    idle_stat="${idle_stat##*) }"; set -- $idle_stat
    [ "${20}" != "$idle_orphan_birth" ] || kill "$idle_orphan" 2>/dev/null || true
}
idle_stop() {
    [ "$idle_launch" = 0 ] || idle_pid=$!
    idle_launch=0
    exec 8<&- 9>&-
    if [ -n "$idle_pid" ]; then
        idle_guard_alive && kill "$idle_pid" 2>/dev/null || true
        wait "$idle_pid" 2>/dev/null || true
    fi
    idle_stop_orphan
    idle_pid=''; idle_birth=''; idle_active=0
    idle_remove_files
    idle_dir=''
}
idle_diagnostic() {
    idle_error=''
    [ -z "$idle_dir" ] || idle_error="$(awk 'NR==1{print substr($0,1,160);exit}' "$idle_dir/error" 2>/dev/null)"
    printf '%s: idle pause unavailable (%s); foreground timing retained; %s\n' "$(date)" "$1" "$idle_error" >> "$LOG"
    idle_failed=1; idle_stop
}
idle_start() {
    idle_dir="$(mktemp -d /tmp/reading-idle.XXXXXX)" || return 1
    chmod 700 "$idle_dir" || return 1
    : > "$idle_dir/events"
    for ep in "${READING_INPUT_SYSFS:-/sys/class/input}"/event*; do [ ! -d "$ep" ] || printf '%s\n' "${ep##*/}" >> "$idle_dir/events"; done
    idle_lua_found=0; idle_lua_seen=':'
    for idle_candidate in "${idle_lua:-}" "$(command -v lua 2>/dev/null)" /mnt/us/libkh/bin/lua /usr/bin/lua /usr/local/bin/lua; do
        [ -n "$idle_candidate" ] && [ -x "$idle_candidate" ] || continue
        case "$idle_lua_seen" in *:"$idle_candidate":*) continue;; esac
        idle_lua_seen="$idle_lua_seen$idle_candidate:"
        if READING_TOUCH_REQUIRE_CONTACT=1 READING_TOUCH_MACHINE="$(uname -m)" "$idle_candidate" "$IDLE_HELPERS/reading-insights-touch-probe.lua" "$idle_dir" "$idle_dir/events" > "$idle_dir/probe" 2> "$idle_dir/error"; then
            idle_lua="$idle_candidate"; idle_lua_found=1; break
        fi
    done
    [ "$idle_lua_found" = 1 ] || return 1
    idle_device="$(sed -n '1p' "$idle_dir/probe")"; idle_size="$(sed -n '2p' "$idle_dir/probe")"
    case "$idle_size" in 16|24) :;; *) return 1;; esac
    # Seed before launch so startup never needs a polling loop.
    printf '%s 0 %s 0\n' "$now" "$today" > "$idle_dir/snapshot" || return 1
    # A blocked pipe guard gets EOF even if this daemon is SIGKILLed. Both
    # descriptors are opened before forking, avoiding an open()/death race.
    mkfifo "$idle_dir/owner-pipe" || return 1
    exec 9<>"$idle_dir/owner-pipe" || return 1
    exec 8<"$idle_dir/owner-pipe" || return 1
    idle_launch=1
    /bin/sh "$IDLE_HELPERS/reading-idle.sh" --guard "$idle_dir" "$idle_lua" "$idle_device" "$idle_size" "$now" "$((idle_minutes*60))" &
    idle_pid=$!; idle_launch=0; exec 8<&-
    idle_guard_stat || return 1
    idle_birth="$idle_stat_birth"
    idle_active=1; idle_seen=0; idle_paused=0
    idle_id="$book_id"; idle_title="$book_title"; idle_date="$today"
    idle_limit="$idle_minutes"
}
idle_save_credit() {
    # Read one atomic four-field snapshot; never source data as shell code.
    IFS=' ' read -r idle_last idle_closed idle_day idle_day_closed < "$idle_dir/snapshot" || return 1
    case "$idle_last:$idle_closed:$idle_day_closed" in *[!0-9:]*|:*|*::*) return 1;; esac
    # LIPC queries may straddle a second (or midnight) after the sampler's
    # timestamp. A newly published touch is then newer than that timestamp.
    if [ "$now" -lt "$idle_last" ]; then now="$(date +%s)"; today="$(date +%Y-%m-%d)"; fi
    [ "$now" -ge "$idle_last" ] || return 1
    idle_end="$now"; idle_boundary=$((idle_last+idle_limit*60))
    [ "$idle_end" -le "$idle_boundary" ] || idle_end="$idle_boundary"
    idle_total=$((idle_closed+idle_end-idle_last)); idle_credit=$((idle_total-idle_seen))
    [ "$idle_credit" -ge 0 ] || return 1
    idle_today_closed=0; [ "$idle_day" != "$today" ] || idle_today_closed="$idle_day_closed"
    if [ "${idle_midnight_date:-}" != "$today" ]; then
        idle_midnight="$(date -d "$today 00:00:00" +%s)" || return 1
        idle_midnight_date="$today"
    fi
    idle_day_start="$idle_last"; [ "$idle_day_start" -ge "$idle_midnight" ] || idle_day_start="$idle_midnight"
    idle_today_total="$idle_today_closed"
    [ "$idle_end" -le "$idle_day_start" ] || idle_today_total=$((idle_today_total+idle_end-idle_day_start))
    if [ "$idle_date" != "$today" ]; then
        idle_old_credit=$((idle_credit-idle_today_total))
        [ "$idle_old_credit" -le 0 ] || { bucket_id="$idle_id"; bucket_title="$idle_title"; bucket_date="$idle_date"; bucket=$((bucket+idle_old_credit)); }
        flush; idle_credit="$idle_today_total"; idle_date="$today"
    fi
    bucket_id="$idle_id"; bucket_title="$idle_title"; bucket_date="$today"; bucket=$((bucket+idle_credit)); idle_seen="$idle_total"
    if [ "$now" -ge "$idle_boundary" ]; then
        service_state="无操作暂停"
        if [ "$idle_paused" = 0 ]; then flush; write_report; idle_paused=1; fi
    else service_state="正在阅读"; idle_paused=0; fi
    if [ "$bucket" -ge "$SAVE_INTERVAL" ]; then flush; write_report; fi
}
idle_dispatch() {
    rr_config_read
    # After a diagnosed failure, the original sampler owns this session.
    # Do not duplicate its book queries or retry the failed runtime every tick.
    if [ "$reader" = 1 ] && [ "$idle_enabled" = 1 ] && [ "$idle_active" = 0 ] && [ "$idle_failed" = 1 ]; then return 1; fi
    if [ "$reader" = 1 ]; then
        if [ "$idle_enabled" = 1 ] || [ "$idle_active" = 1 ]; then
            context="$(prop com.lab126.appmgrd activeContext)"; metadata="$(prop com.lab126.yjr.annotations getCurrentBookMetadata)"; read_book "$context" "$metadata"
        fi
    else idle_failed=0; fi
    if [ "$idle_active" = 1 ]; then
        if ! idle_guard_alive; then
            flush; idle_diagnostic listener_exit; was_reader=0; delta=0
        elif [ "$delta" -lt 0 ] || [ "$delta" -gt 15 ]; then
            flush; idle_stop; was_reader=0; delta=0
        else
            idle_save_credit || { flush; idle_diagnostic invalid_snapshot; was_reader=0; delta=0; }
        fi
    fi
    if [ "$idle_active" = 1 ]; then
        if [ "$reader" != 1 ] || [ "$book_id" != "$idle_id" ] || [ "$idle_enabled" != 1 ] || [ "$idle_minutes" != "$idle_limit" ]; then
            flush; idle_stop; write_report; was_reader=0; delta=0
        fi
    fi
    if [ "$idle_enabled" != 1 ]; then idle_failed=0; return 1; fi
    if [ "$reader" != 1 ]; then return 1; fi
    [ "$idle_failed" = 0 ] || return 1
    if [ "$idle_active" = 0 ]; then
        flush
        idle_start || { idle_diagnostic probe_or_runtime; was_reader=0; delta=0; return 1; }
        service_state="正在阅读"
    fi
    current_id="$book_id"; current_title="$book_title"; interval="$READING_INTERVAL"
    return 0
}

# Run the guard as a distinct executable, so the existing service census sees
# only one native-reading-time-daemon.sh process during recovery and upgrades.
if [ "${1:-}" = --guard ]; then
    idle_dir="$2"; idle_lua="$3"; idle_device="$4"; idle_size="$5"; now="$6"; idle_guard_timeout="$7"
    IDLE_HELPERS="${0%/*}"
    # The guard creates and reaps its reader. Thus a daemon dying during
    # launch cannot leave a reader behind before a sibling guard exists.
    trap - INT TERM HUP EXIT CHLD
    exec 9>&-
    idle_child=''; idle_owner_gone=0
    idle_guard_cleanup() {
        trap - CHLD; trap '' INT TERM HUP
        [ -n "$idle_child" ] || idle_child=$!
        if [ -n "$idle_child" ]; then kill "$idle_child" 2>/dev/null || true; wait "$idle_child" 2>/dev/null || true; fi
        [ "$idle_owner_gone" = 0 ] || idle_remove_files
    }
    trap idle_guard_cleanup EXIT
    trap 'exit 0' INT TERM HUP
    trap 'exit 2' CHLD
    "$idle_lua" "$IDLE_HELPERS/reading-idle-touch.lua" "$idle_device" "$idle_size" "$idle_dir/snapshot" "$now" "$idle_guard_timeout" 8<&- 2> "$idle_dir/error" &
    idle_child=$!
    idle_record_child() {
        IFS= read -r idle_child_stat < "/proc/$idle_child/stat" || return 1
        idle_child_stat="${idle_child_stat##*) }"; set -- $idle_child_stat
        printf '%s %s\n' "$idle_child" "${20}" > "$idle_dir/listener.pid"
    }
    idle_record_child || exit 2
    IFS= read -r idle_owner_end <&8
    idle_owner_gone=1
    exit 0
fi
