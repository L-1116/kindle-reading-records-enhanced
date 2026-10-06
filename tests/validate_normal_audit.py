"""Audit exact ancestry and exercise the production duplicate-row selector."""
from normal_fixture import *
import json
import re
from PIL import Image

checks = []
def passed(name, detail=""):
    checks.append({"check": name, "result": "PASS", "detail": detail})
    print("PASS: " + name, flush=True)

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

tag = 'v9.7.5-测试版'
baseline = git('rev-parse', tag + '^{commit}').decode().strip()
assert baseline == 'e41707492b985284d77e0ec5ec5ceffe98209a89'
commits = git('rev-list', '--reverse', tag + '..HEAD').decode().splitlines()
assert commits and git('rev-parse', commits[0] + '^').decode().strip() == baseline
assert git('rev-parse', commits[0] + '^{tree}') == git('rev-parse', tag + '^{tree}')
assert not git('rev-list', '--merges', tag + '..HEAD').strip()
subprocess.run(['git','merge-base','--is-ancestor','df5fd1e128d6a943435ea0ee8426b8f9f166b250','HEAD'],cwd=ROOT,check=True)
passed('exact frozen Vera baseline, empty original baseline commit and linear ancestry', baseline)

changed = []
for name in git('ls-tree', '-r', '--name-only', tag, 'native-reading-time-package').decode('utf-8').splitlines():
    if (ROOT / name).read_bytes() != git('show', tag + ':' + name):
        changed.append(name)
assert set(changed) == {
    'native-reading-time-package/阅读记录-optimized.sh',
    'native-reading-time-package/阅读记录.sh',
    'native-reading-time-package/reading-insights-title-widths.lua',
}, changed
original = git('show', tag + ':native-reading-time-package/reading-insights-title-widths.lua')
assert original.replace(b'\r\n', b'\n') == (PKG / 'reading-insights-title-widths.lua').read_bytes()
passed('strict baseline bytes: only two UI shells and width-table line endings changed', str(changed))
viewer = (PKG / '阅读记录-optimized.sh').read_text(encoding='utf-8')
old = git('show', tag + ':native-reading-time-package/阅读记录-optimized.sh').decode('utf-8')
for start, end in [
    ('find_touch_device()', 'scale_len()'),
    ('build_cache()', 'catalog_loaded=0'),
    ('extract_epub_cover()', 'renderer_available=0'),
    ('prepare_week_view()', 'draw_count=0'),
]:
    assert viewer[viewer.index(start):viewer.index(end)] == old[old.index(start):old.index(end)], start
passed('touch selection, cover extraction, statistics and UI rendering functions preserved exactly')

with zipfile.ZipFile(ARCHIVE) as z:
    for shell in (SH, DASH):
        subprocess.run([shell, "-n"], input=z.read(BOOTSTRAP), check=True, capture_output=True)
    with tarfile.open(fileobj=io.BytesIO(z.read(PAYLOAD))) as t:
        names = t.getnames()
        assert not any(any(token in name.lower() for token in [
            'compat/', 'probe', 'watchdog', 'diagnostic', 'ks-package', 'ks-ui', 'detect_env', 'runtime-fallback'
        ]) for name in names)
        for name in names:
            if name.endswith('.sh'):
                raw_script = t.extractfile(name).read()
                for shell in (SH, DASH):
                    subprocess.run([shell, '-n'], input=raw_script, check=True, capture_output=True)
                source = raw_script.decode('utf-8')
                assert '5.19' not in source and '5.17' not in source
                assert 'hard_float' not in source and 'fbink -e' not in source
        assert not any('Install-Native' in n or 'RUNME.sh' in n for n in names)
passed('tar excludes compatibility/KS code, probes, watchdogs, obsolete installers and diagnostics')

cleanup=(PKG/'resources/reading-records-install-cleanup.sh').read_text(encoding='utf-8')
whitelist=(PKG/'cleanup-manifest.txt').read_text(encoding='utf-8').splitlines()
actual=re.findall(r'(?m)^(?:rm -(?:rf|f)|remove_owned) "(/mnt/us/[^"\n]+)"',cleanup)
assert actual==whitelist,(actual,whitelist)
assert all('/reading-time' not in path and not any(c in path for c in '*?[') for path in whitelist)
self_delete='rm -f /mnt/us/documents/reading-records-install-cleanup.sh || exit 1'
assert self_delete in cleanup and 'rm ' not in cleanup.split(self_delete,1)[1]
passed('literal cleanup paths exactly match manifest; no data paths/globs; self removed last')

