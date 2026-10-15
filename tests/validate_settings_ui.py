"""Real evdev hitboxes/actions and FBInk argv; Pillow previews approximate OT text."""
from pathlib import Path
import os, shutil, struct, subprocess, tempfile
from lupa.lua51 import LuaRuntime, LuaError
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]; PKG=ROOT/'native-reading-time-package'
OUT=ROOT/'build/validation'; OUT.mkdir(parents=True,exist_ok=True)
SH=shutil.which('sh') or 'C:/Program Files/Git/usr/bin/sh.exe'
cases=[(m,(1100,90),'settings_open') for m in ('daily','books','total')]
for mode in ('settings','settings_custom'):
    cases += [(mode,p,'settings_back' if mode=='settings' else 'settings_cancel')
              for p in ((160,100),(44,34),(276,166))]
    cases += [(mode,p,'') for p in ((43,100),(277,100),(160,167),(600,100))]
cases += [('settings',p,'settings_toggle') for p in ((600,480),(1090,470),(104,410),(1168,554))]
cases += [('settings',(600,1250),'settings_custom')]
for mode,values,x0,y0,step_x,step_y,w,h in (
    ('settings',(1,2,3,4,5,10),104,888,362,138,340,116),
    ('settings_custom',('1','2','3','4','5','6','7','8','9','delete','0','save'),72,758,383,160,362,140)):
    for i,value in enumerate(values):
        x,y=x0+(i%3)*step_x,y0+(i//3)*step_y
        action=(f'settings_preset_{value}' if mode=='settings' else
                f'settings_{value}' if value in ('delete','save') else f'settings_digit_{value}')
        cases += [(mode,p,action) for p in ((x+w//2,y+h//2),(x,y),(x+w-1,y+h-1))]
        cases += [(mode,(x+w,y+h//2),'')]
        cases += [(mode,(x+w//2,y+h),'')]
cases += [('settings',p,'') for p in ((600,606),(600,820),(600,1160),(600,1480),(1168,950))]
cases += [('settings_custom',p,'') for p in ((600,520),(600,688),(600,1400),(1200,820))]
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
                lua.execute('io.write=capture; io.stderr={write=function() end}; os.exit=function(n) error("TEST_EXIT:"..n) end')
                try: lua.execute((PKG/'reading-insights-touch-ui.lua').read_text(encoding='utf-8'))
                except LuaError as e: assert f'TEST_EXIT:{0 if expected else 2}' in str(e),str(e)
                assert ''.join(outputs).strip()==expected,(legacy,size,mode,x,y,outputs)
                lua.execute('collectgarbage("collect")'); count+=1
    # Run unchanged production action/save functions, including errors and cancellation.
    code=f'export PATH="/usr/bin:/bin:$PATH"\nBASE="{root.as_posix()}"\n. "{(PKG/"reading-config.sh").as_posix()}"\n. "{(PKG/"reading-settings.sh").as_posix()}"\n'+'''
act() { action="$1"; rr_settings_action; }
rr_config_read; test "$idle_enabled $idle_minutes" = '0 3' || exit 1
mode=books; book_filter=year; book_page=3; act settings_open
act settings_preset_10; rr_config_read; test "$idle_enabled $idle_minutes" = '0 10' || exit 2
act settings_back; test "$mode $book_filter $book_page" = 'books year 3' || exit 3
act settings_open; act settings_toggle; rr_config_read; test "$idle_enabled" = 1 || exit 4
for n in 1 2 3 4 5 10; do
    act "settings_preset_$n"; rr_config_read; test "$idle_minutes" = "$n" || exit 5
done
act settings_custom; test -z "$settings_digits" || exit 6
act settings_digit_1; act settings_digit_7; act settings_cancel
test "$mode $idle_minutes" = 'settings 10' || exit 7
for n in 1 17 1440; do
    act settings_custom; settings_digits="$n"; act settings_save; rr_config_read
    test "$mode $idle_minutes" = "settings $n" || exit 8
done
for n in '' 0 01 1441; do
    act settings_custom; settings_digits="$n"; act settings_save
    test "$mode" = settings_custom && test -n "$settings_error" || exit 9
    rr_config_read; test "$idle_minutes" = 1440 || exit 10
done
settings_digits=1440; act settings_digit_5; test "$settings_digits" = 1440 || exit 11
act settings_delete; test "$settings_digits" = 144 || exit 12
settings_digits=''; act settings_delete; test -z "$settings_digits" || exit 13
rr_config_save() { return 1; }
settings_digits=17; act settings_save
test "$mode $idle_minutes $settings_error" = 'settings_custom 1440 保存失败，请重试' || exit 14
'''
    p=subprocess.run([SH],input=code,text=True,encoding='utf-8',capture_output=True)
    assert p.returncode==0,(p.returncode,p.stdout,p.stderr)

    states=[('settings',enabled,n,'','') for enabled in (0,1) for n in (1,2,3,4,5,10,17,1440)]
    states += [('settings_custom',1,3,d,'') for d in ('','1','17','1440')]
    states += [('settings_custom',1,3,'1441','请输入 1 至 1440 的整数'),('settings',1,3,'','保存失败，请重试')]
    previews=0
    for legacy in (False,True):
        viewer=(PKG/('阅读记录.sh' if legacy else '阅读记录-optimized.sh')).read_text(encoding='utf-8')
        ot=viewer[viewer.index('ot() {'):viewer.index('\n}',viewer.index('ot() {'))+2]
        for mode,enabled,minutes,digits,error in states:
            code=f'''
scale_x() {{ printf '%s' "$1"; }}
scale_y() {{ printf '%s' "$1"; }}
scale_len() {{ printf '%s' "$1"; }}
scale_right() {{ printf '%s' "$1"; }}
fb() {{ printf 'fb'; printf '\t%s' "$@"; printf '\n'; }}
RFONT="{(PKG/'NotoSansCJKsc-Regular.otf').as_posix()}"; BFONT="$RFONT"
{ot}
. "{(PKG/'reading-settings.sh').as_posix()}"
SETTINGS_ASSETS="{(PKG/'ui-calendar').as_posix()}"
mode={mode}; idle_enabled={enabled}; idle_minutes={minutes}; settings_digits='{digits}'; settings_error='{error}'
rr_settings_draw
'''
            output=subprocess.check_output([SH],input=code,text=True,encoding='utf-8')
            im=Image.open(PKG/f'ui-calendar/{mode}.png').convert('L'); d=ImageDraw.Draw(im)
            boxes=[]; sprites=[]; messages=[]
            for line in output.splitlines():
                args=line.split('\t')[1:]
                option='-g' if '-g' in args else '-t'
                params=dict(v.split('=',1) for v in args[args.index(option)+1].split(','))
                if option=='-g':
                    sprite=Image.open(params['file']); sprites.append(Path(params['file']).name)
                    x,y,w,h=[int(params[k]) for k in ('x','y','w','h')]
                    assert sprite.size==(w,h) and 0<=x<=1272-w and 0<=y<=1696-h
                    im.paste(sprite,(x,y))
                else:
                    size,y,x,right=[int(params[k]) for k in ('px','top','left','right')]
                    msg=args[-1]; messages.append(msg)
                    f=ImageFont.truetype(params['regular'],size)
                    box=d.textbbox((x,y),msg,font=f)
                    assert 0<=box[0]<box[2]<=1272-right and 0<=box[1]<box[3]<=1460,(msg,box,right)
                    for old in boxes:
                        assert min(old[2],box[2])<=max(old[0],box[0]) or min(old[3],box[3])<=max(old[1],box[1]),(old,box)
                    boxes.append(box); d.text((x,y),msg,font=f,fill=0)
            if mode=='settings':
                assert f'settings-switch-{enabled}.png' in sprites
                selected=f'settings-preset-{minutes}.png' if minutes in (1,2,3,4,5,10) else 'settings-custom-selected.png'
                assert sprites==[f'settings-switch-{enabled}.png',selected]
                assert f'当前 {minutes} 分钟' in messages
                assert ('已开启' if enabled else '已关闭') in messages
                assert (f'连续 {minutes} 分钟无触摸，计时自动暂停。' if enabled else '未启用，仍按原有方式计时。') in messages
            else:
                assert messages[0]==(digits or '请输入') and messages[1]=='分钟'
            if error:assert error in messages
            name=f'{mode}-{enabled}-{minutes}-{digits or "empty"}{"-error" if error else ""}{"-legacy" if legacy else ""}.png'
            im.save(OUT/name); previews+=1
            if mode=='settings' and enabled and minutes==3 and not error and not legacy:
                im.save(OUT/'settings-preview.png')
            if mode=='settings_custom' and digits=='17' and not error and not legacy:
                im.save(OUT/'settings_custom-preview.png')
print(f'settings UI: PASS ({count} real Lua hitboxes, 16/24 byte ABI; actions/persistence/errors; {previews} FBInk-command previews, optimized + legacy)')
