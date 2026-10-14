"""Exact KS ownership from preserved historical packages; no Standard claims."""
import io
import re
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ownership_manifest(current, checksum):
    records = set()
    sums = {}

    def add(kind, name, raw, origin):
        key = __import__('hashlib').sha256(raw).digest()
        if key not in sums:
            sums[key] = checksum(raw)
        records.add((kind, name, str(sums[key]), str(len(raw)), origin))

    def inventory(files, origin):
        prefix = 'native-reading-time-package/'
        for name, raw in files.items():
            if name.startswith('documents/'):
                add('entry', name.removeprefix('documents/'), raw, origin)
            elif name.startswith(prefix):
                add('payload', name.removeprefix(prefix), raw, origin)
            elif name in ('RUNME.sh', 'README.txt', 'PACKAGE-MANIFEST-KS.json', 'V4-PAYLOAD') or name.startswith('extensions/'):
                add('root', name, raw, origin)
        for source, target in [('阅读记录-KS-entry.sh', '阅读记录.sh'), ('阅读记录-KS-entry.sh', 'reading-records.sh'),
                               ('阅读记录-KS-force-exit-entry.sh', 'reading-records-ks-force-exit.sh')]:
            if prefix + source in files:
                add('entry', target, files[prefix + source], origin)
        if 'v4/cleanup.sh' in files:
            for target in ('安装好之后，确认无误了再点这个.sh', 'reading-records-install-cleanup.sh'):
                add('entry', target, files['v4/cleanup.sh'], origin)
        ui = files.get(prefix + '阅读记录-ks.sh', b'')
        match = re.search(rb'\$BASE/releases/([0-9A-Za-z.-]+)', ui)
        if not match:
            return
        release = match.group(1).decode()
        for name, raw in files.items():
            if not name.startswith(prefix):
                continue
            relative = name.removeprefix(prefix)
            target = None
            if relative == '阅读记录-ks.sh':
                target = 'bin/reading-records-ks.sh'
            elif relative.startswith('reading-insights-') and relative.endswith(('.lua', '.awk', '.sh')):
                target = 'bin/' + relative
            elif relative.startswith(('ui-scribe/', 'render-assets/')):
                target = relative
            elif relative == 'launcher-icon.png':
                target = 'assets/' + relative
            if target:
                add('release', release + '/' + target, raw, origin)

    current_version = current['V4-PAYLOAD'].decode().split('product_version=')[1].splitlines()[0]
    # Only actual KS packages qualify; never infer ownership from a book name.
    for path in sorted((ROOT / 'dist').rglob('*.zip')):
        if 'ks' not in path.name.lower():
            continue
        with zipfile.ZipFile(path) as outer:
            if '阅读记录安装数据.tar' in outer.namelist():
                with tarfile.open(fileobj=io.BytesIO(outer.read('阅读记录安装数据.tar'))) as archive:
                    files = {m.name: archive.extractfile(m).read() for m in archive if m.isfile()}
            else:
                files = {name: outer.read(name) for name in outer.namelist() if not name.endswith('/')}
            if 'native-reading-time-package/阅读记录-ks.sh' not in files:
                continue
            if f'product_version={current_version}\n'.encode() in files.get('BUILD-INFO', b''):
                continue
            if 'reading-records-v4-install.sh' in outer.namelist():
                add('entry', 'reading-records-v4-install.sh', outer.read('reading-records-v4-install.sh'), path.stem)
            inventory(files, path.stem)
    inventory(current, 'current')
    return ''.join('\t'.join(row) + '\n' for row in sorted(records)).encode('utf-8')
