#!/bin/sh
# Shared UI/transaction mutex. mkdir + PID-specific owner directories only;
# no flock, recursive deletion, timeout, probe or background process.
acquire_runtime_lock() {
    LOCK_OWNER="$LOCK/owner.$$"
    [ ! -L "$LOCK" ] || return 1
    mkdir "$LOCK" 2>/dev/null || [ -d "$LOCK" ] || return 1
    LOCK_OWNED=1
    # Claim before reaping. A competing live claimant is never removed; both
    # may refuse, but cannot both enter. No stale root rename/delete ABA window.
    mkdir "$LOCK_OWNER" 2>/dev/null || return 1
    lock_had_dead_owner=0
    for lock_owner in "$LOCK"/owner.*; do
        [ "$lock_owner" != "$LOCK_OWNER" ] || continue
        lock_pid="${lock_owner##*.}"
        case "$lock_pid" in ''|0|*[!0-9]*) return 1;; esac
        kill -0 "$lock_pid" 2>/dev/null && return 1
        lock_had_dead_owner=1
        rm -f "$lock_owner/ui-start" "$lock_owner/ui-cancel" || return 1
        rmdir "$lock_owner" 2>/dev/null || return 1
    done
    set -- "$LOCK"/owner.*
    [ "$#" -eq 1 ] && [ "$1" = "$LOCK_OWNER" ] || return 1
    # Old PID-layout sessions remain excluded. Never guess that an unowned,
    # empty PID file is stale; an interrupted modern write has a dead owner.
    lock_pid="$(cat "$LOCK/pid" 2>/dev/null)"
    case "$lock_pid" in
        '') if [ -e "$LOCK/pid" ]; then
                [ "$lock_had_dead_owner" -eq 1 ] || return 1
                rm -f "$LOCK/pid" || return 1
            fi;;
        0|*[!0-9]*) return 1;;
        *) kill -0 "$lock_pid" 2>/dev/null && return 1
           rm -f "$LOCK/pid" "$LOCK/ui-start" "$LOCK/ui-cancel" || return 1;;
    esac
    # Kept for an already installed older launcher, which checks a live PID.
    printf '%s\n' "$$" > "$LOCK/pid" || return 1
}
release_runtime_lock() {
    [ "$LOCK_OWNED" -eq 1 ] || return 0
    rm -f "$LOCK_OWNER/ui-start" "$LOCK_OWNER/ui-cancel"
    if [ "$(cat "$LOCK/pid" 2>/dev/null)" = "$$" ]; then rm -f "$LOCK/pid"; fi
    rmdir "$LOCK_OWNER" 2>/dev/null || true
    rmdir "$LOCK" 2>/dev/null || true
}
