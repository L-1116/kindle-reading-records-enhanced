"""Real shell + Lua atlas pixels and touch geometry for the total page.

Importing the existing fixture also runs the statistics/filter regression.
These are offline renders, never a claim of Kindle framebuffer acceptance.
"""
import struct
import subprocess
import tempfile
import io
from PIL import Image, ImageChops, ImageOps
from lupa.lua51 import LuaRuntime, LuaError
from validate_stats_filters import ROOT, PKG, OUT, SESSION, render, touch_source


def ink_box(image, white=False):
    return (image.point(lambda p: 255 if p > 20 else 0)
            if white else ImageOps.invert(image)).getbbox()


def centered(image, box, white=False):
    bounds = ink_box(image.crop(box), white)
    assert bounds, box
    w, h = box[2]-box[0], box[3]-box[1]
    assert abs(bounds[0]+bounds[2]-w) <= 1, (box, bounds, 'horizontal')
    assert abs(bounds[1]+bounds[3]-h) <= 1, (box, bounds, 'vertical')


# Preserve every other shipped payload byte against the accepted test3 source.
allowed = {'reading-config.sh', 'reading-settings.sh', 'ui-calendar/settings.png',
           'ui-calendar/settings_idle.png', 'ui-calendar/settings_cover.png',
           'ui-calendar/settings_custom.png', '阅读记录-optimized.sh', 'reading-insights-render.lua',
           'reading-insights-touch-ui.lua', 'ui-calendar/total.png',
           'reading-power.sh', 'launch.sh', '阅读记录.sh', 'Install-Native-Reading-Time-Optimized.sh',
           'reading-insights-touch-preflight.sh', 'compat/migration.sh',
           'reading-custom-covers.sh','reading-custom-covers.lua','cover-image',
           'install-manifest.txt','ui-calendar/settings_cover_manage.png',
           'ui-calendar/settings_cover_images.png','ui-calendar/settings_cover_books.png',
           'ui-calendar/settings_cover_info.png','ui-calendar/settings_cover_picker.png'}
for path in PKG.rglob('*'):
    if not path.is_file() or path.relative_to(PKG).as_posix() in allowed:
        continue
    previous = subprocess.check_output(['git', 'show',
        '63e34dba:native-reading-time-package/'+path.relative_to(PKG).as_posix()], cwd=ROOT)
    actual = path.read_bytes()
    if path.name == 'Install-Native-Reading-Time-Optimized.sh':
        actual = actual.replace(b'9.8.1-5.20-vera-test6', b'9.8.1-5.20-vera-test3')
    if path.suffix not in ('.png', '.pgm', '.otf'):
        # Account for Git's Windows checkout line-ending conversion.
        actual, previous = actual.replace(b'\r\n', b'\n'), previous.replace(b'\r\n', b'\n')
    assert actual == previous, path
cleanup = ROOT/'v4/cleanup.sh'
assert cleanup.read_bytes().replace(b'9.8.1-5.20-vera-test8', b'9.8.1-5.20-vera-test3').replace(b'reading-records-v4-install.sh', b'reading-records-9.8.1-install.sh') == subprocess.check_output(['git','show','63e34dba:v4/cleanup.sh'], cwd=ROOT)

old_bg = subprocess.check_output(['git', 'show',
    '63e34dba:native-reading-time-package/ui-calendar/total.png'], cwd=ROOT)
old_bg = Image.open(io.BytesIO(old_bg)).convert('L')
new_bg = Image.open(PKG/'ui-calendar/total.png').convert('L')
diff = ImageChops.difference(old_bg, new_bg).getbbox()
assert diff and diff[0] >= 50 and diff[1] >= 600 and diff[2] <= 1223 and diff[3] <= 1621

