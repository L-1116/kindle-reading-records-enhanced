"""Package the deployable Kindle tree, then verify every archived byte."""
from pathlib import Path
import hashlib,json,zipfile
from PIL import Image

root=Path(__file__).resolve().parents[1]
out=root/'build/validation';out.mkdir(parents=True,exist_ok=True)
dist=root/'dist';dist.mkdir(exist_ok=True)
files=[
    root/'RUNME.sh',
    root/'README.txt',
    root/'documents/reading-records-install.sh',
    root/'documents/reading-records-uninstall.sh',
    *sorted(p for p in (root/'extensions/reading-records-installer').rglob('*') if p.is_file()),
    *sorted(p for p in (root/'native-reading-time-package').rglob('*') if p.is_file()),
]
assert root/'native-reading-time-package/launcher-icon.png' in files
assert root/'native-reading-time-package/reading-insights-cover.lua' in files
assert root/'native-reading-time-package/compat/detect_env.sh' in files
assert root/'extensions/reading-records-installer/menu.json' in files
canonical_pairs={
    root/'documents/reading-records-uninstall.sh': root/'native-reading-time-package/resources/reading-records-uninstall.sh',
    root/'extensions/reading-records-installer/bin/action.sh': root/'native-reading-time-package/resources/kual/reading-records-installer/bin/action.sh',
    root/'extensions/reading-records-installer/config.xml': root/'native-reading-time-package/resources/kual/reading-records-installer/config.xml',
    root/'extensions/reading-records-installer/menu.json': root/'native-reading-time-package/resources/kual/reading-records-installer/menu.json',
}
for deployed,canonical in canonical_pairs.items():assert deployed.read_bytes()==canonical.read_bytes()
archive=dist/'kindle-reading-records-v9.7.5-test.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in files:z.write(p,p.relative_to(root).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert len(z.namelist())==len(files)
    assert 'native-reading-time-package/launcher-icon.png' in z.namelist()
    assert 'native-reading-time-package/reading-insights-cover.lua' in z.namelist()
    assert 'documents/reading-records-install.sh' in z.namelist()
    assert 'documents/reading-records-uninstall.sh' in z.namelist()
    assert 'native-reading-time-package/uninstall.sh' in z.namelist()
    assert 'native-reading-time-package/install-manifest.txt' in z.namelist()
    assert 'README.txt' in z.namelist()
    assert 'extensions/reading-records-installer/menu.json' in z.namelist()
    assert 'native-reading-time-package/resources/reading-records-uninstall.sh' in z.namelist()
    assert 'native-reading-time-package/resources/kual/reading-records-installer/menu.json' in z.namelist()
    for p in files:assert z.read(p.relative_to(root).as_posix())==p.read_bytes()
manifest={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(out/'release-sha256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
for name in ['daily-final','day-detail-multiple','day-detail-page-2','books-filters','total-week','month-detail','week-trend','book-detail']:
    im=Image.open(out/f'{name}.png')
    im.resize((636,848)).save(out/f'{name}-preview.png')
sheet=Image.new('L',(1272,1696),255)
for i,name in enumerate(['book-detail','month-detail','daily-final','total-week']):
    sheet.paste(Image.open(out/f'{name}-preview.png'),((i%2)*636,(i//2)*848))
sheet.save(out/'layout-contact-sheet.png')
result={'result':'PASS','archive_files':len(files),'archive_bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'checks':['Every ZIP entry matches its source byte-for-byte.']}
(out/'package-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
