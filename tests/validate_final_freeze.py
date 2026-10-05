"""Narrow freeze audit: production sh/dash, mocked Kindle commands; no hardware."""
from normal_fixture import *
import json
import re
import time

checks = []


def passed(name):
    checks.append({'check': name, 'result': 'PASS'})
    print('PASS: ' + name, flush=True)


def spawn(d, path):
    return subprocess.Popen([d.shell, '-c',
        'export PATH="$SIM/mockbin:/usr/bin:/bin:$PATH"; exec "$1" "$2"',
        'run', d.shell, path.as_posix()], env=d.env, cwd=ROOT,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def await_file(d, name, process):
    until = time.monotonic() + 20
    while not (d.root / name).exists():
        assert process.poll() is None, (process.returncode, d.install_log(), d.calls())
        assert time.monotonic() < until, d.calls()
        time.sleep(.02)


def runtime_bytes(d):
    paths = [d.etc / 'upstart/native-reading-time.conf', *d.base.rglob('*'),
             d.docs / 'reading-records.sh', d.docs / 'reading-records-install-cleanup.sh',
             d.docs / '阅读记录.sh']
    return {p.as_posix(): digest(p) for p in paths if p.is_file()
            and '.install-' not in p.as_posix()
            and p.name not in {'install-last.log', 'dashboard-launch.log', 'state.tsv', 'upstart.log'}}


installed_templates = {}


def ready(shell=SH):
    # Reuse a verified installation for starting state; each fault still runs
    # its own complete production repair transaction and rollback.
    if shell not in installed_templates:
        template = Device(shell); template.seed('9.7.5-test'); template.install()
        template.no_temporary(); installed_templates[shell] = template
    template = installed_templates[shell]
    d = Device(shell)
    for src, dst in [(template.base, d.base), (template.docs, d.docs),
                     (template.etc / 'upstart', d.etc / 'upstart')]:
        shutil.copytree(src, dst, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(BOOTSTRAP, PAYLOAD) if src == template.docs else None)
        for path in dst.rglob('*'):
            if path.is_file() and path.suffix in ['.sh', '.conf', '.tsv', '.txt']:
                path.write_bytes(path.read_bytes().replace(template.root.as_posix().encode(), d.root.as_posix().encode()))
    d.flag('running')
    return d


# Execute the actual firmware gate, not a Python reimplementation.
source = (PKG / 'install.sh').read_text(encoding='utf-8')
for shell in (SH, DASH):
    d = Device(shell)
    gate = d.root / 'gate.sh'
    write(gate, d.transform((source[:source.index('[ -x /sbin/initctl ]')] + '\nexit 0\n').encode()).decode())
    for primary, fallback, ok, expected in [
        ('Kindle 5.19.6', '5.18.1', True, '5.19.6'),
        ('Kindle 5.19.6', '5.19.1 5.20.0', True, '5.19.6'),
        ('garbage', '5.19.6.1', True, '5.19.6.1'),
        (None, '5.19.0', True, '5.19.0'),
        ('', '5.19.1', True, '5.19.1'),
        ('5.19.6 5.19.1', '5.19.6', False, None),
        ('5.19.6 5.18.1', '5.19.6', False, None),
        ('garbage', '5.19.6 5.19.1', False, None),
        (None, 'garbage', False, None),
        ('5.18.1', '5.19.6', False, None),
        ('5.20.0', '5.19.6', False, None),
        ('5.190.1', '5.19.6', False, None),
        ('5.19.6 5.19.6', None, True, '5.19.6'),
        ('5.19.6.1.2.3.4', None, True, '5.19.6.1.2.3.4'),
    ]:
        for name, text in [('prettyversion.txt', primary), ('version.txt', fallback)]:
            path = d.etc / name
            if text is None: path.unlink(missing_ok=True)
            else: write(path, text)
        # Print the selected version from the production gate for positive cases.
        text = d.transform((source[:source.index('[ -x /sbin/initctl ]')] + '\nprintf "selected=%s\\n" "$firmware"\nexit 0\n').encode()).decode()
        write(gate, text)
        result = d.run(gate, ok=ok)
        if ok: assert 'selected=' + expected in result.stdout.splitlines()
        d.no_temporary()
        passed(Path(shell).name + ': primary/fallback ' + repr((primary, fallback)))
    # Unreadable is injected as cat failure, even when the host runs as admin.
    write(d.etc / 'prettyversion.txt', '5.19.6'); write(d.etc / 'version.txt', '5.19.1')
    d.command('cat', 'case "$1" in */prettyversion.txt) exit 3;; esac\nexec /usr/bin/cat "$@"')
    d.chmod([d.mock / 'cat']); result = d.run(gate)
    assert 'selected=5.19.1' in result.stdout.splitlines()
    passed(Path(shell).name + ': unreadable primary falls back')

# Only one exact job's positive PID can be remembered (no trailing/multiline
# output or an unrelated job masquerading as the owned service).
d = Device(DASH); path = d.root / 'service-pid.sh'
pid_helper = source[source.index('remember_daemon_pid()'):source.index('verify_running_daemon()')]
write(path, '#!/bin/sh\n' + pid_helper + '\nremember_daemon_pid "$(cat "$SIM/job-status")"\n')
for status, ok in [('native-reading-time start/running, process 123', True),
                   ('other-job start/running, process 123', False),
                   ('native-reading-time start/running, process 123\nother-job start/running, process 987', False),
                   ('native-reading-time start/running, process 0', False),
                   ('native-reading-time start/running, process -123', False),
                   ('native-reading-time start/running, process 123 extra', False)]:
    write(d.root / 'job-status', status); d.run(path, ok=ok)
passed('service PID parser accepts only one exact owned job and positive PID')

# Run both production df parsers with alternate BusyBox/POSIX headers and
# unsupported layouts. Filesystem/mount spaces must never shift numeric fields.
for location in ['tmp', 'us']:
    text = (ROOT / 'documents' / BOOTSTRAP).read_text(encoding='utf-8') if location == 'tmp' else source
    parser = re.search(r"printf '%s\\n' \"\$space\" \| awk -v need=([^\n]+)\n(.*?)' \|\| fail", text, re.S).group(2)
    d = Device(DASH); path = d.root / 'df-parser.sh'
    write(path, "#!/bin/sh\nspace=$(cat \"$SIM/df-output\")\nprintf '%s\\n' \"$space\" | awk -v need=100 '" + parser + "'\n")
    for header, row, ok in [
        ('Filesystem 1K-blocks Used Available Use% Mounted on', 'kindle 1000 10 990 1% /', True),
        ('Filesystem 1024-blocks Used Available Capacity Mounted on', '  kindle\t1000  10\t990  1%  /', True),
        ('Filesystem 1K-blocks Used Available Use% Mounted on', 'kindle name 1000 10 990 1% /', False),
        ('Filesystem 1K-blocks Used Available Use% Mounted on', 'kindle 1000 10 990 1% /mount name', False),
        ('Filesystem 1K-blocks Used Available Use% Mounted on', 'kindle\n 1000 10 990 1% /', False),
        ('Filesystem 1K-blocks Used Available Use% Mounted on', 'kindle 1000 10 99 1% /', False),
        ('Filesystem 1K-blocks Used Available Use% Mounted on', 'kindle 1000 10 nope 1% /', False),
    ]:
        write(d.root / 'df-output', header + '\n' + row + '\n'); d.run(path, ok=ok)
        passed('df ' + location + ': ' + repr(row))

# Production du helper: real host du and malformed/failing fixtures.
d = Device(DASH); path = d.root / 'du-helper.sh'
helper = source[source.index('disk_kib()'):source.index('payload_kib=')]
write(path, '#!/bin/sh\n' + helper + '\ndisk_kib "$SIM/du-target"\n')
target = d.root / 'du-target'; target.mkdir()
d.run(path); passed('du -sk: real empty directory')
write(target / 'file', 'payload' * 1000); d.run(path); passed('du -sk: real ordinary directory')
shutil.rmtree(target); d.run(path, ok=False); passed('du -sk: missing directory rejected')
for output, code, ok in [('  24\t/path with spaces  ', 0, True), ('0\t/empty', 0, True),
                         ('nonnumeric\t/path', 0, False), ('-1\t/path', 0, False),
                         ('24\t/path\n12\t/extra', 0, False), ('24\t/path', 3, False)]:
    d.command('du', "printf '%s\\n' '" + output + "'\nexit " + str(code)); d.chmod([d.mock / 'du'])
    d.run(path, ok=ok); passed('du -sk fixture: ' + repr((output, code)))

# Execute production tar fallback, with capabilities mocked (not BusyBox tar).
boot_source = (ROOT / 'documents' / BOOTSTRAP).read_text(encoding='utf-8')
tar_helper = boot_source[boot_source.index('tar_run()'):boot_source.index('tar_run -tf')]
for mode in ['system-success', 'system-failure', 'system-missing', 'both-fail']:
    d = Device(DASH)
    with tarfile.open(d.root / 'tiny.tar', 'w', format=tarfile.USTAR_FORMAT) as t:
        m = tarfile.TarInfo('file'); m.size = 4; t.addfile(m, io.BytesIO(b'data'))
    (d.root / 'extracted').mkdir()
    d.command('tar', 'echo system >> "$SIM/tar-calls"\n' +
              ('exec /usr/bin/tar "$@"' if mode == 'system-success' else 'exit 9'))
    d.command('busybox', 'echo fallback >> "$SIM/tar-calls"\n' +
              ('exit 9' if mode == 'both-fail' else 'shift; exec /usr/bin/tar "$@"'))
    d.chmod([d.mock / 'tar', d.mock / 'busybox'])
    path = d.root / 'tar-helper.sh'
    capability = 'command() { case "$1:$2" in -v:tar) return 1;; -v:busybox) return 0;; *) return 2;; esac; }\n' if mode == 'system-missing' else ''
    write(path, '#!/bin/sh\n' + capability + tar_helper +
          '\ntar_run -tf "$SIM/tiny.tar" || exit 1\ntar_run -xf "$SIM/tiny.tar" -C "$SIM/extracted"\n')
    d.run(path, ok=mode != 'both-fail')
    if mode != 'both-fail': assert (d.root / 'extracted/file').read_bytes() == b'data'
    calls = (d.root / 'tar-calls').read_text()
    if mode == 'system-success': assert 'fallback' not in calls
    if mode == 'system-missing': assert 'system' not in calls
    passed('production tar capability/fallback (mock BusyBox): ' + mode)
for raw in [b'', b'POSIX\x00\xff\nchecksum']:
    assert cksum(raw) == python_cksum(raw)
    passed('POSIX cksum host execution vs builder CRC: ' + repr(raw))

# Canonical lock helper is embedded so UI never sources replacing release files.
launch_source = (PKG / 'launch.sh').read_text(encoding='utf-8')
helper = (PKG / 'runtime-lock.sh').read_text(encoding='utf-8').split('\n', 1)[1]
assert launch_source.split('# BEGIN runtime-lock.sh\n', 1)[1].split('# END runtime-lock.sh', 1)[0] == helper
assert '. "$RELEASE/' not in launch_source
assert launch_source.index('installer_busy &&') < launch_source.index('acquire_runtime_lock ||') < launch_source.index('[ -r "$MAIN" ]')
assert source.index('acquire_runtime_lock ||') < source.index('mkdir "$STAGE"') < source.index('stop_daemon ||')
assert 'reading-records-9.7.6-install.lock' not in (PKG / 'runtime-lock.sh').read_text()
cleanup = (PKG / 'resources/reading-records-install-cleanup.sh').read_text(encoding='utf-8')
assert 'acquire_runtime_lock' not in cleanup and 'INSTALL_LOCK' not in cleanup
passed('lock order: bootstrap install -> shared -> transaction; UI only shared; cleanup no lock')

for shell in (SH, DASH):
    # Actual production launcher holds shared lock while mocked touch waits.
    d = ready(shell); d.flag('block-touch'); a = spawn(d, d.docs / 'reading-records.sh')
    await_file(d, 'touch-pid', a)
    before = runtime_bytes(d); calls = d.calls()
    d.install(ok=False)
    assert runtime_bytes(d) == before and (d.root / 'running').exists()
    assert 'service stop' not in d.calls()[len(calls):] and 'root rw' not in d.calls()[len(calls):]
    assert not list(d.base.glob('.install-*'))
    assert '阅读记录正在运行，请先退出后再安装' in d.calls()
    d.unflag('block-touch'); assert a.wait(timeout=30) == 0; d.no_temporary()
    passed(Path(shell).name + ': active UI refuses installer before snapshot/stop/publication')

    # Installer owns bootstrap lock during extraction, before shared lock.
    d = ready(shell); d.flag('block-unpack')
    d.command('tar', r'''case "$1" in -xf)
echo ready > "$SIM/unpacking"
while [ -f "$SIM/block-unpack" ]; do /usr/bin/sleep .02; done;; esac
exec /usr/bin/tar "$@"'''); d.chmod([d.mock / 'tar'])
    a = spawn(d, d.docs / BOOTSTRAP); await_file(d, 'unpacking', a)
    d.run(d.docs / 'reading-records.sh', ok=False)
    assert not (d.root / 'touch-pid').exists()
    d.unflag('block-unpack'); assert a.wait(timeout=40) == 0; d.no_temporary()
    passed(Path(shell).name + ': bootstrap active refuses UI before touching runtime')

    # During repair the versioned directory is momentarily absent; the formal
    # launcher must use its own lock code and fail cleanly, not source that dir.
    d = ready(shell); d.flag('block-publish')
    d.command('mv', r'''case "$1:$2" in */.install-*/release:*/releases/9.7.6-5.19-normal)
echo ready > "$SIM/publishing"
while [ -f "$SIM/block-publish" ]; do /usr/bin/sleep .02; done;; esac
exec /usr/bin/mv "$@"'''); d.chmod([d.mock / 'mv'])
    a = spawn(d, d.docs / BOOTSTRAP); await_file(d, 'publishing', a)
    assert not (d.base / 'releases/9.7.6-5.19-normal').exists()
    result = d.run(d.docs / 'reading-records.sh', ok=False)
    assert '缺少会话锁模块' not in result.stderr
    assert not (d.root / 'touch-pid').exists()
    d.unflag('block-publish'); assert a.wait(timeout=40) == 0; d.no_temporary()
    passed(Path(shell).name + ': repair handoff excludes UI even while release absent')

    # Cleanup's installation-only deletions can run while the formal UI owns
    # its lock; the reader and runtime bytes must remain intact.
    d = ready(shell); d.flag('block-touch'); a = spawn(d, d.docs / 'reading-records.sh')
    await_file(d, 'touch-pid', a); before = runtime_bytes(d)
    cleanup_path = d.docs / 'reading-records-install-cleanup.sh'
    before.pop(cleanup_path.as_posix())
    d.run(cleanup_path)
    assert runtime_bytes(d) == before and a.poll() is None
    d.unflag('block-touch'); assert a.wait(timeout=30) == 0; d.no_temporary()
    passed(Path(shell).name + ': cleanup leaves active UI and its shared lock intact')

# Recover abandoned bootstrap owners without deleting them from the UI path.
d = ready(); (d.tmp / 'reading-records-9.7.6-install.lock/owner.99999999').mkdir(parents=True)
d.run(d.docs / 'reading-records.sh')
assert (d.tmp / 'reading-records-9.7.6-install.lock/owner.99999999').is_dir()
d.install(); d.no_temporary(); passed('UI tolerates dead installer owner; next install recovers private lock')

# Signals between install-lock observation and shared claim do not hold either
# lock or leave a child. Existing suites cover shared reaper/owner races too.
for signal in ['INT', 'TERM', 'HUP']:
    d = ready(); path = d.docs / 'reading-records.sh'
    text = path.read_text(encoding='utf-8').replace('acquire_runtime_lock ||', 'kill -' + signal + ' "$$"\nacquire_runtime_lock ||')
    write(path, text); d.run(path, ok=False); d.no_temporary()
    assert not (d.root / 'touch-pid').exists()
    passed('UI cross-lock handoff signal: ' + signal)

# Real filesystem rollback with small rootfs/service writes faulted, no rootfs
# size guessing. Same-version repair makes mixed runtime/service observable.
for mode in ['root-remount-readonly', 'root-target-readonly', 'root-target-readonly-persistent', 'service-copy', 'service-reload',
             'activation-start', 'inactive-stop-error', 'activation-status', 'activation-status-error', 'activation-pid-dead',
             'activation-verify', 'rollback-restart', 'daemon-stop', 'daemon-alive']:
    d = ready()
    # Distinct prior bytes make a mixed deployment observable, even for a
    # repair of the same version. Only fixture files gain harmless comments.
    for prior in [d.base / 'releases/9.7.6-5.19-normal/bin/reading-records-ui.sh',
                  d.base / 'bin/native-reading-time-daemon.sh',
                  d.etc / 'upstart/native-reading-time.conf']:
        write(prior, prior.read_text(encoding='utf-8') + '\n# fixture prior deployment\n')
    before = runtime_bytes(d); data = d.preserved()
    d.flag('fault-once'); d.env['FREEZE_MODE'] = mode
    if mode == 'root-remount-readonly': d.flag('fail-root')
    d.command('cp', r'''case "$*" in *'/upstart/native-reading-time.conf.'*)
if [ "$FREEZE_MODE" = root-target-readonly-persistent ]; then echo 'Read-only file system' >&2; exit 9; fi;; esac
case "$2" in */upstart/native-reading-time.conf.new.*)
case "$FREEZE_MODE" in root-target-readonly|service-copy)
if [ -f "$SIM/fault-once" ]; then rm -f "$SIM/fault-once"; echo 'Read-only file system' >&2; exit 9; fi;; esac;; esac
exec /usr/bin/cp "$@"''')
    init = (d.mock / 'initctl').read_text(encoding='utf-8')
    init = init.replace('stop) rm -f', '''stop)
case "$FREEZE_MODE" in daemon-stop) exit 9;; daemon-alive) : > "$SIM/daemon-survives-stop";; esac
if [ "$FREEZE_MODE" = inactive-stop-error ] && [ -f "$SIM/failed-activation" ]; then exit 9; fi
rm -f''')
    init = init.replace('start)\n', '''start)
if [ "$FREEZE_MODE" = rollback-restart ] && [ -f "$SIM/failed-activation" ]; then exit 9; fi
if [ "$FREEZE_MODE" = activation-start ] || [ "$FREEZE_MODE" = rollback-restart ] || [ "$FREEZE_MODE" = inactive-stop-error ]; then
if [ -f "$SIM/fault-once" ]; then rm -f "$SIM/fault-once"; : > "$SIM/failed-activation"; exit 9; fi
fi
''')
    init = init.replace('reload-configuration) [', '''reload-configuration)
if [ "$FREEZE_MODE" = service-reload ] && [ -f "$SIM/fault-once" ]; then rm -f "$SIM/fault-once"; exit 9; fi
[''')
    init = init.replace('status) if', '''status)
case "$FREEZE_MODE" in activation-status|activation-status-error|activation-pid-dead)
if [ -f "$SIM/activation-check" ] && [ -f "$SIM/fault-once" ]; then
rm -f "$SIM/fault-once"
if [ "$FREEZE_MODE" = activation-status-error ]; then echo 'native-reading-time start/running, process 123'; exit 9; fi
if [ "$FREEZE_MODE" = activation-pid-dead ]; then echo 'native-reading-time start/running, process 99999999'; exit 0; fi
echo 'native-reading-time stop/waiting'; exit 0
fi;; esac
if''')
    init = init.replace(': > "$SIM/running"', ': > "$SIM/running"; : > "$SIM/activation-check"')
    # Force a real cmp failure after both runtime and service are published.
    d.command('cmp', r'''case "$2" in */reading-time/bin/native-reading-time-daemon.sh)
if [ "$FREEZE_MODE" = activation-verify ] && [ -f "$SIM/activation-check" ] && [ -f "$SIM/fault-once" ]; then
rm -f "$SIM/fault-once"; exit 9; fi;; esac
exec /usr/bin/cmp "$@"''')
    write(d.mock / 'initctl', init); d.chmod([d.mock / n for n in ['cp', 'cmp', 'initctl']])
    d.install(ok=False)
    assert 'SUCCESS' not in d.install_log() and d.preserved() == data
    assert (d.docs / BOOTSTRAP).exists() and d.payload.exists()
    assert not list(d.tmp.iterdir())
    if mode in ['root-target-readonly-persistent', 'rollback-restart', 'daemon-stop', 'daemon-alive']:
        stages = list(d.base.glob('.install-*')); assert len(stages) == 1
        assert 'RECOVERY_REQUIRED snapshot=' + stages[0].as_posix() in d.install_log()
        assert (stages[0] / 'backup').is_dir() and (stages[0] / 'journal').is_file()
        assert runtime_bytes(d) == before
    else:
        assert runtime_bytes(d) == before and (d.root / 'running').exists()
        d.no_temporary()
    passed('rootfs/service fault rollback: ' + mode)

# An earlier RECOVERY_REQUIRED snapshot can collide after PID reuse. Failed
# mkdir is not ownership and must not authorize finish() to remove that path.
d = ready(); before = runtime_bytes(d)
d.command('mkdir', r'''case "$1" in */.install-9.7.6-normal.[0-9]*)
/usr/bin/mkdir -p "$1/backup"
echo 'prior journal' > "$1/journal"
echo 'only recovery bytes' > "$1/backup/old-file"
echo "$1" > "$SIM/collision-snapshot"
exit 9;; esac
exec /usr/bin/mkdir "$@"'''); d.chmod([d.mock / 'mkdir'])
d.install(ok=False)
stage = Path(d.read('collision-snapshot'))
assert (stage / 'journal').read_text().strip() == 'prior journal'
assert (stage / 'backup/old-file').read_text().strip() == 'only recovery bytes'
assert runtime_bytes(d) == before and (d.root / 'running').exists()
assert 'service stop' not in d.calls() and 'root rw' not in d.calls()
assert not list(d.tmp.iterdir()) and 'SUCCESS' not in d.install_log()
passed('staging mkdir collision preserves unowned prior recovery snapshot')

# A genuine owned service PID survives a lying stop/waiting status. The
# installer must not publish or kill that process; it preserves recovery data.
d = ready(); owner = subprocess.Popen([SH, '-c',
    'echo "$$" > "$SIM/real-daemon-pid"; exec /usr/bin/sleep 90'],
    env=d.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    await_file(d, 'real-daemon-pid', owner); pid = d.read('real-daemon-pid')
    assert int(pid) > 0 and pid != '123', 'real PID must bypass synthetic service-PID fixture'
    d.command('initctl', '''echo "service $*" >> "$SIM/calls"
case "$1" in status)
if [ -f "$SIM/stopped" ]; then echo 'native-reading-time stop/waiting'; else
echo "native-reading-time start/running, process $(cat "$SIM/real-daemon-pid")"; fi;;
stop) : > "$SIM/stopped";; *) exit 9;; esac'''); d.chmod([d.mock / 'initctl'])
    before = runtime_bytes(d); d.install(ok=False)
    assert runtime_bytes(d) == before and owner.poll() is None
    assert 'RECOVERY_REQUIRED snapshot=' in d.install_log() and 'SUCCESS' not in d.install_log()
    passed('daemon actual PID survives stop/waiting: refuse publication and retain snapshot')
finally:
    subprocess.run([SH, '-c', 'kill -TERM "$1"', 'owned-daemon', pid], capture_output=True)
    owner.wait(timeout=5)

# Reject unsupported command use across all shipped production shell helpers.
with zipfile.ZipFile(ARCHIVE) as z:
    with tarfile.open(fileobj=io.BytesIO(z.read(PAYLOAD))) as t:
        production = {m.name: t.extractfile(m).read().decode('utf-8') for m in t.getmembers() if m.name.endswith('.sh')}
production[BOOTSTRAP] = (ROOT / 'documents' / BOOTSTRAP).read_text(encoding='utf-8')
for name, text in production.items():
    active = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('#'))
    assert not re.search(r'\[\[|<\(|>\(|\b(?:flock|timeout|realpath|killall|pkill)\b|\breadlink\s+-f|\bfind\b[^\n]*-printf|\bdu\s+-b|\bsed\s+-r|\bdate\s+-d|\bsha256sum\b', active), name
    for shell in (SH, DASH): subprocess.run([shell, '-n', '-'], input=text.encode(), check=True, capture_output=True)
passed('sh/dash syntax and shipped production command/option audit (static, not BusyBox ash)')
assert 'LC_ALL=C df -Pk' in source and 'du -sk' in source
assert 'tar "$@" && return 0' in production[BOOTSTRAP] and 'busybox tar "$@"' in production[BOOTSTRAP]
assert 'cksum < "$PAYLOAD"' in production[BOOTSTRAP]
passed('df/du/tar/cksum option contracts; no runtime SHA-256 dependency')

write(OUT / 'final-freeze-results.json', json.dumps({
    'result': 'PASS', 'checks': checks, 'case_count': len(checks),
    'busybox_ash_executed': False,
    'limits': ['MSYS sh/dash and real host filesystem/cksum/tar/du; Kindle commands and synthetic service PID 123 mocked. No BusyBox binary or Kindle hardware executed.']
}, ensure_ascii=False, indent=2))