d = Device()
thumb = d.us / 'system/thumbnails/new.jpg'
write(thumb, 'thumbnail bytes')
epub = d.docs / 'new.epub'
mobi = d.docs / 'new.mobi'
pdf = d.docs / 'new.pdf'
write(mobi, 'mobi source')
write(pdf, 'PDF source')
image = io.BytesIO()
Image.new('L', (48, 72), 150).save(image, 'JPEG')
with zipfile.ZipFile(epub, 'w') as z:
    z.writestr('META-INF/container.xml', '<container><rootfiles><rootfile full-path="OPS/content.opf"/></rootfiles></container>')
    z.writestr('OPS/content.opf', '<package><metadata><meta name="cover" content="cover"/></metadata><manifest><item id="cover" href="cover.jpg" media-type="image/jpeg"/></manifest></package>')
    z.writestr('OPS/cover.jpg', image.getvalue())
write(d.base / 'book-covers/old.jpg', 'old cached image')
write(d.base / 'book-cover-cache.tsv', 'OLD\t' + (d.base / 'book-covers/old.jpg').as_posix() + '\n')
write(d.base / 'book-cover-misses.tsv', 'OLDMISS\tunchanged signature\n')

def row(book, thumbnail='', location='', title='Book'):
    return '\t'.join(['-1', title, book, thumbnail, location, '']) + '\n'

fixture = d.root / 'catalog.tsv'
write(fixture, ''.join([
    row('A'), row('A', thumb.as_posix()),
    row('B'), row('B', location=epub.as_posix()),
    row('C', location=mobi.as_posix()), row('C', thumb.as_posix(), mobi.as_posix()),
    row('P'), row('P', thumb.as_posix(), pdf.as_posix()),
    row('E'), row('E', location=mobi.as_posix()),
    row('S', (d.us / 'system/thumbnails/missing.jpg').as_posix()), row('S', location=epub.as_posix()),
    row('NO'), row('NO'), row('OTHER', thumb.as_posix(), title='Repeated title'),
]))
defs = viewer[:viewer.index('\n. "$RELEASE/bin/runtime-child.sh"')].replace('exec >> "$LOG" 2>&1', '')
defs = defs.replace('echo "$(date): optimized dashboard launch, uid=$(id -u), pid=$$"', '')
code = d.transform(defs.encode()).decode() + f'''
CATALOG="{fixture.as_posix()}"; catalog_loaded=1
SESSION_DIR="{d.tmp.as_posix()}/covers"; mkdir -p "$SESSION_DIR"
COVER_HELPER="{(PKG / 'reading-insights-cover.lua').as_posix()}"
for book in A B C P E S NO; do
    value="$(catalog_row_for_book "$book" Book)"
    printf '%s\\t%s\\n' "$book" "$value" >> "{(d.root / 'selected.tsv').as_posix()}"
done
resolveBookCover A Book > "{(d.root / 'resolved-A').as_posix()}"
resolveBookCover P Book > "{(d.root / 'resolved-P').as_posix()}"
resolveBookCover B Book > "{(d.root / 'resolved-B').as_posix()}" || exit 42
! resolveBookCover NO 'Repeated title' > "{(d.root / 'resolved-wrong').as_posix()}" || exit 8
resolveBookCover WRONG 'Repeated title' > "{(d.root / 'resolved-title-fallback').as_posix()}" || exit 9
rm -rf "$SESSION_DIR"
'''
script = d.root / 'cover-regression.sh'
write(script, code)
d.run(script)
selected = {line.split('\t', 1)[0]: line.split('\t')[1:] for line in (d.root / 'selected.tsv').read_text(encoding="utf-8").splitlines()}
assert selected['A'][3] == thumb.as_posix(), selected
assert selected['B'][4] == epub.as_posix()
assert selected['C'][3] == thumb.as_posix() and selected['C'][4] == mobi.as_posix()
assert selected['P'][3] == thumb.as_posix()
assert selected['E'][4] == mobi.as_posix()
assert selected['S'][4] == epub.as_posix()
assert (d.root / 'resolved-title-fallback').read_text(encoding='utf-8').strip() == thumb.as_posix()
assert (d.root / 'resolved-A').read_text(encoding="utf-8").strip() == thumb.as_posix()
assert (d.root / 'resolved-P').read_text(encoding="utf-8").strip() == thumb.as_posix()
cover = Path((d.root / 'resolved-B').read_text(encoding="utf-8").strip())
assert cover.read_bytes() == image.getvalue()
assert (d.base / 'book-covers/old.jpg').read_text(encoding="utf-8") == 'old cached image'
assert 'OLDMISS' in (d.base / 'book-cover-misses.tsv').read_text(encoding="utf-8")
assert 'OLD\t' in (d.base / 'book-cover-cache.tsv').read_text(encoding="utf-8")
d.no_temporary()
passed('duplicate rows: empty first row, stale thumbnail, usable locations, preference ranking, PDF thumbnail, actual EPUB extraction, matching ID isolation, baseline title fallback when ID absent, preserved caches')

result = {'result': 'PASS', 'checks': checks, 'case_count': len(checks), 'baseline_sha': baseline,
          'limits': ['Real repository/shell/Lua fixtures; no live Kindle catalog queried.']}
write(OUT / 'audit-results.json', json.dumps(result, ensure_ascii=False, indent=2))
