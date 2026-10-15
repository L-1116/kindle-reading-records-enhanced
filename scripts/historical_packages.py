"""Pinned released bytes shared by ownership generation and upgrade fixtures.

Run with --fetch to restore missing public artifacts; local test archives must
be supplied separately. No installed path is inferred from a release tag.
"""
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / 'scripts/historical-packages.json').read_text(encoding='utf-8'))


def package(row):
    path = ROOT / row['path']
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != row['sha256']:
        raise ValueError(f"Historical package checksum mismatch: {path}")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert archive.testzip() is None, path
        outer = {n: archive.read(n) for n in archive.namelist() if not n.endswith('/')}
    files = dict(outer)
    for name, data in outer.items():
        if not name.endswith('.tar'):
            continue
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            for member in archive:
                if not member.isfile() or member.name.startswith('/') or '..' in Path(member.name).parts:
                    raise ValueError(f'Unsafe historical archive: {path}')
                files[member.name] = archive.extractfile(member).read()
    return outer, files


if __name__ == '__main__':
    for row in CATALOG:
        path = ROOT / row['path']
        if not path.exists() and '--fetch' in sys.argv and row.get('url'):
            request = urllib.request.Request(row['url'], headers={'User-Agent': 'reading-records-build'})
            raw = urllib.request.urlopen(request, timeout=180).read()
            assert hashlib.sha256(raw).hexdigest() == row['sha256'], path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        package(row)
        print(row['id'], row['sha256'])
