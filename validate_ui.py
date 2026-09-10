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
STABLE=ROOT.parent/'v9.6.9-calendar-heatmap'
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

stable_payload_changes=[]
for file in sorted(PKG.rglob('*')):
    if file.is_file():
        source=STABLE/file.relative_to(ROOT)
        if not source.exists() or file.read_bytes()!=source.read_bytes():
            stable_payload_changes.append(file.relative_to(ROOT).as_posix())
assert stable_payload_changes==[
    'native-reading-time-package/Install-Native-Reading-Time-Optimized.sh',
    'native-reading-time-package/reading-insights-render.lua',
    'native-reading-time-package/阅读记录-optimized.sh',
]
record('stable payload scope','Against v9.6.9, only the optimized viewer, compositor and versioned installer payload changed; all other shipped payload bytes are identical.')

unchanged=['native-reading-time-daemon.sh','native-reading-time.conf','reading-insights-cache.awk','reading-insights-touch.lua','阅读记录.sh','Install-Native-Reading-Time.sh','NotoSansCJKsc-Regular.otf','FONT-LICENSE.txt']
for rel in unchanged:
    assert (PKG/rel).read_bytes()==(STABLE/'native-reading-time-package'/rel).read_bytes(),rel
for folder in ('ui',):
    for file in (PKG/folder).iterdir():
        assert file.read_bytes()==(STABLE/'native-reading-time-package'/folder/file.name).read_bytes()
record('preserved core','Daemon, Upstart, cache, progress query, legacy viewer/touch, UI/font byte-identical to v9.6.9.')

viewer=(PKG/'阅读记录-optimized.sh').read_text(encoding='utf-8')
old=(STABLE/'native-reading-time-package/阅读记录-optimized.sh').read_text(encoding='utf-8')
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
DATA="$SESSION_DIR/reading-time.tsv"; SUMMARY="$SESSION_DIR/summary.tsv"; MONTHS="$SESSION_DIR/months.tsv"; WEEKS="$SESSION_DIR/weeks.tsv"; DAYS="$SESSION_DIR/days.tsv"; DAY_BOOKS="$SESSION_DIR/day-books.tsv"; CALENDAR="$SESSION_DIR/calendar.tsv"
BOOKS="$SESSION_DIR/books.tsv"; BOOKS_7D="$SESSION_DIR/books-7d.tsv"; BOOKS_MONTH="$SESSION_DIR/books-month.tsv"; BOOKS_YEAR="$SESSION_DIR/books-year.tsv"; PROGRESS="$SESSION_DIR/book-progress.tsv"; SPEC="$SESSION_DIR/render-spec.tsv"; TOTAL_VALUES="$SESSION_DIR/total-values.tsv"; WEEK_VIEW="$SESSION_DIR/week-view.tsv"
RENDERER=native-reading-time-package/reading-insights-render.lua; RENDER_ASSETS=native-reading-time-package/render-assets; CACHE_BUILDER=native-reading-time-package/reading-insights-cache.awk; TITLE_LAYOUT=native-reading-time-package/reading-insights-titles.lua
renderer_available=1; RFONT=native-reading-time-package/NotoSansCJKsc-Regular.otf
today=0000-00-00
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
        elif p[0] in ('text','textfit'):
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
            if p[0]=='textfit':
                min_x,max_x=map(int,p[10:12]); padding=4 if len(p)>9 and p[9] else 0
                if x+left-padding<min_x: x=min_x-left+padding
                if x+right+padding>max_x: x=max_x-right-padding
                assert x+left-padding>=min_x and x+right+padding<=max_x,(name,row,x,left,right)
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
    remaining=sec; day_values=[]
    for index in range(days):
        value=remaining//(days-index); remaining-=value
        day_values.append(f'2026-09-{index+1:02}\t{value}\n')
    (session/'days.tsv').write_text(''.join(day_values),encoding='utf-8')
    p=render(f'average-{sec}-{days}','total','view_year=2026; render_total')
    assert '日均  '+label in p
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

