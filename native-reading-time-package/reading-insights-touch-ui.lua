-- Resolution-independent interactive dashboard input reader. It only
-- observes evdev events:
-- no EVIOCGRAB, no eatTapMode, and no write access to the input device.
local device = arg[1]
local log_path = arg[2] or "/mnt/us/reading-time/dashboard-touch.log"
local mode = arg[3] or "daily"
local calendar_offset = tonumber(arg[4] or "0") or 0
local calendar_days = tonumber(arg[5] or "31") or 31
local origin_x = tonumber(arg[6] or "0") or 0
local origin_y = tonumber(arg[7] or "0") or 0
local view_w = tonumber(arg[8] or "1272") or 1272
local view_h = tonumber(arg[9] or "1696") or 1696
local detail_pages = tonumber(arg[10] or "1") or 1
local detail_page = tonumber(arg[11] or "1") or 1
local pager_y = tonumber(arg[12] or "1576") or 1576
local total_period = arg[13] or "week"
local book_filter = arg[14] or "7d"
local logical_w, logical_h = 1272, 1696
local transform_hint = arg[15] or "auto"
local event_size = tonumber(arg[16])
local screen_w, screen_h = tonumber(arg[17]), tonumber(arg[18])
local report_path = arg[19]
local min_x, max_x = tonumber(arg[20]), tonumber(arg[21])
local min_y, max_y = tonumber(arg[22]), tonumber(arg[23])
local legacy = arg[24] == "legacy"
local f
local last_type, last_code
local log = io.open(log_path, "a")
local function report(fields)
    if not report_path then return end
    local old, lines = io.open(report_path, "rb"), {}
    if old then
        for line in old:lines() do
            local key = line:match("^([^=]+)=")
            if not key or fields[key] == nil then lines[#lines+1] = line end
        end
        old:close()
    end
    local tmp = report_path .. ".new"
    local out = io.open(tmp, "wb")
    if not out then return end
    for _,line in ipairs(lines) do out:write(line,"\n") end
    for key,value in pairs(fields) do out:write(key,"=",tostring(value),"\n") end
    out:close()
    if not os.rename(tmp, report_path) then
        os.remove(report_path)
        os.rename(tmp, report_path)
    end
end
local function reader_fail(reason)
    report({reader_state="reader_failed",reader_error=reason,reader_exit_code=2,
        last_event_type=last_type or "none",last_event_code=last_code or "none"})
    if f then f:close() end
    if log then log:close() end
    io.stderr:write("touch reader: ",reason,"\n")
    os.exit(2)
end

local function u16(s, p)
    local a, b = s:byte(p, p + 1)
    return a + b * 256
end
local function u32(s, p)
    local a, b, c, d = s:byte(p, p + 3)
    return a + b * 256 + c * 65536 + d * 16777216
end
local function note(message)
    if log then log:write(os.date("%Y-%m-%d %H:%M:%S "), message, "\n"); log:flush() end
end
local function finish(action)
    note("action=" .. action)
    report({reader_state="action_returned",last_action=action,reader_exit_code=0})
    io.write(action, "\n")
    f:close()
    if log then log:close() end
    os.exit(0)
end
local function inside(px, py, left, top, right, bottom)
    return px >= left and px <= right and py >= top and py <= bottom
end
local function settings_action(px, py)
    if mode:match('^settings_cover') then
        if mode~='settings_cover' and inside(px,py,64,54,256,146) then return 'settings_cover_back' end
        if mode=='settings_cover' then
            if inside(px,py,64,330,1208,580) then return 'settings_cover_generic' end
            if inside(px,py,64,650,1208,900) then return 'settings_cover_books' end
            if inside(px,py,64,954,1208,1074) then return 'settings_cover_info' end
            if inside(px,py,64,1134,1208,1254) then return 'settings_cover_scan' end
        elseif mode=='settings_cover_manage' then
            if inside(px,py,104,1080,1168,1210) then return 'settings_cover_choose' end
            if inside(px,py,104,1250,1168,1380) then return 'settings_cover_clear' end
        elseif mode=='settings_cover_images' or mode=='settings_cover_books' then
            if inside(px,py,80,1400,410,1520) then return 'settings_cover_prev' end
            if inside(px,py,862,1400,1192,1520) then return 'settings_cover_next' end
            if mode=='settings_cover_images' and inside(px,py,452,1400,820,1520) then return 'settings_cover_scan' end
            local count,step,height=6,160,140
            if mode=='settings_cover_images' then count,step,height=4,260,230 end
            for i=1,count do
                local y=310+(i-1)*step
                if inside(px,py,80,y,1192,y+height) then return 'settings_cover_item_'..i end
            end
        end
        if mode~='settings_cover' then return false end
    end
    if mode == "settings" or mode == "settings_idle" or mode == "settings_cover" or mode == "settings_custom" then
        if inside(px,py,44,34,276,166) then
            if mode == "settings" then return "settings_back" end
            return mode == "settings_custom" and "settings_cancel" or "settings_home"
        end
        if mode == "settings" then
            -- Each switch owns only its visible capsule; the detail region
            -- ends before the divider and never overlaps the switch.
            if inside(px,py,1016,373,1167,450) then return "settings_toggle" end
            if inside(px,py,1016,909,1167,986) then return "settings_cover_toggle" end
            if inside(px,py,104,360,960,658) then return "settings_idle" end
            if inside(px,py,104,896,960,1194) then return "settings_cover" end
        elseif mode == "settings_idle" then
            if inside(px,py,104,410,1168,554) then return "settings_toggle" end
            if inside(px,py,104,888,1167,1141) then
                local col,row=math.floor((px-104)/362),math.floor((py-888)/138)
                if col<3 and row<2 and (px-104)%362<340 and (py-888)%138<116 then
                    local values={1,2,3,4,5,10}; return "settings_preset_" .. values[row*3+col+1]
                end
            end
            if inside(px,py,104,1186,1168,1314) then return "settings_custom" end
        elseif mode == "settings_custom" and inside(px,py,72,758,1199,1377) then
            local col,row=math.floor((px-72)/383),math.floor((py-758)/160)
            if col<3 and row<4 and (px-72)%383<362 and (py-758)%160<140 then
                local values={"1","2","3","4","5","6","7","8","9","delete","0","save"}
                local key=values[row*3+col+1]
                return (key=="delete" or key=="save") and "settings_" .. key or "settings_digit_" .. key
            end
        end
        return false
    end
    if (mode=="total" or mode=="daily" or mode=="books") and inside(px,py,990,20,1250,155) then return "settings_open" end
end
local function action_for_logical(px, py)
    local settings = settings_action(px,py)
    if settings ~= nil then return settings or nil end
    local secondary = mode == "day_detail" or mode == "month_detail" or mode == "week_trend" or mode == "book_detail"
    if secondary and inside(px, py, 20, 20, 300, 155) then
        if mode == "day_detail" then return "day_detail_back" end
        if mode == "month_detail" then return "month_detail_back" end
        if mode == "book_detail" then return "book_detail_back" end
        return "week_trend_back"
    end
    if not secondary and inside(px, py, 20, 20, 270, 155) then return "exit" end
    if not secondary then
        if inside(px, py, 35, 165, 415, 275) then return "tab_daily" end
        if inside(px, py, 430, 165, 800, 275) then return "tab_books" end
        if inside(px, py, 815, 165, 1237, 275) then return "tab_total" end
    end

    if mode == "total" then
        if inside(px, py, 75, 650, 432, 737) then return "total_week" end
        if inside(px, py, 457, 650, 814, 737) then return "total_year" end
        if inside(px, py, 839, 650, 1196, 737) then return "total_all" end
        if total_period ~= "all" and inside(px, py, 300, 762, 411, 845) then return "total_prev" end
        if total_period ~= "all" and inside(px, py, 860, 762, 971, 845) then return "total_next" end
        if total_period == "week" and inside(px, py, 85, 380, 1187, 560) then return "week_trend_open" end
        if total_period == "year" and inside(px, py, 75, 884, 1197, 1573) then
            local month = math.floor((px - 75) * 12 / 1123) + 1
            if month > 12 then month = 12 end
            return "year_month_" .. month
        end
        if total_period == "week" and inside(px, py, 135, 884, 1181, 1573) then
            local day_index = math.floor((px - 135) * 7 / 1047)
            if day_index > 6 then day_index = 6 end
            return "week_day_" .. day_index
        end
    elseif mode == "daily" then
        if inside(px, py, 220, 300, 450, 430) then return "month_prev" end
        if inside(px, py, 840, 300, 1070, 430) then return "month_next" end
        if inside(px, py, 450, 300, 822, 430) then return "month_detail_open" end
        if detail_pages > 1 then
            if detail_page > 1 and inside(px, py, 390, pager_y, 529, pager_y+47) then return "detail_prev" end
            if detail_page < detail_pages and inside(px, py, 742, pager_y, 881, pager_y+47) then return "detail_next" end
        end
        -- The visible title is small, but the complete quick-preview header is
        -- a generous drill-down target.
        if inside(px, py, 70, 1222, 1202, 1305) then return "day_detail_open" end
        -- Same 1120 x 648 grid as render_daily; Monday=0, four to six rows.
        local rows = math.floor((calendar_offset + calendar_days + 6) / 7)
        local cell_h = math.floor(648 / rows)
        if px >= 75 and px < 1195 and py >= 460 and py < 460 + rows*cell_h then
            local col = math.floor((px - 75) / 160)
            local row = math.floor((py - 460) / cell_h)
            -- Ignore the six-pixel gutters, including their far edges.
            if (px - 75) % 160 < 154 and (py - 460) % cell_h < cell_h - 6 then
                local day = row * 7 + col - calendar_offset + 1
                if day >= 1 and day <= calendar_days then return "day_" .. day end
            end
            -- Consume visible blank cells/gutters at the UI hit-test layer:
            -- they must not fall through to the swapped-axis compatibility retry.
            return "ignore"
        end
    elseif mode == "day_detail" then
        if detail_pages > 1 then
            if detail_page > 1 and inside(px, py, 390, pager_y, 529, pager_y+53) then return "day_detail_prev" end
            if detail_page < detail_pages and inside(px, py, 742, pager_y, 881, pager_y+53) then return "day_detail_next" end
        end
    elseif mode == "book_detail" then
        if inside(px, py, 300, 750, 510, 860) then return "book_month_prev" end
        if inside(px, py, 760, 750, 970, 860) then return "book_month_next" end
        local rows = math.floor((calendar_offset + calendar_days + 6) / 7)
        local cell_h = math.floor(520 / rows)
        if px >= 76 and px < 1196 and py >= 895 and py < 895 + rows*cell_h then
            local col = math.floor((px - 76) / 160)
            local row = math.floor((py - 895) / cell_h)
            local day = row * 7 + col - calendar_offset + 1
            if day >= 1 and day <= calendar_days then return "book_day_" .. day end
            return "book_calendar_clear"
        end
        if inside(px, py, 55, 750, 1217, 1640) then return "book_calendar_clear" end
    elseif mode == "books" then
        if inside(px, py, 70, 285, 333, 339) then return "books_7d" end
        if inside(px, py, 360, 285, 623, 339) then return "books_month" end
        if inside(px, py, 650, 285, 913, 339) then return "books_year" end
        if inside(px, py, 940, 285, 1202, 339) then return "books_all" end
        if inside(px, py, 70, 345, 1202, 1425) then
            local row = math.floor((py - 345) / 360) + 1
            if row > 3 then row = 3 end
            return "book_row_" .. row
        end
        if inside(px, py, 55, 1465, 385, 1595) then return "page_prev" end
        if inside(px, py, 885, 1465, 1217, 1595) then return "page_next" end
    end
    return nil
end

local function legacy_action_for_logical(px, py)
    local settings = settings_action(px,py)
    if settings ~= nil then return settings or nil end
    if inside(px, py, 20, 20, 270, 155) then return "exit" end
    if inside(px, py, 35, 165, 415, 275) then return "tab_total" end
    if inside(px, py, 430, 165, 800, 275) then return "tab_daily" end
    if inside(px, py, 815, 165, 1237, 275) then return "tab_books" end

    if mode == "total" then
        if inside(px, py, 280, 625, 440, 750) then return "year_prev" end
        if inside(px, py, 840, 625, 1000, 750) then return "year_next" end
    elseif mode == "daily" then
        if inside(px, py, 220, 300, 450, 430) then return "month_prev" end
        if inside(px, py, 840, 300, 1070, 430) then return "month_next" end
        -- Seven columns, six rows. The shell passes the weekday offset of day 1.
        if inside(px, py, 55, 500, 1210, 960) then
            local col = math.floor((px - 55) / 165)
            local row = math.floor((py - 500) / 78)
            if col >= 0 and col <= 6 and row >= 0 and row <= 5 then
                local day = row * 7 + col - calendar_offset + 1
                if day >= 1 and day <= calendar_days then return "day_" .. day end
            end
        end
    elseif mode == "books" then
        if inside(px, py, 55, 1465, 385, 1595) then return "page_prev" end
        if inside(px, py, 885, 1465, 1217, 1595) then return "page_next" end
    end
    return nil
end

-- Map physical framebuffer coordinates back to the 1272x1696 design canvas.
-- The viewer uses the inverse of this transform for every rendered element.
local function coordinates_for_physical(px, py, transform)
    transform = transform or "direct"
    local swapped = transform:sub(1,4) == "swap"
    local sw, sh = screen_w or (origin_x*2+view_w), screen_h or (origin_y*2+view_h)
    local tw, th = swapped and sh or sw, swapped and sw or sh
    if min_x and max_x and min_y and max_y then
        if px < min_x or px > max_x or py < min_y or py > max_y then return nil end
        px = math.floor((px-min_x)*(tw-1)/(max_x-min_x)+0.5)
        py = math.floor((py-min_y)*(th-1)/(max_y-min_y)+0.5)
    end
    if px < 0 or px >= tw or py < 0 or py >= th then return nil end
    if swapped then px,py = py,px end
    if transform == "invert_x" or transform == "invert_xy" or transform == "swap_invert_x" or transform == "swap_invert_xy" then px = sw-1-px end
    if transform == "invert_y" or transform == "invert_xy" or transform == "swap_invert_y" or transform == "swap_invert_xy" then py = sh-1-py end
    if px < origin_x or py < origin_y or
       px > origin_x + view_w or py > origin_y + view_h then
        return nil
    end
    local lx = math.floor((px - origin_x) * logical_w / view_w + 0.5)
    local ly = math.floor((py - origin_y) * logical_h / view_h + 0.5)
    local action
    if legacy then action = legacy_action_for_logical(lx,ly) else action = action_for_logical(lx,ly) end
    if action then
        note(string.format("mapped x=%d y=%d action=%s", lx, ly, action))
    end
    return action, px, py, lx, ly
end
local function action_for_physical(px,py,transform)
    return (coordinates_for_physical(px,py,transform))
end

note(string.format("interactive watcher started mode=%s viewport=%dx%d+%d+%d",
    mode, view_w, view_h, origin_x, origin_y))
report({reader_state="reader_starting",reader_mode=mode,reader_error="none"})
if event_size ~= 16 and event_size ~= 24 then reader_fail("invalid_event_struct_size") end
if not screen_w or not screen_h or screen_w < 1 or screen_h < 1 or view_w <= 0 or view_h <= 0 then reader_fail("invalid_screen_size") end
local transforms = {direct=true,swap=true,invert_x=true,invert_y=true,invert_xy=true,
    swap_invert_x=true,swap_invert_y=true,swap_invert_xy=true}
if transform_hint ~= "auto" and not transforms[transform_hint] then reader_fail("invalid_transform") end
if (min_x or max_x or min_y or max_y) and
    (not min_x or not max_x or not min_y or not max_y or max_x <= min_x or max_y <= min_y) then reader_fail("invalid_raw_range") end
if not device then reader_fail("missing_touch_device") end
f = io.open(device, "rb")
if not f then reader_fail("device_open_failed") end
report({reader_state="waiting"})
if os.getenv("READING_PERF") == "1" and not os.getenv("READING_PERF_READY_DONE") then
    local up = io.open(os.getenv("READING_UPTIME_PATH") or "/proc/uptime", "rb")
    local now = up and up:read("*n")
    if up then up:close() end
    local perf = io.open(os.getenv("READING_PERF_LOG") or "/mnt/us/reading-time/startup-performance.log", "a")
    if perf and now then perf:write("stage=software_interactive_ready uptime=", tostring(now), " source=touch_reader\n") end
    if perf then perf:close() end
end
local selected_transform = transform_hint ~= "auto" and transform_hint or nil
if not selected_transform and min_x and max_x then
    local ratio = (max_x-min_x)/(max_y-min_y)
    local direct_error = math.abs(ratio/(screen_w/screen_h)-1)
    local swap_error = math.abs(ratio/(screen_h/screen_w)-1)
    if swap_error < 0.05 and direct_error > 0.05 then selected_transform = "swap" end
end
local function tap(x,y)
    -- Select by geometry only; never retry because a different transform hits
    -- a button. Inversions require trusted metadata; a point alone cannot
    -- distinguish a mirrored touchscreen from an ordinary one.
    local transform = selected_transform
    if not transform then
        if x >= 0 and x < screen_w and y >= 0 and y < screen_h or min_x then transform = "direct"
        elseif x >= 0 and x < screen_h and y >= 0 and y < screen_w then transform = "swap"
        else reader_fail("coordinate_range_unavailable") end
        selected_transform = transform
    end
    local action,px,py,lx,ly = coordinates_for_physical(x,y,transform)
    note(string.format("tap x=%d y=%d transform=%s",x,y,transform))
    report({reader_state="touch_received",last_raw_x=x,last_raw_y=y,
        last_physical_x=px or "outside",last_physical_y=py or "outside",
        last_logical_x=lx or "outside",last_logical_y=ly or "outside",
        last_transform=transform,last_action=action or "ignore_outside"})
    if action and action ~= "ignore" then finish(action) end
    report({reader_state="waiting"})
end
local slots, slot, uses_slots = {}, 0, false
local abs_x,abs_y,abs_dirty,abs_contact,abs_released,abs_first = nil,nil,false,nil,false,nil
local mt_seen,tracking_seen,btn_seen,multi = false,false,false,false
local packets,packet_x,packet_y = 0,nil,nil
local invalid = 0
local function current()
    if not slots[slot] then slots[slot] = {active=nil,dirty=false} end
    return slots[slot]
end
local function signed(value) return value >= 2147483648 and value-4294967296 or value end
while true do
    local event = f:read(event_size)
    if not event or #event ~= event_size then reader_fail("short_read") end
    local offset = event_size-7
    local etype,code,value = u16(event,offset),u16(event,offset+2),signed(u32(event,offset+4))
    local valid = etype <= 31 and code <= 767 and
        (etype ~= 0 or code <= 3) and (etype ~= 3 or code <= 63)
    last_type,last_code = etype,code
    if not valid then
        invalid = invalid+1
        if invalid >= 8 then reader_fail("corrupt_event_stream") end
    else
        invalid = 0
        if etype == 0 and code == 3 then
            -- Without EVIOCG* resynchronization, guessing after queue overrun
            -- could dispatch an old position. Recover the Library instead.
            reader_fail("syn_dropped")
        elseif etype == 3 then
            if code == 47 then
                if value < 0 or value > 255 then reader_fail("invalid_mt_slot") end
                slot,uses_slots = value,true
            elseif code == 57 then
                tracking_seen,mt_seen = true,true
                local c = current()
                if value < 0 then c.released,c.active = c.active == true,false
                elseif c.id ~= value or not c.active then
                    c.id,c.active,c.first,c.released = value,true,nil,false
                end
            elseif code == 53 or code == 54 then
                mt_seen = true
                local c = current()
                if code == 53 then c.x,packet_x = value,value else c.y,packet_y = value,value end
                c.dirty = true
            elseif code == 0 then abs_x,abs_dirty = value,true
            elseif code == 1 then abs_y,abs_dirty = value,true end
        elseif etype == 1 and code == 330 then
            btn_seen = true
            if value == 0 then
                abs_released,abs_contact = abs_contact == true,false
                if not tracking_seen then
                    local c = current(); c.released,c.active = c.active == true,false
                end
            elseif value == 1 and abs_contact ~= true then
                abs_contact,abs_first = true,nil
                if not tracking_seen then local c = current(); c.active,c.first,c.released = true,nil,false end
            end
        elseif etype == 0 and code == 2 and not uses_slots then
            if packet_x and packet_y then packets = packets+1 end
            packet_x,packet_y = nil,nil
        elseif etype == 0 and code == 0 then
            report({last_event_type=etype,last_event_code=code})
            if packet_x and packet_y and not uses_slots then packets = packets+1 end
            local contacts = 0
            for _,c in pairs(slots) do if c.active or c.released then contacts = contacts+1 end end
            if contacts > 1 or packets > 1 then multi = true end
            if mt_seen then
                for _,c in pairs(slots) do
                    if c.x and c.y and c.dirty and c.active ~= false and not c.first then c.first = {c.x,c.y} end
                    if c.released then
                        if c.first and not multi then tap(c.first[1],c.first[2]) end
                        c.first,c.released = nil,false
                    elseif not tracking_seen and not btn_seen and c.dirty and c.x and c.y and not multi then
                        tap(c.x,c.y)
                        c.first = nil
                    end
                    c.dirty = false
                end
            else
                if abs_x and abs_y and abs_dirty and abs_contact ~= false and not abs_first then abs_first = {abs_x,abs_y} end
                if abs_released then
                    if abs_first then tap(abs_first[1],abs_first[2]) end
                    abs_first,abs_released = nil,false
                elseif not btn_seen and abs_dirty and abs_x and abs_y then tap(abs_x,abs_y); abs_first = nil end
            end
            local active = false
            for _,c in pairs(slots) do if c.active then active = true end end
            if not active then multi = false end
            abs_dirty,packets,packet_x,packet_y = false,0,nil,nil
        end
    end
end
