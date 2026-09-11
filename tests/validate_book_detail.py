"""Focused offline checks for the lazy, identity-safe per-book detail page."""
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
OUT = ROOT / "build/validation"
SESSION = OUT / "book-detail-session"
BASE_HASHES = json.loads((ROOT / "tests/baselines/v9.6.10/payload-sha256.json").read_text(encoding="utf-8"))
SH = shutil.which("sh") or "C:/Program Files/Git/usr/bin/sh.exe"
OUT.mkdir(parents=True, exist_ok=True)
SESSION.mkdir(exist_ok=True)


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
(OUT / "functions-book-detail.sh").write_text(definitions, encoding="utf-8", newline="\n")
(OUT / "lua_runner_book_detail.py").write_text(
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

setup = r'''. build/validation/functions-book-detail.sh
SESSION_DIR=build/validation/book-detail-session
DATA="$SESSION_DIR/reading-time.tsv"; SUMMARY="$SESSION_DIR/summary.tsv"; MONTHS="$SESSION_DIR/months.tsv"; WEEKS="$SESSION_DIR/weeks.tsv"
DAYS="$SESSION_DIR/days.tsv"; DAY_BOOKS="$SESSION_DIR/day-books.tsv"; CALENDAR="$SESSION_DIR/calendar.tsv"
BOOKS="$SESSION_DIR/books.tsv"; BOOKS_7D="$SESSION_DIR/books-7d.tsv"; BOOKS_MONTH="$SESSION_DIR/books-month.tsv"; BOOKS_YEAR="$SESSION_DIR/books-year.tsv"
PROGRESS="$SESSION_DIR/book-progress.tsv"; PROGRESS_DB="$SESSION_DIR/cc-progress-viewer.db"
BOOK_DETAIL_SUMMARY="$SESSION_DIR/book-detail-summary.tsv"; BOOK_DETAIL_DAILY="$SESSION_DIR/book-detail-daily.tsv"
BOOK_DETAIL_TITLE="$SESSION_DIR/book-detail-title.tsv"; BOOK_DETAIL_TITLE_LAYOUT="$SESSION_DIR/book-detail-title-layout.tsv"
SPEC="$SESSION_DIR/render-spec.tsv"; CACHE_BUILDER=native-reading-time-package/reading-insights-cache.awk
RENDERER=native-reading-time-package/reading-insights-render.lua; RENDER_ASSETS=native-reading-time-package/render-assets
TITLE_LAYOUT=native-reading-time-package/reading-insights-titles.lua; RFONT=native-reading-time-package/NotoSansCJKsc-Regular.otf
renderer_available=1; cache_ok=1; progress_loaded=1; today_date=2026-01-05
lua() { "$PYTHON_BIN" build/validation/lua_runner_book_detail.py "$@"; }
image() { printf 'image\t%s\t%s\t%s\t%s\t%s\n' "$@" >> "$SESSION_DIR/draw.tsv"; }
ot() { printf 'ot\t%s\t%s\t%s\t%s\t%s\t%s\n' "$@" >> "$SESSION_DIR/draw.tsv"; }
'''

checks: list[dict[str, str]] = []


def passed(name: str, detail: str) -> None:
    checks.append({"check": name, "result": "PASS", "detail": detail})


def jdn(value: date) -> int:
    return value.toordinal() + 1721425


# The launch-time cache appends identity without changing its original columns.
raw = """date\tbook_id\tseconds\ttitle
2025-12-20\tid-a\t600\t旧标题
2026-01-01\tid-a\t1200\t新标题
2026-01-02\tid-b\t1800\t旧标题
2026-01-03\tunknown\t300\t旧书
2026-01-04\tunknown\t400\t另一旧书
"""
(SESSION / "reading-time.tsv").write_text(raw, encoding="utf-8", newline="\n")
run_shell(setup + f'printf "%s\\n" "{jdn(date(2026, 1, 5))}" > "$CALENDAR"\nbuild_cache\n')
day_rows = [line.split("\t") for line in (SESSION / "day-books.tsv").read_text(encoding="utf-8").splitlines()]
assert all(len(row) == 5 for row in day_rows)
assert {tuple(row[:3]) for row in day_rows} == {
    ("2025-12-20", "600", "旧标题"),
    ("2026-01-01", "1200", "旧标题"),
    ("2026-01-02", "1800", "旧标题"),
    ("2026-01-03", "300", "旧书"),
    ("2026-01-04", "400", "另一旧书"),
}
id_a = [row for row in day_rows if row[3] == "id-a"]
id_b = [row for row in day_rows if row[3] == "id-b"]
assert len({row[4] for row in id_a}) == 1 and id_a[0][4] != id_b[0][4]
legacy = [row for row in day_rows if row[3] == "unknown"]
assert len({row[4] for row in legacy}) == 2
passed("stable cache identity", "DAY_BOOKS preserves date/seconds/title as columns 1–3 and appends id/book_no; same-ID title history shares one identity, same-title different IDs and legacy no-ID titles remain distinct.")


# One book-only pass calculates all metrics and a zero-filled 30-day calendar.
today = date(2026, 1, 5)
(SESSION / "calendar.tsv").write_text(f"{jdn(today)}\n", encoding="utf-8")
(SESSION / "day-books.tsv").write_text(
    """2025-11-01\t600\t旧标题\tid-a\t7
2025-12-07\t1200\t旧标题\tid-a\t7
2025-12-31\t1800\t新标题\tid-a\t7
2026-01-01\t3600\t新标题\tid-a\t7
2026-01-05\t300\t新标题\tid-a\t7
2026-01-05\t9999\t新标题\tid-b\t8
""",
    encoding="utf-8",
    newline="\n",
)
(SESSION / "book-progress.tsv").write_text("42\t新标题\tid-a\n", encoding="utf-8")
metrics = run_shell(setup + r'''get_book_detail 7 "新标题" id-a
printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$book_detail_total" "$book_detail_read_days" "$book_detail_first_date" "$book_detail_last_date" "$book_detail_active_average" "$book_detail_month_total" "$book_detail_7d_total" "$book_detail_30d_total" "$book_detail_progress"
''').strip()
assert metrics == "7500\t5\t2025-11-01\t2026-01-05\t1500\t3900\t5700\t6900\t42"
daily = [line.split("\t") for line in (SESSION / "book-detail-daily.tsv").read_text(encoding="utf-8").splitlines()]
assert len(daily) == 30 and daily[0][0] == "2025-12-07" and daily[-1][0] == "2026-01-05"
assert sum(int(row[1]) for row in daily) == 6900 and sum(int(row[1]) == 0 for row in daily) == 26
assert daily[24] == ["2025-12-31", "1800"] and daily[25] == ["2026-01-01", "3600"]
passed("book aggregation", "A single DAY_BOOKS scan returns correct lifetime/days/first/last/active-average/month/7-day/30-day values and exactly 30 natural days including zeros across month and year boundaries.")


# Progress lookup remains the existing cdeKey-first helper and has a safe empty state.
missing = run_shell(setup + 'get_book_detail 7 "没有进度" missing-id\nprintf "<%s>\\n" "$book_detail_progress"\n').strip()
assert missing == "<>"
progress_body = viewer[viewer.index("progress_for_book()") : viewer.index("pgm_valid()")]
assert "$3==id" in progress_body and "$2==t" in progress_body and "sqlite3" not in viewer[viewer.index("get_book_detail()") : viewer.index("weekday_text()")]
passed("progress reuse", "The existing ID-first/title-fallback progress result is reused; missing progress is empty and triggers the safe ‘暂无进度’ presentation without another SQLite path.")


# Lua maps five full rows only; shell resolves row -> current filtered page.
touch = (PKG / "reading-insights-touch-ui.lua").read_text(encoding="utf-8")
touch = touch[: touch.index('\nnote(string.format("interactive watcher started')]
touch = touch.replace('local f = assert(io.open(device, "rb"))', "local f = nil")
touch = touch.replace('local log = io.open(log_path, "a")', "local log = nil") + "\nreturn action_for_logical"
lua = LuaRuntime(); lua.globals().arg = lua.table_from({3: "books"}); hit = lua.execute(touch)
assert [hit(636, 345 + row * 217 + 100) for row in range(5)] == [f"book_row_{row}" for row in range(1, 6)]
assert hit(636, 1435) is None and hit(200, 300) == "books_7d" and hit(1100, 1520) == "page_next"
lua = LuaRuntime(); lua.globals().arg = lua.table_from({3: "book_detail"}); detail_hit = lua.execute(touch)
assert detail_hit(150, 90) == "book_detail_back" and detail_hit(600, 210) is None
passed("touch rows", "All five visible book rows have full-width distinct actions; filter/pager targets remain intact, blank space is inert, and book detail exposes only its back control.")


def books_file(name: str, prefix: str) -> None:
    (SESSION / name).write_text(
        "".join(f"{10000-i}\t{prefix} {i}\t{prefix}-id-{i}\t{100+i}\n" for i in range(1, 13)),
        encoding="utf-8",
    )


books_file("books-7d.tsv", "Seven")
books_file("books-month.tsv", "Month")
books_file("books-year.tsv", "Year")
(SESSION / "day-books.tsv").write_text("", encoding="utf-8")
(SESSION / "book-progress.tsv").unlink(missing_ok=True)
routes = run_shell(setup + r'''
perform_draw() { printf '%s:%s:%s:%s\n' "$1" "$mode" "$book_detail_title" "$book_detail_book_no"; }
for route in '7d 1 3' 'month 2 2' 'year 2 5'; do
    set -- $route; book_filter="$1"; book_page="$2"; open_book_detail "$3" || exit 1
    printf 'state:%s:%s:%s:%s\n' "$book_filter" "$book_page" "$book_detail_filter" "$book_detail_page"
done
book_filter=7d; book_page=3; open_book_detail 5; printf 'empty:%s\n' "$?"
''').splitlines()
assert routes == [
    "book_detail_open:book_detail:Seven 3:103", "state:7d:1:7d:1",
    "book_detail_open:book_detail:Month 7:107", "state:month:2:month:2",
    "book_detail_open:book_detail:Year 10:110", "state:year:2:year:2",
    "empty:2",
]
assert 'book_detail_back) book_filter="$book_detail_filter"; book_page="$book_detail_page"; mode=books; perform_draw book_detail_back' in viewer
assert "METRIC operation=$metric_name" in viewer and "perform_draw book_detail_open" in viewer and "perform_draw book_detail_back" in viewer
passed("routing and state", "Shell resolves row numbers against all three filtered book views and page offsets, ignores an empty row, opens with book_detail_open, and restores the saved filter/page with book_detail_back.")


# Render the real PGM tiles and compose a preview, including a hostile long title.
long_title = "很长的单书标题《跨年阅读记录》用于验证两行安全省略与指标区域隔离 " * 8
(SESSION / "day-books.tsv").write_text("2026-01-05\t300\t书\tid-a\t7\n", encoding="utf-8")
(SESSION / "draw.tsv").write_text("", encoding="utf-8")
run_shell(setup + f'get_book_detail 7 "{long_title}" id-a\nrender_book_detail\n')
spec = (SESSION / "render-spec.tsv").read_text(encoding="utf-8")
assert all(label in spec for label in ("累计阅读", "阅读天数", "首次阅读", "最近阅读", "活跃日均", "本月阅读", "阅读进度", "最近30天"))
title_lines = (SESSION / "book-detail-title-layout.tsv").read_text(encoding="utf-8").splitlines()
assert 1 <= len(title_lines) <= 2 and title_lines[-1].endswith("…")
page = Image.open(PKG / "ui-calendar/book_detail.png").convert("L")
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
        assert int(y) < 205 + 112
        draw.text((int(x), int(y)), text, font=font, fill=0)
page.save(OUT / "book-detail.png")
assert page.size == (1272, 1696) and (PKG / "ui-calendar/book_detail.png").stat().st_size > 0
assert sum(1 for line in spec.splitlines() if line.startswith("rect\tbook_chart") and line.endswith("\t105")) == 1
passed("render and long title", "The 1272×1696 secondary page renders all metrics and a 30-day chart through validated PGM tiles; arbitrary long Unicode titles are measured, limited to two lines, ellipsized, and kept above the metric divider.")


# Lightweight boundary, protected files, versions and install packaging hooks.
book_body = viewer[viewer.index("get_book_detail()") : viewer.index("weekday_text()")]
assert '"$DATA"' not in book_body and book_body.count('"$DAY_BOOKS"') == 1 and "sort " not in book_body
startup = viewer[viewer.index("metric_begin first_open") : viewer.index("\n\nwhile :; do")]
assert "get_book_detail" not in startup and "render_book_detail" not in startup
assert hashlib.sha256((PKG / "native-reading-time-daemon.sh").read_bytes()).hexdigest() == BASE_HASHES["native-reading-time-package/native-reading-time-daemon.sh"]
assert "reading-time.tsv" not in (PKG / "reading-insights-cache.awk").read_text(encoding="utf-8")
installer = (PKG / "Install-Native-Reading-Time-Optimized.sh").read_text(encoding="utf-8")
assert "9.7.3-测试版" in installer and "book_detail.png" in installer
assert "9.7.3-测试版" in viewer and "book_detail.png" in viewer
for lua_file in PKG.glob("*.lua"):
    LuaRuntime().execute("assert(loadstring(...))", lua_file.read_text(encoding="utf-8"))
for shell_file in [ROOT / "RUNME.sh", *PKG.glob("*.sh")]:
    subprocess.run([SH, "-n", str(shell_file)], check=True, capture_output=True)
passed("performance and release guardrails", "Book detail is absent from startup, performs one unsorted DAY_BOOKS scan and never names DATA; daemon bytes and persisted format stay protected, release/resource checks are v9.7.3, and shipped shell/Lua syntax passes.")


result = {"result": "PASS", "check_count": len(checks), "checks": checks}
(OUT / "book-detail-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=True, indent=2))