book_fixture=''.join(f'{sec}\t{title}\tb{i}\t{i}\n' for i,(sec,title) in enumerate([(9000,'72-庆余年'),(4416,long_cn),(1344,'55-变身荒野女主播'),(25,'67-球状闪电'),(10,long_en)],1))
(session/'books.tsv').write_text(book_fixture,encoding='utf-8')
(session/'books-7d.tsv').write_text(book_fixture,encoding='utf-8')
(session/'book-progress.tsv').write_text('13\t72-庆余年\n100\t'+long_cn+'\n30\t55-变身荒野女主播\n0\t67-球状闪电\n',encoding='utf-8')
spec=render('books-long-titles','books','progress_loaded=1; book_filter=7d; book_page=1; render_books')
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

# Calendar heatmap uses the same raw daily seconds already consumed by the
# duration labels and month summary. Verify exact second boundaries first.
boundary_seconds=[0,1,1799,1800,3599,3600,7199,7200,10799,10800,14399,14400,19020,36000]
expected_levels=[0,1,1,2,2,3,3,4,4,5,5,6,6,6]
expected_grays=[255,235,235,210,210,180,180,145,145,105,105,70,70,70]
expected_inks=[0,0,0,0,0,0,0,0,0,255,255,255,255,255]
boundary_output=run_shell(setup+'\n'.join(
    f'l=$(calendar_heat_level {seconds}); printf "%s\\t%s\\t%s\\t%s\\n" {seconds} "$l" "$(calendar_heat_gray "$l")" "$(calendar_heat_ink "$l")"'
    for seconds in boundary_seconds
))
actual_boundary=[tuple(map(int,line.split('\t'))) for line in boundary_output.splitlines()]
assert actual_boundary==list(zip(boundary_seconds,expected_levels,expected_grays,expected_inks))
record('heatmap exact boundaries','Raw seconds pass all 14 cases: 0, 1, every threshold minus one, exact 30m/1h/2h/3h/4h, 5h17m and 10h; no minute rounding or off-by-one.')

renderer_source=(PKG/'reading-insights-render.lua').read_text(encoding='utf-8')
assert 'assert(tonumber(token()) == 255' in renderer_source
assert 'string.rep(string.char(value), width)' in renderer_source
record('heatmap grayscale support','The existing compositor writes exact 8-bit PGM values (0 black, 255 white), so 255/235/210/180/145/105/70 are used without dithering.')

def calendar_cell_point(year,month,day,dx=10,dy=10):
    offset,dim=calendar.monthrange(year,month)
    rows=(offset+dim+6)//7; cell_h=648//rows; index=offset+day-1
    return index%7*160+dx,index//7*cell_h+dy

def slot_point(year,month,index,dx=10,dy=10):
    offset,dim=calendar.monthrange(year,month)
    rows=(offset+dim+6)//7; cell_h=648//rows
    return index%7*160+dx,index//7*cell_h+dy

def calendar_pixels():
    return Image.open(session/'daily-calendar.pgm').convert('L')

# One month covers Level 0–6, threshold edges, a non-Monday month start and
# trailing empty slots. Day 13 is today and retains its true level-6 fill.
(session/'days.tsv').write_text(''.join(
    f'2026-09-{day:02}\t{seconds}\n' for day,seconds in enumerate(boundary_seconds,1)
),encoding='utf-8')
(session/'day-books.tsv').write_text('2026-09-13\t19020\t热力测试书籍\n',encoding='utf-8')
heat_spec=render('heatmap-boundaries','daily','today=2026-09-13; daily_y=2026; daily_m=9; selected_day=13; detail_page=1; render_daily 1')
heat_image=calendar_pixels()
for day,(gray,level) in enumerate(zip(expected_grays,expected_levels),1):
    assert heat_image.getpixel(calendar_cell_point(2026,9,day))==gray,(day,level,gray)
for index in list(range(calendar.monthrange(2026,9)[0]))+list(range(calendar.monthrange(2026,9)[0]+30,35)):
    assert heat_image.getpixel(slot_point(2026,9,index))==255,index
date_text={int(parts[8]):int(parts[7]) for line in heat_spec.splitlines()
           if (parts:=line.split('\t'))[:4]==['text','calendar','B','36']}
