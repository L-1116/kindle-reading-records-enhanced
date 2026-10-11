"""Test both production selectors against the reported KPW4 sysfs layout.

Host fixtures cannot create Kindle character devices or privileged Windows
symlinks. Node type and link status use explicit markers; all path, numeric,
readability and sysfs-name checks execute unchanged under sh/dash.
Lua fixtures separately exercise the unchanged real Lua 5.1 readers.
"""
from pathlib import Path
import json, os, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / 'native-reading-time-package'
OUT = ROOT / 'build/test2-audit'
OUT.mkdir(parents=True, exist_ok=True)
SHELLS = ['C:/Program Files/Git/usr/bin/sh.exe', 'C:/Program Files/Git/usr/bin/dash.exe'] if os.name == 'nt' else ['/bin/sh', '/bin/dash']
NAMES = ('阅读记录-optimized.sh', '阅读记录.sh')
from springbreak_archives import historical_zip, members
import io, zipfile
TEST1_ZIP=historical_zip('test1')
with zipfile.ZipFile(io.BytesIO(TEST1_ZIP)) as z: TEST1_FILES=members(z.read('reading-records-9.7.6-data.tar'))
checks = []
def passed(name, **detail):
    checks.append(dict(check=name, result='PASS', **detail))
    print('PASS: ' + name, flush=True)

def selector(source):
    start = 'touch_device_is_valid() {' if 'touch_device_is_valid() {' in source else 'find_touch_device() {'
    return source[source.index(start):source.index('scale_len() {')]

def run_select(source, layout, override=None, absent=(), nonchar=(), links=(), stale=False, shell=SHELLS[0]):
    with tempfile.TemporaryDirectory(prefix='kpw4-touch-') as tmp:
        folder = Path(tmp); sysfs = folder / 'sys'; dev = folder / 'dev'; dev.mkdir()
        for node, label in layout.items():
            p = sysfs / node / 'device/name'; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(label, encoding='utf-8')
            if node not in absent:
                (dev / node).touch()
                if node not in nonchar: (dev / (node + '.fixture-char')).touch()
        # Windows native links need privileges this task does not request.
        # Explicitly simulate link metadata, without treating ln's file copy
        # fallback as a real link or skipping the rejection assertion.
        for node, target in links:
            assert (dev / target).exists()
            (dev / (node + '.fixture-symlink')).touch()
        code = selector(source)
        if 'touch_device_is_valid() {' in source:
            assert code.count('[ -c "$touch_candidate" ]') == 1
            code = code.replace('[ -c "$touch_candidate" ]', '[ -f "$touch_candidate.fixture-char" ]')
            assert code.count('[ ! -L "$touch_candidate" ]') == 1
            code = code.replace('[ ! -L "$touch_candidate" ]', '[ ! -L "$touch_candidate" ] && [ ! -f "$touch_candidate.fixture-symlink" ]')
        code = code.replace('/sys/class/input', sysfs.as_posix()).replace('/dev/input', dev.as_posix())
        override = '' if override is None else override.replace('/dev/input', dev.as_posix())
        env = os.environ.copy(); env['READING_TOUCH_DEVICE'] = override
        # Do not inherit a user's unrelated input override into these fixtures.
        result = subprocess.run([shell, '-c', 'export PATH="/usr/bin:/bin:$PATH"; fail() { echo "ERROR: $1"; exit 1; }; ' + code +
                                 ('\nTOUCH=stale; ' if stale else '\n') + 'find_touch_device; printf "SELECTED=%s\n" "$TOUCH"'],
                                env=env, capture_output=True, text=True, encoding='utf-8')
        selected = next((s.removeprefix('SELECTED=') for s in result.stdout.splitlines() if s.startswith('SELECTED=')), None)
        if selected: selected = '/dev/input/' + selected.rsplit('/', 1)[-1]
        return result.returncode, selected, result.stdout + result.stderr

REAL = {'event0': '20cc000.snvs', 'event1': 'bd71827-power', 'event2': 'goodix-ts'}
for name in NAMES:
    original = TEST1_FILES[name].decode()
    status, selected, log = run_select(original, REAL)
    assert status == 0 and selected == '/dev/input/event1', (status, selected, log)
    passed(name + ': exact Test 1 selector reproduces wrong power-node fallback', selected=selected)
if '--reproduce-only' in sys.argv:
    (OUT / 'touch-before.json').write_text(json.dumps(dict(result='PASS', checks=checks, reported_sysfs=REAL), ensure_ascii=False, indent=2), encoding='utf-8')
    raise SystemExit(0)

