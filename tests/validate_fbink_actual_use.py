"""Run both complete dashboards against actual-command FBInk fixtures.

The permanent regression fixture crashes on -e but succeeds on every command
used by the UI. No device-side probes or user action are needed.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
from runtime_fixture import install_python_fixture
import subprocess
import tempfile

from validate_runtime_probe import ROOT, OUT, SH, executable, setup, shell_path


FIRMWARES = ("5.17.1.0.4", "5.18", "5.18.0", "5.18.1", "5.18.1.1.1",
             "5.18.1.2", "5.18.2", "5.18.4", "5.18.5", "5.18.5.0.1",
             "5.18.6", "5.18.10", "5.19.1", "5.19.2", "5.19.5", "5.19.6")
RESULTS = []


def check(variant: str) -> None:
    with tempfile.TemporaryDirectory(prefix="actual-fbink-", dir=OUT) as name:
        root = Path(name)
        launcher, env, pretty, _ = setup(root, variant)
        launcher.write_text(launcher.read_text(encoding="utf-8").replace('/mnt/us/libkh/bin/fbink', shell_path(root / 'alternate/third-fbink')), encoding="utf-8", newline="\n")
        base = launcher.parent.parent
        package = ROOT / ("native-reading-time-package" if variant == "standard" else "ks-package/native-reading-time-package")
        release = base / ("releases/9.7.5-test" if variant == "standard" else "releases/9.7.5-ks-test1")
        main = release / "bin" / ("reading-records.sh" if variant == "standard" else "reading-records-ks.sh")
        source = (package / ("阅读记录-optimized.sh" if variant == "standard" else "阅读记录-ks.sh")).read_text(encoding="utf-8")
        if variant == "standard":
            source = source.replace('/tmp/native-reading-dashboard.', shell_path(root) + '/native-reading-dashboard.')
        main.write_text(source, encoding="utf-8", newline="\n")
        for helper in ("reading-insights-cache.awk", "reading-insights-render.lua", "reading-insights-cover.lua",
                       "reading-insights-titles.lua", "reading-insights-title-widths.lua"):
            shutil.copyfile(ROOT / "native-reading-time-package" / helper, release / "bin" / helper)
        (release / "bin/reading-records-v9.6.3.sh").write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
        fake_lua = root / "mockbin/lua-fake"
        install_python_fixture(ROOT / "tests/fixtures/ks-runtime/lua", fake_lua)
        executable(root / "mockbin/lua", '[ -z "${READING_PROBE_SOURCE:-}" ] || [ -r "$READING_PROBE_SOURCE" ] || exit 2\n'
                   'case "$1" in *reading-insights-touch-ui.lua) echo exit; exit 0;; esac\n'
                   'exec "${0%/*}/lua-fake" "$@"\n')
        executable(root / "mockbin/uname", 'case "$1" in -m) echo armv7l;; -r) echo "$ACTUAL_TEST_KERNEL";; esac\n')
        executable(root / "mockbin/fbset", 'echo "geometry $ACTUAL_TEST_SCREEN $ACTUAL_TEST_SCREEN 8"\n')
        touch = root / "touch-device"
        touch.write_bytes(b"")
        env["PATH"] = shell_path(root / "mockbin") + ":/usr/bin:/bin:" + env["PATH"]
        env.update(READING_TOUCH_DEVICE=touch.as_posix(), READING_TMPDIR=root.as_posix(),
                   READING_VERSION_PATH=(root / "absent-version").as_posix(),
                   READING_DEVICETYPE_PATH=(root / "absent-device").as_posix())
        # Reuse the complete legacy screen as a second real FBInk consumer.
        # It must honor the runtime chosen by the optimized parent.
        if variant == "standard":
            legacy = (ROOT / "native-reading-time-package/阅读记录.sh").read_text(encoding="utf-8")
            for folder in (base / "ui",):
                folder.mkdir()
            (base / "ui/total.png").write_bytes(b"png")
            (base / "bin/reading-insights-touch.lua").write_text("return true\n", encoding="utf-8")
            executable(root / "mockbin/lua", '[ -z "${READING_PROBE_SOURCE:-}" ] || [ -r "$READING_PROBE_SOURCE" ] || exit 2\n'
                   'case "$1" in *reading-insights-touch-ui.lua|*reading-insights-touch.lua) echo exit; exit 0;; esac\n'
                       'exec "${0%/*}/lua-fake" "$@"\n')
            selected = shell_path(root / "alternate/fbink")
            legacy_main = root / "legacy.sh"
            legacy_main.write_text(legacy, encoding="utf-8", newline="\n")
            result = subprocess.run([SH, legacy_main.as_posix()], env={**env, "READING_FBINK": selected,
                                    "READING_LAUNCHER_CAPTURE": "1", "ACTUAL_TEST_SCREEN": "1072 1448",
                                    "PRIMARY_FBINK_MODE": "signal"}, capture_output=True, timeout=25)
            assert result.returncode == 0 and f"selected_fbink={selected}" in result.stdout.decode("utf-8", errors="replace"), result

        # Never run -e from the launcher. Prove explicitly that the fixture
        # would crash there, then clear that trace before checking startup.
        for candidate in (root / "mockbin/fbink", root / "alternate/fbink"):
            result = subprocess.run([SH, candidate.as_posix(), "-e"], env=env, capture_output=True, timeout=5)
            assert result.returncode == 139

        def run_case(firmware: str, screen: str, label: str, code: int = 0, **changes: str) -> tuple[str, list[str]]:
            pretty.write_text(f"Kindle {firmware}\n", encoding="utf-8")
            (root / "fb-calls.txt").write_text("", encoding="utf-8")
            (root / "lipc.txt").write_text("", encoding="utf-8")
            kernel = "4.1.15-lab126" if firmware.startswith("5.18") else "5.15.41-lab126" if firmware == "5.19.5" else "4.9.77-lab126"
            result = subprocess.run([SH, launcher.as_posix()], env={**env, "ACTUAL_TEST_SCREEN": screen,
                                    "ACTUAL_TEST_KERNEL": kernel, **changes}, capture_output=True, timeout=30)
            log = (base / "launch-last.log").read_text(encoding="utf-8", errors="replace")
            calls = (root / "fb-calls.txt").read_text(encoding="utf-8").splitlines()
            assert result.returncode == code, (label, result.returncode, log)
            assert not any(c.endswith(" -e") for c in calls), calls
            lipc = (root / "lipc.txt").read_text(encoding="utf-8")
            assert "eatTapMode 0" in lipc and "preventScreenSaver 0" in lipc and "KPP_LIBRARY" in lipc, (label, lipc)
            assert f"firmware={firmware}" in log and "arch=armv7l" in log and "hard_float=1" in log
            if code == 0:
                assert "actual_fbink_first_command_result=ok" in log and "FBINK_LOCKED=1" in log
                assert "touch_listener_begin" in (base / "dashboard-startup-stage.txt").read_text(encoding="utf-8") if variant == "standard" else "[UI] first paint completed" in (base / "reading_time_ks_debug.log").read_text(encoding="utf-8")
                refresh = [c for c in calls if "-W GC16 -s" in c]
                assert refresh, calls
                assert (" -f " not in refresh[0]) == firmware.startswith("5.18"), refresh
            else:
                assert "fbink_runtime_failure=1" in log and "failing_command=" in log
                if variant == "ks":
                    assert "touch_support_begin" in log and "touch_support_end" in log
                assert (base / "last-launch-status.txt").read_text(encoding="utf-8").endswith("error=UI process exited unexpectedly\n")
                # Cleanup must not call the known failing binary a second time.
                assert len(calls) <= 3, calls
            RESULTS.append({"variant": variant, "firmware": firmware, "screen": screen, "case": label,
                            "exit_code": code, "fbink_calls": len(calls), "result": "PASS"})
            print(variant, firmware, screen, label, "PASS", flush=True)
            return log, calls

        versions = FIRMWARES if variant == "standard" else ("5.18", "5.18.1.1.1", "5.18.10", "5.19.6")
        for firmware in versions:
            for screen in (("1072 1448", "1272 1696") if variant == "standard" else ("1860 2480",)):
                _, calls = run_case(firmware, screen, "probe=139/actual=0")
                assert all(c.startswith("PRIMARY ") for c in calls)
        screen = "1072 1448" if variant == "standard" else "1860 2480"
        log, calls = run_case("5.19.6", screen, "A=139/B=0", PRIMARY_FBINK_MODE="signal")
        assert f"selected_fbink={shell_path(root / 'alternate')}/fbink" in log
        assert calls[0].removeprefix("PRIMARY ") == calls[1].removeprefix("FALLBACK ")
        assert len([c for c in calls if c.startswith("PRIMARY ")]) == 1
        executable(root / "alternate/third-fbink", 'printf "THIRD %s\\n" "$*" >> "$READING_TEST_FB_CALLS"\nexit 7\n')
        run_case("5.19.6", screen, "all actual commands fail", 31,
                 PRIMARY_FBINK_MODE="signal", FALLBACK_FBINK_MODE="nonzero")


if __name__ == "__main__":
    for variant in ("standard", "ks"):
        check(variant)
    (OUT / "fbink-actual-use-results.json").write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
