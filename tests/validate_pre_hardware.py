"""Execute pre-hardware faults against production shells; no foreground use."""
from normal_fixture import *
import json
import re
import shlex
import time

checks = []

def passed(name):
    checks.append({'check': name, 'result': 'PASS'})
    print('PASS: ' + name, flush=True)

def launch(d, path=None):
    return subprocess.Popen([d.shell, '-c', 'export PATH="$SIM/mockbin:/usr/bin:/bin:$PATH"; exec "$1" "$2"',
                             'run', d.shell, (path or d.docs / BOOTSTRAP).as_posix()],
                            env=d.env, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def await_file(d, name, process):
    deadline = time.monotonic() + 20
    while not (d.root / name).exists():
        assert process.poll() is None, (process.returncode, d.install_log())
        assert time.monotonic() < deadline, d.calls()
        time.sleep(.02)

def runtime_hashes(d):
    return {p.relative_to(d.us).as_posix(): digest(p) for p in d.us.rglob('*')
            if p.is_file() and 'install-last.log' not in p.name
            and '.install-' not in p.as_posix() and p.name != PAYLOAD}

def no_transaction(d, before):
    assert runtime_hashes(d) == before
    assert (d.root / 'running').exists()
    assert 'service stop' not in d.calls() and 'root rw' not in d.calls()
    assert not (d.docs / 'reading-records-install-cleanup.sh').exists()
    assert (d.docs / BOOTSTRAP).exists() and d.payload.exists()
    d.no_temporary()

# One production parser/gate harness, reused across data fixtures. Full installs
# of the accepted patch structure also execute in validate_install.py.
d = Device()
source = (PKG / 'install.sh').read_text(encoding='utf-8')
gate = source[:source.index('[ -x /sbin/initctl ]')] + '\nexit 0\n'
gate_path = d.root / 'gate.sh'
write(gate_path, d.transform(gate.encode()).decode())
allowed = ['5.19.0', '5.19.1', '5.19.6', '5.19.6.1', '5.19.123.456.789',
           '"5.19.6"', 'Kindle 5.19.6', 'Kindle 5.19.6 (build)',
           'Firmware Version: Kindle 5.19.6', '   Kindle 5.19.6   ',
           'Kindle 5.19.6\n', 'Kindle 5.19.6\r\n']
for text in allowed:
    write(d.etc / 'prettyversion.txt', text)
    d.run(gate_path)
    passed('firmware accepted: ' + repr(text))
for text in ['5.17.1', '5.18.6.1', '5.20.0', '5.190', '5.190.1', '', 'garbage',
             '5.19', '5.19.', '5.19.x', '5.19.6..1', '5.19.6evil', 'evil5.19.6',
             '5.19.6 5.18.1', '5.19.6 5.19.1', '5.19.6,5.20.0',
             '5.19.6/6.1.1', 'Kindle 5.19.6\r\nFirmware 5.20.0']:
    write(d.etc / 'prettyversion.txt', text)
    d.run(gate_path, ok=False)
    passed('firmware rejected: ' + repr(text))
for other, ok in [('Kindle 5.19.6 (51999999)', True), ('Kindle 5.19.1', True), ('5.18.1', True)]:
    d.firmware('5.19.6'); write(d.etc / 'version.txt', other)
    d.run(gate_path, ok=ok)
    passed('firmware primary priority over independent fallback: ' + other)
(d.etc / 'prettyversion.txt').unlink(); write(d.etc / 'version.txt', 'Firmware Version: Kindle 5.19.6.1\r\n')
d.run(gate_path); passed('firmware version.txt fallback with CRLF')
(d.etc / 'version.txt').unlink(); d.firmware('5.19.6')

for width, height in [(1072,1448), (1236,1648), (1264,1680), (1448,1072), (1648,1236), (1680,1264), (1860,2480), (2480,1860)]:
    d.command('fbset', f"echo 'geometry {width} {height} {width} {height} 8'"); d.chmod([d.mock / 'fbset'])
    d.run(gate_path, ok=min(width,height)<1500)
    passed(f'Standard/KS framebuffer gate: {width}x{height}')
d.command('fbset', "echo 'geometry 1264 1680 1264 1680 8'"); d.chmod([d.mock / 'fbset'])
for input_name in ['Wacom', 'STYLUS', 'digitizer', 'Hanvon pen']:
    write(d.sys / 'class/input/event2/device/name', input_name)
    d.run(gate_path, ok=False); passed('pen exclusion: ' + input_name)
(d.sys / 'class/input/event2/device/name').unlink()
for model in ['Kindle Scribe', 'KS', 'Kindle KS']:
    write(d.root / 'var/local/deviceType.txt', model)
    d.run(gate_path, ok=False); passed('model exclusion: ' + model)
write(d.root / 'var/local/deviceType.txt', 'Future Standard Kindle')
for name, value in [('VERSION','9.7.5-ks'), ('PACKAGE_VARIANT','KS'), ('release-info','variant=scribe')]:
    write(d.base / name, value); d.run(gate_path, ok=False)
    (d.base / name).unlink(); passed('existing KS marker exclusion: ' + name)
d.run(gate_path); d.no_temporary(); passed('unknown Standard name accepted without serial allowlist')

# Both filesystems and every malformed df case fail before backups/daemon stop.
for partition in ['tmp', 'us']:
    for mode in ['low', 'failure', 'unavailable', 'empty', 'garbage', 'negative', 'truncated', 'multiple', 'wrong-units']:
        d = Device(); d.seed('9.7.5-test'); before = runtime_hashes(d)
        row = {'low': 'kindle 1048576 1048575 1 100% /',
               'negative': 'kindle 1048576 1024 -1 1% /',
               'truncated': 'kindle 1048576 1024',
               'multiple': 'kindle 1048576 1024 1047552 1% /\nsecond 1048576 1024 1047552 1% /',
               'garbage': 'unparseable df output', 'empty': ''}.get(mode, 'kindle 1048576 1024 1047552 1% /')
        header = 'Filesystem bytes Used Available Capacity Mounted on' if mode == 'wrong-units' else 'Filesystem 1024-blocks Used Available Capacity Mounted on'
        bad = 'exit 127' if mode == 'unavailable' else 'exit 3' if mode == 'failure' else f"printf '%s\\n' '{header}' '{row}'"
        # Per-partition failure is independent of the other partition's fixture.
        target = d.tmp.as_posix() if partition == 'tmp' else d.us.as_posix()
        d.command('df', f'echo "df $*" >> "$SIM/calls"\ncase "$2" in "{target}") {bad};; *) echo "Filesystem 1K-blocks Used Available Use% Mounted on"; echo "kindle 1048576 1024 1047552 1% /";; esac')
        d.chmod([d.mock / 'df']); d.install(ok=False)
        assert '存储空间不足' in d.install_log() and 'toasterMessage 存储空间不足' in d.calls()
        if partition == 'tmp': assert 'service ' not in d.calls()
        no_transaction(d, before); passed(f'preflight {partition}: {mode}')

# A failed du cannot turn a large rollback requirement into a guess of zero.
d = Device(); d.seed('9.7.5-test'); before = runtime_hashes(d)
d.command('du', 'exit 3'); d.chmod([d.mock/'du']); d.install(ok=False)
no_transaction(d, before); passed('preflight unknown backup/payload size fails safe')

# If storage cannot even create/open the log, there is no writable log target.
# Still show an explicit toaster, release the install lock, and preserve runtime.
for shell,mode in [(shell,mode) for shell in (SH,DASH) for mode in ['log-directory-failure','log-open-failure']]:
    d=Device(shell);d.seed('9.7.5-test')
    if mode=='log-directory-failure':
        d.command('mkdir', f'case "$1:$2" in "-p:{d.base.as_posix()}") exit 9;; esac\nexec /usr/bin/mkdir "$@"')
        d.chmod([d.mock/'mkdir'])
    else:(d.base/'install-last.log').mkdir()
    before=runtime_hashes(d);d.install(ok=False)
    assert 'toasterMessage 存储空间不足' in d.calls()
    no_transaction(d,before);passed(Path(shell).name+': preflight preserves runtime when '+mode)

def block_unpack(d):
    d.flag('block-unpack')
    d.command('tar', r'''case "$1" in -xf)
echo ready > "$SIM/unpacking"
while [ -f "$SIM/block-unpack" ]; do /usr/bin/sleep .02; done;; esac
exec /usr/bin/tar "$@"''')
    d.chmod([d.mock/'tar'])

for stale in [False, True]:
    d = Device(); d.seed('9.7.5-test')
    if stale: (d.tmp/'reading-records-9.7.6-install.lock/owner.99999999').mkdir(parents=True)
    block_unpack(d); a = launch(d)
    await_file(d, 'unpacking', a)
    before = runtime_hashes(d); log = d.install_log(); tmp = sorted(str(p) for p in d.tmp.rglob('*'))
    d.install(ok=False)
    assert 'toasterMessage 安装正在进行' in d.calls()
    assert d.install_log() == log and runtime_hashes(d) == before
    assert sorted(str(p) for p in d.tmp.rglob('*')) == tmp
    assert 'service stop' not in d.calls() and not list(d.base.glob('.install-*'))
    d.unflag('block-unpack'); assert a.wait(timeout=30)==0, d.install_log()
    assert d.calls().count('service stop native-reading-time')==1
    d.no_temporary(); passed('double-click excludes log/unpack/transaction' + (' after stale lock' if stale else ''))

for mode in ['empty', 'dead-owner']:
    d = Device()
    lock = d.tmp/'reading-records-9.7.6-install.lock'; lock.mkdir()
    if mode == 'dead-owner': (lock/'owner.99999999').mkdir()
    d.install(); d.no_temporary(); passed('stale installer lock recovered: ' + mode)

# Stop A between root mkdir and owner mkdir, let B reclaim the empty lock.
# A must not erase B's claim/log/tmp when it resumes into the new directory.
d = Device(); d.flag('pause-owner'); d.flag('arm-owner'); block_unpack(d)
d.command('mkdir', r'''/usr/bin/mkdir "$@" || exit $?
case "$1" in */reading-records-9.7.6-install.lock)
if [ -f "$SIM/arm-owner" ]; then
rm -f "$SIM/arm-owner"; echo ready > "$SIM/owner-gap"
while [ -f "$SIM/pause-owner" ]; do /usr/bin/sleep .02; done
fi;; esac'''); d.chmod([d.mock/'mkdir'])
a=launch(d); await_file(d,'owner-gap',a)
b=launch(d); await_file(d,'unpacking',b)
log=d.install_log(); owners=list((d.tmp/'reading-records-9.7.6-install.lock').iterdir())
d.unflag('pause-owner'); assert a.wait(timeout=10)!=0
assert d.install_log()==log and list((d.tmp/'reading-records-9.7.6-install.lock').iterdir())==owners
d.unflag('block-unpack'); assert b.wait(timeout=30)==0,d.install_log()
d.no_temporary(); passed('empty-lock ownership race never admits two installers or releases winner lock')

for signal in ['INT','TERM','HUP']:
    for point in ['before-owner','after-owner']:
        d=Device(); path=d.docs/BOOTSTRAP
        text=path.read_text(encoding='utf-8')
        needle='mkdir "$INSTALL_OWNER" 2>/dev/null || fail'
        text=text.replace(needle, ('kill -'+signal+' "$$"\n' if point=='before-owner' else '')+needle)
        if point=='after-owner':text=text.replace('# A contender', 'kill -'+signal+' "$$"\n# A contender')
        write(path,text); d.install(ok=False); d.no_temporary()
        # Install again with an untouched bootstrap: cancellation isn't stale.
        d.prepare_payload(); d.install(); d.no_temporary()
        passed('installer lock signal release: '+signal+' '+point)

def lock_harness(d):
    helper=d.transform((PKG/'runtime-lock.sh').read_bytes()).decode()
    path=d.root/'shared-lock.sh'
    write(path, f'#!/bin/sh\nLOCK="{d.tmp.as_posix()}/reading-records-ui.lock"\nLOCK_OWNED=0\n'+helper+r'''
trap release_runtime_lock EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
acquire_runtime_lock || exit 1
: > "$LOCK_OWNER/ui-start"
echo ready > "$SIM/acquired-$LOCK_LABEL"
while [ -f "$SIM/block-$LOCK_LABEL" ]; do /usr/bin/sleep .02; done
''')
    return path

for mode in ['empty','dead-owner-markers','dead-owner-empty-pid','legacy-dead-pid']:
    d=Device();d.env['LOCK_LABEL']='A';path=lock_harness(d)
    lock=d.tmp/'reading-records-ui.lock';lock.mkdir()
    if mode.startswith('dead-owner'):
        write(lock/'owner.99999999/ui-start','');write(lock/'owner.99999999/ui-cancel','')
        if mode=='dead-owner-empty-pid':write(lock/'pid','')
    if mode=='legacy-dead-pid':
        write(lock/'pid','99999999');write(lock/'ui-start','');write(lock/'ui-cancel','')
    d.run(path);d.no_temporary();passed('shared UI/installer stale lock: '+mode)

for shell in (SH,DASH):
    d=Device(shell);d.env['LOCK_LABEL']='A';d.flag('block-A');path=lock_harness(d)
    a=launch(d,path);await_file(d,'acquired-A',a)
    before={str(p):digest(p) for p in d.tmp.rglob('*') if p.is_file()}
    d.env['LOCK_LABEL']='B';d.run(path,ok=False)
    assert {str(p):digest(p) for p in d.tmp.rglob('*') if p.is_file()}==before
    d.unflag('block-A');assert a.wait(timeout=10)==0;d.no_temporary()
    passed(Path(shell).name+': shared active owner blocks contender without touching handoff files')

# Delay the stale reaper just before deleting legacy PID files. The claimant's
# directory must already exclude B, preventing the old rm/rmdir/mkdir ABA race.
d=Device();d.env['LOCK_LABEL']='A';path=lock_harness(d);d.flag('pause-reaper');d.flag('arm-reaper')
write(d.tmp/'reading-records-ui.lock/pid','99999999')
d.command('rm', r'''case "$1:$2" in -f:*/reading-records-ui.lock/pid)
if [ -f "$SIM/arm-reaper" ]; then
/usr/bin/rm -f "$SIM/arm-reaper"; echo ready > "$SIM/reaper-gap"
while [ -f "$SIM/pause-reaper" ]; do /usr/bin/sleep .02; done
fi;; esac
exec /usr/bin/rm "$@"''');d.chmod([d.mock/'rm'])
a=launch(d,path);await_file(d,'reaper-gap',a)
before={str(p):digest(p) for p in d.tmp.rglob('*') if p.is_file()}
d.env['LOCK_LABEL']='B';d.run(path,ok=False)
assert {str(p):digest(p) for p in d.tmp.rglob('*') if p.is_file()}==before
d.unflag('pause-reaper');assert a.wait(timeout=10)==0;d.no_temporary()
passed('shared dead-PID cleanup race cannot steal a new UI/transaction owner')

# Every destructive cleanup target is a fixed constant, including helper arms.
cleanup=(PKG/'resources/reading-records-install-cleanup.sh').read_text(encoding='utf-8')
whitelist=(PKG/'cleanup-manifest.txt').read_text(encoding='utf-8').splitlines()
lexer=shlex.shlex(cleanup, posix=True, punctuation_chars=True); lexer.whitespace_split=True
tokens=list(lexer); targets=[]
for index, token in enumerate(tokens):
    if token != 'rm': continue
    flag,target=tokens[index+1:index+3]
    assert flag in ['-f','-rf'] and target.startswith('/mnt/us/')
    assert not any(c in target for c in '$*?[]`') and '..' not in Path(target).parts
    assert target not in ['/mnt/us','/mnt/us/documents','/mnt/us/reading-time']
    assert not target.startswith('/mnt/us/reading-time/')
    assert tokens[index+3] in ['||',';;',';'], tokens[index:index+6]
    targets.append(target)
assert set(targets)==set(whitelist)|{'/mnt/us/documents/reading-records-install-cleanup.sh'}
assert len(targets)==len(set(targets))==len(whitelist)+1
original=subprocess.check_output(['git','show','93b6e79:native-reading-time-package/cleanup-manifest.txt'],cwd=ROOT).decode('utf-8').splitlines()
assert len(original)==33 and set(whitelist)==set(original)|{'/mnt/us/documents/reading-records-9.7.6-data.tar'}
passed('destructive cleanup audit: all original 33 paths plus ASCII payload, 35 literal rm targets including self')

for parent in ['extensions','v4','documents']:
    d=Device(); write(d.base/'VERSION','9.7.6-5.19-normal'); write(d.base/'activation-verified','verified')
    write(d.base/'reading-records-installer/user-data','must survive'); write(d.base/'cleanup.sh','user data')
    if parent=='documents':shutil.move(str(d.docs),str(d.root/'saved-documents'))
    alias=d.us/parent
    try:
        os.symlink(d.base,alias,target_is_directory=True)
    except OSError:
        assert os.name=='nt'
        # MSYS treats a native directory junction as -L; this requires no
        # symlink privilege and exercises a real alias rather than mocking test.
        subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',
                        f"New-Item -ItemType Junction -Path '{alias}' -Target '{d.base}' | Out-Null"],check=True,capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    subprocess.run([SH,'-c','[ -L "$1" ]','alias',alias.as_posix()],env=d.env,check=True,capture_output=True)
    path=d.root/'cleanup.sh';write(path,d.transform(cleanup.encode()).decode())
    before={str(p):digest(p) for p in d.base.rglob('*') if p.is_file()}
    d.run(path,ok=False)
    assert {str(p):digest(p) for p in d.base.rglob('*') if p.is_file()}==before
    if alias.is_symlink():alias.unlink()
    else:alias.rmdir()  # Removes only the junction, never the target directory.
    passed('cleanup rejects parent alias into reading-time: '+parent)

