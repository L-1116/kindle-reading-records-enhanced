"""Build deterministic 1860x2480 Kindle Scribe UI shells and mock previews."""

from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ks-package/native-reading-time-package/ui-scribe"
PREVIEWS = ROOT / "build/ks-preview"
FONT = ROOT / "native-reading-time-package/NotoSansCJKsc-Regular.otf"
W, H = 1860, 2480
INK, MID, LIGHT, WHITE = 18, 130, 205, 255


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT), size)


def card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int = 24) -> None:
    draw.rounded_rectangle(box, radius=radius, outline=INK, width=3, fill=WHITE)


def centered(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, size: int, fill: int = 0) -> None:
    draw.text(xy, text, font=font(size), fill=fill, anchor="mm", stroke_width=1 if size >= 36 else 0)


def shell() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("L", (W, H), WHITE)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((24, 24, W - 24, H - 24), radius=32, outline=INK, width=3)
    return image, draw


def primary(active: str) -> Image.Image:
    image, draw = shell()
    card(draw, (55, 54, 310, 150), 22)
    centered(draw, (182, 102), "退出", 38)
    centered(draw, (W // 2, 102), "阅读记录", 50)
    tabs = ((55, 175, 585, 285, "daily", "每日时长"),
            (665, 175, 1195, 285, "books", "阅读书籍"),
            (1275, 175, 1805, 285, "total", "累计时长"))
    for left, top, right, bottom, key, label in tabs:
        selected = key == active
        draw.rounded_rectangle((left, top, right, bottom), radius=22,
                               outline=INK, width=3, fill=INK if selected else WHITE)
        centered(draw, ((left + right) // 2, (top + bottom) // 2), label, 38,
                 WHITE if selected else 0)
    if active == "daily":
        card(draw, (70, 330, 1790, 1785))
        card(draw, (70, 1820, 1790, 2410))
        card(draw, (220, 355, 445, 445), 20)
        card(draw, (1415, 355, 1640, 445), 20)
        centered(draw, (332, 400), "‹", 44)
        centered(draw, (1527, 400), "›", 44)
        for col, label in enumerate("一二三四五六日"):
            centered(draw, (218 + col * 237, 490), label, 30)
    elif active == "books":
        card(draw, (70, 345, 1790, 2190))
        card(draw, (105, 2240, 485, 2375), 20)
        card(draw, (1375, 2240, 1755, 2375), 20)
        centered(draw, (295, 2307), "上一页", 38)
        centered(draw, (1565, 2307), "下一页", 38)
    else:
        card(draw, (70, 345, 1790, 900))
        card(draw, (70, 935, 1790, 2410))
    return image


def secondary(title: str, first: tuple[int, int, int, int], second: tuple[int, int, int, int]) -> Image.Image:
    image, draw = shell()
    card(draw, (55, 54, 310, 150), 22)
    centered(draw, (182, 102), "返回", 38)
    centered(draw, (W // 2, 102), title, 50)
    card(draw, first)
    card(draw, second)
    return image


def preview_daily(base: Image.Image) -> Image.Image:
    image = base.copy(); draw = ImageDraw.Draw(image)
    centered(draw, (930, 400), "2026年9月", 44)
    left, top, col_w, rows, grid_h = 100, 520, 237, 5, 1120
    row_h = grid_h // rows
    values = [0, 25, 70, 135, 45, 0, 10, 190, 55, 80, 0, 20, 120, 240,
              60, 10, 0, 95, 150, 30, 0, 15, 65, 110, 210, 75, 0, 35, 160, 85]
    for index in range(35):
        row, col = divmod(index, 7); x, y = left + col * col_w, top + row * row_h
        draw.rectangle((x, y, x + col_w - 10, y + row_h - 10), outline=INK, width=2, fill=WHITE)
    for day, minutes in enumerate(values, 1):
        index = 1 + day - 1; row, col = divmod(index, 7); x, y = left + col * col_w, top + row * row_h
        gray = max(65, 245 - minutes // 2)
        draw.rectangle((x + 2, y + 2, x + col_w - 12, y + row_h - 12), fill=gray)
        centered(draw, (x + (col_w - 10) // 2, y + 42), str(day), 34, WHITE if gray < 110 else 0)
        if minutes:
            centered(draw, (x + (col_w - 10) // 2, y + row_h - 50), f"{minutes}分", 24,
                     WHITE if gray < 110 else 0)
    draw.line((120, 1680, 1740, 1680), fill=LIGHT, width=2)
    draw.text((120, 1710), "本月阅读 24 天   共 38小时20分钟", font=font(30), fill=0)
    draw.text((110, 1860), "9月28日阅读详情", font=font(34), fill=0)
    draw.line((110, 1915, 1750, 1915), fill=LIGHT, width=2)
    for i, (name, duration) in enumerate((("设计心理学", "1小时12分钟"), ("人类简史", "46分钟"), ("银河帝国", "28分钟"))):
        y = 1965 + i * 125
        draw.text((125, y), name, font=font(30), fill=0)
        draw.text((1725, y), duration, font=font(28), fill=0, anchor="ra")
    return image


def preview_books(base: Image.Image) -> Image.Image:
    image = base.copy(); draw = ImageDraw.Draw(image)
    filters = ((105, "近7日", True), (520, "本月", False), (935, "今年", False), (1350, "全部", False))
    for x, label, selected in filters:
        draw.rounded_rectangle((x, 370, x + 300, 430), radius=16, outline=INK, width=2,
                               fill=INK if selected else WHITE)
        centered(draw, (x + 150, 400), label, 28, WHITE if selected else 0)
    titles = [("置身事内",), ("设计心理学",),
              ("被讨厌的勇气：自我启发", "之父阿德勒的教导"),
              ("A Very Long English", "Book Title About Reading…"),
              ("银河帝国",), ("万历十五年",)]
    for index, lines in enumerate(titles):
        col, row = index % 2, index // 2
        left, top = 100 + col * 850, 465 + row * 545
        draw.rectangle((left, top, left + 800, top + 505), outline=INK, width=3)
        draw.rectangle((left + 24, top + 130, left + 194, top + 385), outline=INK, width=2, fill=230)
        centered(draw, (left + 109, top + 257), "封面", 27, MID)
        for line_index, line in enumerate(lines):
            draw.text((left + 222, top + 55 + line_index * 44), line, font=font(36), fill=0)
        draw.text((left + 222, top + 235), f"阅读 {index + 1}小时{12 + index * 7}分钟", font=font(27), fill=0)
        progress = 22 + index * 14
        draw.text((left + 222, top + 285), f"阅读进度  {progress}%", font=font(24), fill=0)
        draw.rectangle((left + 222, top + 345, left + 757, top + 362), fill=LIGHT)
        draw.rectangle((left + 222, top + 345, left + 222 + int(535 * progress / 100), top + 362), fill=INK)
    centered(draw, (930, 2280), "第 1 页，共 2 页", 30)
    return image


def preview_total(base: Image.Image) -> Image.Image:
    image = base.copy(); draw = ImageDraw.Draw(image)
    metrics = (("累计时长", "126小时40分钟"), ("阅读天数", "68天"), ("阅读书籍", "24本"),
               ("本年时长", "91小时12分钟"), ("本月时长", "18小时35分钟"), ("本周时长", "4小时20分钟"))
    for x in (655, 1200): draw.line((x, 410, x, 850), fill=LIGHT, width=2)
    draw.line((130, 630, 1730, 630), fill=LIGHT, width=2)
    for i, (label, value) in enumerate(metrics):
        row, col = divmod(i, 3); x, y = 383 + col * 545, 444 + row * 240
        centered(draw, (x, y), label, 24, MID)
        centered(draw, (x, y + 78), value, 39)
    for i, (label, selected) in enumerate((("本周", True), ("今年", False), ("全部", False))):
        x = 110 + i * 105
        draw.rounded_rectangle((x, 965, x + 90, 1025), radius=15, outline=INK, width=2,
                               fill=INK if selected else WHITE)
        centered(draw, (x + 45, 995), label, 24, WHITE if selected else 0)
    centered(draw, (930, 995), "9月22日 - 9月28日", 32)
    chart_left, chart_right, base_y, chart_h = 170, 1740, 2250, 1030
    for h in range(1, 5):
        y = base_y - h * chart_h // 5
        draw.line((chart_left, y, chart_right, y), fill=LIGHT, width=2)
        draw.text((145, y), f"{h}h", font=font(20), fill=0, anchor="ra")
    vals = [2.1, 3.2, 1.4, 4.0, 2.8, 3.6, 1.9]
    for i, value in enumerate(vals):
        cx = chart_left + (i * 2 + 1) * (chart_right - chart_left) // 14
        bh = int(value / 5 * chart_h)
        draw.rectangle((cx - 54, base_y - bh, cx + 54, base_y), fill=80 if i == 6 else 140)
        centered(draw, (cx, base_y + 45), "一二三四五六日"[i], 26)
    return image


def preview_book_detail(base: Image.Image) -> Image.Image:
    image = base.copy(); draw = ImageDraw.Draw(image)
    draw.rectangle((145, 390, 445, 840), outline=INK, width=2, fill=230)
    centered(draw, (295, 615), "封面", 30, MID)
    draw.text((585, 250), "置身事内：中国政府与经济发展", font=font(42), fill=0)
    draw.line((525, 360, 1715, 360), fill=LIGHT, width=2)
    draw.line((525, 360, 525, 860), fill=LIGHT, width=2)
    metrics = (("累计阅读", "12小时36分钟"), ("阅读天数", "18天"), ("首次阅读", "2026-07-11"),
               ("最近阅读", "2026-09-28"), ("活跃日均", "42分钟"), ("阅读进度", "68%"))
    for i, (label, value) in enumerate(metrics):
        row, col = divmod(i, 2); x, y = 585 + col * 575, 410 + row * 175
        draw.text((x, y), label, font=font(22), fill=MID)
        draw.text((x, y + 48), value, font=font(34), fill=0)
    draw.text((120, 1050), "每日阅读趋势", font=font(34), fill=0)
    draw.line((120, 1108, 1740, 1108), fill=LIGHT, width=2)
    values = [0, 15, 34, 8, 72, 0, 52, 90, 28, 45, 17, 0, 60, 42, 35, 85,
              50, 65, 16, 90, 27, 41, 55, 36, 72, 20, 12, 74, 68, 40]
    draw.line((200, 1550, 1660, 1550), fill=INK, width=2)
    draw.line((200, 1370, 1660, 1370), fill=LIGHT, width=2)
    for i, value in enumerate(values):
        x = 200 + (i * 2 + 1) * 1460 // 60
        if value: draw.rectangle((x - 17, 1550 - int(value * 3.4), x + 17, 1550), fill=115)
        if i + 1 in (1, 7, 14, 21, 28): centered(draw, (x, 1580), str(i + 1), 22)
    draw.line((120, 1650, 1740, 1650), fill=LIGHT, width=2)
    draw.text((120, 1675), "阅读日历", font=font(32), fill=0)
    centered(draw, (930, 1690), "2026年9月", 36)
    for col, label in enumerate("一二三四五六日"):
        centered(draw, (218 + col * 237, 1765), label, 24)
    left, top, col_w, row_h = 100, 1790, 237, 86
    for day in range(1, 31):
        index = day + 1; row, col = divmod(index, 7); x, y = left + col * col_w, top + row * row_h
        centered(draw, (x + col_w // 2, y + 18), str(day), 27)
        draw.rectangle((x + 85, y + 37, x + 153, y + 65), fill=max(70, 245 - day * 5))
    draw.line((120, 2240, 1740, 2240), fill=LIGHT, width=2)
    centered(draw, (930, 2310), "9月28日 · 阅读 1小时12分钟", 28)
    return image


def preview_week(base: Image.Image) -> Image.Image:
    image = base.copy(); draw = ImageDraw.Draw(image)
    metrics = (("本周", "4小时20分钟"), ("上周", "3小时15分钟"), ("较上周", "+1小时05分钟"),
               ("8周平均", "3小时42分钟"), ("最佳一周", "6小时18分钟"), ("本周阅读", "5天"))
    for i, (label, value) in enumerate(metrics):
        row, col = divmod(i, 3); x, y = 380 + col * 550, 300 + row * 160
        centered(draw, (x, y), label, 25, MID)
        centered(draw, (x, y + 55), value, 34)
    draw.line((120, 440, 1740, 440), fill=LIGHT, width=2)
    draw.text((120, 735), "每周阅读趋势", font=font(34), fill=0)
    draw.line((120, 805, 1740, 805), fill=LIGHT, width=2)
    values = [2.3, 4.1, 3.0, 5.7, 4.4, 3.5, 6.2, 4.3]
    left, right, baseline, chart_h = 180, 1740, 2280, 1310
    for h in (2, 4, 6):
        y = baseline - int(h / 7 * chart_h)
        draw.line((left, y, right, y), fill=LIGHT, width=2)
        draw.text((145, y), f"{h}h", font=font(20), fill=0, anchor="ra")
    for i, value in enumerate(values):
        x = left + (i * 2 + 1) * (right - left) // 16
        bar_h = int(value / 7 * chart_h)
        draw.rectangle((x - 63, baseline - bar_h, x + 63, baseline), fill=70 if i == 7 else 135)
        centered(draw, (x, 2330), f"{i + 1}周", 24)
    return image


def standard_preview(page: str) -> Image.Image:
    """Illustrative content on the unmodified Standard UI shell at 1272x1696."""
    image = Image.open(ROOT / "native-reading-time-package/ui-calendar" / f"{page}.png").convert("L")
    draw = ImageDraw.Draw(image)
    if page == "books":
        titles = ("置身事内", "设计心理学", "人类简史")
        for i, title in enumerate(titles):
            y = 382 + i * 360
            draw.rectangle((98, y, 288, y + 285), outline=INK, width=2, fill=230)
            centered(draw, (193, y + 142), "封面", 27, MID)
            draw.text((340, y + 8), title, font=font(42), fill=0)
            draw.text((330, y + 175), f"阅读 {i + 1}小时{12 + i * 7}分钟", font=font(28), fill=0)
            draw.text((1165, y + 175), f"阅读进度  {22 + i * 14}%", font=font(27), fill=0, anchor="ra")
            draw.rectangle((330, y + 235, 1160, y + 253), fill=LIGHT)
            draw.rectangle((330, y + 235, 330 + int(830 * (22 + i * 14) / 100), y + 253), fill=INK)
            if i < 2: draw.line((115, y + 335, 1157, y + 335), fill=LIGHT, width=2)
        centered(draw, (636, 1510), "第 1 页，共 2 页", 30)
    elif page == "total":
        draw.text((95, 390), "126小时40分钟", font=font(70), fill=0)
        draw.text((115, 522), "阅读天数  68天", font=font(32), fill=0)
        draw.text((720, 522), "阅读日均  1小时52分钟", font=font(32), fill=0)
        centered(draw, (636, 695), "9月22日 - 9月28日", 30)
        values = [2.1, 3.2, 1.4, 4.0, 2.8, 3.6, 1.9]
        for i, value in enumerate(values):
            x = 155 + (i * 2 + 1) * 1020 // 14
            height = int(value / 5 * 590)
            draw.rectangle((x - 38, 1390 - height, x + 38, 1390), fill=90 if i == 6 else 140)
            centered(draw, (x, 1425), "一二三四五六日"[i], 24)
    return image


def comparison(standard: Image.Image, scribe: Image.Image, label: str) -> Image.Image:
    # The comparison is a display thumbnail. Each separately saved source
    # retains its actual 1272x1696 or 1860x2480 viewport resolution.
    height = 1696
    scribe_thumb = scribe.resize((1272, height), Image.Resampling.LANCZOS)
    result = Image.new("L", (2604, height + 90), WHITE)
    result.paste(standard, (0, 90)); result.paste(scribe_thumb, (1332, 90))
    draw = ImageDraw.Draw(result)
    draw.text((20, 18), f"Standard · {label} · 1272×1696", font=font(32), fill=INK)
    draw.text((1352, 18), f"Scribe · {label} · 1860×2480 (缩略显示)", font=font(32), fill=INK)
    return result


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True); PREVIEWS.mkdir(parents=True, exist_ok=True)
    pages = {
        "daily.png": primary("daily"), "books.png": primary("books"), "total.png": primary("total"),
        "day_detail.png": secondary("阅读详情", (70, 190, 1790, 610), (70, 650, 1790, 2410)),
        "month_detail.png": secondary("月份详情", (70, 190, 1790, 710), (70, 750, 1790, 2410)),
        "week_trend.png": secondary("最近8周", (70, 190, 1790, 650), (70, 690, 1790, 2410)),
        "book_detail.png": secondary("书籍详情", (70, 190, 1790, 1005), (70, 1015, 1790, 2410)),
    }
    for name, image in pages.items(): image.save(OUT / name, optimize=True)
    previews = {
        "daily": preview_daily(pages["daily.png"]),
        "books": preview_books(pages["books.png"]),
        "total": preview_total(pages["total.png"]),
        "week": preview_week(pages["week_trend.png"]),
        "book-detail": preview_book_detail(pages["book_detail.png"]),
    }
    for name, image in previews.items():
        image.save(PREVIEWS / f"ks-{name}-preview.png", optimize=True)
    for name, label in (("books", "阅读书籍"), ("total", "累计时长")):
        original = standard_preview(name)
        original.save(PREVIEWS / f"standard-{name}-preview.png", optimize=True)
        comparison(original, previews[name], label).save(PREVIEWS / f"compare-{name}.png", optimize=True)


if __name__ == "__main__":
    build()
