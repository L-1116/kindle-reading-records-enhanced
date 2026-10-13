#!/bin/sh
# Installation eligibility only. Unknown models may attempt Standard; runtime
# compatibility is checked separately. Never print raw model text or a USID.
# Device codes: KindleModding Hotfix libhotfixutils (rewrite-lite), supplemented
# by NiLuJe/KindleTool kindle_tool.h (Scribe 2/3/Colorsoft), audited 2026-10-13.

rr_device_text_class() {
    rr_model=$(printf '%s' "$1" | LC_ALL=C tr '[:upper:]' '[:lower:]' | LC_ALL=C tr -cd '[:alnum:]')
    case "$rr_model" in
        *scribe*|ks|ks[0-9]*|kindleks|kindleks[0-9]*) printf ks;;
        kindlepaperwhite*|paperwhite*|kpw[0-9]*|pw[0-9]*|kindlecolorsoft*|colorsoft*|kc|cs|kindlebasic*|basic*|kt[0-9]*|kindletouch*|kindlevoyage*|kindleoasis*) printf standard;;
        *) printf unknown;;
    esac
}

rr_device_code_class() {
    case "$1" in
        # This is a Scribe exclusion list, never a Standard eligibility list.
        new:27J|new:2BL|new:263|new:227|new:2BM|new:23L|new:23M|new:270|\
        new:3V0|new:3V1|new:3X5|new:3UV|new:3X4|new:3X3|new:41E|new:41D|\
        new:4PG|new:4PE|new:4PL|new:4F8|new:4FA|new:454|\
        new:4VX|new:4PF|new:4PH|new:4F9|new:4FB|new:46P) printf ks;;
        # Positive non-Scribe evidence detects conflicting sources. An absent
        # entry here does NOT prevent installation, including future models.
        old:24|old:1B|old:1D|old:1F|old:1C|old:20|old:D4|old:5A|old:D5|old:D6|old:D7|old:D8|old:F2|old:17|old:60|old:F4|old:F9|old:62|old:61|old:5F|old:13|old:54|old:2A|old:4F|old:52|old:53|old:C6|old:DD|old:0F|old:11|old:10|old:12|\
        new:0G1|new:0G2|new:0G4|new:0G5|new:0G6|new:0G7|new:0KB|new:0KC|new:0KD|new:0KE|new:0KF|new:0KG|new:0LK|new:0LL|\
        new:0GC|new:0GD|new:0GR|new:0GS|new:0GT|new:0GU|new:0DU|new:0K9|new:0KA|\
        new:0LM|new:0LN|new:0LP|new:0LQ|new:0P1|new:0P2|new:0P6|new:0P7|new:0P8|new:0S1|new:0S2|new:0S3|new:0S4|new:0S7|new:0SA|\
        new:0PP|new:0T1|new:0T2|new:0T3|new:0T4|new:0T5|new:0T6|new:0T7|new:0TJ|new:0TK|new:0TL|new:0TM|new:0TN|new:102|new:103|new:16Q|new:16R|new:16S|new:16T|new:16U|new:16V|\
        new:10L|new:0WF|new:0WG|new:0WH|new:0WJ|new:0VB|new:11L|new:0WQ|new:0WP|new:0WN|new:0WM|new:0WL|\
        new:1LG|new:1Q0|new:1PX|new:1VD|new:219|new:21A|new:2BH|new:2BJ|new:2DK|new:22D|new:25T|new:23A|new:2AQ|new:2AP|new:1XH|new:22C|\
        new:349|new:346|new:33X|new:33W|new:3HA|new:3H5|new:3H3|new:3H8|new:3J5|new:3JS|\
        new:3L5|new:3L6|new:3L4|new:3L3|new:A89|new:3L2|new:3KM|\
        new:3H9|new:3H4|new:3HB|new:3H6|new:3H2|new:34X|new:3H7|new:3JT|new:3J6|new:456|new:455|new:4EP) printf standard;;
        *) printf unknown;;
    esac
}

rr_device_evidence() {
    rr_device_sources="${rr_device_sources}${rr_device_sources:+,}$1:$2:$3"
    case "$3" in
        ks) rr_device_ks=1;;
        standard) rr_device_standard=1;;
    esac
    rr_device_log "device_source=$1 status=$2 classification=$3${4:+ device_code=$4}"
}

rr_device_read() {
    rr_input=; rr_input_status=missing
    if [ -e "$1" ]; then
        rr_input_status=unreadable
        if [ -f "$1" ] && [ -r "$1" ]; then
            # Model text only; strip a device-tree NUL terminator and CRLF.
            # Read errors stay distinct from a successfully read empty file.
            if rr_input=$(LC_ALL=C awk 'NR==1 { sub(/\r$/, ""); gsub(/\0/, ""); print substr($0,1,256); exit }' "$1" 2>/dev/null); then
                rr_input_status=read
                [ -n "$(printf '%s' "$rr_input" | tr -d '[:space:]')" ] || rr_input_status=empty
            else
                rr_input=; rr_input_status=read_failed
            fi
        fi
    fi
}

