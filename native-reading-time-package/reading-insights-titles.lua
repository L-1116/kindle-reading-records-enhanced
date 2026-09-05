-- Read-only title layout for FBInk; Lua 5.1 compatible, no font replacement.
local input = assert(arg[1])
local width, size = assert(tonumber(arg[2])), assert(tonumber(arg[3]))
local number, row_height = tonumber(arg[4]) or 0, assert(tonumber(arg[5]))
local script_dir = arg[0]:match("^(.*)/") or "."
local advances = dofile(script_dir .. "/reading-insights-title-widths.lua")
local row = 0
for line in io.lines(input) do
    local title = line:match("^[^\t]*\t([^\t]*)")
    if title and title ~= "" then
        if number > 0 then title = (number + row) .. ". " .. title end
        local chars, widths = {}, {}
        for ch in title:gmatch("[%z\1-\127\194-\244][\128-\191]*") do
            chars[#chars+1] = ch
            local b = ch:byte()
            -- Non-ASCII gets a full em; reserve 8% for native rasterizer differences.
            widths[#widths+1] = ((b>=32 and b<=126) and advances[b-31] or 1) * size * 1.08
        end
        local pos = 1
        for n = 1, 2 do
            if pos > #chars then break end
            local start, used = pos, 0
            local limit = width - (n==2 and size*1.08 or 0)
            while pos <= #chars and used + widths[pos] <= limit do
                used = used + widths[pos]; pos = pos + 1
            end
            local text = table.concat(chars, "", start, pos-1)
            if n == 2 and pos <= #chars then text = text .. "…" end
            io.write(row*row_height+(n-1)*(size+8), "\t", text, "\n")
        end
        row = row + 1
    end
end
