-- Read-only title layout for FBInk; Lua 5.1 compatible, no font replacement.
local input = assert(arg[1])
local width, size = assert(tonumber(arg[2])), assert(tonumber(arg[3]))
local number, row_height = tonumber(arg[4]) or 0, assert(tonumber(arg[5]))
local script_dir = arg[0]:match("^(.*)/") or "."
local advances = dofile(script_dir .. "/reading-insights-title-widths.lua")
local function codepoint(ch)
    local a,b,c,d=ch:byte(1,4)
    if a<128 then return a end
    if a<224 then return (a-192)*64+b-128 end
    if a<240 then return (a-224)*4096+(b-128)*64+c-128 end
    return (a-240)*262144+(b-128)*4096+(c-128)*64+d-128
end
local function word_char(ch)
    local cp=codepoint(ch)
    return ch:match("^[%w_']$") or (cp>=0xC0 and cp<=0x24F)
        or (cp>=0x300 and cp<=0x36F) or (cp>=0x1E00 and cp<=0x1EFF)
end
local row = 0
for line in io.lines(input) do
    local title = line:match("^[^\t]*\t([^\t]*)")
    if title and title ~= "" then
        if number > 0 then title = (number + row) .. ". " .. title end
        local tokens = {}
        for ch in title:gmatch("[%z\1-\127\194-\244][\128-\191]*") do
            local b = ch:byte()
            -- Non-ASCII gets a full em; reserve 8% for native rasterizer differences.
            local w = ((b>=32 and b<=126) and advances[b-31] or 1) * size * 1.08
            local kind=word_char(ch) and "word" or (ch==" " and "space" or "other")
            local prev=tokens[#tokens]
            if prev and kind=="word" and prev.kind=="word" then
                prev.text=prev.text..ch; prev.width=prev.width+w
            elseif prev and ch:match("^[,.;:!?%-%/]$") then
                prev.text=prev.text..ch; prev.width=prev.width+w; prev.kind="other"
            else tokens[#tokens+1]={text=ch,width=w,kind=kind} end
        end
        local pos = 1
        for n = 1, 2 do
            while tokens[pos] and tokens[pos].kind=="space" do pos=pos+1 end
            if pos > #tokens then break end
            local parts, used = {}, 0
            local limit = width - (n==2 and size*1.08 or 0)
            while pos <= #tokens and used + tokens[pos].width <= limit do
                parts[#parts+1]=tokens[pos].text
                used=used+tokens[pos].width; pos=pos+1
            end
            local text=table.concat(parts):gsub("%s+$", "")
            -- An overlong unbreakable word is omitted with an ellipsis rather
            -- than split. Chinese can wrap between characters as before.
            local stop=(#parts==0)
            if (n==2 or stop) and pos<=#tokens then text=text.."…" end
            io.write(row*row_height+(n-1)*(size+8), "\t", text, "\n")
            if stop then break end
        end
        row = row + 1
    end
end