assert date_text[9]==0 and date_text[10]==255 and date_text[11]==255
assert date_text[12]==255 and date_text[13]==255 and date_text[14]==255
assert '本月阅读 13 天  共 36小时16分钟' in heat_spec
assert '共 5小时17分钟' in heat_spec
today_x,today_y=calendar_cell_point(2026,9,13,0,0)
assert all(heat_image.getpixel((today_x+d,today_y+20))==20 for d in range(4))
assert heat_image.getpixel((today_x+4,today_y+20))==70
record('heatmap month rendering','A September fixture covers all levels and boundaries: inner fills match exact gray values, Level 5/6 text is white, Level 4 and lighter text is black, today keeps Level 6 while gaining a 4 px inward border, and empty slots stay white.')

# Selection continues to drive details but no longer changes any heat fill;
# today's border remains attached to the actual date rather than selection.
render('heatmap-selection-moved','daily','today=2026-09-13; daily_y=2026; daily_m=9; selected_day=2; detail_page=1; render_daily 0')
moved_image=calendar_pixels()
assert moved_image.getpixel(calendar_cell_point(2026,9,13))==70
assert moved_image.getpixel(calendar_cell_point(2026,9,2))==235
today_x,today_y=calendar_cell_point(2026,9,13,0,0)
selected_x,selected_y=calendar_cell_point(2026,9,2,0,0)
assert moved_image.getpixel((today_x+3,today_y+20))==20 and moved_image.getpixel((today_x+4,today_y+20))==70
assert moved_image.getpixel((selected_x+2,selected_y+20))==235
record('today versus selection','Selecting another date changes details only: both cells retain their heat gray and the 4 px border remains exclusively on today.')

# Empty month, one active day, and a fully populated 31-day month exercise the
# three density extremes without changing calendar geometry or summaries.
(session/'days.tsv').write_text('',encoding='utf-8'); (session/'day-books.tsv').write_text('',encoding='utf-8')
empty_spec=render('heatmap-empty-month','daily','daily_y=2026; daily_m=3; selected_day=31; detail_page=1; render_daily 1')
empty_image=calendar_pixels()
assert all(empty_image.getpixel(calendar_cell_point(2026,3,day))==255 for day in range(1,32))
assert all(empty_image.getpixel(slot_point(2026,3,index))==255 for index in range(6))
assert '本月阅读 0 天  共 0分钟' in empty_spec and '当日无阅读记录' in empty_spec
(session/'days.tsv').write_text('2026-04-15\t1\n',encoding='utf-8')
one_spec=render('heatmap-one-day','daily','daily_y=2026; daily_m=4; selected_day=1; detail_page=1; render_daily 1')
assert calendar_pixels().getpixel(calendar_cell_point(2026,4,15))==235
assert '本月阅读 1 天  共 0分钟' in one_spec
all_month_seconds=[(day%6+1)*1800 for day in range(1,32)]
(session/'days.tsv').write_text(''.join(f'2026-05-{day:02}\t{seconds}\n' for day,seconds in enumerate(all_month_seconds,1)),encoding='utf-8')
full_spec=render('heatmap-31-days','daily','daily_y=2026; daily_m=5; selected_day=1; detail_page=1; render_daily 1')
assert '本月阅读 31 天' in full_spec
assert all(calendar_pixels().getpixel(calendar_cell_point(2026,5,day))!=(255) for day in range(2,32))
record('heatmap month densities','Completely empty, one-reading-day and all-31-days-populated months render correctly; no-reading cells remain white and existing month statistics stay intact.')

