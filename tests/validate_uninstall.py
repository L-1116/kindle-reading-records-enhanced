"""Exercise safe uninstall edge cases against a redirected Kindle filesystem."""

from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "native-reading-time-package"
OUT = ROOT / "build/validation"
OUT.mkdir(parents=True, exist_ok=True)
SANDBOX = Path(tempfile.mkdtemp(prefix="uninstall-sandbox-", dir=OUT))
assert SANDBOX.resolve().is_relative_to(OUT.resolve())
atexit.register(shutil.rmtree, SANDBOX, ignore_errors=True)
SH = shutil.which("sh") or "C:/Program Files/Git/usr/bin/sh.exe"


def make_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8", newline="\n")
    subprocess.run([SH, "-c", '/usr/bin/chmod 755 "$1"', "test", path.as_posix()], check=True)


mockbin = SANDBOX / "mockbin"
mockbin.mkdir()
service_log = SANDBOX / "service-calls.log"
scanner_log = SANDBOX / "scanner-calls.log"
make_executable(
    mockbin / "initctl",
    f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{service_log.as_posix()}"\nexit 0\n',
)
make_executable(mockbin / "mntroot", "#!/bin/sh\nexit 0\n")
make_executable(
    mockbin / "lipc-set-prop",
    f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{scanner_log.as_posix()}"\nexit 0\n',
)


def env_for(root: Path, **extra: str) -> dict[str, str]:
    us = root / "us"
    env = {
        **os.environ,
        "PATH": mockbin.as_posix() + ":/usr/bin:/bin:" + os.environ.get("PATH", ""),
        "READING_PACKAGE_DIR": PKG.as_posix(),
        "READING_BASE": (us / "reading-time").as_posix(),
        "READING_DOCUMENTS": (us / "documents").as_posix(),
        "READING_UPSTART_DIR": (root / "etc/upstart").as_posix(),
        "READING_MNT_US": us.as_posix(),
        "READING_TMPDIR": (root / "tmp").as_posix(),
        "READING_SKIP_ROOT_CHECK": "1",
    }
    env.update(extra)
    return env


def seed(root: Path, upgraded: bool = False, partial: bool = False) -> tuple[Path, Path, Path]:
    us = root / "us"
    base = us / "reading-time"
    docs = us / "documents"
    upstart = root / "etc/upstart"
    for folder in (base, docs, upstart, root / "tmp"):
        folder.mkdir(parents=True, exist_ok=True)
    history = "date\tbook_id\tseconds\ttitle\n2026-09-22\tb1\t321\tHistory survives\n"
    (base / "reading-time.tsv").write_text(history, encoding="utf-8")
    (base / "reading-time.tsv.bak").write_text(history, encoding="utf-8")
    (base / "阅读时长统计.txt").write_text("persistent report", encoding="utf-8")
    (base / "user.conf").write_text("custom=true", encoding="utf-8")
    (base / "unknown-user-file.txt").write_text("keep unknown", encoding="utf-8")
    if partial:
        (base / "bin").mkdir()
        (base / "bin/launch.sh").write_text("partial", encoding="utf-8")
        return base, docs, upstart
    for folder in (
        base / "bin",
        base / "compat",
        base / "releases/9.7.5-test/bin",
        base / "ui",
        base / "fonts",
        base / "assets",
        base / "book-covers",
        us / "extensions/reading-records-installer/bin",
    ):
        folder.mkdir(parents=True, exist_ok=True)
    for path in (
        base / "bin/launch.sh",
        base / "bin/diagnostics.sh",
        base / "bin/uninstall.sh",
        base / "bin/native-reading-time-daemon.sh",
        base / "compat/detect_env.sh",
        base / "releases/9.7.5-test/bin/reading-records.sh",
        base / "ui/daily.png",
        base / "fonts/NotoSansCJKsc-Regular.otf",
        base / "assets/launcher-icon.png",
        base / "VERSION",
        base / "state",
        base / "book-cover-cache.tsv",
        base / "book-cover-misses.tsv",
        base / "book-covers/cached.jpg",
        base / "book-progress.tsv",
        base / "display-layout.txt",
        base / "service.log",
        base / "install.log",
        base / "dashboard-launch.log",
        docs / "阅读记录.sh",
        us / "extensions/reading-records-installer/bin/action.sh",
        upstart / "native-reading-time.conf",
    ):
        path.write_text("generated", encoding="utf-8")
    shutil.copy2(PKG / "install-manifest.txt", base / "install-manifest.txt")
    (base / ".install-9.7.5-test.123").mkdir()
    (base / ".install-9.7.5-test.123/staged").write_text("temporary", encoding="utf-8")
    (base / "reading-time.tsv.bak.new.123").write_text("temporary", encoding="utf-8")
    (root / "tmp/native-reading-dashboard.123").mkdir()
    (root / "tmp/native-reading-dashboard.123/session").write_text("temporary", encoding="utf-8")
    if upgraded:
        old = base / "releases/9.7.4/bin"
        old.mkdir(parents=True)
        (old / "old-app.sh").write_text("old program", encoding="utf-8")
    return base, docs, upstart


