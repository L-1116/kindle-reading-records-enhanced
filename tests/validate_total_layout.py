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
allowed = {'阅读记录-optimized.sh', 'reading-insights-render.lua',
           'reading-insights-touch-ui.lua', 'ui-calendar/total.png'}
for path in PKG.rglob('*'):
    if not path.is_file() or path.relative_to(PKG).as_posix() in allowed:
        continue
    previous = subprocess.check_output(['git', 'show',
        '63e34dba:native-reading-time-package/'+path.relative_to(PKG).as_posix()], cwd=ROOT)
    actual = path.read_bytes()
    if path.name == 'Install-Native-Reading-Time-Optimized.sh':
        actual = actual.replace(b'9.8.1-5.20-vera-test4', b'9.8.1-5.20-vera-test3')
    if path.suffix not in ('.png', '.pgm', '.otf'):
        # Account for Git's Windows checkout line-ending conversion.
        actual, previous = actual.replace(b'\r\n', b'\n'), previous.replace(b'\r\n', b'\n')
    assert actual == previous, path
cleanup = ROOT/'v4/cleanup.sh'
assert cleanup.read_bytes().replace(b'9.8.1-5.20-vera-test4', b'9.8.1-5.20-vera-test3') == subprocess.check_output(['git','show','63e34dba:v4/cleanup.sh'], cwd=ROOT)

old_bg = subprocess.check_output(['git', 'show',
    '63e34dba:native-reading-time-package/ui-calendar/total.png'], cwd=ROOT)
old_bg = Image.open(io.BytesIO(old_bg)).convert('L')
new_bg = Image.open(PKG/'ui-calendar/total.png').convert('L')
diff = ImageChops.difference(old_bg, new_bg).getbbox()
assert diff and diff[0] >= 50 and diff[1] >= 600 and diff[2] <= 1223 and diff[3] <= 1621

# Freeze all shell behavior outside the total rendering block and its refresh
# extents: aggregation, pause/settings handlers, data/config and other pages.
viewer_path = 'native-reading-time-package/阅读记录-optimized.sh'
before = subprocess.check_output(['git', 'show', '63e34dba:'+viewer_path], cwd=ROOT).decode()
after = (ROOT/viewer_path).read_text(encoding='utf-8')
def outside_total(source):
    start = source.index('spec_total_toggle_button()') if 'spec_total_toggle_button()' in source else source.index('spec_period_card()')
    end = source.index('# Reusable on-demand interval aggregation.')
    source = source[:start] + source[end:]
    return '\n'.join(line for line in source.replace('1162 1220','1162 1070').splitlines()
                     if not line.startswith('scenter()'))
assert outside_total(before) == outside_total(after)
touch_path = 'native-reading-time-package/reading-insights-touch-ui.lua'
before = subprocess.check_output(['git', 'show', '63e34dba:'+touch_path], cwd=ROOT).decode()
after = (ROOT/touch_path).read_text(encoding='utf-8')
def outside_total_touch(source):
    start = source.index('    if mode == "total" then')
    end = source.index('    elseif mode == "daily" then', start)
    return source[:start] + source[end:]
assert outside_total_touch(before) == outside_total_touch(after)

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