# Real staging/atomic publication/rollback with injected filesystem/service errors.
recovery_modes=['rollback-copy','rollback-move','rollback-release-move','rollback-release-rm',
                'rollback-remove-new','rollback-full','rollback-missing-backup','rollback-reload','rollback-start','rollback-root-ro','stop-status-failure',
                'rollback-journal-missing','rollback-journal-truncated','rollback-journal-read-error']
for mode in ['publish-release','publish-service','snapshot-full','stop-failure',*recovery_modes]:
    d=Device();d.seed('9.7.5-test');d.flag('fault-armed')
    if mode=='rollback-journal-read-error':
        # Model a read returning failure after its first successful record,
        # while the journal bytes remain intact (digest alone cannot catch it).
        buffer=io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(d.original_tar)) as src, tarfile.open(fileobj=buffer,mode='w',format=tarfile.USTAR_FORMAT) as dst_tar:
            for member in src.getmembers():
                raw=src.extractfile(member).read()
                if member.name.endswith('/install.sh'):
                    raw=raw.replace(b'rollback() {',b'''read() {
    case "${1:-}:${2:-}:${3:-}:${4:-}" in '-r:slot:dst:had_file')
        rollback_read_calls=$((${rollback_read_calls:-0}+1))
        [ "$rollback_read_calls" -le 1 ] || return 1;;
    esac
    command read "$@"
}
rollback() {''')
                member.size=len(raw);dst_tar.addfile(member,io.BytesIO(raw))
        d.original_tar=buffer.getvalue();d.prepare_payload()
    if mode!='rollback-remove-new':write(d.base/'releases/9.7.6-5.19-normal/old-marker','original release')
    before=d.preserved(); old_daemon=digest(d.base/'bin/native-reading-time-daemon.sh')
    mv_body=r'''echo "mv $*" >> "$SIM/fs-calls"
case "$1:$2" in
 */.install-*/release:*/releases/9.7.6-5.19-normal)
    if [ "$FAULT_MODE" = publish-release ] && [ -f "$SIM/fault-armed" ]; then
        rm -f "$SIM/fault-armed"; /usr/bin/mkdir -p "$2"; echo partial > "$2/partial"; exit 9
    fi;;
 *.new.*:*/documents/reading-records.sh)
    case "$FAULT_MODE" in rollback-*|stop-failure)
        if [ -f "$SIM/fault-armed" ]; then rm -f "$SIM/fault-armed"; : > "$SIM/in-rollback"; exit 9; fi;; esac;;
 *.new.*:*/upstart/native-reading-time.conf)
    if [ "$FAULT_MODE" = publish-service ] && [ -f "$SIM/fault-armed" ]; then rm -f "$SIM/fault-armed"; exit 9; fi;;
 *.rollback.*:*) if [ "$FAULT_MODE" = rollback-move ] && [ -f "$SIM/in-rollback" ]; then rm -f "$SIM/in-rollback"; exit 9; fi;;
 */old-release:*) if [ "$FAULT_MODE" = rollback-release-move ]; then exit 9; fi;;
esac
exec /usr/bin/mv "$@"'''
    cp_body=r'''echo "cp $*" >> "$SIM/fs-calls"
case "$*" in
 *'/backup/'*)
   if [ "$FAULT_MODE" = snapshot-full ] && [ -f "$SIM/fault-armed" ]; then echo 'No space left on device' >&2; exit 9; fi;;
esac
case "$*" in
 *'.rollback.'*)
    if [ "$FAULT_MODE" = rollback-full ]; then echo 'No space left on device' >&2; exit 9; fi
    if [ "$FAULT_MODE" = rollback-copy ] && [ -f "$SIM/in-rollback" ]; then rm -f "$SIM/in-rollback"; exit 9; fi;;
esac
exec /usr/bin/cp "$@"'''
    rm_body=r'''echo "rm $*" >> "$SIM/fs-calls"
case "$*" in *'/releases/9.7.6-5.19-normal')
case "$FAULT_MODE" in rollback-release-rm|rollback-remove-new) if [ -f "$SIM/in-rollback" ]; then exit 9; fi;; esac;; esac
exec /usr/bin/rm "$@"'''
    d.env['FAULT_MODE']=mode
    for name,body in [('mv',mv_body),('cp',cp_body),('rm',rm_body)]:d.command(name,body)
    init=(d.mock/'initctl').read_text(encoding='utf-8')
    init=init.replace('stop) rm -f', '''stop)
if [ "$FAULT_MODE" = stop-failure ]; then exit 9; fi
if [ "$FAULT_MODE" = rollback-missing-backup ] && [ -f "$SIM/in-rollback" ]; then
    /usr/bin/rm -f "$SIM/us/reading-time"/.install-*/backup/1
fi
if [ -f "$SIM/in-rollback" ]; then
    for journal in "$SIM/us/reading-time"/.install-*/journal; do
        case "$FAULT_MODE" in
            rollback-journal-missing) /usr/bin/rm -f "$journal";;
            rollback-journal-truncated) head -n 1 "$journal" > "$SIM/journal-prefix"; /usr/bin/cp "$SIM/journal-prefix" "$journal";;
        esac
    done
fi
rm -f''')
    init=init.replace('status) if', 'status) if [ "$FAULT_MODE" = stop-status-failure ] && [ -f "$SIM/stop-requested" ]; then exit 3; fi; if')
    init=init.replace('stop)\n', 'stop)\n: > "$SIM/stop-requested"\n')
    init=init.replace('reload-configuration) [', '''reload-configuration)
if [ "$FAULT_MODE" = rollback-reload ] && [ -f "$SIM/in-rollback" ]; then exit 9; fi
[''')
    init=init.replace('start)\n', 'start)\n   if [ "$FAULT_MODE" = rollback-start ]; then exit 9; fi\n')
    write(d.mock/'initctl',init)
    if mode=='rollback-root-ro':d.flag('fail-root-ro')
    d.chmod([d.mock/name for name in ['mv','cp','rm','initctl']])
    d.install(ok=False);assert d.preserved()==before and 'SUCCESS' not in d.install_log()
    assert (d.docs/BOOTSTRAP).exists() and d.payload.exists()
    assert not (d.docs/'reading-records-install-cleanup.sh').exists()
    assert not list(d.tmp.iterdir()),list(d.tmp.iterdir())
    if mode in recovery_modes or mode=='stop-failure':
        stages=list(d.base.glob('.install-*'));assert len(stages)==1,d.install_log()
        stage=stages[0];assert 'RECOVERY_REQUIRED snapshot='+stage.as_posix() in d.install_log()
        assert (stage/'backup').is_dir()
        assert (stage/'journal').is_file()==(mode!='rollback-journal-missing')
        if mode in ['rollback-release-move','rollback-release-rm']:
            assert (stage/'old-release/old-marker').read_text().strip()=='original release'
            assert not (d.base/'releases/9.7.6-5.19-normal/old-release').exists()
        if mode not in ['rollback-missing-backup']:assert digest(stage/'backup/1')==old_daemon
        if mode not in ['stop-failure']:assert not (d.root/'running').exists()
    else:
        d.no_temporary();assert digest(d.base/'bin/native-reading-time-daemon.sh')==old_daemon
        assert (d.root/'running').exists()
        if mode=='snapshot-full':assert 'service stop' not in d.calls()
    passed('transaction/recovery fault: '+mode)

