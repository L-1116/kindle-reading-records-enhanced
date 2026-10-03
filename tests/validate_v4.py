"""Exercise packaged V4 bootstraps in relocated Kindle filesystem sandboxes."""

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
OUT = ROOT / "build/validation"
OUT.mkdir(parents=True, exist_ok=True)
SHELL = r"C:\Program Files\Git\bin\sh.exe"
BOOT = "点这个安装，然后确认插件正常之前不要删文件.sh"
TAR = "阅读记录安装数据.tar"
CLEAN = "安装好之后，确认无误了再点这个.sh"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def msys(path: Path) -> str:
    return f"/{path.drive[0].lower()}{path.as_posix()[2:]}"


def historical(tag: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{tag}:{path}"], cwd=ROOT)


def run(session: Path, variant: str, previous: str | None, *, mutation: str = "", cleanup: bool = False, legacy_tag: str = "", legacy_archive: str = "", cleanup_unknown: bool = False) -> dict:
    us = session / "us"
    docs = us / "documents"
    base = us / "reading-time"
    upstart = session / "upstart"
    mock = session / "mockbin"
    tmp = session / "tmp"
    for folder in (docs, upstart, mock, tmp):
        folder.mkdir(parents=True, exist_ok=True)
    zip_name = "ReadingTime-V4-Test.zip" if variant == "standard" else "ReadingTime-V4-KS-Test.zip"
    with zipfile.ZipFile(ROOT / "dist" / zip_name) as archive:
        assert set(archive.namelist()) == {BOOT, TAR}
        archive.extractall(docs)
    script = docs / BOOT
    if mutation == "missing_payload":
        (docs / TAR).unlink()
    elif mutation == "bad_checksum":
        data = bytearray((docs / TAR).read_bytes())
        data[0] ^= 1
        (docs / TAR).write_bytes(data)
    elif mutation == "bad_tar":
        data = (docs / TAR).read_bytes()
        (docs / TAR).write_bytes(b"X" * len(data))
        text = script.read_text(encoding="utf-8")
        from build_v4 import posix_cksum
        checksum = str(posix_cksum((docs / TAR).read_bytes()))
        script.write_text(text.replace(text.split("PAYLOAD_CKSUM='")[1].split("'")[0], checksum), encoding="utf-8", newline="\n")
    if previous is not None:
        tag = {"9.7.4": "v9.7.4", "9.7.5": "v9.7.5-test.1", "V1": "v9.7.5-test.1", "V2": "v9.7.5-compat-v2"}.get(previous)
        put(base / "reading-time.tsv", b"date\tbook_id\tseconds\ttitle\n2026-09-01\tb1\t120\tOld book\n")
        put(base / "book-covers/old-cover.jpg", b"old image")
        put(base / "book-covers/second-cover.png", b"another cached image")
        put(base / "user.conf", b"preference=keep\n")
        put(base / "book-cover-cache.tsv", b"old cache\n")
        put(base / "reading-time.tsv.bak", b"old history backup\n")
        put(base / "阅读时长统计.txt", b"old statistics export\n")
        put(base / "launch-last.log", b"old launch diagnostic\n")
        put(base / "touch-last.log", b"old touch diagnostic\n")
        put(base / "bin/native-reading-time-daemon.sh", historical(tag, "native-reading-time-package/native-reading-time-daemon.sh") if tag else (ROOT / "native-reading-time-package/native-reading-time-daemon.sh").read_bytes())
        if previous == "V3-KS":
            put(base / "VERSION", b"9.7.5-ks-test1-touch-compat\n")
            put(base / "bin/launch-ks.sh", b"old KS launcher")
            put(base / "releases/9.7.5-ks-test1/bin/reading-records-ks.sh", (ROOT / "ks-package/native-reading-time-package/阅读记录-ks.sh").read_bytes())
        elif previous == "V4-KS":
            put(base / "VERSION", b"V4-KS\n")
            put(base / "release-info", b"release_family=V4\nvariant=ks\n")
            put(base / "bin/launch-ks.sh", b"old KS launcher")
            put(base / "releases/9.7.5-ks-test1/bin/reading-records-ks.sh", (ROOT / "ks-package/native-reading-time-package/阅读记录-ks.sh").read_bytes())
        else:
            put(base / "VERSION", ("V4\n" if previous == "V4" else f"{previous}\n").encode())
            if previous == "V4":
                put(base / "release-info", b"release_family=V4\nvariant=standard\n")
            put(base / "bin/launch.sh", b"old standard launcher")
            resolver_source = historical(tag, "native-reading-time-package/阅读记录-optimized.sh") if tag else (ROOT / "native-reading-time-package/阅读记录-optimized.sh").read_bytes()
            put(base / "releases/9.7.5-test/bin/reading-records.sh", resolver_source)
        put(docs / "阅读记录.sh", b"old entry")
        put(upstart / "native-reading-time.conf", b"old service")
        if previous in {"V3", "V3-KS"}:
            put(us / "RUNME.sh", b"#!/bin/sh\n/mnt/us/native-reading-time-package/install.sh\n")
            put(docs / "reading-records-install.sh", b"/mnt/us/native-reading-time-package/install.sh\n")
            put(us / "extensions/reading-records-installer/config.xml", b"reading-records-installer\n")
            put(us / "extensions/reading-records-installer/bin/action.sh", b"old KUAL installer\n")
        put(base / "ui/old-ui.png", b"old UI asset")
        put(base / "fonts/old-font.otf", b"old font asset")
        put(base / "assets/old-icon.png", b"old icon")
    protected = {str(path): digest(path) for path in (base / "reading-time.tsv", base / "reading-time.tsv.bak", base / "阅读时长统计.txt", base / "user.conf", base / "book-cover-cache.tsv", base / "launch-last.log", base / "touch-last.log") if path.is_file()}
    if (base / "book-covers").is_dir():
        protected.update({str(path): digest(path) for path in (base / "book-covers").rglob("*") if path.is_file()})
    cover_count = sum(path.is_file() for path in (base / "book-covers").rglob("*")) if (base / "book-covers").is_dir() else 0
    old_runtime = {str(path): digest(path) for path in (base / "VERSION", base / "bin/launch.sh", base / "bin/launch-ks.sh", base / "releases/9.7.5-test/bin/reading-records.sh", base / "releases/9.7.5-ks-test1/bin/reading-records-ks.sh", docs / "阅读记录.sh", upstart / "native-reading-time.conf") if path.is_file()}
    for folder in (base / "bin", base / "releases", base / "compat", base / "ui", base / "fonts", base / "assets"):
        if folder.is_dir():
            old_runtime.update({str(path): digest(path) for path in folder.rglob("*") if path.is_file()})

    initctl = mock / "initctl"
    initctl.write_text(
        '#!/bin/sh\ncase "$1" in\n'
        f'  start) [ -f "{(base / "reading-time.tsv").as_posix()}" ] || printf "date\\tbook_id\\tseconds\\ttitle\\n" > "{(base / "reading-time.tsv").as_posix()}" ;;\n'
        '  status) echo "native-reading-time start/running, process 123" ;;\n'
        'esac\nexit 0\n', encoding="utf-8", newline="\n")
    scripts = {
        "id": '#!/bin/sh\n[ "$1" = -u ] && { echo 0; exit 0; }; /usr/bin/id "$@"\n',
        "mntroot": '#!/bin/sh\nexit 0\n',
        "lipc-get-prop": '#!/bin/sh\nexit 0\n',
        "lipc-set-prop": '#!/bin/sh\nexit 0\n',
        "fbink": '#!/bin/sh\nexit 0\n',
        "lua": '#!/bin/sh\nexit 0\n',
        "sleep": '#!/bin/sh\nexit 0\n',
        "sync": '#!/bin/sh\nexit 0\n',
    }
    for name, body in scripts.items():
        (mock / name).write_text(body, encoding="utf-8", newline="\n")
    subprocess.run([SHELL, "-c", '/usr/bin/chmod 755 "$@"', "test", *(p.as_posix() for p in mock.iterdir())], check=True)
    loader = session / "ld-linux-armhf.so.3"
    loader.write_bytes(b"loader")
    device = session / "deviceType.txt"
    device.write_text("KindleScribe\n" if variant == "ks" or mutation == "wrong_device" else "KindlePaperwhite\n", encoding="ascii")
    env = {**os.environ, "PATH": msys(mock) + ":/usr/bin:/bin", "READING_MNT_US": us.as_posix(), "READING_BASE": base.as_posix(), "READING_DOCUMENTS": docs.as_posix(), "READING_TMPDIR": tmp.as_posix(), "READING_UPSTART_DIR": upstart.as_posix(), "READING_DEVICETYPE_PATH": device.as_posix(), "READING_ARMHF_LOADER_PATH": loader.as_posix(), "READING_ARCH_OVERRIDE": "armhf", "READING_ALLOW_NONROOT_TEST": "1"}
    # Relocate the device-only absolute paths in the packaged installer scripts
    # after extraction. Runtime payload files are left byte-identical.
    if mutation not in {"missing_payload", "bad_checksum", "bad_tar", "temp_failure", "tar_unavailable"}:
        import tarfile
        import io
        tar_path = docs / TAR
        members: dict[str, bytes] = {}
        with tarfile.open(tar_path) as archive:
            for member in archive:
                raw = archive.extractfile(member).read()
                if member.name in {"native-reading-time-package/install.sh", "native-reading-time-package/Install-Native-Reading-Time.sh", "native-reading-time-package/Install-Native-Reading-Time-Optimized.sh", "native-reading-time-package/Install-Native-Reading-Time-KS.sh"}:
                    raw = raw.replace(b"/sbin/initctl", initctl.as_posix().encode()).replace(b"/lib/ld-linux-armhf.so.3", loader.as_posix().encode())
                    if mutation == "core_failure" and member.name.endswith("/install.sh"):
                        raw = raw.replace(b"STAGE=install", b"exit 73\nSTAGE=install")
                    if mutation == "staging_failure" and member.name.endswith("/Install-Native-Reading-Time-Optimized.sh"):
                        raw = raw.replace(b'rm -rf "$STAGE"; mkdir -p', b'exit 72\nrm -rf "$STAGE"; mkdir -p')
                    if mutation == "staging_failure" and member.name.endswith("/Install-Native-Reading-Time-KS.sh"):
                        raw = raw.replace(b'rm -rf "$STAGE"; mkdir -p', b'exit 72\nrm -rf "$STAGE"; mkdir -p')
                    if mutation == "activation_failure" and member.name.endswith("/Install-Native-Reading-Time-Optimized.sh"):
                        raw = raw.replace(b'echo "$(date): final sanity resolver=ok', b'fail "injected post-activation failure"\necho "$(date): final sanity resolver=ok')
                    if mutation == "activation_failure" and member.name.endswith("/Install-Native-Reading-Time-KS.sh"):
                        raw = raw.replace(b'cleanup_stage; trap - INT TERM HUP; sync', b'fail "injected post-activation failure"\ncleanup_stage; trap - INT TERM HUP; sync')
                members[member.name] = raw
        # Rebuild only the sandbox copy and update its bootstrap checksum.
        from build_v4 import make_tar, posix_cksum
        rebuilt = make_tar(members)
        tar_path.write_bytes(rebuilt)
        checksum = str(posix_cksum(rebuilt))
        script.write_text(script.read_text(encoding="utf-8").replace(script.read_text(encoding="utf-8").split("PAYLOAD_SIZE='")[1].split("'")[0], str(len(rebuilt)), 1).replace(script.read_text(encoding="utf-8").split("PAYLOAD_CKSUM='")[1].split("'")[0], checksum, 1), encoding="utf-8", newline="\n")
    if mutation == "verified_failure":
        source = script.read_text(encoding="utf-8")
        source = source.replace('[ -x "$launcher" ] && [ -x "$resolver" ]', 'false && [ -x "$launcher" ] && [ -x "$resolver" ]')
        script.write_text(source, encoding="utf-8", newline="\n")
    if mutation == "temp_failure":
        env["READING_TMPDIR"] = (session / "missing-tmp-root").as_posix()
    if mutation == "tar_unavailable":
        source = script.read_text(encoding="utf-8")
        source = source.replace("command -v tar >/dev/null 2>&1", "false").replace("command -v busybox >/dev/null 2>&1", "false")
        script.write_text(source, encoding="utf-8", newline="\n")
    if mutation in {"tar_extract_failure", "busybox_fallback"}:
        if mutation == "tar_extract_failure":
            source = script.read_text(encoding="utf-8")
            source = source.replace('tar_cmd() {', 'tar_cmd() { [ "$1" = -xf ] && return 79;')
            script.write_text(source, encoding="utf-8", newline="\n")
        else:
            source = script.read_text(encoding="utf-8").replace("command -v tar >/dev/null 2>&1", "false")
            source = source.replace('tar_cmd() {', 'busybox() { [ "$1" = tar ] || return 1; shift; /usr/bin/tar "$@"; }\ntar_cmd() {')
            script.write_text(source, encoding="utf-8", newline="\n")
    if mutation == "early_cleanup":
        put(docs / CLEAN, (ROOT / "v4/cleanup.sh").read_bytes())
        before = subprocess.run([SHELL, (docs / CLEAN).as_posix()], env=env, capture_output=True, timeout=30)
        assert before.returncode != 0
        assert (docs / BOOT).exists() and (docs / TAR).exists() and (docs / CLEAN).exists()
        assert all(digest(Path(path)) == value for path, value in protected.items())
        return {"returncode": before.returncode, "result": "early cleanup refused", "protected_hashes": protected}
    result = subprocess.run([SHELL, script.as_posix()], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    details = (docs / "reading-records-v4-install-result.txt").read_text(encoding="utf-8") if (docs / "reading-records-v4-install-result.txt").exists() else ""
    expected_failure = bool(mutation and mutation != "busybox_fallback")
    if expected_failure:
        assert result.returncode != 0, (mutation, result.stdout, result.stderr, details)
        assert not (docs / CLEAN).exists()
        expected_error = {
            "missing_payload": "payload not found",
            "bad_checksum": "payload checksum mismatch",
            "bad_tar": "tar listing failed",
            "tar_unavailable": "tar unavailable",
            "tar_extract_failure": "tar extraction failed",
            "temp_failure": "temporary directory creation failed",
            "core_failure": "internal installer failed",
            "staging_failure": "internal installer failed",
            "activation_failure": "internal installer failed",
            "verified_failure": "verified activation failed",
            "cross_variant": "cross-variant upgrade refused",
            "wrong_device": "device variant mismatch",
        }.get(mutation)
        if expected_error:
            assert f"error={expected_error}" in details, (mutation, details)
    else:
        assert result.returncode == 0, (variant, previous, result.stdout, result.stderr, details, (docs / "reading-records-v4-install.log").read_text(errors="replace")[-2000:], (base / "install.log").read_text(errors="replace")[-3000:] if (base / "install.log").exists() else "")
        assert (docs / CLEAN).is_file()
        assert (base / "VERSION").read_text().strip() == ("V4-KS" if variant == "ks" else "V4")
        import tarfile
        with tarfile.open(docs / TAR) as archive:
            source_name = "native-reading-time-package/阅读记录-optimized.sh" if variant == "standard" else "native-reading-time-package/阅读记录-ks.sh"
            expected_runtime = archive.extractfile(source_name).read()
        installed_runtime = base / ("releases/9.7.5-test/bin/reading-records.sh" if variant == "standard" else "releases/9.7.5-ks-test1/bin/reading-records-ks.sh")
        assert installed_runtime.read_bytes() == expected_runtime
        if previous in {"V4", "V4-KS"}:
            repeated = subprocess.run([SHELL, script.as_posix()], env=env, capture_output=True, timeout=90)
            assert repeated.returncode == 0, (variant, repeated.stdout, repeated.stderr)
            assert installed_runtime.read_bytes() == expected_runtime
            assert all(digest(Path(path)) == value for path, value in protected.items())
    assert all(digest(Path(path)) == value for path, value in protected.items())
    if previous is not None:
        assert sum(path.is_file() for path in (base / "book-covers").rglob("*")) == cover_count
    if expected_failure:
        assert all(digest(Path(path)) == value for path, value in old_runtime.items()), mutation
        for folder in (base / "bin", base / "releases", base / "compat", base / "ui", base / "fonts", base / "assets"):
            if folder.is_dir():
                assert all(str(path) in old_runtime for path in folder.rglob("*") if path.is_file()), mutation
    if mutation and mutation != "missing_payload":
        assert (docs / TAR).exists()
    assert not list(tmp.glob("reading-records-installer.*"))
    if cleanup:
        assert not mutation
        backup = session / "cleanup-copy.sh"
        backup.write_bytes((docs / CLEAN).read_bytes())
        if legacy_tag:
            old_files = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", legacy_tag, "native-reading-time-package"], cwd=ROOT).decode().splitlines()
            for name in old_files:
                put(us / name, historical(legacy_tag, name))
            assert not (us / "PACKAGE-MANIFEST.json").exists()
        elif legacy_archive:
            with zipfile.ZipFile(ROOT / "dist" / legacy_archive) as archive:
                archive.extractall(us)
        else:
            full_name = "ReadingTime-V4-Full-Compatibility.zip" if variant == "standard" else "ReadingTime-V4-KS-Full-Compatibility.zip"
            with zipfile.ZipFile(ROOT / "dist" / full_name) as archive:
                archive.extractall(us)
        leftovers = {
            us / "RUNME.sh": b"#!/bin/sh\n/mnt/us/native-reading-time-package/install.sh\n",
            us / "README.txt": "Kindle 阅读记录\n".encode(),
            docs / "reading-records-install.sh": b"/mnt/us/native-reading-time-package/install.sh\n",
        }
        for path, raw in leftovers.items():
            put(path, raw)
        if cleanup_unknown:
            put(us / "native-reading-time-package/user-extra.txt", b"user file, must not be removed")
            denied = subprocess.run([SHELL, (docs / CLEAN).as_posix()], env=env, capture_output=True, timeout=30)
            assert denied.returncode != 0
            assert (us / "native-reading-time-package/user-extra.txt").is_file()
            assert (docs / BOOT).is_file() and (docs / TAR).is_file() and (docs / CLEAN).is_file()
            assert all(digest(Path(path)) == value for path, value in protected.items())
            return {"returncode": denied.returncode, "result": "unknown package member protected", "protected_hashes": protected}
        first = subprocess.run([SHELL, (docs / CLEAN).as_posix()], env=env, capture_output=True, timeout=30)
        assert first.returncode == 0, (first.stdout, first.stderr, (base / "cleanup-last.log").read_text(errors="replace"))
        assert not (docs / BOOT).exists() and not (docs / TAR).exists() and not (docs / CLEAN).exists()
        assert not (us / "native-reading-time-package").exists()
        assert not (us / "extensions/reading-records-installer").exists()
        assert all(not path.exists() for path in leftovers)
        assert all(digest(Path(path)) == value for path, value in protected.items())
        assert (base / "bin/native-reading-time-daemon.sh").exists()
        second = subprocess.run([SHELL, backup.as_posix()], env=env, capture_output=True, timeout=30)
        assert second.returncode == 0, (second.stdout, second.stderr)
    return {"returncode": result.returncode, "result": details.strip(), "protected_hashes": protected}


def main() -> None:
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    matrix = [("standard", None), ("standard", "9.7.4"), ("standard", "9.7.5"), ("standard", "V1"), ("standard", "V2"), ("standard", "V3"), ("standard", "V4"), ("ks", None), ("ks", "V3-KS"), ("ks", "V4-KS")]
    selected = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("READING_V4_TEST_FILTER", "")
    if selected:
        matrix = [case for case in matrix if case[0] == selected]
    report: dict[str, dict] = {}
    for variant, previous in matrix:
        with tempfile.TemporaryDirectory(prefix="v4-", dir=OUT) as name:
            key = f"{previous or 'empty'} -> {'V4-KS' if variant == 'ks' else 'V4'}"
            report[key] = run(Path(name), variant, previous)
            print(key, "PASS", flush=True)
    for mutation in (() if selected else ("missing_payload", "bad_checksum", "bad_tar", "tar_unavailable", "tar_extract_failure", "temp_failure", "core_failure", "staging_failure", "activation_failure", "verified_failure", "early_cleanup", "busybox_fallback", "cross_variant", "wrong_device")):
        with tempfile.TemporaryDirectory(prefix="v4-fail-", dir=OUT) as name:
            test_variant = "ks" if mutation == "cross_variant" else "standard"
            old = "V4" if mutation == "cross_variant" else "V3"
            report[mutation] = run(Path(name), test_variant, old, mutation=mutation)
            print(mutation, "PASS", flush=True)
    if not selected:
        for mutation in ("staging_failure", "activation_failure", "verified_failure"):
            with tempfile.TemporaryDirectory(prefix="v4-ks-fail-", dir=OUT) as name:
                report[f"ks {mutation}"] = run(Path(name), "ks", "V3-KS", mutation=mutation)
                print("ks", mutation, "PASS", flush=True)
        for variant in ("standard", "ks"):
            with tempfile.TemporaryDirectory(prefix="v4-cleanup-", dir=OUT) as name:
                report[f"cleanup {variant}"] = run(Path(name), variant, "V3" if variant == "standard" else "V3-KS", cleanup=True)
                print("cleanup", variant, "PASS", flush=True)
        for tag in ("v9.7.4", "v9.7.5-test.1", "v9.7.5-compat-v2"):
            with tempfile.TemporaryDirectory(prefix="v4-legacy-cleanup-", dir=OUT) as name:
                report[f"cleanup {tag}"] = run(Path(name), "standard", "V3", cleanup=True, legacy_tag=tag)
                print("cleanup", tag, "PASS", flush=True)
    if selected == "focused":
        for variant, previous, mutation, do_cleanup in (("standard", "V3", "activation_failure", False), ("standard", "V3", "verified_failure", False), ("ks", "V3-KS", "staging_failure", False), ("ks", "V3-KS", "activation_failure", False), ("ks", "V3-KS", "verified_failure", False), ("standard", "V3", "", True), ("ks", "V3-KS", "", True)):
            with tempfile.TemporaryDirectory(prefix="v4-focused-", dir=OUT) as name:
                report[f"focused {variant} {mutation or 'cleanup'}"] = run(Path(name), variant, previous, mutation=mutation, cleanup=do_cleanup)
                print("focused", variant, mutation or "cleanup", "PASS", flush=True)
        with tempfile.TemporaryDirectory(prefix="v4-focused-legacy-", dir=OUT) as name:
            report["focused cleanup v9.7.4"] = run(Path(name), "standard", "V3", cleanup=True, legacy_tag="v9.7.4")
            print("focused cleanup v9.7.4 PASS", flush=True)
        with tempfile.TemporaryDirectory(prefix="v4-focused-unknown-", dir=OUT) as name:
            report["focused cleanup unknown member"] = run(Path(name), "standard", "V3", cleanup=True, cleanup_unknown=True)
            print("focused cleanup unknown member PASS", flush=True)
    if selected == "legacy":
        for tag in ("v9.7.4", "v9.7.5-test.1", "v9.7.5-compat-v2"):
            with tempfile.TemporaryDirectory(prefix="v4-legacy-cleanup-", dir=OUT) as name:
                report[f"legacy cleanup {tag}"] = run(Path(name), "standard", "V3", cleanup=True, legacy_tag=tag)
                print("legacy cleanup", tag, "PASS", flush=True)
        with tempfile.TemporaryDirectory(prefix="v4-legacy-ks-cleanup-", dir=OUT) as name:
            report["legacy cleanup V3-KS"] = run(Path(name), "ks", "V3-KS", cleanup=True, legacy_archive="ReadingTime-v9.7.5-KS-touch-compat-hotfix.zip")
            print("legacy cleanup V3-KS PASS", flush=True)
    output = OUT / (f"v4-{selected}-results.json" if selected else "v4-results.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
