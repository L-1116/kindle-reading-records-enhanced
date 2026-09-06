"""Deterministic UI and common-baseline glyph assets from the installed Noto font."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
import json, hashlib

ROOT=Path(__file__).resolve().parent
PKG=ROOT/'native-reading-time-package'
BASE=ROOT.parent/'v9.6.6-stats-filters'
FONT=PKG/'NotoSansCJKsc-Regular.otf'

def build():
    # Preserve the stable cards and navigation.  Only clear the two old static
    # section labels so the new dynamic secondary filters can occupy that space.
    total=Image.open(BASE/'native-reading-time-package/ui-calendar/total.png').convert('L')
    ImageDraw.Draw(total).rectangle((70,630,292,724),fill=255)
    total.save(PKG/'ui-calendar/total.png')
    books=Image.open(BASE/'native-reading-time-package/ui-calendar/books.png').convert('L')
    ImageDraw.Draw(books).rectangle((60,285,1210,342),fill=255)
    books.save(PKG/'ui-calendar/books.png')

    old=(BASE/'native-reading-time-package/render-assets/dynamic-glyphs.tsv').read_text().splitlines()[1:]
    chars={chr(int(row.split('\t')[2],16)) for row in old}
    chars.update(chr(i) for i in range(32,127))
    chars.update('周一二三四五六日月近本今年当前范围暂无满的书籍阅读日均')
    sizes=sorted({int(row.split('\t')[1]) for row in old}|{28,44})
    records=[]
    for size in sizes:
        font=ImageFont.truetype(str(FONT),size)
        ascent,descent=font.getmetrics()
        group=[]
        for style in ('R','B'):
            stroke=max(1,round(size/40)) if style=='B' else 0
            for ch in sorted(chars):
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
    out=ROOT/'validation';out.mkdir(exist_ok=True)
    (out/'font-metrics.json').write_text(json.dumps({'font_sha256':hashlib.sha256(FONT.read_bytes()).hexdigest(),'sizes':sizes,'glyphs':len(records),'baseline_policy':'One shared baseline per size; per-glyph bearings from the same Noto font. No fallback font.'},indent=2),encoding='utf-8')

if __name__=='__main__':build()
