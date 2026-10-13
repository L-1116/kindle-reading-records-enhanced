#!/bin/sh
# Standard touch initialization, shared by the current and legacy renderers.
# Sourced only; no framebuffer commands, input consumption or daemon changes.
standard_touch_failure() {
    printf 'error_stage=touch\n'
    lipc-set-prop com.lab126.winmgr eatTapMode 0 >/dev/null 2>&1 || true
    lipc-set-prop com.lab126.powerd preventScreenSaver "${READING_ORIGINAL_POWER:-0}" >/dev/null 2>&1 || true
    lipc-set-prop com.lab126.appmgrd start 'app://com.lab126.KPPMainApp?view=KPP_LIBRARY' >/dev/null 2>&1 || true
    fail "阅读记录触摸初始化失败，已返回书库"
}
standard_touch_preflight() {
    TOUCH_LOG="$BASE/touch-last.log"
    mkdir -p "$SESSION_DIR" || standard_touch_failure
    chmod 700 "$SESSION_DIR" 2>/dev/null || true
    [ -r "$TOUCH_PROBE" ] && [ -r "$TOUCH_READER" ] || standard_touch_failure
    command -v lua >/dev/null 2>&1 || standard_touch_failure
    if [ "${READING_LUA_PREFLIGHT:-}" != "$TOUCH_READER" ]; then
        READING_TOUCH_READER="$TOUCH_READER" lua -e 'assert(io.open and os.rename and os.exit); assert(loadfile(os.getenv("READING_TOUCH_READER")))' || standard_touch_failure
    fi
    : > "$SESSION_DIR/touch-events"
    for ep in "${READING_INPUT_SYSFS:-/sys/class/input}"/event*; do
        [ -d "$ep" ] && printf '%s\n' "${ep##*/}" >> "$SESSION_DIR/touch-events"
    done
    READING_TOUCH_FIRMWARE="${FIRMWARE_FULL:-unknown}" READING_TOUCH_MODEL="${DEVICE_TYPE:-unknown}" \
    READING_TOUCH_MACHINE="${MACHINE:-$(uname -m)}" READING_TOUCH_ARCH="${ARCH:-unknown}" \
    READING_TOUCH_SCREEN_WIDTH="$SCREEN_W" READING_TOUCH_SCREEN_HEIGHT="$SCREEN_H" \
    READING_TOUCH_ORIENTATION=portrait READING_TOUCH_VIEWPORT="${VIEW_W}x${VIEW_H}+${ORIGIN_X}+${ORIGIN_Y}" \
    READING_TOUCH_LOGICAL_SIZE="${LOGICAL_W}x${LOGICAL_H}" \
        lua "$TOUCH_PROBE" "$BASE" "$SESSION_DIR/touch-events" > "$SESSION_DIR/touch-probe" || standard_touch_failure
    TOUCH="$(sed -n '1p' "$SESSION_DIR/touch-probe")"
    EVENT_STRUCT_SIZE="$(sed -n '2p' "$SESSION_DIR/touch-probe")"
    RAW_X_MIN="$(sed -n '3p' "$SESSION_DIR/touch-probe")"
    RAW_X_MAX="$(sed -n '4p' "$SESSION_DIR/touch-probe")"
    RAW_Y_MIN="$(sed -n '5p' "$SESSION_DIR/touch-probe")"
    RAW_Y_MAX="$(sed -n '6p' "$SESSION_DIR/touch-probe")"
    TOUCH_TRANSFORM="$(sed -n '7p' "$SESSION_DIR/touch-probe")"
    [ -n "$TOUCH" ] && [ -r "$TOUCH" ] || standard_touch_failure
    case "$EVENT_STRUCT_SIZE" in 16|24) :;; *) standard_touch_failure;; esac
    rm -f "$SESSION_DIR/touch-events" "$SESSION_DIR/touch-probe"
}
standard_touch_reader_failed() {
    if [ -r "$TOUCH_LOG" ]; then
        sed '/^reader_state=/d; /^reader_exit_code=/d; /^shell_action_state=/d' "$TOUCH_LOG" > "$TOUCH_LOG.new"
        printf 'reader_state=reader_failed\nreader_exit_code=%s\nshell_action_state=reader_failed\n' "$1" >> "$TOUCH_LOG.new"
        mv "$TOUCH_LOG.new" "$TOUCH_LOG"
    fi
    fail "阅读记录触摸读取失败，已返回书库"
}
standard_touch_action_received() {
    # Persist a geometry-derived transform across per-action reader processes.
    touch_transform_last="$(sed -n 's/^last_transform=//p' "$TOUCH_LOG" 2>/dev/null)"
    case "$touch_transform_last" in direct|swap|invert_x|invert_y|invert_xy|swap_invert_x|swap_invert_y|swap_invert_xy) TOUCH_TRANSFORM="$touch_transform_last";; esac
    [ -n "$action" ] || standard_touch_reader_failed 2
    if [ -r "$TOUCH_LOG" ]; then
        sed '/^shell_action_state=/d; /^shell_last_action=/d' "$TOUCH_LOG" > "$TOUCH_LOG.new"
        printf 'shell_action_state=received\nshell_last_action=%s\n' "$action" >> "$TOUCH_LOG.new"
        mv "$TOUCH_LOG.new" "$TOUCH_LOG"
    fi
}
