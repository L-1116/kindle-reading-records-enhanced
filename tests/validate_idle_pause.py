"""Real Lua event decoding and production shell accounting, with deterministic clocks."""
from pathlib import Path
import datetime, os, shutil, struct, subprocess, tempfile, time, sys
from lupa.lua51 import LuaRuntime, LuaError
from idle_contract import assert_legacy_timing

ROOT=Path(__file__).resolve().parents[1]; PKG=ROOT/'native-reading-time-package'
SH=shutil.which('sh') or 'C:/Program Files/Git/usr/bin/sh.exe'
COUNT=0
def shell(code):
    p=subprocess.run([SH],input='export PATH="/usr/bin:/bin:$PATH"\n'+code,text=True,encoding='utf-8',capture_output=True,timeout=120)
    assert p.returncode==0,(p.stdout,p.stderr,code)
    return p.stdout
def source(name): return f'. "{(PKG/name).as_posix()}"\n'
def check():
    global COUNT; COUNT+=1

assert_legacy_timing(); check()
for f in PKG.glob('*.sh'):
    for interpreter in (SH,shutil.which('dash') or 'C:/Program Files/Git/usr/bin/dash.exe'):
        subprocess.run([interpreter,'-n',str(f)],check=True,capture_output=True)
for f in PKG.glob('*.lua'): LuaRuntime().execute('assert(loadstring(...))',f.read_text(encoding='utf-8'))
check()
with tempfile.TemporaryDirectory(prefix='idle-') as tmp:
    base=Path(tmp); b=base.as_posix()
    head=f'BASE="{b}"\n'+source('reading-config.sh')+source('reading-settings.sh')
    assert shell(head+'rr_config_read; echo "$idle_enabled $idle_minutes"').strip()=='0 3';check()
    (base/'user.conf').write_text('other=keep\n# comment\nidle_pause_enabled=0\n')
    for n in [1,2,3,4,5,10,1440,17]:
        assert shell(head+f'idle_enabled=1; idle_minutes={n}; rr_config_save; rr_config_read; echo "$idle_enabled $idle_minutes"').strip()==f'1 {n}'
        assert 'other=keep' in (base/'user.conf').read_text(encoding="utf-8"); check()
    for n in ['', '0','01','-1','1.5','1441','99999999999999','$(touch sentinel)']:
        assert shell(head+"rr_minutes_valid '"+n+"'; echo $?").strip()=='1';check()
    assert shell(head+'rr_config_read; mode=books; book_filter=year; book_page=3; action=settings_open; rr_settings_action; action=settings_toggle; rr_settings_action; action=settings_back; rr_settings_action; echo "$mode $book_filter $book_page"')=='books year 3\n';check()
    assert shell(head+'rr_config_read; mode=settings; action=settings_custom; rr_settings_action; action=settings_digit_1; rr_settings_action; action=settings_digit_7; rr_settings_action; action=settings_save; rr_settings_action; rr_config_read; echo "$mode $idle_minutes"').strip()=='settings 17';check()
    assert shell(head+'mode=settings_custom; settings_digits=0; action=settings_save; rr_settings_action; echo "$mode $settings_error"').startswith('settings_custom 请输入');check()

    saved=(base/'user.conf').read_bytes(); (base/'user.conf').unlink(); (base/'user.conf').mkdir()
    assert shell(head+'idle_enabled=1; idle_minutes=3; rr_config_save; echo $?').strip()=='1'
    assert list((base/'user.conf').iterdir())==[]; (base/'user.conf').rmdir(); (base/'user.conf').write_bytes(saved); check()

    # Execute the real decoder. EOF is the expected terminal failure for a finite stream.
    def decode(events, size=16, start=1000, limit=120):
        stream=base/'events'; snap=base/'snapshot'
        stream.write_bytes(b''.join(struct.pack('<'+('ii' if size==16 else 'qq')+'HHi',t,0,typ,code,value) for t,typ,code,value in [(t+1728000,typ,code,value) for t,typ,code,value in events]))
        lua=LuaRuntime(); lua.globals().arg=lua.table_from({1:stream.as_posix(),2:str(size),3:snap.as_posix(),4:str(start+1728000),5:str(limit)})
        lua.globals().os.rename=lambda a,b: (os.replace(a,b) is None) or True
        lua.globals().os.time=lambda *args: (1728000+events[-1][0] if not args else time.mktime((int(args[0]['year']),int(args[0]['month']),int(args[0]['day']),int(args[0]['hour']),int(args[0]['min']),int(args[0]['sec']),0,0,-1)))
        # Stream replay uses a fixed delivery clock per event below, without
        # changing the kernel timeval values consumed by production decoding.
        lua.execute('local open=io.open; io.open=function(path,mode) local f=open(path,mode); if path~=arg[1] then return f end; return {setvbuf=function() end, read=function(_,n) local s=f:read(n); if s then local a,b,c,d=s:byte(1,4); TEST_EVENT_TIME=a+b*256+c*65536+d*16777216 else f:close() end; return s end} end')
        clock=lua.globals().os.time
        lua.globals().os.time=lambda *args: clock(*args) if args else (lua.globals().TEST_EVENT_TIME or 1728000+start)
        try: lua.execute((PKG/'reading-idle-touch.lua').read_text(encoding="utf-8"))
        except LuaError as e: assert 'EOF/short read' in str(e) or 'SYN_DROPPED' in str(e),str(e)
        lua.execute('collectgarbage("collect")')
        fields=snap.read_text(encoding="utf-8").split(); fields[0]=str(int(fields[0])-1728000)
        return fields
    def tap(t): return [(t,1,330,1),(t,3,0,44),(t,3,1,55),(t,0,0,0),(t,3,0,80),(t,0,0,0),(t,1,330,0),(t,0,0,0)]
    for size in [16,24]:
        s=decode(tap(1060)+tap(1480),size); assert s[:2]==['1480','180'],s;check()
        s=decode(tap(1001)+tap(1003),size);assert s[:2]==['1003','3'],s;check()
        # Movement and a held press must not extend activity repeatedly.
        s=decode(tap(1060)[:6]+[(1070,3,0,90),(1070,0,0,0),(1080,1,330,0),(1080,0,0,0)],size)
        assert s[:2]==['1060','60'];check()
        s=decode([(1001,3,47,0),(1001,3,57,7),(1001,3,53,30),(1001,3,54,40),(1001,0,0,0),(1002,3,53,80),(1002,0,0,0),(1003,3,57,-1),(1003,0,0,0)]+tap(1008),size)
        assert s[:2]==['1008','8'];check()
        s=decode(tap(990)+tap(1005),size);assert s[:2]==['1005','5'];check()
        s=decode(tap(1005)+[(1006,0,3,0)],size);assert s[:2]==['1005','5'];check()

    # Feed snapshots produced by the real decoder into the production shell module.
    # Sample at irregular times; never round a timeout to a sampling boundary.
    accounting=source('reading-config.sh')+source('reading-idle.sh')+f'''
BASE="{b}"; LOG="$BASE/log"; DATA="$BASE/data"; SAVE_INTERVAL=90
bucket=0; bucket_id=''; bucket_title=''; bucket_date=''; idle_pid=''
flush() {{ [ "$bucket" -eq 0 ] || printf '%s %s %s\n' "$bucket_date" "$bucket_id" "$bucket" >> "$DATA"; bucket=0; }}
write_report() {{ :; }}
idle_dir="$BASE"; idle_id=AAAA; idle_title=Book; idle_limit=2; idle_seen=0; idle_date=1970-01-01; idle_paused=0
today=1970-01-01
'''
    script=accounting
    for now,last,closed in [(1000,1000,0),(1057,1000,0),(1063,1060,60),(1177,1060,60),(1183,1060,60),(1483,1480,180),(1599,1480,180),(1605,1480,180)]:
        script+=f'now={now}; printf "{last} {closed} 1970-01-01 {closed}\\n" > "$BASE/snapshot"; idle_save_credit || exit 3\n'
    script+='flush; cat "$DATA"\n'
    rows=shell(script).splitlines(); assert sum(int(x.split()[2]) for x in rows)==300,rows;check()
    # Midnight split with a pause before midnight and resume after it.
    midnight=int(time.mktime((2026,10,15,0,0,0,0,0,-1)))
    day_prev='2026-10-14'; day='2026-10-15'
    script=accounting+f'''
rm -f "$DATA"; idle_date={day_prev}; today={day_prev}; now={midnight-2}
printf '{midnight-60} 0 {day_prev} 0\n' > "$BASE/snapshot"; idle_save_credit || exit 3
today={day}; now={midnight+8}
printf '{midnight+3} 63 {day} 3\n' > "$BASE/snapshot"; idle_save_credit || exit 3
flush; cat "$DATA"
'''
    rows=shell(script).splitlines(); assert rows==[f'{day_prev} AAAA 60',f'{day} AAAA 8'],rows;check()
    # A touch published during LIPC queries can be newer than the sampler's
    # timestamp. Reconcile the fresh clock, including a midnight transition.
    script=accounting+f"""
rm -f "$DATA"; idle_date={day_prev}; today={day_prev}; now={midnight-1}
date() {{ case "$1" in +%s) echo {midnight+1};; +%Y-%m-%d) echo {day};; *) /usr/bin/date "$@";; esac; }}
printf '{midnight} 1 {day} 0\\n' > "$BASE/snapshot"; idle_save_credit || exit 3
flush; cat "$DATA"
"""
    assert shell(script).splitlines()==[f'{day_prev} AAAA 1',f'{day} AAAA 1'];check()
    # Listener cleanup owns and waits for its one child, preserving user data.
    assert shell(source('reading-idle.sh')+f'BASE="{b}"; sleep 30 & idle_pid=$!; child=$idle_pid; idle_guard_stat; idle_birth=$idle_stat_birth; idle_stop; kill -0 "$child" 2>/dev/null; echo $?').strip()=='1';check()