# History evidence: "sessions" in b344986 is runtime/transaction ownership only.
protected=['native-reading-time-daemon.sh','native-reading-time.conf','reading-insights-cache.awk',
           'reading-insights-touch-ui.lua','reading-insights-touch.lua']
for name in protected:
    path='native-reading-time-package/'+name
    baseline=subprocess.check_output(['git','show','e417074:'+path],cwd=ROOT)
    assert (PKG/name).read_bytes()==baseline
    assert not subprocess.check_output(['git','diff','b344986^','b344986','--',path],cwd=ROOT)
for name in ['runtime-child.sh','阅读记录-optimized.sh','阅读记录.sh']:
    path='native-reading-time-package/'+name
    assert (PKG/name).read_bytes()==subprocess.check_output(['git','show','93b6e79:'+path],cwd=ROOT)
    active='\n'.join(line for line in (PKG/name).read_text(encoding='utf-8').splitlines() if not line.lstrip().startswith('#'))
    assert not re.search(r'EVIOCGRAB|power.?button|power.?key|kill[^\n]*powerd',active,re.I)
launch_source=(PKG/'launch.sh').read_text(encoding='utf-8')
old_launch=subprocess.check_output(['git','show','93b6e79:native-reading-time-package/launch.sh'],cwd=ROOT).decode('utf-8')
# Only the lock release/handoff paths change inside cleanup; LIPC order/flags
# and all geometry/property/startup logic after lock acquisition are identical.
def cleanup_body(text):return text[text.index('cleanup_runtime_state()'):text.index('on_signal()')]
expected=cleanup_body(old_launch).replace('rm -f "$LOCK/pid" "$LOCK/ui-start" "$LOCK/ui-cancel"; rmdir "$LOCK" 2>/dev/null || true;', 'release_runtime_lock;')
expected=expected.replace('$LOCK/ui-', '$LOCK_OWNER/ui-')
assert cleanup_body(launch_source)==expected
start='[ -r "$MAIN" ]';end='UI_ENTERED=1'
assert launch_source[launch_source.index(start):launch_source.index(end)]==old_launch[old_launch.index(start):old_launch.index(end)]
active='\n'.join(line for line in launch_source.splitlines() if not line.lstrip().startswith('#'))
assert not re.search(r'EVIOCGRAB|power.?button|power.?key|kill[^\n]*powerd',active,re.I)
passed('b344986/runtime baseline evidence: tracker, TSV, AWK, touch, UI and power-key behavior unchanged')

write(OUT/'pre-hardware-results.json',json.dumps({'result':'PASS','checks':checks,'case_count':len(checks),
      'limits':['Hardware capacity/LIPC/input behavior simulated; real shell/filesystem/archives exercised.']},ensure_ascii=False,indent=2))
