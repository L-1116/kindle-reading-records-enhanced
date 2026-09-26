"""Run five isolated V3 package installs with Kindle-only commands mocked.

The payload is extracted from the distributable ZIP, not read from the live
source tree. Only hard-coded device paths in installer scripts are redirected
into each sandbox; installed resolver and helpers retain their packaged bytes.
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
ARCHIVE = Path(os.environ.get("READING_V3_ARCHIVE", ROOT / "dist/kindle-reading-records-v9.7.5-compat-v3-cover-test.zip"))
OUT = ROOT / "build/validation"
OUT.mkdir(parents=True, exist_ok=True)
SHELL = shutil.which("sh") or "C:/Program Files/Git/usr/bin/sh.exe"
RESOLVER_NAME = "native-reading-time-package/阅读记录-optimized.sh"
CASES = {
    "9.7.4 → V3": "v9.7.4",
    "V1 → V3": "v9.7.5-test.1",
    "V2 → V3": "v9.7.5-compat-v2",
    "V3 → V3": "v3",
    "clean → V3": None,
}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def tag_file(tag: str, name: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{tag}:{name}"], cwd=ROOT)


with zipfile.ZipFile(ARCHIVE) as package:
    assert package.testzip() is None
    manifest = json.loads(package.read("PACKAGE-MANIFEST.json"))
    entries = {item["path"]: item for item in manifest["files"]}
    assert set(entries) | {"PACKAGE-MANIFEST.json"} == set(package.namelist())
    for name, item in entries.items():
        raw = package.read(name)
        assert len(raw) == item["size"] and sha(raw) == item["sha256"], name
        mode = (package.getinfo(name).external_attr >> 16) & 0o777
        assert mode == (0o755 if item["executable"] else 0o644), name
    resolver_bytes = package.read(RESOLVER_NAME)
    assert resolver_bytes == (ROOT / RESOLVER_NAME).read_bytes()
    assert tag_file("v9.7.4", RESOLVER_NAME) != resolver_bytes
    assert tag_file("v9.7.5-test.1", RESOLVER_NAME) != resolver_bytes
    assert tag_file("v9.7.5-compat-v2", RESOLVER_NAME) != resolver_bytes


def put(target: Path, raw: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)


def installed_seed(tag: str | None, state: Path, docs: Path, ext: Path, upstart: Path) -> dict[str, bytes]:
    if tag is None:
        assert not state.exists()
        return {}
    historical = "v9.7.5-compat-v2" if tag == "v3" else tag
    prefix = "native-reading-time-package/"
    common = {
        state / "bin/native-reading-time-daemon.sh": prefix + "native-reading-time-daemon.sh",
        state / "bin/reading-insights-touch.lua": prefix + "reading-insights-touch.lua",
        upstart / "native-reading-time.conf": prefix + "native-reading-time.conf",
    }
    if tag == "v9.7.4":
        common[docs / "阅读记录.sh"] = prefix + "阅读记录-optimized.sh"
        release = state / "releases/9.7.4"
        common[release / "bin/reading-records-v9.6.3.sh"] = prefix + "阅读记录.sh"
        common[release / "bin/reading-insights-cache.awk"] = prefix + "reading-insights-cache.awk"
        common[release / "bin/reading-insights-touch-ui.lua"] = prefix + "reading-insights-touch-ui.lua"
    else:
        release = state / "releases/9.7.5-test"
        common[docs / "阅读记录.sh"] = prefix + "阅读记录-entry.sh"
        common[state / "bin/launch.sh"] = prefix + "launch.sh"
        common[state / "bin/diagnostics.sh"] = prefix + "diagnostics.sh"
        common[state / "bin/uninstall.sh"] = prefix + "uninstall.sh"
        common[state / "install-manifest.txt"] = prefix + "install-manifest.txt"
        common[state / "compat/detect_env.sh"] = prefix + "compat/detect_env.sh"
        common[release / "bin/reading-records.sh"] = prefix + "阅读记录-optimized.sh"
        common[release / "bin/reading-insights-cover.lua"] = prefix + "reading-insights-cover.lua"
        common[docs / "reading-records-uninstall.sh"] = prefix + "resources/reading-records-uninstall.sh"
        common[ext / "bin/action.sh"] = prefix + "resources/kual/reading-records-installer/bin/action.sh"
        common[ext / "config.xml"] = prefix + "resources/kual/reading-records-installer/config.xml"
        common[ext / "menu.json"] = prefix + "resources/kual/reading-records-installer/menu.json"
    for target, name in common.items():
        raw = resolver_bytes if tag == "v3" and name == RESOLVER_NAME else tag_file(historical, name)
        put(target, raw)
    if tag == "v3":
        # Simulate an already installed V3, including the V3 launcher and
        # diagnostics, before running the same installer again.
        with zipfile.ZipFile(ARCHIVE) as package:
            for target, name in common.items():
                if name in package.namelist():
                    put(target, package.read(name))
    put(state / "VERSION", ("9.7.4\n" if tag == "v9.7.4" else "9.7.5-test\n").encode())
    put(release / "historical-program-marker", tag.encode())
    user_files = {
        state / "reading-time.tsv": b"date\tbook_id\tseconds\ttitle\n2026-09-05\tb1\t14760\tKeep reading history\n",
        state / "reading-time.tsv.bak": b"pre-existing history backup\n",
        state / "阅读时长统计.txt": b"pre-existing statistics report\n",
        state / "user.conf": b"user-preference=keep\n",
        state / "cover-debug.enabled": b"",
        state / "book-cover-cache.tsv": b"b1\t/mnt/us/reading-time/book-covers/old-cover.jpg\n",
        state / "book-cover-misses.tsv": b"miss-state\n",
        state / "book-covers/old-cover.jpg": b"old cached image bytes\n",
    }
    for target, raw in user_files.items():
        put(target, raw)
    return {str(target): raw for target, raw in user_files.items()}


def prepare_package(session: Path, us: Path, upstart: Path, mock: Path) -> tuple[Path, dict[str, str]]:
    package_dir = us / "native-reading-time-package"
    with zipfile.ZipFile(ARCHIVE) as package:
        package.extractall(us)
    original = {name: sha((us / name).read_bytes()) for name in entries}
    fake_loader = session / "ld-linux-armhf.so.3"
    fake_loader.write_bytes(b"sandbox loader marker")
    initctl = mock / "initctl"
    data = us / "reading-time/reading-time.tsv"
    initctl.write_text(
        '#!/bin/sh\ncase "$1" in\n'
        f'  start) [ -f "{data.as_posix()}" ] || printf "date\\tbook_id\\tseconds\\ttitle\\n" > "{data.as_posix()}" ;;\n'
        '  status) echo "native-reading-time start/running, process 123" ;;\n'
        'esac\nexit 0\n',
        encoding="utf-8", newline="\n",
    )
    for name, body in {
        "id": '#!/bin/sh\n[ "$1" = -u ] && { echo 0; exit 0; }; /usr/bin/id "$@"\n',
        "mntroot": "#!/bin/sh\nexit 0\n",
        "lipc-get-prop": "#!/bin/sh\nexit 0\n",
        "lipc-set-prop": "#!/bin/sh\nexit 0\n",
        "fbink": "#!/bin/sh\nexit 0\n",
        "lua": "#!/bin/sh\nexit 0\n",
        "sleep": "#!/bin/sh\nexit 0\n",
        "sync": "#!/bin/sh\nexit 0\n",
    }.items():
        (mock / name).write_text(body, encoding="utf-8", newline="\n")
    subprocess.run([SHELL, "-c", '/usr/bin/chmod 755 "$@"', "test", *[p.as_posix() for p in mock.iterdir()]], check=True)

    # The three installer scripts are the only relocated files. The installed
    # application payload stays byte-identical to the archive.
    replacements = {
        "/mnt/us": us.as_posix(),
        "/etc/upstart": upstart.as_posix(),
        "/sbin/initctl": initctl.as_posix(),
        "/lib/ld-linux-armhf.so.3": fake_loader.as_posix(),
    }
    for name in ("install.sh", "Install-Native-Reading-Time.sh", "Install-Native-Reading-Time-Optimized.sh"):
        target = package_dir / name
        script = target.read_text(encoding="utf-8")
        for before, after in replacements.items():
            script = script.replace(before, after)
        target.write_text(script, encoding="utf-8", newline="\n")
    return package_dir, original


def install(package_dir: Path, state: Path, docs: Path, upstart: Path, mock: Path, loader: Path, route: str = "core") -> None:
    env = {
        **os.environ,
        "PATH": mock.as_posix() + ":/usr/bin:/bin:" + os.environ.get("PATH", ""),
        "READING_PACKAGE_DIR": package_dir.as_posix(),
        "READING_BASE": state.as_posix(),
        "READING_DOCUMENTS": docs.as_posix(),
        "READING_UPSTART_DIR": upstart.as_posix(),
        "READING_ARMHF_LOADER_PATH": loader.as_posix(),
        "READING_ARCH_OVERRIDE": "armhf",
    }
    if route == "core":
        command = [SHELL, (package_dir / "install.sh").as_posix(), "install"]
    else:
        us = package_dir.parent
        source = {
            "runme": us / "RUNME.sh",
            "scriptlet": docs / "reading-records-install.sh",
            "kual": us / "extensions/reading-records-installer/bin/action.sh",
        }[route]
        wrapper = state.parent.parent / f"{route}-route.sh"
        wrapper.write_text(source.read_text(encoding="utf-8").replace("/mnt/us", us.as_posix()), encoding="utf-8", newline="\n")
        command = [SHELL, wrapper.as_posix()] + (["install"] if route == "kual" else [])
    result = subprocess.run(command, env=env, capture_output=True, timeout=60)
    if result.returncode:
        log = (state / "install.log").read_text(encoding="utf-8", errors="replace") if (state / "install.log").exists() else "<no log>"
        raise AssertionError((result.returncode, result.stdout, result.stderr, log[-3500:]))


def verify_case(label: str, tag: str | None) -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix="upgrade-matrix-", dir=OUT) as temporary:
        session = Path(temporary)
        us = session / "us"
        state = us / "reading-time"
        docs = us / "documents"
        ext = us / "extensions/reading-records-installer"
        upstart = session / "etc/upstart"
        mock = session / "mockbin"
        for folder in (us, docs, upstart, mock):
            folder.mkdir(parents=True, exist_ok=True)
        if tag is None:
            # mkdir of /mnt/us/documents is allowed; the plugin itself is absent.
            assert not state.exists() and not ext.exists()
        preserved = installed_seed(tag, state, docs, ext, upstart)
        old_release = state / ("releases/9.7.4" if tag == "v9.7.4" else "releases/9.7.5-test")
        old_marker = old_release / "historical-program-marker" if tag else None
        package_dir, package_hashes = prepare_package(session, us, upstart, mock)
        # Only the three relocated installer scripts differ from packaged bytes.
        for name in entries:
            if name not in {
                "native-reading-time-package/install.sh",
                "native-reading-time-package/Install-Native-Reading-Time.sh",
                "native-reading-time-package/Install-Native-Reading-Time-Optimized.sh",
            }:
                assert sha((us / name).read_bytes()) == package_hashes[name], name
        loader = session / "ld-linux-armhf.so.3"
        route = {"v9.7.4": "runme", "v9.7.5-test.1": "scriptlet", "v9.7.5-compat-v2": "kual", "v3": "kual", None: "scriptlet"}[tag]
        install(package_dir, state, docs, upstart, mock, loader, route)
        if tag == "v3":
            first_install_data = {path: Path(path).read_bytes() for path in preserved}
            install(package_dir, state, docs, upstart, mock, loader, route)
            assert all(Path(path).read_bytes() == raw for path, raw in first_install_data.items())

        for path, raw in preserved.items():
            assert Path(path).read_bytes() == raw, (label, path)
        assert (state / "reading-time.tsv").is_file()
        assert (state / "book-covers").is_dir()
        assert not list((state / "book-covers").glob(".install-write-test.*"))
        if tag is None:
            assert (state / "reading-time.tsv").read_bytes() == b"date\tbook_id\tseconds\ttitle\n"
        else:
            assert old_marker is not None and old_marker.read_bytes() == tag.encode()
        active = state / "releases/9.7.5-test/bin/reading-records.sh"
        assert active.read_bytes() == resolver_bytes
        assert (state / "bin/launch.sh").read_bytes() == (us / "native-reading-time-package/launch.sh").read_bytes()
        assert (docs / "阅读记录.sh").read_bytes() == (us / "native-reading-time-package/阅读记录-entry.sh").read_bytes()
        assert sha((docs / "reading-records-install.sh").read_bytes()) == package_hashes["documents/reading-records-install.sh"]
        assert 'RELEASE="$BASE/releases/9.7.5-test"' in (state / "bin/launch.sh").read_text(encoding="utf-8")
        assert 'MAIN="$RELEASE/bin/reading-records.sh"' in (state / "bin/launch.sh").read_text(encoding="utf-8")
        for helper in ("reading-insights-cover.lua", "reading-insights-cache.awk", "reading-insights-render.lua", "reading-insights-touch-ui.lua"):
            assert (state / "releases/9.7.5-test/bin" / helper).read_bytes() == (package_dir / helper).read_bytes()
        for target, source in {
            state / "bin/diagnostics.sh": package_dir / "diagnostics.sh",
            state / "bin/uninstall.sh": package_dir / "uninstall.sh",
            state / "install-manifest.txt": package_dir / "install-manifest.txt",
            docs / "reading-records-uninstall.sh": package_dir / "resources/reading-records-uninstall.sh",
            ext / "bin/action.sh": package_dir / "resources/kual/reading-records-installer/bin/action.sh",
            ext / "config.xml": package_dir / "resources/kual/reading-records-installer/config.xml",
            ext / "menu.json": package_dir / "resources/kual/reading-records-installer/menu.json",
        }.items():
            assert target.read_bytes() == source.read_bytes(), (label, target)
        assert (state / "VERSION").read_text(encoding="utf-8").strip() == "9.7.5-test"
        assert (upstart / "native-reading-time.conf").read_bytes() == (package_dir / "native-reading-time.conf").read_bytes()
        log = (state / "install.log").read_text(encoding="utf-8")
        assert "final sanity resolver=ok launcher=ok entry=ok helpers=ok history=ok cover_cache=ok" in log
        assert "source resolver path=" in log and "installed resolver path=" in log

        # Run the shipped installed resolver, with no Reading Time cover map,
        # against the exact duplicate-row regression fixture and cache-hit case.
        cover_result = subprocess.run(
            ["python", (ROOT / "tests/validate_cover_regression.py").as_posix()],
            cwd=ROOT,
            env={**os.environ, "READING_TEST_RESOLVER": active.as_posix()},
            capture_output=True,
            timeout=60,
        )
        assert cover_result.returncode == 0, (label, cover_result.stdout, cover_result.stderr)
        return {
            "installer": "PASS",
            "data_preserved": "PASS" if tag else "N/A (new history created)",
            "old_covers_preserved": "PASS" if tag else "N/A",
            "resolver_updated": "PASS",
            "launcher_and_helpers": "PASS",
            "new_cover_resolution": "PASS (sandbox fixture)",
            "idempotent": "PASS" if tag == "v3" else "N/A",
        }


results = {label: verify_case(label, tag) for label, tag in CASES.items()}

# A package with a stale launcher target must fail and roll back, even when
# its file copies all succeeded. This directly exercises the final sanity gate.
with tempfile.TemporaryDirectory(prefix="upgrade-invalid-target-", dir=OUT) as temporary:
    session = Path(temporary)
    us = session / "us"
    state = us / "reading-time"
    docs = us / "documents"
    ext = us / "extensions/reading-records-installer"
    upstart = session / "etc/upstart"
    mock = session / "mockbin"
    for folder in (us, docs, upstart, mock):
        folder.mkdir(parents=True, exist_ok=True)
    protected = installed_seed("v9.7.5-compat-v2", state, docs, ext, upstart)
    previous_resolver = (state / "releases/9.7.5-test/bin/reading-records.sh").read_bytes()
    package_dir, _ = prepare_package(session, us, upstart, mock)
    launcher_payload = package_dir / "launch.sh"
    launcher_payload.write_text(
        launcher_payload.read_text(encoding="utf-8").replace(
            'RELEASE="$BASE/releases/9.7.5-test"',
            'RELEASE="$BASE/releases/stale-release"',
        ),
        encoding="utf-8", newline="\n",
    )
    try:
        install(package_dir, state, docs, upstart, mock, session / "ld-linux-armhf.so.3")
    except AssertionError:
        pass
    else:
        raise AssertionError("stale launcher package was accepted")
    assert "launcher does not target the active release resolver" in (state / "install.log").read_text(encoding="utf-8")
    assert all(Path(path).read_bytes() == raw for path, raw in protected.items())
    assert (state / "releases/9.7.5-test/bin/reading-records.sh").read_bytes() == previous_resolver

report = {
    "result": "PASS",
    "archive": str(ARCHIVE),
    "archive_sha256": sha(ARCHIVE.read_bytes()),
    "resolver_sha256": sha(resolver_bytes),
    "package_entries_verified": len(entries) + 1,
    "invalid_launcher_rejected_and_rolled_back": "PASS",
    "matrix": results,
    "limitation": "Filesystem and installer shell paths are relocated; Kindle service, firmware, and display are mocked. V3 native-cover resolution is executed with a fixture, not a live cc.db.",
}
(OUT / "upgrade-matrix.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
