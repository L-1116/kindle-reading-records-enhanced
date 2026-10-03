"""Validate firmware parsing, launcher failure capture and safe diagnostics."""

from __future__ import annotations

import atexit
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import json
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "native-reading-time-package"
OUT = ROOT / "build/validation"
OUT.mkdir(parents=True, exist_ok=True)
SANDBOX = Path(tempfile.mkdtemp(prefix="compat-sandbox-", dir=OUT))
assert SANDBOX.resolve().is_relative_to(OUT.resolve())
atexit.register(shutil.rmtree, SANDBOX, ignore_errors=True)
SH = shutil.which("sh") or "C:/Program Files/Git/usr/bin/sh.exe"
DASH = shutil.which("dash") or "C:/Program Files/Git/usr/bin/dash.exe"
SHELL_PATH = "/usr/bin:/bin:" + os.environ.get("PATH", "")

shipped_shell = [
    ROOT / "RUNME.sh",
    ROOT / "documents/reading-records-install.sh",
    ROOT / "documents/reading-records-uninstall.sh",
    *sorted((ROOT / "extensions/reading-records-installer").rglob("*.sh")),
    *sorted(PKG.rglob("*.sh")),
]
for script in shipped_shell:
    assert not script.read_bytes().startswith(b"\xef\xbb\xbf") and b"\r\n" not in script.read_bytes(), script
    for shell in (SH, DASH):
        subprocess.run([shell, "-n", str(script)], check=True, capture_output=True)

ET.parse(ROOT / "extensions/reading-records-installer/config.xml")
ET.parse(PKG / "resources/kual/reading-records-installer/config.xml")
kual_menu = json.loads((ROOT / "extensions/reading-records-installer/menu.json").read_text(encoding="utf-8"))
kual_actions = kual_menu["items"][0]["items"]
assert [item["params"] for item in kual_actions] == ["install", "repair", "diagnostics", "cleanup"]
assert kual_actions[-1]["name"] == "安装文件清理"
assert len({item["action"] for item in kual_actions}) == 1
assert "/native-reading-time-package/install.sh" in (ROOT / "RUNME.sh").read_text(encoding="utf-8")
assert "/native-reading-time-package" in (ROOT / "documents/reading-records-install.sh").read_text(encoding="utf-8")
install_entry = (ROOT / "documents/reading-records-install.sh").read_text(encoding="utf-8")
uninstall_entry = (ROOT / "documents/reading-records-uninstall.sh").read_text(encoding="utf-8")
assert "# Name: 阅读记录安装" in install_entry
assert "# Name: 安装文件清理" in uninstall_entry
assert "uninstall.sh" in uninstall_entry and "install.sh" not in uninstall_entry.replace("uninstall.sh", "")
canonical_pairs = {
    ROOT / "documents/reading-records-uninstall.sh": PKG / "resources/reading-records-uninstall.sh",
    ROOT / "extensions/reading-records-installer/bin/action.sh": PKG / "resources/kual/reading-records-installer/bin/action.sh",
    ROOT / "extensions/reading-records-installer/config.xml": PKG / "resources/kual/reading-records-installer/config.xml",
    ROOT / "extensions/reading-records-installer/menu.json": PKG / "resources/kual/reading-records-installer/menu.json",
}
assert all(deployed.read_bytes() == canonical.read_bytes() for deployed, canonical in canonical_pairs.items())


def run_shell(code: str, env: dict[str, str], check: bool = True) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged.update(env)
    result = subprocess.run(
        [SH, "-c", code], capture_output=True, text=True, encoding="utf-8", errors="replace", env=merged
    )
    if check and result.returncode:
        raise AssertionError((result.returncode, result.stdout, result.stderr))
    return result


pretty = SANDBOX / "prettyversion.txt"
version_txt = SANDBOX / "version.txt"
device_type = SANDBOX / "deviceType.txt"
loader = SANDBOX / "ld-linux-armhf.so.3"
loader.write_text("mock", encoding="utf-8")
device_type.write_text("KindleMock\n", encoding="utf-8")
detect_env = PKG / "compat/detect_env.sh"

