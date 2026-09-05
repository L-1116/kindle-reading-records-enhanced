"""Offline integration checks: real POSIX shell functions + Lua 5.1 compositor.
No Kindle commands or foreground UI are used. Native FBInk text is approximated
only in preview images; those previews are NOT a Kindle validation result.
"""
from pathlib import Path
import calendar, datetime, hashlib, json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont
from lupa.lua51 import LuaRuntime

ROOT=Path(__file__).resolve().parent
PKG=ROOT/'native-reading-time-package'
BASE=ROOT.parent/'v9.6.4-ui-calendar'
OUT=ROOT/'validation'
OUT.mkdir(exist_ok=True)
os.chdir(ROOT)
SH='C:/Program Files/Git/usr/bin/sh.exe'
DASH='C:/Program Files/Git/usr/bin/dash.exe'
checks=[]
def record(name,detail):
    checks.append({'check':name,'result':'PASS','detail':detail})
def run_shell(code):
    p=subprocess.run([SH,'-c','export PATH="/usr/bin:$PATH"\n'+code],capture_output=True,encoding='utf-8')
    assert p.returncode==0,(code,p.stdout,p.stderr)
    return p.stdout

for file in [ROOT/'RUNME.sh', *PKG.glob('*.sh')]:
    for shell in (SH,DASH):
        subprocess.run([shell,'-n',str(file)],check=True,capture_output=True)
    assert not file.read_bytes().startswith(b'\xef\xbb\xbf')
    assert b'\r\n' not in file.read_bytes()
for file in PKG.glob('*.lua'):
    lua=LuaRuntime()
    lua.execute('assert(loadstring(...))',file.read_text(encoding='utf-8'))
record('syntax','All shipped .sh files: sh -n and dash -n; Lua files: Lua 5.1 loadstring; UTF-8 without BOM, LF.')

unchanged=['native-reading-time-daemon.sh','native-reading-time.conf','reading-insights-cache.awk','reading-insights-touch.lua','阅读记录.sh','Install-Native-Reading-Time.sh','NotoSansCJKsc-Regular.otf','FONT-LICENSE.txt']
for rel in unchanged:
    assert (PKG/rel).read_bytes()==(BASE/'native-reading-time-package'/rel).read_bytes(),rel
for folder in ('ui',):
    for file in (PKG/folder).iterdir():
        assert file.read_bytes()==(BASE/'native-reading-time-package'/folder/file.name).read_bytes()
record('preserved core','Daemon, Upstart, cache, progress query, legacy viewer/touch, original UI/font byte-identical.')

viewer=(PKG/'阅读记录-optimized.sh').read_text(encoding='utf-8')
old=(BASE/'native-reading-time-package/阅读记录-optimized.sh').read_text(encoding='utf-8')
for start,end in [('ensure_progress()','pgm_valid()'),('detect_screen()','time_text()'),('refresh_region()','dashboard_active=0'),('book_pages()','render_books()')]:
    assert viewer[viewer.index(start):viewer.index(end)]==old[old.index(start):old.index(end)]
for name in ('page_prev)','page_next)'):
    assert next(x for x in viewer.splitlines() if x.strip().startswith(name))==next(x for x in old.splitlines() if x.strip().startswith(name))
assert 'mode=daily; view_year=' in viewer
record('interaction invariants','Default daily; original book paging branches, page count, progress query, geometry and refresh policy unchanged.')

# Extract definitions only: never run startup, hardware access, or EXIT cleanup.
defs=viewer[:viewer.index('\ndetect_screen; find_touch_device')]
defs=defs.replace('exec >> "$LOG" 2>&1','').replace('\ntrap cleanup EXIT INT TERM HUP\n','\n')
defs=defs.replace('echo "$(date): optimized dashboard launch, uid=$(id -u), pid=$$"','')
(OUT/'functions.sh').write_text(defs,encoding='utf-8',newline='\n')
calendar_key=hashlib.sha256(viewer[viewer.index('days_in_month()'):viewer.index('shift_month()')].encode()).hexdigest()
cached=OUT/'calendar-arithmetic.tsv'
if not cached.exists():
    import shutil
    assert viewer[viewer.index('days_in_month()'):viewer.index('shift_month()')]==old[old.index('days_in_month()'):old.index('shift_month()')]
    shutil.copy2(BASE/'validation/calendar-arithmetic.tsv',cached)
    (OUT/'calendar-arithmetic.sha256').write_text(calendar_key)
