-- Foreground-only compositor for the optimized reading records dashboard.
-- It reads a simple TSV drawing specification and writes opaque PGM regions.
-- No process is daemonized and no input or user data is modified.

local asset_dir = assert(arg[1], "missing render asset directory")
local spec_path = assert(arg[2], "missing render specification")

local function read_all(path)
    local file = assert(io.open(path, "rb"))
    local data = assert(file:read("*a"))
    file:close()
    return data
end

local function split_tsv(line)
    local fields, start = {}, 1
    while true do
        local pos = string.find(line, "\t", start, true)
        if not pos then
            fields[#fields + 1] = string.sub(line, start)
            return fields
        end
        fields[#fields + 1] = string.sub(line, start, pos - 1)
        start = pos + 1
    end
end

local function utf8_char(code)
    if code < 0x80 then
        return string.char(code)
    elseif code < 0x800 then
        return string.char(0xC0 + math.floor(code / 0x40), 0x80 + code % 0x40)
    elseif code < 0x10000 then
        return string.char(
            0xE0 + math.floor(code / 0x1000),
            0x80 + math.floor(code / 0x40) % 0x40,
            0x80 + code % 0x40
        )
    end
    return string.char(
        0xF0 + math.floor(code / 0x40000),
        0x80 + math.floor(code / 0x1000) % 0x40,
        0x80 + math.floor(code / 0x40) % 0x40,
        0x80 + code % 0x40
    )
end

local function utf8_chars(text)
    local index, length = 1, #text
    return function()
        if index > length then return nil end
        local first = string.byte(text, index)
        local bytes = 1
        if first >= 0xF0 then bytes = 4
        elseif first >= 0xE0 then bytes = 3
        elseif first >= 0xC0 then bytes = 2 end
        local char = string.sub(text, index, index + bytes - 1)
        index = index + bytes
        return char
    end
end

local function parse_pgm(path)
    local data = read_all(path)
    local pos = 1
    local function token()
        while true do
            local byte = string.byte(data, pos)
            if not byte then error("invalid PGM header") end
            if byte == 35 then
                local newline = assert(string.find(data, "\n", pos, true))
                pos = newline + 1
            elseif byte == 9 or byte == 10 or byte == 13 or byte == 32 then
                pos = pos + 1
            else
                break
            end
        end
        local start = pos
        while true do
            local byte = string.byte(data, pos)
            if not byte or byte == 9 or byte == 10 or byte == 13 or byte == 32 then break end
            pos = pos + 1
        end
        return string.sub(data, start, pos - 1)
    end
    assert(token() == "P5", "glyph atlas must be binary PGM")
    local width = assert(tonumber(token()), "missing PGM width")
    local height = assert(tonumber(token()), "missing PGM height")
    assert(tonumber(token()) == 255, "unsupported PGM depth")
    while true do
        local byte = string.byte(data, pos)
        if byte == 9 or byte == 10 or byte == 13 or byte == 32 then pos = pos + 1 else break end
    end
    local pixels = string.sub(data, pos)
    assert(#pixels == width * height, "truncated glyph atlas")
    return { width = width, height = height, pixels = pixels }
end

local atlas = parse_pgm(asset_dir .. "/dynamic-glyphs.pgm")
local glyphs = {}
for line in io.lines(asset_dir .. "/dynamic-glyphs.tsv") do
    local f = split_tsv(line)
    if f[1] ~= "style" then
        local style, size = f[1], assert(tonumber(f[2]))
        local char = utf8_char(assert(tonumber(f[3], 16)))
        local key = style .. ":" .. size .. ":" .. char
        glyphs[key] = {
            x = assert(tonumber(f[4])), y = assert(tonumber(f[5])),
            w = assert(tonumber(f[6])), h = assert(tonumber(f[7])),
            advance = assert(tonumber(f[8])),
            bearing_x = assert(tonumber(f[9]), "missing baseline metrics"),
            bearing_y = assert(tonumber(f[10])), baseline = assert(tonumber(f[11])),
            ink = tonumber(f[12]) == 1
        }
    end
end

local canvases = {}

local function new_canvas(id, width, height, output)
    assert(not canvases[id], "duplicate canvas " .. id)
    local rows = {}
    local blank = string.rep(string.char(255), width)
    for y = 1, height do rows[y] = blank end
    canvases[id] = { width = width, height = height, output = output, rows = rows }
end

local function set_run(canvas, x, y, width, value)
    if y < 0 or y >= canvas.height or width <= 0 then return end
    if x < 0 then width = width + x; x = 0 end
    if x + width > canvas.width then width = canvas.width - x end
    if width <= 0 then return end
    local row = canvas.rows[y + 1]
    canvas.rows[y + 1] = string.sub(row, 1, x)
        .. string.rep(string.char(value), width)
        .. string.sub(row, x + width + 1)
end

local function rect(canvas, x, y, width, height, value)
    for row = y, y + height - 1 do set_run(canvas, x, row, width, value) end
end

local function rounded_rect(canvas, x, y, width, height, radius, value)
    radius = math.max(0, math.min(radius, math.floor(math.min(width, height) / 2)))
    for row = 0, height - 1 do
        local inset = 0
        if row < radius then
            local dy = radius - row - 0.5
            inset = math.ceil(radius - math.sqrt(math.max(0, radius * radius - dy * dy)))
        elseif row >= height - radius then
            local dy = row - (height - radius) + 0.5
            inset = math.ceil(radius - math.sqrt(math.max(0, radius * radius - dy * dy)))
        end
        set_run(canvas, x + inset, y + row, width - inset * 2, value)
    end
end

local function glyph_for(style, size, char)
    return glyphs[style .. ":" .. size .. ":" .. char]
        or glyphs["R:" .. size .. ":" .. char]
end

local function measure(style, size, text)
    local width, left, right = 0, nil, nil
    for char in utf8_chars(text) do
        local glyph = assert(glyph_for(style, size, char), "missing glyph: " .. char)
        if glyph.ink then
            left = math.min(left or math.huge, width + glyph.bearing_x)
            right = math.max(right or -math.huge, width + glyph.bearing_x + glyph.w)
        end
        width = width + glyph.advance
    end
    return width, left or 0, right or width
end

local function draw_glyph(canvas, glyph, x, y, color)
    for row_index = 0, glyph.h - 1 do
        local atlas_start = (glyph.y + row_index) * atlas.width + glyph.x + 1
        local mask = string.sub(atlas.pixels, atlas_start, atlas_start + glyph.w - 1)
        local target_y = y + row_index
        if target_y >= 0 and target_y < canvas.height then
            local target = canvas.rows[target_y + 1]
            local bytes = {}
            for column = 1, glyph.w do
                local target_x = x + column - 1
                if target_x >= 0 and target_x < canvas.width then
                    local alpha = 255 - string.byte(mask, column)
                    local background = string.byte(target, target_x + 1)
                    bytes[#bytes + 1] = string.char(math.floor((background * (255 - alpha) + color * alpha + 127) / 255))
                else
                    bytes[#bytes + 1] = string.char(255)
                end
            end
            local left = math.max(0, x)
            local right = math.min(canvas.width, x + glyph.w)
            if right > left then
                local offset = left - x + 1
                local replacement = table.concat(bytes, "", offset, offset + right - left - 1)
                canvas.rows[target_y + 1] = string.sub(target, 1, left)
                    .. replacement .. string.sub(target, right + 1)
            end
        end
    end
end

local function text(canvas, style, size, x, y, align, color, message, background)
    local width, left, right = measure(style, size, message)
    if align == "center" then x = math.floor(x - (left + right) / 2)
    elseif align == "right" then x = x - right end
    if background then
        local bottom = 0
        for char in utf8_chars(message) do
            local glyph = assert(glyph_for(style, size, char))
            bottom = math.max(bottom, glyph.baseline + glyph.bearing_y + glyph.h)
        end
        -- A plain white margin keeps chart grid lines out of value labels.
        rect(canvas, x + left - 4, y - 3, right - left + 8, bottom + 6, background)
    end
    -- Each whole string has one font size and baseline. Cropped glyph masks
    -- retain their font bearings; digits/CJK are never independently top-aligned.
    local baseline = nil
    for char in utf8_chars(message) do
        local glyph = assert(glyph_for(style, size, char), "missing glyph: " .. char)
        baseline = baseline or (y + glyph.baseline)
        assert(baseline == y + glyph.baseline, "inconsistent font baseline")
        draw_glyph(canvas, glyph, x + glyph.bearing_x, baseline + glyph.bearing_y, color)
        x = x + glyph.advance
    end
end

local function write_canvas(canvas)
    local file = assert(io.open(canvas.output, "wb"))
    assert(file:write("P5\n", canvas.width, " ", canvas.height, "\n255\n"))
    for y = 1, canvas.height do assert(file:write(canvas.rows[y])) end
    assert(file:close())
end

for line in io.lines(spec_path) do
    if line ~= "" and string.sub(line, 1, 1) ~= "#" then
        local f = split_tsv(line)
        local op = f[1]
        if op == "canvas" then
            new_canvas(f[2], assert(tonumber(f[3])), assert(tonumber(f[4])), f[5])
        elseif op == "rect" then
            rect(assert(canvases[f[2]]), tonumber(f[3]), tonumber(f[4]), tonumber(f[5]), tonumber(f[6]), tonumber(f[7]))
        elseif op == "round" then
            rounded_rect(assert(canvases[f[2]]), tonumber(f[3]), tonumber(f[4]), tonumber(f[5]), tonumber(f[6]), tonumber(f[7]), tonumber(f[8]))
        elseif op == "text" then
            text(assert(canvases[f[2]]), f[3], tonumber(f[4]), tonumber(f[5]), tonumber(f[6]), f[7], tonumber(f[8]), f[9] or "", tonumber(f[10]))
        elseif op == "write" then
            write_canvas(assert(canvases[f[2]]))
        else
            error("unknown render operation: " .. tostring(op))
        end
    end
end
