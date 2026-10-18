"""Execute production C decoder, Lua store, shell actions/resolver and evdev hitboxes.
Windows uses the same C source in a host executable; ARM framebuffer, touch and
sleep acceptance remain pending on Kindle. No simulated hardware claim.
"""
from pathlib import Path
import io, os, shlex, shutil, sqlite3, struct, subprocess, sys, tempfile, time
from PIL import Image, ImageDraw, ImageFont
from lupa.lua51 import LuaRuntime, LuaError

ROOT=Path(__file__).resolve().parents[1]; PKG=ROOT/'native-reading-time-package'
OUT=ROOT/'build/validation/custom-covers';OUT.mkdir(parents=True,exist_ok=True)
SH=shutil.which('sh') or 'C:/Program Files/Git/usr/bin/sh.exe'
NATIVE=ROOT/('build/cover-image-host.exe' if os.name=='nt' else 'build/cover-image-host')
q=lambda p:shlex.quote(str(p).replace('\\','/'))
if not NATIVE.exists() and os.name!='nt':
    cc=shutil.which('cc') or shutil.which('clang')
    assert cc,'A host C compiler is required for the offline decoder checks'
    subprocess.run([cc,'-std=c99','-Os','native/custom-cover/cover-image.c','-lm','-o',str(NATIVE)],cwd=ROOT,check=True)
assert NATIVE.is_file(),'Run scripts/build_cover_helper.py first'

