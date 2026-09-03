#!/usr/bin/env python3
"""Offline smoke test for the foreground-only Lua PGM compositor."""

from __future__ import annotations

import sys
import tempfile
import shutil
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "native-reading-time-package"


def main() -> None:
    try:
        from lupa import LuaRuntime
    except ImportError as exc:
        raise SystemExit("Install lupa in a temporary environment to run this test") from exc

    # Lua runtimes on Windows may keep a recently closed handle alive until the
    # runtime is collected, so cleanup is best-effort in this developer test.
    with tempfile.TemporaryDirectory(prefix="kindle-render-test-", ignore_cleanup_errors=True) as directory:
        temp = Path(directory)
        assets = temp / "assets"
        assets.mkdir()
        shutil.copy2(PACKAGE / "render-assets" / "dynamic-glyphs.pgm", assets)
        shutil.copy2(PACKAGE / "render-assets" / "dynamic-glyphs.tsv", assets)
        output = temp / "smoke.pgm"
        spec = temp / "spec.tsv"
        spec.write_text(
            "\n".join(
                [
                    f"canvas\tsmoke\t1000\t760\t{output}",
                    "rect\tsmoke\t10\t10\t980\t2\t190",
                    "round\tsmoke\t20\t30\t110\t70\t18\t16",
                    "text\tsmoke\tB\t31\t75\t48\tcenter\t255\t31",
                    "text\tsmoke\tB\t42\t160\t35\tleft\t0\t共 12小时34分钟",
                    "text\tsmoke\tR\t24\t160\t105\tleft\t0\t暂无进度 75%",
                    "text\tsmoke\tB\t70\t20\t165\tleft\t0\t128小时5分钟",
                    "text\tsmoke\tB\t32\t20\t255\tleft\t0\t阅读天数  37天 日均  45分钟2秒",
                    "text\tsmoke\tB\t39\t20\t310\tleft\t0\t2026年9月",
                    "text\tsmoke\tR\t20\t20\t370\tleft\t0\t60分",
                    "text\tsmoke\tB\t24\t150\t370\tleft\t0\t12月",
                    "text\tsmoke\tB\t22\t260\t370\tleft\t0\t123",
                    "text\tsmoke\tB\t36\t20\t425\tleft\t0\t9月3日 阅读详情",
                    "text\tsmoke\tB\t27\t20\t485\tleft\t0\t阅读 1小时20分钟 88%",
                    "text\tsmoke\tR\t34\t20\t540\tleft\t0\t当日无阅读记录",
                    "text\tsmoke\tB\t28\t20\t600\tleft\t0\t阅读 35分钟8秒",
                    "text\tsmoke\tB\t30\t20\t655\tleft\t0\t第 2 页，共 8 页",
                    "write\tsmoke",
                    "",
                ]
            ),
            encoding="utf-8",
            newline="\n",
        )
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.globals().arg = lua.table_from(
            [str(assets), str(spec)]
        )
        lua.execute((PACKAGE / "reading-insights-render.lua").read_text(encoding="utf-8"))
        with Image.open(output) as image:
            image.load()
            assert image.mode == "L"
            assert image.size == (1000, 760)
            extrema = image.getextrema()
            assert extrema == (0, 255)
            image.save(ROOT / "tools" / "renderer-smoke-preview.png")
    print("renderer smoke test passed")


if __name__ == "__main__":
    main()
