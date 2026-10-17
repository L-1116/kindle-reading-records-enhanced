"""Build the settings hierarchy with the project font; no device dependencies."""
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
    chevron(d, 116, 100, -1)
    text(d, 143, 100, '返回', 36)
    text(d, 636, 100, title, 52, center=True)
    d.line((64, 178, 1208, 178), fill=176, width=2)
    return im, d

def button(d, box, label, size=38):
    d.rounded_rectangle(box, 18, outline=104, width=3)
    if label: text(d, (box[0]+box[2])/2, (box[1]+box[3])/2, label, size, center=True)

def covers(out):
    im,d=page('自定义缺失封面')
    for y,title,desc in ((330,'通用替代封面','无专属图片时使用'),(650,'单本书籍指定封面','从全部历史阅读书籍中选择')):
        button(d,(64,y,1208,y+250),'')
        text(d,104,y+62,title,42); text(d,104,y+126,desc,32,MUTED)
        chevron(d,1150,y+62)
    button(d,(64,954,1208,1074),'图片目录与使用说明')
    button(d,(64,1134,1208,1254),'重新扫描图片')
    text(d,80,1456,'真实封面始终优先。关闭开关后保留所有选择。',32,MUTED)
    text(d,80,1516,'图片可在各书籍及通用封面的「选择图片」中预览。',32,MUTED)
    im.save(out/'settings_cover.png')
    im,d=page('替代封面管理')
    d.rounded_rectangle((436,330,836,910),18,outline=176,width=2)
    button(d,(104,1080,1168,1210),'选择图片')
    button(d,(104,1250,1168,1380),'取消选择')
    text(d,80,1490,'真实封面优先；图片失效时自动使用下一级封面。',32,MUTED)
    im.save(out/'settings_cover_manage.png')
    for mode,title,size,step,height in (('images','选择图片',4,260,230),('books','历史书籍',6,160,140)):
        im,d=page(title)
        for row in range(size):
            y=310+row*step
            d.rounded_rectangle((80,y,1192,y+height),16,outline=160,width=2)
        button(d,(80,1400,410,1520),'上一页')
        button(d,(862,1400,1192,1520),'下一页')
        if mode=='images': button(d,(452,1400,820,1520),'重新扫描',34)
        text(d,636,1594,'轻触条目选择，返回保留原有选择。',30,MUTED,center=True)
        im.save(out/f'settings_cover_{mode}.png')
    im,d=page('图片目录与使用说明')
    for y,s,size in ((330,'用 USB 连接 Kindle，将图片复制到：',38),
                     (440,'reading-time/custom-covers/',40),
                     (550,'支持 JPG、JPEG、PNG；文件名可含中文和空格。',32),
                     (650,'推荐 2:3，例如 400×600 或 600×900。',34),
                     (750,'其他比例将等比例缩放、居中留白。',34),
                     (850,'每张不超过 8 MiB、1200 万像素、单边 8192 像素。',32),
                     (970,'返回后轻触「重新扫描图片」，或进入图片选择。',32),
                     (1070,'进入选择页扫描一次；不会在后台持续扫描。',32),
                     (1190,'未安装的历史书籍也可指定图片。',34),
                     (1290,'取消专属指定后使用通用图片，再回退至占位图。',32),
                     (1420,'关闭功能后保留图片与关联，不修改真实封面缓存。',32)):
        text(d,80,y,s,size,MUTED)
    im.save(out/'settings_cover_info.png')


def build():
    out = PKG / 'ui-calendar'
    # settings-button.png is deliberately untouched: the approved homepage gear.
    im, d = page('设置')
    for title, name, description, y in (
        ('阅读设置', '无操作暂停计时', '无触摸时暂停计时，再次触摸后恢复', 328),
        ('封面设置', '自定义缺失封面', '为缺少封面的书籍指定替代图片', 864),
    ):
        text(d, 64, y-64, title, 48)
        d.rounded_rectangle((64, y, 1208, y+362), 24, outline=104, width=3)
        text(d, 104, y+84, name, 44)
        text(d, 104, y+166, description, 32, MUTED)
        chevron(d, 932, y+84)
        d.line((980, y+32, 980, y+330), fill=192, width=2)
    text(d, 104, 1094, '仅替代缺失封面，真实封面优先', 32, MUTED)
    text(d, 104, 1148, '通用图片与单本书籍图片均可在此选择', 32, MUTED)
    text(d, 80, 1480, '轻触文字或箭头查看详情，拨片独立开关。', 32, MUTED)
    text(d, 80, 1538, '设置自动保存。', 32, MUTED)
    im.save(out / 'settings.png')

    covers(out)

    im, d = page('无操作暂停计时')
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
    im.save(out / 'settings_idle.png')

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