with tempfile.TemporaryDirectory(prefix='covers-',dir=OUT) as tmp:
    root=Path(tmp);base=root/'reading-time';images=base/'custom-covers';cache=base/'custom-cover-previews'
    images.mkdir(parents=True);cache.mkdir();session=root/'session';session.mkdir()
    def native(*args,ok=True):
        p=subprocess.run([str(NATIVE),*map(str,args)],capture_output=True,encoding='utf-8',timeout=10)
        assert (p.returncode==0)==ok,(args,p.returncode,p.stdout,p.stderr)
        return p.stdout.strip()
    assert native('scan',images)==''
    names=['01 中文 封面.jpg','02 landscape.PNG','03 portrait.jpeg','04 alpha.png','05,a=b.png','06 图片 六.png','07 '+('很长的文件名'*9)+'.jpg']
    for i,name in enumerate(names):Image.new('RGB',(400,600),(40+i*20,)*3).save(images/name)
    Image.new('RGB',(600,300),(60,)*3).save(images/names[1])
    Image.new('RGBA',(100,100),(0,0,0,0)).save(images/names[3])
    (images/'empty.jpg').write_bytes(b'');(images/'bad.png').write_bytes(b'not a picture')
    (images/'fake.jpg').write_text('PNG',encoding='utf-8')
    Image.new('RGB',(40,60)).save(images/'unsupported.gif')
    (images/'truncated.jpg').write_bytes((images/names[0]).read_bytes()[:-10])
    Image.new('L',(8193,1)).save(images/'too-wide.png')
    Image.new('L',(4096,4096)).save(images/'too-many-pixels.png')
    with (images/'too-large.jpg').open('wb') as f:f.truncate(8*1024*1024+1)
    found=native('scan',images).splitlines();assert set(found)==set(names),found
    for name in ['empty.jpg','bad.png','fake.jpg','truncated.jpg','unsupported.gif','too-wide.png','too-many-pixels.png','too-large.jpg','../outside.png','/outside.jpg']:
        native('prepare',images,name,cache,ok=False)
    # Path safety: reject a linked directory and a symlinked image, including
    # Windows junction fallback when file-symlink privilege is unavailable.
    linked=root/'linked-images'
    if os.name=='nt':
        subprocess.run(['cmd','/c','mklink','/J',str(linked),str(images)],check=True,capture_output=True)
    else:linked.symlink_to(images,target_is_directory=True)
    native('scan',linked,ok=False);native('prepare',linked,names[0],cache,ok=False)
    try:
        (images/'outside.jpg').symlink_to(images/names[0])
    except OSError:
        pass # Windows lacks file symlink privilege; Linux openat uses O_NOFOLLOW.
    else:
        native('prepare',images,'outside.jpg',cache,ok=False)
        assert 'outside.jpg' not in native('scan',images).splitlines()
    first=Path(native('prepare',images,names[0],cache));before=first.stat().st_mtime_ns
    assert Image.open(first).size==(240,360)
    assert Path(native('prepare',images,names[0],cache))==first and first.stat().st_mtime_ns==before
    landscape=Image.open(native('prepare',images,names[1],cache)).convert('L')
    assert landscape.getpixel((120,0))==255 and landscape.getpixel((120,180))==60
    alpha=Image.open(native('prepare',images,names[3],cache));assert alpha.getextrema()==(255,255);alpha.close()
    first.write_bytes(b'broken cache');native('prepare',images,names[0],cache);assert Image.open(first).size==(240,360)
    # Same size and mtime replacement is detected by content, not a stale stat key.
    stat=(images/names[0]).stat();Image.new('RGB',(400,600),(179,)*3).save(images/names[0]);os.utime(images/names[0],ns=(stat.st_atime_ns,stat.st_mtime_ns))
    assert Path(native('prepare',images,names[0],cache))!=first

    runner=root/'lua.py'
    runner.write_text('''from pathlib import Path
import os,sys
from lupa.lua51 import LuaRuntime
lua=LuaRuntime()
lua.globals().arg=lua.table_from({i:v for i,v in enumerate(sys.argv[1:])})
# Lua's Windows CRT rename cannot replace a destination; emulate the POSIX
# rename used by the exact device program, without changing the Lua source.
lua.globals().replace=lambda a,b: os.replace(a,b) or True
lua.execute('os.rename=replace')
lua.execute(Path(sys.argv[1]).read_text(encoding='utf-8'))
''',encoding='utf-8')
    history=base/'reading-time.tsv'
    history.write_text('date\tbook_id\tseconds\ttitle\n2026-10-01\tid-a\t30\t同名书\n2026-10-02\tid-b\t300\t同名书\n2026-10-03\tunknown\t20\t已卸载的 无 ID 书籍\n2026-10-04\t\t10\t无 ID 第二本\n2026-10-05\tgeneric\t99\t真实 ID generic\n',encoding='utf-8')
    original_history=history.read_bytes()
    conf=base/'user.conf';conf.write_text('idle_pause_enabled=1\nidle_pause_minutes=1440\nfuture=opaque value\ncustom_cover_enabled=0\n',encoding='utf-8')
    original_conf=conf.read_bytes()
    src=(PKG/'阅读记录-optimized.sh').read_text(encoding='utf-8')
    definitions=src[:src.index('\ndetect_screen; find_touch_device')]
    definitions=definitions.replace('. "$RELEASE/bin/reading-power.sh" || exit 1\nrr_power_init\n','').replace('\ntrap cleanup EXIT\n','\n')
    definitions=definitions.replace('if [ "${READING_LAUNCHER_CAPTURE:-0}" != 1 ]; then exec >> "$LOG" 2>&1; fi','').replace('echo "$(date): optimized dashboard launch, uid=$(id -u), pid=$$"','')
    functions=root/'functions.sh';functions.write_text(definitions,encoding='utf-8',newline='\n')
    head=f'''
export PATH="/usr/bin:/bin:$PATH"
. {q(functions)}
BASE={q(base)}; SESSION_DIR={q(session)}; SETTINGS_HELPERS={q(PKG)}; SETTINGS_ASSETS={q(PKG/'ui-calendar')}; RENDER_ASSETS={q(PKG/'render-assets')}
lua() {{ {q(sys.executable)} {q(runner)} "$@"; }}
. "$SETTINGS_HELPERS/reading-config.sh"
. "$SETTINGS_HELPERS/reading-settings.sh"
. "$SETTINGS_HELPERS/reading-custom-covers.sh"
rr_cover_init; rr_config_read
COVER_IMAGE_HELPER={q(NATIVE)}
act() {{ action="$1"; rr_settings_action; }}
'''
    def shell(code):
        p=subprocess.run([SH],input=head+code,cwd=ROOT,text=True,encoding='utf-8',capture_output=True,timeout=45)
        assert p.returncode==0,(p.returncode,p.stdout,p.stderr,code)
        return p.stdout.strip()
    assert shell('rr_cover_history; cat "$SESSION_DIR/custom-books.tsv"').count('book:')==5
    # The page query retains exact IDs and escapes quoted IDs/titles. No
    # optional location column or full progress snapshot is required.
    page_input=session/'query-page.tsv'
    page_input.write_text("book:id-a\t同名书\nbook:\t无 ID 第二本\nbook:x' OR 1=1 --\tquoted\nbook:unknown\tO'Brien.epub\n",encoding='utf-8')
    query=shell('rr_cover_cmd catalog-query '+q(page_input))
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE Entries(p_titles_0_nominal,p_cdeKey,p_thumbnail,p_lastAccess)')
        db.executemany('INSERT INTO Entries VALUES (?,?,?,?)',[
            ('同名书','id-a','a.jpg',1),('同名书','id-b','b.jpg',2),
            ('无 ID 第二本',None,'none.jpg',3),("quoted","x' OR 1=1 --",'q.jpg',4),
            ("O'Brien",'unknown','title.jpg',5),('not requested','other','other.jpg',6)])
        result=db.execute(query).fetchall()
        assert {row[3] for row in result}=={'a.jpg','none.jpg','q.jpg','title.jpg'},result
    page_input.write_text('book:ABCDEF0123456789\tABCDEF0123456789\n',encoding='utf-8')
    hidden=shell('rr_cover_cmd cards '+q(page_input)).split('\t')
    assert hidden[:2]==['book:ABCDEF0123456789','title:ABCDEF0123456789']
    assert hidden[3]=='line:未知书籍',hidden
    assert shell('rr_cover_scan; echo "$cover_count"')=='7'
    # Navigation, confirmation, returning without selection, page bounds,
    # atomic save failures and independent special/empty/unknown identities.
    shell('''
mode=settings; act settings_cover; act settings_cover_generic
test "$mode" = settings_cover_manage || exit 1
act settings_cover_choose; test "$mode $cover_page $cover_count" = 'settings_cover_images 1 7' || exit 2
act settings_cover_next; test "$cover_page" = 2 || exit 3
act settings_cover_next; test "$cover_page" = 2 || exit 4
act settings_cover_prev; act settings_cover_item_1
test "$mode" = settings_cover_manage && test -n "$(rr_cover_current)" || exit 5
act settings_cover_choose; act settings_cover_back
test "$mode" = settings_cover_manage || exit 6
act settings_cover_back; test "$mode" = settings_cover || exit 7
act settings_cover_books; test "$cover_book_count" = 5 || exit 8
act settings_cover_item_1; test "$mode $cover_target_kind" = 'settings_cover_manage book' || exit 9
act settings_cover_choose; act settings_cover_back; act settings_cover_back
test "$mode $cover_book_page" = 'settings_cover_books 1' || exit 10
cover_target_kind=book; cover_target_id=id-a; cover_target_title=同名书
rr_cover_save '03 portrait.jpeg' || exit 11
cover_target_id=id-b; rr_cover_save '04 alpha.png' || exit 12
cover_target_id=unknown; cover_target_title='已卸载的 无 ID 书籍'; rr_cover_save '05,a=b.png' || exit 13
cover_target_id=generic; cover_target_title='真实 ID generic'; rr_cover_save '06 图片 六.png' || exit 14
rr_cover_save '../bad.png' && exit 15
mkdir "$BASE/.custom-cover-save.$$"; rr_cover_save '03 portrait.jpeg' && exit 16
rmdir "$BASE/.custom-cover-save.$$"
exit 0
''')
    assert conf.read_bytes()==original_conf and history.read_bytes()==original_history
    state=base/'custom-cover-associations.tsv';saved=state.read_bytes()
    assert shell('rr_cover_cmd get id-a 同名书')=='03 portrait.jpeg'
    assert shell('rr_cover_cmd get id-b 同名书')=='04 alpha.png'
    assert shell("rr_cover_cmd get unknown '已卸载的 无 ID 书籍'")=='05,a=b.png'
    assert shell('rr_cover_cmd generic')=='01 中文 封面.jpg'
    assert shell("rr_cover_cmd get generic '真实 ID generic'")=='06 图片 六.png'
    assert shell('rr_cover_cmd count')=='4'
    # Empty historical identities retain their raw fallback key, while the UI
    # supplies a readable label. Ten records per page, with four on the last.
    with history.open('a',encoding='utf-8') as f:
        f.write('2026-10-06\tunknown\t12\t\n')
        for i in range(8):f.write(f'2026-10-07\textra-{i}\t10\t第 {i} 本 '+('很长的历史书名 '*8)+'\n')
    shell('''
rr_cover_history;test "$cover_book_count" = 14 || exit 1
mode=settings_cover_books;act settings_cover_next;act settings_cover_next;act settings_cover_next
test "$cover_book_page" = 2 || exit 2
act settings_cover_item_6;test "$mode" = settings_cover_books || exit 3
act settings_cover_prev;act settings_cover_item_1
test "$mode $cover_manage_return" = 'settings_cover_manage settings_cover_books' || exit 4
act settings_cover_back;test "$cover_book_page" = 1 || exit 5
cover_target_kind=book;cover_target_id=unknown;cover_target_title=''
rr_cover_save '06 图片 六.png' || exit 6
test "$(rr_cover_cmd get unknown '')" = '06 图片 六.png' || exit 7
test "$(rr_cover_cmd get unknown unknown)" = '06 图片 六.png' || exit 9
test "$(rr_cover_cmd get unknown 0123456789ABCDEF)" = '06 图片 六.png' || exit 10
rr_cover_save '' || exit 8
''')
    history.write_bytes(original_history)
    assert state.read_bytes()==saved
    # All three UI call sites use this resolver. Corrupt real image must fall
    # through to a valid catalog image, then exclusive, generic and placeholder.
    real=base/'book-covers';real.mkdir();good=real/'real.jpg';bad=real/'bad.jpg'
    Image.new('RGB',(200,300),(23,)*3).save(good);bad.write_bytes(b'broken JPEG')
    setup=f'''
COVER_CACHE={q(base/'book-cover-cache.tsv')}; COVER_CACHE_DIR={q(real)}; COVER_MISS_CACHE={q(base/'misses.tsv')}; CATALOG={q(session/'catalog.tsv')}; catalog_loaded=1
cover_path_allowed() {{ case "$1" in "$COVER_CACHE_DIR"/*) [ -s "$1" ];; *) return 1;; esac; }}
book_path_allowed() {{ return 1; }}
custom_cover_enabled=1
'''
    def resolve(code):return shell(setup+code)
    shell("cover_target_kind=book;cover_target_id=unknown;cover_target_title='';rr_cover_save '06 图片 六.png'")
    assert Image.open(resolve('resolveBookCover unknown unknown')).getpixel((120,180))==140
    shell("cover_target_kind=book;cover_target_id=unknown;cover_target_title='';rr_cover_save ''")
    assert state.read_bytes()==saved
    assert resolve(f"printf 'id-a\\t%s\\n' {q(good)} > \"$COVER_CACHE\"; resolveBookCover id-a 同名书")==good.as_posix()
    actual=resolve('image() { printf "%s\\n" "$1"; };renderBookCover id-a 同名书 90 300 190 285')
    assert Image.open(actual).getpixel((120,180))==23
    assert resolve(f"printf 'id-a\\t%s\\n' {q(bad)} > \"$COVER_CACHE\"; resolveBookCover id-a 同名书").endswith('.pgm')
    # Identify which source is used by its decoded pixel, not a mocked status.
    def pixel(book):
        p=resolve(f'rm -f "$COVER_CACHE" "$CATALOG"; resolveBookCover {book} 同名书')
        return Image.open(p).getpixel((120,180))
    assert pixel('id-a')==80 and pixel('id-b')==255 and pixel('other')==179
    assert resolve('custom_cover_enabled=0; rm -f "$COVER_CACHE"; resolveBookCover id-a 同名书 || echo PLACEHOLDER')=='PLACEHOLDER'
    assert state.read_bytes()==saved
    assert pixel('id-a')==80 # Re-enabling restores prior choices, across processes.
    # Status uses the same real resolver but must not unpack any source book.
    status_setup='''
extract_embedded_cover() { echo UNEXPECTED_EXTRACTION >&2; exit 70; }
rr_generic="$(rr_cover_cmd generic)"; rr_generic_checked=0; rr_generic_valid=0
status() { rr_cover_status "$@"; printf '%s\\n' "$rr_status"; }
'''
    def status(code):return resolve(status_setup+code)
    assert status('status id-a 同名书 "03 portrait.jpeg"')=='专属封面'
    assert status('status other 同名书 ""')=='通用封面'
    assert status('custom_cover_enabled=0; status id-a 同名书 "03 portrait.jpeg"')=='暂无封面 · 专属未启用'
    assert status('custom_cover_enabled=0; status other 同名书 ""')=='暂无封面'
    assert status(f'printf "id-a\\t%s\\n" {q(good)} > "$COVER_CACHE"; status id-a 同名书 "03 portrait.jpeg"')=='原始封面 · 已设专属'
    assert status('custom_cover_enabled=0; status id-a 同名书 "03 portrait.jpeg"')=='原始封面 · 专属未启用'
    # A broken cache entry must not hide another decodable native thumbnail.
    assert resolve(f'''printf 'id-a\\t%s\\n' {q(bad)} > "$COVER_CACHE"
printf '0\\t同名书\\tid-a\\t%s\\tfile://missing\\n0\\t同名书\\tid-a\\t%s\\t\\n' {q(bad)} {q(good)} > "$CATALOG"
resolveBookCover id-a 同名书''')==good.as_posix()
    (images/'03 portrait.jpeg').unlink();assert pixel('id-a')==179
    (images/names[0]).write_bytes(b'damaged');assert resolve('resolveBookCover id-a 同名书 || echo PLACEHOLDER')=='PLACEHOLDER'
    assert status('status id-a 同名书 "03 portrait.jpeg"')=='暂无封面'
    assert history.read_bytes()==original_history and conf.read_bytes()==original_conf
    assert b'custom-cover' not in (base/'book-cover-cache.tsv').read_bytes() if (base/'book-cover-cache.tsv').exists() else True
    # Restore for previews and exercise deletion/rescan, generic clear, specific
    # clear and a history page, without changing historical bytes.
    Image.new('RGB',(400,600),(179,)*3).save(images/names[0])
    assert shell('rr_cover_scan; echo "$cover_count"')=='6'
    shell('cover_target_kind=book; cover_target_id=id-b; cover_target_title=同名书; rr_cover_save ""')
    assert pixel('id-b')==179
    # One state machine serves both lists: no-op single page, group navigation,
    # last partial group, invalid/out-of-group selection and cancellation.
    shell('''
mode=books;rr_pager_open books 1 1;test "$mode" = books || exit 1
for context in books settings_cover_books; do
    mode=$context;rr_pager_open "$context" 50 8
    test "$mode $RR_PAGER_START" = 'settings_cover_picker 1' || exit 2
    act settings_cover_pager_pick_50;test "$mode" = settings_cover_picker || exit 3
    act settings_cover_pager_next;act settings_cover_pager_next;act settings_cover_pager_next
    test "$RR_PAGER_START" = 41 || exit 4
    act settings_cover_pager_pick_51;test "$mode" = settings_cover_picker || exit 5
    act settings_cover_pager_pick_50;test "$mode" = "$context" || exit 6
    if [ "$context" = books ]; then test "$book_page" = 50 || exit 7
    else test "$cover_book_page" = 50 || exit 8; fi
    rr_pager_open "$context" 50 50;act settings_cover_pager_prev
    test "$RR_PAGER_START" = 21 || exit 9
    act settings_cover_pager_back;test "$mode" = "$context" || exit 10
done
''')
    # A 503-book history inspects exactly the current ten, then only the last
    # three. Neither history reload, full catalog initialization nor extraction
    # is permitted while rendering or paging.
    with history.open('a',encoding='utf-8') as f:
        for i in range(498):f.write(f'2026-10-07\tlarge-{i:03d}\t10\t第 {i:03d} 本 '+('很长的中文书籍标题'*9)+'\n')
    shell('''
rr_cover_history;test "$cover_book_count" = 503 || exit 1
ensure_catalog() { exit 91; };extract_embedded_cover() { exit 92; }
resolveOriginalBookCover() { printf '%s\\n' "$1" >> "$SESSION_DIR/checked";return 1; }
ot() { :; };rr_pager_render() { :; }
custom_cover_enabled=0;mode=settings_cover_books
rr_cover_draw_books;test "$(wc -l < "$SESSION_DIR/checked")" = 10 || exit 2
test "$(wc -l < "$SESSION_DIR/custom-cards.tsv")" = 10 || exit 3
rr_pager_open settings_cover_books 51 1
act settings_cover_pager_next;act settings_cover_pager_next;act settings_cover_pager_pick_51
rr_cover_draw_books;test "$(wc -l < "$SESSION_DIR/checked")" = 13 || exit 4
test "$(wc -l < "$SESSION_DIR/custom-cards.tsv")" = 3 || exit 5
test "$cover_book_page" = 51 || exit 6
act settings_cover_item_4;test "$mode" = settings_cover_books || exit 7
act settings_cover_item_3;test "$mode" = settings_cover_manage || exit 8
test "book:$cover_target_id" = "$(sed -n '503p' "$SESSION_DIR/custom-books.tsv" | cut -f1)" || exit 9
# Returning through cover management to image selection cannot inherit the
# history loop's row counter and draw previews below the screen.
mode=settings_cover_images;rr_cover_scan
rr_cover_preview() { test "$3" -lt 1300 || exit 72; }
rr_cover_text() { test "$2" -lt 1300 || exit 73; }
rr_cover_current() { :; }
rr_cover_draw
''')
    history.write_bytes(original_history)
    # Log real FBInk argv from production OT and cover drawing functions.
    drawhead='''
scale_len() { echo "$1"; }; scale_x() { echo "$1"; }; scale_y() { echo "$1"; }; scale_right() { echo "$1"; }
fb() { printf 'fb'; printf '\\t%s' "$@"; printf '\\n'; }
'''+f'RFONT={q(PKG/"NotoSansCJKsc-Regular.otf")}\n'
    # Render ten long-title cards and the modal through the production renderer.
    with history.open('a',encoding='utf-8') as f:
        for i in range(8):f.write(f'2026-10-07\tlong-{i}\t10\t'+('长中文书名 Mixed Title '*12)+'\n')
    for mode in ('settings_cover','settings_cover_manage','settings_cover_images','settings_cover_books','settings_cover_info','settings_cover_picker'):
        output=shell(drawhead+f'''
rr_cover_scan; rr_cover_history
cover_target_kind=generic; cover_target_title='通用替代封面'
custom_cover_enabled=1;mode={mode}
[ "$mode" != settings_cover_picker ] || rr_pager_open books 50 8
rr_settings_draw
''')
        im=Image.open(PKG/f'ui-calendar/{mode}.png').convert('L');d=ImageDraw.Draw(im)
        for line in output.splitlines():
            args=line.split('\t')[1:]
            if not args:continue
            option='-g' if '-g' in args else '-t';params=dict(s.split('=',1) for s in args[args.index(option)+1].split(','))
            if option=='-g':
                x,y,w,h=[int(params[k]) for k in ('x','y','w','h')]
                assert 0<=x<=1272-w and 0<=y<=1696-h
                im.paste(Image.open(params['file']).convert('L').resize((w,h)),(x,y))
            else:
                size,x,y,right=[int(params[k]) for k in ('px','left','top','right')]
                f=ImageFont.truetype(params['regular'],size);box=d.textbbox((x,y),args[-1],font=f)
                assert box[2]<=1272-right and box[3]<1696,(mode,args[-1],box,right)
                d.text((x,y),args[-1],font=f,fill=0)
        im.save(OUT/f'{mode}.png')
    history.write_bytes(original_history)
    shell('cover_target_kind=generic;rr_cover_save ""')
    assert resolve('resolveBookCover other 同名书 || echo PLACEHOLDER')=='PLACEHOLDER'
    # Preserve unknown association versions on attempted writes.
    state.write_bytes(b'# a future format\nkeep this payload\n')
    shell('cover_target_kind=generic;rr_cover_save "" && exit 1;exit 0')
    assert state.read_bytes()==b'# a future format\nkeep this payload\n'

