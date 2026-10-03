-- KS evdev preflight. Runs before painting, and never reads an event device.
local base = assert(arg[1])
local sysfs = os.getenv("READING_INPUT_SYSFS") or "/sys/class/input"
local devroot = os.getenv("READING_INPUT_DEV") or "/dev/input"
local report = base .. "/touch-last.log"
local function read(path)
    local f = io.open(path, "rb")
    if not f then return nil end
    local s = f:read("*a"); f:close()
    return s and s:gsub("%s+$", "")
end
local function put(f, key, value)
    f:write(key, "=", tostring(value or "unknown"):gsub("[\r\n]", " "), "\n")
end
local function has(hex, code)
    if not hex then return false end
    local words = {}
    for word in hex:gmatch("%x+") do table.insert(words, 1, word) end
    local word_bits = 32
    for _, word in ipairs(words) do if #word > 8 then word_bits = 64 end end
    local word = words[math.floor(code / word_bits) + 1]
    if not word then return false end
    local within = code % word_bits
    local digit = tonumber(word:sub(-math.floor(within / 4) - 1, -math.floor(within / 4) - 1), 16)
    return digit and math.floor(digit / 2 ^ (within % 4)) % 2 == 1 or false
end
local function abi()
    local forced = os.getenv("READING_EVENT_STRUCT_SIZE")
    if forced then return tonumber(forced), "override" end
    local binary = os.getenv("READING_LUA_BINARY")
    local elf
    if binary then
        local f = io.open(binary, "rb")
        if f then elf = f:read(6); f:close() end
    end
    if elf and elf:sub(1, 4) == "\127ELF" and elf:byte(6) == 1 then
        if elf:byte(5) == 1 then return 16, "lua_elf32" end
        if elf:byte(5) == 2 then return 24, "lua_elf64" end
    end
    -- getconf describes its own executable and may differ from the Lua ELF.
    return nil, "lua_elf_class_unavailable"
end
local output = assert(io.open(report, "wb"))
put(output, "timestamp", os.date("%Y-%m-%dT%H:%M:%S%z"))
put(output, "package", "V3-KS-touch-compat-hotfix")
put(output, "device", os.getenv("READING_TOUCH_MODEL"))
for _, key in ipairs({"firmware", "machine", "arch", "screen_width", "screen_height", "orientation", "viewport", "logical_size"}) do
    put(output, key, os.getenv("READING_TOUCH_" .. key:upper()))
end
local candidates = {}
local listing = io.open(assert(arg[2], "missing event listing"), "rb")
if listing then
    for line in listing:lines() do
        local entry = line:gsub("%s+$", "")
        if entry:match("^event%d+$") then
            local path = devroot .. "/" .. entry
            local root = sysfs .. "/" .. entry .. "/device/"
            local name = read(root .. "name") or "unknown"
            local ev = read(root .. "capabilities/ev") or ""
            local abs = read(root .. "capabilities/abs") or ""
            local prop = read(root .. "properties") or read(root .. "capabilities/prop") or ""
            local xy = has(abs, 0) and has(abs, 1)
            local mt = has(abs, 53) and has(abs, 54)
            local lower = name:lower()
            local pen = lower:find("stylus", 1, true) or lower:find("wacom", 1, true) or
                        lower:find("digitizer", 1, true) or lower:find(" pen", 1, true)
            local finger = lower == "pt_mt" or lower:find("touch", 1, true) or
                           lower:find("zforce", 1, true) or lower:find("cyttsp", 1, true) or
                           lower:find("fts", 1, true)
            local unrelated = lower:find("accel", 1, true) or lower:find("gyro", 1, true) or
                              lower:find("_acc", 1, true) or lower:find("power", 1, true) or
                              lower:find("pwrkey", 1, true) or lower:find("keyboard", 1, true) or
                              has(prop, 6)
            local class, score = "unrelated", -1
            if has(ev, 3) and (xy or mt) then
                if pen then class, score = "pen_digitizer", -1
                elseif unrelated then class, score = "sensor_or_button", -1
                elseif mt and (finger or has(prop, 1)) then class, score = "finger_mt", 30
                elseif finger and xy then class, score = "finger_xy", 20
                else class, score = "absolute_unknown", -1 end
            end
            local readable = io.open(path, "rb")
            if readable then readable:close() end
            if not readable then class, score = class .. "_unreadable", -1 end
            table.insert(candidates, {path=path, name=name, ev=ev, abs=abs, prop=prop,
                xy=xy, mt=mt, class=class, score=score})
        end
    end
    listing:close()
end
table.sort(candidates, function(a,b) return a.path < b.path end)
put(output, "touch_candidates_count", #candidates)
local override = os.getenv("READING_TOUCH_DEVICE")
if override == "" then override = nil end
local selected, reason, override_candidate
for i, c in ipairs(candidates) do
    local prefix = "candidate_" .. (i - 1) .. "_"
    for _, item in ipairs({"path", "name", "ev", "abs", "prop", "class"}) do
        local label = ({ev="ev_cap", abs="abs_cap", prop="prop_cap", class="classification"})[item] or item
        put(output, prefix .. label, c[item])
    end
    put(output, prefix .. "has_xy", c.xy)
    put(output, prefix .. "has_mt_position_xy", c.mt)
    if c.score > 0 and (not selected or c.score > selected.score) then selected = c end
    if override and c.path == override then override_candidate = c end
end
if override then
    if override_candidate and override_candidate.score > 0 then
        selected, reason = override_candidate, "validated_override"
    else
        selected, reason = nil, override_candidate and "override_rejected" or "override_not_enumerated"
    end
end
if not reason then reason = selected and selected.class or "no_finger_touch_candidate" end
local size, size_reason = abi()
local bounds = {}
for _, axis in ipairs({"x", "y"}) do
    local upper = axis:upper()
    local low = tonumber(os.getenv("READING_TOUCH_ABS_" .. upper .. "_MIN"))
    local high = tonumber(os.getenv("READING_TOUCH_ABS_" .. upper .. "_MAX"))
    if low and high and high > low then bounds[axis] = {low, high} end
end
local normalized = bounds.x and bounds.y
put(output, "selected_touch", selected and selected.path or "none")
put(output, "selection_reason", reason)
put(output, "event_struct_size", size or "unknown")
put(output, "event_struct_reason", size_reason)
put(output, "coordinate_mode", normalized and "normalized_configured_range" or "direct_unverified_range")
for _, axis in ipairs({"x", "y"}) do
    put(output, "raw_abs_" .. axis .. "_min", bounds[axis] and bounds[axis][1] or "unknown")
    put(output, "raw_abs_" .. axis .. "_max", bounds[axis] and bounds[axis][2] or "unknown")
end
output:flush(); output:close()
if not selected or (size ~= 16 and size ~= 24) then os.exit(2) end
io.write(selected.path, "\n", tostring(size), "\n")
for _, axis in ipairs({"x", "y"}) do
    for _, value in ipairs(bounds[axis] or {"unknown", "unknown"}) do io.write(value, "\n") end
end
