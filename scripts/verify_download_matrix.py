"""Verify the four v9.8.1 downloads against independent frozen source commits."""
from pathlib import Path, PurePosixPath
import argparse, hashlib, io, json, re, subprocess, tarfile, urllib.parse, urllib.request, zipfile

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT/'docs/releases/v9.8.1-downloads.json'
REPO = 'L-1116/kindle-reading-records-enhanced'
TOP_LEVEL = ['reading-records-v4-install.sh', '阅读记录安装数据.tar']


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def blobs(commit, names):
    assert re.fullmatch(r'[0-9a-f]{40}', commit), 'Invalid source commit'
    names = list(names)
    assert all('\n' not in n and '\r' not in n for n in names)
    p = subprocess.run(['git', 'cat-file', '--batch'], cwd=ROOT,
                       input=''.join(commit+':'+n+'\n' for n in names).encode(), capture_output=True, check=True)
    stream = io.BytesIO(p.stdout)
    result = {}
    for name in names:
        header = stream.readline().split()
        assert len(header) == 3 and header[1] == b'blob', 'Missing frozen source: '+name
        result[name] = stream.read(int(header[2]))
        assert stream.read(1) == b'\n'
    assert not stream.read()
    return result


def verify_sources(matrix):
    assert matrix['tag'] == 'v9.8.1' and matrix['release_id'] == 416331823
    assert [r['id'] for r in matrix['packages']] == ['test12', '519', 'test11', 'test10']
    assert len({r['asset_name'] for r in matrix['packages']}) == 4
    for row in matrix['packages']:
        source = blobs(row['source_commit'], row['source_sha256'])
        assert len(source) >= 100, row['id']
        for name, raw in source.items():
            assert sha(raw) == row['source_sha256'][name], 'Frozen source mismatch: '+name
        print('PASS: independent source', row['id'], row['source_commit'], flush=True)


def verify_zip(raw, row):
    assert len(raw) == row['zip_size'] and sha(raw) == row['zip_sha256'], 'ZIP differs from accepted original: '+row['id']
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert z.testzip() is None and z.namelist() == TOP_LEVEL
        bootstrap = z.read(TOP_LEVEL[0]); payload = z.read(TOP_LEVEL[1])
    assert sha(bootstrap) == row['bootstrap_sha256'] and sha(payload) == row['payload_sha256']
    with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
        members = archive.getmembers()
        assert all(m.isfile() and not m.issym() and not m.islnk() and
                   not PurePosixPath(m.name).is_absolute() and '..' not in PurePosixPath(m.name).parts for m in members)
        assert len(members) == len({m.name for m in members}) == row['payload_files']
        files = {m.name: archive.extractfile(m).read() for m in members}
        for name in ('native-reading-time-package/cover-image', 'native-reading-time-package/idle-input'):
            if name in files:
                assert archive.getmember(name).mode == 0o755
                binary = files[name]
                assert binary[:6] == b'\x7fELF\x01\x01' and int.from_bytes(binary[18:20], 'little') == 40
    manifest = json.loads(files['PACKAGE-MANIFEST.json'])
    assert manifest['variant'] == 'standard' and manifest['product_version'] == row['product_version']
    assert set(files) == {r['path'] for r in manifest['files']} | {'PACKAGE-MANIFEST.json'}
    assert len(manifest['files']) == len({r['path'] for r in manifest['files']})
    for entry in manifest['files']:
        data = files[entry['path']]
        assert len(data) == entry['size'] and sha(data) == entry['sha256'], entry['path']
    info = dict(line.split('=', 1) for line in files['BUILD-INFO'].decode().splitlines())
    assert info['variant'] == 'standard' and info['product_version'] == row['product_version'] and info['build_id'] == row['build_id']
    assert f"PRODUCT_VERSION='{row['product_version']}'".encode() in bootstrap
    assert f"RUNTIME_VERSION='{row['runtime_version']}'".encode() in bootstrap
    assert not any(n.startswith('ks-package/') or n.endswith('/launch-ks.sh') for n in files)
    generated = {'native-reading-time-package/migration-manifest.tsv',
                 'native-reading-time-package/resources/kual/reading-records-installer/bin/action.sh'}
    names = [n for n in files if n.startswith(('native-reading-time-package/', 'v4/')) and n not in generated]
    source = blobs(row['source_commit'], names)
    overrides = row.get('accepted_checkout_bytes', {})
    for name in names:
        if files[name] != source[name]:
            assert name in overrides and sha(files[name]) == overrides[name], 'Package/source mismatch: '+name
            assert files[name].replace(b'\r\n', b'\n') == source[name].replace(b'\r\n', b'\n'), name
    assert files['v4/cleanup.sh'].decode().splitlines()[1] == '# Name: 确认无误之后，再点这个'
    return files


def release_assets(release, matrix):
    assert release['id'] == matrix['release_id'] and release['tag_name'] == matrix['tag']
    assert release['name'] == matrix['release_title'] and not release['draft'] and not release['prerelease']
    expected = {r['asset_name']: r for r in matrix['packages']}
    assets = release['assets']
    assert len(assets) == 4 and {a['name'] for a in assets} == set(expected), 'Expected exactly four installation ZIP assets'
    result = {}
    for asset in assets:
        row = expected[asset['name']]
        assert asset['state'] == 'uploaded' and asset['size'] == row['zip_size']
        assert asset['digest'] == 'sha256:'+row['zip_sha256'], asset['name']
        parsed = urllib.parse.urlsplit(asset['browser_download_url'])
        assert parsed.scheme == 'https' and parsed.hostname == 'github.com'
        assert urllib.parse.unquote(parsed.path) == '/'+REPO+'/releases/download/v9.8.1/'+row['asset_name']
        result[row['id']] = asset
    return result


def fetch(url):
    url = urllib.parse.quote(url, safe=':/?=&%')
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'krr-four-download-verifier'}), timeout=180) as r:
        return r.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-only', action='store_true')
    parser.add_argument('--github', action='store_true')
    parser.add_argument('--zip-dir', type=Path)
    parser.add_argument('--zip', type=Path, help='Verify the recommended test12 original ZIP')
    args = parser.parse_args()
    assert args.source_only or args.github or args.zip_dir or args.zip
    matrix = json.loads(RECORD.read_text(encoding='utf-8'))
    verify_sources(matrix)
    if args.zip_dir:
        for row in matrix['packages']:
            verify_zip((args.zip_dir/row['asset_name']).read_bytes(), row)
            print('PASS: original ZIP', row['id'], flush=True)
    if args.zip:
        verify_zip(args.zip.read_bytes(), matrix['packages'][0])
    if args.github:
        tag = json.loads(fetch('https://api.github.com/repos/'+REPO+'/git/ref/tags/v9.8.1'))
        assert tag['object']['sha'] == matrix['preserved_tag_object'], 'Existing v9.8.1 tag changed'
        release = json.loads(fetch('https://api.github.com/repos/'+REPO+'/releases/tags/v9.8.1'))
        assets = release_assets(release, matrix)
        for row in matrix['packages']:
            verify_zip(fetch(assets[row['id']]['browser_download_url']), row)
            print('PASS: public download', row['id'], flush=True)
    print('PASS: four independent Standard originals; no rebuilding or device claims')


if __name__ == '__main__':
    main()
