"""Real evdev hitboxes/actions and FBInk argv; Pillow previews approximate OT text."""
from pathlib import Path
import os, shutil, struct, subprocess, tempfile, sys, io
from unittest.mock import patch
from lupa.lua51 import LuaRuntime, LuaError
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]; PKG=ROOT/'native-reading-time-package'
OUT=ROOT/'build/validation'; OUT.mkdir(parents=True,exist_ok=True)
SH=shutil.which('sh') or 'C:/Program Files/Git/usr/bin/sh.exe'
sys.path.insert(0,str(ROOT/'scripts'))
import build_settings

# Measure actual font boxes in the asset builder without rewriting shipped PNGs.
static_boxes={}; static_draws=[]
original_text=build_settings.text
def checked_text(draw,x,y,value,size,color=build_settings.INK,center=False):
    a,b,c,e=draw.textbbox((0,0),value,font=build_settings.font(size))
    px=x-(c-a)/2-a if center else x-a; py=y-(b+e)/2
    box=draw.textbbox((px,py),value,font=build_settings.font(size))
    w,h=draw._image.size
    assert 0<=box[0]<box[2]<=w and 0<=box[1]<box[3]<=h,(value,box)
    if center: assert abs((box[0]+box[2])/2-x)<=.5,(value,box,x)
    static_draws.append(draw)
    for old in static_boxes.get(id(draw),[]):
        assert min(box[2],old[2])<=max(box[0],old[0]) or min(box[3],old[3])<=max(box[1],old[1]),(old,box,value)
    static_boxes.setdefault(id(draw),[]).append(box)
    return original_text(draw,x,y,value,size,color,center)
with patch.object(build_settings,'text',checked_text),patch.object(Image.Image,'save'):
    build_settings.build()
for mode,old in (('settings_idle','settings'),('settings_custom','settings_custom')):
    previous=subprocess.check_output(['git','show',f'92cd750:native-reading-time-package/ui-calendar/{old}.png'],cwd=ROOT)
    before=Image.open(io.BytesIO(previous)).convert('L')
    after=Image.open(PKG/f'ui-calendar/{mode}.png').convert('L')
    content=(0,178,1272,1696)
    assert before.crop(content).tobytes()==after.crop(content).tobytes(),mode
for mode in ('settings','settings_idle','settings_cover','settings_custom'):
    button=Image.open(PKG/f'ui-calendar/{mode}.png').convert('L').crop((64,54,256,146))
    ink=button.point(lambda value:255 if value<64 else 0).getbbox()
    assert ink and abs(ink[0]+ink[2]-192)<=1 and abs(ink[1]+ink[3]-92)<=1,(mode,ink)
cases=[(m,(1100,90),'settings_open') for m in ('daily','books','total')]
for mode in ('settings','settings_idle','settings_cover','settings_custom'):
    cases += [(mode,p,'settings_back' if mode=='settings' else 'settings_cancel' if mode=='settings_custom' else 'settings_home')
              for p in ((160,100),(44,34),(276,166))]
    cases += [(mode,p,'') for p in ((43,100),(277,100),(160,167),(600,100))]