# Month changes and returning from another page both regenerate from DAYS. Use
# deliberately different August/September values to detect stale backgrounds.
(session/'days.tsv').write_text('2026-08-01\t1800\n2026-09-01\t14400\n',encoding='utf-8')
render('heatmap-september-before-switch','daily','daily_y=2026; daily_m=9; selected_day=2; detail_page=1; render_daily 1')
assert calendar_pixels().getpixel(calendar_cell_point(2026,9,1))==70
switch_spec=render('heatmap-august-after-switch','daily','daily_y=2026; daily_m=9; selected_day=28; detail_page=4; shift_month -1; render_daily 1')
assert '2026年8月' in switch_spec and '8月1日 阅读详情' in switch_spec
assert calendar_pixels().getpixel(calendar_cell_point(2026,8,1))==210
render('heatmap-august-unselected','daily','daily_y=2026; daily_m=8; selected_day=2; detail_page=1; render_daily 1')
assert calendar_pixels().getpixel(calendar_cell_point(2026,8,1))==210
(session/'books.tsv').write_text('',encoding='utf-8'); (session/'books-7d.tsv').write_text('',encoding='utf-8')
(session/'books-month.tsv').write_text('',encoding='utf-8'); (session/'books-year.tsv').write_text('',encoding='utf-8')
render('heatmap-other-page','books','progress_loaded=1; book_filter=7d; book_page=1; render_books')
render('heatmap-return-daily','daily','daily_y=2026; daily_m=9; selected_day=2; detail_page=1; render_daily 1')
assert calendar_pixels().getpixel(calendar_cell_point(2026,9,1))==70
record('heatmap redraw lifecycle','Previous/next-month state resets selection/page and rebuilds all cell fills from the target month; returning from another primary page and a fresh render both regenerate the correct heatmap with no stale prior-month gray.')

# The user's representative September values provide a practical visual preview.
representative={2:1740,3:5580,4:2700,5:19020,6:7500}
(session/'days.tsv').write_text(''.join(f'2026-09-{day:02}\t{seconds}\n' for day,seconds in representative.items()),encoding='utf-8')
(session/'day-books.tsv').write_text('2026-09-05\t19020\t实机灰度预期检查\n',encoding='utf-8')
representative_spec=render('heatmap-2026-09','daily','daily_y=2026; daily_m=9; selected_day=1; detail_page=1; render_daily 1')
representative_image=calendar_pixels()
assert [representative_image.getpixel(calendar_cell_point(2026,9,day)) for day in representative]==[235,180,210,70,145]
assert '本月阅读 5 天  共 10小时9分钟' in representative_spec
record('heatmap representative month','Visual preview matches the requested pattern: Sep 2/3/4/5/6 are Level 1/3/2/6/4 (235/180/210/70/145).')

# Required today cases: the interior must keep its duration gray, the 4 px
# border must remain black, and text ink must continue to follow heat level.
today_cases=[
    ('zero',0,255,0),
    ('four-minutes',240,235,0),
    ('forty-five-minutes',2700,210,0),
    ('ninety-minutes',5400,180,0),
    ('four-hours',14400,70,255),
]
for case,seconds,gray,ink in today_cases:
    rows='' if seconds==0 else f'2026-09-10\t{seconds}\n'
    (session/'days.tsv').write_text(rows,encoding='utf-8')
    spec=render(f'today-{case}','daily',f'today=2026-09-10; daily_y=2026; daily_m=9; selected_day=9; detail_page=1; render_daily 1')
    image=calendar_pixels(); x,y=calendar_cell_point(2026,9,10,0,0)
    assert all(image.getpixel((x+dx,y+55))==20 for dx in range(4)),case
    assert image.getpixel((x+4,y+55))==gray,case
    date_line=next(line.split('\t') for line in spec.splitlines()
                   if line.startswith('text\tcalendar\tB\t36\t') and line.split('\t')[8]=='10')
    assert int(date_line[7])==ink,(case,date_line)
record('today duration matrix','Today at 0 min, 4 min, 45 min, 90 min and 4 h keeps gray 255/235/210/180/70 respectively, always has a 4 px inward black border, and keeps the heat-derived black/white text decision.')

