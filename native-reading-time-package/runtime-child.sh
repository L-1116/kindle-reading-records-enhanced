#!/bin/sh
# Only owns this UI's direct child (Lua reader or legacy UI), never system input.
UI_CHILD=; UI_SPAWNING=0; UI_SIGNAL=0; UI_CLEANING=0; UI_GATE_OPEN=0
runtime_child_signal() { [ "$UI_CLEANING" -eq 0 ] || return 0; UI_SIGNAL=$1; [ "$UI_SPAWNING" -eq 1 ] || exit "$1"; }
start_ui_child() {
    rm -f "$SESSION_DIR/child-start" "$SESSION_DIR/child-cancel"
    mkfifo "$SESSION_DIR/child-start" || exit 1
    exec 9<> "$SESSION_DIR/child-start" || exit 1
    UI_GATE_OPEN=1
    UI_SPAWNING=1
    (
        IFS= read -r permission <&9
        exec 9>&-
        [ "$permission" = start ] && [ ! -f "$SESSION_DIR/child-cancel" ] || exit 143
        exec "$@"
    ) &
    UI_CHILD=$!
    UI_SPAWNING=0
    [ "$UI_SIGNAL" -eq 0 ] || exit "$UI_SIGNAL"
    printf 'start\n' >&9 || exit 1
    exec 9>&-; UI_GATE_OPEN=0
    rm -f "$SESSION_DIR/child-start"
}
stop_ui_child() {
    UI_CLEANING=1
    if [ "$UI_GATE_OPEN" -eq 1 ]; then
        : > "$SESSION_DIR/child-cancel"
        printf 'cancel\n' >&9 || true
        exec 9>&-; UI_GATE_OPEN=0
    fi
    if [ -n "$UI_CHILD" ]; then
        kill -TERM "$UI_CHILD" 2>/dev/null || true
        wait "$UI_CHILD" 2>/dev/null || true
        UI_CHILD=
    fi
}
read_touch_action() {
    start_ui_child lua "$@" > "$SESSION_DIR/touch-action"
    wait "$UI_CHILD"; touch_result=$?; UI_CHILD=
    [ "$touch_result" -eq 0 ] || fail "触摸监听器异常退出"
    action="$(cat "$SESSION_DIR/touch-action")"
}
