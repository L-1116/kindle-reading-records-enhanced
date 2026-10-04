#!/bin/sh
# Only owns this UI's direct child (Lua reader or legacy UI), never system input.
UI_CHILD=
stop_ui_child() {
    if [ -n "$UI_CHILD" ]; then
        kill -TERM "$UI_CHILD" 2>/dev/null || true
        wait "$UI_CHILD" 2>/dev/null || true
        UI_CHILD=
    fi
}
read_touch_action() {
    lua "$@" > "$SESSION_DIR/touch-action" &
    UI_CHILD=$!
    wait "$UI_CHILD"; touch_result=$?; UI_CHILD=
    [ "$touch_result" -eq 0 ] || fail "触摸监听器异常退出"
    action="$(cat "$SESSION_DIR/touch-action")"
}
