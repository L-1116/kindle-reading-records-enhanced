"""Real frontend/launcher cleanup against a blocking, offline powerd event bus.

No Kindle hardware or firmware timing claims are made by these tests.
"""
from pathlib import Path
import hashlib
import shlex
import subprocess
import tempfile
import time

from validate_runtime_probe import ROOT, OUT, SH, setup, executable

PKG = ROOT / 'native-reading-time-package'
q = lambda p: shlex.quote(Path(p).as_posix())


def wait_file(path, process):
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        if path.exists() and path.stat().st_size:
            return
        if process.poll() is not None:
            log = path.parent/'reading-time/launch-last.log'
            raise AssertionError((process.returncode, path, process.communicate(), log.read_text(errors='replace') if log.exists() else ''))
        time.sleep(.02)
    raise AssertionError(('fixture readiness timeout', path))


def alive(pid):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if subprocess.run([SH, '-c', 'kill -0 "$1" 2>/dev/null', 'fixture', pid], capture_output=True).returncode != 0:
            return False
        time.sleep(.02)
    return subprocess.run([SH, '-c', 'kill -0 "$1" 2>/dev/null', 'fixture', pid],
                          capture_output=True).returncode == 0


def case(renderer, event, stage='touch', external_power='0', cover_mode=None):
    with tempfile.TemporaryDirectory(prefix='power-exit-', dir=OUT) as directory:
        root = Path(directory)
        launcher, env, _, _ = setup(root, 'standard')
        base = root / 'reading-time'
        release = base / 'releases/9.8.1-5.20-vera-test1'
        mock = root / 'mockbin'
        session = root / 'native-reading-dashboard.123'
        trace = root / 'power-trace'
        # Persistent data must survive every foreground exit.
        protected = [base/'reading-time.tsv', base/'user.conf', base/'book-covers/sentinel']
        for path in protected:
            path.parent.mkdir(exist_ok=True, parents=True)
            if not path.exists(): path.write_bytes(b'preserve me\n')
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
        touch = root / 'touch'
        touch.write_bytes(b'mock')
        (base/'ui').mkdir()
        (base/'ui/total.png').write_bytes(b'mock')
        env.update(READING_TOUCH_DEVICE=touch.as_posix(), READING_LAUNCHER_CAPTURE='1',
                   POWER_TEST_PID=(root/'event-pid').as_posix(), TRACE=trace.as_posix(),
                   READING_UI_LOCK=(root/'ui.lock').as_posix(),
                   READER_PID=(root/'reader-pid').as_posix(), BLOCK_FIFO=(mock/'power-events').as_posix(),
                   TEST_ROOT=root.as_posix(), TEST_RENDERER=renderer, TEST_STAGE=stage,
                   TEST_COVER_HELPERS=(PKG/'reading-custom-covers.sh').as_posix(),
                   READING_TEST_ORIGINAL_POWER=external_power,
                   POWER_TEST_STATE='screenSaver' if stage == 'already_asleep' else 'active')
        executable(mock/'lipc-get-prop',
                   'case "$2" in state) echo "$POWER_TEST_STATE";; orientationLock) echo U;; *) echo "$READING_TEST_ORIGINAL_POWER";; esac\n')
        executable(mock/'lipc-set-prop', '''
printf '%s\\n' "$*" >> "$TRACE"
if [ "$TEST_STAGE:$2" = exit_race:eatTapMode ]; then
    if [ -f "$TEST_ROOT/eat-tap-seen" ]; then
        printf 'goingToScreenSaver 2\\n' > "$BLOCK_FIFO"
    else : > "$TEST_ROOT/eat-tap-seen"; fi
fi
''')
        # Separate control FIFO for a reader blocked in an ordinary input read.
        subprocess.run([SH, '-c', '/usr/bin/mkfifo "$1"', 'fixture', (root/'touch-control').as_posix()], check=True)
        executable(mock/'lua', '''
case "$1" in -e) exit 0;; esac
if [ "$TEST_RENDERER" = fallback ] && [ ! -f "$TEST_ROOT/switched" ]; then
    : > "$TEST_ROOT/switched"; echo tab_books; exit 0
fi
echo $$ > "$READER_PID"
exec 7<>"$TEST_ROOT/touch-control"
IFS= read -r action <&7
printf '%s\\n' "$action"
''')
        common = '''
detect_screen() { SCREEN_W=1272; SCREEN_H=1696; VIEW_W=1272; VIEW_H=1696; ORIGIN_X=0; ORIGIN_Y=0; }
find_touch_device() { TOUCH="$READING_TOUCH_DEVICE"; }
rr_settings_init() { . "$TEST_COVER_HELPERS"; }
standard_touch_action_received() { :; }
standard_touch_reader_failed() { exit 72; }
days_in_month() { echo 31; }; weekday_offset() { echo 0; }
refresh_progress_cache() { :; }
build_cache() { :; }; metric_begin() { :; }; metric_end() { :; }
remove_session() { rm -rf "$SESSION_DIR"; }
draw_background() { if [ "$TEST_STAGE" = fbink ]; then fb -q -W GC16 -s; fi; }
draw_dynamic() { if [ "$TEST_STAGE" = cover_worker ]; then rr_cover_exec "$TEST_ROOT/mockbin/block-cover"; fi; [ "$TEST_RENDERER:$mode" != fallback:books ]; }
refresh_region() { :; }; draw() { :; }
'''
        source = (PKG/'阅读记录-optimized.sh').read_text(encoding='utf-8')
        prefix, tail = source.split('\ndetect_screen; find_touch_device', 1)
        source = prefix + common + '\ndetect_screen; find_touch_device' + tail
        if cover_mode: source=source.replace('mode=daily; view_year=',f'mode={cover_mode}; view_year=')
        legacy = (PKG/'阅读记录.sh').read_text(encoding='utf-8')
        legacy = legacy.replace('\ndetect_screen\nfind_touch_device', '\n' + common + '\ndetect_screen\nfind_touch_device')
        legacy = legacy.replace('\n# Safety invariant:', '\n' + common + '\n# Safety invariant:')
        if cover_mode: legacy=legacy.replace('mode="total"; view_year=',f'mode="{cover_mode}"; view_year=')
        for path, raw in ((release/'bin/reading-records.sh', source),
                          (release/'bin/reading-records-v9.6.3.sh', legacy)):
            raw = raw.replace('SESSION_DIR="/tmp/native-reading-dashboard.$$"', 'SESSION_DIR='+q(session))
            # Legacy runs under its parent, so give it a separate transient folder.
            if path.name.endswith('v9.6.3.sh'):
                raw = raw.replace('SESSION_DIR="${READING_UI_SESSION:-/tmp/native-reading-dashboard.$$}"', 'SESSION_DIR="${READING_UI_SESSION:-'+(root/'native-reading-dashboard.124').as_posix()+'}"')
            path.write_text(raw, encoding='utf-8', newline='\n')
            subprocess.run([SH, '-c', '/usr/bin/chmod 755 "$1"', 'fixture', path.as_posix()], check=True)
        executable(mock/'fbink', '''
if [ "$TEST_STAGE" = fbink ]; then
    echo $$ > "$READER_PID"
    exec 7<>"$TEST_ROOT/touch-control"; IFS= read -r unused <&7
fi
exit 0
''')
        executable(mock/'block-cover','echo $$ > "$READER_PID"\nexec 7<>"$TEST_ROOT/touch-control"; IFS= read -r unused <&7\n')
        # The native FIFO subscription is always the real module installed by setup.
        if stage == 'subscription_failure': env['POWER_TEST_FAIL'] = '1'
        command = launcher if renderer != 'legacy' else release/'bin/reading-records-v9.6.3.sh'
        process = subprocess.Popen([SH, command.as_posix()], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            if stage != 'already_asleep': wait_file(root/'event-pid', process)
            if stage not in ('subscription_failure', 'already_asleep'):
                wait_file(root/'reader-pid', process)
                target = root/'touch-control' if event == 'manual' else mock/'power-events'
                value = 'exit' if event == 'manual' else event
                subprocess.run([SH, '-c', 'printf "%s\\n" "$1" > "$2"', 'fixture', value, target.as_posix()],
                               env=env, check=True, timeout=4)
            output = process.communicate(timeout=12)
            expected = 91 if stage == 'subscription_failure' else 90 if renderer == 'legacy' and event != 'manual' else 0
            log = (base/'launch-last.log').read_text(errors='replace') if command == launcher else str(output)
            assert process.returncode == expected, (renderer, event, stage, process.returncode, log, output)
            calls = trace.read_text(encoding='utf-8') if trace.exists() else ''
            assert 'preventScreenSaver' not in calls and 'powerButton' not in calls and 'toggleSuspend' not in calls, calls
            if event == 'manual' and stage != 'exit_race': assert 'KPP_LIBRARY' in calls, calls
            elif stage != 'subscription_failure': assert 'KPP_LIBRARY' not in calls, calls
            if command == launcher and (event != 'manual' or stage == 'exit_race') and stage != 'subscription_failure':
                assert 'frontend_exit=sleep_request' in log and 'error_stage=none' in log, log
            for file in (root/'event-pid', root/'reader-pid'):
                if file.exists():
                    assert not alive(file.read_text().strip()), (file, log)
            assert not session.exists() and not (root/'native-reading-dashboard.124').exists()
            assert not Path(env['READING_UI_LOCK']).exists()
            assert all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p,h in before.items())
            if stage == 'reopen':
                for file in (root/'event-pid', root/'reader-pid'): file.unlink()
                process = subprocess.Popen([SH, command.as_posix()], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                wait_file(root/'event-pid', process)
                wait_file(root/'reader-pid', process)
                subprocess.run([SH, '-c', 'printf "exit\\n" > "$1"', 'fixture', (root/'touch-control').as_posix()],
                               env=env, check=True, timeout=4)
                output = process.communicate(timeout=12)
                assert process.returncode == 0, output
                for file in (root/'event-pid', root/'reader-pid'):
                    assert not alive(file.read_text().strip()), file
                assert not session.exists() and not Path(env['READING_UI_LOCK']).exists()
        finally:
            if process.poll() is None:
                process.kill(); process.communicate(timeout=5)
        print(renderer, event, stage, external_power, 'PASS', flush=True)


if __name__ == '__main__':
    for renderer in ('optimized', 'fallback', 'legacy'):
        for event in ('goingToScreenSaver 2', 'goingToScreenSaver 4', 'goingToScreenSaver 0', 'readyToSuspend 10', 'manual'):
            case(renderer, event)
    case('optimized', 'goingToScreenSaver 2', 'fbink')
    case('optimized', 'unused', 'subscription_failure')
    case('optimized', 'manual', external_power='7')
    case('optimized', 'manual', 'exit_race')
    case('optimized', 'unused', 'already_asleep')
    case('optimized', 'manual', 'reopen')
    for mode in ('settings_cover','settings_cover_manage','settings_cover_images','settings_cover_books','settings_cover_info'):
        for renderer in ('optimized','legacy'):
            for event in ('goingToScreenSaver 2','goingToScreenSaver 4'):
                case(renderer,event,cover_mode=mode)
    case('optimized','goingToScreenSaver 2','cover_worker',cover_mode='settings_cover_images')
    print('Power exit: 42 offline integration scenarios PASS; Kindle hardware acceptance PENDING')
