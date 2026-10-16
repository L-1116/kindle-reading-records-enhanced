"""Rebuild only the cumulative-time chart card; no device-side dependencies."""
from pathlib import Path
from PIL import Image, ImageDraw
from build_ui import draw_standard_card

ROOT = Path(__file__).resolve().parents[1]


def build():
    path = ROOT / 'native-reading-time-package/ui-calendar/total.png'
    page = Image.open(path).convert('L')
    draw = ImageDraw.Draw(page)
    # Erase the previous card and its static grid. The runtime owns all ticks.
    # Keep the approved summary, tabs, header and outer frame byte-identical.
    draw.rectangle((50, 600, 1222, 1620), fill=255)
    draw_standard_card(draw, (55, 625, 1217, 1600))
    page.save(path)


if __name__ == '__main__':
    build()
