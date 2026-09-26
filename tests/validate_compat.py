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
    "5.18.1": "fw518",
    "5.18.1.1.1": "fw518",
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
for folder in (base / "bin", base / "compat", base / "fonts", release / "bin", release / "ui-calendar", docs, mockbin):
    folder.mkdir(parents=True, exist_ok=True)
shutil.copy2(detect_env, base / "compat/detect_env.sh")
shutil.copy2(PKG / "diagnostics.sh", base / "bin/diagnostics.sh")
shutil.copy2(PKG / "launch.sh", base / "bin/launch.sh")
(base / "reading-time.tsv").write_text("date\tbook_id\tseconds\ttitle\n", encoding="utf-8")
(base / "fonts/NotoSansCJKsc-Regular.otf").write_bytes(b"font")
(release / "ui-calendar/daily.png").write_bytes(b"png")
main = release / "bin/reading-records.sh"
main.write_text("#!/bin/sh\necho launcher-ok\nexit 0\n", encoding="utf-8", newline="\n")
fbink = mockbin / "fbink"
fbink.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
lua = mockbin / "lua"
lua.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
subprocess.run([SH, "-c", '/usr/bin/chmod 755 "$@"', "test", (base / "bin/launch.sh").as_posix(), (base / "bin/diagnostics.sh").as_posix(), main.as_posix(), fbink.as_posix(), lua.as_posix()], check=True)

launch_env = {
    "READING_BASE": base.as_posix(),
    "READING_DOCUMENTS": docs.as_posix(),
    "READING_MNT_US": SANDBOX.as_posix(),
    "READING_FBINK": fbink.as_posix(),
    "READING_PRETTYVERSION_PATH": pretty.as_posix(),
    "READING_VERSION_PATH": version_txt.as_posix(),
    "READING_DEVICETYPE_PATH": device_type.as_posix(),
    "READING_ARMHF_LOADER_PATH": loader.as_posix(),
    "PATH": mockbin.as_posix() + ":/usr/bin:/bin:" + os.environ.get("PATH", ""),
}
pretty.write_text("Kindle 5.18.6\n", encoding="utf-8")
success = subprocess.run([SH, (base / "bin/launch.sh").as_posix()], capture_output=True, text=True, encoding="utf-8", errors="replace", env={**os.environ, **launch_env})
assert success.returncode == 0, (success.stdout, success.stderr)
assert "launcher-ok" in (base / "last-launch.stdout").read_text(encoding="utf-8")
success_status = (base / "last-launch-status.txt").read_text(encoding="utf-8")
assert "stage=complete" in success_status, success_status

main.write_text("#!/bin/sh\necho simulated-ui-failure >&2\nexit 7\n", encoding="utf-8", newline="\n")
failure = subprocess.run([SH, (base / "bin/launch.sh").as_posix()], capture_output=True, text=True, encoding="utf-8", errors="replace", env={**os.environ, **launch_env})
assert failure.returncode == 7, failure
status = (base / "last-launch-status.txt").read_text(encoding="utf-8")
assert "stage=ui" in status and "exit_code=7" in status
diagnostic = docs / "reading-records-diagnostic.txt"
report = diagnostic.read_text(encoding="utf-8")
assert all(section in report for section in ("[Device]", "[Compatibility]", "[Jailbreak]", "[KUAL/MRPI]", "[Plugin]", "[Dependencies]", "[Last Launch]"))
assert "compat_profile=fw518" in report and "simulated-ui-failure" in report
assert f"missing: {SANDBOX.as_posix()}/extensions/MRInstaller" in report
assert "token=" not in report.lower() and "password=" not in report.lower()
assert (docs / "阅读记录诊断.txt").exists()

print("compatibility parser, launcher capture and diagnostics: PASS")
