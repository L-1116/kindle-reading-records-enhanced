"""Generate the small shared settings assets without changing statistics assets."""
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
PKG=ROOT/'native-reading-time-package'
FONT=PKG/'NotoSansCJKsc-Regular.otf'

def build():
    out=PKG/'ui-calendar'
    def text(draw,xy,value,size=36):
        draw.text(xy,value,font=ImageFont.truetype(str(FONT),size),fill=0,anchor='mm')
    gear=Image.new('L',(211,91),255); d=ImageDraw.Draw(gear)
    d.rounded_rectangle((1,1,209,89),22,outline=20,width=3)
    points=[]
    for i in range(64):
        a=i*math.pi/32; r=23 if i%8 in (0,1,6,7) else 18
        points.append((44+r*math.cos(a),45+r*math.sin(a)))
    d.polygon(points,fill=20); d.ellipse((35,36,53,54),fill=255)
    text(d,(132,44),'设置',34); gear.save(out/'settings-button.png')
    for custom in (False,True):
        im=Image.new('L',(1272,1696),255); d=ImageDraw.Draw(im)
        d.rounded_rectangle((22,22,1250,1674),30,outline=20,width=3)
        d.rounded_rectangle((55,54,266,145),22,outline=20,width=3)
        text(d,(160,99),'返回'); text(d,(636,99),'自定义时长' if custom else '设置',46)
        text(d,(210,230),'阅读计时',38)
        d.rounded_rectangle((55,280,1217,1510),24,outline=20,width=3)
        if not custom:
            d.rounded_rectangle((80,300,1190,425),16,outline=20,width=2)
            d.rounded_rectangle((100,900,1150,1040),16,outline=20,width=2)
        for i in range(12 if custom else 6):
            x=100+(i%3)*360; y=(500+(i//3)*170) if custom else (600+(i//3)*150)
            d.rounded_rectangle((x,y,x+330,y+(150 if custom else 110)),16,outline=20,width=2)
        im.save(out/('settings_custom.png' if custom else 'settings.png'))

if __name__=='__main__': build()
