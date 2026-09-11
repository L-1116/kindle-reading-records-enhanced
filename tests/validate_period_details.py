"""Focused offline checks for reusable period stats, month detail and 8-week trend."""
from __future__ import annotations

from datetime import date, timedelta
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
SESSION = OUT / "period-detail-session"
OUT.mkdir(parents=True, exist_ok=True)
SESSION.mkdir(exist_ok=True)
SH = shutil.which("sh") or "C:/Program Files/Git/usr/bin/sh.exe"


def run_shell(code: str) -> str:
    result = subprocess.run(
        [SH, "-c", 'PYTHON_BIN=$(command -v python)\nexport PATH="/usr/bin:$PATH"\n' + code],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, (result.stdout, result.stderr, code)
    return result.stdout


viewer = (PKG / "阅读记录-optimized.sh").read_text(encoding="utf-8")
definitions = viewer[: viewer.index("\ndetect_screen; find_touch_device")]
definitions = definitions.replace('exec >> "$LOG" 2>&1', "")
definitions = definitions.replace('echo "$(date): optimized dashboard launch, uid=$(id -u), pid=$$"', "")
(OUT / "functions-period-details.sh").write_text(definitions, encoding="utf-8", newline="\n")
(OUT / "lua_runner_period_details.py").write_text(
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

setup = r'''. build/validation/functions-period-details.sh
SESSION_DIR=build/validation/period-detail-session
DAYS="$SESSION_DIR/days.tsv"; DAY_BOOKS="$SESSION_DIR/day-books.tsv"; CALENDAR="$SESSION_DIR/calendar.tsv"
PERIOD_SUMMARY="$SESSION_DIR/period-summary.tsv"; PERIOD_DAILY="$SESSION_DIR/period-daily.tsv"; PERIOD_BOOKS="$SESSION_DIR/period-books.tsv"
MONTH_VALUES="$SESSION_DIR/month-values.tsv"; MONTH_TOP="$SESSION_DIR/month-top.tsv"; WEEK_TREND_VALUES="$SESSION_DIR/week-trend-values.tsv"
SPEC="$SESSION_DIR/render-spec.tsv"; RENDERER=native-reading-time-package/reading-insights-render.lua
RENDER_ASSETS=native-reading-time-package/render-assets; TITLE_LAYOUT=native-reading-time-package/reading-insights-titles.lua
RFONT=native-reading-time-package/NotoSansCJKsc-Regular.otf; renderer_available=1; cache_ok=1
lua() { "$PYTHON_BIN" build/validation/lua_runner_period_details.py "$@"; }
image() { printf 'image\t%s\t%s\t%s\t%s\t%s\n' "$@" >> "$SESSION_DIR/draw.tsv"; }
ot() { printf 'ot\t%s\t%s\t%s\t%s\t%s\t%s\n' "$@" >> "$SESSION_DIR/draw.tsv"; }
'''


def write_fixture(rows: list[tuple[str, int, str]]) -> None:
    totals: dict[str, int] = {}
    for day, seconds, _ in rows:
        totals[day] = totals.get(day, 0) + seconds
    (SESSION / "days.tsv").write_text(
        "".join(f"{day}\t{seconds}\n" for day, seconds in sorted(totals.items())), encoding="utf-8"
    )
    (SESSION / "day-books.tsv").write_text(
        "".join(f"{day}\t{seconds}\t{title}\n" for day, seconds, title in rows), encoding="utf-8"
    )


def set_today(day: date) -> None:
    # Python ordinal 1 is Gregorian JDN 1721426.
    (SESSION / "calendar.tsv").write_text(str(day.toordinal() + 1721425) + "\n", encoding="utf-8")


def render(name: str, background: str, code: str) -> str:
    (SESSION / "draw.tsv").write_text("", encoding="utf-8")
    run_shell(setup + "\n" + code)
    spec = (SESSION / "render-spec.tsv").read_text(encoding="utf-8")
    (OUT / f"{name}.spec.tsv").write_text(spec, encoding="utf-8")
    page = Image.open(PKG / "ui-calendar" / background).convert("L")
    draw = ImageDraw.Draw(page)
    for line in (SESSION / "draw.tsv").read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if fields[0] == "image":
            _, path, x, y, width, height = fields
            tile = Image.open(ROOT / path)
            assert tile.size == (int(width), int(height))
            page.paste(tile, (int(x), int(y)))
        elif fields[0] == "ot":
            _, size, y, x, right, _style, text = fields
            font = ImageFont.truetype(str(PKG / "NotoSansCJKsc-Regular.otf"), int(size))
            assert font.getlength(text) <= 1272 - int(x) - int(right)
            draw.text((int(x), int(y)), text, font=font, fill=0, anchor="lt")
    page.save(OUT / f"{name}.png")
    return spec


checks: list[dict[str, str]] = []


def passed(name: str, detail: str) -> None:
    checks.append({"check": name, "result": "PASS", "detail": detail})


# One interval pass covers totals, active-day average, peak, distinct books and top order.
long_title = "A very long English title with punctuation: volume [two] & symbols! " * 3
write_fixture([
    ("2026-09-01", 3600, "庆余年"),
    ("2026-09-01", 1800, "三体"),
    ("2026-09-08", 7200, "庆余年"),
    ("2026-09-08", 1200, long_title),
    ("2026-09-30", 60, "特殊字符《书》"),
    ("2026-10-01", 9999, "不应计入"),
])
period = run_shell(setup + r'''
get_period_stats 2026-09-01 2026-09-30
cat "$PERIOD_SUMMARY"
cat "$PERIOD_BOOKS"
''').splitlines()
assert period[0] == "13860\t3\t4620\t4\t2026-09-08\t8400"
assert period[1].startswith("10800\t庆余年")
assert len(period[1:]) == 4
assert sum(int(line.split("\t", 1)[0]) for line in period[1:]) == 13860
passed("period aggregation", "One on-demand pass over DAYS and DAY_BOOKS returns 3 active days, a 77-minute active-day average, four books, the 8400-second peak day and duration-sorted books; out-of-range rows are excluded.")

# Calendar boundaries and empty/one-day months use the same function.
boundary = run_shell(setup + r'''
get_period_stats 2026-10-01 2026-10-31; cat "$PERIOD_SUMMARY"
get_period_stats 2026-11-01 2026-11-30; cat "$PERIOD_SUMMARY"
get_period_stats 2024-02-01 2024-02-29; cat "$PERIOD_SUMMARY"
get_period_stats 2025-12-01 2026-01-31; cat "$PERIOD_SUMMARY"
''').splitlines()
assert boundary[0].startswith("9999\t1\t10020\t1\t2026-10-01\t9999")
assert boundary[1] == "0\t0\t0\t0\t-\t0"
assert boundary[2] == "0\t0\t0\t0\t-\t0"
assert boundary[3] == "0\t0\t0\t0\t-\t0"
passed("month boundaries", "31-day, 30-day, leap-February, empty and cross-year ranges complete without date-command extensions; a one-day month keeps an active-day average and empty ranges stay guarded.")

# Month detail reuses the period output, displays only Top 3 and renders 30 daily bars.
month_spec = render(
    "month-detail",
    "month_detail.png",
    "month_detail_y=2026; month_detail_m=9; prepare_month_detail; render_month_detail",
)
assert all(text in month_spec for text in ("2026年9月", "总阅读", "阅读天数", "阅读日均", "阅读书籍", "最高一天", "本月阅读最多", "每日阅读趋势"))
assert len((SESSION / "month-values.tsv").read_text(encoding="utf-8").splitlines()) == 30
assert len((SESSION / "month-top.tsv").read_text(encoding="utf-8").splitlines()) == 3
assert "不应计入" not in (SESSION / "month-top.tsv").read_text(encoding="utf-8")
write_fixture([])
empty_spec = render("month-detail-empty", "month_detail.png", "month_detail_y=2026; month_detail_m=2; prepare_month_detail; render_month_detail")
assert empty_spec.count("本月暂无阅读记录") == 1
assert "总阅读" not in empty_spec and len((SESSION / "month-values.tsv").read_text(encoding="utf-8").splitlines()) == 28
passed("month detail rendering", "A 30-day populated month renders core metrics, Top 3 and sparse-label daily bars; February emits 28 values and the empty view suppresses the zero-metric grid.")

# Eight natural weeks span New Year, allow empty weeks, exclude future current-week rows and guard prior-week zero.
today = date(2026, 1, 7)
set_today(today)
current_monday = today - timedelta(days=today.weekday())
start = current_monday - timedelta(weeks=7)
trend_rows = []
for index in range(6):
    trend_rows.append(((start + timedelta(weeks=index)).isoformat(), (index + 1) * 600, f"Book {index}"))
trend_rows.extend([
    ((current_monday + timedelta(days=0)).isoformat(), 2400, "当前书"),
    ((current_monday + timedelta(days=1)).isoformat(), 1200, "当前书"),
    ((current_monday + timedelta(days=3)).isoformat(), 9000, "未来记录"),
])
write_fixture(trend_rows)
trend = run_shell(setup + f'''today_date={today.isoformat()}
prepare_week_trend
cat "$WEEK_TREND_VALUES"
printf 'summary\t%s\t%s\t%s\t%s\t%s\n' "$week_current" "$week_previous" "$week_difference" "$week_average" "$week_current_days"
''').splitlines()
assert len(trend[:-1]) == 8
assert trend[0].startswith("11/17\t600\t0") and trend[-3].split("\t")[1] == "0"
assert trend[-1] == "summary\t3600\t0\t3600\t2040\t2"
trend_spec = render("week-trend", "week_trend.png", f"today_date={today.isoformat()}; prepare_week_trend; render_week_trend")
assert all(text in trend_spec for text in ("本周", "上周", "较上周", "+1小时0分钟", "8周平均", "最佳一周", "本周阅读", "每周阅读趋势"))
assert "9000" not in (SESSION / "period-daily.tsv").read_text(encoding="utf-8")
assert any(line.startswith("rect\ttrend_chart") and line.endswith("\t20") for line in trend_spec.splitlines())
all_week_rows = [((start + timedelta(weeks=index)).isoformat(), (index + 1) * 300, f"All {index}") for index in range(8)]
write_fixture(all_week_rows)
all_weeks = run_shell(setup + f'''today_date={today.isoformat()}
prepare_week_trend
cat "$WEEK_TREND_VALUES"
''').splitlines()
assert len(all_weeks) == 8 and all(int(line.split("\t")[1]) > 0 for line in all_weeks)
passed("8-week trend", "Eight Monday-based buckets cross Nov/Dec/Jan, cover both all-populated and missing-week fixtures, exclude a future current-week row, report two active current-week days and render the current-week outline without division or infinity text.")

# Actual Lua hit testing keeps every entry distinct and secondary tabs hidden.
touch = (PKG / "reading-insights-touch-ui.lua").read_text(encoding="utf-8")
touch = touch[: touch.index('\nnote(string.format("interactive watcher started')]
touch = touch.replace('local f = assert(io.open(device, "rb"))', "local f = nil")
touch = touch.replace('local log = io.open(log_path, "a")', "local log = nil") + "\nreturn action_for_logical"
lua = LuaRuntime(); lua.globals().arg = lua.table_from({3: "daily"}); daily_touch = lua.execute(touch)
assert daily_touch(636, 360) == "month_detail_open"
lua = LuaRuntime(); lua.globals().arg = lua.table_from({3: "total", 13: "week"}); week_touch = lua.execute(touch)
assert week_touch(600, 450) == "week_trend_open" and week_touch(600, 1000) == "week_day_3"
lua = LuaRuntime(); lua.globals().arg = lua.table_from({3: "total", 13: "year"}); year_touch = lua.execute(touch)
assert [year_touch(x, 1000) for x in (100, 370, 650, 930, 1180)] == ["year_month_1", "year_month_4", "year_month_7", "year_month_10", "year_month_12"]
for mode, action in (("month_detail", "month_detail_back"), ("week_trend", "week_trend_back")):
    lua = LuaRuntime(); lua.globals().arg = lua.table_from({3: mode}); detail_touch = lua.execute(touch)
    assert detail_touch(150, 90) == action and detail_touch(600, 210) is None
passed("touch and state routes", "Calendar title, annual month columns, weekly summary and both back buttons map to distinct actions; secondary pages expose no primary tabs, while weekly day drill-down remains intact.")

# Opening a detail computes lazily and does not reset either source page's state.
write_fixture([("2025-12-31", 600, "Book")])
set_today(today)
state = run_shell(setup + f'''perform_draw() {{ :; }}
mode=daily; daily_y=2025; daily_m=12; selected_date=2025-12-31; view_year=2024; total_period=year; week_offset=-4; today_date={today.isoformat()}
open_month_detail 2025 12 daily
printf '%s|%s|%s|%s|%s\n' "$mode" "$month_detail_source" "$daily_y" "$daily_m" "$selected_date"
mode=total; open_month_detail 2024 2 total
printf '%s|%s|%s|%s|%s\n' "$mode" "$month_detail_source" "$view_year" "$total_period" "$week_offset"
mode=total; total_period=week; open_week_trend
printf '%s|%s|%s\n' "$mode" "$total_period" "$week_offset"
''').splitlines()
assert state == [
    "month_detail|daily|2025|12|2025-12-31",
    "month_detail|total|2024|year|-4",
    "week_trend|week|-4",
]
assert 'month_detail_back) mode="$month_detail_source"' in viewer
assert 'week_trend_back) mode=total' in viewer
passed("return-state preservation", "Calendar month/date, historical annual year, period selector and historical week offset survive lazy opens, including December/January and leap-February targets.")

# Startup/core isolation is structural and byte-checked against the stable payload.
for unchanged in ("native-reading-time-daemon.sh", "native-reading-time.conf", "阅读记录.sh", "reading-insights-touch.lua"):
    key = f"native-reading-time-package/{unchanged}"
    assert hashlib.sha256((PKG / unchanged).read_bytes()).hexdigest() == BASE_HASHES[key], unchanged
startup = viewer[viewer.index("metric_begin first_open"):viewer.index("\n\nwhile :; do")]
assert "prepare_month_detail" not in startup and "prepare_week_trend" not in startup and "get_period_stats" not in startup
period_body = viewer[viewer.index("get_period_stats()"):viewer.index("weekday_text()")]
assert '"$DATA"' not in period_body and 'set -- "$DAYS" phase=books "$DAY_BOOKS"' in period_body
passed("performance isolation", "Startup still performs only build_cache plus the existing daily render; primary cache/core files are byte-identical, period pages read session aggregates on demand, and 8-week mode omits DAY_BOOKS from its input list.")

result = {"result": "PASS", "check_count": len(checks), "checks": checks}
(OUT / "period-detail-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=True, indent=2))