cases = {
    "5.19.0": "default",
    "5.18": "fw518",
    "5.18.0": "fw518",
    "5.18.1": "fw518",
    "5.18.1.2": "fw518",
    "5.18.1.1.1": "fw518",
    "5.18.2": "fw518",
    "5.18.4": "fw518",
    "5.18.10": "fw518",
    "5.18.5": "fw518",
    "5.18.5.0.1": "fw518",
    "5.18.6": "fw518",
    "5.17.1.0.4": "default",
}
for firmware, expected_profile in cases.items():
    pretty.write_text(f"Kindle Firmware Version {firmware} (mock build)\n", encoding="utf-8")
    version_txt.write_text("System Software Version fallback\n", encoding="utf-8")
    result = subprocess.run(
        [SH, "-c", '. "$1"; printf "%s|%s|%s|%s|%s|%s\\n" "$FIRMWARE_FULL" "$FIRMWARE_MAJOR" "$FIRMWARE_MINOR" "$DEVICE_TYPE" "$HARD_FLOAT" "$COMPAT_PROFILE"', "test", detect_env.as_posix()],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PATH": SHELL_PATH, "READING_PRETTYVERSION_PATH": pretty.as_posix(), "READING_VERSION_PATH": version_txt.as_posix(), "READING_DEVICETYPE_PATH": device_type.as_posix(), "READING_ARMHF_LOADER_PATH": loader.as_posix()},
        check=True,
    )
    assert result.stdout.strip() == f"{firmware}|5|{firmware.split('.')[1]}|KindleMock|1|{expected_profile}", result.stdout

# Numeric comparison must not regress to lexical ordering.
comparison = subprocess.run(
    [SH, "-c", '. "$1"; printf "%s|%s|%s|%s\\n" "$(version_compare 5.18.10 5.18.2)" "$(version_compare 5.18.2 5.18.10)" "$(version_compare 5.18 5.18.0.0)" "$DEVICE_TYPE"', "test", detect_env.as_posix()],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    env={**os.environ, "PATH": SHELL_PATH, "READING_PRETTYVERSION_PATH": pretty.as_posix(), "READING_VERSION_PATH": version_txt.as_posix(), "READING_DEVICETYPE_PATH": (SANDBOX / "missing-device.txt").as_posix(), "READING_ARMHF_LOADER_PATH": loader.as_posix()},
    check=True,
)
assert comparison.stdout.strip() == "1|-1|0|unknown", comparison.stdout

# Build a minimal installed tree. sqlite3/unzip are deliberately not mocked:
# they are optional and must not be launch gates.
base = SANDBOX / "reading-time"
docs = SANDBOX / "documents"
release = base / "releases/9.7.5-test"
mockbin = SANDBOX / "mockbin"
for folder in (base / "bin", base / "compat", base / "fonts", release / "bin", release / "ui-calendar", release / "render-assets", docs, mockbin):
    folder.mkdir(parents=True, exist_ok=True)
shutil.copy2(detect_env, base / "compat/detect_env.sh")
shutil.copy2(PKG / "diagnostics.sh", base / "bin/diagnostics.sh")
shutil.copy2(PKG / "launch.sh", base / "bin/launch.sh")
(base / "reading-time.tsv").write_text("date\tbook_id\tseconds\ttitle\n", encoding="utf-8")
(base / "fonts/NotoSansCJKsc-Regular.otf").write_bytes(b"font")
for name in ("daily.png", "total.png", "books.png", "day_detail.png", "month_detail.png", "week_trend.png", "book_detail.png"):
    (release / "ui-calendar" / name).write_bytes(b"png")
for name in ("reading-insights-touch-ui.lua", "reading-insights-render.lua", "reading-insights-cover.lua", "reading-insights-titles.lua", "reading-insights-title-widths.lua"):
    (release / "bin" / name).write_text("return true\n", encoding="utf-8")
for name in ("dynamic-glyphs.pgm", "dynamic-glyphs.tsv"):
    (release / "render-assets" / name).write_text("mock\n", encoding="utf-8")
main = release / "bin/reading-records.sh"
main.write_text('#!/bin/sh\necho "launcher-ok profile=$COMPAT_PROFILE"\nexit 0\n', encoding="utf-8", newline="\n")
fbink = mockbin / "fbink"
fbink.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
lua = mockbin / "lua"
lua.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
lipc_calls = SANDBOX / "lipc-calls.txt"
lipc = mockbin / "lipc-set-prop"
lipc.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$READING_TEST_LIPC_LOG"\n', encoding="utf-8", newline="\n")
subprocess.run([SH, "-c", '/usr/bin/chmod 755 "$@"', "test", (base / "bin/launch.sh").as_posix(), (base / "bin/diagnostics.sh").as_posix(), main.as_posix(), fbink.as_posix(), lua.as_posix(), lipc.as_posix()], check=True)