for name in NAMES:
    source = (PKG / name).read_text(encoding='utf-8')
    for shell in SHELLS:
        prefix = name + '/' + Path(shell).name
        def ok(layout, expected, **args):
            status, selected, log = run_select(source, layout, shell=shell, **args)
            assert status == 0 and selected == '/dev/input/' + expected, (status, selected, log)
            assert selected not in ('/dev/input/event0', '/dev/input/event1') or expected == 'event1'
        def reject(layout, **args):
            status, selected, log = run_select(source, layout, shell=shell, **args)
            assert status == 1 and selected is None and 'ERROR:' in log, (status, selected, log)
        ok(REAL, 'event2')
        passed(prefix + ': actual KPW4 layout selects event2, never event0/event1')
        ok({'event0': REAL['event0'], 'event1': REAL['event1'], 'event7': 'GOODIX-TS'}, 'event7')
        passed(prefix + ': goodix-ts is case-insensitive and independent of event number')
        for label in ('touch', 'zforce', 'cyttsp', 'fts', 'driver_ts', 'CYTTSP TOUCH'):
            ok({'event1': 'powerkey touch', 'event3': label}, 'event3')
            passed(prefix + ': preserves existing recognized name', device_name=label)
        ok({'event1': 'cyttsp touch'}, 'event1')
        passed(prefix + ': positively identified Standard event1 remains supported')
        for label in ('powerkey', 'power', 'bd71827-power', 'power touch', 'powerkey_ts', 'fts power button', '20cc000.snvs'):
            reject({'event1': label}, stale=True)
            passed(prefix + ': rejects non-touch/power node without default fallback', device_name=label)
        reject({}); reject({'event1': 'unknown driver'}, stale=True)
        passed(prefix + ': missing or unknown device fails with an explicit error, even with stale TOUCH')
        reject(REAL, absent=('event2',)); reject(REAL, nonchar=('event2',))
        passed(prefix + ': missing node or ordinary readable file is not a touch device')
        ok(REAL, 'event2', override='/dev/input/event2')
        passed(prefix + ': valid recognized override is accepted')
        for override in ('/dev/input/event0', '/dev/input/event1', '/dev/input/event99', '/dev/input/event2junk',
                         '/dev/input/event-2', '/dev/input/event', '/dev/input/event2/../event1', '/dev/null', '/tmp/input'):
            reject(REAL, override=override)
            passed(prefix + ': unsafe or invalid override fails closed', override=override)
        reject(REAL, override='/dev/input/event2', nonchar=('event2',))
        reject({'event2': 'unknown driver'}, override='/dev/input/event2')
        passed(prefix + ': override cannot bypass character-node or positive sysfs-name validation')
        reject(REAL, override='/dev/input/event2', links=(('event2', 'event1'),))
        passed(prefix + ': override rejects simulated symbolic-link metadata for a power-node alias')

# Exercise installed launcher -> optimized/legacy -> reader handoff and cleanup,
# rather than only extracting the selector. Shell commands/hardware are mocked.
from normal_fixture import Device, SH, DASH, write, digest, BOOTSTRAP, PAYLOAD
from springbreak_contract import VERSION
import hashlib, io, shutil, tarfile, zipfile

def actual_layout(d):
    for node, label in REAL.items():
        write(d.sys / ('class/input/' + node + '/device/name'), label + '\n')
        write(d.root / ('dev/input/' + node), 'synthetic evdev node\n')
        write(d.root / ('dev/input/' + node + '.fixture-char'), 'character metadata\n')
    lua = d.mock / 'lua'
    source = lua.read_text(encoding='utf-8')
    assert source.count('echo "$$" > "$SIM/touch-pid"') == 1
    write(lua, source.replace('echo "$$" > "$SIM/touch-pid"',
        'echo "$$" > "$SIM/touch-pid"\n    echo "touch_node=$2" >> "$SIM/calls"'))
    d.chmod([lua])

templates = {}
def ready(shell):
    if shell not in templates:
        d = Device(shell); d.seed('9.7.6-5.18-springbreak-kpw4-test1'); d.install(); templates[shell] = d
    t = templates[shell]; d = Device(shell)
    for src, dst in ((t.base, d.base), (t.docs, d.docs), (t.etc / 'upstart', d.etc / 'upstart')):
        shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns(BOOTSTRAP, PAYLOAD) if src == t.docs else None)
        for path in dst.rglob('*'):
            if path.is_file() and path.suffix in {'.sh', '.conf', '.tsv', '.txt'}:
                path.write_bytes(path.read_bytes().replace(t.root.as_posix().encode(), d.root.as_posix().encode()))
    d.flag('running'); actual_layout(d); return d

