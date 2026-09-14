"""Focused offline checks for selected_date and the reusable day-detail page."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont
from lupa.lua51 import LuaRuntime


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "native-reading-time-package"
BASE_HASHES = json.loads((ROOT / "tests/baselines/v9.6.10/payload-sha256.json").read_text(encoding="utf-8"))
OUT = ROOT / "build/validation"
SESSION = OUT / "day-detail-session"
OUT.mkdir(parents=True, exist_ok=True)
SESSION.mkdir(exist_ok=True)
SH = shutil.which("sh") or "C:/Program Files/Git/usr/bin/sh.exe"


def run_shell(code: str) -> str:
    result = subprocess.run(
        [SH, "-c", 'PYTHON_BIN=$(command -v python)\nexport PATH="/usr/bin:$PATH"\n' + code],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, (result.stdout, result.stderr, code)
    return result.stdout


viewer = (PKG / "阅读记录-optimized.sh").read_text(encoding="utf-8")
definitions = viewer[: viewer.index("\ndetect_screen; find_touch_device")]
definitions = definitions.replace('exec >> "$LOG" 2>&1', "")
definitions = definitions.replace('echo "$(date): optimized dashboard launch, uid=$(id -u), pid=$$"', "")
(OUT / "functions-day-detail.sh").write_text(definitions, encoding="utf-8", newline="\n")
(OUT / "lua_runner_day_detail.py").write_text(
    """import sys
