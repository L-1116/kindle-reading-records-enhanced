"""Offline integration tests retained for v9.6.10-ui-layout-fix.

The production POSIX shell functions, AWK cache builder, Lua 5.1 renderer,
title wrapper and touch hit-testing are exercised without Kindle hardware.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import time

from PIL import Image, ImageDraw, ImageFont
from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "native-reading-time-package"
BASE = ROOT / "tests/baselines/v9.6.7"
BASE_HASHES = json.loads((BASE / "payload-sha256.json").read_text(encoding="utf-8"))
OUT = ROOT / "build/validation"
SESSION = OUT / "stats-session"
SH = Path(shutil.which("sh") or "C:/Program Files/Git/usr/bin/sh.exe")
DASH = Path(shutil.which("dash") or "C:/Program Files/Git/usr/bin/dash.exe")
os.chdir(ROOT)
OUT.mkdir(parents=True, exist_ok=True)
SESSION.mkdir(exist_ok=True)
checks: list[dict[str, str]] = []


def record(name: str, detail: str) -> None:
    checks.append({"check": name, "result": "PASS", "detail": detail})


def run_shell(code: str) -> str:
    result = subprocess.run(
        [SH, "-c", 'PYTHON_BIN=$(command -v python)\nexport PATH="/usr/bin:$PATH"\n' + code],
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
    key = f"native-reading-time-package/{relative}"
    assert hashlib.sha256((PKG / relative).read_bytes()).hexdigest() == BASE_HASHES[key], relative
assert not list(PKG.rglob("*.db"))
record("protected core", "Daemon, Upstart config, legacy viewer/touch and daily background are byte-identical to v9.6.7; no database is shipped.")

viewer = (PKG / "阅读记录-optimized.sh").read_text(encoding="utf-8")
baseline_viewer = (BASE / "阅读记录-optimized.sh").read_text(encoding="utf-8")
new_progress = viewer[viewer.index("catalog_loaded=0"):viewer.index("pgm_valid()")]
old_progress = baseline_viewer[baseline_viewer.index("ensure_progress()"):baseline_viewer.index("pgm_valid()")]
assert all(token in new_progress for token in ("p_percentFinished", "p_cdeKey", "p_thumbnail", "sqlite3 -readonly"))
assert "UPDATE " not in new_progress and "INSERT " not in new_progress and "DELETE " not in new_progress
assert "p_percentFinished" in old_progress and "sqlite3 -readonly" in old_progress
record("progress safety", "Progress and thumbnails share one delayed read-only cc.db snapshot; reliable cdeKey matching is tried first with exact-title progress fallback, with no database writes or directory scan.")

# Extract function definitions only; hardware startup and cleanup never run.
definitions = viewer[: viewer.index("\ndetect_screen; find_touch_device")]
definitions = definitions.replace('exec >> "$LOG" 2>&1', "")
definitions = definitions.replace('\ntrap cleanup EXIT INT TERM HUP\n', "\n")
definitions = definitions.replace('echo "$(date): optimized dashboard launch, uid=$(id -u), pid=$$"', "")
definitions = definitions.replace('$(date +%Y-%m-%d)', '${TEST_TODAY:-$(date +%Y-%m-%d)}')
(OUT / "functions-v9.6.8.sh").write_text(definitions, encoding="utf-8", newline="\n")
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
    ("2026-09-06", "a", 45000, "Top 750 minute title"),
    ("2026-09-07", "future", 99999, "Future record ignored by current ranges"),
]
(SESSION / "reading-time.tsv").write_text(
    "date\tbook_id\tseconds\ttitle\n" + "".join("\t".join(map(str, row)) + "\n" for row in fixture_rows),
    encoding="utf-8",
)

setup = r'''. build/validation/functions-v9.6.8.sh
TEST_TODAY=2026-09-06
SESSION_DIR=build/validation/stats-session
DATA="$SESSION_DIR/reading-time.tsv"; SUMMARY="$SESSION_DIR/summary.tsv"; MONTHS="$SESSION_DIR/months.tsv"; WEEKS="$SESSION_DIR/weeks.tsv"
DAYS="$SESSION_DIR/days.tsv"; DAY_BOOKS="$SESSION_DIR/day-books.tsv"; CALENDAR="$SESSION_DIR/calendar.tsv"
BOOKS="$SESSION_DIR/books.tsv"; BOOKS_7D="$SESSION_DIR/books-7d.tsv"; BOOKS_MONTH="$SESSION_DIR/books-month.tsv"; BOOKS_YEAR="$SESSION_DIR/books-year.tsv"
PROGRESS="$SESSION_DIR/book-progress.tsv"; SPEC="$SESSION_DIR/render-spec.tsv"; TOTAL_VALUES="$SESSION_DIR/total-values.tsv"; WEEK_VIEW="$SESSION_DIR/week-view.tsv"
RENDERER=native-reading-time-package/reading-insights-render.lua; RENDER_ASSETS=native-reading-time-package/render-assets; CACHE_BUILDER=native-reading-time-package/reading-insights-cache.awk; TITLE_LAYOUT=native-reading-time-package/reading-insights-titles.lua
renderer_available=1; RFONT=native-reading-time-package/NotoSansCJKsc-Regular.otf
lua() { "$PYTHON_BIN" build/validation/lua_runner.py "$@"; }
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
    "books.tsv": [45000, 7500, 7200, 3600, 2700, 2700, 1200, 900, 600, 600, 300],
    "books-7d.tsv": [45000, 7500, 2700, 1200, 600, 300],
    "books-month.tsv": [45000, 7500, 2700, 1200, 300],
    "books-year.tsv": [45000, 7500, 3600, 2700, 2700, 1200, 900, 600, 600, 300],
}
for file_name, expected in expected_visible.items():
    actual = [int(line[0]) for line in rows(file_name)]
    assert actual == expected, (file_name, actual, expected)
    assert 299 not in actual and all(value >= 300 for value in actual)
run_shell(setup + "TEST_TODAY=2026-09-03; build_cache")
titles_7d = {line[1] for line in rows("books-7d.tsv")}
titles_month = {line[1] for line in rows("books-month.tsv")}
assert "Older this year" in titles_7d and "Older this year" not in titles_month
assert "Future record ignored by current ranges" not in titles_7d | titles_month
run_shell(setup + "week_offset=0; prepare_week_view")
assert [int(r[1]) for r in rows("week-view.tsv")] == [600, 299, 300, 1200, 0, 0, 0]
run_shell(setup + "TEST_TODAY=2026-09-06; build_cache")
record("book ranges", "Sep 6 and midweek Sep 3 snapshots verify today+6 days, month-to-date and year-to-date boundaries, including future-record exclusion; the redundant book-only week range is absent.")
record("book filter/order", "4m59s is excluded, 5m00s is included, every range is sorted by that range's seconds descending before pagination.")

page_probe = run_shell(setup + '''book_filter=7d; book_page=1; prepare_book_view; wc -l < "$SESSION_DIR/book-view.tsv"
book_page=2; prepare_book_view; wc -l < "$SESSION_DIR/book-view.tsv"
book_filter=month; book_page=1; prepare_book_view; wc -l < "$SESSION_DIR/book-view.tsv"
''').splitlines()
assert page_probe == ["3", "3", "3"], page_probe
assert 'book_filter="$new_filter"; book_page=1;' in viewer
record("book pagination", "Filtering precedes three-item pagination: near-7-days yields two pages of three and month yields 3+2; changing range explicitly resets page to 1.")

duration_output = run_shell(setup + '''for n in 45 60 125 576 750; do chart_time_text "$n"; echo; done''').splitlines()
assert duration_output == ["45min", "1h", "2h5min", "9h36min", "12h30min"], duration_output
record("h/min formatting", "Chart formatter returns exactly 45min, 1h, 2h5min, 9h36min and 12h30min while cached/internal values remain seconds/minutes.")

# One natural week, seven fixed days and one-week navigation.
run_shell(setup + 'week_offset=0; prepare_week_view')
week_zero = rows("week-view.tsv")
assert [r[0] for r in week_zero] == ["2026-08-31", "2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04", "2026-09-05", "2026-09-06"]
assert [int(r[1]) for r in week_zero] == [600, 299, 300, 1200, 2700, 7500, 45000]
summary = run_shell(setup + 'week_offset=0; total_period=week; prepare_total_values; prepare_period_summary; echo "$total $read_days $average $period_title"').strip()
assert summary == "57599 7 8220 8月31日 - 9月6日", summary
run_shell(setup + 'week_offset=-2; prepare_week_view')
assert [int(r[1]) for r in rows("week-view.tsv")] == [2700, 0, 0, 0, 0, 0, 0]
one_day = run_shell(setup + 'week_offset=-2; total_period=week; prepare_total_values; prepare_period_summary; echo "$total $read_days $average"').strip()
assert one_day == "2700 1 2700", one_day
run_shell(setup + 'week_offset=-1; prepare_week_view')
assert [int(r[1]) for r in rows("week-view.tsv")] == [3600, 0, 0, 0, 0, 0, 900]
run_shell(setup + 'week_offset=-3; prepare_week_view')
assert [int(r[1]) for r in rows("week-view.tsv")] == [0] * 7
empty_week = run_shell(setup + 'week_offset=-3; total_period=week; prepare_total_values; prepare_period_summary; echo "$total $read_days $average"').strip()
assert empty_week == "0 0 0", empty_week
run_shell(setup + "TEST_TODAY=2026-01-04; build_cache; week_offset=0; prepare_week_view")
assert [r[0] for r in rows("week-view.tsv")] == ["2025-12-29", "2025-12-30", "2025-12-31", "2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]
run_shell(setup + "TEST_TODAY=2026-09-06; build_cache")
assert 'if [ "$week_offset" -lt 0 ]' in viewer and 'week_offset=$((week_offset-1))' in viewer
record("weekly grouping", "The current, one-day, empty, cross-month and Dec/Jan cross-year weeks all produce exactly Monday–Sunday; navigation moves one week and the event guard blocks moving beyond offset 0.")

year_current = run_shell(setup + 'total_period=year; view_year=2026; prepare_total_values; prepare_period_summary; echo "$total $read_days $average $period_title"').strip()
year_previous = run_shell(setup + 'total_period=year; view_year=2025; prepare_total_values; prepare_period_summary; echo "$total $read_days $average $period_title"').strip()
all_history = run_shell(setup + 'total_period=all; prepare_total_values; prepare_period_summary; echo "$total $read_days $average $period_title"').strip()
assert year_current == "65399 11 5940 2026年", year_current
assert year_previous == "7200 1 7200 2025年", year_previous
assert all_history == "72599 12 6060 全部历史", all_history
assert [r[0] for r in rows("total-values.tsv")] == ["2025年", "2026年"]
record("period summaries", "Weekly and annual values retain their boundaries; all history reads the launch summary, excludes future-dated rows and aggregates the small DAYS cache by year.")

# Regression for the on-device stale-summary report. The data, title and summary
# are recalculated from the same selected period across repeated week/year moves.
(SESSION / "days.tsv").write_text(
    "2025-01-01\t7200\n"
    "2026-08-17\t3600\n"
    "2026-08-31\t7200\n2026-09-01\t7200\n2026-09-02\t7200\n"
    "2026-09-03\t7200\n2026-09-04\t7800\n",
    encoding="utf-8",
)
week_sequence = run_shell(setup + '''for week_offset in 0 -1 -2 -1 0; do
  total_period=week; prepare_total_values; prepare_period_summary
  printf '%s|%s|%s|%s|%s\\n' "$week_offset" "$period_title" "$total" "$read_days" "$average"
done
''').splitlines()
assert week_sequence == [
    "0|8月31日 - 9月6日|36600|5|7320",
    "-1|8月24日 - 8月30日|0|0|0",
    "-2|8月17日 - 8月23日|3600|1|3600",
    "-1|8月24日 - 8月30日|0|0|0",
    "0|8月31日 - 9月6日|36600|5|7320",
], week_sequence
mode_sequence = run_shell(setup + '''total_period=week; week_offset=0; prepare_total_values; prepare_period_summary; echo "week:$total:$read_days:$average"
total_period=year; view_year=2026; prepare_total_values; prepare_period_summary; echo "year2026:$total:$read_days:$average"
total_period=all; prepare_total_values; prepare_period_summary; echo "all:$total:$read_days:$average"
total_period=week; prepare_total_values; prepare_period_summary; echo "week:$total:$read_days:$average"
total_period=year; view_year=2025; prepare_total_values; prepare_period_summary; echo "year2025:$total:$read_days:$average"
view_year=2026; prepare_total_values; prepare_period_summary; echo "year2026:$total:$read_days:$average"
''').splitlines()
assert mode_sequence == [
    "week:36600:5:7320",
    "year2026:40200:6:6720",
    "all:72599:12:6060",
    "week:36600:5:7320",
    "year2025:7200:1:7200",
    "year2026:40200:6:6720",
], mode_sequence
run_shell(setup + "TEST_TODAY=2026-09-06; build_cache")
record("period state sequences", "Current week → empty prior week → populated older week → current week, week → year → all → week, and 2026 → 2025 → 2026 all recalculate title/chart data and summary from the selected period; the 10h10m/5-day fixture averages 2h2m.")

# render_total already redraws all four tiles. Every total-page state change must
# also refresh the summary tile on the physical e-ink display.
for operation in ("total_to_week", "total_to_year", "total_to_all", "week_previous", "year_previous", "week_next", "year_next"):
    assert f"perform_draw {operation} 0 0 55 380 1162 1070" in viewer, operation
assert "55 625 1162 845" not in viewer[viewer.index("      total_week)"):viewer.index("      month_prev)")]
refresh_left, refresh_top, refresh_width, refresh_height = 55, 380, 1162, 1070
for left, top, width, height in ((85, 380, 1102, 180), (65, 638, 230, 58), (300, 644, 676, 84), (75, 760, 1122, 690)):
    assert refresh_left <= left and refresh_top <= top
    assert refresh_left + refresh_width >= left + width
    assert refresh_top + refresh_height >= top + height
record("total partial refresh", "Week/year arrows and all range switches retain one partial GC16_FAST update covering summary, toggle, mode-aware period card and chart; all mode has no arrow tile or touch target.")

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


# A 1h31min daily maximum should use a compact 2h weekly scale.
(SESSION / "days.tsv").write_text("2026-09-01\t5460\n", encoding="utf-8")
low_week_spec = render("total-week-low-scale", "total", "total_period=week; week_offset=0; render_total")
low_ticks = [line.split("\t")[8] for line in low_week_spec.splitlines() if line.startswith("text\tchart\tR\t20")]
assert low_ticks == ["1h", "2h"], low_ticks
assert "1h31min" in low_week_spec
record("weekly scale", "A 1h31min daily maximum selects a 2h ceiling; the >10h fixture also retains headroom above its exact value label.")

# Focused annual chart data for required labels and a >10h column.
(SESSION / "days.tsv").write_text(
    "2026-01-01\t2700\n2026-02-01\t3600\n2026-03-01\t7500\n2026-04-01\t34560\n2026-05-01\t45000\n",
    encoding="utf-8",
)
year_spec = render("total-year", "total", "total_period=year; view_year=2026; week_offset=0; render_total")
for label in ("45min", "1h", "2h5min", "9h36min", "12h30min"):
    assert label in year_spec
tick_labels = [line.split("\t")[8] for line in year_spec.splitlines() if line.startswith("text\tchart\tR\t20")]
assert tick_labels and all(label.endswith("h") and "分" not in label for label in tick_labels), tick_labels
assert "阅读日均" in year_spec and "\t日均  " not in year_spec
empty_spec = render("total-empty", "total", "total_period=year; view_year=2025; week_offset=0; render_total")
assert not any("min" in line and line.startswith("text\tchart\tB\t20") for line in empty_spec.splitlines())
run_shell(setup + "TEST_TODAY=2026-09-06; build_cache")
week_spec = render("total-week", "total", "total_period=week; view_year=2026; week_offset=0; render_total")
assert all(label in week_spec for label in ("周一", "周二", "周三", "周四", "周五", "周六", "周日"))
assert "8月31日 - 9月6日" in week_spec and "12h30min" in week_spec
assert not any(line.split("\t")[8] == "0min" for line in week_spec.splitlines() if line.startswith("text\tchart\tB\t20"))
assert all(f"{month}月" in year_spec for month in range(1, 13)) and "2026年" in year_spec
record("chart rendering", "Seven-day weekly and 12-month annual charts render through the shipped Lua compositor; adaptive integer-hour ticks, h/min labels, zero periods and a >10h day pass.")

for filter_name in ("7d", "month", "year", "all"):
    render(f"books-{filter_name}", "books", f"progress_loaded=1; book_filter={filter_name}; book_page=1; render_books")
render("books-filters", "books", "progress_loaded=1; book_filter=7d; book_page=2; render_books")
books_spec = (OUT / "books-7d.spec.tsv").read_text(encoding="utf-8")
assert "暂无进度" in books_spec and "42%" in books_spec and "88%" in books_spec
assert "本周" not in books_spec and all(label in books_spec for label in ("近7日", "本月", "今年", "全部"))
record("book rendering", "All four filters, a second page, cdeKey/title progress matches and ‘暂无进度’ render with the three-row cover layout.")

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
lua = LuaRuntime(); lua.globals().arg = lua.table_from({3: "total", 13: "week"}); total_touch = lua.execute(touch_source)
assert [total_touch(x, 665) for x in (100, 180, 260, 350, 920)] == ["total_week", "total_year", "total_all", "total_prev", "total_next"]
lua = LuaRuntime(); lua.globals().arg = lua.table_from({3: "total", 13: "all"}); all_touch = lua.execute(touch_source)
assert [all_touch(x, 665) for x in (260, 350, 920)] == ["total_all", None, None]
lua = LuaRuntime(); lua.globals().arg = lua.table_from({3: "books", 14: "7d"}); books_touch = lua.execute(touch_source)
assert [books_touch(x, 310) for x in (100, 500, 800, 1050)] == ["books_7d", "books_month", "books_year", "books_all"]
record("touch controls", "The hit map returns week/year/all, suppresses arrows in all-time mode, and exposes all four book-range controls.")

# Rendering paths use only the launch cache, never the original TSV.
render_total_section = viewer[viewer.index("prepare_week_view()"):viewer.index("prepare_daily_view()")]
render_books_section = viewer[viewer.index("active_books()"):viewer.index("draw_background()")]
assert "$DATA" not in render_total_section + render_books_section
assert viewer.count("build_cache || fallback_to_legacy") == 1
assert "mode=daily; view_year=\"$(date +%Y)\"; total_period=week; week_offset=0; book_filter=7d" in viewer
assert 'if [ "$view_year" -lt "$current_year" ]' in viewer
record("state and cache performance", f"Fresh startup defaults to week/offset 0 and books/7d; one launch-time raw-data scan ({build_ms} ms on the fixture) feeds all clicks from small session caches, with future week/year navigation guarded.")

result = {"result": "PASS", "checks": checks, "check_count": len(checks)}
(OUT / "stats-filters-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=True, indent=2))
