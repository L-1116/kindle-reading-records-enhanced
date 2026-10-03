"""Check KS glyph sizes and exercise tab_total with the real Lua renderer."""

from __future__ import annotations

import csv
from datetime import date
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
KS = ROOT / "ks-package/native-reading-time-package/阅读记录-ks.sh"
PREVIEW = ROOT / "scripts/build_ks_ui.py"
RENDERER = ROOT / "native-reading-time-package/reading-insights-render.lua"
ASSETS = ROOT / "native-reading-time-package/render-assets"
FIXTURES = ROOT / "tests/fixtures/ks-runtime"
SHELL = next(
    path for path in (shutil.which("sh"), r"C:\Program Files\Git\bin\sh.exe")
    if path and Path(path).is_file()
)


def glyphs_by_size() -> dict[tuple[str, int], set[str]]:
    glyphs: dict[tuple[str, int], set[str]] = {}
    with (ASSETS / "dynamic-glyphs.tsv").open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            glyphs.setdefault((row["style"], int(row["size"])), set()).add(chr(int(row["char"], 16)))
    assert (ASSETS / "dynamic-glyphs.pgm").is_file()
    return glyphs


def validate_static_contract(source: str, glyphs: dict[tuple[str, int], set[str]]) -> None:
    missing = []
    calls = 0
    pattern = re.compile(r'\b(?:stext|slabel|sfitlabel)\s+(?:"[^"]+"|\S+)\s+([RB])\s+(\d+|"\$[A-Za-z_]+")')
    for line_number, line in enumerate(source.splitlines(), 1):
        for match in pattern.finditer(line):
            calls += 1
            style, raw_size = match.groups()
            if raw_size.isdigit():
                sizes = {int(raw_size)}
            else:
                variable = raw_size[2:-1]
                # Account for both branches of shell assignments such as title_size.
                sizes = {int(value) for value in re.findall(rf'\b{variable}=(\d+)\b', source)}
                assert sizes, (line_number, variable)
            segment = line[match.end():].split(";", 1)[0]
            segment = re.split(r'\b(?:stext|slabel|sfitlabel)\b', segment, maxsplit=1)[0]
            literal_cjk = {char for part in re.findall(r'"([^"]*)"', segment)
                           for char in part if "\u3400" <= char <= "\u9fff"}
            for size in sizes:
                available = glyphs.get((style, size))
                if available is None:
                    missing.append(f"line {line_number}: missing size {style}{size}")
                elif literal_cjk - available:
                    missing.append(f"line {line_number}: {style}{size} missing {''.join(sorted(literal_cjk - available))}")
    assert calls >= 70, calls
    assert not missing, "\n".join(missing)

    labels = ("累计时长", "阅读天数", "阅读书籍", "本年时长", "本月时长", "本周时长")
    for label in labels:
        assert set(label) <= glyphs[("R", 24)], label
    assert set("0123456789小时分钟秒天本") <= glyphs[("B", 39)]
    book_labels = ("累计阅读", "阅读天数", "首次阅读", "最近阅读", "活跃日均", "阅读进度")
    for label in book_labels:
        assert set(label) <= glyphs[("R", 22)], label
    assert set("0123456789小时分钟秒天本暂无进度%-") <= glyphs[("B", 34)]
    assert re.search(r'stext summary R 24\b', source)
    assert re.search(r'stext summary B 39\b', source)
    assert re.search(r'stext book_summary R 22\b', source)
    assert re.search(r'stext book_summary B 34\b', source)
    assert not re.search(r'\b(?:stext|slabel|sfitlabel)\s+\S+\s+R\s+25\b', source)
    assert not re.search(r'\b(?:stext|slabel|sfitlabel)\s+\S+\s+B\s+38\b', source)
    preview = PREVIEW.read_text(encoding="utf-8")
    assert 'centered(draw, (x, y), label, 24, MID)' in preview
    assert 'centered(draw, (x, y + 78), value, 39)' in preview
    assert 'draw.text((x, y), label, font=font(22), fill=MID)' in preview
    assert 'draw.text((x, y + 48), value, font=font(34), fill=0)' in preview


def validate_old_sizes_fail() -> None:
    # Preserve an executable proof of the original renderer failure, separately
    # for the two old sizes so the first assert cannot mask the second.
    with tempfile.TemporaryDirectory(prefix="ks-old-glyphs-") as directory:
        root = Path(directory)
        assets = root / "assets"
        assets.mkdir()
        for asset in ("dynamic-glyphs.tsv", "dynamic-glyphs.pgm"):
            shutil.copy2(ASSETS / asset, assets / asset)
        for style, size in (("R", 25), ("B", 38)):
            spec = root / f"old-{style}{size}.tsv"
            spec.write_text(
                f"canvas\tpage\t80\t80\t{(root / 'page.pgm').as_posix()}\n"
                f"text\tpage\t{style}\t{size}\t5\t5\tleft\t0\t0\n"
                "write\tpage\n", encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(ROOT / "tests/ks_real_renderer_lua.py"),
                 str(RENDERER), str(assets), str(spec)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
            )
            assert result.returncode != 0
            assert f"SPEC MISSING: {style}{size} U+0030" in result.stderr, result.stderr
            assert "missing glyph: 0" in result.stderr, result.stderr
    print("Original R25 and B38 renderer asserts: reproduced")