cases += [('settings_idle',p,'settings_toggle') for p in ((600,480),(1090,470),(104,410),(1168,554))]
cases += [('settings_idle',(600,1250),'settings_custom')]
for mode,values,x0,y0,step_x,step_y,w,h in (
    ('settings_idle',(1,2,3,4,5,10),104,888,362,138,340,116),
    ('settings_custom',('1','2','3','4','5','6','7','8','9','delete','0','save'),72,758,383,160,362,140)):
    for i,value in enumerate(values):
        x,y=x0+(i%3)*step_x,y0+(i//3)*step_y
        action=(f'settings_preset_{value}' if mode=='settings_idle' else
                f'settings_{value}' if value in ('delete','save') else f'settings_digit_{value}')
        cases += [(mode,p,action) for p in ((x+w//2,y+h//2),(x,y),(x+w-1,y+h-1))]
        cases += [(mode,(x+w,y+h//2),'')]
        cases += [(mode,(x+w//2,y+h),'')]
cases += [('settings_idle',p,'') for p in ((600,606),(600,820),(600,1160),(600,1480),(1168,950))]
cases += [('settings_custom',p,'') for p in ((600,520),(600,688),(600,1400),(1200,820))]
for top, toggle, detail in ((373,'settings_toggle','settings_idle'),(909,'settings_cover_toggle','settings_cover')):
    cases += [('settings',p,toggle) for p in ((1016,top),(1092,top+39),(1167,top+77))]
    cases += [('settings',p,detail) for p in ((104,top-13),(932,top+39),(960,top+285))]
    cases += [('settings',p,'') for p in ((961,top+39),(1000,top+39),(1015,top+39),(1168,top+39),(1092,top-1),(1092,top+78))]
cases += [('settings_cover',p,'') for p in ((600,600),(600,1100),(600,1274))]
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
    # Execute production navigation/save functions, including errors/cancellation.
    code=f'export PATH="/usr/bin:/bin:$PATH"\nBASE="{root.as_posix()}"\n. "{(PKG/"reading-config.sh").as_posix()}"\n. "{(PKG/"reading-settings.sh").as_posix()}"\n'+'''
act() { action="$1"; rr_settings_action; }
rr_config_read; test "$idle_enabled $idle_minutes" = '0 3' || exit 1
mode=books; book_filter=year; book_page=3; act settings_open
test "$mode" = settings || exit 15
act settings_idle; act settings_preset_10; rr_config_read; test "$idle_enabled $idle_minutes" = '0 10' || exit 2
act settings_home; act settings_back; test "$mode $book_filter $book_page" = 'books year 3' || exit 3
act settings_open; act settings_toggle; act settings_idle; rr_config_read; test "$idle_enabled" = 1 || exit 4
for n in 1 2 3 4 5 10; do
    act "settings_preset_$n"; rr_config_read; test "$idle_minutes" = "$n" || exit 5
done
act settings_custom; test -z "$settings_digits" || exit 6
act settings_digit_1; act settings_digit_7; act settings_cancel
test "$mode $idle_minutes" = 'settings_idle 10' || exit 7
for n in 1 17 1440; do
    act settings_custom; settings_digits="$n"; act settings_save; rr_config_read
    test "$mode $idle_minutes" = "settings_idle $n" || exit 8
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

    head=f'export PATH="/usr/bin:/bin:$PATH"\nBASE="{root.as_posix()}"\n. "{(PKG/"reading-config.sh").as_posix()}"\n. "{(PKG/"reading-settings.sh").as_posix()}"\n'
    def shell(script):
        result=subprocess.run([SH],input=head+script,text=True,encoding='utf-8',capture_output=True)
        assert result.returncode==0,(result.returncode,result.stdout,result.stderr)
        return result.stdout.strip()
    conf=root/'user.conf'
    # Exact test5 configuration, including opaque future preferences and no final LF.
    old=b'# personal settings\nidle_pause_enabled=1\nidle_pause_minutes=17\nfuture_option=keep=verbatim'
    for origin in ('total','daily','books'):
        conf.write_bytes(old)
        shell('''
act() { action="$1"; rr_settings_action; }
mode='''+origin+'''; book_filter=year; book_page=3; daily_page=2
view_year=2025; daily_y=2025; daily_m=11; selected_day=8; selected_date=2025-11-08
week_offset=-4; total_period=year; detail_page=2
rr_config_read; test "$idle_enabled $idle_minutes $custom_cover_enabled" = '1 17 0' || exit 1
act settings_open; test "$mode" = settings || exit 2
act settings_cover_toggle
test "$mode $idle_enabled $idle_minutes $custom_cover_enabled" = 'settings 1 17 1' || exit 3
act settings_cover; test "$mode" = settings_cover || exit 4
act settings_home; test "$mode" = settings || exit 5
act settings_toggle; act settings_idle
test "$mode $idle_enabled $idle_minutes" = 'settings_idle 0 17' || exit 6
act settings_toggle; act settings_custom; settings_digits=23; act settings_save
test "$mode $idle_enabled $idle_minutes $custom_cover_enabled" = 'settings_idle 1 23 1' || exit 7
act settings_home; test "$mode $idle_minutes" = 'settings 23' || exit 8
act settings_cover_toggle; act settings_back
test "$mode" = '''+origin+''' || exit 9
test "$book_filter $book_page $daily_page $view_year $daily_y $daily_m $selected_day $selected_date $week_offset $total_period $detail_page" = 'year 3 2 2025 2025 11 8 2025-11-08 -4 year 2' || exit 10
''')
        assert conf.read_bytes().startswith(b'# personal settings\nfuture_option=keep=verbatim\n')
        # A new process models reopening/restarting; both switches and minutes survive.
        assert shell('rr_config_read; echo "$idle_enabled $idle_minutes $custom_cover_enabled"')=='1 23 0'
        assert shell('rr_config_read; action=settings_cover_toggle; rr_settings_action; rr_config_read; echo "$idle_enabled $idle_minutes $custom_cover_enabled"')=='1 23 1'
        assert shell('rr_config_read; echo "$idle_enabled $idle_minutes $custom_cover_enabled"')=='1 23 1'
        saved=conf.read_bytes()
        # Failed saves restore both visible switches from the stored configuration.
        shell('''rr_config_read
rr_config_save() { return 1; }
action=settings_cover_toggle; rr_settings_action
test "$custom_cover_enabled $settings_error" = '1 保存失败，请重试' || exit 1
action=settings_toggle; rr_settings_action
test "$idle_enabled $settings_error" = '1 保存失败，请重试' || exit 2
''')
        assert conf.read_bytes()==saved
    for invalid in ('2','-1','yes','$(touch sentinel)'):
        conf.write_text(f'idle_pause_enabled=1\nidle_pause_minutes=17\ncustom_cover_enabled={invalid}\n',encoding='utf-8',newline='\n')
        assert shell('rr_config_read; echo "$idle_enabled $idle_minutes $custom_cover_enabled"')=='1 17 0'
    assert not (root/'sentinel').exists()
    for contents,expected in (
        ('idle_pause_enabled=1\nidle_pause_minutes=17','1 17 0'),
        ('idle_pause_enabled=1\nidle_pause_minutes=17\ncustom_cover_enabled=1','1 17 1'),
    ):
        conf.write_bytes(contents.encode())
        assert shell('rr_config_read; echo "$idle_enabled $idle_minutes $custom_cover_enabled"')==expected

    # Keep verified timer/power/render engines, allowing the 5.19 runtime path.
    for name in ('reading-insights-cover.lua','reading-idle.sh','reading-idle-touch.lua',
                 'native-reading-time-daemon.sh','reading-power.sh','reading-insights-render.lua',
                 'ui-calendar/total.png'):
        previous=subprocess.check_output(['git','show','92cd750:native-reading-time-package/'+name],cwd=ROOT)
        previous=previous.replace(b'9.8.1-5.20-vera-test1', b'9.8.1-5.19-vera-test1')
        current=(PKG/name).read_bytes()
        if name=='阅读记录-optimized.sh':
            # Only request month labels during the full navigation redraw;
            # rendering, timing, sleep exit and statistics code stay frozen.
            current=current.replace(b'perform_draw settings_change 1 1 0 0 1272 1696',
                                    b'perform_draw settings_change 1 0 0 0 1272 1696')
        assert current.replace(b'\r\n',b'\n')==previous.replace(b'\r\n',b'\n'),name

    states=[('settings_idle',enabled,n,'','') for enabled in (0,1) for n in (1,2,3,4,5,10,17,1440)]
    states += [('settings',e,n,'','') for e in (0,1) for n in (3,1440)]
    states += [('settings_custom',1,3,d,'') for d in ('','1','17','1440')]
    states += [('settings_custom',1,3,'1441','请输入 1 至 1440 的整数'),('settings_idle',1,3,'','保存失败，请重试')]
    states=[(*state,cover) for state in states for cover in ((0,1) if state[0]=='settings' else (state[1],))]
    previews=0
    for legacy in (False,True):
        viewer=(PKG/('阅读记录.sh' if legacy else '阅读记录-optimized.sh')).read_text(encoding='utf-8')
        ot=viewer[viewer.index('ot() {'):viewer.index('\n}',viewer.index('ot() {'))+2]
        for mode,enabled,minutes,digits,error,cover in states:
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
mode={mode}; idle_enabled={enabled}; idle_minutes={minutes}; custom_cover_enabled={cover}; settings_digits='{digits}'; settings_error='{error}'
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
            if mode=='settings_idle':
                assert f'settings-switch-{enabled}.png' in sprites
                selected=f'settings-preset-{minutes}.png' if minutes in (1,2,3,4,5,10) else 'settings-custom-selected.png'
                assert sprites==[f'settings-switch-{enabled}.png',selected]
                assert f'当前 {minutes} 分钟' in messages
                assert ('已开启' if enabled else '已关闭') in messages
                assert (f'连续 {minutes} 分钟无触摸，计时自动暂停。' if enabled else '未启用，仍按原有方式计时。') in messages
            elif mode=='settings':
                assert sprites==[f'settings-switch-{enabled}.png',f'settings-switch-{cover}.png']
                assert messages==[f'{minutes} 分钟无操作后暂停' if enabled else f'已关闭 · 已选 {minutes} 分钟']
            elif mode=='settings_cover':
                assert not sprites and '功能尚未接入' in messages[0]
            else:
                assert messages[0]==(digits or '请输入') and messages[1]=='分钟'
            if error:assert error in messages
            name=f'{mode}-{enabled}-{minutes}-{digits or "empty"}{"-error" if error else ""}{"-legacy" if legacy else ""}.png'
            if mode=='settings':name=name.replace('.png',f'-cover{cover}.png')
            im.save(OUT/name); previews+=1
            if mode=='settings_idle' and enabled and minutes==3 and not error and not legacy:
                im.save(OUT/'settings-preview.png')
            if mode=='settings_custom' and digits=='17' and not error and not legacy:
                im.save(OUT/'settings_custom-preview.png')
print(f'settings UI: PASS ({count} real Lua hitboxes, 16/24 byte ABI; actions/persistence/errors; {previews} FBInk-command previews, optimized + legacy)')
