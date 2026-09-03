#!/usr/bin/env python3
"""Generate the small glyph atlas used by the on-device PGM compositor.

The Kindle never runs this script.  It is kept with the package so the binary
atlas can be reproduced from the bundled Noto CJK font.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "native-reading-time-package" / "NotoSansCJKsc-Regular.otf"
OUT_DIR = ROOT / "native-reading-time-package" / "render-assets"

SIZES = (20, 22, 24, 27, 28, 29, 30, 31, 32, 34, 36, 39, 42, 70)
CHARS = (
    " 0123456789%.-/，"
    "总阅读时长天数日均小时分钟秒年月本详情共当无记录暂无进度第页"
)


def unique(text: str) -> list[str]:
    return list(dict.fromkeys(text))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    chars = unique(CHARS)
    padding = 4
    cells: list[tuple[str, int, int, Image.Image]] = []

    for style in ("R", "B"):
        for size in SIZES:
            font = ImageFont.truetype(str(FONT), size=size)
            stroke = max(1, size // 30) if style == "B" else 0
            for char in chars:
                if char == " ":
                    advance = max(1, round(font.getlength(char)))
                    glyph = Image.new("L", (1, max(1, size)), 255)
                else:
                    bbox = font.getbbox(char, stroke_width=stroke)
                    width = max(1, bbox[2] - bbox[0])
                    height = max(1, bbox[3] - bbox[1])
                    glyph = Image.new("L", (width, height), 255)
                    draw = ImageDraw.Draw(glyph)
                    draw.text(
                        (-bbox[0], -bbox[1]),
                        char,
                        fill=0,
                        font=font,
                        stroke_width=stroke,
                        stroke_fill=0,
                    )
                    # The compositor uses a single top coordinate just like the
                    # existing FBInk calls.  Keep a little consistent breathing
                    # room above glyphs of different shapes.
                    advance = max(1, round(font.getlength(char)))
                cells.append((style, size, advance, glyph))

    atlas_width = 1024
    x = padding
    y = padding
    row_height = 0
    placements: list[tuple[str, int, str, int, int, int, int, int]] = []
    atlas_height = padding
    for (style, size, advance, glyph), char in zip(
        cells, chars * (len(SIZES) * 2), strict=True
    ):
        if x + glyph.width + padding > atlas_width:
            x = padding
            y += row_height + padding
            row_height = 0
        placements.append(
            (style, size, char, x, y, glyph.width, glyph.height, advance)
        )
        x += glyph.width + padding
        row_height = max(row_height, glyph.height)
        atlas_height = max(atlas_height, y + glyph.height + padding)

    atlas = Image.new("L", (atlas_width, atlas_height), 255)
    for placement, (_, _, _, glyph) in zip(placements, cells, strict=True):
        atlas.paste(glyph, (placement[3], placement[4]))

    atlas.save(OUT_DIR / "dynamic-glyphs.pgm")
    with (OUT_DIR / "dynamic-glyphs.tsv").open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("style\tsize\tchar\tx\ty\twidth\theight\tadvance\n")
        for style, size, char, gx, gy, width, height, advance in placements:
            fh.write(
                f"{style}\t{size}\t{ord(char):X}\t{gx}\t{gy}\t"
                f"{width}\t{height}\t{advance}\n"
            )

    print(f"generated {atlas.width}x{atlas.height} atlas with {len(placements)} glyphs")


if __name__ == "__main__":
    main()