def run_case(name: str, history: str, actions: tuple[str, ...] = ("tab_books", "tab_total", "exit")) -> None:
    # Lua 5.1's Windows file API cannot open the workspace's non-ASCII path.
    with tempfile.TemporaryDirectory(prefix=f"ks-renderer-{name}-") as directory:
        base = Path(directory) / "reading-time"
        release = base / "releases/9.7.5-ks-test1"
        for path in (base / "bin", base / "fonts", base / "tmp", release / "bin",
                     release / "render-assets", release / "ui-scribe"):
            path.mkdir(parents=True)
        for utility in ("fbink", "fbset", "lipc-get-prop", "lipc-set-prop"):
            target = base / "bin" / utility
            shutil.copy2(FIXTURES / utility, target)
            target.chmod(0o755)
        shutil.copy2(FIXTURES / "lua", base / "bin/lua-fake")
        (base / "fonts/NotoSansCJKsc-Regular.otf").write_bytes(b"")
        shutil.copy2(KS, release / "bin/reading-records-ks.sh")
        shutil.copy2(ROOT / "ks-package/native-reading-time-package/reading-insights-touch-ks.lua",
                     release / "bin/reading-insights-touch-ks.lua")
        shutil.copy2(ROOT / "ks-package/native-reading-time-package/reading-insights-touch-probe-ks.lua",
                     release / "bin/reading-insights-touch-probe-ks.lua")
        for helper in ("reading-insights-render.lua", "reading-insights-cache.awk",
                       "reading-insights-cover.lua", "reading-insights-titles.lua",
                       "reading-insights-title-widths.lua"):
            shutil.copy2(ROOT / "native-reading-time-package" / helper, release / "bin" / helper)
        for asset in ("dynamic-glyphs.tsv", "dynamic-glyphs.pgm"):
            shutil.copy2(ASSETS / asset, release / "render-assets" / asset)
        for image in (ROOT / "ks-package/native-reading-time-package/ui-scribe").glob("*.png"):
            shutil.copy2(image, release / "ui-scribe" / image.name)
        lua_command = base / "bin/lua"
        shutil.copy2(ROOT / "tests/ks_real_renderer_lua.py", lua_command)
        lua_command.chmod(0o755)
        (base / "reading_time_ks_debug.log").write_text("", encoding="utf-8")
        (base / "reading-time.tsv").write_text(history, encoding="utf-8")
        (base / "actions.txt").write_text("\n".join(actions) + "\n", encoding="utf-8")
        (base / "touch-device").write_bytes(b"")
        environment = {
            **os.environ,
            "PATH": base.joinpath("bin").as_posix() + ":/usr/bin:/bin:" + os.environ.get("PATH", ""),
            "READING_BASE": base.as_posix(),
            "READING_FBINK": base.joinpath("bin/fbink").as_posix(),
            "READING_TOUCH_DEVICE": base.joinpath("touch-device").as_posix(),
            "READING_TMPDIR": base.joinpath("tmp").as_posix(),
            "KS_SIM_ACTIONS_FILE": base.joinpath("actions.txt").as_posix(),
        }
        result = subprocess.run(
            [SHELL, (release / "bin/reading-records-ks.sh").as_posix()],
            env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
        )
        log = (base / "reading_time_ks_debug.log").read_text(encoding="utf-8", errors="replace")
        assert result.returncode == 0, (name, result.returncode, result.stdout, result.stderr, log[-6000:])
        for action in actions:
            assert f"[NAV] action={action}" in log, (name, action, log[-6000:])
        assert "[UI] draw begin mode=total" in log
        assert "[UI] draw success mode=total" in log
        assert "[UI] draw failed" not in log and "[ERROR]" not in log, (name, log[-6000:])
        assert "[EXIT] finished" in log
        assert not list((base / "tmp").glob("native-reading-dashboard-ks.*"))
        print(f"KS {name}: daily -> {' -> '.join(actions)}, real renderer: PASS")


def main() -> None:
    source = KS.read_text(encoding="utf-8")
    validate_static_contract(source, glyphs_by_size())
    validate_old_sizes_fail()
    today = date.today().isoformat()
    run_case("zero", "")
    run_case("nonzero", f"{today}\tKSBOOK1\t3600\tKS Test Book One\n"
                        f"{today}\tKSBOOK2\t600\tKS Test Book Two\n",
             ("tab_books", "book_row_1", "book_detail_back", "tab_total", "exit"))


if __name__ == "__main__":
    main()
