"""Run the dedicated target gate and bounded-session recovery against real sh/dash."""
from normal_fixture import *
from springbreak_contract import *
import time, json

checks=[]
def passed(name, **detail):
    checks.append(dict(check=name,result='PASS',**detail));print('PASS: '+name,flush=True)

def git_file(name, ref=BASE):
    return subprocess.check_output(['git','show',ref+':native-reading-time-package/'+name],cwd=ROOT)

launcher=(PKG/'launch.sh').read_text(encoding='utf-8')
assert baseline_launcher(launcher).encode()==git_file('launch.sh')
for name in ['阅读记录-optimized.sh','阅读记录.sh','resources/reading-records-install-cleanup.sh']:
    current=(PKG/name).read_text(encoding='utf-8')
    if name.startswith('阅读记录'): current=baseline_ui(current,git_file(name).decode())
    assert current.replace(VERSION,VERA).encode()==git_file(name)
passed('launcher exact inverse delta; UI shells only selector/identity changed; cleanup only identity changed')
files=subprocess.check_output(['git','ls-tree','-rz','--name-only',BASE,'native-reading-time-package'],cwd=ROOT).decode().split('\0')
allowed={'launch.sh','install.sh','阅读记录-optimized.sh','阅读记录.sh','resources/reading-records-install-cleanup.sh'}
for path in filter(None,files):
    name=path.split('/',1)[1]
    if name not in allowed:assert (PKG/name).read_bytes()==git_file(name),name
passed('all other baseline package source bytes unchanged: both Lua readers, runtime helpers, assets, tracker and statistics')
assert launcher.count('SESSION_LIMIT=120')==1 and '$SESSION_LIMIT' in launcher
active='\n'.join(l for l in launcher.splitlines() if not l.lstrip().startswith('#'))
assert 'eatTapMode' not in active and ' &\n' not in SESSION_BLOCK
assert 'kill -TERM "$UI_PID"' in launcher and 'wait "$UI_PID"' in launcher
passed('120 fixed sleep ticks; no timer process, user override, alternate cleanup or eatTapMode request')

source=(PKG/'install.sh').read_text(encoding='utf-8')
assert source.count(MODEL_BLOCK)==1
inverse=source.replace(MODEL_BLOCK,'').replace(VERSION,VERA)
inverse=inverse.replace('Kindle firmware 5.18.1.1.1','Kindle firmware 5.18.x').replace('case "$firmware" in 5.18.1.1.1)','case "$firmware" in 5.18.*)')
assert inverse.encode()==git_file('install.sh')
boot_source=(ROOT/'documents'/BOOTSTRAP).read_text(encoding='utf-8')
assert boot_source.count("log 'BEGIN: "+VERSION+" install'\n")==1
boot_inverse=boot_source.replace("log 'BEGIN: "+VERSION+" install'\n",'').replace("printf '' >> \"$LOG\"", "printf '' > \"$LOG\"")
assert boot_inverse.encode()==subprocess.check_output(['git','show',BASE+':documents/'+BOOTSTRAP],cwd=ROOT)
passed('installer exact inverse: target guards/identity only; bootstrap only appends and delimits existing log')
gate=source[:source.index('[ -x /sbin/initctl ]')]+'\nexit 0\n'
codes=['0PP','0T1','0T2','0T3','0T4','0T5','0T6','0T7','0TJ','0TK','0TL','0TM','0TN','102','103','16Q','16R','16S','16T','16U','16V']
for shell in (SH,DASH):
    d=Device(shell);path=d.root/'target-gate.sh';write(path,d.transform(gate.encode()).decode())
    for code in codes:
        write(d.root/'proc/usid','G00'+code)
        d.run(path);d.no_temporary();passed(Path(shell).name+': supported non-unique PW4 product code '+code)
    for code in ['1Q0','0G1','10L','0WQ','27J','XXX','0P','0PPextra','']:
        write(d.root/'proc/usid','G00'+code)
        # Only bytes 4..6 matter, so longer identifiers share the same product.
        result=d.run(path,ok=(code=='0PPextra'))
        if code!='0PPextra':assert '仅适用于 KPW4' in result.stdout
        assert 'G00' not in result.stdout
        if code: assert code not in result.stdout
        d.no_temporary();passed(Path(shell).name+': product code rejection/length '+repr(code))
    (d.root/'proc/usid').unlink();d.run(path,ok=False)
    passed(Path(shell).name+': absent model evidence refuses before transaction')
    write(d.root/'proc/usid','G000PP')
    for firmware in ['5.18.0','5.18.1','5.18.1.1','5.18.1.1.1.1','5.18.4','5.19.1','5.180.1','5.18.1.1.1evil']:
        d.firmware(firmware);result=d.run(path,ok=False)
        assert '5.18.1.1.1' in result.stdout;d.no_temporary()
        passed(Path(shell).name+': dedicated firmware rejects '+firmware)
    for primary,fallback,ok in [('Kindle 5.18.1.1.1','5.19.1',True),
                                ('5.18.1.1.1 5.18.4','5.18.1.1.1',False),
                                ('bad','Kindle 5.18.1.1.1',True),
                                ('bad','5.18.1.1.1 5.19.1',False)]:
        write(d.etc/'prettyversion.txt',primary);write(d.etc/'version.txt',fallback)
        d.run(path,ok=ok);d.no_temporary();passed(Path(shell).name+': strict primary/fallback '+repr((primary,fallback)))
    assert 'root rw' not in d.calls() and 'service stop' not in d.calls()
    passed(Path(shell).name+': unsupported target never writes rootfs/stops service')

