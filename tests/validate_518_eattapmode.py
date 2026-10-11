"""5.18 write-only regression: real old/new launcher and same-version upgrade."""
from normal_fixture import *
import json

START = '01109630d1b03c693eef587b494c2bafe00c60e3'
checks = []


def passed(name):
    checks.append({'check': name, 'result': 'PASS'})
    print('PASS: ' + name, flush=True)


def old_launcher():
    return subprocess.check_output(['git', 'show', START + ':native-reading-time-package/launch.sh'], cwd=ROOT)


def copy_device(template):
    d = Device(template.shell)
    for src, dst in [(template.base, d.base), (template.docs, d.docs),
                     (template.etc / 'upstart', d.etc / 'upstart')]:
        shutil.copytree(src, dst, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(BOOTSTRAP, PAYLOAD) if src == template.docs else None)
        for p in dst.rglob('*'):
            if p.is_file() and p.suffix in {'.sh', '.conf', '.tsv', '.txt'}:
                p.write_bytes(p.read_bytes().replace(template.root.as_posix().encode(), d.root.as_posix().encode()))
    d.flag('running')
    return d


def reproduce():
    # Run before touching production; final regression also retains this test
    # against the exact starting launcher, rather than a simplified model.
    evidence = []
    for shell in (SH, DASH):
        template = Device(shell); template.seed('9.7.5-test'); template.install()
        for hidden in (None, '0', '7'):
            for direction in ('U', 'R'):
                d = copy_device(template)
                (d.docs / 'reading-records.sh').write_bytes(d.transform(old_launcher()))
                d.flag('orientation', direction)
                if hidden is None: d.unflag('eatTapMode')
                else: d.flag('eatTapMode', hidden)
                # Direct property read has no stdout even if private data exists.
                path = d.root / 'get-write-only.sh'
                write(path, 'lipc-get-prop com.lab126.winmgr eatTapMode')
                read_result = d.run(path, ok=False)
                assert read_result.stdout == '' and 'not readable' in read_result.stderr
                (d.root / 'calls').unlink()
                p = d.run(d.docs / 'reading-records.sh', ok=False)
                log = (d.base / 'dashboard-launch.log').read_text(encoding='utf-8')
                calls = d.calls()
                assert p.returncode == 1 and 'ERROR: 无法保存触摸状态' in log
                assert 'get com.lab126.winmgr eatTapMode' in calls
                assert not any(c.startswith('set com.lab126.winmgr eatTapMode') for c in calls.splitlines())
                assert not (d.root / 'touch-pid').exists()
                assert d.read('orientation') == direction and d.read('preventScreenSaver') == '0'
                if hidden is None: assert not (d.root / 'eatTapMode').exists()
                else: assert d.read('eatTapMode') == hidden
                d.no_temporary()
                evidence.append({'shell': Path(shell).name, 'hidden_state': hidden,
                                 'orientation': direction, 'exit': p.returncode,
                                 'log': log, 'calls': calls})
                passed(f'old 5.18 launcher reproduces write-only startup exit: {Path(shell).name}/{hidden}/{direction}')
    return evidence


def baseline_payload(d):
    # All protected current payload bytes equal START (audited separately).
    # Reconstruct the exact old launcher package with valid manifest/checksum.
    with tarfile.open(fileobj=io.BytesIO(d.original_tar)) as t:
        sources = {m.name: t.extractfile(m).read() for m in t.getmembers()}
    prefix = 'native-reading-time-package/'
    sources[prefix + 'launch.sh'] = old_launcher()
    sources.pop(prefix + 'payload-manifest.tsv')
    sources[prefix + 'payload-manifest.tsv'] = ''.join(
        f'{python_cksum(raw)[0]}\t{len(raw)}\t{name.removeprefix(prefix)}\n'
        for name, raw in sorted(sources.items())).encode()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w', format=tarfile.USTAR_FORMAT) as t:
        for name, raw in sorted(sources.items()):
            m = tarfile.TarInfo(name); m.size = len(raw)
            m.mode = 0o755 if name.endswith('.sh') else 0o644
            t.addfile(m, io.BytesIO(raw))
    raw = buf.getvalue()
    assert hashlib.sha256(raw).hexdigest() == '650a4b3e649241d932651c1d84bb74c5c83c9dd47d2f86247cb7b6a61561ba63'
    checksum, size = python_cksum(raw)
    boot = re.sub(rb'EXPECTED_CKSUM=\d+', f'EXPECTED_CKSUM={checksum}'.encode(), d.original_boot)
    boot = re.sub(rb'EXPECTED_SIZE=\d+', f'EXPECTED_SIZE={size}'.encode(), boot)
    return raw, boot


