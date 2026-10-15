-- Standard evdev preflight, derived from the KS design. Never consumes events.
local base, listing_path = assert(arg[1]), assert(arg[2])
local sysfs = os.getenv("READING_INPUT_SYSFS") or "/sys/class/input"
local devroot = os.getenv("READING_INPUT_DEV") or "/dev/input"
local function read(path)
    local f = io.open(path, "rb")
    if not f then return nil end
    local s = f:read("*a"); f:close()
    return s and s:gsub("%s+$", "")
end
local function put(f, key, value)
    f:write(key, "=", tostring(value == nil and "unknown" or value):gsub("[\r\n]", " "), "\n")
end
-- Sysfs bitmaps use kernel unsigned-long words, NOT the Lua userspace ABI.
local kernel_bits = tonumber(os.getenv("READING_INPUT_WORD_BITS"))
local machine = os.getenv("READING_TOUCH_MACHINE") or ""
if not kernel_bits then
    if machine:find("64", 1, true) then kernel_bits = 64
    elseif machine:match("^arm") or machine:match("^i%d86$") then kernel_bits = 32 end
end
local function has(hex, code)
    local words = {}
    for word in (hex or ""):gmatch("%x+") do table.insert(words, 1, word) end
    local bits = kernel_bits or 32
    for _, word in ipairs(words) do if #word > 8 then bits = 64 end end
    local word = words[math.floor(code / bits) + 1]
    if not word then return false end
    local bit = code % bits
    local index = #word - math.floor(bit / 4)
    if index < 1 then return false end
    local digit = tonumber(word:sub(index, index), 16)
    return digit and math.floor(digit / 2 ^ (bit % 4)) % 2 == 1 or false
end
local function abi()
    local override = os.getenv("READING_EVENT_STRUCT_SIZE")
    if override and override ~= "" then return tonumber(override), "internal_override" end
    -- /proc/self/exe identifies the interpreter actually running this probe.
    local binary = os.getenv("READING_LUA_BINARY") or "/proc/self/exe"
    local f = io.open(binary, "rb")
    local elf = f and f:read(6)
    if f then f:close() end
    if elf and elf:sub(1, 4) == "\127ELF" and elf:byte(6) == 1 then
        if elf:byte(5) == 1 then return 16, "lua_elf32" end
        if elf:byte(5) == 2 then return 24, "lua_elf64" end
    end
    return nil, "lua_elf_class_unavailable"
end
local output = assert(io.open(base .. "/touch-last.log", "wb"))
put(output, "timestamp", os.date("%Y-%m-%dT%H:%M:%S%z"))
put(output, "package", "Standard")
put(output, "device", os.getenv("READING_TOUCH_MODEL"))
for _, key in ipairs({"firmware", "machine", "arch", "screen_width", "screen_height", "orientation", "viewport", "logical_size"}) do
    put(output, key, os.getenv("READING_TOUCH_" .. key:upper()))
end
local candidates = {}
local listing = assert(io.open(listing_path, "rb"))
for entry in listing:lines() do
    entry = entry:gsub("%s+$", "")
    if entry:match("^event%d+$") then
        local root = sysfs .. "/" .. entry .. "/device/"
        local name = read(root .. "name") or "unknown"
        local ev = read(root .. "capabilities/ev") or ""
        local abs = read(root .. "capabilities/abs") or ""
        local keys = read(root .. "capabilities/key") or ""
        local prop = read(root .. "properties") or read(root .. "capabilities/prop") or ""
        local xy, mt = has(abs, 0) and has(abs, 1), has(abs, 53) and has(abs, 54)
        local lower = name:lower()
        local pen = lower:find("stylus", 1, true) or lower:find("wacom", 1, true) or
            lower:find("digitizer", 1, true) or lower:match("%f[%a]pen%f[%A]") or
            has(keys, 320) or has(keys, 321) or has(keys, 331) or has(keys, 332) or
            has(abs, 26) or has(abs, 27)
        local sensor = lower:find("accel", 1, true) or lower:find("gyro", 1, true) or
            lower:find("sensor", 1, true) or lower:find("_acc", 1, true) or
            lower:find("power", 1, true) or lower:find("pwrkey", 1, true) or
            lower:find("keyboard", 1, true) or has(prop, 6) or has(keys, 116) or
            (has(keys, 30) and has(keys, 44))
        local named = lower:find("touch", 1, true) or lower:find("zforce", 1, true) or
            lower:find("cyttsp", 1, true) or lower:find("fts", 1, true) or
            lower:find("goodix", 1, true) or lower == "pt_mt" or lower:match("_ts$")
        local class, score = "unrelated", -1
        if pen then class = "pen_digitizer"
        elseif sensor then class = "sensor_or_button"
        elseif has(prop, 0) or has(prop, 2) then class = "pointer_or_touchpad"
        elseif has(ev, 3) and (xy or mt) then
            if has(prop, 1) then class, score = mt and "finger_mt" or "finger_xy", mt and 60 or 50
            elseif mt then class, score = "finger_mt_legacy", 40
            elseif has(keys, 330) then class, score = "finger_xy_contact", 30
            elseif named then class, score = "finger_xy_legacy", 20
            else class = "absolute_unknown" end
        end
        if os.getenv("READING_TOUCH_REQUIRE_CONTACT") == "1" and not has(keys,330) and not has(abs,57) then
            class, score = "idle_contact_protocol_unavailable", -1
        end
        if score > 0 and named then score = score + 1 end
        local path = devroot .. "/" .. entry
        local readable = io.open(path, "rb") -- open/close only: no event read
        if readable then readable:close() else class, score = class .. "_unreadable", -1 end
        candidates[#candidates+1] = {path=path, name=name, ev=ev, abs=abs, key=keys,
            prop=prop, class=class, score=score, xy=xy, mt=mt}
    end
