"""Exercise the changed KS page geometry without creating a release archive."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import shutil
import subprocess
import tempfile


from validate_ks_compat_sync import setup


ROOT = Path(__file__).resolve().parents[1]
SHELL = next(
    path for path in (shutil.which("sh"), r"C:\Program Files\Git\bin\sh.exe")
    if path and Path(path).is_file()
)

with tempfile.TemporaryDirectory(prefix="ks-layout-flow-", dir=ROOT / "build") as directory:
    actions = (
        "tab_books\nbooks_all\nbook_row_6\nbook_detail_back\n"
        "tab_total\nweek_trend_open\nweek_trend_back\n"
        "tab_daily\nexit\n"
    )
    base, environment = setup(Path(directory), version="5.19.6", geometry="1860 2480", lock="U", actions=actions)
    release = base / "releases/9.7.5-ks-test1"
    environment["READING_EVENT_STRUCT_SIZE"] = "16"
    today = date.today().isoformat()
    with (base / "reading-time.tsv").open("a", encoding="utf-8") as history:
        for index in range(1, 8):
            history.write(f"{today}\tKSBOOK{index}\t{index * 600}\tKS Test Book {index}\n")
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