# Exercise the actual daemon loop, retaining its LIPC/session/persistence code.
# Only process creation is replaced here; decoder and child lifetime have their
# own tests above and the guard test below.
for scenario in (() if '--unit-only' in sys.argv else ('example','boundary','switch','locked','restart','failure','probe-failure','clock-jump','off')):
    with tempfile.TemporaryDirectory(prefix='idle-daemon-') as tmp:
        base=Path(tmp); helpers=base/'release/bin'; helpers.mkdir(parents=True)
        shutil.copy2(PKG/'reading-config.sh',helpers/'reading-config.sh')
        mock_start='''
idle_start() {
    [ "$scenario" != probe-failure ] || return 1
    idle_dir="$BASE/session"; mkdir -p "$idle_dir"; idle_pid=99999999; idle_active=1
    idle_seen=0; idle_paused=0; idle_limit="$idle_minutes"; idle_id="$book_id"; idle_title="$book_title"; idle_date="$today"
    touch_last="$now"; touch_closed=0
    printf '%s 0 %s 0\n' "$now" "$today" > "$idle_dir/snapshot"
    echo "start $loops $book_id" >> "$BASE/lifetime"
}
idle_guard_alive() { [ "$scenario:$loops" != failure:25 ]; }
kill() { :; }
'''
        (helpers/'reading-idle.sh').write_text((PKG/'reading-idle.sh').read_text(encoding="utf-8")+mock_start,encoding='utf-8',newline='\n')
        (base/'user.conf').write_text(f'idle_pause_enabled={0 if scenario=="off" else 1}\nidle_pause_minutes={1 if scenario=="boundary" else 2}\n',newline="\n")
        # Realistic epoch avoids CRT restrictions at dates before local 1970.
        epoch=int(time.time())//86400*86400+3600
        prelude=f'BASE="{base.as_posix()}"; export READING_BASE="$BASE"; export READING_RELEASE="$BASE/release"\nscenario={scenario}; epoch={epoch}; loops=0\n'+'''
date() {
    if [ "$1" = +%s ]; then echo "$((epoch+loops*5))"
    elif [ "$1" = +%Y-%m-%d ]; then echo "FIXED_DAY"
    else /usr/bin/date "$@"; fi
}
lipc-get-prop() {
    case "$2" in
    activeApp) [ "$loops" -lt 120 ] && echo com.lab126.booklet.reader || echo home;;
    state) if [ "$scenario" = locked ] && [ "$loops" -ge 20 ] && [ "$loops" -lt 40 ]; then echo screenSaver; else echo active; fi;;
    activeContext) echo file:///Book_AAAA.kfx;;
    getCurrentBookMetadata) if [ "$scenario" = switch ] && [ "$loops" -ge 60 ]; then echo '{"cdeKey":"BBBB"}'; else echo '{"cdeKey":"AAAA"}'; fi;;
    esac
}
sleep() {
    loops=$((loops+1))
    if [ "$scenario" = clock-jump ] && [ "$loops" = 10 ]; then epoch=$((epoch+600)); fi
    if [ -n "$idle_dir" ] && [ -f "$idle_dir/snapshot" ]; then
        case "$scenario:$loops" in
        example:12|example:96|boundary:1|boundary:15)
            event=$((epoch+loops*5))
            [ "$scenario:$loops" != boundary:1 ] || event=$((epoch+1))
            [ "$scenario:$loops" != boundary:15 ] || event=$((epoch+72))
            finish="$event"; cap=$((touch_last+idle_limit*60)); [ "$finish" -le "$cap" ] || finish="$cap"
            touch_closed=$((touch_closed+finish-touch_last)); touch_last="$event"
            printf '%s %s %s %s\n' "$touch_last" "$touch_closed" "$today" "$touch_closed" > "$idle_dir/snapshot";;
        esac
    fi
    [ "$scenario:$loops" != restart:30 ] || exit 0
    [ "$loops" -lt 121 ] || exit 0
}
'''
        print('daemon scenario',scenario,flush=True)
        shell(prelude.replace("FIXED_DAY",datetime.datetime.fromtimestamp(epoch).strftime("%Y-%m-%d"))+(PKG/'native-reading-time-daemon.sh').read_text(encoding="utf-8"))
        rows=[r.split('\t') for r in (base/'reading-time.tsv').read_text(encoding='utf-8').splitlines()[1:]]
        total=sum(int(r[2]) for r in rows)
        expected={'example':300,'boundary':121,'switch':240,'locked':220,'restart':120,'failure':592,'probe-failure':597,'clock-jump':165,'off':597}[scenario]
        assert total==expected,(scenario,total,rows,(base/'service.log').read_text(encoding='utf-8'),(base/'lifetime').read_text(encoding='utf-8') if (base/'lifetime').exists() else 'no start')
        if scenario=='restart':
            shell(prelude.replace('epoch='+str(epoch),'epoch='+str(epoch+600),1).replace("FIXED_DAY",datetime.datetime.fromtimestamp(epoch+600).strftime("%Y-%m-%d"))+(PKG/'native-reading-time-daemon.sh').read_text(encoding='utf-8'))
            restarted=(base/'reading-time.tsv').read_text(encoding='utf-8').splitlines()
            assert restarted.count('date\tbook_id\tseconds\ttitle')==1
            assert sum(int(r.split('\t')[2]) for r in restarted[1:])==240
            check()
        if scenario=='switch': assert {r[1] for r in rows}=={'AAAA','BBBB'}
        if scenario in ('failure','probe-failure'): assert 'foreground timing retained' in (base/'service.log').read_text(encoding="utf-8")
        check()
print(f'idle pause: PASS ({COUNT} checks; real Lua 5.1 + production daemon, hardware pending)')
