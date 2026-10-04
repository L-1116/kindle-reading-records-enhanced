"""Exercise bounded Lua checks and actual-use FBInk resolution in both launchers."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
SH = shutil.which("sh") or r"C:\Program Files\Git\bin\sh.exe"
OUT = ROOT / "build/validation"
OUT.mkdir(parents=True, exist_ok=True)
FIRMWARES = ("5.18", "5.18.0", "5.18.1", "5.18.1.1.1", "5.18.1.2", "5.18.2",
             "5.18.4", "5.18.5", "5.18.5.0.1", "5.18.6", "5.18.10")


def executable(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8", newline="\n")
    path.chmod(0o755)


def shell_path(path: Path) -> str:
    return f"/{path.drive[0].lower()}{path.as_posix()[2:]}" if path.drive else path.as_posix()


def setup(root: Path, variant: str) -> tuple[Path, dict[str, str], Path, Path]:
    package = ROOT / ("native-reading-time-package" if variant == "standard" else "ks-package/native-reading-time-package")
    base = root / "reading-time"
    release = base / ("releases/9.7.5-test" if variant == "standard" else "releases/9.7.5-ks-test1")
    mock = root / "mockbin"
    alternate = root / "alternate"
    ui = "ui-calendar" if variant == "standard" else "ui-scribe"
    for directory in (base / "bin", base / "compat", base / "fonts", release / "bin", release / ui,
                      release / "render-assets", mock, alternate):
        directory.mkdir(parents=True, exist_ok=True)
    launcher_name = "launch.sh" if variant == "standard" else "launch-ks.sh"
    launcher = base / "bin" / launcher_name
    source = (package / launcher_name).read_text(encoding="utf-8")
    source = source.replace("STAGE=runtime_probe\n", 'STAGE=runtime_probe\nprintf "%s\\n" "$$" > "$BASE/launcher-test.pid"\n', 1)
    source = source.replace("/mnt/us/libkh/bin/lua /usr/bin/lua /usr/local/bin/lua",
                            f"{shell_path(alternate)}/lua {shell_path(alternate)}/lua-missing")
    source = source.replace('fbink_candidate_add /var/local/kmc/bin/fbink',
                            f'fbink_candidate_add {shell_path(alternate)}/fbink')
    launcher.write_text(source, encoding="utf-8", newline="\n")
    shutil.copy2(ROOT / "native-reading-time-package/compat/detect_env.sh", base / "compat/detect_env.sh")
    (base / "reading-time.tsv").write_text("date\tbook_id\tseconds\ttitle\n", encoding="utf-8")
    (base / "fonts/NotoSansCJKsc-Regular.otf").write_bytes(b"font")
    (release / "render-assets/dynamic-glyphs.pgm").write_bytes(b"pgm")
    (release / "render-assets/dynamic-glyphs.tsv").write_bytes(b"tsv")
    for name in ("daily", "total", "books", "day_detail", "month_detail", "week_trend", "book_detail"):
        (release / ui / f"{name}.png").write_bytes(b"png")
    lua_sources = ["reading-insights-render.lua", "reading-insights-cover.lua", "reading-insights-titles.lua",
                   "reading-insights-title-widths.lua"]
    lua_sources += (["reading-insights-touch-ui.lua"] if variant == "standard" else
                    ["reading-insights-touch-probe-ks.lua", "reading-insights-touch-ks.lua"])
    for name in lua_sources:
        (release / "bin" / name).write_text("return true\n", encoding="utf-8")
    main = release / "bin" / ("reading-records.sh" if variant == "standard" else "reading-records-ks.sh")
    viewer = (package / ("阅读记录-optimized.sh" if variant == "standard" else "阅读记录-ks.sh")).read_text(encoding="utf-8")
    wrapper = viewer[viewer.index("# Candidate resolution"):viewer.index("\not() {", viewer.index("# Candidate resolution"))]
    executable(main, 'fbink_calls=0\nFBINK=$READING_FBINK\n' + wrapper +
               '\ntrap fbink_stop_child EXIT\n'
               'printf "ui_process_entered=1\\n"\n'
               'fb -q -b -B WHITE -k "top=0,left=0,width=1072,height=1448"\n'
               'fb -q -W GC16 -s\n'
               'fb -q -f -W GC16 -s\n'
               'fb -q -b -g "file=background.png,x=0,y=0,w=1072,h=1448"\n'
               'fb -q -b -t "regular=font,px=28" "阅读记录"\n'
               'printf "ui_entered=1\\nui_lua=%s\\nui_lua_path=%s\\nui_fbink=%s\\n" "$READING_LUA_BINARY" "$(command -v lua)" "$READING_FBINK"\n')
    executable(mock / "lua", 'printf "%s\\n" "$$" >> "$READING_TEST_CHILDREN"\n'
               '[ -z "${READING_PROBE_SOURCE:-}" ] || [ -r "$READING_PROBE_SOURCE" ] || exit 2\n'
               'case "${PRIMARY_LUA_MODE:-ok}" in hang) exec sleep 30;; nonzero) exit 6;; signal) exit 139;; syntax) [ -z "${READING_PROBE_SOURCE:-}" ] || exit 2;; esac\nexit 0\n')
    executable(alternate / "lua", 'printf "%s\\n" "$$" >> "$READING_TEST_CHILDREN"\n'
               '[ -z "${READING_PROBE_SOURCE:-}" ] || [ -r "$READING_PROBE_SOURCE" ] || exit 2\n'
               'case "${FALLBACK_LUA_MODE:-ok}" in hang) exec sleep 30;; nonzero) exit 6;; signal) exit 139;; esac\nexit 0\n')
    executable(mock / "fbink", 'printf "%s\\n" "$$" >> "$READING_TEST_CHILDREN"\n'
               'printf "PRIMARY %s\\n" "$*" >> "$READING_TEST_FB_CALLS"\n'
               '[ "$1" != -e ] || exit 139\n'
               'case "${PRIMARY_FBINK_MODE:-ok}" in hang) exec sleep 30;; nonzero) exit 6;; signal) exit 139;; esac\nexit 0\n')
    executable(alternate / "fbink", 'printf "%s\\n" "$$" >> "$READING_TEST_CHILDREN"\n'
               'printf "FALLBACK %s\\n" "$*" >> "$READING_TEST_FB_CALLS"\n'
               '[ "$1" != -e ] || exit 139\n'
               'case "${FALLBACK_FBINK_MODE:-ok}" in hang) exec sleep 30;; nonzero) exit 6;; signal) exit 139;; esac\nexit 0\n')
    executable(mock / "fbset", 'echo "geometry 1072 1448 1072 1448 8"\n')
    executable(mock / "lipc-set-prop", 'printf "%s\\n" "$*" >> "$READING_TEST_LIPC"\n')
    pretty = root / "prettyversion.txt"
    pretty.write_text("Kindle 5.18.1.1.1\n", encoding="utf-8")
    loader = root / "ld-linux-armhf.so.3"
    loader.write_bytes(b"loader")
    children = root / "children.txt"
    env = {**os.environ, "READING_BASE": base.as_posix(), "READING_FBINK": (mock / "fbink").as_posix(),
           "READING_PRETTYVERSION_PATH": pretty.as_posix(), "READING_ARMHF_LOADER_PATH": loader.as_posix(),
           "READING_ARCH_OVERRIDE": "armv7l", "READING_TEST_CHILDREN": children.as_posix(),
           "READING_TEST_FB_CALLS": (root / "fb-calls.txt").as_posix(),
           "READING_TEST_LIPC": (root / "lipc.txt").as_posix(),
           "PATH": mock.as_posix() + ":/usr/bin:/bin:" + os.environ.get("PATH", "")}
    return launcher, env, pretty, children


def run(launcher: Path, env: dict[str, str], **changes: str) -> tuple[int, str]:
    result = subprocess.run([SH, launcher.as_posix()], env={**env, **changes}, capture_output=True, timeout=25)
    log = (launcher.parent.parent / "launch-last.log").read_text(encoding="utf-8", errors="replace")
    return result.returncode, log


def assert_timed_out_children_gone(log: str) -> None:
    child = ""
    timed_out: set[str] = set()
    for line in log.splitlines():
        if line.startswith("probe_child_pid="):
            child = line.split("=", 1)[1]
        elif line.endswith("_result=timeout") and child:
            timed_out.add(child)
    assert timed_out, log
    for pid in timed_out:
        alive = subprocess.run([SH, "-c", 'kill -0 "$1" 2>/dev/null', "test", pid], capture_output=True)
        assert alive.returncode != 0, pid


def check(variant: str) -> None:
    with tempfile.TemporaryDirectory(prefix="runtime-probe-", dir=OUT) as name:
        root = Path(name)
        launcher, env, pretty, children = setup(root, variant)
        base = launcher.parent.parent
        code, log = run(launcher, env)
        assert code == 0 and "lua_primary_result=ok" in log and "actual_fbink_first_command_result=ok" in log, log
        assert "launch_command=" in log and "ui_entered=1" in log
        assert "screen_width=1072\nscreen_height=1448\norientation=portrait" in log
        versions = (FIRMWARES if variant == "standard" else
                    ("5.18.1", "5.18.1.1.1", "5.18.2", "5.18.4", "5.18.6", "5.18.10"))
        for firmware in versions + ("5.17.1.0.4", "5.19.1", "5.19.2", "5.19.5", "5.19.6"):
            pretty.write_text(f"Kindle {firmware}\n", encoding="utf-8")
            code, log = run(launcher, env)
            assert code == 0 and f"detected_env={'fw518' if firmware.startswith('5.18') else 'default'}" in log, (variant, firmware, log)
        pretty.write_text("Kindle 5.18.1.1.1\n", encoding="utf-8")
        for mode, result in (("nonzero", "nonzero_exit"), ("signal", "signal"), ("hang", "timeout")):
            code, log = run(launcher, env, PRIMARY_LUA_MODE=mode)
            assert code == 0 and f"lua_primary_result={result}" in log and "lua_fallback_1_result=ok" in log, (variant, mode, log)
            assert "fallback_used=1" in log and "ui_entered=1" in log
            assert "ui_lua_path=" in log and "/alternate/lua" in log
            if variant == "ks":
                assert f"ui_lua={shell_path(root / 'alternate')}/lua" in log
            if mode == "hang":
                assert_timed_out_children_gone(log)
        code, log = run(launcher, env, PRIMARY_LUA_MODE="syntax")
        assert code == 0 and "lua_primary_result=syntax_probe_failed" in log and "lua_fallback_1_result=ok" in log
        for mode, rc in (("nonzero", 6), ("signal", 139), ("hang", 124)):
            (root / "fb-calls.txt").write_text("", encoding="utf-8")
            code, log = run(launcher, env, PRIMARY_FBINK_MODE=mode)
            assert code == 0 and f"exit_code={rc}" in log and "fallback_used=1" in log, log
            assert f"selected_fbink={shell_path(root / 'alternate')}/fbink" in log, log
            calls = (root / "fb-calls.txt").read_text(encoding="utf-8").splitlines()
            assert len([c for c in calls if c.startswith("PRIMARY ")]) == 1, calls
            assert calls[0].removeprefix("PRIMARY ") == calls[1].removeprefix("FALLBACK "), calls
            assert len([c for c in calls if c.startswith("FALLBACK ")]) == 5, calls
        (root / "fb-calls.txt").write_text("", encoding="utf-8")
        code, log = run(launcher, env)
        calls = (root / "fb-calls.txt").read_text(encoding="utf-8").splitlines()
        assert len(calls) == 5 and all(c.startswith("PRIMARY ") and c != "PRIMARY -e" for c in calls), calls
        assert log.count("FBINK_LOCKED=1") == 1 and "duplicate_of=" in log, log
        # Distinct paths with byte-identical contents must not be tried twice.
        fallback = root / "alternate/fbink"
        original = fallback.read_bytes()
        shutil.copyfile(root / "mockbin/fbink", fallback)
        code, log = run(launcher, env, PRIMARY_FBINK_MODE="signal")
        assert code == 31 and log.count("fbink_actual_attempt ") == 1 and "duplicate_of=" in log, log
        fallback.write_bytes(original)
        for mode in ("nonzero", "signal", "hang"):
            code, log = run(launcher, env, PRIMARY_FBINK_MODE=mode, FALLBACK_FBINK_MODE=mode)
            assert code == 31 and "fbink_runtime_failure=1" in log and "failing_command=" in log, log
            assert "ui_entered=1" not in log and "error_stage=ui" in log, log
            assert "stage=ui" in (base / "last-launch-status.txt").read_text(encoding="utf-8")
            assert "com.lab126.appmgrd start app://com.lab126.KPPMainApp?view=KPP_LIBRARY" in (root / "lipc.txt").read_text(encoding="utf-8")
        # A missing primary is observed, then the exact fallback path is selected.
        missing = root / "missing-lua"
        (root / "mockbin/lua").rename(missing)
        code, log = run(launcher, env)
        assert code == 0 and "lua_primary_result=missing" in log and "lua_fallback_1_result=ok" in log, log
        missing.rename(root / "mockbin/lua")
        code, log = run(launcher, env, READING_FBINK=(root / "missing-fbink").as_posix())
        assert code == 0 and "result=not_executable" in log and "actual_fbink_first_command_result=ok" in log, log
        code, log = run(launcher, env, PRIMARY_LUA_MODE="hang", FALLBACK_LUA_MODE="hang")
        assert code == 32 and "lua_primary_result=timeout" in log and "lua_fallback_1_result=timeout" in log, log
        assert_timed_out_children_gone(log)
        assert "error_stage=runtime_probe" in log and "selected_runtime=none" in log
        assert "stage=runtime_probe" in (base / "last-launch-status.txt").read_text(encoding="utf-8")
        assert "com.lab126.appmgrd start app://com.lab126.KPPMainApp?view=KPP_LIBRARY" in (root / "lipc.txt").read_text(encoding="utf-8")
        # The watchdog never targets an unrelated process.
        unrelated = subprocess.Popen([SH, "-c", "exec sleep 20"])
        try:
            code, log = run(launcher, env, PRIMARY_LUA_MODE="hang")
            assert code == 0 and unrelated.poll() is None
        finally:
            unrelated.terminate()
            unrelated.wait(timeout=5)
        for signal in ("INT", "TERM", "HUP"):
            children.write_text("", encoding="ascii")
            launched = subprocess.Popen([SH, launcher.as_posix()], env={**env, "PRIMARY_LUA_MODE": "hang"},
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    if children.exists() and children.read_text(encoding="ascii").strip():
                        break
                    time.sleep(0.05)
                else:
                    raise AssertionError((variant, signal, "probe did not start"))
                child_pid = children.read_text(encoding="ascii").splitlines()[-1]
                launcher_pid = (base / "launcher-test.pid").read_text(encoding="ascii").strip()
                sent = subprocess.run([SH, "-c", f'kill -{signal} "$1"', "test", launcher_pid], capture_output=True)
                assert sent.returncode == 0, (signal, sent.stderr)
                launched.communicate(timeout=8)
                assert launched.returncode == 70, (variant, signal, launched.returncode)
                assert "stage=interrupted" in (base / "last-launch-status.txt").read_text(encoding="utf-8")
                alive = subprocess.run([SH, "-c", 'kill -0 "$1" 2>/dev/null', "test", child_pid])
                assert alive.returncode != 0, (variant, signal, child_pid)
            finally:
                if launched.poll() is None:
                    launched.kill()
                    launched.communicate(timeout=5)
        print(variant, "runtime probe PASS", flush=True)


if __name__ == "__main__":
    standard_source = (ROOT / "native-reading-time-package/launch.sh").read_text(encoding="utf-8")
    ks_source = (ROOT / "ks-package/native-reading-time-package/launch-ks.sh").read_text(encoding="utf-8")
    for begin, end in (("STAGE=runtime_probe\n", "probe_lua() {"),
                       ("# Keep the historical KMC", "STAGE=runtime_probe\n")):
        assert standard_source.split(begin, 1)[1].split(end, 1)[0] == ks_source.split(begin, 1)[1].split(end, 1)[0], begin
    for variant in ("standard", "ks"):
        check(variant)
