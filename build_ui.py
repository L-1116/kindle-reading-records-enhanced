"""Deterministic UI and common-baseline glyph assets from the installed Noto font."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
import json, hashlib

ROOT=Path(__file__).resolve().parent
PKG=ROOT/'native-reading-time-package'
BASE=ROOT.parent/'v9.6.4-ui-calendar'
FONT=PKG/'NotoSansCJKsc-Regular.otf'

def build():
    # Only the two daily card boundaries move; tabs, buttons and headers stay exact.
    im=Image.open(BASE/'native-reading-time-package/ui-calendar/daily.png').convert('L')
    d=ImageDraw.Draw(im)
    d.rectangle((50,1098,1222,1644),fill=255)
    # Repaint the lower portion of the existing calendar, retaining its upper part.
    d.line((54,1098,54,1167),fill=20,width=3)
    d.line((1217,1098,1217,1167),fill=20,width=3)
    lower=Image.new('L',(1164,894),255)
    ImageDraw.Draw(lower).rounded_rectangle((0,0,1163,892),radius=25,outline=20,width=3)
    im.paste(lower.crop((0,798,1164,894)),(54,1098))
    d.rounded_rectangle((54,1212,1217,1640),radius=25,outline=20,width=3)
    im.save(PKG/'ui-calendar/daily.png')

    old=(BASE/'native-reading-time-package/render-assets/dynamic-glyphs.tsv').read_text().splitlines()[1:]
    chars={chr(int(row.split('\t')[2],16)) for row in old}
    chars.update(chr(i) for i in range(32,127))
    sizes=sorted({int(row.split('\t')[1]) for row in old}|{44})
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
