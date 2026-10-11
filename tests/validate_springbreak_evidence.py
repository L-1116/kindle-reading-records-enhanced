"""Characterize the exact Vera input readers; no device/hardware inference."""
from pathlib import Path
import json, struct, subprocess, sys, tempfile
from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / 'native-reading-time-package'
OUT = ROOT / 'build/springbreak-audit'
OUT.mkdir(parents=True, exist_ok=True)
BASE = '3acda144ee7bf3a09d7472628efdffd9c09ab240'
checks = []

def passed(name, **details):
    checks.append(dict(check=name, result='PASS', **details))
    print('PASS: ' + name, flush=True)

def event(t, c, v, size=16):
    return struct.pack('<IIHHi' if size == 16 else '<QQHHi', 123, 456, t, c, v)

def run_reader(source, raw):
    with tempfile.TemporaryDirectory(prefix='springbreak-evdev-') as tmp:
        device = Path(tmp) / 'input.bin'; log = Path(tmp) / 'touch.log'
        device.write_bytes(raw)
        lua = LuaRuntime()
        lua.globals().arg = lua.table_from({1:device.as_posix(),2:log.as_posix(),3:'daily',
                                           4:'0',5:'31',6:'0',7:'9',8:'1072',9:'1429'})
        lua.execute('handles={}; native_open=io.open; io.open=function(...) '
                    'local h,e=native_open(...); if h then handles[#handles+1]=h end; return h,e end; '
                    'output=""; status=nil; io.write=function(s) output=output..s end; '
                    'os.exit=function(s) status=s; error("fixture exit") end')
        try: lua.execute(source)
        except Exception as exc: assert 'fixture exit' in str(exc), str(exc)
        lua.execute('for _,h in ipairs(handles) do pcall(function() h:close() end) end')
        return lua.globals().status, lua.globals().output, log.read_text() if log.exists() else ''

for name in ('reading-insights-touch.lua', 'reading-insights-touch-ui.lua'):
    before = subprocess.check_output(['git','show',BASE+':native-reading-time-package/'+name],cwd=ROOT)
    assert (PKG/name).read_bytes() == before, name
    source = before.decode()
    for codes in ((0,1),(53,54)):
        raw = event(3,codes[0],90)+event(3,codes[1],80)+event(0,0,0)
        status, output, log = run_reader(source, raw)
        assert status == 0 and output == 'exit' and 'mapped' in log and 'tap x=90 y=80' in log
        passed(name+': 16-byte ABS/MT tap maps exit at KPW4 viewport', codes=codes)
    # Other contacts/key/sync codes are ignored; SYN_MT_REPORT is not a tap.
    raw = event(3,47,0)+event(3,57,1)+event(1,330,1)+event(3,53,90)+event(3,54,80)+event(0,2,0)+event(0,0,0)
    assert run_reader(source,raw)[:2] == (0,'exit')
    passed(name+': MT slot/tracking/BTN_TOUCH/SYN_MT_REPORT do not suppress valid SYN_REPORT')
    for label,raw in [
        ('non-touch event node',event(1,116,1)+event(0,0,0)),
        ('missing Y coordinate',event(3,53,90)+event(0,0,0)),
        ('24-byte event layout',event(3,53,90,24)+event(3,54,80,24)+event(0,0,0,24)),
    ]:
        status,output,log = run_reader(source,raw)
        assert status == 2 and not output and 'watcher started' in log and 'tap ' not in log
        passed(name+': watcher with no tap reproduced', fixture=label,
               conclusion='Synthetic fixture, not evidence that this Kindle uses this condition')
    # Coordinates split over reports work only if neither complete pair was consumed.
    assert run_reader(source,event(3,53,90)+event(0,0,0)+event(3,54,80)+event(0,0,0))[:2] == (0,'exit')
    passed(name+': separate SYN_REPORT packets retain incomplete X/Y pair')
    status,output,log = run_reader(source,event(3,53,4000)+event(3,54,4000)+event(0,0,0))
    assert status == 2 and not output and 'tap x=4000 y=4000' in log and 'mapped' not in log
    passed(name+': out-of-viewport coordinates produce tap but no mapped; differs from historical no-tap')

assert 1696*1072//1272 == 1429 and (1448-1429)//2 == 9
passed('integer fit exactly reproduces historical 1072x1448 / 1072x1429+0+9')

SH = 'C:/Program Files/Git/usr/bin/sh.exe' if sys.platform == 'win32' else '/bin/sh'
for name in ('阅读记录-optimized.sh','阅读记录.sh'):
    source=subprocess.check_output(['git','show',BASE+':native-reading-time-package/'+name],cwd=ROOT).decode()
    function=source[source.index('find_touch_device() {'):source.index('scale_len() {')]
    with tempfile.TemporaryDirectory(prefix='springbreak-selection-') as tmp:
        folder=Path(tmp); sysfs=folder/'sys'; dev=folder/'dev'; dev.mkdir()
        for node,label in [('event1','power button'),('event3','cyttsp touch')]:
            p=sysfs/node/'device/name';p.parent.mkdir(parents=True);p.write_text(label)
            (dev/node).touch()
        fn=function.replace('/sys/class/input',sysfs.as_posix()).replace('/dev/input',dev.as_posix())
        def select():
            return subprocess.check_output([SH,'-c','export PATH="/usr/bin:/bin:$PATH"; '+fn+'\nfind_touch_device; printf "%s" "$TOUCH"']).decode()
        assert select()==(dev/'event3').as_posix()
        passed(name+': recognized readable event3 wins over readable non-touch event1')
        (sysfs/'event3/device/name').write_text('unrecognized driver')
        assert select()==(dev/'event1').as_posix()
        passed(name+': event1 can be fallback without positive touch identification')

(OUT/'input-evidence.json').write_text(json.dumps(dict(result='PASS',base=BASE,checks=checks,
    conclusion='Test 1 real sysfs proves event1 is bd71827-power and event2 is goodix-ts. Historical baseline selectors still reproduced above; raw goodix event layout/coordinates remain unverified.'),ensure_ascii=False,indent=2),encoding='utf-8')
