"""Exercise RUNME and both installers in isolated, mocked Kindle sandboxes."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess


ROOT = Path(__file__).resolve().parent
PKG = ROOT / "native-reading-time-package"
RUNME = ROOT / "RUNME.sh"
OUT = ROOT / "validation"
SANDBOX = OUT / "install-sandbox"
assert SANDBOX.resolve().is_relative_to(OUT.resolve())
index = 0
while SANDBOX.exists():
    index += 1
    SANDBOX = OUT / f"install-sandbox-{index}"
SANDBOX.mkdir(parents=True)

SH = Path("C:/Program Files/Git/usr/bin/sh.exe")
assert SH.is_file(), "Git for Windows sh.exe is required for installer tests"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_executable(path):
    subprocess.run(
        [str(SH), "-c", '/usr/bin/chmod 755 "$1"', "test", path.as_posix()],
        check=True,
    )


def create_sandbox(name, *, daemon=None, history=None, missing=None, base_failure=False):
    root = SANDBOX / name
    us = root / "us"
    state = us / "reading-time"
    docs = us / "documents"
    etc = root / "etc/upstart"
    mockbin = root / "mockbin"
    payload = us / "native-reading-time-package"
    for folder in (docs, etc, mockbin):
        folder.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PKG, payload)

    service_log = root / "service-calls.log"
    initctl = mockbin / "initctl"
    initctl.write_text(
        "#!/bin/sh\n"
        f'printf \'%s\\n\' "$*" >> "{service_log.as_posix()}"\n'
        "case \"$1\" in status) echo 'native-reading-time start/running, process 123';; esac\n"
        "exit 0\n",
        encoding="utf-8",
        newline="\n",
    )
    make_executable(initctl)

    fake_ld = root / "ld-linux-armhf.so.3"
    if not base_failure:
        fake_ld.write_bytes(b"mock kindle loader\n")

    prelude = (
        'export PATH="/usr/bin:/bin:$PATH"\n'
        "id() { echo 0; }\n"
        "mntroot() { return 0; }\n"
        "lipc-set-prop() { return 0; }\n"
        "killall() { return 0; }\n"
        "sleep() { return 0; }\n"
        "sync() { return 0; }\n"
    )
    for installer_name in (
        "Install-Native-Reading-Time.sh",
        "Install-Native-Reading-Time-Optimized.sh",
    ):
        installer_path = payload / installer_name
        installer = installer_path.read_text(encoding="utf-8")
        installer = installer.replace("/mnt/us", us.as_posix())
        installer = installer.replace("/etc/upstart", etc.as_posix())
        installer = installer.replace("/sbin/initctl", f'"{initctl.as_posix()}"')
        installer = installer.replace("/lib/ld-linux-armhf.so.3", fake_ld.as_posix())
        installer_path.write_text(prelude + installer, encoding="utf-8", newline="\n")

    runme = root / "RUNME.sh"
    runme.write_text(
        'export PATH="/usr/bin:/bin:$PATH"\n'
        + RUNME.read_text(encoding="utf-8").replace("/mnt/us", us.as_posix()),
        encoding="utf-8",
        newline="\n",
    )

    if daemon is not None:
        target = state / "bin/native-reading-time-daemon.sh"
        target.parent.mkdir(parents=True, exist_ok=True)
        if daemon == "payload":
            shutil.copy2(PKG / "native-reading-time-daemon.sh", target)
        else:
            target.write_bytes(daemon)
    if history is not None:
        state.mkdir(parents=True, exist_ok=True)
        (state / "reading-time.tsv").write_bytes(history)
    if missing is not None:
        (payload / missing).unlink()

    return {
        "root": root,
        "state": state,
        "docs": docs,
        "etc": etc,
        "payload": payload,
        "runme": runme,
        "service_log": service_log,
    }


def run(case):
    process = subprocess.run([str(SH), case["runme"].as_posix()], capture_output=True)
    log_path = case["state"] / "install.log"
    log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    install_logs = list(case["root"].rglob("install.log"))
    assert install_logs == [log_path], install_logs
    return process, log


def assert_installed(case):
    state = case["state"]
    release = state / "releases/9.7.1-day-detail"
    assert digest(case["docs"] / "阅读记录.sh") == digest(PKG / "阅读记录-optimized.sh")
    assert digest(state / "bin/native-reading-time-daemon.sh") == digest(
        PKG / "native-reading-time-daemon.sh"
    )
    assert digest(case["etc"] / "native-reading-time.conf") == digest(
        PKG / "native-reading-time.conf"
    )
    assert (state / "VERSION").read_text(encoding="utf-8").strip() == "9.7.1-day-detail"
    for name in (
        "reading-insights-touch-ui.lua",
        "reading-insights-titles.lua",
        "reading-insights-title-widths.lua",
        "reading-insights-cache.awk",
        "reading-insights-render.lua",
    ):
        assert digest(release / "bin" / name) == digest(PKG / name), name
    for name in ("daily.png", "books.png", "total.png", "day_detail.png"):
        assert digest(release / "ui-calendar" / name) == digest(PKG / "ui-calendar" / name)
    service_calls = case["service_log"].read_text(encoding="utf-8")
    assert "start native-reading-time" in service_calls
    assert "status native-reading-time" in service_calls


for shell_script in (
    RUNME,
    PKG / "Install-Native-Reading-Time.sh",
    PKG / "Install-Native-Reading-Time-Optimized.sh",
):
    subprocess.run([str(SH), "-n", shell_script.as_posix()], check=True)

runme_source = RUNME.read_text(encoding="utf-8")
assert "su " not in runme_source and "su\n" not in runme_source
assert 'if [ ! -f "$DAEMON" ]' in runme_source

# 1. A genuinely fresh device gets the base install and then the optimized release.
fresh = create_sandbox("fresh")
p, log = run(fresh)
assert p.returncode == 0, (p.stdout, p.stderr, log)
assert "fresh install detected" in log
assert "base installation completed; continuing to optimized 9.7.1 installation" in log
assert "RUNME completed successfully" in log
assert_installed(fresh)
assert not (fresh["state"] / "reading-time.tsv").exists()
assert not (fresh["state"] / "reading-time.tsv.bak").exists()

# 2. A matching 9.6.3 daemon skips the base installer and preserves history.
history = b"date\tbook_id\tseconds\ttitle\n2026-09-05\tb1\t14760\tKeep reading history\n"
upgrade = create_sandbox("upgrade", daemon="payload", history=history)
p, log = run(upgrade)
assert p.returncode == 0, (p.stdout, p.stderr, log)
assert "existing installation detected; using optimized upgrade path" in log
assert ": installer entered, uid=" not in log
assert "base installation completed" not in log
assert_installed(upgrade)
assert (upgrade["state"] / "reading-time.tsv").read_bytes() == history
assert (upgrade["state"] / "reading-time.tsv.bak").read_bytes() == history

# 3. An unknown daemon still fails the optimized installer's byte-for-byte guard.
mismatch = create_sandbox("mismatched-daemon", daemon=b"modified daemon\n", history=history)
viewer = mismatch["docs"] / "阅读记录.sh"
conf = mismatch["etc"] / "native-reading-time.conf"
viewer.write_bytes(b"existing viewer\n")
conf.write_bytes(b"existing upstart config\n")
before = {path: digest(path) for path in (viewer, conf, mismatch["state"] / "reading-time.tsv")}
p, log = run(mismatch)
assert p.returncode != 0
assert "existing installation detected; using optimized upgrade path" in log
assert "payload daemon differs from installed 9.6.3" in log
assert "optimized installation failed with exit code" in log
assert digest(mismatch["state"] / "bin/native-reading-time-daemon.sh") == hashlib.sha256(
    b"modified daemon\n"
).hexdigest()
assert all(digest(path) == sha for path, sha in before.items())
assert not mismatch["service_log"].exists()
assert not (mismatch["state"] / "VERSION").exists()

# 4. Partial state without a daemon is repaired without altering existing history.
partial = create_sandbox("partial", history=history)
(partial["state"] / "fonts").mkdir()
(partial["state"] / "ui").mkdir()
(partial["state"] / "partial-marker").write_bytes(b"keep me\n")
existing_backup = b"pre-existing reading history backup\n"
(partial["state"] / "reading-time.tsv.bak").write_bytes(existing_backup)
p, log = run(partial)
assert p.returncode == 0, (p.stdout, p.stderr, log)
assert "fresh install detected" in log
assert_installed(partial)
assert (partial["state"] / "reading-time.tsv").read_bytes() == history
assert (partial["state"] / "reading-time.tsv.bak").read_bytes() == existing_backup
assert (partial["state"] / "partial-marker").read_bytes() == b"keep me\n"

# 5. Either missing installer is rejected before a partial installation starts.
for missing_name in (
    "Install-Native-Reading-Time.sh",
    "Install-Native-Reading-Time-Optimized.sh",
):
    case = create_sandbox(f"missing-{missing_name}", missing=missing_name)
    p, log = run(case)
    assert p.returncode != 0
    assert f"installer not found: {case['payload'].as_posix()}/{missing_name}" in log
    assert "fresh install detected" not in log
    assert "optimized installer entered" not in log
    assert not (case["state"] / "bin/native-reading-time-daemon.sh").exists()
    assert not (case["docs"] / "阅读记录.sh").exists()

# 6. A base-installer failure stops the chain before optimized installation.
base_failure = create_sandbox("base-failure", base_failure=True)
p, log = run(base_failure)
assert p.returncode != 0
assert "fresh install detected" in log
assert "not a kindlehf device" in log
assert "base installation failed with exit code" in log
assert "optimized installation not started" in log
assert "optimized installer entered" not in log
assert not (base_failure["state"] / "VERSION").exists()

result = {
    "result": "PASS",
    "scenarios": {
        "fresh install": "base then optimized; launcher, daemon, service config and VERSION installed",
        "matching 9.6.3 upgrade": "base skipped; optimized succeeded; history preserved and backed up",
        "mismatched daemon": "optimized cmp guard rejected it before service or data changes",
        "partial install": "missing daemon selected repair path; history, prior backup and unrelated state preserved",
        "incomplete payload": "missing base or optimized installer rejected before installation",
        "base failure": "non-zero status stopped the chain before optimized installation",
    },
    "checks": [
        "RUNME and both installers pass shell syntax validation.",
        "All RUNME and installer messages use the same install.log in each sandbox.",
        "No test performs an on-device install; Kindle service, rootfs and toaster calls are mocked.",
    ],
}
(OUT / "installer-results.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(result, ensure_ascii=False, indent=2))