def verify_fixed():
    assert b'ORIGINAL_EAT' not in (PKG / 'launch.sh').read_bytes()
    for name in ('reading-insights-touch.lua', 'reading-insights-touch-ui.lua'):
        source = (PKG / name).read_text(encoding='utf-8')
        assert 'io.open(device, "rb")' in source
        active = '\n'.join(l for l in source.splitlines() if not l.lstrip().startswith('--'))
        assert not re.search(r'EVIOCGRAB|eatTapMode|ioctl', active)
    passed('both actual evdev readers remain read-only without grab or touch-state calls')
    for shell in (SH, DASH):
        template = Device(shell); template.seed('9.7.5-test'); template.install()
        # Synthetic /tmp destinations prove a single pass on Windows too.
        d = copy_device(template)
        d.us = Path('/tmp/simulator/us'); d.tmp = Path('/tmp/simulator/tmp')
        assert d.transform(b'/mnt/us/a /tmp/b') == b'/tmp/simulator/us/a /tmp/simulator/tmp/b'
        passed(f'{Path(shell).name}: original-prefix replacement does not rewrite inserted /tmp paths')
        for hidden in (None, '0', '7'):
            for fallback in (False, True):
                d = copy_device(template); d.flag('orientation', 'R'); d.flag('preventScreenSaver', '2')
                d.flag('fail-set-eatTapMode')
                if hidden is None: d.unflag('eatTapMode')
                else: d.flag('eatTapMode', hidden)
                if fallback: (d.base / 'releases/9.7.6-5.18-vera/bin/reading-insights-render.lua').unlink()
                actions = ['tab_total', 'tab_books', 'tab_daily', 'month_prev', 'exit']
                d.flag('actions', '\n'.join(actions)); before = d.preserved()
                d.run(d.docs / 'reading-records.sh')
                log = (d.base / 'dashboard-launch.log').read_text(encoding='utf-8')
                assert ('switching to original dashboard' in log) == fallback
                for action in actions: assert 'dashboard action=' + action + ' ' in log
                assert not any('eatTapMode' in c for c in d.calls().splitlines())
                assert d.read('orientation') == 'R' and d.read('preventScreenSaver') == '2'
                if hidden is None: assert not (d.root / 'eatTapMode').exists()
                else: assert d.read('eatTapMode') == hidden
                assert d.preserved() == before; d.no_temporary()
                passed(f'fixed startup/navigation/exit, no touch-state get/set: {Path(shell).name}/{hidden}/fallback={fallback}')

    d = Device(); d.seed('9.7.5-test')
    new_tar, new_boot = d.original_tar, d.original_boot
    d.original_tar, d.original_boot = baseline_payload(d); d.prepare_payload(); d.install()
    assert (d.docs / 'reading-records.sh').read_bytes() == d.transform(old_launcher())
    d.flag('eatTapMode', '7'); d.flag('orientation', 'R')
    d.run(d.docs / 'reading-records.sh', ok=False)
    old_log = (d.base / 'dashboard-launch.log').read_bytes()
    for name in ('install.log', 'dashboard-touch.log', 'upstart.log'):
        write(d.base / name, 'preserved core log\n')
    before = d.preserved()
    logs = {name: digest(d.base / name) for name in ('install.log', 'dashboard-touch.log', 'upstart.log')}
    d.original_tar, d.original_boot = new_tar, new_boot; d.prepare_payload(); d.install()
    assert (d.base / 'dashboard-launch.log').read_bytes() == old_log
    assert (d.docs / 'reading-records.sh').read_bytes() == d.transform((PKG / 'launch.sh').read_bytes())
    assert d.preserved() == before and all(digest(d.base / n) == h for n, h in logs.items())
    (d.root / 'calls').unlink(); d.run(d.docs / 'reading-records.sh')
    assert 'eatTapMode' not in d.calls() and d.read('eatTapMode') == '7'
    d.run(d.docs / 'reading-records-install-cleanup.sh')
    assert d.preserved() == before and all(digest(d.base / n) == h for n, h in logs.items())
    assert not (d.docs / BOOTSTRAP).exists() and not d.payload.exists()
    d.flag('actions', 'exit'); (d.root / 'calls').unlink(); d.run(d.docs / 'reading-records.sh')
    assert 'eatTapMode' not in d.calls() and d.read('orientation') == 'R'
    assert d.preserved() == before; d.no_temporary()
    assert (d.base / 'dashboard-launch.log').read_bytes().startswith(old_log)
    passed('old 5.18 package same-version upgrade replaces launcher; data/logs survive cleanup and relaunch')


if __name__ == '__main__':
    evidence = reproduce()
    before_only = '--reproduce' in sys.argv
    if before_only:
        assert (PKG / 'launch.sh').read_bytes() == old_launcher()
        # Keep old archive and old reports as evidence before rebuilding.
        saved = OUT / '518-eattapmode-before'; saved.mkdir(exist_ok=True)
        shutil.copy2(ARCHIVE, saved / ARCHIVE.name)
        for name in ('package-results.json', 'suite-results.json', '5.18-vera-final-report.md'):
            if (OUT / name).exists(): shutil.copy2(OUT / name, saved / name)
    else: verify_fixed()
    output = '518-eattapmode-before.json' if before_only else '518-eattapmode-results.json'
    write(OUT / output, json.dumps({'result': 'PASS', 'start_sha': START,
          'production_unmodified': before_only, 'checks': checks,
          'reproduction': evidence, 'limits': ['5.18 hardware not verified; LIPC and physical input simulated.']}, ensure_ascii=False, indent=2))
