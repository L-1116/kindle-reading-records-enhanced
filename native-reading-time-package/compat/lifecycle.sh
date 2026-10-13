#!/bin/sh
# READING_RECORDS_LIFECYCLE_V1 -- sourceable, no action on load.
# Every timeout owns and reaps only its command and timer children.
rr_run() {
    rr_seconds=$1; shift
    "$@" & rr_child=$!
    [ "${RR_PROBE_TRACK:-0}" != 1 ] || printf 'probe_child_pid=%s\n' "$rr_child"
    (
        rr_sleep=
        trap '[ -z "$rr_sleep" ] || { kill "$rr_sleep" 2>/dev/null; wait "$rr_sleep" 2>/dev/null; }; exit 0' TERM INT HUP
        "${READING_SLEEP_COMMAND:-/bin/sleep}" "$rr_seconds" & rr_sleep=$!; wait "$rr_sleep" || exit 0
        [ -z "${RR_TIMEOUT_MARKER:-}" ] || : > "$RR_TIMEOUT_MARKER"
        kill -TERM "$rr_child" 2>/dev/null || exit 0
        "${READING_SLEEP_COMMAND:-/bin/sleep}" 1 & rr_sleep=$!; wait "$rr_sleep" || exit 0
        kill -KILL "$rr_child" 2>/dev/null || true
    ) >/dev/null 2>&1 & rr_timer=$!
    wait "$rr_child"; rr_rc=$?
    kill -TERM "$rr_timer" 2>/dev/null || true
    wait "$rr_timer" 2>/dev/null || true
    rr_child=; rr_timer=
    return "$rr_rc"
}
rr_cancel() {
    rr_cancel_child=${rr_child:-}; rr_cancel_timer=${rr_timer:-}
    if [ -n "$rr_cancel_child" ]; then
        kill -TERM "$rr_cancel_child" 2>/dev/null || true
        ( "${READING_SLEEP_COMMAND:-/bin/sleep}" 2; kill -KILL "$rr_cancel_child" 2>/dev/null || true ) >/dev/null 2>&1 & rr_forcer=$!
        wait "$rr_cancel_child" 2>/dev/null || true
        kill -TERM "$rr_forcer" 2>/dev/null || true; wait "$rr_forcer" 2>/dev/null || true
    fi
    if [ -n "$rr_cancel_timer" ]; then kill -TERM "$rr_cancel_timer" 2>/dev/null || true; wait "$rr_cancel_timer" 2>/dev/null || true; fi
    rr_child=; rr_timer=
}
rr_identity() {
    case "$1" in ''|*[!0-9]*) return 1;; esac
    [ -r "${READING_LOCK_PROC_ROOT:-/proc}/$1/stat" ] || return 1
    # comm may contain spaces and parentheses; field 22 follows its last ')'.
    sed 's/.*) //' "${READING_LOCK_PROC_ROOT:-/proc}/$1/stat" | awk '{print $20}'
}
rr_lock() {
    RR_LOCK="${READING_LIFECYCLE_LOCK:-${READING_TMPDIR:-/tmp}/reading-records-lifecycle.lock}"
    RR_LOCK_OWNED=0
    [ ! -L "$RR_LOCK" ] && [ ! -L "$RR_LOCK.reap" ] || return 75
    if [ -n "${READING_LIFECYCLE_OWNER:-}" ] && [ -r "$RR_LOCK/owner" ]; then
        IFS=' ' read -r rr_owner rr_start < "$RR_LOCK/owner"
        [ "$rr_owner:$rr_start" = "$READING_LIFECYCLE_OWNER" ] &&
            [ "$(rr_identity "$rr_owner")" = "$rr_start" ] && return 0
    fi
    # The reaper gate is checked before and after mkdir. Missing owner metadata
    # is busy, never guessed stale; /tmp is cleared on a device reboot.
    [ ! -d "$RR_LOCK.reap" ] || return 75
    if ! mkdir "$RR_LOCK" 2>/dev/null; then
        [ -r "$RR_LOCK/owner" ] || return 75
        IFS=' ' read -r rr_owner rr_start < "$RR_LOCK/owner"
        case "$rr_owner:$rr_start" in *[!0-9:]*|:*) return 75;; esac
        rr_owner_current=$(rr_identity "$rr_owner")
        [ "$rr_owner_current" != "$rr_start" ] || return 75
        if [ -z "$rr_owner_current" ] && [ -d "${READING_LOCK_PROC_ROOT:-/proc}/$rr_owner" ]; then return 75; fi
        mkdir "$RR_LOCK.reap" 2>/dev/null || return 75
        # Recheck while excluding new owners. Only remove our two known files.
        if [ -r "$RR_LOCK/owner" ]; then
            IFS=' ' read -r rr_owner rr_start < "$RR_LOCK/owner"
            rr_owner_current=$(rr_identity "$rr_owner")
            if [ -n "$rr_start" ] && [ "$rr_owner_current" != "$rr_start" ] && { [ -n "$rr_owner_current" ] || [ ! -d "${READING_LOCK_PROC_ROOT:-/proc}/$rr_owner" ]; }; then
                rm -f "$RR_LOCK/owner"; rmdir "$RR_LOCK" 2>/dev/null || true
            fi
        fi
        rmdir "$RR_LOCK.reap" 2>/dev/null || true
        mkdir "$RR_LOCK" 2>/dev/null || return 75
    fi
    if [ -d "$RR_LOCK.reap" ]; then rmdir "$RR_LOCK" 2>/dev/null || true; return 75; fi
    rr_start=$(rr_identity "$$")
    [ -n "$rr_start" ] || { rmdir "$RR_LOCK"; return 75; }
    printf '%s %s\n' "$$" "$rr_start" > "$RR_LOCK/owner" || { rmdir "$RR_LOCK"; return 75; }
    READING_LIFECYCLE_OWNER="$$:$rr_start"; export READING_LIFECYCLE_OWNER
    RR_LOCK_OWNED=1
}
rr_unlock() {
    [ "${RR_LOCK_OWNED:-0}" = 1 ] || return 0
    if [ -r "$RR_LOCK/owner" ]; then
        IFS=' ' read -r rr_owner rr_start < "$RR_LOCK/owner"
        if [ "$rr_owner:$rr_start" = "${READING_LIFECYCLE_OWNER:-}" ]; then
            rm -f "$RR_LOCK/owner"; rmdir "$RR_LOCK" 2>/dev/null || true
        fi
    fi
    RR_LOCK_OWNED=0
}
rr_mount_state() {
    awk '$2=="/" { n=split($4,a,","); for(i=1;i<=n;i++) if(a[i]=="ro" || a[i]=="rw") {print a[i]; exit} }' "${READING_MOUNTS_PATH:-/proc/mounts}"
}
rr_mount_capture() {
    [ -n "${RR_ROOT_ORIGINAL:-}" ] && return 0
    RR_ROOT_ORIGINAL=$(rr_mount_state) || return 1
    case "$RR_ROOT_ORIGINAL" in ro|rw) :;; *) RR_ROOT_ORIGINAL=; return 1;; esac
}
rr_mount_set() {
    rr_mode=$1
    [ "$(rr_mount_state)" = "$rr_mode" ] && return 0
    for rr_mount_cmd in "${READING_MNTROOT_COMMAND:-mntroot}" /usr/sbin/mntroot /sbin/mntroot; do
        command -v "$rr_mount_cmd" >/dev/null 2>&1 || continue
        rr_run 2 "$rr_mount_cmd" "$rr_mode"; rr_mount_rc=$?
        printf 'mount_method=%s requested=%s exit=%s actual=%s\n' "$rr_mount_cmd" "$rr_mode" "$rr_mount_rc" "$(rr_mount_state)" >&2
        [ "$(rr_mount_state)" = "$rr_mode" ] && return 0
    done
    rr_mount_cmd=${READING_MOUNT_COMMAND:-/bin/mount}
    rr_run 2 "$rr_mount_cmd" -o "remount,$rr_mode" /; rr_mount_rc=$?
    printf 'mount_method=%s requested=%s exit=%s actual=%s\n' "$rr_mount_cmd" "$rr_mode" "$rr_mount_rc" "$(rr_mount_state)" >&2
    [ "$(rr_mount_state)" = "$rr_mode" ]
}
rr_root_rw() { rr_mount_capture && rr_mount_set rw; }
rr_root_restore() {
    [ -n "${RR_ROOT_ORIGINAL:-}" ] || return 0
    rr_mount_set "$RR_ROOT_ORIGINAL"
}
rr_initctl() {
    rr_run 2 "${READING_INITCTL:-/sbin/initctl}" "$@"
}
rr_install_helpers() {
    READING_BASE="$BASE"; export READING_BASE
    mkdir -p "$BASE/bin" "$BASE/compat" "$BASE/service" || return 1
    for rr_file in service-manager.sh; do
        cp "$PKG/$rr_file" "$BASE/bin/$rr_file.new.$$" && chmod 755 "$BASE/bin/$rr_file.new.$$" && mv "$BASE/bin/$rr_file.new.$$" "$BASE/bin/$rr_file" || return 1
    done
    cp "$PKG/compat/lifecycle.sh" "$BASE/compat/lifecycle.sh.new.$$" && chmod 644 "$BASE/compat/lifecycle.sh.new.$$" && mv "$BASE/compat/lifecycle.sh.new.$$" "$BASE/compat/lifecycle.sh" || return 1
    cp "$PKG/native-reading-time.conf" "$BASE/service/native-reading-time.conf.new.$$" && chmod 644 "$BASE/service/native-reading-time.conf.new.$$" && mv "$BASE/service/native-reading-time.conf.new.$$" "$BASE/service/native-reading-time.conf" || return 1
}