cache_key=OUT/'calendar-arithmetic.sha256'
if cached.exists() and cache_key.exists() and cache_key.read_text()==calendar_key:
    rows=cached.read_text()
else:
    rows=run_shell('''. validation/functions.sh
y=1900
while [ "$y" -le 2100 ]; do
 m=1
 while [ "$m" -le 12 ]; do printf '%s %s %s %s\\n' "$y" "$m" "$(days_in_month "$y" "$m")" "$(weekday_offset "$y" "$m")"; m=$((m+1)); done
 y=$((y+1))
done''')
months=[]
for row in rows.splitlines():
    y,m,dim,off=map(int,row.split()); expected=calendar.monthrange(y,m)
    assert (off,dim)==expected,(y,m,dim,off,expected)
    months.append((y,m,dim,off))
record('calendar arithmetic',f'{len(months)} months (1900–2100), including century leap rules; 28/29/30/31 days and all weekday offsets match Python calendar.')
cached.write_text(rows); cache_key.write_text(calendar_key)
print('Calendar arithmetic passed.',flush=True)

shift=run_shell('''. validation/functions.sh
daily_y=2026; daily_m=12; selected_day=31; shift_month 1; echo "$daily_y $daily_m $selected_day"
shift_month -1; echo "$daily_y $daily_m $selected_day"
daily_y=2024; daily_m=3; selected_day=31; shift_month -1; echo "$daily_y $daily_m $selected_day"
''')
assert shift.splitlines()==['2027 1 1','2026 12 1','2024 2 1']
record('month transitions','December ↔ January and March 31 → leap February reset selection to valid day 1.')