templates={}
def ready(shell):
    if shell not in templates:
        d=Device(shell);d.seed(VERA);d.install();templates[shell]=d
    template=templates[shell];d=Device(shell)
    for src,dst in [(template.base,d.base),(template.docs,d.docs),(template.etc/'upstart',d.etc/'upstart')]:
        shutil.copytree(src,dst,dirs_exist_ok=True,ignore=shutil.ignore_patterns(BOOTSTRAP,PAYLOAD) if src==template.docs else None)
        for p in dst.rglob('*'):
            if p.is_file() and p.suffix in {'.sh','.conf','.tsv','.txt'}:
                p.write_bytes(p.read_bytes().replace(template.root.as_posix().encode(),d.root.as_posix().encode()))
    d.flag('running');return d

def spawn(d):
    path=d.docs/'reading-records.sh'
    text=path.read_text(encoding='utf-8').replace('exec >> "$LOG" 2>&1','echo "$$" > "$SIM/launch-pid"\nexec >> "$LOG" 2>&1')
    write(path,text)
    return subprocess.Popen([d.shell,'-c','export PATH="$SIM/mockbin:/usr/bin:/bin:$PATH"; exec "$1" "$2"','run',d.shell,path.as_posix()],env=d.env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def await_reader(d,process):
    until=time.monotonic()+40
    while not (d.root/'touch-pid').exists():
        assert process.poll() is None,(process.returncode,d.calls())
        assert time.monotonic()<until,(d.calls(),d.base/'dashboard-launch.log')
        time.sleep(.02)

def dead(pid):
    return subprocess.run([SH,'-c','kill -0 "$1"','owned',pid],capture_output=True).returncode!=0

for shell in (SH,DASH):
    for fallback in (False,True):
        for direction,power in [('U','0'),('R','2')]:
            d=ready(shell);d.flag('block-touch');d.flag('orientation',direction);d.flag('preventScreenSaver',power)
            d.command('fbset', 'case "$(cat "$SIM/orientation")" in R|L) echo "geometry 1448 1072 1448 1072 8";; *) echo "geometry 1072 1448 1072 1448 8";; esac')
            d.chmod([d.mock/'fbset'])
            if fallback:(d.base/f'releases/{VERSION}/bin/reading-insights-render.lua').unlink()
            # Mock only sleep duration after input-reader readiness. Production
            # still executes all 120 ticks and the unmodified cleanup functions.
            d.command('sleep','case "$1" in 1) if [ -f "$SIM/touch-pid" ]; then /usr/bin/sleep 0.01; else /usr/bin/sleep 1; fi;; *) exit 0;; esac')
            d.chmod([d.mock/'sleep']);before=d.preserved();process=spawn(d);await_reader(d,process)
            touch=d.read('touch-pid');started=time.monotonic()
            layout=(d.base/'display-layout.txt').read_text()
            assert 'screen=1072x1448' in layout and 'viewport=1072x1429+0+9' in layout
            # A second launch is refused while the guarded session owns the lock.
            d.run(d.docs/'reading-records.sh',ok=False)
            assert process.wait(timeout=15)==124
            log=(d.base/'dashboard-launch.log').read_text(encoding='utf-8')
            assert log.count('SAFETY_EXIT:')==1 and 'session_limit_seconds=120' in log
            assert dead(touch) and d.read('orientation')==direction and d.read('preventScreenSaver')==power
            assert 'eatTapMode' not in d.calls() and d.preserved()==before
            assert (d.docs/BOOTSTRAP).exists() and d.payload.exists()
            d.no_temporary();passed(f'{Path(shell).name}: timeout blocked real UI fallback={fallback} direction={direction} power={power}',scaled_seconds=round(time.monotonic()-started,2))
            # Reopening after timeout verifies no stale mutex or deadline process.
            d.unflag('block-touch');d.flag('actions','exit');d.run(d.docs/'reading-records.sh');d.no_temporary()
            assert log.count('SAFETY_EXIT:')==(d.base/'dashboard-launch.log').read_text(encoding='utf-8').count('SAFETY_EXIT:')
            passed(f'{Path(shell).name}: after timeout clean relaunch fallback={fallback} direction={direction}')
    # Real short wall-clock deadline on a minimal owned UI + actual runtime-child.
    d=ready(shell);main=d.base/f'releases/{VERSION}/bin/reading-records-ui.sh'
    child=main.parent/'runtime-child.sh'
    minimal=f'''#!/bin/sh
BASE="{d.base.as_posix()}"; SESSION_DIR="{d.tmp.as_posix()}/native-reading-dashboard.$$"
fail() {{ exit 1; }}
mkdir "$SESSION_DIR"
. "{child.as_posix()}"
cleanup() {{ stop_ui_child; rm -rf "$SESSION_DIR"; }}
trap cleanup EXIT
trap 'runtime_child_signal 143' TERM
read_touch_action "{main.parent.as_posix()}/reading-insights-touch-ui.lua"
'''
    write(main,minimal);d.flag('block-touch');path=d.docs/'reading-records.sh'
    text=path.read_text(encoding='utf-8');assert text.count('SESSION_LIMIT=120')==1
    write(path,text.replace('SESSION_LIMIT=120','SESSION_LIMIT=2'))
    started=time.monotonic();process=spawn(d);await_reader(d,process);touch=d.read('touch-pid')
    assert process.wait(timeout=10)==124
    elapsed=time.monotonic()-started
    assert 2 <= elapsed < 10 and dead(touch);d.no_temporary()
    passed(Path(shell).name+': real sleep, short literal deadline terminates/reaps live blocked reader',seconds=round(elapsed,2))

    d=ready(shell);d.flag('orientation','R');d.flag('preventScreenSaver','2')
    d.command('fbink','echo "fbink $*" >> "$SIM/calls"; exit 139');d.chmod([d.mock/'fbink'])
    d.run(d.docs/'reading-records.sh',ok=False)
    assert ' -e ' not in d.calls() and 'fbink -q' in d.calls()
    assert d.read('orientation')=='R' and d.read('preventScreenSaver')=='2';d.no_temporary()
    assert (d.docs/BOOTSTRAP).exists() and d.payload.exists()
    passed(Path(shell).name+': simulated actual FBInk exit 139 cleans state; never runs -e')

    # Install the exact latest Vera payload first, then fault and retry candidate.
    # No copied V4 compatibility source participates in either package.
    d=Device(shell);new_tar,new_boot=d.original_tar,d.original_boot
    with tarfile.open(fileobj=io.BytesIO(new_tar)) as archive:
        old={m.name:git_file(m.name.split('/',1)[1]) for m in archive.getmembers()
             if not m.name.endswith('/payload-manifest.tsv')}
    prefix='native-reading-time-package/'
    old[prefix+'payload-manifest.tsv']=''.join(f'{python_cksum(raw)[0]}\t{len(raw)}\t{name.removeprefix(prefix)}\n'
        for name,raw in sorted(old.items())).encode()
    buffer=io.BytesIO()
    with tarfile.open(fileobj=buffer,mode='w',format=tarfile.USTAR_FORMAT) as archive:
        for name,raw in sorted(old.items()):
            entry=tarfile.TarInfo(name);entry.size=len(raw);entry.mode=0o755 if name.endswith('.sh') else 0o644
            archive.addfile(entry,io.BytesIO(raw))
    old_tar=buffer.getvalue()
    assert hashlib.sha256(old_tar).hexdigest()=='89e46b1e1c44a1943a17365fd2306f7842aa9cae8f709b1b070a674588962a3f'
    checksum,size=python_cksum(old_tar)
    old_boot=subprocess.check_output(['git','show',BASE+':documents/'+BOOTSTRAP],cwd=ROOT)
    old_boot=old_boot.replace(b'@PAYLOAD_CKSUM@',str(checksum).encode()).replace(b'@PAYLOAD_SIZE@',str(size).encode())
    d.original_tar,d.original_boot=old_tar,old_boot;d.prepare_payload();d.seed(VERA);d.install()
    assert d.read('us/reading-time/VERSION')==VERA
    old_runtime={p.relative_to(d.root).as_posix():digest(p) for p in [d.base/'VERSION',d.docs/'reading-records.sh',d.base/'bin/native-reading-time-daemon.sh',d.etc/'upstart/native-reading-time.conf']}
    log_names=['install.log','dashboard-launch.log','dashboard-touch.log','service.log','upstart.log']
    for name in log_names:write(d.base/name,'preserved original core log\n')
    old_log=(d.base/'install-last.log').read_bytes();data=d.preserved()
    d.original_tar,d.original_boot=new_tar,new_boot;d.prepare_payload();d.flag('fail-service');d.install(ok=False)
    assert d.read('us/reading-time/VERSION')==VERA
    assert all(digest(d.root/name)==value for name,value in old_runtime.items())
    assert d.preserved()==data and (d.base/'install-last.log').read_bytes().startswith(old_log)
    assert all((d.base/name).read_text()=='preserved original core log\n' for name in log_names)
    assert (d.docs/BOOTSTRAP).exists() and d.payload.exists();d.no_temporary()
    passed(Path(shell).name+': exact latest Vera -> failed candidate rolls back runtime, retains all data/core logs and install files')
    d.install();assert d.read('us/reading-time/VERSION')==VERSION and d.preserved()==data
    assert (d.base/'install-last.log').read_bytes().startswith(old_log)
    assert all((d.base/name).read_text()=='preserved original core log\n' for name in log_names)
    assert (d.base/f'releases/{VERA}/bin/reading-records-ui.sh').exists()
    broken=d.base/f'releases/{VERSION}/bin/reading-records-ui.sh';write(broken,'exit 99\n');d.install()
    assert broken.read_bytes()==d.transform((PKG/'阅读记录-optimized.sh').read_bytes())
    assert d.preserved()==data;d.no_temporary()
    d.run(d.docs/'reading-records-install-cleanup.sh');assert d.preserved()==data
    assert all((d.base/name).read_text()=='preserved original core log\n' for name in log_names)
    assert (d.base/'install-last.log').read_bytes().startswith(old_log)
    assert not (d.docs/BOOTSTRAP).exists() and not d.payload.exists()
    passed(Path(shell).name+': exact latest Vera -> candidate retry/repair/cleanup preserves history, cache, old release and original install log')

write(OUT/'springbreak-candidate-results.json',json.dumps(dict(result='PASS',checks=checks,
    limits=['Full UI deadline tests accelerate only mocked sleep after readiness. A real 2-second literal test covers wall-clock termination.',
            'Uninterruptible kernel I/O, unresponsive LIPC, SIGKILL and power loss remain hardware/system risks.']),ensure_ascii=False,indent=2))
