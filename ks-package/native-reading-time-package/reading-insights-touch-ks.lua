-- Kindle Scribe input reader. It only
-- observes evdev events:
-- no EVIOCGRAB, no eatTapMode, and no write access to the input device.
local device = arg[1] or "/dev/input/touch"
local log_path = arg[2] or "/mnt/us/reading-time/reading_time_ks_debug.log"
local mode = arg[3] or "daily"
local calendar_offset = tonumber(arg[4] or "0") or 0
local calendar_days = tonumber(arg[5] or "31") or 31
local origin_x = tonumber(arg[6] or "0") or 0
local origin_y = tonumber(arg[7] or "0") or 0
local view_w = tonumber(arg[8] or "1860") or 1860
local view_h = tonumber(arg[9] or "2480") or 2480
local detail_pages = tonumber(arg[10] or "1") or 1
local detail_page = tonumber(arg[11] or "1") or 1
local pager_y = tonumber(arg[12] or "1576") or 1576
local total_period = arg[13] or "week"
local book_filter = arg[14] or "7d"
local transform_hint = arg[15] or "auto"
local logical_w, logical_h = 1860, 2480

local f = assert(io.open(device, "rb"))
local log = io.open(log_path, "a")
local x, y = nil, nil
local contact_reported = false

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
    local secondary = mode == "day_detail" or mode == "month_detail" or mode == "week_trend" or mode == "book_detail"
    if secondary and inside(px, py, 20, 20, 340, 165) then
        if mode == "day_detail" then return "day_detail_back" end
        if mode == "month_detail" then return "month_detail_back" end
        if mode == "book_detail" then return "book_detail_back" end
        return "week_trend_back"
    end
    if not secondary and inside(px, py, 20, 20, 340, 165) then return "exit" end
    if not secondary then
        if inside(px, py, 35, 165, 615, 300) then return "tab_daily" end
        if inside(px, py, 640, 165, 1220, 300) then return "tab_books" end
        if inside(px, py, 1245, 165, 1825, 300) then return "tab_total" end
    end

    if mode == "total" then
        if inside(px, py, 100, 930, 200, 1045) then return "total_week" end
        if inside(px, py, 205, 930, 305, 1045) then return "total_year" end
        if inside(px, py, 310, 930, 410, 1045) then return "total_all" end
        if total_period ~= "all" and inside(px, py, 470, 925, 650, 1065) then return "total_prev" end
        if total_period ~= "all" and inside(px, py, 1210, 925, 1390, 1065) then return "total_next" end
        if total_period == "week" and inside(px, py, 100, 365, 1760, 850) then return "week_trend_open" end
        if total_period == "year" and inside(px, py, 100, 1080, 1760, 2320) then
            local month = math.floor((px - 100) * 12 / 1660) + 1
            if month > 12 then month = 12 end
            return "year_month_" .. month
        end
        if total_period == "week" and inside(px, py, 150, 1080, 1760, 2320) then
            local day_index = math.floor((px - 150) * 7 / 1610)
            if day_index > 6 then day_index = 6 end
            return "week_day_" .. day_index
        end
    elseif mode == "daily" then
        if inside(px, py, 190, 330, 480, 470) then return "month_prev" end
        if inside(px, py, 1380, 330, 1670, 470) then return "month_next" end
        if inside(px, py, 650, 330, 1210, 470) then return "month_detail_open" end
        if detail_pages > 1 then
            if detail_page > 1 and inside(px, py, 650, pager_y, 850, pager_y+60) then return "detail_prev" end
            if detail_page < detail_pages and inside(px, py, 1010, pager_y, 1210, pager_y+60) then return "detail_next" end
        end
        -- The visible title is small, but the complete quick-preview header is
        -- a generous drill-down target.
        if inside(px, py, 90, 1820, 1770, 1925) then return "day_detail_open" end
        -- Same 1660 x 1120 grid as render_daily; Monday=0, four to six rows.
        local rows = math.floor((calendar_offset + calendar_days + 6) / 7)
        local cell_h = math.floor(1120 / rows)
        if px >= 100 and px < 1759 and py >= 520 and py < 520 + rows*cell_h then
            local col = math.floor((px - 100) / 237)
            local row = math.floor((py - 520) / cell_h)
            -- Ignore the ten-pixel gutters, including their far edges.
            if (px - 100) % 237 < 227 and (py - 520) % cell_h < cell_h - 10 then
                local day = row * 7 + col - calendar_offset + 1
                if day >= 1 and day <= calendar_days then return "day_" .. day end
            end
            -- Consume visible blank cells/gutters at the UI hit-test layer:
            -- they must not fall through to the swapped-axis compatibility retry.
            return "ignore"
        end
    elseif mode == "day_detail" then
        if detail_pages > 1 then
            if detail_page > 1 and inside(px, py, 650, pager_y, 850, pager_y+65) then return "day_detail_prev" end
            if detail_page < detail_pages and inside(px, py, 1010, pager_y, 1210, pager_y+65) then return "day_detail_next" end
        end
    elseif mode == "book_detail" then
        if inside(px, py, 410, 1640, 700, 1775) then return "book_month_prev" end
        if inside(px, py, 1160, 1640, 1450, 1775) then return "book_month_next" end
        local rows = math.floor((calendar_offset + calendar_days + 6) / 7)
        local cell_h = math.floor(430 / rows)
        if px >= 100 and px < 1759 and py >= 1790 and py < 1790 + rows*cell_h then
            local col = math.floor((px - 100) / 237)
            local row = math.floor((py - 1790) / cell_h)
            local day = row * 7 + col - calendar_offset + 1
            if day >= 1 and day <= calendar_days then return "book_day_" .. day end
            return "book_calendar_clear"
        end
        if inside(px, py, 70, 1030, 1790, 2390) then return "book_calendar_clear" end
    elseif mode == "books" then
        if inside(px, py, 100, 355, 420, 445) then return "books_7d" end
        if inside(px, py, 510, 355, 830, 445) then return "books_month" end
        if inside(px, py, 920, 355, 1240, 445) then return "books_year" end
        if inside(px, py, 1330, 355, 1760, 445) then return "books_all" end
        if inside(px, py, 100, 465, 1750, 2060) then
            local column = px <= 900 and 0 or (px >= 950 and 1 or nil)
            local row = math.floor((py - 465) / 545)
            local local_y = (py - 465) % 545
            if column ~= nil and row < 3 and local_y <= 505 then
                return "book_row_" .. (row * 2 + column + 1)
            end
            return "ignore"
        end
        if inside(px, py, 80, 2210, 520, 2410) then return "page_prev" end
        if inside(px, py, 1340, 2210, 1780, 2410) then return "page_next" end
    end
    return nil
