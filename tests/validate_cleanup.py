"""Validate one-shot cleanup against V3 plus historical plugin leftovers.

Only test sandboxes are deleted. The shipped cleanup core is relocated by
literal device-path substitution; its deletion list remains unchanged.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "dist/kindle-reading-records-v9.7.5-compat-v3-cover-test.zip"
OUT = ROOT / "build/validation"
OUT.mkdir(parents=True, exist_ok=True)
SHELL = shutil.which("sh") or "C:/Program Files/Git/usr/bin/sh.exe"
CORE = ROOT / "native-reading-time-package/uninstall.sh"
MANIFEST = ROOT / "native-reading-time-package/cleanup-manifest.txt"
ENTRY = ROOT / "documents/reading-records-uninstall.sh"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest_rows = [line for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]
embedded_rows = CORE.read_text(encoding="utf-8").split("<<'CLEANUP_TARGETS'\n", 1)[1].split("\nCLEANUP_TARGETS", 1)[0].splitlines()
assert manifest_rows == embedded_rows and len(manifest_rows) == 25
assert all(len(row.split("|")) == 6 for row in manifest_rows)
for row in manifest_rows:
    phase, kind, root, relative, _, _ = row.split("|")
    assert phase in {"REPORT", "DEBUG", "ENTRY", "PACKAGE", "SELF"}
    assert kind in {"FILE", "TREE", "RMDIR"} and root in {"BASE", "DOCS", "MNT_US"}
    assert relative and not relative.startswith("/") and ".." not in relative
    assert not (root == "BASE" and relative in {"reading-time.tsv", "book-cover-cache.tsv", "book-cover-misses.tsv", "book-covers", "releases", "bin/launch.sh"})
assert not any("/etc/upstart" in row or "reading-time.tsv" in row for row in manifest_rows)
assert "initctl stop" not in CORE.read_text(encoding="utf-8")
assert "manifest_pass" not in CORE.read_text(encoding="utf-8")
assert "# Name: 安装文件清理" in ENTRY.read_text(encoding="utf-8")
assert ENTRY.read_bytes() == (ROOT / "native-reading-time-package/resources/reading-records-uninstall.sh").read_bytes()


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def chmod(*paths: Path) -> None:
    subprocess.run([SHELL, "-c", '/usr/bin/chmod 755 "$@"', "test", *(path.as_posix() for path in paths)], check=True)


def sandbox(label: str) -> tuple[Path, Path, Path, Path, Path, dict[str, str], dict[str, str], Path]:
    session = Path(tempfile.mkdtemp(prefix=f"cleanup-{label}-", dir=OUT))
    us = session / "us"
    base = us / "reading-time"
    docs = us / "documents"
    package = us / "native-reading-time-package"
    tmp = session / "tmp"
    tmp.mkdir()
    with zipfile.ZipFile(ARCHIVE) as archive:
        assert archive.testzip() is None
        archive.extractall(us)
        assert archive.read("native-reading-time-package/阅读记录-optimized.sh") == (ROOT / "native-reading-time-package/阅读记录-optimized.sh").read_bytes()
    write(base / "releases/9.7.5-test/bin/reading-records.sh", (package / "阅读记录-optimized.sh").read_bytes())
    write(base / "releases/9.7.5-test/bin/reading-insights-cover.lua", (package / "reading-insights-cover.lua").read_bytes())
    write(base / "bin/launch.sh", (package / "launch.sh").read_bytes())
    write(base / "bin/native-reading-time-daemon.sh", (package / "native-reading-time-daemon.sh").read_bytes())
    write(base / "bin/diagnostics.sh", (package / "diagnostics.sh").read_bytes())
    write(base / "compat/detect_env.sh", (package / "compat/detect_env.sh").read_bytes())
    write(base / "install-manifest.txt", (package / "install-manifest.txt").read_bytes())
    write(session / "etc/upstart/native-reading-time.conf", (package / "native-reading-time.conf").read_bytes())
    viewer = (package / "阅读记录-entry.sh").read_text(encoding="utf-8").replace("/mnt/us", us.as_posix())
    write(docs / "阅读记录.sh", viewer.encode())

    # Relocate only the test copy of the cleanup core. The packaged resolver
    # and active installed resolver remain byte-identical.
    relocated = CORE.read_text(encoding="utf-8").replace("/mnt/us", us.as_posix()).replace("/etc/upstart", (session / "etc/upstart").as_posix())
    write(package / "uninstall.sh", relocated.encode())
    write(base / "bin/uninstall.sh", relocated.encode())
    manual = session / "manual-cleanup.sh"
    write(manual, relocated.encode())
    chmod(docs / "阅读记录.sh", base / "bin/launch.sh", base / "bin/native-reading-time-daemon.sh", base / "bin/uninstall.sh", base / "releases/9.7.5-test/bin/reading-records.sh", package / "uninstall.sh")

    protected_files = {
        "history": base / "reading-time.tsv",
        "history_backup": base / "reading-time.tsv.bak",
        "statistics": base / "阅读时长统计.txt",
        "user_config": base / "user.conf",
        "cover_map": base / "book-cover-cache.tsv",
        "cover_misses": base / "book-cover-misses.tsv",
        "cover_image": base / "book-covers/old-cover.jpg",
        "progress_cache": base / "book-progress.tsv",
        "other_user_data": base / "personal-notes.txt",
        "viewer": docs / "阅读记录.sh",
        "launcher": base / "bin/launch.sh",
        "resolver": base / "releases/9.7.5-test/bin/reading-records.sh",
        "daemon": base / "bin/native-reading-time-daemon.sh",
        "helper": base / "releases/9.7.5-test/bin/reading-insights-cover.lua",
        "upstart": session / "etc/upstart/native-reading-time.conf",
    }
    data = {
        "history": b"date\tbook_id\tseconds\ttitle\n2026-09-22\tb1\t321\tHistory survives\n",
        "history_backup": b"older backup\n",
        "statistics": b"old statistics\n",
        "user_config": b"custom=true\n",
        "cover_map": b"b1\t/mnt/us/reading-time/book-covers/old-cover.jpg\n",
        "cover_misses": b"prior misses\n",
        "cover_image": b"cached cover bytes\n",
        "progress_cache": b"derived stats\n",
        "other_user_data": b"never delete unknown files\n",
    }
    for name, value in data.items():
        write(protected_files[name], value)
    before = {name: digest(path) for name, path in protected_files.items()}

    mockbin = session / "mockbin"
    mockbin.mkdir()
    scanner = session / "scanner-calls.log"
    mock_lipc = mockbin / "lipc-set-prop"
    mock_lipc.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{scanner.as_posix()}"\nexit 0\n', encoding="utf-8", newline="\n")
    chmod(mock_lipc)
    env = {
        **os.environ,
        "PATH": mockbin.as_posix() + ":/usr/bin:/bin:" + os.environ.get("PATH", ""),
        "READING_PACKAGE_DIR": package.as_posix(),
        "READING_BASE": base.as_posix(),
        "READING_DOCUMENTS": docs.as_posix(),
        "READING_TMPDIR": tmp.as_posix(),
    }
    return session, us, base, docs, package, env, before, manual


def run(script: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run([SHELL, script.as_posix(), *args], env=env, capture_output=True, timeout=60)


matrix: dict[str, dict[str, str]] = {}
for label in ("974", "v1", "v2", "v3"):
    session, us, base, docs, package, env, before, manual = sandbox(label)
    try:
        if label == "974":
            write(base / "releases/9.7.4/old-program-marker", b"old rollback release")
            (us / "extensions/reading-records-cover-debug/bin/action.sh").unlink()
            (us / "extensions/reading-records-cover-debug/menu.json").unlink()
            (us / "extensions/reading-records-cover-debug/config.xml").unlink()
            (us / "extensions/reading-records-cover-debug/bin").rmdir()
            (us / "extensions/reading-records-cover-debug").rmdir()
            (docs / "阅读记录封面诊断.sh").unlink()
        elif label == "v1":
            write(docs / "reading-records-uninstall-result.txt", b"legacy uninstall result")
        elif label == "v2":
            write(docs / "reading-records-diagnostic.txt", b"legacy diagnostic")
            write(docs / "阅读记录诊断.txt", b"legacy diagnostic")
        else:
            debug_copy = us / "debug/cover-debug"
            shutil.copytree(ROOT / "debug/cover-debug", debug_copy)
            write(us / "debug/cover-v3-test-README.txt", b"Compatibility V3 debug copy")
            write(us / "debug/personal.txt", b"user-owned debug file")
            # This generic filename has been replaced by unrelated user data;
            # its ownership signature must prevent deletion.
            write(us / "README.txt", b"my personal Kindle README\n")
            # The old installed core is intentionally markerless and unsafe.
            # The Scriptlet must prefer the extracted safe package core.
            write(base / "bin/uninstall.sh", b"#!/bin/sh\nprintf 'OLD_UNINSTALL_RAN\\n'\nexit 99\n")
        write(docs / "reading-records-install-result.txt", b"installation report")
        write(docs / "reading-records-cover-debug-result.txt", b"debug report")
        write(docs / "reading-records-uninstall-diagnostic.txt", b"old diagnostic")
        write(docs / "reading-records-kual-error.txt", b"KUAL report")
        write(docs / "reading-records-launch-error.txt", b"launcher report")
        write(base / "cover-debug.log", b"one-shot debug log")
        write(docs / "personal-reading-notes.pdf", b"user book")
        if label == "v2":
            # Stale KUAL action aliases still route to the safe cleanup core.
            result = run(package / "install.sh", env, "uninstall-keep-data")
        else:
            result = run(docs / "reading-records-uninstall.sh", env)
        assert result.returncode == 0, (label, result.stdout, result.stderr, (base / "cleanup-last.log").read_text(errors="replace"))
        for name, expected in before.items():
            assert digest({
                "history": base / "reading-time.tsv", "history_backup": base / "reading-time.tsv.bak",
                "statistics": base / "阅读时长统计.txt", "user_config": base / "user.conf",
                "cover_map": base / "book-cover-cache.tsv", "cover_misses": base / "book-cover-misses.tsv",
                "cover_image": base / "book-covers/old-cover.jpg", "progress_cache": base / "book-progress.tsv",
                "other_user_data": base / "personal-notes.txt", "viewer": docs / "阅读记录.sh",
                "launcher": base / "bin/launch.sh", "resolver": base / "releases/9.7.5-test/bin/reading-records.sh",
                "daemon": base / "bin/native-reading-time-daemon.sh",
                "helper": base / "releases/9.7.5-test/bin/reading-insights-cover.lua",
                "upstart": session / "etc/upstart/native-reading-time.conf",
            }[name]) == expected, (label, name)
        assert (docs / "personal-reading-notes.pdf").read_bytes() == b"user book"
        assert not package.exists() and not (us / "cover-debug.sh").exists()
        assert not (docs / "reading-records-install.sh").exists()
        assert not (docs / "reading-records-uninstall.sh").exists()
        assert not (docs / "阅读记录封面诊断.sh").exists()
        assert not (us / "extensions/reading-records-installer").exists()
        assert not (us / "extensions/reading-records-cover-debug").exists()
        assert not (base / "bin/uninstall.sh").exists()
        assert not (base / "cover-debug.log").exists()
        assert not any(p.name.startswith("reading-records-") for p in docs.iterdir())
        assert (docs / "阅读记录.sh").exists()
        assert "result=SUCCESS" in (base / "cleanup-last.log").read_text(encoding="utf-8")
        assert "doFullScan 1" in (session / "scanner-calls.log").read_text(encoding="utf-8")
        if label == "974":
            assert (base / "releases/9.7.4/old-program-marker").read_bytes() == b"old rollback release"
        if label == "v3":
            assert (us / "README.txt").read_bytes() == b"my personal Kindle README\n"
            assert (us / "debug/personal.txt").read_bytes() == b"user-owned debug file"
            assert "SKIP PROTECTED" in (base / "cleanup-last.log").read_text(encoding="utf-8")

        repeated = run(manual, env)
        assert repeated.returncode == 0, (label, repeated.stdout, repeated.stderr)
        assert "result=SUCCESS" in (base / "cleanup-last.log").read_text(encoding="utf-8")
        assert not (docs / "reading-records-uninstall.sh").exists()
        matrix[label] = {"cleanup": "PASS", "protected_files": "PASS", "visible_entries": "1", "repeat": "PASS"}
    finally:
        assert session.resolve().is_relative_to(OUT.resolve())
        shutil.rmtree(session)


# Installing only the payload without an active V3 must not remove the package.
for defect in ("missing_resolver", "mismatched_payload", "foreign_payload_file"):
    session, us, base, docs, package, env, before, _ = sandbox(defect)
    try:
        write(docs / "reading-records-install-result.txt", b"must survive aborted cleanup")
        if defect == "missing_resolver":
            (base / "releases/9.7.5-test/bin/reading-records.sh").unlink()
        elif defect == "mismatched_payload":
            write(package / "阅读记录-optimized.sh", b"staged-but-not-installed resolver")
        else:
            write(package / "personal-file.txt", b"not owned by the installer")
        result = run(docs / "reading-records-uninstall.sh", env)
        assert result.returncode != 0
        assert b"ABORT:" in result.stderr
        assert "result=ABORT" in (base / "cleanup-last.log").read_text(encoding="utf-8")
        assert package.exists() and (docs / "reading-records-install.sh").exists()
        assert (docs / "reading-records-uninstall.sh").exists()
        assert (docs / "reading-records-install-result.txt").exists()
        if defect == "foreign_payload_file":
            assert (package / "personal-file.txt").read_bytes() == b"not owned by the installer"
        assert (base / "reading-time.tsv").read_bytes() == b"date\tbook_id\tseconds\ttitle\n2026-09-22\tb1\t321\tHistory survives\n"
        assert not (docs / "reading-records-clean-result.txt").exists()
    finally:
        assert session.resolve().is_relative_to(OUT.resolve())
        shutil.rmtree(session)


report = {
    "result": "PASS",
    "matrix": matrix,
    "abort_before_delete": "PASS",
    "legacy_uninstall_alias_runs_only_safe_core": "PASS",
    "manifest_matches_embedded_allowlist": "PASS",
    "limitation": "Kindle filesystem and launcher refresh are sandboxed; actual Kindle library re-indexing remains a device check.",
}
(OUT / "cleanup-results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
