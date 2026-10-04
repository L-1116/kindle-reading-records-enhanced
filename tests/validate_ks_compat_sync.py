"""Exercise KS orientation, firmware refresh and diagnostics with hardware mocks."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
from runtime_fixture import install_python_fixture
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
KS = ROOT / "ks-package/native-reading-time-package"
COMMON = ROOT / "native-reading-time-package"
FIXTURES = ROOT / "tests/fixtures/ks-runtime"
SH = next(path for path in (shutil.which("sh"), r"C:\Program Files\Git\bin\sh.exe") if path and Path(path).is_file())


def script(path: Path, body: str) -> None:
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8", newline="\n")
    path.chmod(0o755)


def setup(root: Path, *, version: str, geometry: str, lock: str, actions: str = "exit\n") -> tuple[Path, dict[str, str]]:
    base = root / "reading-time"
    release = base / "releases/9.7.5-ks-test1"
    docs = root / "documents"
    for path in (base / "bin", base / "compat", base / "fonts", base / "tmp", release / "bin",
                 release / "render-assets", release / "ui-scribe", docs):
        path.mkdir(parents=True)
    shutil.copy2(KS / "阅读记录-ks.sh", release / "bin/reading-records-ks.sh")
    shutil.copy2(KS / "reading-insights-touch-ks.lua", release / "bin/reading-insights-touch-ks.lua")
    shutil.copy2(KS / "reading-insights-touch-probe-ks.lua", release / "bin/reading-insights-touch-probe-ks.lua")
    shutil.copy2(KS / "launch-ks.sh", base / "bin/launch-ks.sh")
    shutil.copy2(KS / "diagnostics-ks.sh", base / "bin/diagnostics-ks.sh")
    shutil.copy2(KS / "install.sh", root / "install-ks.sh")
    shutil.copy2(COMMON / "compat/detect_env.sh", base / "compat/detect_env.sh")
    for helper in ("reading-insights-render.lua", "reading-insights-cache.awk", "reading-insights-cover.lua",
                   "reading-insights-titles.lua", "reading-insights-title-widths.lua"):
        shutil.copy2(COMMON / helper, release / "bin" / helper)
    for asset in ("dynamic-glyphs.tsv", "dynamic-glyphs.pgm"):
        shutil.copy2(COMMON / "render-assets" / asset, release / "render-assets" / asset)
    for image in (KS / "ui-scribe").glob("*.png"):
        shutil.copy2(image, release / "ui-scribe" / image.name)
    install_python_fixture(FIXTURES / "lua", base / "bin/lua-fake")
    script(base / "bin/lua", '''
case "$1" in
    *reading-insights-render.lua) [ "${KS_SIM_RENDER_FAIL:-0}" = 1 ] && exit 9;;
    *reading-insights-touch-ks.lua)
        [ "${KS_SIM_TOUCH_FAIL:-0}" = 1 ] && exit 2
        [ "${KS_SIM_TOUCH_DELAY:-0}" = 0 ] || sleep "$KS_SIM_TOUCH_DELAY"
        if [ "${KS_SIM_TOUCH_BLOCK:-0}" = 1 ]; then
            printf '%s\n' "$$" > "$READING_BASE/touch-child.pid"
            (sleep 1; kill -"${KS_SIM_SIGNAL:-TERM}" "$(cat "$READING_BASE/reading-time-ks-ui.pid")") &
            sleep 20
            exit 0
        fi;;
esac
exec "$READING_BASE/bin/lua-fake" "$@"
''')
    script(base / "bin/fbset", '''
read width height < "$KS_SIM_GEOMETRY"
printf 'mode "%sx%s"\\n    geometry %s %s %s %s 8\\nendmode\\n' "$width" "$height" "$width" "$height" "$width" "$height"
''')
    script(base / "bin/lipc-get-prop", '''
if [ "$2" = orientationLock ]; then
    [ "${KS_SIM_LOCK_FAIL:-0}" = 0 ] || exit 1
    printf '%s\n' "$KS_SIM_LOCK"
else printf 'U\n'; fi
''')
    script(base / "bin/lipc-set-prop", '''
printf '%s %s %s\n' "$1" "$2" "$3" >> "$KS_SIM_LIPC_TRACE"
if [ "$2" = orientationLock ] && [ "$3" = U ]; then
    [ "${KS_SIM_SET_FAIL:-0}" = 0 ] || exit 1
    [ "${KS_SIM_TIMEOUT:-0}" = 0 ] || exit 0
    printf '1860 2480\n' > "$KS_SIM_GEOMETRY"
fi
exit 0
''')
    script(base / "bin/fbink", 'printf "%s\\n" "$*" >> "$KS_SIM_FB_TRACE"\n')
    (base / "fonts/NotoSansCJKsc-Regular.otf").write_bytes(b"")
    (base / "reading-time.tsv").write_text("", encoding="utf-8")
    (base / "actions.txt").write_text(actions, encoding="utf-8")
    (base / "touch-device").write_bytes(b"")
    (root / "prettyversion.txt").write_text(version, encoding="utf-8")
    (root / "geometry.txt").write_text(geometry + "\n", encoding="utf-8")
    for name in ("lipc-trace.txt", "fb-trace.txt"):
        (root / name).write_text("", encoding="utf-8")
    for executable in (base / "bin/launch-ks.sh", release / "bin/reading-records-ks.sh"):
        executable.chmod(0o755)
    env = {
        **os.environ,
        "PATH": (base / "bin").as_posix() + ":/usr/bin:/bin:" + os.environ.get("PATH", ""),
        "READING_BASE": base.as_posix(),
        "READING_DOCUMENTS": docs.as_posix(),
        "READING_FBINK": (base / "bin/fbink").as_posix(),
        "READING_TOUCH_DEVICE": (base / "touch-device").as_posix(),
        "READING_TMPDIR": (base / "tmp").as_posix(),
        "KS_SIM_ACTIONS_FILE": (base / "actions.txt").as_posix(),
        "KS_SIM_GEOMETRY": (root / "geometry.txt").as_posix(),
        "KS_SIM_LIPC_TRACE": (root / "lipc-trace.txt").as_posix(),
        "KS_SIM_FB_TRACE": (root / "fb-trace.txt").as_posix(),
        "KS_SIM_LOCK": lock,
        "READING_PRETTYVERSION_PATH": (root / "prettyversion.txt").as_posix(),
        "READING_VERSION_PATH": (root / "missing-version").as_posix(),
        "READING_DEVICETYPE_PATH": (root / "missing-device").as_posix(),
        "READING_ARMHF_LOADER_PATH": (root / "missing-loader").as_posix(),
        "READING_ARCH_OVERRIDE": "armv7hf",
    }
    return base, env


def run_case(label: str, *, version: str = "5.18.1", geometry: str = "1860 2480",
             lock: str = "U", overrides: dict[str, str] | None = None,
             expected_code: int = 0, expected_restore: str | None = None,
             expect_first_flash: bool | None = None, actions: str = "exit\n") -> None:
    with tempfile.TemporaryDirectory(prefix="ks-compat-") as directory:
        root = Path(directory)
        base, env = setup(root, version=version, geometry=geometry, lock=lock, actions=actions)
        env.update(overrides or {})
        canary = None
        if env.get("KS_SIM_TOUCH_BLOCK") == "1":
            canary = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            result = subprocess.run([SH, (base / "bin/launch-ks.sh").as_posix()], env=env,
                                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=55)
            if canary:
                assert canary.poll() is None, "unrelated process was stopped"
                child = (base / "touch-child.pid").read_text(encoding="utf-8").strip()
                gone = subprocess.run([SH, "-c", f"kill -0 {child} 2>/dev/null"], capture_output=True)
                assert gone.returncode != 0, "session touch child survived TERM"
        finally:
            if canary:
                canary.terminate()
                canary.wait(timeout=5)
        trace = (root / "lipc-trace.txt").read_text(encoding="utf-8")
        fb = (root / "fb-trace.txt").read_text(encoding="utf-8").splitlines()
        debug = (base / "reading_time_ks_debug.log").read_text(encoding="utf-8", errors="replace")
        assert (result.returncode == 0) == (expected_code == 0), (label, result.returncode, result.stdout, result.stderr, debug[-6000:], (base / "last-launch.stderr").read_text(encoding="utf-8", errors="replace"))
        writes = [line for line in trace.splitlines() if "orientationLock" in line]
        if geometry == "1860 2480":
            assert not writes, (label, writes)
        else:
            assert writes and writes[0].endswith("orientationLock U"), (label, writes)
            if expected_restore:
                assert len(writes) == 2 and writes[-1].endswith("orientationLock " + expected_restore), (label, writes)
            else:
                assert len(writes) == 1, (label, writes)
        if expect_first_flash is not None and expected_code == 0:
            full = [line for line in fb if "-W GC16 -s" in line and "top=" not in line]
            assert full and ("-f" in full[0].split()) == expect_first_flash, (label, full[:2])
        assert (base / "last-launch-diagnostic.txt").exists() == (expected_code != 0), label
        if env.get("KS_SIM_TOUCH_FAIL") == "1":
            launch = (base / "launch-last.log").read_text(encoding="utf-8", errors="replace")
            touch = (base / "touch-last.log").read_text(encoding="utf-8", errors="replace")
            assert "error_stage=touch" in launch and "reader_exit_code=2" in touch, label
            assert "KPP_LIBRARY" in trace, label
        assert not list((root / "documents").glob("*diagnostic*.txt")), label
        assert not list((base / "tmp").glob("native-reading-dashboard-ks.*")), label
        print(label + ": PASS")


def refresh_contract() -> None:
    source = (KS / "阅读记录-ks.sh").read_text(encoding="utf-8")
    start = source.index("refresh_region() {")
    function = source[start:source.index("\n}\n", start) + 3]
    with tempfile.TemporaryDirectory(prefix="ks-refresh-") as directory:
        root = Path(directory)
        trace = root / "fb.txt"
        runner = root / "refresh.sh"
        runner.write_text('''#!/bin/sh
CLEAN_REFRESH_INTERVAL=6; draw_count=0; COMPAT_PROFILE=fw518
scale_x() { echo "$1"; }; scale_y() { echo "$1"; }; scale_len() { echo "$1"; }
fb() { printf '%s\\n' "$*" >> "$FB_TRACE"; case "$*" in *GC16_FAST*) return 1;; esac; return 0; }
''' + function + '''
refresh_region 11 22 33 44
refresh_region 11 22 33 44
refresh_region 11 22 33 44
refresh_region 11 22 33 44
refresh_region 11 22 33 44
refresh_region 11 22 33 44
''', encoding="utf-8", newline="\n")
        result = subprocess.run([SH, runner.as_posix()], env={**os.environ, "FB_TRACE": trace.as_posix()},
                                capture_output=True, text=True, timeout=10)
        calls = trace.read_text(encoding="utf-8").splitlines()
        assert result.returncode == 0 and calls[0] == "-q -W GC16 -s", calls
        assert calls[1].endswith("GC16_FAST -s top=22,left=11,width=33,height=44"), calls
        assert calls[2].endswith("GC16 -s top=22,left=11,width=33,height=44"), calls
        assert calls[-1] == "-q -f -W GC16 -s", calls
        print("5.18.1 first, regional fallback and periodic refresh: PASS")


def main() -> None:
    refresh_contract()
    run_case("A/J portrait 5.18.1", expect_first_flash=False)
    run_case("B/K landscape R 5.18.1", geometry="2480 1860", lock="R", expected_restore="R", expect_first_flash=False)
    run_case("C landscape L", geometry="2480 1860", lock="L", expected_restore="L")
    run_case("D portrait unreadable lock", overrides={"KS_SIM_LOCK_FAIL": "1"})
    run_case("E landscape unreadable lock", geometry="2480 1860", lock="", overrides={"KS_SIM_LOCK_FAIL": "1"})
    run_case("F set U fails", geometry="2480 1860", lock="R", overrides={"KS_SIM_SET_FAIL": "1"}, expected_code=1)
    run_case("G geometry timeout", geometry="2480 1860", lock="R", overrides={"KS_SIM_TIMEOUT": "1"}, expected_code=1, expected_restore="R")
    run_case("H renderer failure", geometry="2480 1860", lock="R", overrides={"KS_SIM_RENDER_FAIL": "1"}, expected_code=1, expected_restore="R")
    run_case("I TERM during touch wait", geometry="2480 1860", lock="R", overrides={"KS_SIM_TOUCH_BLOCK": "1"}, expected_code=1, expected_restore="R")
    run_case("I INT during touch wait", geometry="2480 1860", lock="R", overrides={"KS_SIM_TOUCH_BLOCK": "1", "KS_SIM_SIGNAL": "INT"}, expected_code=1, expected_restore="R")
    run_case("I HUP during touch wait", geometry="2480 1860", lock="R", overrides={"KS_SIM_TOUCH_BLOCK": "1", "KS_SIM_SIGNAL": "HUP"}, expected_code=1, expected_restore="R")
    run_case("L 5.18.2", version="5.18.2", expect_first_flash=False)
    run_case("M 5.19.1", version="5.19.1", expect_first_flash=True)
    run_case("N touch reader failure restores Library", version="5.19.6",
             overrides={"KS_SIM_TOUCH_FAIL": "1"}, expected_code=1)
    run_case("O quiet reader waits 11 seconds", version="5.19.6",
             overrides={"KS_SIM_TOUCH_DELAY": "11"})
    with tempfile.TemporaryDirectory(prefix="ks-manual-diagnostic-") as directory:
        root = Path(directory)
        base, env = setup(root, version="5.18.1", geometry="1860 2480", lock="U")
        report = root / "documents/reading-records-ks-diagnostic.txt"
        result = subprocess.run([SH, (root / "install-ks.sh").as_posix(), "diagnostics"], env=env,
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
        assert result.returncode == 0 and report.is_file() and "KS diagnostic" in report.read_text(encoding="utf-8")
        print("S manual diagnostic export: PASS")


if __name__ == "__main__":
    main()