end
listing:close()
table.sort(candidates, function(a,b) return a.path < b.path end)
put(output, "touch_candidates_count", #candidates)
local selected, tied, reason
for i,c in ipairs(candidates) do
    local prefix = "candidate_" .. (i-1) .. "_"
    for _, field in ipairs({"path", "name", "ev", "abs", "key", "prop", "class", "score"}) do
        local label = ({ev="ev_cap",abs="abs_cap",key="key_cap",prop="prop_cap",class="classification"})[field] or field
        put(output, prefix .. label, c[field])
    end
    put(output, prefix .. "has_xy", c.xy)
    put(output, prefix .. "has_mt_position_xy", c.mt)
    if c.score > 0 then
        if not selected or c.score > selected.score then selected, tied = c, false
        elseif c.score == selected.score then tied = true end
    end
end
local override = os.getenv("READING_TOUCH_DEVICE")
if override and override ~= "" then
    selected, tied, reason = nil, false, "override_rejected"
    for _,c in ipairs(candidates) do
        if c.path == override and c.score > 0 then selected, reason = c, "validated_override" end
    end
elseif tied then selected, reason = nil, "ambiguous_finger_touch_candidates" end
reason = reason or (selected and selected.class or "no_finger_touch_candidate")
local size, size_reason = abi()
local bounds, count, configured = {}, 0, false
for _, axis in ipairs({"X", "Y"}) do
    local low = tonumber(os.getenv("READING_TOUCH_ABS_" .. axis .. "_MIN"))
    local high = tonumber(os.getenv("READING_TOUCH_ABS_" .. axis .. "_MAX"))
    if os.getenv("READING_TOUCH_ABS_" .. axis .. "_MIN") or os.getenv("READING_TOUCH_ABS_" .. axis .. "_MAX") then configured = true end
    if low and high and high > low then bounds[axis] = {low,high}; count = count+1 end
end
local transform = os.getenv("READING_TOUCH_TRANSFORM") or "auto"
local valid = {auto=true,direct=true,swap=true,invert_x=true,invert_y=true,invert_xy=true,
    swap_invert_x=true,swap_invert_y=true,swap_invert_xy=true}
local error_reason
if not selected then error_reason = reason
elseif size ~= 16 and size ~= 24 then error_reason = size_reason
elseif not valid[transform] then error_reason = "invalid_transform"
elseif configured and count ~= 2 then error_reason = "incomplete_raw_range" end
put(output, "selected_touch", selected and selected.path or "none")
put(output, "selection_reason", reason)
put(output, "event_struct_size", size)
put(output, "event_struct_reason", size_reason)
put(output, "coordinate_mode", count == 2 and "normalized_configured_range" or "screen_pixels_unverified_range")
put(output, "coordinate_transform", transform)
put(output, "transform_reason", transform == "auto" and "screen_geometry_direct_default" or "internal_metadata")
for _,axis in ipairs({"X","Y"}) do
    put(output, "raw_abs_" .. axis:lower() .. "_min", bounds[axis] and bounds[axis][1])
    put(output, "raw_abs_" .. axis:lower() .. "_max", bounds[axis] and bounds[axis][2])
end
put(output, "reader_state", error_reason and "preflight_failed" or "probe_ok")
put(output, "reader_error", error_reason or "none")
for _, key in ipairs({"last_event_type","last_event_code","last_raw_x","last_raw_y",
    "last_physical_x","last_physical_y","last_logical_x","last_logical_y","last_transform","last_action"}) do put(output,key,"none") end
output:close()
if error_reason then os.exit(2) end
io.write(selected.path, "\n", size, "\n")
for _,axis in ipairs({"X","Y"}) do
    for _,value in ipairs(bounds[axis] or {"unknown","unknown"}) do io.write(value,"\n") end
end
io.write(transform,"\n")
