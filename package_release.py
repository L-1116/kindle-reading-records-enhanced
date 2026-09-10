"""Package only the two deployable entries, then verify every archived byte."""
from pathlib import Path
import hashlib,json,zipfile
from PIL import Image

root=Path(__file__).resolve().parent
files=[root/'RUNME.sh',*sorted(p for p in (root/'native-reading-time-package').rglob('*') if p.is_file())]
archive=root/'Kindle安装包-v9.7.1-day-detail.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in files:z.write(p,p.relative_to(root).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert len(z.namelist())==len(files)
    for p in files:assert z.read(p.relative_to(root).as_posix())==p.read_bytes()
manifest={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(root/'validation/release-sha256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
original=root.parent/'v9.6.10-ui-layout-fix'
baseline_manifest=json.loads((original/'validation/release-sha256.json').read_text(encoding='utf-8'))
for name,sha256 in baseline_manifest.items():
    assert hashlib.sha256((original/name).read_bytes()).hexdigest()==sha256,name
for name in ['daily-final','day-detail-multiple','day-detail-page-2','books-filters','total-week']:
    im=Image.open(root/'validation'/f'{name}.png')
    im.resize((636,848)).save(root/'validation'/f'{name}-preview.png')
sheet=Image.new('L',(1272,1696),255)
for i,name in enumerate(['daily-final','day-detail-multiple','day-detail-page-2','total-week']):
    sheet.paste(Image.open(root/'validation'/f'{name}-preview.png'),((i%2)*636,(i//2)*848))
sheet.save(root/'validation/layout-contact-sheet.png')
result={'result':'PASS','archive_files':len(files),'archive_bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'checks':['Every ZIP entry matches its source byte-for-byte.','Original baseline hashes still match after the work.']}
(root/'validation/package-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
