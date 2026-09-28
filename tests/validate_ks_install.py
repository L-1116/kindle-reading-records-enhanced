"""Exercise the relocatable KS activation twice and prove data preservation."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "dist/ReadingTime-v9.7.5-KS-test1.zip"
SHELL = next(
    path for path in (shutil.which("sh"), r"C:\Program Files\Git\bin\sh.exe")
    if path and Path(path).is_file()
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


with tempfile.TemporaryDirectory(prefix="ks-install-", dir=ROOT / "build") as name:
    sandbox = Path(name)
    usb = sandbox / "us"
    package_root = usb / "native-reading-time-package"
    base = usb / "reading-time"
    documents = usb / "documents"
    mockbin = sandbox / "mockbin"
    for directory in (base / "bin", documents, mockbin):
        directory.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(ARCHIVE) as archive:
        archive.extractall(usb)

    daemon = base / "bin/native-reading-time-daemon.sh"
    daemon.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
    history = base / "reading-time.tsv"
    history.write_text(
        "date\tbook_id\tseconds\ttitle\n"
        "2026-09-27\tB001\t900\tExisting reading data\n",
        encoding="utf-8",
        newline="\n",
    )
    history_before = digest(history)
    fixtures = ROOT / "tests/fixtures/ks-runtime"
    for utility in ("lua", "fbset", "fbink", "lipc-get-prop", "lipc-set-prop"):
        shutil.copy2(fixtures / utility, mockbin / utility)
    subprocess.run(
        [SHELL, "-c", '/usr/bin/chmod 755 "$@"', "test", daemon.as_posix(), *(path.as_posix() for path in mockbin.iterdir())],
        check=True,
    )

    environment = {
        **os.environ,
        "PATH": mockbin.as_posix() + ":/usr/bin:/bin:" + os.environ.get("PATH", ""),
        "READING_PACKAGE_DIR": package_root.as_posix(),
        "READING_BASE": base.as_posix(),
        "READING_DOCUMENTS": documents.as_posix(),
        "READING_MNT_US": usb.as_posix(),
        "READING_ALLOW_NONROOT_TEST": "1",
    }
    installer = package_root / "Install-Native-Reading-Time-KS.sh"
    for attempt in (1, 2):
        result = subprocess.run(
            [SHELL, installer.as_posix()],
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        assert result.returncode == 0, (attempt, result.stdout, result.stderr, (base / "install.log").read_text(errors="replace"))
        assert digest(history) == history_before, attempt
        assert not list(base.glob(".install-9.7.5-ks-test1.*")), attempt

    release = base / "releases/9.7.5-ks-test1"
    assert (release / "bin/reading-records-ks.sh").is_file()
    assert (release / "ui-scribe/daily.png").is_file()
    assert (base / "bin/launch-ks.sh").is_file()
    assert (base / "bin/force-exit-ks.sh").is_file()
    assert (base / "bin/diagnostics-ks.sh").is_file()
    assert (base / "compat/detect_env.sh").is_file()
    assert (documents / "阅读记录.sh").is_file()
    assert (documents / "reading-records-ks-force-exit.sh").is_file()
    assert (usb / "extensions/reading-records-installer/menu.json").is_file()
    assert (base / "VERSION").read_text(encoding="utf-8").strip() == "9.7.5-ks-test1"
    assert not (base / "releases/9.7.5-test/bin/reading-records.sh").exists()

    # Start through the installed launcher, render once, consume an exit touch
    # action and complete normal cleanup. This guards the KS-only entry paths.
    action_file = sandbox / "actions.txt"
    action_file.write_text("exit\n", encoding="utf-8", newline="\n")
    pretty_version = sandbox / "prettyversion.txt"
    pretty_version.write_text("Kindle 5.18.6\n", encoding="utf-8", newline="\n")
    version_file = sandbox / "version.txt"
    version_file.write_text("System Software Version 5.18.6\n", encoding="utf-8", newline="\n")
    device_type = sandbox / "deviceType.txt"
    device_type.write_text("KindleScribe\n", encoding="utf-8", newline="\n")
    armhf_loader = sandbox / "ld-linux-armhf.so.3"
    armhf_loader.write_bytes(b"")
    touch_file = sandbox / "touch-device"
    touch_file.write_bytes(b"")
    runtime_tmp = sandbox / "tmp"
    runtime_tmp.mkdir()
    runtime_environment = {
        **environment,
        "READING_FBINK": (mockbin / "fbink").as_posix(),
        "READING_TOUCH_DEVICE": touch_file.as_posix(),
        "READING_TMPDIR": runtime_tmp.as_posix(),
        "KS_SIM_ACTIONS_FILE": action_file.as_posix(),
        "READING_PRETTYVERSION_PATH": pretty_version.as_posix(),
        "READING_VERSION_PATH": version_file.as_posix(),
        "READING_DEVICETYPE_PATH": device_type.as_posix(),
        "READING_ARCH_OVERRIDE": "armv7l",
        "READING_ARMHF_LOADER_PATH": armhf_loader.as_posix(),
    }
    launch = subprocess.run(
        [SHELL, (base / "bin/launch-ks.sh").as_posix()],
        env=runtime_environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert launch.returncode == 0, (launch.stdout, launch.stderr, (base / "reading_time_ks_debug.log").read_text(errors="replace"))
    debug_log = (base / "reading_time_ks_debug.log").read_text(encoding="utf-8", errors="replace")
    assert "[UI] first paint completed" in debug_log
    assert "[NAV] action=exit" in debug_log
    assert "[EXIT] exit requested" in debug_log
    assert "[EXIT] finished" in debug_log
    assert "[ERROR]" not in debug_log

print("KS transactional install, launcher/render/exit flow and data preservation: PASS")
