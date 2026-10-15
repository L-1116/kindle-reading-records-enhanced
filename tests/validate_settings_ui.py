"""Actual touch hitboxes in both renderers, plus an offline settings preview."""
from pathlib import Path
import os, shutil, struct, subprocess, tempfile
from lupa.lua51 import LuaRuntime, LuaError
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]; PKG=ROOT/'native-reading-time-package'
OUT=ROOT/'build/validation'; OUT.mkdir(parents=True,exist_ok=True)
SH=shutil.which('sh') or 'C:/Program Files/Git/usr/bin/sh.exe'
cases=[('daily',(1100,90),'settings_open'),('books',(1100,90),'settings_open'),
       ('total',(1100,90),'settings_open'),('settings',(150,90),'settings_back'),
       ('settings',(600,350),'settings_toggle'),('settings',(200,650),'settings_preset_1'),
       ('settings',(550,650),'settings_preset_2'),('settings',(900,650),'settings_preset_3'),
       ('settings',(200,800),'settings_preset_4'),('settings',(550,800),'settings_preset_5'),
       ('settings',(900,800),'settings_preset_10'),('settings',(600,950),'settings_custom'),
       ('settings_custom',(150,90),'settings_cancel'),('settings_custom',(200,550),'settings_digit_1'),
       ('settings_custom',(550,1060),'settings_digit_0'),('settings_custom',(200,1060),'settings_delete'),
       ('settings_custom',(900,1060),'settings_save')]
count=0
with tempfile.TemporaryDirectory(prefix='settings-') as tmp:
    root=Path(tmp)
    for legacy in (False,True):
        for size in (16,24):
            for mode,(x,y),expected in cases:
                dev=root/'input'; dev.write_bytes(b''.join(bytes(size-8)+struct.pack('<HHi',*e) for e in [(3,53,x),(3,54,y),(0,0,0)]))
                args=[dev.as_posix(),(root/'debug').as_posix(),mode,0,31,0,0,1272,1696,1,1,1576,'week','7d','direct',size,1272,1696,(root/'report').as_posix(),'unknown','unknown','unknown','unknown','legacy' if legacy else 'current']
                lua=LuaRuntime(); lua.globals().arg=lua.table_from({i+1:str(v) for i,v in enumerate(args)})
                outputs=[]; lua.globals().capture=lambda *v:outputs.append(''.join(map(str,v)))
                lua.execute('io.write=capture; os.exit=function(n) error("TEST_EXIT:"..n) end')
                try: lua.execute((PKG/'reading-insights-touch-ui.lua').read_text(encoding='utf-8'))
                except LuaError as e: assert 'TEST_EXIT:0' in str(e),str(e)
                assert ''.join(outputs).strip()==expected,(legacy,size,mode,x,y,outputs)
                lua.execute('collectgarbage("collect")'); count+=1
    for mode in ('settings','settings_custom'):
        code=f'''
. "{(PKG/'reading-settings.sh').as_posix()}"
ot() {{ printf 'text\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$6"; }}
rect() {{ printf 'rect\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4"; }}
mode={mode}; idle_enabled=0; idle_minutes=3; settings_digits=17; rr_settings_draw
'''
        output=subprocess.check_output([SH],input=code,text=True,encoding='utf-8')
        im=Image.open(PKG/f'ui-calendar/{mode}.png').convert('L'); d=ImageDraw.Draw(im)
        for line in output.splitlines():
            kind,*v=line.split('\t')
            if kind=='rect':
                y,x,w,h=map(int,v); d.rectangle((x,y,x+w-1,y+h-1),fill=136)
            else:
                size,y,x=map(int,v[:3]); d.text((x,y),v[3],font=ImageFont.truetype(str(PKG/'NotoSansCJKsc-Regular.otf'),size),fill=0)
        im.save(OUT/f'{mode}-preview.png')
print(f'settings UI: PASS ({count} actual Lua hitboxes; optimized + legacy; 16/24 byte ABI)')
