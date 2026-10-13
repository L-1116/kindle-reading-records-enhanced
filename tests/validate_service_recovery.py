"""Exercise shared service recovery, fault evidence and the actual timing daemon."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from service_fixture import service_fixture

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT/'native-reading-time-package'
OUT = ROOT/'build/validation'; OUT.mkdir(parents=True,exist_ok=True)
SH = shutil.which('sh') or 'C:/Program Files/Git/usr/bin/sh.exe'
REPORT = []


def setup(folder, variant='standard', running=True):
    base=folder/'reading-time'; upstart=folder/'upstart'; tmp=folder/'tmp'; tmp.mkdir()
    for d in ('bin','compat','service'): (base/d).mkdir(parents=True)
    for src,dest in [('service-manager.sh','bin/service-manager.sh'),('compat/lifecycle.sh','compat/lifecycle.sh'),('native-reading-time-daemon.sh','bin/native-reading-time-daemon.sh'),('native-reading-time.conf','service/native-reading-time.conf')]:
        shutil.copy2(PKG/src,base/dest)
    subprocess.run([SH,'-c','/usr/bin/chmod 755 "$1"','fixture',(base/'bin/native-reading-time-daemon.sh').as_posix()],check=True)
    env={**os.environ,'PATH':'/usr/bin:/bin','READING_BASE':base.as_posix(),'READING_TMPDIR':tmp.as_posix(),'READING_VARIANT':variant}
    env.update(service_fixture(folder/'fixture',base,upstart,SH,running=running))
    shutil.copy2(PKG/'native-reading-time.conf',upstart/'native-reading-time.conf')
    (base/'reading-time.tsv').write_bytes(b'date\tbook_id\tseconds\ttitle\n2026-10-01\told\t120\tHistory\n')
    (base/'launch-last.log').write_bytes(b'original launch failure\n')
    (base/'upstart.log').write_bytes(b'original service failure\n')
    return base,upstart,env


def call(base,env,action='ensure',timeout=18):
    p=subprocess.run([SH,(base/'bin/service-manager.sh').as_posix(),action],env=env,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=timeout)
    fields=dict(line.split('=',1) for line in p.stdout.splitlines() if '=' in line)
    return p,fields


for variant in ('standard',):
    for scenario in ('healthy','stopped','missing-config','fallback','mount-lies','start-failure','query-failure','wrong-process','foreign-config','evidence-failure','rw-original','write-error','rw-restore-config','unknown-mount','all-mount-fail','valid-config-comment'):
        with tempfile.TemporaryDirectory(prefix='service-',dir=OUT) as name:
            folder=Path(name); base,upstart,env=setup(folder,variant,running=scenario not in ('stopped','start-failure'))
            fx=folder/'fixture'; job=upstart/'native-reading-time.conf'; protected={p:p.read_bytes() for p in (base/'reading-time.tsv',base/'launch-last.log',base/'upstart.log')}
            if scenario in ('missing-config','fallback','mount-lies','evidence-failure','rw-restore-config','unknown-mount','all-mount-fail'): job.unlink()
            if scenario=='fallback': (fx/'mntroot-fail').touch()
            if scenario=='mount-lies': (fx/'mount-lie').touch()
            if scenario=='start-failure': (fx/'start-fail').touch()
            if scenario=='query-failure': (fx/'query-fail').touch()
            if scenario=='wrong-process': (fx/'proc/123/cmdline').write_bytes(b'/bin/sh\0unrelated-daemon\0')
            if scenario=='foreign-config': job.write_text('description "another application"\n'); (fx/'running').unlink(); (fx/'proc/123/cmdline').write_bytes(b'')
            if scenario=='evidence-failure': (base/'service-events').write_text('occupied by user file')
            if scenario in ('rw-original','rw-restore-config'): (fx/'mounts').write_text('/dev/root / ext3 rw,relatime 0 0\n')
            if scenario=='valid-config-comment': job.write_bytes(job.read_bytes()+b'# harmless owner comment\n')
            if scenario=='unknown-mount': (fx/'mounts').write_bytes(b'')
            if scenario=='all-mount-fail': (fx/'mntroot-fail').touch(); (fx/'mount-fail').touch()
            if scenario=='write-error': (base/'timing-observation.txt').write_text('pid=123\nstart_ticks=12345\nerror=write_failed\n')
            p,fields=call(base,env)
            calls=(fx/'calls').read_text(encoding='utf-8', errors='replace') if (fx/'calls').exists() else '';  events=list((base/'service-events').glob('event-*')) if (base/'service-events').is_dir() else []
            assert all(path.read_bytes()==raw for path,raw in protected.items()),scenario
            if scenario in ('healthy','rw-original','valid-config-comment'):
                assert p.returncode==0 and fields['service_status']=='healthy', (scenario,p.stdout,p.stderr)
                assert events==[] and 'start native' not in calls and 'reload-configuration' not in calls
            elif scenario in ('stopped','missing-config','fallback','mount-lies','rw-restore-config'):
                assert p.returncode==0 and fields['recovery_status']=='success', (scenario,p.stdout,p.stderr)
                assert job.read_bytes()==(PKG/'native-reading-time.conf').read_bytes()
                assert len(events)==1 and 'original launch failure' in (events[0]/'before.txt').read_text(encoding='utf-8', errors='replace')
                assert 'initial_status='+('stopped' if scenario=='stopped' else 'config_missing') in (events[0]/'before.txt').read_text(encoding='utf-8', errors='replace')
                assert (fx/'mounts').read_text(encoding='utf-8', errors='replace').split()[3].startswith('rw' if scenario=='rw-restore-config' else 'ro')
                before=calls; q,new=call(base,env)
                after=(fx/'calls').read_text(encoding='utf-8', errors='replace'); assert q.returncode==0 and after.count('start native')==before.count('start native')
            elif scenario=='write-error':
                assert p.returncode==0 and fields['timing_status']=='write_error' and fields['category']=='D'
                assert 'start native' not in calls
            else:
                assert p.returncode!=0,(scenario,p.stdout,p.stderr)
                assert 'start native' not in calls or scenario=='start-failure'
            if scenario!='write-error': assert fields.get('timing_status')=='unverified'
            for e in events:
                assert sum(f.stat().st_size for f in e.iterdir())<=128*1024
            REPORT.append({'variant':variant,'scenario':scenario,'result':'PASS'})

# An occupied/unowned event path cannot be overwritten by snapshot EXIT.
with tempfile.TemporaryDirectory(prefix='service-unowned-',dir=OUT) as name:
    folder=Path(name);base,upstart,env=setup(folder,running=False)
    event=base/'service-events/event-0';event.mkdir(parents=True)
    (event/'after.txt').write_bytes(b'user-owned sentinel')
    p,f=call(base,env,'snapshot');assert p.returncode!=0
    assert (event/'after.txt').read_bytes()==b'user-owned sentinel'
    assert sorted(x.name for x in event.iterdir())==['after.txt']
    REPORT.append({'scenario':'unowned event directory preserved','result':'PASS'})

# Active lifecycle owner rejects concurrent ensure without touching the service.
with tempfile.TemporaryDirectory(prefix='service-concurrent-',dir=OUT) as name:
    folder=Path(name);base,upstart,env=setup(folder,running=False)
    lib=(base/'compat/lifecycle.sh').as_posix()
    holder=subprocess.Popen([SH,'-c',f'. "{lib}"; rr_lock || exit; echo acquired; /bin/sleep 3; rr_unlock'],env=env,stdout=subprocess.PIPE,text=True)
    assert holder.stdout.readline().strip()=='acquired'
    results=[subprocess.Popen([SH,(base/'bin/service-manager.sh').as_posix(),'ensure'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(3)]
    for process in results:
        out,err=process.communicate(timeout=5); assert process.returncode==75 and 'recovery_status=busy' in out,(out,err)
    holder.wait(timeout=5)
    p,fields=call(base,env);assert p.returncode==0
    assert (folder/'fixture/calls').read_text(encoding='utf-8', errors='replace').count('start native')==1
    REPORT.append({'scenario':'concurrent lifecycle owners','result':'PASS'})

# Stale lock, bounded query, evidence ring and mount restoration failures.
with tempfile.TemporaryDirectory(prefix='service-limits-',dir=OUT) as name:
    folder=Path(name);base,upstart,env=setup(folder,running=False);fx=folder/'fixture'
    lock=Path(env['READING_LIFECYCLE_LOCK']);lock.mkdir();(lock/'owner').write_bytes(b'99999999 123\n')
    p,f=call(base,env);assert p.returncode==0,(p.stdout,p.stderr)
    for n in range(7):
        (fx/'running').unlink(missing_ok=True); (fx/'proc/123/cmdline').write_bytes(b''); p,f=call(base,env);assert p.returncode==0
    assert len(list((base/'service-events').glob('event-*')))==5
    (fx/'query-hang').touch();started=time.monotonic();p,f=call(base,env,'status');elapsed=time.monotonic()-started
    assert p.returncode!=0 and elapsed<4.5,(elapsed,p.stdout,p.stderr)
    (fx/'query-hang').unlink(); (upstart/'native-reading-time.conf').unlink(); (fx/'restore-fail').touch()
    p,f=call(base,env);assert p.returncode!=0 and 'mount_restore_failed' in p.stdout
    assert list((base/'service-events').glob('event-*/mount.txt'))
    REPORT.append({'scenario':'stale lock, rotation, timeouts, failed restoration','result':'PASS','query_seconds':round(elapsed,3)})

# Deferred launch must retain the original log before the UI initializes it.
with tempfile.TemporaryDirectory(prefix='service-launch-',dir=OUT) as name:
    folder=Path(name);base,upstart,env=setup(folder,running=False)
    (base/'touch-last.log').write_bytes(b'original touch failure\n')
    p,f=call(base,env,'launch'); assert p.returncode==0
    (base/'launch-last.log').write_bytes(b'new UI log initialization\n')
    (base/'touch-last.log').write_bytes(b'new touch log initialization\n')
    deadline=time.monotonic()+14
    while time.monotonic()<deadline and not (base/'service-status.txt').exists(): time.sleep(.05)
    snapshots=list((base/'service-events').glob('event-*/before.txt'))
    assert snapshots and any('original launch failure' in q.read_text(encoding='utf-8') and 'original touch failure' in q.read_text(encoding='utf-8') for q in snapshots)
    assert (folder/'fixture/calls').read_text(encoding='utf-8').count('start native')==1
    # Allow the bounded worker to release its lock and clean its evidence buffer.
    while time.monotonic()<deadline and Path(env['READING_LIFECYCLE_LOCK']).exists(): time.sleep(.05)
    assert not list(base.glob('.service-before-launch.*'))
    REPORT.append({'scenario':'async evidence precedes launch log reset','result':'PASS'})

# Execute production daemon unchanged, with deterministic time and LIPC inputs.
def timing_case(mode):
    with tempfile.TemporaryDirectory(prefix='timing-',dir=OUT) as name:
        base=Path(name)/'reading-time';base.mkdir()
        source=(PKG/'native-reading-time-daemon.sh').read_text(encoding='utf-8').replace('/mnt/us/reading-time',base.as_posix())
        if mode=='write-failure': (base/'reading-time.tsv').mkdir()
        prelude='''export PATH=/usr/bin:/bin
loops=0
lipc-get-prop() {
case "$2" in
 activeApp) [ "$mode" != state-failure ] || return 7; [ "$loops" -lt 4 ] && echo com.lab126.booklet.reader || echo com.lab126.home;;
 state) [ "$mode" != locked ] && echo active || echo screenSaver;;
 activeContext) if [ "$mode" = switch ] && [ "$loops" -ge 2 ]; then echo file:///mnt/us/documents/Book_BBBB.kfx; else echo file:///mnt/us/documents/Book_AAAA.kfx; fi;;
 getCurrentBookMetadata) if [ "$mode" = switch ] && [ "$loops" -ge 2 ]; then echo '{"cdeKey":"BBBB"}'; else echo '{"cdeKey":"AAAA"}'; fi;;
esac
}
date() { case "$1" in +%s) echo "$((100+loops*5))";; +%Y-%m-%d) if [ "$mode" = midnight ] && [ "$loops" -ge 2 ]; then echo 2026-10-13; else echo 2026-10-12; fi;; *) echo mock;; esac; }
sleep() { loops=$((loops+1)); [ "$loops" -ge 5 ] && exit 0; return 0; }
'''
        p=subprocess.run([SH],input='mode='+mode+'\n'+prelude+source,env={**os.environ,'PATH':'/usr/bin:/bin'},text=True,encoding="utf-8",errors="replace",capture_output=True,timeout=10)
        if mode=='write-failure':
            assert p.stderr and (base/'reading-time.tsv').is_dir()
            return {'scenario':mode,'result':'PASS','write_failure_observed':True}
        rows=(base/'reading-time.tsv').read_text(encoding='utf-8', errors='replace').splitlines()[1:]
        total=sum(int(row.split('\t')[2]) for row in rows)
        assert total==(0 if mode in ('state-failure','locked') else 17),(mode,total,rows,p.stderr)
        if mode=='switch': assert len({row.split('\t')[1] for row in rows})==2
        if mode=='midnight': assert len({row.split('\t')[0] for row in rows})==2
        return {'scenario':mode,'result':'PASS','actual_tsv_seconds':total}
for scenario in ('reading','switch','midnight','locked','state-failure','write-failure'): REPORT.append(timing_case(scenario))

# Both actual bootstraps must opt out within the upstream six-line header.
header=(ROOT/'v4/bootstrap.template.sh').read_text(encoding='utf-8', errors='replace').splitlines()[:6]
assert '# DontUseFBInk' in header
assert (PKG/'native-reading-time-daemon.sh').read_bytes()==subprocess.check_output(['git','show','982ea7131c81a198997315602a79c684bb4f3d7d:native-reading-time-package/native-reading-time-daemon.sh'],cwd=ROOT)
(OUT/'service-recovery-results.json').write_text(json.dumps({'result':'PASS','checks':REPORT,'hardware_5201':'PENDING','performance_on_kindle':'PENDING'},ensure_ascii=False,indent=2),encoding='utf-8')
print(f'service recovery and actual daemon: PASS ({len(REPORT)} scenarios; hardware 5.20.1 pending)')