# Actual touch parser, both ABIs and legacy/current coordinate paths.
touch=(PKG/'reading-insights-touch-ui.lua').read_text(encoding='utf-8')
cases=[]
for m in ('settings_cover_manage','settings_cover_images','settings_cover_books','settings_cover_info'):
    cases += [(m,160,100,'settings_cover_back'),(m,50,100,'')]
cases += [('settings_cover',600,400,'settings_cover_generic'),('settings_cover',600,700,'settings_cover_books'),('settings_cover',600,1000,'settings_cover_info'),('settings_cover',600,1200,'settings_cover_scan'),('settings_cover_manage',600,1140,'settings_cover_choose'),('settings_cover_manage',600,1300,'settings_cover_clear')]
for m,n,step,h in [('settings_cover_images',4,260,230),('settings_cover_books',10,204,184)]:
    for i in range(n):
        x=80+(i%2)*568 if m=='settings_cover_books' else 80
        y=310+(i//2 if m=='settings_cover_books' else i)*step
        cases += [(m,x+10,y+10,f'settings_cover_item_{i+1}'),(m,x+300,y+h,f'settings_cover_item_{i+1}'),(m,79,y+10,''),(m,x+100,y+h+1,'')]
    cases += [(m,200,1460,'settings_cover_prev'),(m,1000,1460,'settings_cover_next')]
cases += [('settings_cover_books',636,1460,'settings_cover_page'),('books',636,1530,'page_jump')]
cases += [('settings_cover_books',636,360+row*204,'') for row in range(5)]
for first,total in ((1,8),(1,50),(21,50),(41,50)):
    os.environ['RR_PAGER_START']=str(first);os.environ['RR_PAGER_TOTAL']=str(total)
    # Evaluated in the loop below with each modal's own numeric environment.
    for i in range(20):
        n=first+i;x=196+(i%5)*180+80;y=600+(i//5)*140+56
        cases.append((f'settings_cover_picker:{first}:{total}',x,y,f'settings_cover_pager_pick_{n}' if n<=total else ''))
    cases += [(f'settings_cover_picker:{first}:{total}',1010,460,'settings_cover_pager_back'),
              (f'settings_cover_picker:{first}:{total}',200,1460,''),
              (f'settings_cover_picker:{first}:{total}',600,200,''),
              (f'settings_cover_picker:{first}:{total}',296,1225,'settings_cover_pager_prev' if first>1 else ''),
              (f'settings_cover_picker:{first}:{total}',976,1225,'settings_cover_pager_next' if first+20<=total else '')]
del os.environ['RR_PAGER_START'];del os.environ['RR_PAGER_TOTAL']
prefix=touch[:touch.index('\nnote(string.format("interactive watcher started')]+ '\nreturn action_for_physical'
for w,h,ox,oy in ((1272,1696,0,0),(1264,1685,0,0),(900,1200,20,40),(600,800,0,0)):
    readers={}
    for tagged,x,y,expected in cases:
        if tagged not in readers:
            mode=tagged
            if ':' in mode:
                mode,first,total=mode.split(':');os.environ['RR_PAGER_START']=first;os.environ['RR_PAGER_TOTAL']=total
            lua=LuaRuntime();lua.globals().arg=lua.table_from({3:mode,6:ox,7:oy,8:w,9:h,17:w+2*ox,18:h+2*oy})
            readers[tagged]=(lua,lua.execute(prefix))
        # getenv is read when a modal tap is mapped, so restore its group.
        if ':' in tagged:
            _,first,total=tagged.split(':');os.environ['RR_PAGER_START']=first;os.environ['RR_PAGER_TOTAL']=total
        actual=readers[tagged][1](ox+x*w/1272,oy+y*h/1696,'direct')
        assert (actual or '')==expected,(tagged,w,h,x,y,actual,expected)
with tempfile.TemporaryDirectory(dir=OUT) as tmp:
    for legacy in ('current','legacy'):
        for size in (16,24):
            for mode,x,y,expected in cases:
                if ':' in mode:
                    mode,first,total=mode.split(':');os.environ['RR_PAGER_START']=first;os.environ['RR_PAGER_TOTAL']=total
                p=Path(tmp)/'input';p.write_bytes(b''.join(bytes(size-8)+struct.pack('<HHi',*e) for e in [(3,53,x),(3,54,y),(0,0,0)]))
                # Compatibility books retain their historical non-jump layout.
                if legacy=='legacy' and mode=='books' and expected=='page_jump':continue
                args=[p.as_posix(),str(Path(tmp)/'log'),mode,0,31,0,0,1272,1696,1,1,1576,'week','7d','direct',size,1272,1696,str(Path(tmp)/'report'),'unknown','unknown','unknown','unknown',legacy]
                lua=LuaRuntime();lua.globals().arg=lua.table_from({i+1:str(v) for i,v in enumerate(args)})
                out=[];lua.globals().capture=lambda *v:out.append(''.join(map(str,v)))
                lua.execute('io.write=capture;io.stderr={write=function() end};os.exit=function(n) error("EXIT:"..n) end')
                try:lua.execute(touch)
                except LuaError as e:assert f'EXIT:{0 if expected else 2}' in str(e),(mode,x,y,str(e))
                assert ''.join(out).strip()==expected,(mode,x,y,out,expected)
print('Custom covers PASS: native decoder/cache, association identity, real source priority/disabled state, 503-book bounded paging, both shared jump targets, six page previews, modal isolation and both evdev ABIs. ARM/Kindle acceptance PENDING.')