rr_detect_device_variant() {
    rr_device_sources=; rr_device_ks=0; rr_device_standard=0
    rr_device_read "${READING_DEVICETYPE_PATH:-/var/local/deviceType.txt}"
    rr_class=$(rr_device_text_class "$rr_input")
    rr_device_evidence deviceType "$rr_input_status" "$rr_class"
    rr_input=; rr_model=

    rr_usid_path="${READING_USID_PATH:-/proc/usid}"
    rr_usid_status=missing; rr_code=
    if [ -e "$rr_usid_path" ]; then
        rr_usid_status=unreadable
        if [ -f "$rr_usid_path" ] && [ -r "$rr_usid_path" ]; then
            # Same offsets as KindleModding; only the shared model code leaves
            # awk. No full serial, suffix, hash, or raw path is logged.
            rr_code=$(LC_ALL=C awk 'NR==1 {
                s=toupper(substr($0,1,6))
                if (s ~ /^[[:space:]]*$/) { print "empty"; exit }
                # Only validate the model-bearing prefix. A changed serial
                # suffix/length must never hide a known Scribe device code.
                if (substr(s,1,1)=="B" || substr(s,1,1)=="9") {
                    p=substr(s,1,4)
                    if (length(p)!=4 || p ~ /[^A-Z0-9]/) print "invalid"
                    else print "old:" substr(p,3,2)
                } else {
                    if (length(s)!=6 || s ~ /[^A-Z0-9]/) print "invalid"
                    else print "new:" substr(s,4,3)
                }
                exit
            }' "$rr_usid_path" 2>/dev/null) || rr_code=unreadable
            case "$rr_code" in
                '') rr_usid_status=empty;;
                empty|invalid|unreadable) rr_usid_status=$rr_code; rr_code=;;
                *) rr_usid_status=read;;
            esac
        fi
    fi
    rr_class=$(rr_device_code_class "$rr_code")
    rr_device_evidence proc_usid "$rr_usid_status" "$rr_class" "$rr_code"

    # Optional read-only kernel model names. Never infer Scribe from screen
    # size, shared CPU/ABI, stylus nodes, FBInk availability, or installed apps.
    for rr_tree_source in proc_device_tree sys_device_tree; do
        case "$rr_tree_source" in
            proc_device_tree) rr_tree_path="${READING_PROC_MODEL_PATH:-/proc/device-tree/model}";;
            sys_device_tree) rr_tree_path="${READING_SYS_MODEL_PATH:-/sys/firmware/devicetree/base/model}";;
        esac
        rr_device_read "$rr_tree_path"
        rr_class=$(rr_device_text_class "$rr_input")
        rr_device_evidence "$rr_tree_source" "$rr_input_status" "$rr_class"
        rr_input=; rr_model=
    done

    RR_DEVICE_VARIANT=unknown; RR_DEVICE_DECISION=allow_unconfirmed; RR_DEVICE_REASON=no_ks_evidence
    if [ "$rr_device_ks" = 1 ] && [ "$rr_device_standard" = 1 ]; then
        RR_DEVICE_VARIANT=conflict; RR_DEVICE_DECISION=refuse; RR_DEVICE_REASON=conflicting_ks_evidence
    elif [ "$rr_device_ks" = 1 ]; then
        RR_DEVICE_VARIANT=ks; RR_DEVICE_DECISION=refuse; RR_DEVICE_REASON=scribe_confirmed
    elif [ "$rr_device_standard" = 1 ]; then
        RR_DEVICE_VARIANT=standard; RR_DEVICE_DECISION=allow; RR_DEVICE_REASON=non_scribe_confirmed
    fi
    RR_DEVICE_SOURCES=$rr_device_sources
    rr_device_log "device_variant=$RR_DEVICE_VARIANT device_decision=$RR_DEVICE_DECISION device_reason=$RR_DEVICE_REASON model_confirmation=$([ "$RR_DEVICE_VARIANT" = unknown ] && printf unconfirmed || printf variant_only)"
}

rr_standard_install_guard() {
    rr_detect_device_variant
    RR_DEVICE_ERROR=
    case "$RR_DEVICE_VARIANT" in
        ks) RR_DEVICE_ERROR='device variant mismatch';;
        conflict) RR_DEVICE_ERROR='device identification conflict';;
    esac
    [ -z "$RR_DEVICE_ERROR" ] || return 1
    # Check remnants regardless of model certainty or apparently Standard
    # release-info, so contradictory KS installations are never overwritten.
    if [ -e "$BASE/bin/launch-ks.sh" ] || [ -d "$BASE/releases/9.7.5-ks-test1" ] ||
       { [ -f "$BASE/release-info" ] && grep -Fqx 'variant=ks' "$BASE/release-info"; } ||
       { [ -f "$BASE/VERSION" ] && grep -Eiq '(^|[-_])ks([-_]|$)|scribe' "$BASE/VERSION"; }; then
        RR_DEVICE_ERROR='cross-variant upgrade refused'
        rr_device_log 'installation_evidence=ks_residue decision=refuse'
        return 1
    fi
    return 0
}