end

-- Map physical framebuffer coordinates back to the 1860x2480 design canvas.
-- The viewer uses the inverse of this transform for every rendered element.
local function action_for_physical(px, py, transform)
    local tx, ty = px, py
    if transform == "swap" then tx, ty = py, px
    elseif transform == "invert_xy" then tx, ty = 2 * origin_x + view_w - 1 - px, 2 * origin_y + view_h - 1 - py
    elseif transform == "invert_x" then tx = 2 * origin_x + view_w - 1 - px
    elseif transform == "invert_y" then ty = 2 * origin_y + view_h - 1 - py
    elseif transform == "swap_invert_xy" then tx, ty = origin_x + view_w - 1 - (py - origin_y), origin_y + view_h - 1 - (px - origin_x)
    elseif transform == "swap_invert_x" then tx, ty = origin_x + view_w - 1 - (py - origin_y), origin_y + (px - origin_x)
    elseif transform == "swap_invert_y" then tx, ty = origin_x + (py - origin_y), origin_y + view_h - 1 - (px - origin_x)
    end
    px, py = tx, ty
    if px < origin_x or py < origin_y or
       px > origin_x + view_w or py > origin_y + view_h then
        return nil
    end
    local lx = math.floor((px - origin_x) * logical_w / view_w + 0.5)
    local ly = math.floor((py - origin_y) * logical_h / view_h + 0.5)
    local action = action_for_logical(lx, ly)
    if action then
        note(string.format("[INPUT] mapped transform=%s client_x=%d client_y=%d action=%s", transform, lx, ly, action))
    end
    return action
end

note(string.format("[INPUT] interactive watcher started mode=%s viewport=%dx%d+%d+%d",
    mode, view_w, view_h, origin_x, origin_y))
note("[INPUT] transform_hint=" .. transform_hint)
while true do
    local event = f:read(16)
    if not event or #event ~= 16 then note("[INPUT] short read"); os.exit(2) end
    local etype = u16(event, 9)
    local code = u16(event, 11)
    local value = u32(event, 13)
    if etype == 3 then
        if code == 53 or code == 0 then x = value end
        if code == 54 or code == 1 then y = value end
        if code == 57 then
            if value == 4294967295 then x, y, contact_reported = nil, nil, false
            else contact_reported = false end
        end
    elseif etype == 1 and code == 330 then
        if value == 0 then x, y, contact_reported = nil, nil, false
        else contact_reported = false end
    elseif etype == 0 and code == 0 and x and y and not contact_reported then
        contact_reported = true
        note(string.format("[INPUT] touch received raw_x=%d raw_y=%d screen_x=%d screen_y=%d", x, y, x, y))
        -- KS firmware has shipped both portrait and rotated input mappings.
        -- Prefer the supplied hint, then try every lossless rectangle transform.
        local order = {"direct", "swap", "invert_xy", "swap_invert_xy", "invert_x", "invert_y", "swap_invert_x", "swap_invert_y"}
        if transform_hint ~= "auto" then table.insert(order, 1, transform_hint) end
        local action = nil
        for _, transform in ipairs(order) do
            action = action_for_physical(x, y, transform)
            if action then break end
        end
        if action and action ~= "ignore" then finish(action) end
    end
end
