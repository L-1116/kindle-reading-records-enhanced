"""Execute real startup/refresh shell paths with background-only hardware mocks."""

from pathlib import Path
import os
import shlex
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "native-reading-time-package"
OUT = ROOT / "build/validation"
OUT.mkdir(parents=True, exist_ok=True)
SH = shutil.which("sh") or "C:/Program Files/Git/usr/bin/sh.exe"
DASH = shutil.which("dash") or "C:/Program Files/Git/usr/bin/dash.exe"
viewer = (PKG / "阅读记录-optimized.sh").read_text(encoding="utf-8")
baseline = (ROOT / "tests/baselines/v9.6.10/阅读记录-optimized.sh").read_text(encoding="utf-8")


def function(source: str, name: str) -> str:
    start = source.index(name + "()")
    return source[start:source.index("\n}\n", start) + 3]


def quote(path: Path) -> str:
    return shlex.quote(path.relative_to(ROOT).as_posix())


def run(shell: str, source: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    # A file avoids Windows command-line length limits for the real event loop.
    with tempfile.TemporaryDirectory(prefix="refresh-harness-", dir=OUT) as directory:
        script = Path(directory) / "run.sh"
        script.write_text(source, encoding="utf-8", newline="\n")
        return subprocess.run(
            [shell, script.as_posix()], cwd=ROOT, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=30,
            env={**os.environ, "PATH": "/usr/bin:/bin:" + os.environ.get("PATH", ""), **env},
        )


with tempfile.TemporaryDirectory(prefix="startup-refresh-", dir=OUT) as directory:
    session = Path(directory)
    pretty = session / "prettyversion.txt"
    commands = session / "commands.txt"
    trace = session / "stages.txt"
    calls = session / "touch-calls.txt"
    stage_path = session / "dashboard-startup-stage.txt"
    detector_env = {
        "READING_PRETTYVERSION_PATH": pretty.as_posix(),
        "READING_VERSION_PATH": (session / "missing-version").as_posix(),
        "READING_DEVICETYPE_PATH": (session / "missing-device").as_posix(),
        "READING_ARMHF_LOADER_PATH": (session / "missing-loader").as_posix(),
        "READING_ARCH_OVERRIDE": "armv7l",
    }
    setup = f'''
. {quote(PKG / "compat/detect_env.sh")}
BASE={quote(session)}
COMMANDS={quote(commands)}
TRACE={quote(trace)}
TOUCH_CALLS={quote(calls)}
SCREEN_W=1072; SCREEN_H=1448; VIEW_W=1072; VIEW_H=1429
ORIGIN_X=0; ORIGIN_Y=9; SCALE_NUM=1072; SCALE_DEN=1272
TOUCH=/dev/input/event7; TOUCH_READER=mock-touch.lua
CLEAN_REFRESH_INTERVAL=6; draw_count=0; fbink_calls=0
FBINK=mock_fbink
scale_x() {{ echo $((ORIGIN_X+$1*SCALE_NUM/SCALE_DEN)); }}
scale_y() {{ echo $((ORIGIN_Y+$1*SCALE_NUM/SCALE_DEN)); }}
scale_len() {{ echo $(($1*SCALE_NUM/SCALE_DEN)); }}
{viewer[viewer.index('fb()'):viewer.index('ot()')]}
mock_fbink() {{
    printf '%s\\n' "$*" >> "$COMMANDS"
    [ "${{STOP_REFRESH:-0}}" = 1 ] && exit 88
    case "$*" in *GC16_FAST*) return "${{FAIL_FAST:-0}}";; esac
    return "${{FAIL_FULL:-0}}"
}}
'''
    firmware_cases = ["5.18.1", "5.18.1.2", "5.18.1.1.1", "5.18.0", "5.18.2", "5.18.10", "5.18.6", "5.19.1", "5.17.1", "unknown"]
    comparisons = 0
    for shell in (SH, DASH):
        for firmware in firmware_cases:
            pretty.write_text(f"Kindle {firmware}\n", encoding="utf-8")
            for fail_fast in (0, 7):
                logs = []
                for source in (baseline, viewer):
                    commands.write_text("", encoding="utf-8")
                    result = run(shell, setup + function(source, "refresh_region") + '''
i=0
while [ "$i" -lt 18 ]; do refresh_region 55 460 1162 1168; i=$((i+1)); done
printf '%s|%s|%s\\n' "$draw_count" "$refresh_kind" "$fbink_calls"
''', {**detector_env, "FAIL_FAST": str(fail_fast)})
                    assert result.returncode == 0, result.stderr
                    logs.append(commands.read_text(encoding="utf-8").splitlines())
                    assert result.stdout.startswith("18|GC16|"), result.stdout
                expected = logs[0].copy()
                if firmware == "5.18.1" or firmware.startswith("5.18.1."):
                    assert expected[0] == "-q -f -W GC16 -s"
                    expected[0] = "-q -W GC16 -s"
                assert logs[1] == expected, (shell, firmware, fail_fast, logs)
                comparisons += 1

    # Run the actual first-frame and event-loop source. Mocks replace drawing,
    # input and metrics; refresh_region and the stage writer remain production.
    startup = viewer[viewer.index("\nfirst_refresh_mode=GC16_flash"):viewer.index('\necho "$(date): optimized dashboard closed"')]
    stage_writer = function(viewer, "startup_stage")
    traced_writer = stage_writer.replace("startup_stage()", "write_real_stage()") + '''
startup_stage() {
    write_real_stage "$@"
    if [ -f "$BASE/dashboard-startup-stage.txt" ]; then
        cat "$BASE/dashboard-startup-stage.txt" >> "$TRACE"
    fi
    return 0
}
'''
    mocks = '''
mode=daily; daily_y=2026; daily_m=10; detail_pages=1; detail_page=1
DETAIL_TOP=1222; DETAIL_H=406; DETAIL_PAGER_H=52
metric_begin() { :; }; metric_end() { :; }
build_cache() { today_date=2026-10-02; }
draw_background() { [ "${STOP_RENDER:-0}" = 1 ] && exit 87; return 0; }
draw_dynamic() { :; }; fallback_to_legacy() { exit 89; }
weekday_offset() { echo 3; }; days_in_month() { echo 31; }
lua() {
    # This snapshot must already exist before the first listener invocation.
    if [ -f "$BASE/dashboard-startup-stage.txt" ]; then
        grep -q '^stage=touch_listener_begin$' "$BASE/dashboard-startup-stage.txt" || return 9
    fi
    if [ -s "$TOUCH_CALLS" ]; then echo exit; else echo tab_daily; fi
    echo invoked >> "$TOUCH_CALLS"
    return "${FAIL_TOUCH:-0}"
}
'''
    expected_stages = ["first_render_begin", "first_render_done", "first_refresh_begin", "first_refresh_done", "touch_listener_begin"]
    startup_checks = 0
    for shell in (SH, DASH):
        for firmware in ("5.18.1", "5.18.2", "5.19.1"):
            pretty.write_text(f"Kindle {firmware}\n", encoding="utf-8")
            for scenario in ({}, {"STOP_RENDER": "1"}, {"STOP_REFRESH": "1"}, {"FAIL_FULL": "7"}, {"FAIL_TOUCH": "2"}):
                for path in (commands, trace, calls):
                    path.write_text("", encoding="utf-8")
                stage_path.unlink(missing_ok=True)
                result = run(shell, setup + function(viewer, "refresh_region") + traced_writer + mocks + startup, {**detector_env, **scenario})
                rows = trace.read_text(encoding="utf-8").splitlines()
                observed = [row.removeprefix("stage=") for row in rows if row.startswith("stage=")]
                expected_count = 1 if "STOP_RENDER" in scenario else 3 if "STOP_REFRESH" in scenario else 5
                assert observed == expected_stages[:expected_count], (scenario, observed, result.stderr)
                assert result.returncode == (87 if "STOP_RENDER" in scenario else 88 if "STOP_REFRESH" in scenario else 0), result
                snapshot = stage_path.read_text(encoding="utf-8")
                assert f"firmware={firmware}\n" in snapshot and "screen=1072x1448\n" in snapshot
                assert "viewport=1072x1429+0+9\n" in snapshot and "touch=/dev/input/event7\n" in snapshot
                expected_mode = "GC16_nonflash" if firmware == "5.18.1" else "GC16_flash"
                assert f"refresh={expected_mode}\n" in snapshot and "timestamp=" in snapshot
                expected_status = "unknown" if expected_count < 5 else scenario.get("FAIL_FULL", "0")
                assert f"refresh_exit_code={expected_status}\n" in snapshot, snapshot
                if expected_count == 5:
                    # Re-entering the listener after a no-op tap adds no stages.
                    assert len(calls.read_text().splitlines()) == (1 if "FAIL_TOUCH" in scenario else 2)
                startup_checks += 1

        # A failed diagnostic write cannot prevent rendering or input startup.
        stage_path.unlink(missing_ok=True)
        stage_path.mkdir()
        for path in (commands, trace, calls):
            path.write_text("", encoding="utf-8")
        result = run(shell, setup + function(viewer, "refresh_region") + stage_writer + mocks + startup, detector_env)
        assert result.returncode == 0 and len(calls.read_text().splitlines()) == 2, result
        stage_path.rmdir()

print(f"startup refresh: PASS ({comparisons} baseline command comparisons, {startup_checks} stage/failure scenarios, sh + dash; diagnostic write failures ignored)")