launch_env = {
    "READING_BASE": base.as_posix(),
    "READING_DOCUMENTS": docs.as_posix(),
    "READING_MNT_US": SANDBOX.as_posix(),
    "READING_FBINK": fbink.as_posix(),
    "READING_PRETTYVERSION_PATH": pretty.as_posix(),
    "READING_VERSION_PATH": version_txt.as_posix(),
    "READING_DEVICETYPE_PATH": device_type.as_posix(),
    "READING_ARMHF_LOADER_PATH": loader.as_posix(),
    "READING_TEST_LIPC_LOG": lipc_calls.as_posix(),
    "PATH": mockbin.as_posix() + ":/usr/bin:/bin:" + os.environ.get("PATH", ""),
}
pretty.write_text("Kindle 5.18.6\n", encoding="utf-8")
success = subprocess.run([SH, (base / "bin/launch.sh").as_posix()], capture_output=True, text=True, encoding="utf-8", errors="replace", env={**os.environ, **launch_env})
assert success.returncode == 0, (success.stdout, success.stderr)
assert "launcher-ok" in (base / "last-launch.stdout").read_text(encoding="utf-8")
success_status = (base / "last-launch-status.txt").read_text(encoding="utf-8")
assert "stage=complete" in success_status, success_status

# Firmware labels are logged, but a successful executable probe decides
# whether a runtime can launch even when the loader heuristic says soft-float.
for firmware, expected_profile in cases.items():
    pretty.write_text(f"Kindle {firmware}\n", encoding="utf-8")
    result = subprocess.run([SH, (base / "bin/launch.sh").as_posix()], capture_output=True, env={**os.environ, **launch_env})
    assert result.returncode == 0, (firmware, result.stderr)
    assert f"profile={expected_profile}" in (base / "last-launch.stdout").read_text(encoding="utf-8")
    result = subprocess.run(
        [SH, (base / "bin/launch.sh").as_posix()], capture_output=True,
        env={**os.environ, **launch_env, "READING_ARMHF_LOADER_PATH": (SANDBOX / "missing-loader").as_posix(), "READING_ARCH_OVERRIDE": "armv7l"},
    )
    assert result.returncode == 0, (firmware, result.stderr)
pretty.write_text("Kindle 5.18.6\n", encoding="utf-8")

main.write_text("#!/bin/sh\necho simulated-ui-failure >&2\nexit 7\n", encoding="utf-8", newline="\n")
failure = subprocess.run([SH, (base / "bin/launch.sh").as_posix()], capture_output=True, text=True, encoding="utf-8", errors="replace", env={**os.environ, **launch_env})
assert failure.returncode == 7, failure
status = (base / "last-launch-status.txt").read_text(encoding="utf-8")
assert "stage=ui" in status and "exit_code=7" in status
diagnostic = base / "last-launch-diagnostic.txt"
report = diagnostic.read_text(encoding="utf-8")
assert all(section in report for section in ("[Device]", "[Compatibility]", "[Jailbreak]", "[KUAL/MRPI]", "[Plugin]", "[Dependencies]", "[Last Launch]"))
assert "compat_profile=fw518" in report and "simulated-ui-failure" in report
assert f"missing: {SANDBOX.as_posix()}/extensions/MRInstaller" in report
assert "token=" not in report.lower() and "password=" not in report.lower()
assert not (docs / "reading-records-diagnostic.txt").exists()
assert not (docs / "阅读记录诊断.txt").exists()

# A manual invocation keeps the existing USB-exportable reports.
manual = subprocess.run([SH, (base / "bin/diagnostics.sh").as_posix()], capture_output=True, env={**os.environ, **launch_env})
assert manual.returncode == 0, manual.stderr
assert (docs / "reading-records-diagnostic.txt").read_bytes() == (docs / "阅读记录诊断.txt").read_bytes()
assert "simulated-ui-failure" in (docs / "reading-records-diagnostic.txt").read_text(encoding="utf-8")