# Required weekly Monday cases.  Override only the prepared view/summary in
# this isolated render harness; production period calculations remain intact.
week_cases=[('zero',0),('thirty-five-minutes',35),('two-hours',120),('over-three-hours',210)]
week_layouts=[]
for case,monday_minutes in week_cases:
    values=''.join(f'周{"一二三四五六日"[i]}\t{monday_minutes if i==0 else 0}\t125\n' for i in range(7))
    (session/'total-values.tsv').write_text(values,encoding='utf-8')
    code=(
        "prepare_total_values() { :; }; "
        f"prepare_period_summary() {{ total={monday_minutes*60}; read_days={1 if monday_minutes else 0}; average={monday_minutes*60}; period_title=2026; }}; "
        "total_period=week; render_total"
    )
    spec=render(f'week-layout-{case}','total',code)
    parts=[line.split('\t') for line in spec.splitlines()]
    baseline=next(p for p in parts if p[:2]==['rect','chart'] and p[3]=='630' and p[5]=='3')
    plot_left,plot_width=int(baseline[2]),int(baseline[4]); plot_right=plot_left+plot_width
    y_ticks=[p for p in parts if p[:4]==['text','chart','R','20']]
    assert y_ticks and all(p[6]=='right' for p in y_ticks)
    axis_text_right=int(y_ticks[0][4]); assert plot_left-axis_text_right==28
    day_labels=[p for p in parts if p[:4]==['text','chart','B','24']]
    assert [p[8] for p in day_labels]==[f'周{x}' for x in '一二三四五六日']
    centers=[int(p[4]) for p in day_labels]
    gaps=[b-a for a,b in zip(centers,centers[1:])]
    assert max(gaps)-min(gaps)<=1,(case,centers)
    assert centers[0]>plot_left and centers[-1]<plot_right
    bars=[p for p in parts if p[:2]==['rect','chart'] and p[4]=='76']
    assert all(int(p[2])>=plot_left and int(p[2])+int(p[4])<=plot_right for p in bars)
    if monday_minutes:
        assert len(bars)==1 and int(bars[0][2])+38==centers[0],(case,bars,centers)
        value=next(p for p in parts if p[:4]==['textfit','chart','B','20'])
        assert int(value[10])==plot_left and int(value[11])==plot_right
    else:
        assert not bars and not any(p[0]=='textfit' for p in parts)
    week_layouts.append((case,plot_left,plot_width,centers))
assert len({tuple(layout[3]) for layout in week_layouts})==1
record('weekly plot layout','Monday at 0, 35, 120 and 210 min uses one measured Y-axis gutter plus a 28 px safety gap; all seven centers are evenly derived from one plot area, labels share those centers, value text is plot-bounded, and Sunday retains right-side clearance.')

# No cache/database/daemon/other-page logic changed. Calendar rendering remains
# one offscreen canvas publication followed by the existing single region refresh.
stable_viewer=(STABLE/'native-reading-time-package/阅读记录-optimized.sh').read_text(encoding='utf-8')
for start,end in [('build_cache()','progress_loaded=0'),('prepare_total_values()','spec_toggle_button()'),('active_books()','draw_background()'),('refresh_region()','dashboard_active=0')]:
    assert viewer[viewer.index(start):viewer.index(end)]==stable_viewer[stable_viewer.index(start):stable_viewer.index(end)]
daily_block=viewer[viewer.index('render_daily()'):viewer.index('active_books()')]
assert daily_block.count('canvas calendar ')==1 and daily_block.count('swrite calendar')==1
assert daily_block.count('image "$SESSION_DIR/daily-calendar.pgm"')==1 and 'refresh_region' not in daily_block
assert 'month_prev) shift_month -1; perform_draw month_previous 0 1 55 320 1162 1308;;' in viewer
assert 'day_*) new_day=' in viewer and 'perform_draw date_select 0 0 55 460 1162 1168' in viewer
record('heatmap isolation and refresh','Cache builder, daemon, database inputs, period-data calculations, books functions and refresh policy are byte-identical to v9.6.9. The calendar is composed offscreen once, published once, then refreshed once through the existing GC16 region path.')

manifest={}
for file in sorted(BASE.rglob('*')):
    if file.is_file():manifest[file.relative_to(BASE).as_posix()]=hashlib.sha256(file.read_bytes()).hexdigest()
(OUT/'baseline-sha256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
changes=[]
for file in sorted(PKG.rglob('*')):
    if file.is_file():
        rel=file.relative_to(ROOT); source=STABLE/rel
        if not source.exists() or file.read_bytes()!=source.read_bytes():changes.append(str(rel))
result={'checks':checks,'modified_or_added_payload':changes,'limits':['No physical Kindle/FBInk runtime test performed. PNG previews approximate native FBInk text only; grayscale distinction and ghosting need on-device observation.','Date selection still redraws the whole calendar+detail offscreen and performs one regional refresh, preserving the low-risk v9.6.9 interaction path.','Daily details paginate all books; capacity is derived from available height.','Books retain baseline sorting by cumulative seconds and five books per page.']}
(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True,indent=2))
