-- Passive, blocking evdev reader. No ioctl, grab, power or window commands.
local device, size, snapshot = arg[1], assert(tonumber(arg[2])), arg[3]
local last, timeout = assert(tonumber(arg[4])), assert(tonumber(arg[5]))
assert(size == 16 or size == 24)
local closed, day_closed = 0, 0
local day = os.date('%Y-%m-%d', last)
local function midnight(t)
    local d = os.date('*t', t); d.hour=0; d.min=0; d.sec=0
    return os.time(d)
end
local function publish()
    local f = assert(io.open(snapshot .. '.new', 'wb'))
    f:write(last, ' ', closed, ' ', day, ' ', day_closed, '\n'); assert(f:close())
    assert(os.rename(snapshot .. '.new', snapshot))
end
local function activity(t)
    -- Kernel timeval (realtime by default), rather than delayed daemon sampling.
    -- Never replay events queued before this session or accept future clocks.
    if t <= last or t > os.time()+1 then return end
    local finish = math.min(t, last+timeout)
    closed = closed + finish-last
    local new_day = os.date('%Y-%m-%d', t)
    if day ~= new_day then day_closed=0; day=new_day end
    day_closed = day_closed + math.max(0, finish-math.max(last,midnight(t)))
    last=t; publish()
end
local function u16(s,p) return s:byte(p)+s:byte(p+1)*256 end
local function u32(s,p) return u16(s,p)+u16(s,p+2)*65536 end
publish()
local multiplex = arg[6] == '--multiplex'
local f = multiplex and io.stdin or assert(io.open(device, 'rb')); f:setvbuf('no')
local keys, page_pending = {}, {}
local function page_event(source, typ, code, value, stamp)
    local down = keys[source]
    if not down then down={}; keys[source]=down end
    if typ==1 and (code==104 or code==109) then
        if value==0 then down[code]=nil
        elseif value==1 and not down[code] then
            down[code]=true; page_pending[source]=stamp
        end -- value=2 is autorepeat, never a new activity.
    elseif typ==0 and code==0 and page_pending[source] then
        local t=page_pending[source]; page_pending[source]=nil
        assert(math.abs(os.time()-t)<30, 'unsupported evdev clock')
        activity(t)
    end
end
local pending, slot, contacts, button = nil, 0, {}, false
local slots_seen, type_a, frame_contact = false, false, false
local invalid = 0
local function contact(value, t)
    local before = button or next(contacts) ~= nil
    if value == 'button_down' then button=true
    elseif value == 'button_up' then button=false
    elseif value == 'tracking_down' then contacts[slot]=true
    else contacts[slot]=nil end
    if not before and (button or next(contacts) ~= nil) then pending=t end
end
while true do
    local source = 0
    if multiplex then
        local header = f:read(1)
        assert(header, 'evdev EOF/short read')
        source=header:byte()
    end
    if source>=128 then
        -- A hotplug slot was reused: discard the previous device's held keys.
        keys[source-128]=nil; page_pending[source-128]=nil
    else
    local s = f:read(size)
    assert(s and #s==size, 'evdev EOF/short read')
    local p=size-7; local typ,code,value=u16(s,p),u16(s,p+2),u32(s,p+4)
    local stamp=u32(s,1)
    if typ>31 or code>767 or (typ==0 and code>3) or (typ==3 and code>63) then
        invalid=invalid+1
        if invalid>=8 then error('corrupt evdev stream') end
    else
    invalid=0
    if typ==0 and code==3 then error('evdev SYN_DROPPED') end
    page_event(source,typ,code,value,stamp)
    -- Page-only devices must never inject touch contacts or coordinates.
    if source==0 then
    if typ==3 then
        if code==47 then assert(value<=255, 'invalid evdev slot'); slot=value; slots_seen=true
        elseif code==57 then
            if value~=4294967295 then frame_contact=true end
            contact(value~=4294967295 and 'tracking_down' or 'tracking_up',stamp)
        end
    elseif typ==1 and code==330 then
        contact(value~=0 and 'button_down' or 'button_up',stamp)
    elseif typ==0 and code==2 and not slots_seen then type_a=true
    elseif typ==0 and code==0 then
        if type_a and not frame_contact then contacts={} end
        frame_contact=false
        if pending then
            -- A different clock domain must fall back, rather than silently
            -- treating every real touch as stale and pausing valid reading.
            assert(math.abs(os.time()-pending)<30, 'unsupported evdev clock')
            activity(pending); pending=nil
        end
    end
    end
    end
    end
end
