"""Verify the accepted 5.19 asset and its independent source without rebuilding."""
from pathlib import Path
import argparse
import hashlib
import io
import json
import subprocess
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT/'docs/releases/v9.8.1-5.19-vera.json'
REPO = 'L-1116/kindle-reading-records-enhanced'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(commit, name):
    return subprocess.check_output(['git', 'show', commit+':'+name], cwd=ROOT)


def verify_source(record):
    assert record['variant'] == 'standard' and record['tag'] == 'v9.8.1'
    assert record['hardware_acceptance']['firmware'] == '5.19.6'
    commit = record['source_commit']
    assert subprocess.check_output(['git', 'rev-parse', commit+'^{commit}'], cwd=ROOT).decode().strip() == commit
    names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', '-z', commit,
                                     '--', 'native-reading-time-package', 'v4/cleanup.sh'], cwd=ROOT).decode().rstrip('\0').split('\0')
    assert len(names) >= 100
    for name in names:
        original = blob(record['source_baseline'], name)
        expected = original.replace(b'9.8.1-5.20-vera-test1', record['product_version'].encode())
        expected = expected.replace(b'9.8.1-5.20-vera', record['product_version'].encode())
        assert blob(commit, name) == expected, 'Source differs beyond accepted identity: '+name


def verify_zip(raw, record):
    assert len(raw) == record['zip_size'] and sha(raw) == record['zip_sha256'] == record['immutable_candidate_sha256']
    with zipfile.ZipFile(io.BytesIO(raw)) as outer:
        assert outer.testzip() is None and outer.namelist() == record['zip_top_level']
        bootstrap = outer.read(record['zip_top_level'][0])
        payload = outer.read(record['zip_top_level'][1])
    with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
        members = archive.getmembers()
        assert all(m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts for m in members)
        files = {m.name: archive.extractfile(m).read() for m in members}
        assert len(files) == len(members) == record['payload_files']
        assert archive.getmember('native-reading-time-package/cover-image').mode == 0o755
    manifest = json.loads(files['PACKAGE-MANIFEST.json'])
    assert manifest['product_version'] == record['product_version'] and manifest['variant'] == 'standard'
    assert set(files) == {r['path'] for r in manifest['files']} | {'PACKAGE-MANIFEST.json'}
    for row in manifest['files']:
        data = files[row['path']]
        assert len(data) == row['size'] and sha(data) == row['sha256'], row['path']
    identity = dict(line.split('=', 1) for line in files['BUILD-INFO'].decode().splitlines())
    for key in ('product_version', 'runtime_version', 'source_baseline', 'reference_519_commit'):
        assert identity[key] == record[key]
    assert identity['target_device'] == 'KPW6' and identity['target_firmware'] == '5.19.6'
    assert identity['hardware_validation'] == record['build_time_hardware_validation'] == 'pending'
    assert f"PRODUCT_VERSION='{record['product_version']}'".encode() in bootstrap
    assert f"RUNTIME_VERSION='{record['runtime_version']}'".encode() in bootstrap
    assert not any(n.startswith('ks-package/') or n.endswith('/launch-ks.sh') for n in files)
    for name, data in files.items():
        if not name.startswith('native-reading-time-package/') or name.endswith('/migration-manifest.tsv'):
            continue
        if name.endswith('/resources/kual/reading-records-installer/bin/action.sh'):
            assert data == files['extensions/reading-records-installer/bin/action.sh']
            continue
        source = blob(record['source_commit'], name)
        if Path(name).suffix in ('.xml', '.json', '.txt', '.tsv', '.conf'):
            data, source = data.replace(b'\r\n', b'\n'), source.replace(b'\r\n', b'\n')
        assert data == source, name
    assert files['v4/cleanup.sh'] == blob(record['source_commit'], 'v4/cleanup.sh')


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Kindle-Reading-Records-Verification'})
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-only', action='store_true')
    parser.add_argument('--zip', type=Path)
    parser.add_argument('--github', action='store_true')
    args = parser.parse_args()
    record = json.loads(REPORT.read_text(encoding='utf-8'))
    verify_source(record)
    if args.zip:
        verify_zip(args.zip.read_bytes(), record)
    if args.github:
        release = json.loads(fetch('https://api.github.com/repos/'+REPO+'/releases/tags/'+record['tag']))
        assert not release['draft'] and not release['prerelease']
        matrix_path = ROOT/'docs/releases/v9.8.1-downloads.json'
        asset_name = record['zip_file']
        if matrix_path.exists():
            matrix = json.loads(matrix_path.read_text(encoding='utf-8'))
            asset_name = next(r['asset_name'] for r in matrix['packages'] if r['id'] == '519')
        assets = [a for a in release['assets'] if a['name'] == asset_name]
        assert len(assets) == 1 and assets[0]['state'] == 'uploaded'
        assert assets[0]['digest'] == 'sha256:'+record['zip_sha256']
        verify_zip(fetch(assets[0]['browser_download_url']), record)
    print('PASS: frozen Standard 5.19 source/asset; user acceptance limited to KPW6 / 5.19.6 / Vera')


if __name__ == '__main__':
    main()
