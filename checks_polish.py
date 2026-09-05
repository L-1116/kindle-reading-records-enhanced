"""Additional real-renderer tests, executed by validate_ui.py with its harness."""
import re
from PIL import ImageOps

for y,m,day in [(2026,9,1),(2026,3,1),(2027,2,1),(2026,10,31)]:
    p=render(f'grid-{y}-{m}','daily',f'daily_y={y}; daily_m={m}; selected_day={day}; detail_page=1; render_daily 1')
    off,dim=calendar.monthrange(y,m); nr=(off+dim+6)//7; height=648//nr
    rects={tuple(map(int,line.split('\t')[2:6])) for line in p.splitlines() if line.startswith('rect\tcalendar\t')}
    for row in range(nr):
        for col in range(7):assert (col*160,row*height,154,height-6) in rects
    assert 1.10<=(height-6)/(576//nr-6)<=1.15
record('complete and taller grid','Every one of the seven slots in every row has a border, including empty month slots; cell height increases 12.8–13.3%.')

# Ink bounding boxes, not guessed string lengths or arrow margins, are centered.
for y,m in [(2026,9),(2026,10),(2027,1),(2028,12)]:
    render(f'center-{y}-{m}','daily',f'daily_y={y}; daily_m={m}; selected_day=1; detail_page=1; render_daily 1')
    box=ImageOps.invert(Image.open(session/'daily-month.pgm')).getbbox()
    assert abs(450+(box[0]+box[2])/2-636)<=0.5,(y,m,box)
for y in [2026,2027,2030]:
    render(f'year-{y}','total',f'view_year={y}; render_total')
    box=ImageOps.invert(Image.open(session/'total-year.pgm')).getbbox()
    assert abs(500+(box[0]+box[2])/2-636)<=0.5,(y,box)
record('true horizontal centering','Rasterized ink bounds for Sep/Oct/Jan/Dec and three year titles center at logical x=636 within half a pixel.')

# Trace actual renderer glyph placement without changing its production file.
samples=[('R',27,'1时33分'),('R',27,'阅读 3小时18分钟'),('B',70,'4小时54分钟'),('B',32,'日均 1小时14分钟'),('R',20,'300分'),('R',24,'14% 暂无进度'),('B',44,'2026年10月')]
probe=OUT/'baseline-probe.tsv'
commands=['canvas\tprobe\t1122\t700\tvalidation/baseline-probe.pgm']
for i,(st,sz,msg) in enumerate(samples):commands.append(f'text\tprobe\t{st}\t{sz}\t20\t{i*95+10}\tleft\t0\t{msg}')
commands.append('write\tprobe');probe.write_text('\n'.join(commands)+'\n',encoding='utf-8')
renderer_source=(PKG/'reading-insights-render.lua').read_text(encoding='utf-8')
traced=renderer_source.replace('local function draw_glyph(canvas, glyph, x, y, color)','''local function draw_glyph(canvas, glyph, x, y, color)
    glyph_trace[#glyph_trace+1]={x=x,y=y,by=glyph.bearing_y,bx=glyph.bearing_x,baseline=glyph.baseline}
''')
lua=LuaRuntime(); lua.globals().glyph_trace=lua.table();lua.globals().arg=lua.table_from({1:'native-reading-time-package/render-assets',2:'validation/baseline-probe.tsv'})
lua.execute(traced)
trace=lua.globals().glyph_trace;idx=1
for i,(st,sz,msg) in enumerate(samples):
    baselines=set()
    for ch in msg:
        item=trace[idx];idx+=1;baselines.add(item['y']-item['by'])
    assert len(baselines)==1,(msg,baselines)
assert idx-1==len(trace)
glyph_rows=[x.split('\t') for x in (PKG/'render-assets/dynamic-glyphs.tsv').read_text(encoding='utf-8').splitlines()[1:]]
for sz in {x[1] for x in glyph_rows}:
    group=[x for x in glyph_rows if x[1]==sz]
    assert len({x[10] for x in group})==1
    assert len({(x[12],x[13]) for x in group})==1
Image.open(OUT/'baseline-probe.pgm').save(OUT/'baseline-probe.png')
record('common font baseline','Actual Lua glyph placements in all seven mixed-string probes share one font baseline per string; weights and glyphs share same-size baseline/ascent/descent. Original Noto font preserved.')

# Font-size hierarchy, shared right edge and dynamic headroom in real specs.
spec=render('books-polished','books','progress_loaded=1; book_page=1; render_books')
progress_fields=[l.split('\t') for l in spec.splitlines() if l.startswith('text\tbooks\t') and (l.endswith('暂无进度') or re.search(r'\d+%$',l))]
assert progress_fields and {tuple(f[4:5]+f[6:7]) for f in progress_fields}=={('1090','right')}
for maximum in [0,5,61,73,100,120,246,294,300,999,6000]:
    (session/'months.tsv').write_text(f'2026-09\t{maximum*60}\n')
    p=render(f'chart-{maximum}','total','view_year=2026; render_total; printf "%s %s\\n" "$scale" "$tick_step" > "$SESSION_DIR/chart-scale.tsv"')
    ceiling,step=map(int,(session/'chart-scale.tsv').read_text(encoding='utf-8').split())
    if maximum>=60:assert 1.10<=ceiling/maximum<=1.15,(maximum,ceiling)
    else:assert ceiling==60
    if maximum==294:
        assert ceiling==330
        labels=[l.split('\t')[-1] for l in p.splitlines() if l.startswith('text\tchart\tR\t20')]
        assert labels==['100分','200分','300分']
record('progress column and chart headroom','Known/unknown progress share x=1090/right; 11 chart scales tested. 294min gives 330min ceiling and 100/200/300 ticks; normal maxima get 10–15% headroom.')

# Titles must preserve Latin words at either line boundary, including ellipsis.
title_cases=["Harry Potter and the Philosopher's Stone (English Edition)",
             '中文标题 English Edition 混合阅读记录 Something Else',
             'A practical guide: word-boundaries, punctuation/spacing and hyphen-separated-words',
             'Café français naïve résumé coöperate English Edition',
             'W'*150,
             '标题 Supercalifragilisticexpialidocious'*10]
(session/'title-cases.tsv').write_text(''.join(f'60\t{x}\n' for x in title_cases),encoding='utf-8')
run_shell(setup+'lua "$TITLE_LAYOUT" "$SESSION_DIR/title-cases.tsv" 800 40 0 96 > "$SESSION_DIR/title-result.tsv"')
lines=(session/'title-result.tsv').read_text(encoding='utf-8').splitlines()
by_row={}
for line in lines:
    y,txt=line.split('\t',1);by_row.setdefault(int(y)//96,[]).append(txt)
for i,source in enumerate(title_cases):
    outputs=by_row[i];assert len(outputs)<=2
    source_words=re.findall(r"[A-Za-zÀ-ɏ]+(?:'[A-Za-z]+)?",source)
    for line in outputs:
        words=re.findall(r"[A-Za-zÀ-ɏ]+(?:'[A-Za-z]+)?",line)
        assert all(w in source_words for w in words),(source,line,words)
assert by_row[4]==['…']
assert any('English' in line for line in by_row[0])
assert not any(re.search(r'\bnglish\b',line) for lines in by_row.values() for line in lines)
record('Latin word boundaries','English, Latin-accented, mixed CJK/Latin, punctuation, hyphens and overlong unbroken words tested; no partial words at wrap or ellipsis.')

# Exercise 0/1/3/4/7/10 books over all pages, not just the first three records.
for count in [0,1,3,4,7,10]:
    entries=[(60*(count-i+1),f'Book{i:02} English Edition 阅读记录') for i in range(1,count+1)]
    (session/'day-books.tsv').write_text(''.join(f'2026-09-05\t{sec}\t{title}\n' for sec,title in entries),encoding='utf-8')
    total=sum(v for v,t in entries);(session/'days.tsv').write_text(f'2026-09-05\t{total}\n')
    seen=[];pages=max(1,(count+2)//3)
    for page in range(1,pages+1):
        p=render(f'detail-{count}-page-{page}','daily',f'daily_y=2026; daily_m=9; selected_day=5; detail_page={page}; render_daily 1')
        selected=(session/'daily-view.tsv').read_text(encoding='utf-8').splitlines()
        seen.extend(line.split('\t')[1] for line in selected)
        assert len(selected)<=3
        assert (' / ' in p)==(count>3)
        if count>3:assert f'{page} / {pages}' in p
        if count:
            totals=[l for l in p.splitlines() if l.startswith('text\tdetail\tB\t32')]
            assert len(totals)==1
        old_calendar=(session/'daily-calendar.pgm').read_bytes()
        run_shell(setup+f'cache_ok=1; daily_y=2026; daily_m=9; selected_day=5; detail_page={page}; render_detail_page')
        assert (session/'daily-calendar.pgm').read_bytes()==old_calendar
        assert 'canvas\tcalendar' not in (session/'render-spec.tsv').read_text(encoding='utf-8')
    assert seen==[t for v,t in entries],(count,seen,entries)
    # Entering a day with fewer entries clamps an old page; month shift resets it.
    values=run_shell(setup+f'daily_y=2026; daily_m=9; selected_day=5; detail_page=99; prepare_daily_view; echo "$detail_page $detail_pages $detail_capacity"; shift_month 1; echo "$detail_page $selected_day"')
    assert values.splitlines()==[f'{pages} {pages} 3','1 1']
record('all daily books accessible','0/1/3/4/7/10 entries traversed without loss/duplication; whole-day totals retained, controls only when needed, page clamps and month resets checked; page-only renders leave calendar bytes unchanged.')

# Pager hit tests, including hidden controls and disabled edge actions.
for page,pages in [(1,1),(1,2),(2,2),(2,4)]:
    lua=LuaRuntime();lua.globals().arg=lua.table_from({3:'daily',4:1,5:30,10:pages,11:page,12:1576})
    logical,physical=lua.execute(touch)
    assert logical(460,1600)==('detail_prev' if pages>1 and page>1 else None)
    assert logical(812,1600)==('detail_next' if pages>1 and page<pages else None)
# A Sunday-start leading blank has a valid date at swapped coordinates.
lua=LuaRuntime();lua.globals().arg=lua.table_from({3:'daily',4:6,5:31})
logical,physical=lua.execute(touch)
assert logical(875,500)=='ignore' and logical(500,875).startswith('day_')
assert physical(875,500)=='ignore'
assert 'if action and action ~= "ignore" then finish(action) end' in (PKG/'reading-insights-touch-ui.lua').read_text(encoding='utf-8')
record('blank-cell and pager touch','Leading blank cells/gutters consumed without swapped-coordinate fall-through; pager actions respect visibility and first/last boundaries. Input reader and physical transform otherwise preserved.')

# Restore representative final preview with seven entries and the reported 294min.
entries=[(3357,"Harry Potter and the Philosopher's Stone (English Edition)"),(1344,'55-变身荒野女主播'),(600,'第三本：English Edition 混合书名'),(300,'第四本书'),(180,'第五本书'),(120,'第六本书'),(60,'第七本书')]
(session/'day-books.tsv').write_text(''.join(f'2026-09-05\t{sec}\t{title}\n' for sec,title in entries),encoding='utf-8')
(session/'days.tsv').write_text(f'2026-09-05\t{sum(s for s,t in entries)}\n2026-09-04\t1080\n',encoding='utf-8')
render('daily-final','daily','daily_y=2026; daily_m=9; selected_day=5; detail_page=1; render_daily 1')
render('daily-final-page-3','daily','daily_y=2026; daily_m=9; selected_day=5; detail_page=3; render_daily 1')
(session/'months.tsv').write_text('2026-09\t17640\n');(session/'summary.tsv').write_text('17640\t4\n')
render('total-final','total','view_year=2026; render_total')
