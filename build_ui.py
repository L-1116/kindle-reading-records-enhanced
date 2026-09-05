"""Reproducible code-native UI assets; preserves the supplied baseline font and art."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import json

ROOT = Path(__file__).resolve().parent
PKG = ROOT / 'native-reading-time-package'
FONT = PKG / 'NotoSansCJKsc-Regular.otf'

def build():
    dest = PKG / 'ui-calendar'
    dest.mkdir(exist_ok=True)
    # Move the existing tab artwork as pixels, retaining its exact typography.
    boxes = [(54,174,407,267),(460,174,813,267),(866,174,1219,267)]
    for mode in ('daily','books','total'):
        src = Image.open(PKG / 'ui' / (mode+'.png')).convert('L')
        dst = src.copy()
        for target, old in enumerate((1,2,0)):
            dst.paste(src.crop(boxes[old]), boxes[target][:2])
        if mode == 'daily':
            d = ImageDraw.Draw(dst)
            d.rectangle((50,295,1222,1600), fill=255)
            d.rounded_rectangle((54,300,1217,1120), radius=25, outline=20, width=3)
            d.rounded_rectangle((54,1140,1217,1590), radius=25, outline=20, width=3)
            # Preserve original arrow button artwork.
            for box in ((243,318,428,409),(863,318,1048,409)):
                dst.paste(src.crop(box), box[:2])
            font = ImageFont.truetype(str(FONT), 31)
            for col, label in enumerate('一二三四五六日'):
                d.text((75+col*160+77,422),label,font=font,fill=0,anchor='mt')
        dst.save(dest / (mode+'.png'))

    # Native FBInk still draws book titles. These metrics only bound wrapping.
    f = ImageFont.truetype(str(FONT), 1000)
    widths = ','.join(str(round(f.getlength(chr(i))/1000,4)) for i in range(32,127))
    (PKG / 'reading-insights-title-widths.lua').write_text('return {'+widths+'}\n',encoding='utf-8')

if __name__ == '__main__':
    build()
