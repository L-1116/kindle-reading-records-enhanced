"""Exercise the changed KS page geometry without creating a release archive."""

from __future__ import annotations

from datetime import date
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "build/ks-runtime-sim2"
KS = ROOT / "ks-package/native-reading-time-package"
SHELL = next(
    path for path in (shutil.which("sh"), r"C:\Program Files\Git\bin\sh.exe")
    if path and Path(path).is_file()
)

with tempfile.TemporaryDirectory(prefix="ks-layout-flow-", dir=ROOT / "build") as directory:
    base = Path(directory) / "reading-time"
    shutil.copytree(SOURCE, base)
    (base / "reading_time_ks_debug.log").write_text("", encoding="utf-8")
    release = base / "releases/9.7.5-ks-test1"
    shutil.copy2(KS / "阅读记录-ks.sh", release / "bin/reading-records-ks.sh")
    shutil.copy2(KS / "reading-insights-touch-ks.lua", release / "bin/reading-insights-touch-ks.lua")
    for image in (KS / "ui-scribe").glob("*.png"):
        shutil.copy2(image, release / "ui-scribe" / image.name)
    today = date.today().isoformat()
    with (base / "reading-time.tsv").open("a", encoding="utf-8") as history:
        for index in range(1, 8):
            history.write(f"{today}\tKSBOOK{index}\t{index * 600}\tKS Test Book {index}\n")
    actions = (
        "tab_books\nbooks_all\nbook_row_6\nbook_detail_back\n"
        "tab_total\nweek_trend_open\nweek_trend_back\n"
        "tab_daily\nexit\n"
    )
    (base / "actions.txt").write_text(actions, encoding="utf-8", newline="\n")
    touch = base / "touch-device"
    touch.write_bytes(b"")
    environment = {
        **os.environ,
        "PATH": (base / "bin").as_posix() + ":/usr/bin:/bin:" + os.environ.get("PATH", ""),
        "READING_BASE": base.as_posix(),
        "READING_FBINK": (base / "bin/fbink").as_posix(),
        "READING_TOUCH_DEVICE": touch.as_posix(),
        "READING_TMPDIR": (base / "tmp").as_posix(),
        "KS_SIM_ACTIONS_FILE": (base / "actions.txt").as_posix(),
    }
    result = subprocess.run(
        [SHELL, (release / "bin/reading-records-ks.sh").as_posix()],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    log = (base / "reading_time_ks_debug.log").read_text(encoding="utf-8", errors="replace")
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr, log[-5000:])
    for action in ("tab_books", "book_row_6", "book_detail_back", "tab_total", "week_trend_open", "tab_daily", "exit"):
        assert f"[NAV] action={action}" in log, action
    assert "[UI] first paint completed" in log
    assert "[EXIT] finished" in log
    assert "[ERROR]" not in log, log[-3000:]
    assert not list((base / "tmp").glob("native-reading-dashboard-ks.*"))

print("KS 2x3 book page, sixth-card detail, chart navigation and cleanup: PASS")
