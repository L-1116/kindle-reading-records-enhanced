#!/bin/sh
# Shared device reader is loaded first. KS requires positive hardware evidence;
# an installed layout, framebuffer size or stylus does not prove a Scribe.
rr_ks_install_guard() {
    rr_detect_device_variant
    RR_DEVICE_ERROR=
    case "$RR_DEVICE_VARIANT" in
        ks) RR_DEVICE_DECISION=allow; RR_DEVICE_REASON=scribe_confirmed;;
        conflict) RR_DEVICE_ERROR='device identification conflict';;
        standard) RR_DEVICE_ERROR='device variant mismatch';;
        *) RR_DEVICE_ERROR='Scribe hardware not confirmed'; RR_DEVICE_REASON=scribe_unconfirmed;;
    esac
    if [ -n "$RR_DEVICE_ERROR" ]; then
        RR_DEVICE_DECISION=refuse
        rr_device_log "ks_install_decision=refuse reason=$RR_DEVICE_REASON"
        return 1
    fi
    # Check all installation evidence, even if release-info says KS.
    if [ -e "$BASE/bin/launch.sh" ] ||
       { [ -r "$BASE/release-info" ] && grep -Fqx 'variant=standard' "$BASE/release-info"; } ||
       { [ -r "$BASE/VERSION" ] && ! grep -Eiq '(^|[-_])ks([-_]|$)|scribe' "$BASE/VERSION"; }; then
        RR_DEVICE_ERROR='cross-variant upgrade refused'
        RR_DEVICE_DECISION=refuse
        rr_device_log 'installation_evidence=standard_residue decision=refuse'
        return 1
    fi
    rr_device_log 'ks_install_decision=allow reason=scribe_confirmed'
}
