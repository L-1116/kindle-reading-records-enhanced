#!/bin/sh
# Shared by optimized and legacy FBInk UIs. Parent owns touch and cleanup.
rr_settings_image() {
    fb -q -b -g "file=$1,x=$(scale_x "$2"),y=$(scale_y "$3"),w=$(scale_len "$4"),h=$(scale_len "$5")"
}
rr_settings_gear() {
    case "$mode" in daily|total|books) rr_settings_image "$SETTINGS_ASSETS/settings-button.png" 1006 54 211 91;; esac
}
rr_settings_draw() {
    if [ "$mode" = settings ]; then
        rr_settings_image "$SETTINGS_ASSETS/settings-switch-$idle_enabled.png" 1016 373 152 78
        rr_settings_image "$SETTINGS_ASSETS/settings-switch-$custom_cover_enabled.png" 1016 909 152 78
        if [ "$idle_enabled" = 1 ]; then
            ot 34 560 104 300 REGULAR "$idle_minutes 分钟无操作后暂停"
        else
            ot 34 560 104 300 REGULAR "已关闭 · 已选 $idle_minutes 分钟"
        fi
    elif [ "$mode" = settings_cover ]; then
        if [ "$custom_cover_enabled" = 1 ]; then
            ot 34 244 80 80 REGULAR '开关已开启 · 功能尚未接入'
        else
            ot 34 244 80 80 REGULAR '开关已关闭 · 功能尚未接入'
        fi
    elif [ "$mode" = settings_idle ]; then
        rr_settings_image "$SETTINGS_ASSETS/settings-switch-$idle_enabled.png" 1016 431 152 78
        if [ "$idle_enabled" = 1 ]; then
            ot 34 491 104 104 REGULAR '已开启'
            ot 34 579 104 104 REGULAR "连续 $idle_minutes 分钟无触摸，计时自动暂停。"
        else
            ot 34 491 104 104 REGULAR '已关闭'
            ot 34 579 104 104 REGULAR '未启用，仍按原有方式计时。'
        fi
        settings_x=$((1168-155-19*${#idle_minutes}))
        ot 34 793 "$settings_x" 104 REGULAR "当前 $idle_minutes 分钟"
        settings_i=0
        for settings_n in 1 2 3 4 5 10; do
            settings_x=$((104+(settings_i%3)*362)); settings_y=$((888+(settings_i/3)*138))
            if [ "$idle_minutes" = "$settings_n" ]; then
                rr_settings_image "$SETTINGS_ASSETS/settings-preset-$settings_n.png" "$settings_x" "$settings_y" 340 116
            fi
            settings_i=$((settings_i+1))
        done
        case "$idle_minutes" in 1|2|3|4|5|10) :;;
            *) rr_settings_image "$SETTINGS_ASSETS/settings-custom-selected.png" 1101 1226 48 48;;
        esac
    else
        if [ -n "$settings_digits" ]; then
            settings_x=$((530-61*${#settings_digits}/2))
            ot 110 433 "$settings_x" 500 REGULAR "$settings_digits"
            settings_x=$((settings_x+61*${#settings_digits}+64))
        else
            ot 52 478 452 500 REGULAR '请输入'
            settings_x=672
        fi
        ot 40 511 "$settings_x" 104 REGULAR '分钟'
    fi
    [ -z "${settings_error:-}" ] || ot 32 1400 80 80 REGULAR "$settings_error"
}
rr_settings_action() {
    settings_error=''
    case "$action" in
        settings_open) settings_return="$mode"; rr_config_read; mode=settings;;
        settings_back) mode="$settings_return";;
        settings_idle) mode=settings_idle;;
        settings_cover) mode=settings_cover;;
        settings_home) mode=settings;;
        settings_toggle) idle_enabled=$((1-idle_enabled)); rr_settings_save;;
        settings_cover_toggle) custom_cover_enabled=$((1-custom_cover_enabled)); rr_settings_save;;
        settings_preset_*) idle_minutes="${action#settings_preset_}"; rr_settings_save;;
        settings_custom) settings_digits=''; mode=settings_custom;;
        settings_cancel) mode=settings_idle;;
        settings_digit_*) [ "${#settings_digits}" -ge 4 ] || settings_digits="$settings_digits${action#settings_digit_}";;
        settings_delete) settings_digits="${settings_digits%?}";;
        settings_save)
            if rr_minutes_valid "$settings_digits"; then idle_minutes="$settings_digits"; rr_settings_save; [ -n "$settings_error" ] || mode=settings_idle
            else settings_error='请输入 1 至 1440 的整数'; fi;;
    esac
}
rr_settings_save() {
    rr_config_save || { rr_config_read; settings_error='保存失败，请重试'; }
}
