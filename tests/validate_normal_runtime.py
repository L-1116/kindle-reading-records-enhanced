"""Execute the real launcher/UI shells with mocked hardware, including signals."""
from normal_fixture import *
import json
import time

checks=[]
def passed(name,detail=""):
    checks.append({"check":name,"result":"PASS","detail":detail});print("PASS: "+name,flush=True)

installed_templates = {}
def ready(shell=SH):
    # Install the exact final payload once per shell. Runtime fault cases copy
    # that verified deployment; the separate install matrix executes every
    # fresh/upgrade/repair/rollback transaction rather than repeating it here.
    if shell not in installed_templates:
        template=Device(shell);template.seed('9.7.5-test');template.install()
        template.no_temporary();installed_templates[shell]=template
    template=installed_templates[shell]
    d=Device(shell)
    for source,target in [(template.base,d.base),(template.docs,d.docs),(template.etc/'upstart',d.etc/'upstart')]:
        shutil.copytree(source,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns(BOOTSTRAP,PAYLOAD) if source==template.docs else None)
        for path in target.rglob('*'):
            if path.is_file() and path.suffix in ['.sh','.conf','.tsv','.txt']:
                raw=path.read_bytes().replace(template.root.as_posix().encode(),d.root.as_posix().encode())
                path.write_bytes(raw)
    d.flag('running');d.flag('actions','exit')
    return d

def restored(d,orientation,eat,power):
    assert d.read('orientation')==orientation,(d.read('orientation'),d.calls())
    assert d.read('eatTapMode')==eat and d.read('preventScreenSaver')==power,d.calls()
    d.no_temporary()
    assert ' -e ' not in d.calls()

def ui(d,ok=True):return d.run(d.docs/'reading-records.sh',ok=ok)

for orientation in ['U','D','R','L']:
    d=ready();d.flag('orientation',orientation);d.flag('eatTapMode','2');d.flag('preventScreenSaver','0')
    before=d.preserved();ui(d);restored(d,orientation,'2','0');assert d.preserved()==before
    assert 'switching to original dashboard' not in (d.base/'dashboard-launch.log').read_text(encoding='utf-8')
    if orientation in 'RL':
        assert 'set com.lab126.winmgr orientationLock U' in d.calls()
        assert f'set com.lab126.winmgr orientationLock {orientation}' in d.calls()
    else:assert 'set com.lab126.winmgr orientationLock' not in d.calls()
    passed('portrait/landscape startup and original state restoration: '+orientation)

d=ready();d.flag('orientation','R');d.flag('preventScreenSaver','1')
for i in range(5):d.flag('actions','exit');ui(d);restored(d,'R','0','1')
passed('five repeated landscape launches; original nonzero screensaver property preserved')

for mode in ['missing-main','syntax-main','missing-font','touch-failure','fbink-failure','orientation-timeout','orientation-set-failure','orientation-read-failure','invalid-orientation','power-read-failure','eat-set-failure']:
    d=ready();d.flag('orientation','R');release=d.base/'releases/9.7.6-5.19-normal'
    if mode=='missing-main':(release/'bin/reading-records-ui.sh').unlink()
    elif mode=='syntax-main':write(release/'bin/reading-records-ui.sh','if then broken')
    elif mode=='missing-font':(d.base/'fonts/NotoSansCJKsc-Regular.otf').unlink()
    elif mode=='touch-failure':d.flag('fail-touch')
    elif mode=='fbink-failure':d.flag('fail-fbink')
    elif mode=='orientation-timeout':d.flag('orientation-timeout')
    elif mode=='orientation-set-failure':d.flag('fail-set-orientationLock')
    elif mode=='orientation-read-failure':d.flag('fail-get-orientationLock')
    elif mode=='invalid-orientation':d.flag('orientation','invalid');d.command('fbset',"echo 'geometry 1696 1272 1696 1272 8'");d.chmod([d.mock/'fbset'])
    elif mode=='power-read-failure':d.flag('fail-get-preventScreenSaver')
    elif mode=='eat-set-failure':d.flag('fail-set-eatTapMode')
    ui(d,ok=False);restored(d,'invalid' if mode=='invalid-orientation' else 'R','0','0')
    if mode in ['missing-main', 'syntax-main']:assert 'set com.lab126.appmgrd start' not in d.calls()
    if mode in ['invalid-orientation','orientation-read-failure']:
        assert 'set com.lab126.winmgr orientationLock U' not in d.calls()
    if mode=='fbink-failure':assert 'switching to original dashboard' not in (d.base/'dashboard-launch.log').read_text(encoding='utf-8')
    passed('safe startup/runtime failure cleanup: '+mode)

