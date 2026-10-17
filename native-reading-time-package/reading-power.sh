# Frontend-only powerd subscription. Never inhibit, request, or toggle sleep.
# goingToScreenSaver is emitted for button, hall sensor and idle timeout;
# readyToSuspend also covers a suspend already in progress during startup.
rr_power_pid=; rr_power_pending=0; rr_power_sleep=0
rr_power_init() {
    [ -z "${READING_POWER_OWNER:-}" ] || return 0
    READING_POWER_OWNER=$$; export READING_POWER_OWNER
    trap 'rr_power_sleep=1; exit 90' USR1
    trap 'echo "powerd subscription failed; closing frontend"; exit 91' USR2
}
rr_power_start() {
    [ "${READING_POWER_OWNER:-}" = "$$" ] || return 0
    command -v lipc-wait-event >/dev/null 2>&1 || return 1
    rr_power_pending=1
    (
        rr_event_pid=; rr_event_pending=0
        rr_event_stop() {
            trap '' TERM INT HUP
            [ "$rr_event_pending" = 0 ] || rr_event_pid=$!
            [ -z "$rr_event_pid" ] || {
                kill -TERM "$rr_event_pid" 2>/dev/null || true
                kill -KILL "$rr_event_pid" 2>/dev/null || true
                wait "$rr_event_pid" 2>/dev/null || true
            }
        }
        trap 'rr_event_stop; exit 0' TERM INT HUP
        rr_event_pending=1
        lipc-wait-event -s 0 com.lab126.powerd goingToScreenSaver,readyToSuspend > "$SESSION_DIR/power-event" &
        rr_event_pid=$!; rr_event_pending=0
        wait "$rr_event_pid"; rr_event_code=$?; rr_event_pid=
        if [ "$rr_event_code" = 0 ] && grep -Eq '^(goingToScreenSaver|readyToSuspend)([[:space:]]|$)' "$SESSION_DIR/power-event"; then
            kill -USR1 "$READING_POWER_OWNER" 2>/dev/null || true
        else
            kill -USR2 "$READING_POWER_OWNER" 2>/dev/null || true
        fi
    ) &
    rr_power_pid=$!; rr_power_pending=0
    # One snapshot closes the already-suspending startup case; no state polling.
    rr_power_check
    [ "$rr_power_sleep" = 0 ] || exit 90
}
rr_power_check() {
    [ "${rr_power_sleep:-0}" = 0 ] || return 0
    if grep -Eq '^(goingToScreenSaver|readyToSuspend)([[:space:]]|$)' "$SESSION_DIR/power-event" 2>/dev/null; then rr_power_sleep=1; return 0; fi
    case "$(lipc-get-prop com.lab126.powerd state 2>/dev/null)" in
        screenSaver|goingToScreenSaver|readyToSuspend|suspended) rr_power_sleep=1;;
    esac
}
rr_power_stop() {
    [ "$rr_power_pending" = 0 ] || rr_power_pid=$!
    [ -n "$rr_power_pid" ] || return 0
    # An exited helper may already have been reaped by the shell. Never signal
    # a reused PID belonging to another process.
    if awk -v owner="$$" '
        { sub(/^.*\) /, ""); split($0, fields, " "); if (fields[2]==owner) found=1 }
        END { exit !found }' "/proc/$rr_power_pid/stat" 2>/dev/null; then
        kill -TERM "$rr_power_pid" 2>/dev/null || true
    fi
    wait "$rr_power_pid" 2>/dev/null || true
    rr_power_pid=; rr_power_pending=0
}