from pathlib import Path
from lupa.lua51 import LuaRuntime
lua=LuaRuntime()
lua.globals().arg=lua.table_from({i:v for i,v in enumerate(sys.argv[1:])})
lua.execute(Path(sys.argv[1]).read_text(encoding='utf-8'))
""",
    encoding="utf-8",
    newline="\n",
)

setup = r'''. build/validation/functions-day-detail.sh
SESSION_DIR=build/validation/day-detail-session
DAYS="$SESSION_DIR/days.tsv"; DAY_BOOKS="$SESSION_DIR/day-books.tsv"
DAY_DETAIL_ALL="$SESSION_DIR/day-detail-all.tsv"; DAY_DETAIL_VIEW="$SESSION_DIR/day-detail-view.tsv"
SPEC="$SESSION_DIR/render-spec.tsv"; RENDERER=native-reading-time-package/reading-insights-render.lua
RENDER_ASSETS=native-reading-time-package/render-assets; TITLE_LAYOUT=native-reading-time-package/reading-insights-titles.lua
RFONT=native-reading-time-package/NotoSansCJKsc-Regular.otf; renderer_available=1; cache_ok=1
lua() { "$PYTHON_BIN" build/validation/lua_runner_day_detail.py "$@"; }
image() { printf 'image\t%s\t%s\t%s\t%s\t%s\n' "$@" >> "$SESSION_DIR/draw.tsv"; }
ot() { printf 'ot\t%s\t%s\t%s\t%s\t%s\t%s\n' "$@" >> "$SESSION_DIR/draw.tsv"; }
'''


def write_fixture(rows: list[tuple[str, int, str]]) -> None:
    totals: dict[str, int] = {}
    for date, seconds, _ in rows:
        totals[date] = totals.get(date, 0) + seconds
    (SESSION / "days.tsv").write_text(
        "".join(f"{date}\t{seconds}\n" for date, seconds in sorted(totals.items())), encoding="utf-8"
    )
    (SESSION / "day-books.tsv").write_text(
        "".join(f"{date}\t{seconds}\t{title}\tbook-{index}\t{index}\n" for index, (date, seconds, title) in enumerate(rows, 1)), encoding="utf-8"
    )


def render(name: str, code: str) -> str:
    (SESSION / "draw.tsv").write_text("", encoding="utf-8")
    run_shell(setup + "\n" + code)
    spec = (SESSION / "render-spec.tsv").read_text(encoding="utf-8")
    (OUT / f"{name}.spec.tsv").write_text(spec, encoding="utf-8")
    image = Image.open(PKG / "ui-calendar/day_detail.png").convert("L")
    draw = ImageDraw.Draw(image)
    for line in (SESSION / "draw.tsv").read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if fields[0] == "image":
            _, path, x, y, width, height = fields
            tile = Image.open(ROOT / path)
            assert tile.size == (int(width), int(height))
            image.paste(tile, (int(x), int(y)))
        elif fields[0] == "ot":
            _, size, y, x, right, _style, text = fields
            font = ImageFont.truetype(str(PKG / "NotoSansCJKsc-Regular.otf"), int(size))
            assert font.getlength(text) <= 1272 - int(x) - int(right)
            draw.text((int(x), int(y)), text, font=font, fill=0, anchor="lt")
    image.save(OUT / f"{name}.png")
    return spec


checks = []


def passed(name: str, detail: str) -> None:
    checks.append({"check": name, "result": "PASS", "detail": detail})


# Full-date selection and exact border ownership, including an empty day.
write_fixture([
    ("2026-09-07", 3600, "庆余年"),
    ("2026-09-11", 5400, "球状闪电"),
])
calendar_probe = run_shell(
    setup
    + r'''
selected_date=2026-09-11; daily_y=2026; daily_m=9; detail_page=1
render_daily 1; cp "$SESSION_DIR/daily-calendar.pgm" "$SESSION_DIR/calendar-11.pgm"
set_selected_date 2026-09-07; render_daily 0; cp "$SESSION_DIR/daily-calendar.pgm" "$SESSION_DIR/calendar-07.pgm"
set_selected_date 2026-09-09; render_daily 0; cp "$SESSION_DIR/daily-calendar.pgm" "$SESSION_DIR/calendar-09.pgm"
set_selected_date 2026-09-12; render_daily 0; cp "$SESSION_DIR/daily-calendar.pgm" "$SESSION_DIR/calendar-12.pgm"
daily_y=2026; daily_m=9; selected_date=2026-09-11; shift_month -1; render_daily 0; cp "$SESSION_DIR/daily-calendar.pgm" "$SESSION_DIR/calendar-august.pgm"; echo "$daily_y-$daily_m:$selected_date"
shift_month 1; render_daily 0; cp "$SESSION_DIR/daily-calendar.pgm" "$SESSION_DIR/calendar-september-return.pgm"; echo "$daily_y-$daily_m:$selected_date"
'''
).splitlines()
assert calendar_probe == ["2026-8:2026-08-01", "2026-9:2026-09-01"]


def cell(year: int, month: int, day: int) -> tuple[int, int]:
    import calendar

    offset, days = calendar.monthrange(year, month)
    rows = (offset + days + 6) // 7
    height = 648 // rows
    index = offset + day - 1
    return index % 7 * 160, index // 7 * height


for filename, selected in (("calendar-11.pgm", 11), ("calendar-07.pgm", 7), ("calendar-09.pgm", 9), ("calendar-12.pgm", 12)):
    calendar_image = Image.open(SESSION / filename).convert("L")
    for day, expected_fill in ((7, 180), (11, 180), (9, 255), (12, 255)):
        x, y = cell(2026, 9, day)
        if day == selected:
            assert calendar_image.getpixel((x + 3, y + 40)) == 20
            assert calendar_image.getpixel((x + 4, y + 40)) == expected_fill
        else:
            assert calendar_image.getpixel((x + 1, y + 40)) == 20
            assert calendar_image.getpixel((x + 2, y + 40)) == expected_fill
august_image = Image.open(SESSION / "calendar-august.pgm").convert("L")
august_one = cell(2026, 8, 1); august_eleven = cell(2026, 8, 11)
assert august_image.getpixel((august_one[0] + 3, august_one[1] + 40)) == 20
assert august_image.getpixel((august_one[0] + 4, august_one[1] + 40)) == 255
assert august_image.getpixel((august_eleven[0] + 1, august_eleven[1] + 40)) == 20
assert august_image.getpixel((august_eleven[0] + 2, august_eleven[1] + 40)) == 255
return_image = Image.open(SESSION / "calendar-september-return.pgm").convert("L")
september_one = cell(2026, 9, 1); september_eleven = cell(2026, 9, 11)
assert return_image.getpixel((september_one[0] + 3, september_one[1] + 40)) == 20
assert return_image.getpixel((september_eleven[0] + 2, september_eleven[1] + 40)) == 180
passed("selected_date border", "Sep 11 → 7 → 9 → empty Sep 12 leaves exactly one 4 px border; old cells return to 2 px and heat fills do not change. August/September navigation selects each target month's day 1, never day 11 by coincidence.")

# Unified aggregation: six books, deterministic tie order, rounded ratios and two pages.
long_title = "一本很长的中文书名用于确认当天详情中的标题可以稳定换行而不覆盖右侧时长" * 2
rows = [
    ("2026-09-07", 4200, "Book A"),
    ("2026-09-07", 2520, long_title),
    ("2026-09-07", 1680, "Book C"),
    ("2026-09-07", 600, "Alpha"),
    ("2026-09-07", 600, "Beta"),
    ("2026-09-07", 60, "Book F"),
]
write_fixture(rows)
summary = run_shell(
    setup
    + r'''
get_day_detail 2026-09-07
printf '%s|%s|%s|%s|%s|%s\n' "$day_detail_date" "$day_detail_weekday" "$day_detail_total" "$day_detail_count" "$day_detail_capacity" "$day_detail_pages"
cat "$DAY_DETAIL_ALL"
'''
).splitlines()
assert summary[0] == "2026-09-07|星期一|9660|6|3|2"
detail_rows = [line.split("\t") for line in summary[1:]]
assert [int(row[0]) for row in detail_rows] == [4200, 2520, 1680, 600, 600, 60]
assert [int(row[1]) for row in detail_rows] == [43, 26, 17, 6, 6, 1]
assert [row[2] for row in detail_rows[3:5]] == ["Alpha", "Beta"]
assert all(len(row) == 5 and row[3].startswith("book-") for row in detail_rows)
spec = render("day-detail-multiple", "get_day_detail 2026-09-07; render_day_detail")
assert all(text in spec for text in ("2026年9月7日", "星期一", "2小时41分钟", "6本", "43%", "1 / 2"))
assert len((SESSION / "day-detail-view.tsv").read_text(encoding="utf-8").splitlines()) == 3
page_two = render("day-detail-page-2", "get_day_detail 2026-09-07; day_detail_page=2; render_day_detail")
assert "2 / 2" in page_two
assert len((SESSION / "day-detail-view.tsv").read_text(encoding="utf-8").splitlines()) == 3
assert len((SESSION / "day-detail-all.tsv").read_text(encoding="utf-8").splitlines()) == 6
passed("day aggregation and pagination", "One get_day_detail call returns date/weekday/9660 seconds/6 books, preserves book_id/book_no for covers, sorts seconds descending with Alpha before Beta on a tie, calculates guarded percentages, and exposes all 6 books over 3+3 rows.")

# Empty day is a valid destination and never divides by zero.
write_fixture([])
empty_spec = render("day-detail-empty", "get_day_detail 2026-09-12; render_day_detail")
assert all(text in empty_spec for text in ("2026年9月12日", "星期六", "0分钟", "0本", "当日暂无阅读记录"))
assert "%" not in "\n".join(line for line in empty_spec.splitlines() if line.startswith("text\tday_list"))
passed("empty day", "A no-record Saturday renders 0 minutes, 0 books and the explicit empty message with no ratio calculation or error.")

# Real Lua hit map: primary preview, weekly day columns, detail pager and back.
touch = (PKG / "reading-insights-touch-ui.lua").read_text(encoding="utf-8")
touch = touch[: touch.index('\nnote(string.format("interactive watcher started')]
touch = touch.replace('local f = assert(io.open(device, "rb"))', "local f = nil")
touch = touch.replace('local log = io.open(log_path, "a")', "local log = nil") + "\nreturn action_for_logical"
lua = LuaRuntime(); lua.globals().arg = lua.table_from({3: "daily", 4: 1, 5: 30}); daily_touch = lua.execute(touch)
assert daily_touch(600, 1250) == "day_detail_open"
lua = LuaRuntime(); lua.globals().arg = lua.table_from({3: "total", 13: "week"}); week_touch = lua.execute(touch)
assert [week_touch(x, 1000) for x in (180, 330, 480, 630, 780, 930, 1130)] == [f"week_day_{i}" for i in range(7)]
lua = LuaRuntime(); lua.globals().arg = lua.table_from({3: "total", 13: "year"}); year_touch = lua.execute(touch)
assert year_touch(630, 1000) == "year_month_6"
lua = LuaRuntime(); lua.globals().arg = lua.table_from({3: "day_detail", 10: 2, 11: 1, 12: 1520}); detail_touch = lua.execute(touch)
assert detail_touch(150, 90) == "day_detail_back"
assert detail_touch(800, 1540) == "day_detail_next"
assert detail_touch(600, 210) is None
passed("shared touch routes", "The quick-preview header, all seven weekly columns, detail pager and large back button resolve to shared day-detail actions; annual bars now route only to the shared month detail and hidden primary tabs remain inactive.")

# The one open function does not reset source navigation state.
write_fixture([("2026-09-07", 60, "Book")])
state = run_shell(
    setup
    + r'''
perform_draw() { :; }
mode=daily; daily_y=2026; daily_m=9; selected_date=2026-09-07; week_offset=-3
open_day_detail "$selected_date" daily
printf '%s|%s|%s|%s|%s\n' "$mode" "$day_detail_source" "$selected_date" "$daily_y" "$daily_m"
mode=total; open_day_detail 2026-08-17 total
printf '%s|%s|%s\n' "$mode" "$day_detail_source" "$week_offset"
'''
).splitlines()
assert state == ["day_detail|daily|2026-09-07|2026|9", "day_detail|total|-3"]
assert 'day_detail_back) mode="$day_detail_source"' in viewer
day_route = viewer.index("      day_*)")
assert viewer.index("day_detail_prev)") < day_route
assert viewer.index("day_detail_next)") < day_route
assert viewer.index("day_detail_back)") < day_route
assert 'week_offset=0' not in next(line for line in viewer.splitlines() if line.strip().startswith("day_detail_back)"))
passed("return state", "Opening from calendar preserves selected_date/month; opening from a historical week preserves week_offset. Back restores the recorded source mode without resetting either context.")

for unchanged in ("native-reading-time-daemon.sh", "native-reading-time.conf", "阅读记录.sh", "reading-insights-touch.lua"):
    key = f"native-reading-time-package/{unchanged}"
    assert hashlib.sha256((PKG / unchanged).read_bytes()).hexdigest() == BASE_HASHES[key], unchanged
assert "$DATA" not in viewer[viewer.index("get_day_detail()"):viewer.index("prepare_daily_view()")]
passed("data/core isolation", "Day detail reads the launch-time DAY_BOOKS identity columns for covers without touching persisted data; daemon, TSV format, fallback viewer and legacy touch reader remain byte-identical to v9.6.10.")

result = {"result": "PASS", "check_count": len(checks), "checks": checks}
(OUT / "day-detail-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=True, indent=2))