# Preserve the accepted test4 rendering, aggregation and action handlers.
# Frontend startup/cleanup and interruptible waits have their own power tests.
viewer_path = 'native-reading-time-package/阅读记录-optimized.sh'
before = subprocess.check_output(['git', 'show', 'f9cb13d9:'+viewer_path], cwd=ROOT).decode()
after = (ROOT/viewer_path).read_text(encoding='utf-8')
def preserved_shell(source):
    # Isolate the cover implementation and its initialization. Statistics,
    # renderer, drawing and navigation below remain byte-identical.
    a=source.index('cover_path_allowed() {'); b=source.index('render_cover_placeholder() {',a)
    source=source[:a]+source[b:]
    source=source.replace('    . "$SETTINGS_HELPERS/reading-custom-covers.sh" || exit 1\n    rr_cover_init\n    rr_config_read\n','')
    # Full settings navigation redraws the calendar month title on return.
    source = source.replace('perform_draw settings_change 1 1 0 0 1272 1696',
                            'perform_draw settings_change 1 0 0 0 1272 1696')
    # test8 intentionally changes only these book controls and weekday glyphs.
    source=source.replace('    scenter "$toggle_canvas" B 28 $((toggle_x+toggle_w/2)) 29 "$toggle_ink" "$toggle_text"', '    stext "$toggle_canvas" B 28 $((toggle_x+toggle_w/2)) 10 center "$toggle_ink" "$toggle_text"')
    source=source.replace('        if [ "$total_period" = week ]; then stext chart R 28 "$center" 650 center 0 "$axis_label"\n        else stext chart B "$axis_size" "$center" 650 center 0 "$axis_label"; fi', '        stext chart B "$axis_size" "$center" 650 center 0 "$axis_label"')
    source=source.replace('canvas page 452 100 "$b"; scenter page B 30 226 50 0 "第 ${book_page} 页，共 ${pages} 页"; srect page 64 78 324 1 96', 'canvas page 452 60 "$b"; stext page B 30 226 10 center 0 "第 ${book_page} 页，共 ${pages} 页"')
    source=source.replace('pgm_valid "$b" 452 100','pgm_valid "$b" 452 60').replace('1493 452 100','1480 452 60')
    source=source.replace('book_filter_change 0 0 55 285 1162 1310','book_filter_change 0 0 55 285 1162 1275')
    source=source.replace('book_page_previous 0 0 70 345 1132 1250','book_page_previous 0 0 70 345 1132 1215')
    source=source.replace('book_page_next 0 0 70 345 1132 1250','book_page_next 0 0 70 345 1132 1215')
    source=source.replace('      page_jump) rr_pager_open books "$(book_pages)" "$book_page"; [ "$mode" != settings_cover_picker ] || perform_draw page_picker_open 1 1 0 0 1272 1696;;\n','')
    return (source[:source.index('\ndashboard_active=0;')] +
            source[source.index('\nperform_draw()'):source.index('\nrr_perf geometry_begin')] +
            source[source.index('    standard_touch_action_received\n'):])
assert preserved_shell(before) == preserved_shell(after)
touch_path = 'native-reading-time-package/reading-insights-touch-ui.lua'
before = subprocess.check_output(['git', 'show', '63e34dba:'+touch_path], cwd=ROOT).decode()
after = (ROOT/touch_path).read_text(encoding='utf-8')
def outside_total_touch(source):
    start = source.index('    if mode == "total" then')
    end = source.index('    elseif mode == "daily" then', start)
    prefix = source[:start]
    a = prefix.index('local function settings_action(')
    b = prefix.index('local function action_for_logical(', a)
    result=prefix[:a] + prefix[b:] + source[end:]
    return result.replace('        if inside(px, py, 410, 1493, 862, 1593) then return "page_jump" end\n','')
assert outside_total_touch(before) == outside_total_touch(after)

