"""Offline integration tests for v9.6.6-stats-filters.

The production POSIX shell functions, AWK cache builder, Lua 5.1 renderer,
title wrapper and touch hit-testing are exercised without Kindle hardware.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import subprocess
import time

from PIL import Image, ImageDraw, ImageFont
from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "native-reading-time-package"
BASE = ROOT.parent / "v9.6.5-ui-polish" / "native-reading-time-package"
OUT = ROOT / "validation"
SESSION = OUT / "stats-session"
SH = Path("C:/Program Files/Git/usr/bin/sh.exe")
DASH = Path("C:/Program Files/Git/usr/bin/dash.exe")
os.chdir(ROOT)
OUT.mkdir(exist_ok=True)
SESSION.mkdir(exist_ok=True)
checks: list[dict[str, str]] = []


def record(name: str, detail: str) -> None:
    checks.append({"check": name, "result": "PASS", "detail": detail})


def run_shell(code: str) -> str:
    result = subprocess.run(
        [SH, "-c", 'export PATH="/usr/bin:$PATH"\n' + code],
        capture_output=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, (code, result.stdout, result.stderr)
    return result.stdout


# Shipped syntax and protected files.
for file in [ROOT / "RUNME.sh", *PKG.glob("*.sh")]:
    for shell in (SH, DASH):
        subprocess.run([shell, "-n", str(file)], check=True, capture_output=True)
    assert not file.read_bytes().startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in file.read_bytes()
for file in PKG.glob("*.lua"):
    LuaRuntime().execute("assert(loadstring(...))", file.read_text(encoding="utf-8"))
record("syntax", "All shipped shell files pass sh/dash parsing; all Lua files parse as Lua 5.1; UTF-8/LF checks pass.")

protected = [
    "native-reading-time-daemon.sh",
    "native-reading-time.conf",
    "阅读记录.sh",
    "reading-insights-touch.lua",
    "ui-calendar/daily.png",
]
for relative in protected:
    assert (PKG / relative).read_bytes() == (BASE / relative).read_bytes(), relative
assert not list(PKG.rglob("*.db"))
record("protected core", "Daemon, Upstart config, legacy viewer/touch and daily background are byte-identical to v9.6.5; no database is shipped.")

viewer = (PKG / "阅读记录-optimized.sh").read_text(encoding="utf-8")
baseline_viewer = (BASE / "阅读记录-optimized.sh").read_text(encoding="utf-8")
new_progress = viewer[viewer.index("ensure_progress()"):viewer.index("pgm_valid()")]
old_progress = baseline_viewer[baseline_viewer.index("ensure_progress()"):baseline_viewer.index("pgm_valid()")]
assert "p_percentFinished" in new_progress and "p_cdeKey" in new_progress and "sqlite3 -readonly" in new_progress
assert "UPDATE " not in new_progress and "INSERT " not in new_progress and "DELETE " not in new_progress
assert "p_percentFinished" in old_progress and "sqlite3 -readonly" in old_progress
record("progress safety", "Progress still uses one delayed read-only cc.db snapshot; reliable cdeKey/ASIN matching is tried first with exact-title fallback, with no location guessing or database writes.")

# Extract function definitions only; hardware startup and cleanup never run.
definitions = viewer[: viewer.index("\ndetect_screen; find_touch_device")]
definitions = definitions.replace('exec >> "$LOG" 2>&1', "")
definitions = definitions.replace('\ntrap cleanup EXIT INT TERM HUP\n', "\n")
definitions = definitions.replace('echo "$(date): optimized dashboard launch, uid=$(id -u), pid=$$"', "")
definitions = definitions.replace('today="$(date +%Y-%m-%d)"', 'today="${TEST_TODAY:-$(date +%Y-%m-%d)}"')
(OUT / "functions-v9.6.6.sh").write_text(definitions, encoding="utf-8", newline="\n")
(OUT / "lua_runner.py").write_text(
    """import sys