def run_core(root: Path, **extra: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run([SH, (PKG / "uninstall.sh").as_posix()], capture_output=True, env=env_for(root, **extra))


# The manifest explicitly separates deletable classes from persistent data.
manifest = (PKG / "install-manifest.txt").read_text(encoding="utf-8")
assert all(name in manifest for name in ("PROGRAM_TREE", "CACHE_TREE", "LOG_FILE", "PERSISTENT_FILE"))
assert "PERSISTENT_FILE|BASE|reading-time.tsv|" in manifest
assert "CACHE_TREE|BASE|book-covers|" in manifest
assert "jailbreak" not in manifest.lower() and "linkjail" not in manifest.lower()

# Fresh installation uninstall, cache removal, KUAL/launcher removal and data retention.
fresh = SANDBOX / "fresh"
base, docs, upstart = seed(fresh)
preserved = {p: p.read_bytes() for p in (base / "reading-time.tsv", base / "reading-time.tsv.bak", base / "阅读时长统计.txt", base / "user.conf", base / "unknown-user-file.txt")}
p = run_core(fresh, READING_FIRMWARE_MOCK="5.18.6")
assert p.returncode == 0, (p.stdout, p.stderr)
assert all(path.read_bytes() == content for path, content in preserved.items())
assert not (docs / "阅读记录.sh").exists() and not (base / "bin").exists()
assert not (base / "book-covers").exists() and not (fresh / "us/extensions/reading-records-installer").exists()
assert not (base / ".install-9.7.5-test.123").exists() and not (base / "reading-time.tsv.bak.new.123").exists()
assert not (fresh / "tmp/native-reading-dashboard.123").exists()
assert not (upstart / "native-reading-time.conf").exists()
assert "STATUS=uninstalled" in (docs / "reading-records-uninstall-result.txt").read_text(encoding="utf-8")

# Not installed and repeated uninstall are both successful no-ops.
p = run_core(fresh, READING_FIRMWARE_MOCK="5.19.0")
assert p.returncode == 0
assert "STATUS=already_removed" in (docs / "reading-records-uninstall-result.txt").read_text(encoding="utf-8")

empty = SANDBOX / "empty"
(empty / "us/documents").mkdir(parents=True)
(empty / "tmp").mkdir()
(empty / "etc/upstart").mkdir(parents=True)
p = run_core(empty)
assert p.returncode == 0
assert "STATUS=already_removed" in (empty / "us/documents/reading-records-uninstall-result.txt").read_text(encoding="utf-8")

# Upgrade-shaped and partial installations remove all known program remnants.
upgrade = SANDBOX / "upgrade"
upgrade_base, _, _ = seed(upgrade, upgraded=True)
p = run_core(upgrade)
assert p.returncode == 0 and not (upgrade_base / "releases").exists()
assert (upgrade_base / "reading-time.tsv").exists()

partial = SANDBOX / "partial"
partial_base, partial_docs, _ = seed(partial, partial=True)
p = run_core(partial)
assert p.returncode == 0 and not (partial_base / "bin").exists()
assert (partial_base / "reading-time.tsv").exists()
assert "STATUS=uninstalled" in (partial_docs / "reading-records-uninstall-result.txt").read_text(encoding="utf-8")

# The service stop is always attempted. PID fallback is deliberately limited
# to a numeric PID whose /proc cmdline contains this exact daemon path; Windows
# cannot faithfully emulate Kindle's /proc PID namespace.
core_source = (PKG / "uninstall.sh").read_text(encoding="utf-8")
assert "stop \"$JOB\"" in core_source
assert '"$BASE/bin/native-reading-time-daemon.sh"' in core_source
assert 'kill -TERM "$owned_pid"' in core_source
assert "killall" not in core_source
assert "stop native-reading-time" in service_log.read_text(encoding="utf-8")

# Permission failure: continue safely, report the exact stage/path, and leave
# the blocked file for a retry. A mock rm affects only this isolated case.
permission = SANDBOX / "permission"
permission_base, permission_docs, _ = seed(permission, partial=True)
blocked = permission_base / "blocked-program"
blocked.write_text("cannot remove", encoding="utf-8")
permission_manifest = permission / "permission-manifest.txt"
permission_manifest.write_text("PROGRAM_FILE|BASE|blocked-program|failure injection\nPERSISTENT_FILE|BASE|reading-time.tsv|history\n", encoding="utf-8")
failure_bin = permission / "failure-bin"
failure_bin.mkdir()
make_executable(
    failure_bin / "rm",
    f'''#!/bin/sh
for arg in "$@"; do
    [ "$arg" = "{blocked.as_posix()}" ] && exit 1
done
exec /usr/bin/rm "$@"
''',
)
permission_path = failure_bin.as_posix() + ":" + env_for(permission)["PATH"]
p = run_core(permission, READING_INSTALL_MANIFEST=permission_manifest.as_posix(), PATH=permission_path)
assert p.returncode == 1 and blocked.exists()
result_text = (permission_docs / "reading-records-uninstall-result.txt").read_text(encoding="utf-8")
diagnostic_text = (permission_docs / "reading-records-uninstall-diagnostic.txt").read_text(encoding="utf-8")
assert "STAGE=remove_program" in result_text and "ERROR=permission_denied" in result_text
assert f"PATH={blocked.as_posix()}" in result_text and "ERROR=permission_denied" in diagnostic_text
assert (permission_base / "reading-time.tsv").exists()

# Entrypoints contain routing only; destructive operations are centralized.
entry_sources = [
    ROOT / "documents/reading-records-uninstall.sh",
    ROOT / "extensions/reading-records-installer/bin/action.sh",
    PKG / "install.sh",
]
for entry in entry_sources:
    source = entry.read_text(encoding="utf-8")
    assert "uninstall.sh" in source
    assert "rm -rf" not in source and "reading-time.tsv" not in source

checks = [
    "fresh install -> uninstall",
    "upgrade install -> uninstall",
    "uninstall when not installed",
    "uninstall twice",
    "user data preserved",
    "regenerable cache removed",
    "KUAL entry removed",
    "library launcher removed",
    "missing optional files",
    "partial installation",
    "owned process stopped without killall",
    "permission failure diagnostic",
    "firmware 5.18 and newer-firmware independent paths",
]
result = {
    "result": "PASS",
    "checks": checks,
    "limitation": "Filesystem, service, scanner and firmware conditions are mocked; Kindle indexing/toasts/rootfs/process behavior still require device validation.",
}
(OUT / "uninstaller-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
