#!/bin/sh
# Data only: never execute user.conf. Missing/invalid values keep legacy timing.
rr_config_read() {
    idle_enabled=0; idle_minutes=3
    [ -r "$BASE/user.conf" ] || return 0
    while IFS='=' read -r config_key config_value; do
        case "$config_key" in
            idle_pause_enabled) case "$config_value" in 0|1) idle_enabled="$config_value";; esac;;
            idle_pause_minutes) if rr_minutes_valid "$config_value"; then idle_minutes="$config_value"; fi;;
        esac
    done < "${BASE}/user.conf" 2>/dev/null
    return 0
}
rr_minutes_valid() {
    case "$1" in ''|0*|*[!0-9]*) return 1;; esac
    [ "${#1}" -le 4 ] && [ "$1" -le 1440 ]
}
rr_config_save() {
    rr_minutes_valid "$idle_minutes" || return 1
    case "$idle_enabled" in 0|1) :;; *) return 1;; esac
    [ ! -e "$BASE/user.conf" ] || [ -f "$BASE/user.conf" ] || return 1
    config_tmp="$BASE/user.conf.new.$$"
    (umask 077
        { if [ -f "$BASE/user.conf" ]; then
            sed '/^idle_pause_enabled=/d; /^idle_pause_minutes=/d' "$BASE/user.conf" || exit 1
          fi
          printf 'idle_pause_enabled=%s\nidle_pause_minutes=%s\n' "$idle_enabled" "$idle_minutes"
        } > "$config_tmp"
    ) && mv "$config_tmp" "$BASE/user.conf" && return 0
    rm -f "$config_tmp"; return 1
}