# Preflight failures must occur before the UI can alter the framebuffer.
history_before = (base / "reading-time.tsv").read_bytes()
font_before = (base / "fonts/NotoSansCJKsc-Regular.otf").read_bytes()
def launch(extra: dict[str, str] | None = None) -> tuple[int, str]:
    lipc_calls.unlink(missing_ok=True)
    result = subprocess.run([SH, (base / "bin/launch.sh").as_posix()], capture_output=True,
                            env={**os.environ, **launch_env, **(extra or {})})
    log = (base / "launch-last.log").read_text(encoding="utf-8", errors="replace")
    for key in ("timestamp", "firmware", "kernel", "machine", "arch", "detected_env",
                "hard_float", "selected_runtime", "selected_lua", "selected_fbink",
                "ui_entry", "screen_width", "screen_height", "orientation",
                "launch_command", "primary_probe_result", "fallback_used",
                "exit_code", "error_stage"):
        assert f"{key}=" in log, key
    assert (base / "reading-time.tsv").read_bytes() == history_before
    if (base / "fonts/NotoSansCJKsc-Regular.otf").exists():
        assert (base / "fonts/NotoSansCJKsc-Regular.otf").read_bytes() == font_before
    if result.returncode:
        assert "com.lab126.appmgrd start app://com.lab126.KPPMainApp?view=KPP_LIBRARY" in lipc_calls.read_text(encoding="utf-8")
    return result.returncode, log

main.rename(main.with_suffix(".missing"))
code, log = launch()
assert code == 50 and "error_stage=preflight" in log
main.with_suffix(".missing").rename(main)
main_source = main.read_text(encoding="utf-8")
main.write_text("#!/bin/sh\nif then\n", encoding="utf-8", newline="\n")
code, log = launch()
assert code == 53 and "error_stage=preflight" in log
main.write_text(main_source, encoding="utf-8", newline="\n")
font = base / "fonts/NotoSansCJKsc-Regular.otf"
font.rename(font.with_suffix(".missing"))
code, log = launch()
assert code == 51 and "error_stage=preflight" in log
font.with_suffix(".missing").rename(font)

lua.rename(lua.with_suffix(".missing"))
code, log = launch()
assert code == 32 and "primary_probe_result=lua:failed" in log
lua.with_suffix(".missing").rename(lua)

broken = mockbin / "broken-fbink"
broken.write_text("#!/bin/sh\necho primary-probe-error >&2\nexit 6\n", encoding="utf-8", newline="\n")
subprocess.run([SH, "-c", '/usr/bin/chmod 755 "$1"', "test", broken.as_posix()], check=True)
code, log = launch({"READING_FBINK": broken.as_posix()})
assert code == 7 and "fbink_fallback_reason=" in log and "fallback_used=1" in log
assert any(line.startswith("selected_fbink=") and line.endswith("/mockbin/fbink") for line in log.splitlines()) and "primary-probe-error" in log, log

fbink.rename(fbink.with_suffix(".missing"))
code, log = launch({"READING_FBINK": broken.as_posix()})
assert code == 31 and "error_stage=preflight" in log
fbink.with_suffix(".missing").rename(fbink)

main.write_text('#!/bin/sh\necho run-marker\nexit 0\n', encoding="utf-8", newline="\n")
code, log = launch()
assert code == 0 and "run-marker" in log and "primary-probe-error" not in log
assert log.count("timestamp=") == 1 and (base / "launch-last.log").stat().st_size < 10000

# Internal mode ignores a inherited manual destination and does not even
# require/create the documents directory.
internal_docs = SANDBOX / "absent-documents"
internal = subprocess.run([DASH, (base / "bin/diagnostics.sh").as_posix()], capture_output=True, env={
    **os.environ, **launch_env, "READING_DOCUMENTS": internal_docs.as_posix(),
    "READING_DIAGNOSTIC_INTERNAL": "1", "READING_DIAGNOSTIC_PATH": (internal_docs / "override.txt").as_posix(),
})
assert internal.returncode == 0 and not internal_docs.exists(), internal.stderr

# The automatic entry failure (launcher absent) must be internal as well.
missing_base = SANDBOX / "missing-launcher"
(missing_base / "bin").mkdir(parents=True)
shutil.copy2(PKG / "diagnostics.sh", missing_base / "bin/diagnostics.sh")
missing_docs = SANDBOX / "entry-documents"
entry = SANDBOX / "entry.sh"
entry.write_text((PKG / "阅读记录-entry.sh").read_text(encoding="utf-8").replace(
    "/mnt/us/reading-time", missing_base.as_posix(),
), encoding="utf-8", newline="\n")
for shell in (SH, DASH):
    result = subprocess.run([shell, entry.as_posix()], capture_output=True, env={
        **os.environ, **launch_env, "READING_BASE": missing_base.as_posix(),
        "READING_DOCUMENTS": missing_docs.as_posix(), "READING_DETECT_ENV": detect_env.as_posix(),
    })
    assert result.returncode == 127 and not missing_docs.exists(), result.stderr
    assert (missing_base / "last-launch-diagnostic.txt").exists()
    assert (missing_base / "reading-records-launch-error.txt").exists()

print("compatibility parser, launcher capture and diagnostics: PASS")
