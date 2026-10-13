#!/bin/sh
# READING_RECORDS_SERVICE_MANAGER_V1
# No resident monitor: launch does one check and at most one bounded repair.
BASE="${READING_BASE:-/mnt/us/reading-time}"
SELF=${READING_SERVICE_MANAGER:-$BASE/bin/service-manager.sh}
CONF="${READING_UPSTART_DIR:-/etc/upstart}/native-reading-time.conf"
CANONICAL="$BASE/service/native-reading-time.conf"
DAEMON="$BASE/bin/native-reading-time-daemon.sh"
PROC=${READING_PROC_ROOT:-/proc}
. "${READING_LIFECYCLE_LIB:-$BASE/compat/lifecycle.sh}" || exit 1
WORK="${READING_TMPDIR:-/tmp}/reading-records-service.$$"
umask 077
mkdir "$WORK" || exit 1
EVENT=
service_status=unknown; timing_status=unverified; recovery_status=not_triggered
reason=none; service_pid=; initial_status=unknown; category=E
finish() {
    finish_rc=$?
    rr_cancel
    if ! rr_root_restore >> "$WORK/mount-errors" 2>&1; then
        original_failure=$reason; recovery_status=failed; reason=mount_restore_failed; finish_rc=1
        printf 'original_failure=%s\n' "$original_failure" >> "$WORK/mount-errors"
        publish || true
        [ -z "$EVENT" ] || cp "$WORK/mount-errors" "$EVENT/mount.txt" 2>/dev/null
    fi
    if [ -n "$EVENT" ]; then
        output > "$EVENT/after.txt.new" && mv "$EVENT/after.txt.new" "$EVENT/after.txt"
        tail -c 8192 "$WORK/mount-errors" > "$EVENT/mount.txt" 2>/dev/null || true
    fi
    if [ "${LAUNCH_BUFFER_HANDED:-0}" != 1 ]; then
        case "${pre_launch_log:-}" in "$BASE"/.service-before-launch.[0-9]*) rm -f "$pre_launch_log";; esac
    fi
    case "${READING_PRE_RECOVERY_LOG:-}" in "$BASE"/.service-before-launch.[0-9]*) rm -f "$READING_PRE_RECOVERY_LOG";; esac
    rm -f "$WORK/status" "$WORK/query" "$WORK/error" "$WORK/mount-errors" "$WORK/frontend"
    rmdir "$WORK" 2>/dev/null || true
    rr_unlock
    exit "$finish_rc"
}
trap finish EXIT
trap 'rr_cancel; recovery_status=failed; reason=interrupted; exit 1' INT TERM HUP
output() {
    printf 'service_status=%s\ntiming_status=%s\nrecovery_status=%s\nreason=%s\ncategory=%s\nservice_pid=%s\ninitial_status=%s\n' \
        "$service_status" "$timing_status" "$recovery_status" "$reason" "$category" "$service_pid" "$initial_status"
}
status() {
    service_status=unknown; timing_status=unverified; reason=none; service_pid=; category=E
    if [ ! -e "$CONF" ]; then service_status=config_missing; reason=config_missing; category=A; return 2; fi
    if [ ! -r "$CONF" ]; then reason=config_unreadable; return 3; fi
    config_differs=no
    [ ! -r "$CANONICAL" ] || cmp -s "$CONF" "$CANONICAL" || config_differs=yes
    rr_run "${READING_STATUS_TIMEOUT:-2}" "${READING_INITCTL:-/sbin/initctl}" status native-reading-time > "$WORK/status" 2> "$WORK/error"; status_rc=$?
    case "$(cat "$WORK/status")" in
        *'start/running, process '*)
            service_pid=$(sed -n 's/.*start\/running, process \([0-9][0-9]*\).*/\1/p' "$WORK/status")
            if [ "$status_rc" != 0 ] || [ -z "$service_pid" ] || [ ! -r "$PROC/$service_pid/cmdline" ]; then
                reason=process_identity_unavailable; category=B; return 3
            fi
            if ! tr '\000' '\n' < "$PROC/$service_pid/cmdline" | grep -Fxq "$DAEMON"; then
                reason=process_identity_mismatch; category=B; return 3
            fi
            if [ ! -r "$PROC/$service_pid/stat" ] || grep -Eq '\) [ZX] ' "$PROC/$service_pid/stat"; then reason=process_identity_unavailable; return 3; fi
            service_status=healthy
            # Observations are accepted only from this instance, never a stale
            # PID/state file or a lack of reading-time growth on the Home page.
            if [ -r "$BASE/timing-observation.txt" ] && grep -Fqx "pid=$service_pid" "$BASE/timing-observation.txt" &&
                grep -Fqx "start_ticks=$(sed 's/.*) //' "$PROC/$service_pid/stat" | awk '{print $20}')" "$BASE/timing-observation.txt"; then
                case "$(sed -n 's/^error=//p' "$BASE/timing-observation.txt")" in
                    write_failed) timing_status=write_error; category=D; reason=write_failed;;
                    property_failed) reason=property_failed; category=E;;
                esac
            fi
            return 0;;
        *'stop/waiting'*) [ "$status_rc" = 0 ] || return 3; service_status=stopped; reason=service_stopped; [ "$config_differs" != yes ] || reason=config_mismatch; category=B; return 2;;
        *)
            if grep -Fq 'Unknown job: native-reading-time' "$WORK/error"; then
                service_status=stopped; reason=config_not_loaded; category=B
                [ "$config_differs" != yes ] || reason=config_mismatch
                return 2
            fi
            reason=service_query_failed; return 3;;
    esac
}
instances() {
    # Full process census is installation/recovery-only, not a per-page or
    # normal-launch scan. Refuse to start beside an unmanaged historical daemon.
    daemon_count=0; unmanaged_count=0
    if [ "$service_status" = config_missing ]; then
        rr_initctl status native-reading-time > "$WORK/status" 2> "$WORK/error"
        if [ "$?" = 0 ]; then
            service_pid=$(sed -n 's/.*start\/running, process \([0-9][0-9]*\).*/\1/p' "$WORK/status")
        fi
    fi
    for rr_proc in "$PROC"/[0-9]*; do
        [ -d "$rr_proc" ] || continue
        [ -r "$rr_proc/cmdline" ] || { reason=process_census_unavailable; return 3; }
        if tr '\000' '\n' < "$rr_proc/cmdline" | grep -Eq '(^|/)native-reading-time-daemon\.sh$'; then
            if [ -r "$rr_proc/stat" ] && ! grep -Eq '\) [ZX] ' "$rr_proc/stat"; then
                daemon_count=$((daemon_count+1))
                [ "${rr_proc##*/}" = "$service_pid" ] || unmanaged_count=$((unmanaged_count+1))
            fi
        fi
    done
    if [ "$daemon_count" -gt 1 ] || [ "$unmanaged_count" -gt 0 ]; then
        service_status=unknown; reason=duplicate_or_unmanaged_daemon; category=B; return 3
    fi
    return 0
}
evidence() {
    evidence_root="$BASE/service-events"
    [ ! -L "$evidence_root" ] || return 1
    mkdir -p "$evidence_root" || return 1
    event_slot=$(cat "$evidence_root/next" 2>/dev/null)
    case "$event_slot" in 0|1|2|3|4) :;; *) event_slot=0;; esac
    event_target="$evidence_root/event-$event_slot"
    if [ -d "$event_target" ]; then
        [ ! -L "$event_target" ] && [ ! -L "$event_target/owned" ] && grep -Fqx 'READING_RECORDS_SERVICE_EVENT_V1' "$event_target/owned" || return 1
        # Check the whole group before deleting anything; unknown user files
        # and symlinks are never rotated or overwritten by the EXIT handler.
        for event_entry in "$event_target"/* "$event_target"/.[!.]* "$event_target"/..?*; do
            [ -e "$event_entry" ] || [ -L "$event_entry" ] || continue
            [ ! -L "$event_entry" ] && [ -f "$event_entry" ] || return 1
            case "${event_entry##*/}" in before.txt|after.txt|original.conf|mount.txt|owned|before.txt.new|after.txt.new) :;; *) return 1;; esac
        done
        rm -f "$event_target/before.txt" "$event_target/after.txt" "$event_target/original.conf" "$event_target/mount.txt" "$event_target/owned" "$event_target/before.txt.new" "$event_target/after.txt.new"
        rmdir "$event_target" || return 1
    fi
    mkdir "$event_target" && printf 'READING_RECORDS_SERVICE_EVENT_V1\n' > "$event_target/owned" || return 1
    EVENT="$event_target"
    firmware=unknown; firmware_source=unknown; firmware_raw=
    for firmware_file in "${READING_PRETTYVERSION_PATH:-/etc/prettyversion.txt}" "${READING_VERSION_PATH:-/etc/version.txt}"; do
        [ -r "$firmware_file" ] || continue
        firmware_raw=$(head -c 512 "$firmware_file")
        firmware=$(printf '%s\n' "$firmware_raw" | sed -n 's/.*\(5\.[0-9][0-9.]*\).*/\1/p' | head -n 1)
        [ -z "$firmware" ] || { firmware_source=$firmware_file; break; }
    done
    variant=${READING_VARIANT:-unknown}
    [ ! -r "$BASE/release-info" ] || variant=$(sed -n 's/^variant=//p' "$BASE/release-info" | head -n 1)
    {
        printf 'timestamp=%s\nfirmware=%s\nfirmware_source=%s\nfirmware_raw=%s\nvariant=%s\nconfig_exists=%s\nroot_mount=%s\n' \
            "$(date +%s)" "${firmware:-unknown}" "$firmware_source" "$firmware_raw" "$variant" "$([ -e "$CONF" ] && echo yes || echo no)" "$(rr_mount_state)"
        output
        if [ -n "${READING_PRE_RECOVERY_LOG:-}" ]; then
            printf '\n[launch log preserved before UI log initialization]\n'
            [ -r "$READING_PRE_RECOVERY_LOG" ] && head -c 17408 "$READING_PRE_RECOVERY_LOG" || return 1
        fi
        for evidence_file in state timing-observation.txt launch-last.log touch-last.log service.log upstart.log install.log; do
            printf '\n[%s before recovery]\n' "$evidence_file"
            [ ! -r "$BASE/$evidence_file" ] || tail -c 8192 "$BASE/$evidence_file"
        done
        printf '\n[history metadata; no full TSV scan]\n'
        ls -ld "$BASE" "$BASE/reading-time.tsv" 2>&1
        printf '\n[query stderr]\n'; tail -c 4096 "$WORK/error" 2>/dev/null || true
    } > "$EVENT/before.txt.new" && mv "$EVENT/before.txt.new" "$EVENT/before.txt" || return 1
    if [ -e "$CONF" ]; then
        [ -f "$CONF" ] && [ ! -L "$CONF" ] || return 1
        [ "$(wc -c < "$CONF")" -le 16384 ] || return 1
        cp "$CONF" "$EVENT/original.conf" || return 1
    fi
    printf '%s\n' "$(((event_slot+1)%5))" > "$evidence_root/next.new.$$" && mv "$evidence_root/next.new.$$" "$evidence_root/next" || return 1
}
publish() {
    output > "$BASE/service-status.txt.new.$$" && mv "$BASE/service-status.txt.new.$$" "$BASE/service-status.txt"
}
notify() {
    case "$service_status:$reason" in
        healthy:none) message='计时服务已恢复；实际计时尚未验证';;
        healthy:*) message='计时服务已运行，计时状态异常或未确认';;
        stopped:*) message='计时服务未运行，仍可查看历史统计';;
        config_missing:*) message='计时服务配置缺失，仍可查看历史统计';;
        *) message='无法确认计时服务状态，仍可查看历史统计';;
    esac
    rr_run 1 lipc-set-prop com.lab126.system toasterMessage "$message" >/dev/null 2>&1 || true
}
ensure() {
    rr_lock || { recovery_status=busy; reason=lifecycle_busy; output; return 75; }
    status; initial_status=$service_status
    instances || { evidence || true; recovery_status=not_triggered; publish; output; return 1; }
    if [ "$service_status" = healthy ] && [ "$reason" = none ]; then output; return 0; fi
    recovery_status=not_triggered
    evidence || { EVENT=; reason=evidence_unavailable; recovery_status=failed; publish; output; return 1; }
    if [ "$service_status" = healthy ]; then publish; output; return 0; fi
    case "$service_status:$reason" in
        config_missing:*|unknown:config_mismatch|stopped:*) :;;
        *) publish; output; return 1;;
    esac
    [ -x "$DAEMON" ] && [ -r "$CANONICAL" ] || { reason=recovery_source_missing; recovery_status=failed; publish; output; return 1; }
    recovery_status=processing
    if [ "$service_status" = config_missing ] || [ "$reason" = config_mismatch ]; then
        # Never replace a symlink or another application's job.
        if [ -e "$CONF" ] && ! grep -Fq '/reading-time/bin/native-reading-time-daemon.sh' "$CONF"; then
            reason=config_ownership_unknown; recovery_status=failed; publish; output; return 1
        fi
        rr_root_rw >> "$WORK/mount-errors" 2>&1 || { reason=mount_failed; recovery_status=failed; publish; output; return 1; }
        cp "$CANONICAL" "$CONF.new.$$" && chmod 644 "$CONF.new.$$" && mv "$CONF.new.$$" "$CONF" || { reason=config_restore_failed; recovery_status=failed; publish; output; return 1; }
        printf 'operation=restore_config\n' >> "$EVENT/before.txt"
        rr_initctl reload-configuration > "$WORK/query" 2> "$WORK/error"; reload_rc=$?
        printf 'operation=reload_configuration exit=%s\n' "$reload_rc" >> "$EVENT/before.txt"
        head -c 4096 "$WORK/query" >> "$EVENT/before.txt"; head -c 4096 "$WORK/error" >> "$EVENT/before.txt"
        [ "$reload_rc" = 0 ] || { reason=config_reload_failed; recovery_status=failed; publish; output; return 1; }
        rr_root_restore >> "$WORK/mount-errors" 2>&1 || { reason=mount_restore_failed; recovery_status=failed; publish; output; return 1; }
    fi
    if [ "$reason" = config_not_loaded ]; then
        rr_initctl reload-configuration > "$WORK/query" 2> "$WORK/error"; reload_rc=$?
        printf 'operation=reload_existing_configuration exit=%s\n' "$reload_rc" >> "$EVENT/before.txt"
        head -c 4096 "$WORK/error" >> "$EVENT/before.txt"
        [ "$reload_rc" = 0 ] || { reason=config_reload_failed; recovery_status=failed; publish; output; return 1; }
    fi
    status
    instances || { recovery_status=failed; publish; output; return 1; }
    if [ "$service_status" = healthy ]; then recovery_status=success; publish; output; return 0; fi
    rr_initctl start native-reading-time > "$WORK/query" 2> "$WORK/error"; start_rc=$?
    head -c 4096 "$WORK/query" >> "$EVENT/before.txt"; head -c 4096 "$WORK/error" >> "$EVENT/before.txt"
    printf 'operation=start_service exit=%s\n' "$start_rc" >> "$EVENT/before.txt"
    status
    if [ "$service_status" != healthy ] && [ "$start_rc" = 0 ]; then
        /bin/sleep 1
        status
    fi
    if [ "$service_status" = healthy ]; then recovery_status=success
    else recovery_status=failed; reason=service_start_failed; category=B; fi
    publish; output
    [ "$recovery_status" = success ]
}
case "${1:-status}" in
    audit) status; rc=$?; instances || rc=3; output; printf 'daemon_instances=%s\nunmanaged_instances=%s\n' "$daemon_count" "$unmanaged_count"; exit "$rc";;
    status) status; rc=$?; output; exit "$rc";;
    ensure) ensure; rc=$?; [ "${2:-}" != --notify ] || notify; exit "$rc";;
    launch)
        # The caller owns the foreground timer. A short status check never
        # modifies configuration, history or persistent diagnostic logs.
        # Same identity check in this process, with a one-second command bound.
        # Avoid recursively launching another manager and allocating another WORK.
        READING_STATUS_TIMEOUT=1
        status
        if [ "$service_status" = healthy ] && [ "$reason" = none ]; then exit 0; fi
        # A bounded one-shot wrapper survives Scriptlet UI unloading. It is
        # not a monitor and cannot start a daemon outside Upstart.
        pre_launch_log="$BASE/.service-before-launch.$$"
        {
            for previous_log in launch-last.log touch-last.log last-launch.stdout last-launch.stderr; do
                printf '\n[%s before UI initialization]\n' "$previous_log"
                [ ! -r "$BASE/$previous_log" ] || tail -c 4096 "$BASE/$previous_log" || exit 1
            done
        } > "$pre_launch_log" || exit 1
        READING_PRE_RECOVERY_LOG="$pre_launch_log" nohup /bin/sh "$SELF" bounded-ensure >/dev/null 2>&1 < /dev/null &
        LAUNCH_BUFFER_HANDED=1
        exit 0;;
    bounded-ensure)
        rr_run 11 /bin/sh "$SELF" ensure --notify; exit $?;;
    verify-install)
        status; rc=$?
        instances || rc=3
        output
        printf 'daemon_instances=%s\nunmanaged_instances=%s\n' "$daemon_count" "$unmanaged_count"
        # Availability in a Scriptlet is not a native-reader recognition test.
        printf 'reader_detection=not_tested\nactual_tsv_write=not_tested\n'
        for reading_endpoint in app power; do
            if [ "$reading_endpoint" = app ]; then reading_provider=com.lab126.appmgrd; reading_property=activeApp
            else reading_provider=com.lab126.powerd; reading_property=state; fi
            rr_run 2 lipc-get-prop "$reading_provider" "$reading_property" > "$WORK/query" 2> "$WORK/error"
            reading_rc=$?
            printf 'reading_api=%s/%s exit=%s value=' "$reading_provider" "$reading_property" "$reading_rc"
            head -c 512 "$WORK/query"; printf '\n'
        done
        printf 'history_readable=%s\n' "$([ -r "$BASE/reading-time.tsv" ] && echo yes || echo no)"
        exit "$rc";;
    snapshot)
        rr_lock || exit 75
        status; initial_status=$service_status
        instances || { evidence || true; output; exit 1; }
        [ "$service_status" != unknown ] || { evidence || true; output; exit 1; }
        evidence || { reason=evidence_unavailable; recovery_status=failed; exit 1; }
        output
        printf 'managed_process_before=%s\n' "$([ -n "$service_pid" ] && echo yes || echo no)"
        exit 0;;
    *) exit 2;;
esac
