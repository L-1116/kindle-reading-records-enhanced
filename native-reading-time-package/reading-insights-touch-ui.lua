-- Resolution-independent interactive dashboard input reader. It only
-- observes evdev events:
-- no EVIOCGRAB, no eatTapMode, and no write access to the input device.
local device = arg[1] or "/dev/input/event1"
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

local f = assert(io.open(device, "rb"))
local log = io.open(log_path, "a")
local x, y = nil, nil

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
    io.write(action, "\n")
    f:close()
    if log then log:close() end
    os.exit(0)
end
local function inside(px, py, left, top, right, bottom)
    return px >= left and px <= right and py >= top and py <= bottom
end
local function action_for_logical(px, py)
    if mode == "day_detail" and inside(px, py, 20, 20, 300, 155) then return "day_detail_back" end
    if mode ~= "day_detail" and inside(px, py, 20, 20, 270, 155) then return "exit" end
    if mode ~= "day_detail" then
        if inside(px, py, 35, 165, 415, 275) then return "tab_daily" end
        if inside(px, py, 430, 165, 800, 275) then return "tab_books" end
        if inside(px, py, 815, 165, 1237, 275) then return "tab_total" end
    end

    if mode == "total" then
        if inside(px, py, 65, 638, 160, 692) then return "total_week" end
        if inside(px, py, 180, 638, 275, 692) then return "total_year" end
        if inside(px, py, 280, 625, 440, 750) then return "total_prev" end
        if inside(px, py, 840, 625, 1000, 750) then return "total_next" end
        if total_period == "week" and inside(px, py, 135, 760, 1181, 1450) then
            local day_index = math.floor((px - 135) * 7 / 1047)
            if day_index > 6 then day_index = 6 end
            return "week_day_" .. day_index
        end
    elseif mode == "daily" then
        if inside(px, py, 220, 300, 450, 430) then return "month_prev" end
        if inside(px, py, 840, 300, 1070, 430) then return "month_next" end
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
    elseif mode == "books" then
        if inside(px, py, 70, 285, 424, 339) then return "books_7d" end
        if inside(px, py, 459, 285, 813, 339) then return "books_month" end
        if inside(px, py, 848, 285, 1202, 339) then return "books_year" end
        if inside(px, py, 55, 1465, 385, 1595) then return "page_prev" end
        if inside(px, py, 885, 1465, 1217, 1595) then return "page_next" end
    end
    return nil
end

-- Map physical framebuffer coordinates back to the 1272x1696 design canvas.
-- The viewer uses the inverse of this transform for every rendered element.
local function action_for_physical(px, py)
    if px < origin_x or py < origin_y or
       px > origin_x + view_w or py > origin_y + view_h then
        return nil
    end
    local lx = math.floor((px - origin_x) * logical_w / view_w + 0.5)
    local ly = math.floor((py - origin_y) * logical_h / view_h + 0.5)
    local action = action_for_logical(lx, ly)
    if action then
        note(string.format("mapped x=%d y=%d action=%s", lx, ly, action))
    end
    return action
end

note(string.format("interactive watcher started mode=%s viewport=%dx%d+%d+%d",
    mode, view_w, view_h, origin_x, origin_y))
while true do
    local event = f:read(16)
    if not event or #event ~= 16 then note("short read"); os.exit(2) end
    local etype = u16(event, 9)
    local code = u16(event, 11)
    local value = u32(event, 13)
    if etype == 3 then
        if code == 53 or code == 0 then x = value end
        if code == 54 or code == 1 then y = value end
    elseif etype == 0 and code == 0 and x and y then
        note(string.format("tap x=%d y=%d", x, y))
        -- Some Kindle touch drivers report portrait coordinates directly,
        -- while others expose the axes swapped. Try both non-destructively.
        local action = action_for_physical(x, y) or action_for_physical(y, x)
        if action and action ~= "ignore" then finish(action) end
        -- Clear coordinates so repeated SYN_REPORT events cannot reuse a tap.
        x, y = nil, nil
    end
end
