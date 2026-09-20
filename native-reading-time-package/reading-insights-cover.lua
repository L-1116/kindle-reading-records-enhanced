-- Lightweight, offline cover helpers for the Kindle dashboard.
--
-- This deliberately supports only the formats requested by the dashboard:
-- EPUB metadata discovery and MOBI/PalmDB embedded images.  PDF rendering is
-- not implemented here because shipping a renderer would dwarf the plugin.

local mode = arg[1]

local function fail(message)
    if message then io.stderr:write(message, "\n") end
    os.exit(1)
end

local function read_file(path, limit)
    local f = io.open(path, "rb")
    if not f then return nil end
    local data = f:read(limit and limit + 1 or "*a")
    f:close()
    if not data or (limit and #data > limit) then return nil end
    return data
end

local function be16(s, p)
    local a, b = s:byte(p, p + 1)
    if not a or not b then return nil end
    return a * 256 + b
end

local function be32(s, p)
    local a, b, c, d = s:byte(p, p + 3)
    if not a or not d then return nil end
    return ((a * 256 + b) * 256 + c) * 256 + d
end

local function xml_decode(s)
    if not s then return nil end
    s = s:gsub("&#x([0-9A-Fa-f]+);", function(n)
        local value = tonumber(n, 16)
        return value and value < 256 and string.char(value) or ""
    end)
    s = s:gsub("&#([0-9]+);", function(n)
        local value = tonumber(n, 10)
        return value and value < 256 and string.char(value) or ""
    end)
    return (s:gsub("&quot;", '"'):gsub("&apos;", "'")
        :gsub("&lt;", "<"):gsub("&gt;", ">"):gsub("&amp;", "&"))
end

local function url_decode(s)
    return (s:gsub("%%([0-9A-Fa-f][0-9A-Fa-f])", function(h)
        return string.char(tonumber(h, 16))
    end))
end

local function attribute(tag, name)
    for key, value in tag:gmatch('([%w_:%.%-]+)%s*=%s*"([^"]*)"') do
        if key:lower() == name then return xml_decode(value) end
    end
    for key, value in tag:gmatch("([%w_:%.%-]+)%s*=%s*'([^']*)'") do
        if key:lower() == name then return xml_decode(value) end
    end
    return nil
end

local function safe_zip_path(path)
    if not path then return nil end
    path = url_decode(path):gsub("\\", "/"):gsub("#.*$", "")
    if path == "" or path:sub(1, 1) == "/" then return nil end
    local parts = {}
    for part in path:gmatch("[^/]+") do
        if part == ".." then
            if #parts == 0 then return nil end
            table.remove(parts)
        elseif part ~= "." and part ~= "" then
            parts[#parts + 1] = part
        end
    end
    if #parts == 0 then return nil end
    return table.concat(parts, "/")
end

local function dirname(path)
    return path:match("^(.*)/[^/]*$") or ""
end

local function join_zip(base, relative)
    if base ~= "" then relative = base .. "/" .. relative end
    return safe_zip_path(relative)
end

local function image_extension(data)
    if not data then return nil end
    if data:sub(1, 3) == "\255\216\255" then return "jpg" end
    if data:sub(1, 8) == "\137PNG\13\10\26\10" then return "png" end
    if data:sub(1, 6) == "GIF87a" or data:sub(1, 6) == "GIF89a" then return "gif" end
    if data:sub(1, 2) == "BM" then return "bmp" end
    return nil
end

if mode == "image-extension" then
    local f = io.open(arg[2] or "", "rb")
    if not f then fail() end
    local head = f:read(16)
    f:close()
    local ext = image_extension(head)
    if not ext then fail() end
    io.write(ext, "\n")
    os.exit(0)
end

if mode == "epub-container" then
    local xml = read_file(arg[2] or "", 1024 * 1024)
    if not xml then fail("cannot read EPUB container") end
    xml = xml:gsub("<(/?)[%w_%.%-]+:", "<%1")
    for tag in xml:gmatch("<[Rr][Oo][Oo][Tt][Ff][Ii][Ll][Ee][^>]*>") do
        local path = safe_zip_path(attribute(tag, "full-path"))
        if path then io.write(path, "\n"); os.exit(0) end
    end
    fail("EPUB container rootfile not found")
end

if mode == "epub-opf" then
    local opf_path = safe_zip_path(arg[2] or "")
    local xml = read_file(arg[3] or "", 4 * 1024 * 1024)
    if not opf_path or not xml then fail("cannot read EPUB package") end
    xml = xml:gsub("<(/?)[%w_%.%-]+:", "<%1")
    local base = dirname(opf_path)
    local items, ordered, metadata_cover, guide_cover = {}, {}, nil, nil

    for tag in xml:gmatch("<[Ii][Tt][Ee][Mm]%s+[^>]*>") do
        local id, href = attribute(tag, "id"), attribute(tag, "href")
        local media = (attribute(tag, "media-type") or ""):lower()
        local properties = (attribute(tag, "properties") or ""):lower()
        if id and href then
            local item = { id = id, href = href, media = media, properties = properties }
            items[id] = item
            ordered[#ordered + 1] = item
        end
    end
    for tag in xml:gmatch("<[Mm][Ee][Tt][Aa]%s+[^>]*>") do
        if (attribute(tag, "name") or ""):lower() == "cover" then
            metadata_cover = attribute(tag, "content") or metadata_cover
        end
    end
    for tag in xml:gmatch("<[Rr][Ee][Ff][Ee][Rr][Ee][Nn][Cc][Ee]%s+[^>]*>") do
        if (attribute(tag, "type") or ""):lower():find("cover", 1, true) then
            guide_cover = attribute(tag, "href") or guide_cover
        end
    end

    local candidates, seen = {}, {}
    local function add(href)
        local path = href and join_zip(base, href)
        if path and not seen[path] then seen[path] = true; candidates[#candidates + 1] = path end
    end
    for _, item in ipairs(ordered) do
        if item.properties:match("%f[%w]cover%-image%f[%W]") then add(item.href) end
    end
    if metadata_cover and items[metadata_cover] then add(items[metadata_cover].href) end
    if guide_cover and guide_cover:lower():match("%.(jpe?g|png|gif|bmp)$") then add(guide_cover) end
    for _, item in ipairs(ordered) do
        if item.media:match("^image/") and
           ((item.id or ""):lower():find("cover", 1, true) or
            (item.href or ""):lower():find("cover", 1, true)) then
            add(item.href)
        end
    end
    if #candidates == 0 then fail() end
    for _, path in ipairs(candidates) do io.write(path, "\n") end
    os.exit(0)
end

if mode == "mobi" then
    local source, target = arg[2], arg[3]
    local f = io.open(source or "", "rb")
    if not f then fail() end
    local size = f:seek("end")
    if not size or size < 86 then f:close(); fail() end
    f:seek("set", 0)
    local header = f:read(78)
    local count = be16(header or "", 77)
    if not count or count < 2 or count > 100000 then f:close(); fail() end
    local offsets = {}
    for i = 1, count do
        f:seek("set", 78 + (i - 1) * 8)
        local entry = f:read(4)
        offsets[i] = be32(entry or "", 1)
        if not offsets[i] or offsets[i] >= size or (i > 1 and offsets[i] < offsets[i - 1]) then
            f:close(); fail()
        end
    end
    offsets[count + 1] = size
    local record0_size = offsets[2] - offsets[1]
    if record0_size < 140 or record0_size > 2 * 1024 * 1024 then f:close(); fail() end
    f:seek("set", offsets[1])
    local record0 = f:read(record0_size)
    if not record0 or record0:sub(17, 20) ~= "MOBI" then f:close(); fail() end
    local mobi_header_length = be32(record0, 21)
    local first_image = be32(record0, 125)
    if not mobi_header_length or mobi_header_length < 116 or not first_image then f:close(); fail() end

    local cover_offset, thumb_offset = nil, nil
    local exth_flags = be32(record0, 145) or 0
    if exth_flags % 128 >= 64 then
        local exth = 17 + mobi_header_length
        if record0:sub(exth, exth + 3) == "EXTH" then
            local exth_length, exth_count = be32(record0, exth + 4), be32(record0, exth + 8)
            local p = exth + 12
            if exth_length and exth_count and exth_count <= 10000 then
                for _ = 1, exth_count do
                    local kind, length = be32(record0, p), be32(record0, p + 4)
                    if not kind or not length or length < 8 or p + length > exth + exth_length then break end
                    if kind == 201 and length >= 12 then cover_offset = be32(record0, p + 8) end
                    if kind == 202 and length >= 12 then thumb_offset = be32(record0, p + 8) end
                    p = p + length
                end
            end
        end
    end

    local candidates, seen = {}, {}
    local function candidate(index)
        if index and index >= 0 and index < count and not seen[index] then
            seen[index] = true; candidates[#candidates + 1] = index
        end
    end
    candidate(cover_offset and first_image + cover_offset)
    candidate(thumb_offset and first_image + thumb_offset)
    for index = first_image, math.min(first_image + 8, count - 1) do candidate(index) end

    for _, index in ipairs(candidates) do
        local start_at, finish_at = offsets[index + 1], offsets[index + 2]
        local length = start_at and finish_at and (finish_at - start_at) or 0
        if length > 0 and length <= 8 * 1024 * 1024 then
            f:seek("set", start_at)
            local data = f:read(length)
            if data and image_extension(data:sub(1, 16)) then
                local out = io.open(target or "", "wb")
                if not out then f:close(); fail() end
                out:write(data); out:close(); f:close(); os.exit(0)
            end
        end
    end
    f:close(); fail()
end

fail("unknown cover helper mode")