# Actual glyph-mask centering for all four filters and the underlined pager.
filters=Image.open(SESSION/'books-filters.pgm').convert('L')
for x,w,selected in ((0,263,True),(290,263,False),(580,263,False),(870,262,False)):
    centered(filters,(x+20,8,x+2*(w//2)-20,50),selected)
page=Image.open(SESSION/'books-page.pgm').convert('L')
assert page.size==(452,100)
centered(page,(0,22,452,78))
assert all(page.getpixel((x,78))==96 for x in range(64,388))
# Use the visible button glyphs, whose center differs from the broad touch box.
background=Image.open(PKG/'ui-calendar/books.png').convert('L')
for box in ((140,1510,350,1576),(940,1510,1140,1576)):
    bounds=background.crop(box).point(lambda p:255 if p<80 else 0).getbbox()
    assert abs((bounds[1]+bounds[3])/2+box[1]-(1493+50))<=1
assert '1493\t452\t100' in (SESSION/'draw.tsv').read_text(encoding='utf-8')
assert 'book_page_next 0 0 70 345 1132 1250' in (PKG/'阅读记录-optimized.sh').read_text(encoding='utf-8')


# Keep chart geometry intact while checking every selected/unselected control.
specs = []
for period in ('week', 'year', 'all'):
    spec = render('test4-total-'+period, 'total',
                  f'total_period={period}; view_year=2026; week_offset=0; render_total')
    preview = OUT/('test4-total-'+period+'.png')
    page = Image.open(preview).convert('L')
    page.paste(Image.open(PKG/'ui-calendar/settings-button.png'), (1006,54))
    page.save(preview)
    specs.append(spec)
    labels=[line.split('\t') for line in spec.splitlines() if line.startswith('text\tchart\t') and line.endswith(tuple('周'+d for d in '一二三四五六日'))]
    if period=='week':assert len(labels)==7 and all(row[2:4]==['R','28'] for row in labels)
    toggle = Image.open(SESSION/'total-toggle.pgm').convert('L')
    assert toggle.size == (1122, 88)
    for i, selected in enumerate(('week', 'year', 'all')):
        x = i*382
        centered(toggle, (x+12, 12, x+346, 76), period == selected)
    nav = Image.open(SESSION/'total-period.pgm').convert('L')
    assert nav.size == (1122, 84)
    centered(nav, (352, 0, 770, 84))
    if period != 'all':
        for x in (225, 785):
            centered(nav, (x+10, 10, x+102, 74))
    else:
        assert not ink_box(nav.crop((225, 0, 337, 84)))
        assert not ink_box(nav.crop((785, 0, 897, 84)))
    chart = Image.open(SESSION/'total-chart.pgm').convert('L')
    assert chart.size == (1122, 690)
    bounds = ink_box(chart)
    assert bounds[0] > 0 and bounds[1] > 0 and bounds[2] < 1122 and bounds[3] < 690, bounds
    # Moving down must preserve every chart pixel for an identical spec/data.
    previous = subprocess.check_output(['git', 'show',
        '63e34dba:native-reading-time-package/reading-insights-render.lua'], cwd=ROOT).decode()
    old_spec = '\n'.join(line for line in spec.splitlines()
                         if line.split('\t')[1] == 'chart')
    ref = OUT/'test4-chart-reference.pgm'
    old_spec = old_spec.replace(str(SESSION/'total-chart.pgm.new').replace('\\', '/'), ref.as_posix())
    # Specifications use relative paths in the shared fixture.
    old_spec = old_spec.replace('build/validation/stats-session/total-chart.pgm.new', ref.as_posix())
    path = OUT/'test4-chart-reference.tsv'; path.write_text(old_spec, encoding='utf-8')
    lua = LuaRuntime(); lua.globals().arg = lua.table_from({1:(PKG/'render-assets').as_posix(), 2:path.as_posix()})
    lua.execute(previous)
    assert ref.read_bytes() == (SESSION/'total-chart.pgm').read_bytes(), period

# Exercise variable date widths and mixed numeral/CJK bearings with exact pixels.
renderer = (PKG/'reading-insights-render.lua').read_text(encoding='utf-8')
for title in ('1月1日 - 1月7日', '11月23日 - 11月29日',
              '12月29日 - 1月4日', '2000年', '2026年', '全部历史'):
    size = 30 if '日' in title else 39
    path = OUT/'test4-center.tsv'; output = OUT/'test4-center.pgm'
    path.write_text(f'canvas\tprobe\t1122\t84\t{output.as_posix()}\n'
                    f'textcenter\tprobe\tB\t{size}\t561\t42\t0\t{title}\nwrite\tprobe\n', encoding='utf-8')
    lua = LuaRuntime(); lua.globals().arg = lua.table_from({1:(PKG/'render-assets').as_posix(), 2:path.as_posix()})
    lua.execute(renderer)
    centered(Image.open(output).convert('L'), (0, 0, 1122, 84))

# Test corners, centers, gutters and scaled viewports from the shipped hit map.
cases = []
for action, box in [('total_week',(75,650,432,737)), ('total_year',(457,650,814,737)),
                    ('total_all',(839,650,1196,737)), ('total_prev',(300,762,411,845)),
                    ('total_next',(860,762,971,845))]:
    x,y,r,b = box
    cases += [((x,y),action), ((r,b),action), (((x+r)//2,(y+b)//2),action)]
cases += [((x,y),None) for x,y in ((74,694),(433,694),(456,694),(815,694),(838,694),
                                  (1197,694),(636,738),(356,761),(356,846),(636,804),
                                  (131,804),(1141,804),(299,804),(412,804),
                                  (859,804),(972,804))]
cases += [((1100,90),'settings_open'), ((600,450),'week_trend_open')]
count = 0
for period in ('week','year','all'):
    for w,h,ox,oy in ((1272,1696,0,0),(1264,1685,0,0),(900,1200,20,40),(600,800,0,0)):
        lua = LuaRuntime(); lua.globals().arg = lua.table_from({3:'total',13:period,6:ox,7:oy,8:w,9:h})
        logical,physical = lua.execute(touch_source.replace('return action_for_logical', 'return action_for_logical, action_for_physical'))
        for (x,y), action in cases:
            expected = None if period=='all' and action in ('total_prev','total_next') else action
            if action=='week_trend_open' and period!='week': expected=None
            assert logical(x,y)==expected, (period,x,y,expected)
            # Physical mapping is verified at centers; rounded edge coordinates
            # can legitimately quantize to the adjacent logical pixel.
            if action:
                assert physical(ox+x*w/1272,oy+y*h/1696)==expected, (period,w,x,y)
            count += 1

# Real evdev decoding, using both event struct sizes and every control/mode.
with tempfile.TemporaryDirectory(prefix='total-evdev-') as tmp:
    from pathlib import Path
    root = Path(tmp)
    for period in ('week','year','all'):
        for size in (16,24):
            for (x,y),action in cases[:15]:
                expected = '' if period=='all' and action in ('total_prev','total_next') else action
                dev=root/'input'; dev.write_bytes(b''.join(bytes(size-8)+struct.pack('<HHi',*e)
                    for e in ((3,53,x),(3,54,y),(0,0,0))))
                args=[dev.as_posix(),(root/'log').as_posix(),'total',0,31,0,0,1272,1696,1,1,1576,
                      period,'7d','direct',size,1272,1696,(root/'report').as_posix(),'unknown','unknown','unknown','unknown']
                lua=LuaRuntime(); lua.globals().arg=lua.table_from({i+1:str(v) for i,v in enumerate(args)})
                outputs=[]; lua.globals().capture=lambda *v:outputs.append(''.join(map(str,v)))
                lua.execute('io.write=capture; io.stderr={write=function() end}; os.exit=function(n) error("TEST_EXIT:"..n) end')
                try: lua.execute((PKG/'reading-insights-touch-ui.lua').read_text(encoding='utf-8'))
                except LuaError as e: assert f'TEST_EXIT:{0 if expected else 2}' in str(e), str(e)
                assert ''.join(outputs).strip()==expected, (period,size,x,y,outputs)
                lua.execute('collectgarbage("collect")')
                count += 1
print(f'PASS: total page pixel centering, unchanged charts/core, three modes, six date titles and {count} touch checks.')
