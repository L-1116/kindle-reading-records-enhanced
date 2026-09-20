"""Deterministic UI and common-baseline glyph assets from the installed Noto font."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
import json, hashlib

ROOT=Path(__file__).resolve().parents[1]
PKG=ROOT/'native-reading-time-package'
FONT=PKG/'NotoSansCJKsc-Regular.otf'
CARD_RADIUS=24
CARD_STROKE=3
CARD_INK=20

def draw_standard_card(draw, box):
    """Draw the one card outline shared by every large dashboard panel."""
    draw.rounded_rectangle(box,radius=CARD_RADIUS,outline=CARD_INK,width=CARD_STROKE)

def build():
    # The three primary backgrounds were copied byte-for-byte from v9.6.10.
    # Books is the exception: its legacy five-row panel is cleared and rebuilt
    # with the exact same card helper as the known-good secondary-page panels.
    # Dynamic book content is later composited strictly inside this outline.
    books=Image.open(PKG/'ui-calendar/books.png').convert('L')
    books_draw=ImageDraw.Draw(books)
    books_draw.rectangle((50,340,1222,1434),fill=255)
    draw_standard_card(books_draw,(55,345,1217,1430))
    books.save(PKG/'ui-calendar/books.png')

    # Secondary-page shells keep the same monochrome language and card rhythm.
    detail=Image.new('L',(1272,1696),255)
    draw=ImageDraw.Draw(detail)
    draw.rounded_rectangle((22,22,1250,1674),radius=30,outline=20,width=3)
    draw.rounded_rectangle((55,54,266,145),radius=22,outline=20,width=3)
    draw_standard_card(draw,(55,190,1217,520))
    draw_standard_card(draw,(55,560,1217,1640))
    font_back=ImageFont.truetype(str(FONT),38)
    font_title=ImageFont.truetype(str(FONT),48)
    draw.text((160,99),'返回',font=font_back,fill=0,anchor='mm',stroke_width=1,stroke_fill=0)
    draw.text((636,99),'阅读详情',font=font_title,fill=0,anchor='mm',stroke_width=1,stroke_fill=0)
    detail.save(PKG/'ui-calendar/day_detail.png')

    def secondary_page(title, first_card, second_card, filename):
        page=Image.new('L',(1272,1696),255)
        page_draw=ImageDraw.Draw(page)
        page_draw.rounded_rectangle((22,22,1250,1674),radius=30,outline=20,width=3)
        page_draw.rounded_rectangle((55,54,266,145),radius=22,outline=20,width=3)
        draw_standard_card(page_draw,first_card)
        draw_standard_card(page_draw,second_card)
        page_draw.text((160,99),'返回',font=font_back,fill=0,anchor='mm',stroke_width=1,stroke_fill=0)
        page_draw.text((636,99),title,font=font_title,fill=0,anchor='mm',stroke_width=1,stroke_fill=0)
        page.save(PKG/'ui-calendar'/filename)

    secondary_page('月份详情',(55,190,1217,670),(55,700,1217,1640),'month_detail.png')
    secondary_page('最近8周',(55,190,1217,650),(55,680,1217,1640),'week_trend.png')
    secondary_page('书籍详情',(55,190,1217,720),(55,750,1217,1640),'book_detail.png')

    old=(PKG/'render-assets/dynamic-glyphs.tsv').read_text(encoding='utf-8').splitlines()[1:]
    chars={chr(int(row.split('\t')[2],16)) for row in old}
    chars.update(chr(i) for i in range(32,127))
    # Keep the atlas small: new fixed headings are rasterized into their PNG
    # backgrounds.  Only the few new dynamic-label glyphs are added, and only
    # at the sizes where the compositor actually uses them.
    size_scoped_chars=set('上份佳势回平每趋较返高累计首次活跃进度封面点击查看未·')
    chars.difference_update(size_scoped_chars)
    extra_chars_by_size={
        22:set('首次活跃进度累计'),
        24:set('上佳平较高累计进度封面点击查看'),
        27:set('进度'),
        28:set('未·'),
        34:set('势每趋进度历'),
    }
    chars.update('周一二三四五六日月近本今年全部历史按当前范围暂无满的书籍阅读日均详情星期总时长明细记录最多›‹')
    sizes=sorted(({int(row.split('\t')[1]) for row in old}-{19,25,38})|{28,44})
    records=[]
    for size in sizes:
        font=ImageFont.truetype(str(FONT),size)
        ascent,descent=font.getmetrics()
        group=[]
        for style in ('R','B'):
            stroke=max(1,round(size/40)) if style=='B' else 0
            for ch in sorted(chars|extra_chars_by_size.get(size,set())):
                x0,y0,x1,y1=font.getbbox(ch,anchor='ls',stroke_width=stroke)
                tile=Image.new('L',(max(1,x1-x0),max(1,y1-y0)),255)
                ImageDraw.Draw(tile).text((-x0,-y0),ch,font=font,fill=0,anchor='ls',stroke_width=stroke)
                ink=ImageOps.invert(tile).getbbox()
                if ink:
                    tile=tile.crop(ink); bx=x0+ink[0]; by=y0+ink[1]
                else:
                    tile=Image.new('L',(1,1),255); bx=by=0
                group.append(dict(style=style,size=size,char=ch,tile=tile,bx=bx,by=by,
                                  advance=round(font.getlength(ch)),ink=int(bool(ink)),ascent=ascent,descent=descent))
        # One baseline for a font size, shared by both weights and ALL characters.
        baseline=-min(g['by'] for g in group if g['ink'])
        for g in group:g['baseline']=baseline
        records.extend(group)
    x=y=4; row_h=0
    for g in records:
        w,h=g['tile'].size
        if x+w+4>2048:x=4;y+=row_h+4;row_h=0
        g['x']=x;g['y']=y;x+=w+4;row_h=max(row_h,h)
    atlas=Image.new('L',(2048,y+row_h+4),255)
    lines=['style\tsize\tchar\tx\ty\twidth\theight\tadvance\tbearing_x\tbearing_y\tbaseline\tink\tascent\tdescent']
    for g in records:
        atlas.paste(g['tile'],(g['x'],g['y']))
        values=[g['style'],g['size'],f"{ord(g['char']):X}",g['x'],g['y'],*g['tile'].size,g['advance'],g['bx'],g['by'],g['baseline'],g['ink'],g['ascent'],g['descent']]
        lines.append('\t'.join(map(str,values)))
    assets=PKG/'render-assets'
    atlas.save(assets/'dynamic-glyphs.pgm')
    (assets/'dynamic-glyphs.tsv').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    out=ROOT/'build/validation';out.mkdir(parents=True,exist_ok=True)
    (out/'font-metrics.json').write_text(json.dumps({'font_sha256':hashlib.sha256(FONT.read_bytes()).hexdigest(),'sizes':sizes,'glyphs':len(records),'baseline_policy':'One shared baseline per size; per-glyph bearings from the same Noto font. No fallback font.'},indent=2),encoding='utf-8')

if __name__=='__main__':build()
