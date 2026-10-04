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