for mode in ['renderer-missing','renderer-Lua-error','legacy-failure','fast-refresh-fallback']:
    d=ready();d.flag('orientation','L');release=d.base/'releases/9.7.6-5.19-normal'
    if mode=='renderer-missing':(release/'bin/reading-insights-render.lua').unlink()
    elif mode=='renderer-Lua-error':write(release/'bin/reading-insights-render.lua','error("injected Lua failure")')
    elif mode=='legacy-failure':
        (release/'bin/reading-insights-render.lua').unlink();write(release/'bin/reading-records-v9.6.3.sh','exit 4')
    else:d.flag('fail-fast');d.flag('actions','tab_books\nexit')
    ui(d,ok=mode!='legacy-failure');restored(d,'L','0','0')
    passed('renderer/fallback lifecycle: '+mode)

for shell in (SH,DASH):
    for signum,status in [('INT',130),('TERM',143),('HUP',129)]:
        for fallback in [False,True]:
            d=ready(shell);d.flag('orientation','R');d.flag('block-touch')
            if fallback:(d.base/'releases/9.7.6-5.19-normal/bin/reading-insights-render.lua').unlink()
            path=d.docs/'reading-records.sh'
            text=path.read_text(encoding='utf-8').replace('exec >> "$LOG" 2>&1','echo "$$" > "$SIM/launch-pid"\nexec >> "$LOG" 2>&1')
            write(path,text)
            process=subprocess.Popen([shell,'-c','export PATH="$SIM/mockbin:/usr/bin:/bin:$PATH"; exec "$1" "$2"','run',shell,path.as_posix()],env=d.env,cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            deadline=time.monotonic()+20
            while not (d.root/'touch-pid').exists():
                assert process.poll() is None,(process.returncode,d.calls())
                assert time.monotonic()<deadline,d.calls();time.sleep(.05)
            pid=d.read('launch-pid');touch_pid=d.read('touch-pid')
            subprocess.run([SH,'-c',f'kill -{signum} {pid}'],check=True,capture_output=True)
            code=process.wait(timeout=10);assert code==status,(code,status,d.calls())
            restored(d,'R','0','0')
            alive=subprocess.run([SH,'-c',f'kill -0 {touch_pid} 2>/dev/null'],capture_output=True)
            assert alive.returncode!=0,'orphaned touch reader'
            passed(f'{Path(shell).name}: {signum} while blocked '+('legacy UI' if fallback else 'optimized UI'))

# The failure-prone property request window has a saved value BEFORE mutation.
for signum,status in [('INT',130),('TERM',143),('HUP',129)]:
    d=ready();d.flag('orientation','R')
    mock=(d.mock/'lipc-set-prop').read_text(encoding='utf-8')
    mock=mock.replace('"$SIM/orientation";;', '"$SIM/orientation"; if [ "$3" = U ]; then kill -'+signum+' "$PPID"; fi;;')
    assert 'kill -'+signum in mock
    write(d.mock/'lipc-set-prop',mock);d.chmod([d.mock/'lipc-set-prop'])
    p=ui(d,ok=False);assert p.returncode==status,p.returncode
    restored(d,'R','0','0');passed('signal during orientation request return window: '+signum)

# Inject signals between fork and PID assignment, the smallest ownership gap.
for owner in ['launcher','touch-reader']:
    for signal,status in [('TERM',143),('HUP',129)]:
        d=ready();d.flag('orientation','R');d.flag('block-touch')
        if owner=='launcher':
            path=d.docs/'reading-records.sh';target='UI_PID=$!'
        else:
            path=d.base/'releases/9.7.6-5.19-normal/bin/runtime-child.sh';target='UI_CHILD=$!'
        text=path.read_text(encoding='utf-8').replace(target, 'kill -'+signal+' "$$"\n'+target)
        write(path,text)
        p=ui(d,ok=False);assert p.returncode==status,(p.returncode,d.calls())
        restored(d,'R','0','0')
        if (d.root/'touch-pid').exists():
            pid=d.read('touch-pid');alive=subprocess.run([SH,'-c',f'kill -0 {pid} 2>/dev/null'],capture_output=True)
            assert alive.returncode!=0,'orphaned reader in spawn window'
        passed('signal at fork/PID assignment window: '+owner+' '+signal)

# A terminated old session can leave only these exact lock-owned marker files.
for owner in ['installer', 'launcher']:
    d=ready(); lock=d.tmp/'reading-records-ui.lock'
    write(lock/'pid', '99999999');write(lock/'ui-start', '');write(lock/'ui-cancel', '')
    if owner=='installer':d.install()
    else:ui(d)
    d.no_temporary();passed('stale UI lock with handoff markers safely recovered: '+owner)

# A running UI holds the same lock as an install, excluding mixed activation.
d=ready()
owner=subprocess.Popen([SH,'-c','echo "$$" > "$SIM/owner-pid"; exec /usr/bin/sleep 60'],env=d.env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
deadline=time.monotonic()+5
while not (d.root/'owner-pid').exists():
    assert time.monotonic()<deadline;time.sleep(.05)
owner_pid=d.read('owner-pid');write(d.tmp/'reading-records-ui.lock/pid',owner_pid)
before=d.preserved();d.install(ok=False);assert d.preserved()==before
assert (d.tmp/'reading-records-ui.lock/pid').read_text().strip()==owner_pid
subprocess.run([SH,'-c',f'kill -TERM {owner_pid}'],check=True,capture_output=True);owner.wait(timeout=5)
assert (d.tmp/'reading-records-ui.lock/pid').exists()
shutil.rmtree(d.tmp/'reading-records-ui.lock');d.no_temporary();passed('installer and UI share an exclusive session lock')

d=ready();d.flag('orientation','R')
d.command('fbset',"echo 'geometry 1272 1696 1272 1696 8'");d.chmod([d.mock/'fbset'])
ui(d);restored(d,'R','0','0')
assert 'set com.lab126.winmgr orientationLock U' in d.calls()
passed('landscape orientation property triggers rotation even if framebuffer geometry appears portrait')

# Run the entire retained optimized navigation flow with real Lua rendering.
d=ready();d.flag('orientation','R')
actions=['tab_total','week_trend_open','week_trend_back','total_year','year_month_9','month_detail_back','total_all','tab_books','books_all','book_row_1','book_month_prev','book_month_next','book_day_6','book_calendar_clear','book_detail_back','books_month','books_year','books_7d','tab_daily','month_prev','day_6','day_detail_open','day_detail_back','month_detail_open','month_detail_back','exit']
d.flag('actions','\n'.join(actions));before=d.preserved()
d.run(d.docs/'reading-records.sh',timeout=120)
restored(d,'R','0','0');assert d.preserved()==before
log=(d.base/'dashboard-launch.log').read_text(encoding='utf-8')
assert 'switching to original dashboard' not in log,log
for action in actions:assert 'dashboard action='+action+' ' in log,action
passed('complete optimized UI dispatch with real Lua: statistics, all filters, day/month/8-week/book detail and book calendar')

result={'result':'PASS','checks':checks,'case_count':len(checks),'limits':['LIPC, framebuffer and physical input hardware mocked; no actual Kindle power-key or rotation verification. SIGKILL, power loss and an unresponsive system LIPC service cannot be recovered by POSIX traps.']}
write(OUT/'runtime-results.json',json.dumps(result,ensure_ascii=False,indent=2))
