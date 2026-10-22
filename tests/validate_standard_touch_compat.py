"""Permanent Standard evdev matrix: real Lua 5.1, binary streams and shell recovery.

Hardware is simulated offline; no foreground input or Kindle device is used.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
from lupa.lua51 import LuaRuntime, LuaError

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / 'native-reading-time-package'
PROBE = (PKG/'reading-insights-touch-probe.lua').read_text(encoding='utf-8')
READER = (PKG/'reading-insights-touch-ui.lua').read_text(encoding='utf-8')
FIRMWARES = ['5.17.1.0.4','5.18','5.18.0','5.18.1','5.18.1.1.1','5.18.1.2',
             '5.18.2','5.18.4','5.18.5','5.18.5.0.1','5.18.6','5.18.10',
             '5.19.1','5.19.2','5.19.5','5.19.6']
COUNTS = {'probe':0,'reader':0,'shell':0}
RESULTS = {}

def execute(source, args):
    lua = LuaRuntime()
    lua.globals().arg = lua.table_from({i+1:str(v) for i,v in enumerate(args)})
    lua.execute('os.exit=function(code) error("TEST_EXIT:"..tostring(code)) end; io.write=function(...) end')
    try: lua.execute(source)
    except LuaError as exc:
        result = str(exc)
        assert 'TEST_EXIT:' in result, result
        return int(result.split('TEST_EXIT:')[1].split()[0])
    return 0

def bitmap(codes, bits=32):
    number = sum(1 << c for c in codes)
    chunks = []
    while number:
        chunks.append(f'{number & ((1<<bits)-1):x}')
        number >>= bits
    return ' '.join(reversed(chunks)) or '0'

def candidate(root, num, name, *, xy=False, mt=False, direct=True, keys=(), props=(), readable=True, bits=32):
    node = root/'sys'/f'event{num}'/'device'
    (node/'capabilities').mkdir(parents=True)
    (node/'name').write_text(name)
    (node/'capabilities/ev').write_text(bitmap([0,1,3],bits))
    (node/'capabilities/abs').write_text(bitmap(([0,1] if xy else [])+([53,54,57] if mt else []),bits))
    (node/'capabilities/key').write_text(bitmap(keys,bits))
    (node/'properties').write_text(bitmap(([1] if direct else [])+list(props),bits))
    dev = root/'dev'/f'event{num}'
    dev.parent.mkdir(exist_ok=True)
    if readable: dev.write_bytes(b'')
    return dev

def probe(root, klass=1):
    elf = root/'lua.elf'; elf.write_bytes(b'\x7fELF'+bytes([klass,1]))
    listing = root/'events'; listing.write_text('\n'.join(p.name for p in sorted((root/'sys').glob('event*')))+'\n')
    os.environ.update(READING_INPUT_SYSFS=(root/'sys').as_posix(),READING_INPUT_DEV=(root/'dev').as_posix(),READING_LUA_BINARY=elf.as_posix())
    code = execute(PROBE,[root.as_posix(),listing.as_posix()])
    COUNTS['probe'] += 1
    return code, dict(line.split('=',1) for line in (root/'touch-last.log').read_text().splitlines())

def event(size, typ, code, value):
    return bytes(size-8)+struct.pack('<HHi',typ,code,value)

def reader(root, *, point=(120,85), mode='daily', size=16, screen=(1272,1696),
           viewport=None, transform='auto', bounds=('unknown',)*4, codes=(53,54), stream=None,
           pages=3, page=2, period='week', legacy=False):
    sw,sh=screen
    if viewport is None:
        scale=min(sw/1272,sh/1696)
        vw,vh=int(1272*scale),int(1696*scale)
        viewport=(vw,vh,(sw-vw)//2,(sh-vh)//2)
    vw,vh,ox,oy=viewport
    px,py=round(ox+point[0]*vw/1272),round(oy+point[1]*vh/1696)
    if 'invert_x' in transform or 'invert_xy' in transform: px=sw-1-px
    if 'invert_y' in transform or 'invert_xy' in transform: py=sh-1-py
    if transform.startswith('swap'): px,py=py,px
    if bounds[0] != 'unknown':
        tw,th=(sh,sw) if transform.startswith('swap') else (sw,sh)
        px=round(bounds[0]+px*(bounds[1]-bounds[0])/(tw-1))
        py=round(bounds[2]+py*(bounds[3]-bounds[2])/(th-1))
    if stream is None: stream=[(3,codes[0],px),(3,codes[1],py),(0,0,0)]
    dev=root/'stream'; dev.write_bytes(b''.join(event(size,*e) for e in stream))
    report=root/'reader.log'; report.write_text('selected_touch=fixture\n')
    args=[dev.as_posix(),(root/'debug.log').as_posix(),mode,0,31,ox,oy,vw,vh,pages,page,1576,period,'7d',
          transform,size,sw,sh,report.as_posix(),*bounds,'legacy' if legacy else 'current']
    code=execute(READER,args)
    COUNTS['reader']+=1
    fields=dict(line.split('=',1) for line in report.read_text().splitlines())
    return code, fields

def shell_case(root, kind, legacy=False):
    root.mkdir()
    base=root/'base'; base.mkdir()
    release=base/'releases/9.8.1-5.19-vera-test1'; (release/'bin').mkdir(parents=True)
    for name in ['reading-config.sh','reading-settings.sh','reading-custom-covers.sh','reading-custom-covers.lua','reading-insights-touch-ui.lua','reading-insights-touch-probe.lua','reading-insights-touch-preflight.sh']:
        shutil.copy2(PKG/name,release/'bin'/name)
    for folder,names in [('ui-calendar',['total','daily','books','day_detail','month_detail','week_trend','book_detail']),('ui',['total'])]:
        (release/folder).mkdir()
        for name in names: (release/folder/f'{name}.png').write_bytes(b'fixture')
    shutil.copytree(release/'ui',base/'ui')
    (base/'fonts').mkdir(); (base/'fonts/NotoSansCJKsc-Regular.otf').write_bytes(b'fixture')
    (base/'reading-time.tsv').write_text('history sentinel\n')
    (base/'book-covers').mkdir(); (base/'book-covers/sentinel').write_bytes(b'cover')
    (base/'user.conf').write_bytes(b'config')
    (base/'bin').mkdir(); (base/'bin/native-reading-time-daemon.sh').write_bytes(b'daemon')
    (release/'bin/reading-records-v9.6.3.sh').write_text('exit 0\n')
    (root/'sys').mkdir()
    dev=candidate(root,2,'unknown_vendor_input',mt=True) if kind!='no_candidate' else candidate(root,1,'power',keys=[116],direct=False)
    streams={'exit':[(3,53,120),(3,54,85),(0,0,0)],
             'books':[(3,53,600),(3,54,210),(0,0,0)],
             'short':[], 'corrupt':[(255,0,0)]*8,
             'dropped':[(0,3,0)], 'no_candidate':[]}
    dev.write_bytes(b''.join(event(16,*e) for e in streams[kind]))
    elf=root/'lua.elf'; elf.write_bytes(b'\x7fELF\x01\x01')
    trace=root/'trace'; session=root/'native-reading-dashboard.123'
    runner=root/'lua_runner.py'
    runner.write_text('from pathlib import Path\nimport sys\nfrom lupa.lua51 import LuaRuntime\nlua=LuaRuntime()\na=sys.argv[1:]\nclass ReaderExit(Exception): pass\ndef stop(code=0): raise ReaderExit(int(code))\nlua.globals().os.exit=stop\ncode=0\ntry:\n if a[0]=="-e": lua.execute(a[1])\n else:\n  lua.globals().arg=lua.table_from({i:v for i,v in enumerate(a)})\n  lua.execute(Path(a[0]).read_text(encoding="utf-8"))\nexcept ReaderExit as exc: code=exc.args[0]\nfinally:\n if a[0].endswith("reading-insights-touch-ui.lua"):\n  device=Path(a[1]).resolve()\n  assert device.is_relative_to(Path(__file__).resolve().parent/"dev")\n  device.write_bytes(b"") # emulate consumed evdev bytes across reader processes\nsys.exit(code)\n',encoding='utf-8',newline='\n')
    q=lambda p: shlex.quote(Path(p).as_posix())
    viewer=(PKG/('阅读记录.sh' if legacy else '阅读记录-optimized.sh')).read_text(encoding='utf-8')
    if legacy:
        # Run complete legacy shell, replace only statistics/render functions
        # at its existing safety boundary after initialization.
        prefix,startup=viewer.split('\n# Safety invariant:',1)
        prefix=prefix.replace('detect_screen\nfind_touch_device','detect_screen\nfind_touch_device')
        mocks='\ndraw() { echo DRAW >> "$TRACE"; }; refresh_progress_cache() { :; }; days_in_month() { echo 31; }; weekday_offset() { echo 0; }\n'
        script=prefix+mocks+'\n# Safety invariant:'+startup
        # Early geometry/preflight uses these dependencies; inject before source.
    else:
        prefix,startup=viewer.split('\ndetect_screen; find_touch_device',1)
        mocks='''
detect_screen() { SCREEN_W=1272; SCREEN_H=1696; VIEW_W=1272; VIEW_H=1696; ORIGIN_X=0; ORIGIN_Y=0; }
draw_background() { echo DRAW >> "$TRACE"; }; draw_dynamic() { :; }
build_cache() { :; }; metric_begin() { :; }; metric_end() { :; }
refresh_region() { :; }; days_in_month() { echo 31; }; weekday_offset() { echo 0; }
'''
        script=prefix+mocks+'\ndetect_screen; find_touch_device'+startup
    setup=f'''TRACE={q(trace)}; export TRACE
lua() {{ {q(sys.executable)} {q(runner)} "$@"; }}
lipc-set-prop() {{ printf '%s\\n' "$*" >> "$TRACE"; }}
fbset() {{ echo 'geometry 1272 1696 1272 3392 8'; }}
uname() {{ if [ "$1" = -m ]; then echo armv7l; else /usr/bin/uname "$@"; fi; }}
'''
    script=setup+script.replace('/tmp/native-reading-dashboard.',(root/'native-reading-dashboard.').as_posix()).replace('SESSION_DIR="'+(root/'native-reading-dashboard.').as_posix()+'$$"',f'SESSION_DIR={q(session)}').replace('SESSION_DIR="${READING_UI_SESSION:-'+(root/'native-reading-dashboard.').as_posix()+'$$}"',f'SESSION_DIR={q(session)}')
    from runtime_fixture import install_power_fixture
    install_power_fixture(release, root/'mockbin')
    script='PATH="$(CDPATH= cd -- '+q(root/'mockbin')+' && pwd):$PATH"\n'+script
    script_path=root/'run.sh'; script_path.write_text(script,encoding='utf-8',newline='\n')
    env={**os.environ,'PATH':'/usr/bin:/bin:'+os.environ.get('PATH',''),'READING_BASE':base.as_posix(),'READING_INPUT_SYSFS':(root/'sys').as_posix(),
         'READING_INPUT_DEV':(root/'dev').as_posix(),'READING_LUA_BINARY':elf.as_posix(),'READING_LAUNCHER_CAPTURE':'1',
         'READING_TOUCH_MACHINE':'armv7l'}
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in [base/'reading-time.tsv',base/'user.conf',base/'book-covers/sentinel',base/'bin/native-reading-time-daemon.sh']}
    sh=shutil.which('sh') or r'C:\Program Files\Git\bin\sh.exe'
    result=subprocess.run([sh,script_path.as_posix()],env=env,capture_output=True,timeout=30)
    log=trace.read_text(encoding='utf-8'); text=result.stdout.decode('utf-8',errors='replace')
    assert 'KPP_LIBRARY' in log and 'eatTapMode 0' in log and 'preventScreenSaver' not in log,(kind,legacy,text,result.stderr,log)
    if kind=='exit' and result.returncode != 0:
        shutil.copytree(root, ROOT/'build/validation/touch-shell-failure', dirs_exist_ok=True)
    assert not session.exists(),(kind,legacy,text,result.stderr)
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items())
    if kind=='no_candidate': assert 'DRAW' not in log and result.returncode!=0,(text,log)
    elif kind=='exit': assert 'DRAW' in log and result.returncode==0,(text,result.stderr,log)
    else: assert 'DRAW' in log and result.returncode!=0,(text,result.stderr,log)
    if kind in ('short','corrupt','dropped'):
        fields=(base/'touch-last.log').read_text()
        assert 'reader_state=reader_failed' in fields
        assert {'short':'short_read','corrupt':'corrupt_event_stream','dropped':'syn_dropped'}[kind] in fields
    COUNTS['shell']+=1

def main():
    original=os.environ.copy()
    try:
        for key in list(os.environ):
            if key.startswith(('READING_TOUCH','READING_INPUT','READING_EVENT','READING_LUA')): os.environ.pop(key)
        with tempfile.TemporaryDirectory(prefix='standard-touch-') as tmp:
            work=Path(tmp)
            for firmware in FIRMWARES:
                os.environ.update(READING_TOUCH_FIRMWARE=firmware,READING_TOUCH_MACHINE='armv7l',READING_TOUCH_ARCH='armhf',
                                  READING_TOUCH_SCREEN_WIDTH='1072',READING_TOUCH_SCREEN_HEIGHT='1448',
                                  READING_TOUCH_VIEWPORT='1072x1429+0+9',READING_TOUCH_LOGICAL_SIZE='1272x1696')
                for topology in 'ABCDEFGH':
                    root=work/f'{firmware}-{topology}'; root.mkdir(); (root/'sys').mkdir()
                    expected=None
                    if topology=='A':
                        candidate(root,0,'power',keys=[116],direct=False); candidate(root,1,'orientation sensor',xy=True)
                        expected=candidate(root,2,'unknown_vendor_input',mt=True)
                    elif topology=='B': expected=candidate(root,0,'zforce',xy=True,direct=False)
                    elif topology=='C': candidate(root,1,'stylus',xy=True); expected=candidate(root,2,'finger',mt=True)
                    elif topology=='D': candidate(root,1,'Wacom digitizer',xy=True); expected=candidate(root,3,'finger',xy=True)
                    elif topology=='E': expected=candidate(root,7,'unknown_vendor_input',mt=True)
                    elif topology=='F': candidate(root,1,'touchscreen',direct=True)
                    elif topology=='G': candidate(root,3,'finger',mt=True,readable=False)
                    for klass in (1,2):
                        code,fields=probe(root,klass)
                        assert code==(0 if expected else 2),(firmware,topology,fields)
                        assert fields['selected_touch']==(expected.as_posix() if expected else 'none')
                        assert fields['event_struct_size']==str(16 if klass==1 else 24)
                RESULTS[firmware]='PASS: A-H x ELF32/ELF64'
            idle_root=work/'idle-contact'; idle_root.mkdir(); (idle_root/'sys').mkdir()
            legacy_touch=candidate(idle_root,0,'zforce',xy=True,direct=False)
            os.environ['READING_TOUCH_REQUIRE_CONTACT']='1'
            assert probe(idle_root)[0]==2  # cannot infer gesture boundaries safely
            contact_touch=candidate(idle_root,1,'touchscreen',xy=True,keys=[330],direct=False)
            assert probe(idle_root)[1]['selected_touch']==contact_touch.as_posix()
            os.environ.pop('READING_TOUCH_REQUIRE_CONTACT')
            root=work/'special'; root.mkdir(); (root/'sys').mkdir()
            candidate(root,1,'unknown',xy=True,keys=[320])
            candidate(root,2,'unknown',xy=True,props=[6])
            candidate(root,3,'touchpad',mt=True,props=[0])
            finger=candidate(root,4,'unknown',xy=True,keys=[330],direct=False)
            assert probe(root)[1]['selected_touch']==finger.as_posix()
            assert probe(root,0)[0]==2
            os.environ['READING_TOUCH_DEVICE']=(root/'dev/event1').as_posix(); assert probe(root)[0]==2
            os.environ.pop('READING_TOUCH_DEVICE')
            os.environ['READING_TOUCH_MACHINE']='aarch64'
            root64=work/'bitmap64'; root64.mkdir(); (root64/'sys').mkdir()
            candidate(root64,1,'unknown',xy=True,keys=[320],bits=64)
            finger64=candidate(root64,9,'unknown',mt=True,bits=64)
            assert probe(root64,1)[1]['selected_touch']==finger64.as_posix()
            os.environ['READING_TOUCH_MACHINE']='armv7l'
            (root/'sys/event4/device/properties').rename(root/'sys/event4/device/capabilities/prop')
            assert probe(root)[0]==0
            actions=[('daily',(120,85),'exit'),('daily',(600,210),'tab_books'),('daily',(1050,210),'tab_total'),
                     ('daily',(200,210),'tab_daily'),('daily',(150,510),'day_1'),('daily',(630,360),'month_detail_open'),
                     ('daily',(330,360),'month_prev'),('daily',(950,360),'month_next'),
                     ('daily',(450,1595),'detail_prev'),('daily',(800,1595),'detail_next'),('daily',(600,1260),'day_detail_open'),
                     ('books',(180,310),'books_7d'),('books',(500,310),'books_month'),('books',(750,310),'books_year'),
                     ('books',(1100,310),'books_all'),('books',(600,410),'book_row_1'),('books',(600,810),'book_row_2'),
                     ('books',(600,1150),'book_row_3'),('books',(220,1500),'page_prev'),('books',(1050,1500),'page_next'),
                     ('total',(254,694),'total_week'),('total',(636,694),'total_year'),('total',(1018,694),'total_all'),
                     ('total',(356,804),'total_prev'),('total',(916,804),'total_next'),('total',(600,450),'week_trend_open'),
                     ('total',(180,1000),'week_day_0'),('day_detail',(120,85),'day_detail_back'),
                     ('day_detail',(450,1595),'day_detail_prev'),('day_detail',(800,1595),'day_detail_next'),
                     ('month_detail',(120,85),'month_detail_back'),('week_trend',(120,85),'week_trend_back'),
                     ('book_detail',(120,85),'book_detail_back'),('book_detail',(400,810),'book_month_prev'),
                     ('book_detail',(860,810),'book_month_next'),('book_detail',(150,930),'book_day_1'),
                     ('book_detail',(70,800),'book_calendar_clear')]
            screens=[(1072,1448),(1272,1696),(600,800),(758,1024),(1200,1600),(1264,1680)]
            for size in (16,24):
                for screen in screens:
                    for mode,point,action in actions:
                        code,fields=reader(root,mode=mode,point=point,size=size,screen=screen)
                        assert code==0 and fields['last_action']==action,(size,screen,mode,point,action,fields)
                    for month in range(1,13):
                        code,fields=reader(root,mode='total',period='year',point=(75+(month-.5)*1123/12,1000),size=size,screen=screen)
                        assert code==0 and fields['last_action']==f'year_month_{month}',fields
                    for day in range(7):
                        code,fields=reader(root,mode='total',point=(135+(day+.5)*1047/7,1000),size=size,screen=screen)
                        assert code==0 and fields['last_action']==f'week_day_{day}',fields
                    for transform in ['direct','swap','invert_x','invert_y','invert_xy','swap_invert_x','swap_invert_y','swap_invert_xy']:
                        for point,action in [((120,85),'exit'),((600,210),'tab_books'),((1050,210),'tab_total')]:
                            code,fields=reader(root,point=point,size=size,screen=screen,transform=transform)
                            assert code==0 and fields['last_action']==action and fields['last_transform']==transform,fields
                    code,fields=reader(root,codes=(0,1),size=size,screen=screen)
                    assert code==0 and fields['last_action']=='exit'
                for transform in ['direct','swap','invert_xy','swap_invert_y']:
                    code,fields=reader(root,point=(600,210),size=size,screen=(1072,1448),viewport=(1072,1429,0,9),
                                       transform=transform,bounds=(-20,5559,50,7439))
                    assert code==0 and fields['last_action']=='tab_books',fields
                code,fields=reader(root,point=(600,210),size=size,viewport=(900,1200,20,40))
                assert code==0 and fields['last_action']=='tab_books'
                # Lifecycle: coordinates arrive on different frames, duplicate
                # press and movement must not reuse a tap; commit on release.
                stream=[(1,330,1),(3,0,600),(0,0,0),(3,1,210),(0,0,0),(1,330,1),
                        (3,0,1050),(0,0,0),(0,0,0),(1,330,0),(0,0,0)]
                code,fields=reader(root,size=size,stream=stream)
                assert code==0 and fields['last_action']=='tab_books',fields
                stream=[(3,47,0),(3,57,5),(3,53,600),(0,0,0),(3,54,210),(0,0,0),
                        (3,53,1050),(0,0,0),(3,57,-1),(0,0,0)]
                code,fields=reader(root,size=size,stream=stream)
                assert code==0 and fields['last_action']=='tab_books',fields
                for stream,error in [([], 'short_read'), ([(255,0,0)]*8,'corrupt_event_stream'), ([(0,3,0)],'syn_dropped')]:
                    code,fields=reader(root,size=size,stream=stream)
                    assert code==2 and fields['reader_error']==error,fields
                # Explicit contact outside the UI cannot become a different
                # button via swap/invert retries, and repeat SYN cannot fire.
                stream=[(3,57,1),(3,53,0),(3,54,0),(0,0,0),(3,53,600),(3,54,210),(0,0,0),(3,57,-1),(0,0,0)]
                code,fields=reader(root,size=size,stream=stream)
                assert code==2 and fields['last_action']=='ignore_outside',fields
                stream=[(3,47,0),(3,57,1),(3,53,600),(3,54,210),(3,47,1),(3,57,2),(3,53,1050),(3,54,210),
                        (0,0,0),(3,57,-1),(3,47,0),(3,57,-1),(0,0,0)]
                code,fields=reader(root,size=size,stream=stream)
                assert code==2 and 'last_action' not in fields,fields
                code,fields=reader(root,size=size,stream=[(3,53,600),(3,54,210),(0,2,0),(0,0,0)])
                assert code==0 and fields['last_action']=='tab_books'
                code,fields=reader(root,size=size,legacy=True,point=(200,210))
                assert code==0 and fields['last_action']=='tab_total'
            for legacy in (False,True):
                for kind in ['exit','short','corrupt','dropped','no_candidate','books']:
                    shell_case(work/f'shell-{legacy}-{kind}',kind,legacy)
            assert 'f:read(16)' not in READER and '/dev/input/event1' not in PROBE
            assert 'timeout' not in READER and 'sleep(' not in READER
            RESULTS.update(counts=COUNTS,screen_matrix=screens,result='PASS',real_hardware_verified=False)
            output=ROOT/'build/validation/standard-touch-results.json'; output.parent.mkdir(parents=True,exist_ok=True)
            output.write_text(json.dumps(RESULTS,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(RESULTS,ensure_ascii=False,indent=2))
    finally:
        os.environ.clear(); os.environ.update(original)

if __name__=='__main__': main()