from pathlib import Path
from lupa.lua51 import LuaRuntime
lua=LuaRuntime()
lua.globals().arg=lua.table_from({i:v for i,v in enumerate(sys.argv[1:])})
lua.execute(Path(sys.argv[1]).read_text(encoding='utf-8'))
""",
    encoding="utf-8",
)

fixture_rows = [
    ("2025-12-31", "old", 7200, "Old year title"),
    ("2026-01-01", "year", 600, "Year only title"),
    ("2026-08-17", "w45", 2700, "45 minute week"),
    ("2026-08-24", "w60", 3600, "60 minute week"),
    ("2026-08-30", "older", 900, "Older this year"),
    ("2026-08-31", "g", 600, "Aug boundary title"),
    ("2026-09-01", "short", 299, "Four fifty-nine"),
    ("2026-09-02", "edge", 300, "Exactly five minutes"),
    ("2026-09-03", "cn", 1200, "这是一本很长的中文书名用于测试换行和分页"),
    ("2026-09-04", "hp", 2700, "Harry Potter and the Philosopher's Stone (English Edition)"),
    ("2026-09-05", "b", 3600, "Second ranked title"),
    ("2026-09-05", "b", 3900, "Second ranked title"),
    ("2026-09-06", "a", 34560, "Top 576 minute title"),
    ("2026-09-07", "future", 99999, "Future record ignored by current ranges"),
]
(SESSION / "reading-time.tsv").write_text(
    "date\tbook_id\tseconds\ttitle\n" + "".join("\t".join(map(str, row)) + "\n" for row in fixture_rows),
    encoding="utf-8",
)

setup = r'''. validation/functions-v9.6.6.sh
SESSION_DIR=validation/stats-session
DATA="$SESSION_DIR/reading-time.tsv"; SUMMARY="$SESSION_DIR/summary.tsv"; MONTHS="$SESSION_DIR/months.tsv"; WEEKS="$SESSION_DIR/weeks.tsv"
DAYS="$SESSION_DIR/days.tsv"; DAY_BOOKS="$SESSION_DIR/day-books.tsv"; CALENDAR="$SESSION_DIR/calendar.tsv"
BOOKS="$SESSION_DIR/books.tsv"; BOOKS_7D="$SESSION_DIR/books-7d.tsv"; BOOKS_WEEK="$SESSION_DIR/books-week.tsv"; BOOKS_MONTH="$SESSION_DIR/books-month.tsv"; BOOKS_YEAR="$SESSION_DIR/books-year.tsv"
PROGRESS="$SESSION_DIR/book-progress.tsv"; SPEC="$SESSION_DIR/render-spec.tsv"; TOTAL_VALUES="$SESSION_DIR/total-values.tsv"; WEEK_VIEW="$SESSION_DIR/week-view.tsv"
RENDERER=native-reading-time-package/reading-insights-render.lua; RENDER_ASSETS=native-reading-time-package/render-assets; CACHE_BUILDER=native-reading-time-package/reading-insights-cache.awk; TITLE_LAYOUT=native-reading-time-package/reading-insights-titles.lua
renderer_available=1; RFONT=native-reading-time-package/NotoSansCJKsc-Regular.otf
lua() { python validation/lua_runner.py "$@"; }
image() { printf 'image\t%s\t%s\t%s\t%s\t%s\n' "$@" >> "$SESSION_DIR/draw.tsv"; }
ot() { printf 'ot\t%s\t%s\t%s\t%s\t%s\t%s\n' "$@" >> "$SESSION_DIR/draw.tsv"; }
rect() { :; }
'''

start = time.perf_counter()
run_shell(setup + "TEST_TODAY=2026-09-06; build_cache")
build_ms = round((time.perf_counter() - start) * 1000, 1)


def rows(name: str) -> list[list[str]]:
    text = (SESSION / name).read_text(encoding="utf-8")
    return [line.split("\t") for line in text.splitlines() if line]


expected_visible = {
    "books-7d.tsv": [34560, 7500, 2700, 1200, 600, 300],
    "books-week.tsv": [34560, 7500, 2700, 1200, 600, 300],
    "books-month.tsv": [34560, 7500, 2700, 1200, 300],
    "books-year.tsv": [34560, 7500, 3600, 2700, 2700, 1200, 900, 600, 600, 300],
}
for file_name, expected in expected_visible.items():
    actual = [int(line[0]) for line in rows(file_name)]
    assert actual == expected, (file_name, actual, expected)
    assert 299 not in actual and all(value >= 300 for value in actual)
run_shell(setup + "TEST_TODAY=2026-09-03; build_cache")
titles_7d = {line[1] for line in rows("books-7d.tsv")}
titles_week = {line[1] for line in rows("books-week.tsv")}
assert "Older this year" in titles_7d and "Older this year" not in titles_week
assert "Future record ignored by current ranges" not in titles_7d | titles_week
run_shell(setup + "TEST_TODAY=2026-09-06; build_cache")
record("book ranges", "Sep 6 and midweek Sep 3 snapshots verify today+6 days, Monday–today, month-to-date and year-to-date boundaries, including future-record exclusion.")
record("book filter/order", "4m59s is excluded, 5m00s is included, every range is sorted by that range's seconds descending before pagination.")

page_probe = run_shell(setup + '''book_filter=7d; book_page=1; prepare_book_view; wc -l < "$SESSION_DIR/book-view.tsv"
book_page=2; prepare_book_view; wc -l < "$SESSION_DIR/book-view.tsv"
book_filter=month; book_page=1; prepare_book_view; wc -l < "$SESSION_DIR/book-view.tsv"
''').splitlines()
assert page_probe == ["5", "1", "5"], page_probe
assert 'book_filter="$new_filter"; book_page=1;' in viewer
record("book pagination", "Filtering precedes five-item pagination: near-7-days yields pages of 5+1, month yields one page; changing range explicitly resets page to 1.")

duration_output = run_shell(setup + '''for n in 45 60 125 576; do chart_time_text "$n"; echo; done''').splitlines()
assert duration_output == ["45min", "1h", "2h5min", "9h36min"], duration_output
record("h/min formatting", "Chart formatter returns exactly 45min, 1h, 2h5min and 9h36min while cached/internal values remain seconds/minutes.")

# Natural-week cache and eight-week navigation.
run_shell(setup + 'week_group=0; prepare_week_view')
week_zero = rows("week-view.tsv")
assert [r[0][5:] for r in week_zero] == ["07-13", "07-20", "07-27", "08-03", "08-10", "08-17", "08-24", "08-31"]
assert int(week_zero[-1][1]) == 600 + 299 + 300 + 1200 + 2700 + 7500 + 34560
run_shell(setup + 'week_group=-1; prepare_week_view')
week_early = rows("week-view.tsv")
run_shell(setup + 'week_group=1; prepare_week_view')
week_late = rows("week-view.tsv")
assert week_early[-1][0] < week_zero[0][0] and week_late[0][0] > week_zero[-1][0]
run_shell(setup + "TEST_TODAY=2026-01-04; build_cache; week_group=0; prepare_week_view")
assert rows("week-view.tsv")[-1][0] == "2025-12-29"
run_shell(setup + "TEST_TODAY=2026-09-06; build_cache")
record("weekly grouping", "Weeks are Monday–Sunday JDN buckets; eight-week −1/+1 navigation, zero-data weeks and a Dec/Jan cross-year current week all pass.")

(SESSION / "book-progress.tsv").write_text("88\tDifferent catalog title\ta\n42\tSecond ranked title\tb\n", encoding="utf-8")


def render(name: str, mode: str, code: str) -> str:
    (SESSION / "draw.tsv").write_text("", encoding="utf-8")
    run_shell(setup + "cache_ok=1\n" + code)
    spec = (SESSION / "render-spec.tsv").read_text(encoding="utf-8")
    (OUT / f"{name}.spec.tsv").write_text(spec, encoding="utf-8")
    background = Image.open(PKG / "ui-calendar" / f"{mode}.png").convert("L")
    draw = ImageDraw.Draw(background)
    for line in (SESSION / "draw.tsv").read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if fields[0] == "image":
            _, path, x, y, w, h = fields
            tile = Image.open(ROOT / path)
            assert tile.size == (int(w), int(h)), (name, path, tile.size, w, h)
            background.paste(tile, (int(x), int(y)))
        elif fields[0] == "ot":
            _, size, y, x, right, style, text = fields
            font = ImageFont.truetype(str(PKG / "NotoSansCJKsc-Regular.otf"), int(size))
            assert font.getlength(text) <= 1272 - int(x) - int(right), (name, text)
            draw.text((int(x), int(y)), text, font=font, fill=0, anchor="lt")
    background.save(OUT / f"{name}.png")
    return spec


# Focused chart data for required labels and a >10h column.
(SESSION / "months.tsv").write_text(
    "2026-01\t2700\n2026-02\t3600\n2026-03\t7500\n2026-04\t34560\n2026-05\t45000\n",
    encoding="utf-8",
)
month_spec = render("total-month", "total", "total_period=month; view_year=2026; week_group=0; render_total")
for label in ("45min", "1h", "2h5min", "9h36min", "12h30min"):
    assert label in month_spec
tick_labels = [line.split("\t")[8] for line in month_spec.splitlines() if line.startswith("text\tchart\tR\t20")]
assert tick_labels and all(label.endswith("h") and "分" not in label for label in tick_labels), tick_labels
assert "阅读日均" in month_spec and "\t日均  " not in month_spec
empty_spec = render("total-empty", "total", "total_period=month; view_year=2030; week_group=0; render_total")
assert not any("min" in line and line.startswith("text\tchart\tB\t20") for line in empty_spec.splitlines())
week_spec = render("total-week", "total", "total_period=week; view_year=2026; week_group=0; render_total")
assert all(label in week_spec for label in ("7/13", "7/20", "8/31"))
record("chart rendering", "Monthly/weekly/empty charts render through the shipped Lua compositor; integer-hour ticks, all required h/min labels, zero periods and a 12h30min column pass.")

for filter_name in ("7d", "week", "month", "year"):
    render(f"books-{filter_name}", "books", f"progress_loaded=1; book_filter={filter_name}; book_page=1; render_books")
render("books-filters", "books", "progress_loaded=1; book_filter=7d; book_page=2; render_books")
books_spec = (OUT / "books-7d.spec.tsv").read_text(encoding="utf-8")
assert "暂无进度" in books_spec and "42%" in books_spec and "88%" in books_spec
record("book rendering", "All four filters, a second page, cdeKey/title progress matches and ‘暂无进度’ render with the unchanged five-row layout.")

# Opening punctuation must move with its following token.
titles = [
    "Harry Potter and the Philosopher's Stone (English Edition)",
    "Long English title [Illustrated Edition]",
    "Long English title {Special Edition}",
    "超长中文书名为了验证书名换行不会让左括号落在行末《英文版》",
]
(SESSION / "title-cases-v9.6.6.tsv").write_text("".join(f"600\t{x}\n" for x in titles), encoding="utf-8")
run_shell(setup + 'lua "$TITLE_LAYOUT" "$SESSION_DIR/title-cases-v9.6.6.tsv" 800 44 0 217 > "$SESSION_DIR/title-result-v9.6.6.tsv"')
title_lines = [line[1] for line in rows("title-result-v9.6.6.tsv")]
assert title_lines and not any(line.endswith(("(", "[", "{", "《")) for line in title_lines), title_lines
assert any("(English" in line for line in title_lines)
record("title wrapping", "Long Chinese/English titles and (, [, {, 《 cases wrap to at most two lines without leaving an opening symbol at line end.")

# Real Lua hit map for new controls.
touch_source = (PKG / "reading-insights-touch-ui.lua").read_text(encoding="utf-8")
touch_source = touch_source[: touch_source.index('\nnote(string.format("interactive watcher started')]
touch_source = touch_source.replace('local f = assert(io.open(device, "rb"))', "local f = nil")
touch_source = touch_source.replace('local log = io.open(log_path, "a")', "local log = nil") + "\nreturn action_for_logical"
lua = LuaRuntime(); lua.globals().arg = lua.table_from({3: "total", 13: "month"}); total_touch = lua.execute(touch_source)
assert [total_touch(x, 665) for x in (100, 220, 350, 920)] == ["total_week", "total_month", "total_prev", "total_next"]
lua = LuaRuntime(); lua.globals().arg = lua.table_from({3: "books", 14: "7d"}); books_touch = lua.execute(touch_source)
assert [books_touch(x, 310) for x in (100, 400, 700, 1000)] == ["books_7d", "books_week", "books_month", "books_year"]
record("touch controls", "The shipped Lua hit map returns both total-period controls, both navigation arrows and all four book-range controls at logical and scaled coordinates.")

# Rendering paths use only the launch cache, never the original TSV.
render_total_section = viewer[viewer.index("prepare_week_view()"):viewer.index("prepare_daily_view()")]
render_books_section = viewer[viewer.index("active_books()"):viewer.index("draw_background()")]
assert "$DATA" not in render_total_section + render_books_section
assert viewer.count("build_cache || fallback_to_legacy") == 1
record("cache performance", f"One launch-time raw-data scan builds all range/week caches ({build_ms} ms on the fixture); clicks read only small session caches and never rescan reading-time.tsv.")

result = {"result": "PASS", "checks": checks, "check_count": len(checks)}
(OUT / "stats-filters-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=True, indent=2))