touch=(PKG/'reading-insights-touch-ui.lua').read_text(encoding='utf-8')
touch=touch[:touch.index('\nnote(string.format("interactive watcher started')]
touch=touch.replace('local f = assert(io.open(device, "rb"))','local f = nil').replace('local log = io.open(log_path, "a")','local log = nil')
touch+='\nreturn action_for_logical, action_for_physical'
tap_count=0
for y,m,dim,off in months:
    lua=LuaRuntime(); lua.globals().arg=lua.table_from({3:'daily',4:off,5:dim})
    logical,physical=lua.execute(touch)
    nr=(off+dim+6)//7; ch=648//nr
    for idx in range(nr*7):
        col,row=idx%7,idx//7; day=idx-off+1
        expected=f'day_{day}' if 1<=day<=dim else 'ignore'
        for dx,dy in ((0,0),(153,ch-7),(77,ch//2)):
            assert logical(75+160*col+dx,460+ch*row+dy)==expected,(y,m,idx,dx,dy)
            tap_count+=1
        assert logical(75+160*col+154,460+ch*row+5) == 'ignore'
        assert logical(75+160*col+5,460+ch*row+ch-6) == 'ignore'
    for point,action in [((200,210),'tab_daily'),((600,210),'tab_books'),((1050,210),'tab_total'),((330,360),'month_prev'),((950,360),'month_next')]:
        assert logical(*point)==action
record('touch map',f'{tap_count} real Lua hit checks across every month; cell corners/interiors, gutters, empty slots, tab and month buttons verified.')
for w,h,ox,oy in [(1272,1696,0,0),(1264,1685,0,0),(900,1200,20,40),(600,800,0,0)]:
    lua=LuaRuntime(); lua.globals().arg=lua.table_from({3:'daily',4:1,5:30,6:ox,7:oy,8:w,9:h})
    logical,physical=lua.execute(touch)
    assert physical(ox+952*w/1272,oy+500*h/1696)=='day_5'
record('scaled touch','Logical-to-physical centers checked at four viewports, including nonzero origins; baseline transform retained.')

# A small command adapter runs the shipped Lua code with its real files.
(OUT/'lua_runner.py').write_text('''import sys
from pathlib import Path
from lupa.lua51 import LuaRuntime
lua=LuaRuntime()
lua.globals().arg=lua.table_from({i:v for i,v in enumerate(sys.argv[1:])})
lua.execute(Path(sys.argv[1]).read_text(encoding="utf-8"))
''',encoding='utf-8')
setup='''. validation/functions.sh
SESSION_DIR=validation/session; mkdir -p "$SESSION_DIR"
DATA="$SESSION_DIR/reading-time.tsv"; SUMMARY="$SESSION_DIR/summary.tsv"; MONTHS="$SESSION_DIR/months.tsv"; DAYS="$SESSION_DIR/days.tsv"; DAY_BOOKS="$SESSION_DIR/day-books.tsv"; BOOKS="$SESSION_DIR/books.tsv"; PROGRESS="$SESSION_DIR/book-progress.tsv"; SPEC="$SESSION_DIR/render-spec.tsv"
RENDERER=native-reading-time-package/reading-insights-render.lua; RENDER_ASSETS=native-reading-time-package/render-assets; CACHE_BUILDER=native-reading-time-package/reading-insights-cache.awk; TITLE_LAYOUT=native-reading-time-package/reading-insights-titles.lua
renderer_available=1; RFONT=native-reading-time-package/NotoSansCJKsc-Regular.otf
lua() { python validation/lua_runner.py "$@"; }
image() { printf 'image\\t%s\\t%s\\t%s\\t%s\\t%s\\n' "$@" >> "$SESSION_DIR/draw.tsv"; }
ot() { printf 'ot\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n' "$@" >> "$SESSION_DIR/draw.tsv"; }
rect() { :; }
'''
session=OUT/'session'; session.mkdir(exist_ok=True)
fixture='date\tbook_id\tseconds\ttitle\n2026-09-02\tb1\t3600\t72-庆余年\n2026-09-03\tb1\t5400\t72-庆余年\n2026-09-04\tb2\t1059\t77-亡灵法师弱？关我死亡主宰什么事\n2026-09-05\tb2\t3357\t77-亡灵法师弱？关我死亡主宰什么事\n2026-09-05\tb3\t1344\t55-变身荒野女主播\n'
long_cn='一本很长的中文书名用于检查标题换行边界和右侧时长不会重叠'*4
long_en="Harry Potter and the Philosopher's Stone (English Edition) "+'W'*150
(session/'reading-time.tsv').write_text(fixture,encoding='utf-8')
run_shell(setup+'build_cache\n')
assert (session/'summary.tsv').read_text().strip()=='14760\t4'
record('cache regression','Real unchanged AWK pipeline: repeated sessions and three books sum to 246 minutes over four days.')

def render(name,mode,code):
    (session/'draw.tsv').write_text('',encoding='utf-8')
    run_shell(setup+'cache_ok=1\n'+code)
    spec=(session/'render-spec.tsv').read_text(encoding='utf-8')
    # Assert every composed primitive and actual atlas glyph stays on its canvas.
    atlas={}
    for row in (PKG/'render-assets/dynamic-glyphs.tsv').read_text().splitlines()[1:]:
        st,sz,ch,x,y,w,h,adv,bx,by,bl,ink,asc,desc=row.split('\t')
        atlas[(st,sz,chr(int(ch,16)))]=(int(w),int(h),int(adv),int(bx),int(by),int(bl),int(ink))
    canvases={}
    for row in spec.splitlines():
        p=row.split('\t')
        if p[0]=='canvas': canvases[p[1]]=(int(p[2]),int(p[3]))
        elif p[0]=='rect':
            _,cid,x,y,w,h,c=p; x,y,w,h=map(int,(x,y,w,h)); cw,ch=canvases[cid]
            assert 0<=x and 0<=y and x+w<=cw and y+h<=ch,(name,row)
        elif p[0]=='text':
            _,cid,st,sz,x,y,align,color,msg=p[:9]
            glyph=[atlas[(st,sz,char)] for char in msg]
            advance=sum(g[2] for g in glyph); x=int(x); y=int(y); cw,ch=canvases[cid]
            lefts=[];rights=[];cursor=0
            for gw,gh,ga,bx,by,bl,ink in glyph:
                if ink: lefts.append(cursor+bx);rights.append(cursor+bx+gw)
                cursor+=ga
            left=min(lefts,default=0);right=max(rights,default=advance)
            if align=='center': x=(x-(left+right)/2)//1
            elif align=='right': x-=right
            for gw,gh,ga,bx,by,bl,ink in glyph:
                assert not ink or (x+bx>=0 and y+bl+by>=0 and x+bx+gw<=cw and y+bl+by+gh<=ch),(name,row,x,y,gw,gh,bx,by,bl)
                x+=ga
    (OUT/(name+'.spec.tsv')).write_text(spec,encoding='utf-8')
    # Composite exact Lua PGM output plus approximate FBInk title rasterization.
    im=Image.open(PKG/'ui-calendar'/(mode+'.png')).convert('L')
    d=ImageDraw.Draw(im)
    for line in (session/'draw.tsv').read_text(encoding='utf-8').splitlines():
        fields=line.split('\t')
        if fields[0]=='image':
            _,path,x,y,w,h=fields
            tile=Image.open(ROOT/path); assert tile.size==(int(w),int(h))
            im.paste(tile,(int(x),int(y)))
        else:
            _,size,y,x,right,style,text=fields
            font=ImageFont.truetype(str(PKG/'NotoSansCJKsc-Regular.otf'),int(size))
            assert font.getlength(text)<=1272-int(x)-int(right),(name,text)
            d.text((int(x),int(y)),text,font=font,fill=0,anchor='lt')
    im.save(OUT/(name+'.png'))
    return spec

spec=render('daily-2026-09','daily','daily_y=2026; daily_m=9; selected_day=5; render_daily 1')
assert '1时18分' in spec and '本月阅读 4 天  共 4小时6分钟' in spec
spec=render('total-rounding','total','view_year=2026; render_total')
assert '日均  1小时2分钟' in spec
assert 'canvas\tchart\t1122\t690' in spec
record('daily and average','Actual Shell + Lua rendering: selected daily total 1时18分; monthly 4天/4小时6分钟; 246÷4 rounds to 1小时2分钟.')
for sec,days,label in [(0,0,'0分钟'),(29,1,'0分钟'),(30,1,'1分钟'),(3599,1,'1小时0分钟'),(3690,1,'1小时2分钟'),(14759,4,'1小时1分钟')]:
    (session/'summary.tsv').write_text(f'{sec}\t{days}\n')
    p=render(f'average-{sec}-{days}','total','view_year=2026; render_total')
    assert '日均  '+label in p
(session/'summary.tsv').write_text('14760\t4\n')
record('rounding boundaries','Zero days and values just below/at half-minute boundaries rendered; hour carry and 61.495min vs 61.5min verified.')
for name,y,m,day in [('empty-six-row',2026,3,31),('empty-four-row',2027,2,28),('leap-month',2024,2,29),('new-year',2027,1,1)]:
    spec=render(name,'daily',f'daily_y={y}; daily_m={m}; selected_day={day}; render_daily 1')
    assert '当日无阅读记录' in spec
    assert '本月阅读 0 天  共 0分钟' in spec
record('empty month rendering','Real rendered four/five/six-row months, Feb 29, Jan 1, empty day/month: dates remain visible with no duration, explicit empty detail.')

times=[0,1,25,59,60,61,3599,3600,4680,86399,86400]
actual=run_shell(setup+'\n'.join(f'printf "[{v}]"; calendar_time {v}; printf "\\n"' for v in times))
expected=['[0]','[1]1秒','[25]25秒','[59]59秒','[60]1分','[61]1分','[3599]59分','[3600]1时0分','[4680]1时18分','[86399]23时59分','[86400]24时0分']
assert actual.splitlines()==expected
# Exercise atlas glyphs and short durations on one real rendered month.
(session/'days.tsv').write_text(''.join(f'2026-09-{i:02}\t{v}\n' for i,v in enumerate(times,1)),encoding='utf-8')
render('duration-range','daily','daily_y=2026; daily_m=9; selected_day=10; render_daily 1')
record('duration boundaries','0, 1–59 sec, 1–59 min, exact hour, several hours and 24h tested; no record shows only date; sub-minute reading remains visible in seconds.')

(session/'books.tsv').write_text(''.join(f'{sec}\t{title}\tb{i}\t{i}\n' for i,(sec,title) in enumerate([(9000,'72-庆余年'),(4416,long_cn),(1344,'55-变身荒野女主播'),(25,'67-球状闪电'),(10,long_en)],1)),encoding='utf-8')
(session/'book-progress.tsv').write_text('13\t72-庆余年\n100\t'+long_cn+'\n30\t55-变身荒野女主播\n0\t67-球状闪电\n',encoding='utf-8')
spec=render('books-long-titles','books','progress_loaded=1; book_page=1; render_books')
assert '13%' in spec and '100%' in spec and '0%' in spec and '暂无进度' in spec
title_lines=(session/'book-titles.tsv').read_text(encoding='utf-8').splitlines()
assert len(title_lines)<=10 and sum('…' in x for x in title_lines)==2
(session/'day-books.tsv').write_text(f'2026-09-05\t3600\t{long_cn}\n2026-09-05\t1800\t{long_en}\n2026-09-05\t60\t短书名\n',encoding='utf-8')
(session/'days.tsv').write_text('2026-09-05\t5460\n',encoding='utf-8')
render('daily-long-titles','daily','daily_y=2026; daily_m=9; selected_day=5; render_daily 1')
lines=(session/'daily-titles.tsv').read_text(encoding='utf-8').splitlines()
assert len(lines)<=6 and sum('…' in x for x in lines)==2
record('long titles and progress','Very long Chinese and English/no-space titles wrap to at most two lines then ellipsis; measured width within native text margins. Progress 0/13/30/100 and unknown render successfully.')

# Book pagination artwork is exactly the baseline region, pixel for pixel.
for mode in ('books',):
    a=Image.open(PKG/'ui'/f'{mode}.png').convert('L'); b=Image.open(PKG/'ui-calendar'/f'{mode}.png').convert('L')
    assert a.crop((0,1460,1272,1696)).tobytes()==b.crop((0,1460,1272,1696)).tobytes()
record('book footer unchanged','Pagination footer and buttons byte-identical pixels; existing no-op behavior retained.')

exec((ROOT/'checks_polish.py').read_text(encoding='utf-8'))

manifest={}
for file in sorted(BASE.rglob('*')):
    if file.is_file():manifest[file.relative_to(BASE).as_posix()]=hashlib.sha256(file.read_bytes()).hexdigest()
(OUT/'baseline-sha256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
changes=[]
for file in sorted(PKG.rglob('*')):
    if file.is_file():
        rel=file.relative_to(ROOT); source=BASE/rel
        if not source.exists() or file.read_bytes()!=source.read_bytes():changes.append(str(rel))
result={'checks':checks,'modified_or_added_payload':changes,'limits':['No physical Kindle/FBInk runtime test performed. PNG previews approximate native FBInk text only.','Daily details paginate all books; capacity is derived from available height.','Books retain baseline sorting by cumulative seconds and five books per page.']}
(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True,indent=2))