for shell in (SH, DASH):
    for fallback in (False, True):
        for mode in ('automatic', 'override', 'no-touch', 'power-override'):
            d = ready(shell); d.flag('orientation', 'R'); d.flag('preventScreenSaver', '2')
            if fallback: (d.base / f'releases/{VERSION}/bin/reading-insights-render.lua').unlink()
            if mode == 'override': d.env['READING_TOUCH_DEVICE'] = (d.root / 'dev/input/event2').as_posix()
            elif mode == 'power-override': d.env['READING_TOUCH_DEVICE'] = (d.root / 'dev/input/event1').as_posix()
            elif mode == 'no-touch': write(d.sys / 'class/input/event2/device/name', 'unknown driver\n')
            before = d.preserved(); d.flag('actions', 'tab_total\nexit')
            d.run(d.docs / 'reading-records.sh', ok=mode in ('automatic', 'override'))
            log = (d.base / 'dashboard-launch.log').read_text(encoding='utf-8')
            if mode in ('automatic', 'override'):
                expected = (d.root / 'dev/input/event2').as_posix()
                assert 'touch_device=' + expected in log and 'touch_node=' + expected in d.calls()
                assert 'touch_node=' + (d.root / 'dev/input/event1').as_posix() not in d.calls()
                assert 'touch=' + expected in (d.base / 'display-layout.txt').read_text(encoding='utf-8')
                assert 'action=tab_total' in log and 'action=exit' in log
            else:
                assert 'ERROR:' in log and not (d.root / 'touch-pid').exists()
                assert 'touch_node=' not in d.calls() and 'fbink -q' not in d.calls()
            assert d.read('orientation') == 'R' and d.read('preventScreenSaver') == '2'
            assert 'eatTapMode' not in d.calls() and d.preserved() == before
            assert (d.docs / BOOTSTRAP).exists() and d.payload.exists()
            d.no_temporary()
            passed(f'{Path(shell).name}: full installed UI fallback={fallback} mode={mode}, reader handoff/restore/data/locks verified')

    # Install exact preserved Test 1 bytes, then verify transactional Test 2
    # failure rollback, retry, same-version repair and whitelist cleanup.
    d = Device(shell); new_tar, new_boot = d.original_tar, d.original_boot
    test1 = io.BytesIO(TEST1_ZIP)
    assert hashlib.sha256(TEST1_ZIP).hexdigest() == '11bf3309d509685e841a9ec39d76a831d717d2f020ac142343f253a2c372262d'
    with zipfile.ZipFile(test1) as archive:
        d.original_tar, d.original_boot = archive.read(PAYLOAD), archive.read(BOOTSTRAP)
    d.prepare_payload(); d.seed('9.7.6-5.18-springbreak-kpw4-test1'); d.install()
    assert d.read('us/reading-time/VERSION') == '9.7.6-5.18-springbreak-kpw4-test1'
    runtime = {p: digest(p) for p in (d.base/'VERSION', d.docs/'reading-records.sh', d.base/'bin/native-reading-time-daemon.sh', d.etc/'upstart/native-reading-time.conf')}
    logs = ('dashboard-launch.log', 'dashboard-touch.log', 'service.log', 'upstart.log', 'install.log')
    for name in logs: write(d.base / name, 'original Test 1 core log\n')
    install_log = (d.base / 'install-last.log').read_bytes(); data = d.preserved()
    d.original_tar, d.original_boot = new_tar, new_boot; d.prepare_payload(); d.flag('fail-service'); d.install(ok=False)
    assert all(digest(path) == value for path, value in runtime.items())
    assert d.read('us/reading-time/VERSION') == '9.7.6-5.18-springbreak-kpw4-test1'
    assert d.preserved() == data and (d.base/'install-last.log').read_bytes().startswith(install_log)
    assert all((d.base/name).read_text() == 'original Test 1 core log\n' for name in logs)
    assert (d.docs / BOOTSTRAP).exists() and d.payload.exists(); d.no_temporary()
    passed(Path(shell).name + ': exact Test 1 -> Test 2 fault rolls back and retains data/logs/install files')
    d.install(); assert d.read('us/reading-time/VERSION') == VERSION and d.preserved() == data
    assert (d.base/'releases/9.7.6-5.18-springbreak-kpw4-test1/bin/reading-records-ui.sh').exists()
    broken = d.base / f'releases/{VERSION}/bin/reading-records-ui.sh'; write(broken, 'exit 99\n'); d.install()
    assert broken.read_bytes() == d.transform((PKG/'阅读记录-optimized.sh').read_bytes())
    assert d.preserved() == data; d.no_temporary()
    d.run(d.docs / 'reading-records-install-cleanup.sh')
    assert d.preserved() == data and (d.base/'install-last.log').read_bytes().startswith(install_log)
    assert all((d.base/name).read_text() == 'original Test 1 core log\n' for name in logs)
    assert not (d.docs / BOOTSTRAP).exists() and not d.payload.exists()
    assert (d.base/'releases/9.7.6-5.18-springbreak-kpw4-test1/bin/reading-records-ui.sh').exists()
    passed(Path(shell).name + ': exact Test 1 -> Test 2 retry/repair/cleanup preserves history/backup/config/covers/cache/logs/old release')

(OUT / 'touch-results.json').write_text(json.dumps(dict(result='PASS', checks=checks,
    reported_sysfs=REAL, limits=['Character-node and link metadata are represented by explicit host fixture markers; actual Kindle node checks remain -c/-r/! -L.',
    'No raw goodix event capture supplied; no event format or coordinate changes made.']), ensure_ascii=False, indent=2), encoding='utf-8')
