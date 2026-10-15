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
        [ "$idle_enabled" = 1 ] && settings_switch=开启 || settings_switch=关闭
        ot 36 335 100 400 BOLD "无操作超时暂停：$settings_switch"
        ot 32 470 100 120 REGULAR "当前阈值：$idle_minutes 分钟"
        settings_i=0
        for settings_n in 1 2 3 4 5 10; do
            settings_x=$((100+(settings_i%3)*360)); settings_y=$((600+(settings_i/3)*150))
            if [ "$idle_minutes" = "$settings_n" ]; then rect $((settings_y+6)) $((settings_x+6)) 318 98 GRAY8; fi
            ot 34 $((settings_y+30)) $((settings_x+35)) 60 BOLD "$settings_n 分钟"
            settings_i=$((settings_i+1))
        done
        ot 34 940 135 60 BOLD "自定义分钟数"
        ot 28 1135 100 100 REGULAR "关闭时沿用原有阅读计时方式。"
        ot 28 1200 100 100 REGULAR "设置自动保存，仅影响之后的计时。"
    else
        ot 36 335 100 100 BOLD "分钟数：${settings_digits:-请输入}"
        settings_i=0
        for settings_n in 1 2 3 4 5 6 7 8 9 删除 0 保存; do
            settings_x=$((100+(settings_i%3)*360)); settings_y=$((500+(settings_i/3)*170))
            ot 38 $((settings_y+45)) $((settings_x+100)) 60 BOLD "$settings_n"
            settings_i=$((settings_i+1))
        done
        ot 28 1250 100 100 REGULAR "请输入 1 至 1440 的整数分钟。"
    fi
    [ -z "${settings_error:-}" ] || ot 28 1400 100 100 BOLD "$settings_error"
}
rr_settings_action() {
    settings_error=''
    case "$action" in
        settings_open) settings_return="$mode"; rr_config_read; mode=settings;;
        settings_back) mode="$settings_return";;
        settings_toggle) idle_enabled=$((1-idle_enabled)); rr_settings_save;;
        settings_preset_*) idle_minutes="${action#settings_preset_}"; rr_settings_save;;
        settings_custom) settings_digits=''; mode=settings_custom;;
        settings_cancel) mode=settings;;
        settings_digit_*) [ "${#settings_digits}" -ge 4 ] || settings_digits="$settings_digits${action#settings_digit_}";;
        settings_delete) settings_digits="${settings_digits%?}";;
        settings_save)
            if rr_minutes_valid "$settings_digits"; then idle_minutes="$settings_digits"; rr_settings_save; [ -n "$settings_error" ] || mode=settings
            else settings_error='请输入 1 至 1440 的整数'; fi;;
    esac
}
rr_settings_save() {
    rr_config_save || { rr_config_read; settings_error='保存失败，请重试'; }
}
