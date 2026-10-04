"""Static, layout and package validation for the standalone KS variant."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
KS = ROOT / "ks-package"
PKG = KS / "native-reading-time-package"
ARCHIVE = ROOT / "dist/ReadingTime-v9.7.5-KS-touch-compat-hotfix.zip"


def check_shell_syntax() -> None:
    candidates = [shutil.which("sh"), r"C:\Program Files\Git\bin\sh.exe"]
    shell = next((Path(path) for path in candidates if path and Path(path).is_file()), None)
    if shell is None:
        return
    for path in KS.rglob("*.sh"):
        subprocess.run([str(shell), "-n", str(path)], check=True)


def main() -> None:
    main_sh = (PKG / "阅读记录-ks.sh").read_text(encoding="utf-8")
    touch = (PKG / "reading-insights-touch-ks.lua").read_text(encoding="utf-8")
    probe = (PKG / "reading-insights-touch-probe-ks.lua").read_text(encoding="utf-8")
    installer = (PKG / "Install-Native-Reading-Time-KS.sh").read_text(encoding="utf-8")
    launcher = (PKG / "launch-ks.sh").read_text(encoding="utf-8")
    force_exit = (PKG / "force-exit-ks.sh").read_text(encoding="utf-8")

    assert "LAYOUT_PROFILE=scribe" in main_sh
    assert "LOGICAL_W=1860; LOGICAL_H=2480" in main_sh
    assert "BOOK_PAGE_SIZE=6" in main_sh
    assert "BOOK_COLUMN_STEP=850" in main_sh
    assert "canvas summary 1640 480" in main_sh
    assert "每日阅读趋势" in main_sh
    assert "native-reading-dashboard-ks" in main_sh
    assert "pt_mt" in probe and "capabilities/abs" in probe
    assert 'TOUCH="/dev/input/event1"' not in main_sh
    assert "reading_time_ks_debug.log" in main_sh and "[UI] first paint completed" in main_sh
    for tag in ("[BOOT]", "[DEVICE]", "[RUNTIME]", "[UI]", "[NAV]", "[EXIT]", "[ERROR]"):
        assert tag in main_sh or tag in launcher or tag in force_exit, tag
    assert "[INPUT] touch received" in touch
    assert "raw_x=" in touch and "client_x=" in touch and "transform=" in touch
    assert "direct" in touch and "swap" in touch and "invert_xy" in touch
    assert "reading-time-ks-ui.pid" in main_sh and "reading-time-ks-ui.pid" in force_exit
    assert "kill -TERM" in force_exit and "kill -KILL" in force_exit
    assert "KPP_LIBRARY" in force_exit and "preventScreenSaver 0" in force_exit
    assert "fbink" not in force_exit.lower(), "force-exit must recover through LIPC without an unchecked runtime"
    assert "9.7.5-ks-test1" in installer and "9.7.5-test" not in installer
    assert 'compat/detect_env.sh' in installer and '"$DETECTOR"' in installer
    assert "reading-time.tsv" in installer and '>' + ' "$BASE/reading-time.tsv"' not in installer
    assert "reading history is missing" in installer and "reading history preserved" in installer
    assert 'LOG="$BASE/launch-last.log"' in launcher and ': > "$LOG"' in launcher
    assert 'MAIN="$RELEASE/bin/reading-records-ks.sh"' in launcher
    assert '"$RELEASE/ui-scribe/daily.png"' in launcher
    assert 'bin/reading-records.sh' not in launcher and 'ui-calendar' not in launcher
    assert "legacy fallback intentionally disabled" in main_sh
    from lupa.lua51 import LuaRuntime
    LuaRuntime().execute("assert(loadstring(...))", touch)
    LuaRuntime().execute("assert(loadstring(...))", probe)
    hit_test_source = (
        'local mode, calendar_offset, calendar_days, detail_pages, detail_page, pager_y, total_period = "books", 1, 30, 1, 1, 0, "week"\n'
        'local function inside(x, y, left, top, right, bottom) return x >= left and y >= top and x <= right and y <= bottom end\n'
        + touch[touch.index("local function action_for_logical"):touch.index("-- Map physical framebuffer coordinates")]
        + '\nreturn function(page, x, y) mode=page; return action_for_logical(x, y) end'
    )
    hit = LuaRuntime().execute(hit_test_source)
    for row, y in enumerate((700, 1240, 1780)):
        assert hit("books", 110, y) == f"book_row_{row * 2 + 1}"
        assert hit("books", 900, y) == f"book_row_{row * 2 + 1}"
        assert hit("books", 950, y) == f"book_row_{row * 2 + 2}"
        assert hit("books", 1740, y) == f"book_row_{row * 2 + 2}"
        assert hit("books", 925, y) == "ignore"
    assert hit("daily", 460, 600) == "day_1"
    assert hit("book_detail", 460, 1850) == "book_day_1"
    assert hit("book_detail", 560, 1690) == "book_month_prev"
    title_helper = ROOT / "native-reading-time-package/reading-insights-titles.lua"
    title_widths = [float(value) for value in re.findall(r"\d+\.\d+", (ROOT / "native-reading-time-package/reading-insights-title-widths.lua").read_text(encoding="utf-8"))]
    for sample in (
        "被讨厌的勇气：自我启发之父阿德勒的教导与更多故事",
        "A Very Long English Book Title About Reading and More Reading",
        "SupercalifragilisticexpialidociousWithoutAnySpacesAtAll",
    ):
        lua = LuaRuntime()
        lua.globals().arg = lua.table_from({1: "unused", 2: "520", 3: "36", 4: "0", 5: "545"})
        lua.globals().arg[0] = title_helper.as_posix()
        lua.globals().sample_line = "3600\t" + sample
        lua.globals().advances = lua.table_from(title_widths)
        lua.execute(
            "dofile=function() return advances end; local used=false; io.lines=function() return function() if used then return nil end; used=true; return sample_line end end; "
            "captured={}; io.write=function(...) for i=1,select('#',...) do captured[#captured+1]=tostring(select(i,...)) end end"
        )
        lua.execute(title_helper.read_text(encoding="utf-8"))
        lines = lua.eval("table.concat(captured)").splitlines()
        assert 1 <= len(lines) <= 2, (sample, lines)
        assert all(line.split("\t", 1)[1] for line in lines), (sample, lines)
        assert all(int(line.split("\t", 1)[0]) < 545 for line in lines), (sample, lines)

    for path in sorted((PKG / "ui-scribe").glob("*.png")):
        with Image.open(path) as image:
            assert image.size == (1860, 2480), (path, image.size)
            assert image.mode == "L", (path, image.mode)
    assert {path.name for path in (PKG / "ui-scribe").glob("*.png")} == {
        "daily.png", "books.png", "total.png", "day_detail.png",
        "month_detail.png", "week_trend.png", "book_detail.png",
    }
    for path in (ROOT / "build/ks-preview").glob("ks-*-preview.png"):
        assert Image.open(path).size == (1860, 2480)
    for path in (ROOT / "build/ks-preview").glob("standard-*-preview.png"):
        assert Image.open(path).size == (1272, 1696)
    assert len(list((ROOT / "build/ks-preview").glob("ks-*-preview.png"))) == 5

    # Geometry invariants shared by renderer and hit testing.
    assert "local logical_w, logical_h = 1860, 2480" in touch
    assert "px >= 100 and px < 1759" in touch
    assert "math.floor((px - 100) / 237)" in touch
    assert "local row = math.floor((py - 465) / 545)" in touch
    assert 'return "book_row_" .. (row * 2 + column + 1)' in touch
    assert "math.floor(1120 / rows)" in touch
    assert "math.floor(430 / rows)" in touch

    check_shell_syntax()
    if "--package" not in sys.argv:
        print(json.dumps({"result": "PASS", "variant": "KS layout", "ui": "1860x2480", "book_page_size": 6, "package_rebuilt": False}, ensure_ascii=False))
        return
    subprocess.run([shutil.which("python") or "python", str(ROOT / "scripts/package_ks_release.py")], cwd=ROOT, check=True)
    assert ARCHIVE.is_file()
    with zipfile.ZipFile(ARCHIVE) as package:
        assert package.testzip() is None
        names = set(package.namelist())
        assert "native-reading-time-package/Install-Native-Reading-Time-Optimized.sh" not in names
        for required in (
            "RUNME.sh", "README.txt", "documents/reading-records-ks-install.sh",
            "documents/reading-records-ks-force-exit.sh", "native-reading-time-package/install.sh",
            "native-reading-time-package/Install-Native-Reading-Time-KS.sh",
            "native-reading-time-package/阅读记录-ks.sh",
            "native-reading-time-package/reading-insights-touch-ks.lua",
            "native-reading-time-package/reading-insights-touch-probe-ks.lua",
            "native-reading-time-package/compat/detect_env.sh",
            "native-reading-time-package/ui-scribe/daily.png",
            "PACKAGE-MANIFEST-KS.json",
        ):
            assert required in names, required
        manifest = json.loads(package.read("PACKAGE-MANIFEST-KS.json"))
        assert manifest["variant"] == "kindle-scribe"
        for item in manifest["files"]:
            raw = package.read(item["path"])
            assert len(raw) == item["size"]
            assert hashlib.sha256(raw).hexdigest() == item["sha256"]

    print(json.dumps({"result": "PASS", "variant": "KS", "archive": str(ARCHIVE), "ui": "1860x2480", "book_page_size": 6}, ensure_ascii=False))


if __name__ == "__main__":
    main()
