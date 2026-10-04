"""Run the real dashboard startup, traps and fallback with hardware mocks."""

from pathlib import Path
import atexit
import os
import shlex
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "native-reading-time-package"
OUT = ROOT / "build/validation"
OUT.mkdir(parents=True, exist_ok=True)
SH = shutil.which("sh") or "C:/Program Files/Git/usr/bin/sh.exe"
DASH = shutil.which("dash") or "C:/Program Files/Git/usr/bin/dash.exe"
viewer = (PKG / "阅读记录-optimized.sh").read_text(encoding="utf-8")
prefix, startup = viewer.split("\ndetect_screen; find_touch_device", 1)


def quote(path):
    return shlex.quote(path.relative_to(ROOT).as_posix())


with tempfile.TemporaryDirectory(prefix="orientation-", dir=OUT) as directory:
    session = Path(directory)
    # Verify the complete production child selector without real signals.
    fixture = session / "process-stat"
    root_stat = session / "root-stat"
    fixture.write_text("100 (dashboard fallback) S 1 0\n101 (shell) S 100 0\n102 (touch reader) S 101 0\n200 (unrelated) S 1 0\n201 (other reader) S 200 0\n", encoding="utf-8")
    selector_start = viewer.index("stop_ui_child()")
    selector = viewer[selector_start:viewer.index("\n}\n", selector_start) + 3]
    selector = selector.replace("/proc/[0-9]*/stat", quote(fixture))
    selector = selector.replace('"/proc/$stopping_pid/stat"', quote(root_stat)).replace('-v owner="$$"', '-v owner=1')
    selector_script = session / "selector.sh"
    selection_trace = session / "selection-trace"
    selector_script.write_text(f"SELECTION_TRACE={quote(selection_trace)}\n" + '''kill() { printf 'kill %s\n' "$*" >> "$SELECTION_TRACE"; }
wait() { printf 'wait %s\n' "$*" >> "$SELECTION_TRACE"; }
''' + selector + "\nstop_ui_child 100\n", encoding="utf-8", newline="\n")
    for shell in (SH, DASH):
        root_stat.write_text("100 (our child) S 1 0\n", encoding="utf-8")
        selection_trace.write_text("", encoding="utf-8")
        selected = subprocess.run([shell, selector_script.as_posix()], cwd=ROOT, capture_output=True, text=True, check=True,
                                  env={**os.environ, "PATH": "/usr/bin:/bin:" + os.environ.get("PATH", "")})
        lines = selection_trace.read_text(encoding="utf-8").splitlines()
        assert lines[0] == "kill -STOP 100" and lines[-2:] == ["kill -KILL 100", "wait 100"], lines
        assert set(lines[1].split()) == {"kill", "-TERM", "101", "102"}, lines
        root_stat.write_text("100 (reused unrelated pid) S 200 0\n", encoding="utf-8")
        selection_trace.write_text("", encoding="utf-8")
        subprocess.run([shell, selector_script.as_posix()], cwd=ROOT, capture_output=True, check=True,
                       env={**os.environ, "PATH": "/usr/bin:/bin:" + os.environ.get("PATH", "")})
        assert selection_trace.read_text().splitlines() == []

    # An unrelated process must survive every real signal/cleanup scenario.
    canary_pid = session / "canary-pid"
    canary_script = session / "canary.sh"
    canary_script.write_text(f"echo $$ > {quote(canary_pid)}\nexec /bin/sleep 600\n", encoding="utf-8", newline="\n")
    canary = subprocess.Popen([SH, canary_script.as_posix()], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 5
    while not canary_pid.exists() or not canary_pid.read_text().strip():
        assert time.monotonic() < deadline and canary.poll() is None
        time.sleep(0.01)
    canary_id = int(canary_pid.read_text().strip())

    def stop_canary():
        if canary.poll() is None:
            subprocess.run([SH, "-c", f"kill -TERM {canary_id} 2>/dev/null"], capture_output=True)
        canary.wait(timeout=5)

    atexit.register(stop_canary)
    base = session / "reading-time"
    release = base / "releases/9.7.5-test"
    for folder in (release / "bin", release / "ui-calendar", base / "fonts"):
        folder.mkdir(parents=True)
    for name in ("total", "day_detail", "month_detail", "week_trend", "book_detail"):
        (release / f"ui-calendar/{name}.png").write_bytes(b"mock")
    (base / "reading-time.tsv").write_text("mock", encoding="utf-8")
    (base / "fonts/NotoSansCJKsc-Regular.otf").write_bytes(b"font")
    touch = session / "touch"
    touch.write_bytes(b"mock")
    (release / "bin/reading-insights-touch-ui.lua").write_bytes(b"mock")
    trace = session / "trace"
    state = session / "orientation"
    count = session / "geometry-reads"
    ui_pid = session / "ui-pid"
    reader_pid = session / "reader-pid"
    blocked_reader = session / "blocked-reader.sh"
    blocked_reader.write_text('''#!/bin/sh
echo $$ > "$READER_PID"
echo BLOCKED_READER >> "$TRACE"
/bin/sleep 0.1
kill -"$BLOCK_SIGNAL" "$(cat "$UI_PID")"
exec /bin/sleep 30
''', encoding="utf-8", newline="\n")
    pretty = session / "prettyversion.txt"
    script = session / "run.sh"
    mockbin = session / "mockbin"
    mockbin.mkdir()
    get_prop = mockbin / "lipc-get-prop"
    get_prop.write_text('''#!/bin/sh
echo GET >> "$TRACE"
printf '%s\n' "$ORIGINAL"
exit "${GET_EXIT:-0}"
''', encoding="utf-8", newline="\n")
    set_prop = mockbin / "lipc-set-prop"
    set_prop.write_text('''#!/bin/sh
printf 'LIPC %s\n' "$*" >> "$TRACE"
if [ "$2" = orientationLock ]; then
    if [ "$3" = U ]; then
        [ "$SET_FAIL" = 1 ] && exit 1
        echo U > "$STATE"
        [ -z "$SET_SIGNAL" ] || kill -"$SET_SIGNAL" "$(cat "$UI_PID")"
    else
        [ "$RESTORE_FAIL" = 1 ] && exit 1
        echo "$3" > "$STATE"
    fi
fi
exit 0
''', encoding="utf-8", newline="\n")
    fbink = session / "fbink"
    fbink.write_text('''#!/bin/sh
printf 'FB %s\n' "$*" >> "$TRACE"
exit 0
''', encoding="utf-8", newline="\n")
    legacy = release / "bin/reading-records-v9.6.3.sh"
    legacy.write_text('''#!/bin/sh
printf 'LEGACY orientation=%s\n' "$(cat "$STATE")" >> "$TRACE"
if [ -n "$FALLBACK_SIGNAL" ]; then
    # Parent must terminate a fallback that traps TERM without exiting.
    trap ':' TERM
    kill -"$FALLBACK_SIGNAL" "$(cat "$UI_PID")"
    while :; do /bin/sleep 1; done
fi
exit "${LEGACY_EXIT:-0}"
''', encoding="utf-8", newline="\n")
    subprocess.run([SH, "-c", '/usr/bin/chmod 755 "$@"', "test", fbink.as_posix(), blocked_reader.as_posix(), get_prop.as_posix(), set_prop.as_posix()], check=True)
    setup = f'''
. {quote(PKG / "compat/detect_env.sh")}
TRACE={quote(trace)}; STATE={quote(state)}; COUNT={quote(count)}; UI_PID={quote(ui_pid)}
export TRACE STATE UI_PID
printf '%s\n' "$$" > "$UI_PID"
'''
    mocks = '''
fbset() {
    n=$(cat "$COUNT"); n=$((n+1)); echo "$n" > "$COUNT"
    if [ "$BAD_GEOMETRY" = 1 ]; then return 1; fi
    if [ "$INITIAL_PORTRAIT" = 1 ] || { [ "$(cat "$STATE")" = U ] && [ "$n" -ge "$PORTRAIT_AT" ]; }; then
        echo 'geometry 1272 1696 1272 3392 8'
    else echo 'geometry 1696 1272 1696 2544 8'; fi
}
cat() {
    if [ "$1" = /sys/class/graphics/fb0/virtual_size ]; then echo "${VIRTUAL_SIZE:-invalid}";
    else command cat "$@"; fi
}
sleep() {
    printf 'SLEEP %s\n' "$*" >> "$TRACE"
    case "$1" in 0.*) command sleep "$@"; return;; esac
    [ -z "$WAIT_SIGNAL" ] || kill -"$WAIT_SIGNAL" "$$"
}
find_touch_device() { TOUCH="$READING_TOUCH_DEVICE"; }
remove_session() { echo REMOVE_SESSION >> "$TRACE"; }
metric_begin() { :; }; metric_end() { :; }
build_cache() { today_date=2026-10-02; }
draw_background() { [ "${DRAW_FAIL:-0}" != 1 ]; }
draw_dynamic() { [ "$mode" = daily ] || { [ "$FALLBACK" != 1 ] && [ "$FAIL_LATER" != 1 ]; }; }
weekday_offset() { echo 3; }; days_in_month() { echo 31; }
lua() {
    echo UI_READY >> "$TRACE"
    if [ -n "$BLOCK_SIGNAL" ]; then exec "$BLOCK_READER"; fi
    [ -z "$UI_SIGNAL" ] || kill -"$UI_SIGNAL" "$$"
    if [ "$FAIL_LATER" = 1 ] || [ "$FALLBACK" = 1 ]; then echo tab_total; else echo exit; fi
}
'''
    # Actual UI resource checks, first refresh, listener boundary and exit.
    # Function overrides bypass statistics/rendering, never real hardware.
    relocated = prefix.replace('BASE="${READING_BASE:-/mnt/us/reading-time}"', f"BASE={quote(base)}")
    relocated = relocated.replace('SESSION_DIR="/tmp/native-reading-dashboard.$$"', f"SESSION_DIR={quote(session / 'cache')}")
    source = setup + relocated + mocks
    source += "\ndetect_screen; find_touch_device" + startup.replace(
        '\necho "$(date): optimized dashboard closed"',
        '\n[ "${CLEANUP_TWICE:-0}" != 1 ] || { cleanup; cleanup; }\necho "$(date): optimized dashboard closed"',
    )
    script.write_text(source, encoding="utf-8", newline="\n")
    defaults = {
        "INITIAL_PORTRAIT": "0", "ORIGINAL": "R", "PORTRAIT_AT": "2", "GET_EXIT": "0",
        "SET_FAIL": "0", "RESTORE_FAIL": "0", "BAD_GEOMETRY": "0", "FALLBACK": "0",
        "FAIL_LATER": "0", "UI_SIGNAL": "", "SET_SIGNAL": "", "FALLBACK_SIGNAL": "",
        "BLOCK_SIGNAL": "", "BLOCK_READER": blocked_reader.as_posix(), "READER_PID": reader_pid.as_posix(),
        "WAIT_SIGNAL": "",
        "READING_LAUNCHER_CAPTURE": "1", "READING_FBINK": fbink.as_posix(),
        "READING_TOUCH_DEVICE": touch.as_posix(), "READING_PRETTYVERSION_PATH": pretty.as_posix(),
        "READING_VERSION_PATH": (session / "absent-version").as_posix(),
        "READING_DEVICETYPE_PATH": (session / "absent-device").as_posix(),
        "READING_ARMHF_LOADER_PATH": (session / "absent-loader").as_posix(),
        "PATH": mockbin.as_posix() + ":/usr/bin:/bin:" + os.environ.get("PATH", ""),
    }
    scenarios = [
        ("portrait", {"INITIAL_PORTRAIT": "1", "ORIGINAL": "U"}, 0, []),
        ("portrait-get-fails", {"INITIAL_PORTRAIT": "1", "GET_EXIT": "1"}, 0, []),
        ("landscape-R", {}, 0, ["U", "R"]),
        ("landscape-L-delayed", {"ORIGINAL": "L", "PORTRAIT_AT": "4"}, 0, ["U", "L"]),
        ("landscape-D", {"ORIGINAL": "D"}, 0, ["U", "D"]),
        ("landscape-U-stale", {"ORIGINAL": "U"}, 0, ["U", "U"]),
        ("get-fails", {"GET_EXIT": "1"}, 0, ["U"]),
        ("invalid-lock", {"ORIGINAL": "auto"}, 0, ["U"]),
        ("set-fails", {"SET_FAIL": "1"}, 1, ["U"]),
        ("timeout", {"PORTRAIT_AT": "99"}, 1, ["U", "R"]),
        ("last-poll-succeeds", {"PORTRAIT_AT": "6"}, 0, ["U", "R"]),
        ("early-resource-fail", {"REMOVE_FONT": "1"}, 1, ["U", "R"]),
        ("fbink-draw-fail", {"DRAW_FAIL": "1"}, 1, ["U", "R"]),
        ("later-ui-fail", {"FAIL_LATER": "1", "LEGACY_EXIT": "7"}, 7, ["U", "R"]),
        ("fallback", {"FALLBACK": "1"}, 0, ["U", "R"]),
        ("fallback-unknown-lock", {"FALLBACK": "1", "GET_EXIT": "1"}, 0, ["U"]),
        ("portrait-fallback", {"FALLBACK": "1", "INITIAL_PORTRAIT": "1"}, 0, []),
        ("cleanup-twice", {"CLEANUP_TWICE": "1"}, 0, ["U", "R"]),
        ("restore-fails", {"RESTORE_FAIL": "1"}, 0, ["U", "R"]),
        ("invalid-geometry", {"BAD_GEOMETRY": "1"}, 1, []),
        ("sysfs-portrait", {"BAD_GEOMETRY": "1", "VIRTUAL_SIZE": "1272,3392"}, 0, []),
    ]
    for sig, code in (("INT", 130), ("TERM", 143), ("HUP", 129)):
        scenarios.extend([
            (f"ui-{sig}", {"UI_SIGNAL": sig}, code, ["U", "R"]),
            (f"set-{sig}", {"SET_SIGNAL": sig}, code, ["U", "R"]),
            (f"fallback-{sig}", {"FALLBACK": "1", "FALLBACK_SIGNAL": sig}, code, ["U", "R"]),
            (f"blocked-reader-{sig}", {"BLOCK_SIGNAL": sig}, code, ["U", "R"]),
            (f"rotation-wait-{sig}", {"WAIT_SIGNAL": sig, "PORTRAIT_AT": "99"}, code, ["U", "R"]),
        ])
    checks = 0
    for shell in (SH, DASH):
        for firmware in ("5.18.1", "5.18.2", "5.19.1"):
            pretty.write_text(f"Kindle {firmware}\n", encoding="utf-8")
            for label, overrides, code, expected_sets in scenarios:
                trace.write_text("", encoding="utf-8")
                state.write_text("initial", encoding="utf-8")
                count.write_text("0", encoding="utf-8")
                reader_pid.unlink(missing_ok=True)
                font = base / "fonts/NotoSansCJKsc-Regular.otf"
                font.write_bytes(b"font")
                if overrides.get("REMOVE_FONT") == "1":
                    font.unlink()
                try:
                    result = subprocess.run(
                        [shell, script.as_posix()], cwd=ROOT, capture_output=True,
                        text=True, encoding="utf-8", errors="replace", timeout=15,
                        env={**os.environ, **defaults, **overrides},
                    )
                except subprocess.TimeoutExpired as exc:
                    context = (shell, firmware, label, trace.read_text(encoding="utf-8"), exc.stdout, exc.stderr)
                    (OUT / "orientation-failure-context.txt").write_text(repr(context), encoding="utf-8")
                    raise AssertionError(context) from exc
                rows = trace.read_text(encoding="utf-8").splitlines()
                sets = [row.split()[-1] for row in rows if row.startswith("LIPC com.lab126.winmgr orientationLock ")]
                assert result.returncode == code, (shell, firmware, label, result.returncode, result.stdout, result.stderr, rows)
                assert sets == expected_sets, (label, sets, rows)
                for index, row in enumerate(rows):
                    if row == "LIPC com.lab126.appmgrd start app://com.lab126.KPPMainApp?view=KPP_LIBRARY":
                        restore_refresh = next((item for item in rows[index + 1:] if item.startswith("FB ")), None)
                        assert restore_refresh is None, (label, firmware, restore_refresh, rows)
                assert canary.poll() is None, (label, "unrelated process was terminated")
                if len(expected_sets) == 2:
                    expected_restored = "U" if overrides.get("RESTORE_FAIL") == "1" else expected_sets[-1]
                    assert state.read_text().strip() == expected_restored, (label, state.read_text())
                if label.startswith("portrait") or label == "sysfs-portrait":
                    assert "GET" not in rows and int(count.read_text()) == 1
                if code == 0 and overrides.get("FALLBACK") != "1":
                    first = next(row for row in rows if row.startswith("FB "))
                    assert first == ("FB -q -W GC16 -s" if firmware.startswith("5.18.") else "FB -q -f -W GC16 -s"), (label, first)
                    assert "UI_READY" in rows
                    before_refresh = rows[:rows.index(first)]
                    sleeps = sum(row == "SLEEP 1" for row in before_refresh)
                    expected_sleeps = 2 if label == "landscape-L-delayed" else 4 if label == "last-poll-succeeds" else 0
                    assert sleeps == expected_sleeps, (label, sleeps)
                if label == "timeout":
                    assert int(count.read_text()) == 6 and rows.count("SLEEP 1") == 4
                    assert "result=timeout" in result.stdout and "UI_READY" not in rows
                if label == "set-fails":
                    assert int(count.read_text()) == 1 and not any(row.startswith("SLEEP") for row in rows)
                if overrides.get("FALLBACK") == "1" or overrides.get("FAIL_LATER") == "1":
                    expected_orientation = "initial" if overrides.get("INITIAL_PORTRAIT") == "1" else "U"
                    assert f"LEGACY orientation={expected_orientation}" in rows
                if label == "later-ui-fail":
                    assert "UI_READY" in rows and "dashboard action=tab_total" in result.stdout
                if reader_pid.exists():
                    reader = reader_pid.read_text().strip()
                    stopped = subprocess.run([shell, "-c", f"kill -0 {reader} 2>/dev/null"], capture_output=True)
                    assert stopped.returncode != 0, (label, "reader leaked", reader, rows)
                if len(expected_sets) == 2 and not overrides.get("SET_SIGNAL"):
                    assert f"orientation_restore={overrides.get('ORIGINAL', 'R')}" in result.stdout, (shell, label, result.stdout)
                checks += 1

stop_canary()
atexit.unregister(stop_canary)
print(f"orientation startup: PASS ({checks} real startup/cleanup/fallback scenarios; sh + dash; three firmware versions; child scope and unrelated process preserved)")
