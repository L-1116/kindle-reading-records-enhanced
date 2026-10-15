"""Build the B settings design with the project font; no device-side dependencies."""
from pathlib import Path
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / 'native-reading-time-package'
FONT = PKG / 'NotoSansCJKsc-Regular.otf'
INK, MUTED, PAPER = 16, 96, 255
PRESETS = (1, 2, 3, 4, 5, 10)


@lru_cache(None)
def font(size):
    return ImageFont.truetype(str(FONT), size)


def text(draw, x, y, value, size, color=INK, center=False):
    a, b, c, e = draw.textbbox((0, 0), value, font=font(size))
    draw.text((x - (c-a)/2 - a if center else x-a, y-(b+e)/2),
              value, font=font(size), fill=color)


def chevron(draw, x, y, direction=1):
    draw.line(((x-direction*6, y-12), (x+direction*6, y),
               (x-direction*6, y+12)), fill=INK, width=3, joint='curve')


def tick(draw, x, y, color=PAPER):
    draw.line(((x-10, y), (x-2, y+8), (x+12, y-9)),
              fill=color, width=4, joint='curve')


def page(title):
    im = Image.new('L', (1272, 1696), PAPER)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((64, 54, 256, 146), 16, outline=112, width=2)
    chevron(d, 96, 100, -1)
    text(d, 123, 100, '返回', 36)
    text(d, 636, 100, title, 52, center=True)
    d.line((64, 178, 1208, 178), fill=176, width=2)
    return im, d


def build():
    out = PKG / 'ui-calendar'
    # settings-button.png is deliberately untouched: the approved homepage gear.
    im, d = page('设置')
    text(d, 64, 264, '阅读计时', 52)
    text(d, 64, 328, '无操作时暂停累计阅读时长', 32, MUTED)
    d.rounded_rectangle((64, 386, 1208, 714), 24, outline=104, width=3)
    text(d, 104, 454, '无操作超时暂停', 44)
    text(d, 104, 659, '再次触摸后恢复，暂停时间不计入。', 32, MUTED)
    d.rounded_rectangle((64, 756, 1208, 1378), 24, outline=104, width=3)
    text(d, 104, 820, '暂停时长', 42)
    for i, n in enumerate(PRESETS):
        x, y = 104+(i % 3)*362, 888+(i // 3)*138
        d.rounded_rectangle((x, y, x+339, y+115), 16, outline=144, width=2)
        text(d, x+162, y+58, f'{n} 分钟', 44, center=True)
        selected = Image.new('L', (340, 116), PAPER)
        sd = ImageDraw.Draw(selected)
        sd.rounded_rectangle((0, 0, 339, 115), 16, fill=INK)
        text(sd, 162, 58, f'{n} 分钟', 44, PAPER, center=True)
        tick(sd, 310, 58)
        selected.save(out / f'settings-preset-{n}.png')
    d.rounded_rectangle((104, 1186, 1168, 1314), 16, outline=144, width=2)
    text(d, 140, 1250, '自定义分钟数', 40)
    chevron(d, 1125, 1250)
    text(d, 80, 1480, '设置自动保存，仅影响之后的计时。', 32, MUTED)
    text(d, 80, 1538, '关闭时，所选时长不生效。', 32, MUTED)
    im.save(out / 'settings.png')

    for enabled in (0, 1):
        switch = Image.new('L', (152, 78), PAPER)
        sd = ImageDraw.Draw(switch)
        sd.rounded_rectangle((0, 0, 151, 77), 39,
                             fill=INK if enabled else PAPER, outline=INK, width=3)
        x = 82 if enabled else 8
        sd.ellipse((x, 8, x+61, 69), fill=PAPER if enabled else INK)
        switch.save(out / f'settings-switch-{enabled}.png')
    selected = Image.new('L', (48, 48), PAPER)
    tick(ImageDraw.Draw(selected), 24, 24, INK)
    selected.save(out / 'settings-custom-selected.png')

    im, d = page('自定义时长')
    text(d, 64, 268, '暂停时长', 50)
    d.rounded_rectangle((64, 356, 1208, 642), 24, outline=104, width=3)
    text(d, 104, 410, '分钟数', 32, MUTED)
    text(d, 104, 688, '请输入 1–1440 的整数分钟', 32, MUTED)
    for i, key in enumerate(('1', '2', '3', '4', '5', '6', '7', '8', '9', '删除', '0', '保存')):
        x, y = 72+(i % 3)*383, 758+(i // 3)*160
        solid = key == '保存'
        d.rounded_rectangle((x, y, x+361, y+139), 18,
                             fill=INK if solid else PAPER,
                             outline=INK if solid else 156, width=2)
        text(d, x+181, y+70, key, 42 if key in ('删除', '保存') else 62,
             PAPER if solid else INK, center=True)
    text(d, 636, 1536, '返回将取消本次输入，保留原有设置。', 32, MUTED, center=True)
    im.save(out / 'settings_custom.png')


if __name__ == '__main__':
    build()
