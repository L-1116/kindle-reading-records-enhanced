"""Install Python runtime mocks using the interpreter running the test suite."""

from pathlib import Path
import shlex
import shutil
import sys


def install_python_fixture(source: Path, target: Path) -> None:
    payload = target.with_name(target.name + ".py")
    shutil.copy2(source, payload)
    target.write_text(
        "#!/bin/sh\nexec " + shlex.quote(Path(sys.executable).as_posix())
        + " " + shlex.quote(payload.as_posix()) + ' "$@"\n',
        encoding="utf-8", newline="\n",
    )
    target.chmod(0o755)


def install_power_fixture(release: Path, mockbin: Path) -> None:
    """Real frontend power module, with a blocking mock of the device event bus."""
    root = Path(__file__).resolve().parents[1]
    shutil.copy2(root / "native-reading-time-package/reading-power.sh", release / "bin/reading-power.sh")
    mockbin.mkdir(parents=True, exist_ok=True)
    fifo = mockbin / "power-events"
    shell = shutil.which("sh") or "C:/Program Files/Git/usr/bin/sh.exe"
    if not fifo.exists():
        import subprocess
        subprocess.run([shell, "-c", '/usr/bin/mkfifo "$1"', "fixture", fifo.as_posix()], check=True)
    target = mockbin / "lipc-wait-event"
    target.write_text("#!/bin/sh\n" +
        '[ -z "${POWER_TEST_PID:-}" ] || echo $$ > "$POWER_TEST_PID"\n' +
        '[ "${POWER_TEST_FAIL:-0}" != 1 ] || exit 2\n' +
        'exec 8<>"${0%/*}/power-events"\nIFS= read -r event <&8\nprintf "%s\\n" "$event"\n',
        encoding="utf-8", newline="\n")
    import subprocess
    subprocess.run([shell, "-c", '/usr/bin/chmod 755 "$1"', "fixture", target.as_posix()], check=True)
