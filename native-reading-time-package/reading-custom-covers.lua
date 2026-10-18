-- Independent, versioned association store. No writes to user.conf or history.
local base, command = arg[1], arg[2]
local path = base .. '/custom-cover-associations.tsv'
local function hex(s) return (s:gsub('.',function(c) return string.format('%02x',c:byte()) end)) end
local function unhex(s)
    if #s%2~=0 or s:find('[^0-9a-f]') then return nil end
    return (s:gsub('..',function(c) return string.char(tonumber(c,16)) end))
end
local function usable(t,id)
    return t~='' and t~='unknown' and t~=id and not (#t>=16 and not t:find('[^0-9a-fA-F]'))
end
local function key(id,title)
    if id and id~='' and id~='unknown' then return 'id:'..id end
    -- The statistics cache substitutes the ID when a historical title is
    -- missing/unusable. Normalize here too, because every cover entry receives
    -- that display title. Identical missing metadata shares one fallback key.
    title=title or '';id=id or ''
    return 'title:'..(usable(title,id) and title or id)
end
local function valid_name(s)
    return s and #s>0 and #s<=255 and not s:find('[%z\1-\31\127/\\]') and s~='.' and s~='..'
end
local rows={};local store_valid=true
local f=io.open(path,'rb')
if f then
    if (f:seek('end') or 0)<=4*1024*1024 then
        f:seek('set'); local header=f:read('*l')
        if header=='# reading-records custom covers v1; hex key<TAB>hex filename' then
            for line in f:lines() do
                local k,v=line:match('^([0-9a-f]+)\t([0-9a-f]+)$')
                if k and valid_name(unhex(v)) then rows[k]=v end
            end
        else store_valid=false end
    else store_valid=false end
    f:close()
end
local advances
local function wrapped(s,size,limit,lines)
    if s:sub(1,1)=='-' then s=' '..s end -- Never expose a name as an FBInk option.
    advances=advances or dofile((arg[0]:match('^(.*)/') or '.')..'/reading-insights-title-widths.lua')
    local chars={};for ch in s:gmatch('[%z\1-\127\194-\244][\128-\191]*') do chars[#chars+1]=ch end
    local out,part,used={}, {},0
    for i,ch in ipairs(chars) do
        local b=ch:byte();local w=((b>=32 and b<=126) and advances[b-31] or 1)*size*1.08
        local reserve=(#out==lines-1 and i<#chars) and size*1.08 or 0
        if used+w>limit-reserve then
            if #out==lines-1 then part[#part+1]='…';break end
            out[#out+1]=table.concat(part);part={};used=0
        end
        part[#part+1]=ch;used=used+w
    end
    out[#out+1]=table.concat(part)
    for i,line in ipairs(out) do if line:sub(1,1)=='-' then out[i]=' '..line end end
    return out
end
local k=hex(command=='generic' and 'generic' or key(arg[3],arg[4]))
if command=='generic' or command=='get' then
    local v=rows[k]; if v then io.write(unhex(v),'\n') end
elseif command=='count' then
    local n=0;for k in pairs(rows) do if unhex(k)~='generic' then n=n+1 end end
    io.write(n,'\n')
elseif command=='save' or command=='save-generic' then
    if not store_valid then os.exit(1) end
    k=hex(command=='save-generic' and 'generic' or key(arg[3],arg[4]))
    local name=arg[5] or ''
    if name~='' and not valid_name(name) then os.exit(1) end
    rows[k]=name~='' and hex(name) or nil
    local ordered={};for r in pairs(rows) do ordered[#ordered+1]=r end;table.sort(ordered)
    -- Parent creates an exclusive private transaction directory beside path.
    local tmp=assert(arg[6])..'/associations'
    local bytes=0;for _,r in ipairs(ordered) do bytes=bytes+#r+#rows[r]+2 end
    if bytes>4*1024*1024-128 then os.exit(1) end
    local out=io.open(tmp,'wb'); if not out then os.exit(1) end
    local ok=out:write('# reading-records custom covers v1; hex key<TAB>hex filename\n')
    for _,r in ipairs(ordered) do if not out:write(r,'\t',rows[r],'\n') then ok=nil end end
    if not out:close() then ok=nil end
    if not ok or not os.rename(tmp,path) then os.remove(tmp);os.exit(1) end
elseif command=='history' then
    local books,order={},{}
    local history=io.open(base..'/reading-time.tsv','rb')
    if history then
        history:read('*l')
        for line in history:lines() do
            local _,id,seconds,title=line:match('^([^\t]*)\t([^\t]*)\t([^\t]*)\t([^\t\r]*)')
            if id and tonumber(seconds) then
                local ident=key(id,title)
                if not books[ident] then books[ident]={id=id,title=title};order[#order+1]=ident end
                local b=books[ident]
                if not usable(b.title,id) and usable(title,id) then b.title=title end
            end
        end
        history:close()
    end
    table.sort(order,function(a,b) local x,y=books[a],books[b];return x.title==y.title and a<b or x.title<y.title end)
    for _,ident in ipairs(order) do
        local b=books[ident]
        -- Prefix keeps empty IDs intact when shell reads tab-separated fields.
        -- Preserve an empty fallback title exactly; only the UI substitutes a
        -- display label, so a nameless historical identity still resolves.
        io.write('book:',b.id,'\t',b.title,'\n')
    end
elseif command=='catalog-query' then
    local predicates={};local n=0
    local function quote(s) return "'"..s:gsub("'","''").."'" end
    for line in io.lines(assert(arg[3])) do
        n=n+1;if n>10 then break end
        local id,title=line:match('^book:([^\t]*)\t(.*)$')
        if id and id~='' and id~='unknown' then
            predicates[#predicates+1]='p_cdeKey='..quote(id)
        elseif title and title~='' then
            title=title:lower():gsub('%.epub$',''):gsub('%.mobi$',''):gsub('%.pdf$','')
            local norm="lower(CASE WHEN lower(substr(p_titles_0_nominal,-5)) IN ('.epub','.mobi') THEN substr(p_titles_0_nominal,1,length(p_titles_0_nominal)-5) WHEN lower(substr(p_titles_0_nominal,-4))='.pdf' THEN substr(p_titles_0_nominal,1,length(p_titles_0_nominal)-4) ELSE p_titles_0_nominal END)"
            predicates[#predicates+1]="((p_cdeKey IS NULL OR p_cdeKey='' OR p_cdeKey='unknown') AND "..norm..'='..quote(title)..')'
        end
    end
    io.write("SELECT -1,replace(replace(COALESCE(p_titles_0_nominal,''),char(9),' '),char(10),' '),COALESCE(p_cdeKey,''),replace(replace(COALESCE(p_thumbnail,''),char(9),' '),char(10),' '),'','' FROM Entries WHERE ",#predicates>0 and table.concat(predicates,' OR ') or '0'," ORDER BY p_lastAccess DESC LIMIT 80;\n")
elseif command=='cards' then
    -- Input is already sliced to the visible page. Load associations/metrics once.
    local n=0
    for line in io.lines(assert(arg[3])) do
        n=n+1;if n>10 then break end
        local id,title=line:match('^book:([^\t]*)\t(.*)$')
        if id then
            local label=usable(title,id) and title or '未知书籍'
            local t=wrapped(label,34,500,2)
            local name=rows[hex(key(id,title))]
            io.write('book:',id,'\ttitle:',title,'\tname:',name and unhex(name) or '',
                '\tline:',t[1] or '', '\tline:',t[2] or '', '\n')
        end
    end
elseif command=='text' then
    io.write(wrapped(arg[3] or '',tonumber(arg[4]) or 34,tonumber(arg[5]) or 800,1)[1],'\n')
else os.exit(2) end
