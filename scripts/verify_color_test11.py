"""Verify the local test11 package against the accepted test10 original ZIP.

Read-only: does not build, publish, rewrite historical records or use a device.
"""
from pathlib import Path
import argparse, hashlib, io, json, subprocess, tarfile, zipfile

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_VERSION = '9.8.1-5.20-vera-test11'
RUNTIME_VERSION = '9.8.1-5.20-vera-test1'
BOOT_NAME = 'reading-records-v4-install.sh'
TAR_NAME = '阅读记录安装数据.tar'
SIMPLE_ARCHIVE = ROOT/'dist/standard-9.8.1-test11/Kindle-Reading-Records-v9.8.1-5.20-vera-test11.zip'
BASELINE_SHA = 'a195a3f6320d1ca3f523d6b5d2354d923faccf8f67d6575ba9fa809fed19ff52'
EXPECTED_CHANGES = {
    'BUILD-INFO', 'PACKAGE-MANIFEST.json', 'README.txt', 'V4-PAYLOAD',
    'native-reading-time-package/Install-Native-Reading-Time-Optimized.sh',
    'native-reading-time-package/cover-image', 'native-reading-time-package/install.sh',
    'native-reading-time-package/launch.sh', 'native-reading-time-package/阅读记录-entry.sh',
    'native-reading-time-package/migration-manifest.tsv', 'v4/cleanup.sh',
}

def sha(raw): return hashlib.sha256(raw).hexdigest()

def unpack(path):
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None and z.namelist() == [BOOT_NAME, TAR_NAME]
        boot = z.read(BOOT_NAME); payload = z.read(TAR_NAME)
    with tarfile.open(fileobj=io.BytesIO(payload)) as t:
        members = t.getmembers()
        assert all(m.isfile() and not m.issym() and not m.islnk() for m in members)
        assert len(members) == len({m.name for m in members})
        files = {m.name: t.extractfile(m).read() for m in members}
        assert t.getmember('native-reading-time-package/cover-image').mode == 0o755
    return boot, payload, files

def verify(archive, baseline):
    assert sha(baseline.read_bytes()) == BASELINE_SHA, 'Wrong test10 baseline'
    _, _, old = unpack(baseline)
    boot, payload, files = unpack(archive)
    assert files.keys() == old.keys()
    changed = {n for n in files if files[n] != old[n]}
    assert changed == EXPECTED_CHANGES, ('Unexpected payload changes', sorted(changed ^ EXPECTED_CHANGES))
    manifest = json.loads(files['PACKAGE-MANIFEST.json'])
    assert manifest['product_version'] == PRODUCT_VERSION and manifest['variant'] == 'standard'
    assert set(files) == {r['path'] for r in manifest['files']} | {'PACKAGE-MANIFEST.json'}
    for row in manifest['files']:
        raw = files[row['path']]
        assert len(raw) == row['size'] and sha(raw) == row['sha256'], row['path']
    assert not any(n.startswith('ks-package/') for n in files)
    info = dict(s.split('=', 1) for s in files['BUILD-INFO'].decode().splitlines())
    assert info['product_version'] == PRODUCT_VERSION and info['variant'] == 'standard'
    assert info['source_baseline'] == '6ab389ae5d688393499088d46422d03c89a7e2dc'
    assert info['release_status'] == 'local_unpublished'
    build_inputs = {n:r for n,r in files.items() if n not in ('BUILD-INFO', 'PACKAGE-MANIFEST.json')}
    assert info['build_id'] == sha(b''.join(n.encode()+b'\0'+sha(r).encode() for n,r in sorted(build_inputs.items())))[:20]
    assert f"PRODUCT_VERSION='{PRODUCT_VERSION}'".encode() in boot
    assert f"RUNTIME_VERSION='{RUNTIME_VERSION}'".encode() in boot
    for n in ('native-reading-time-package/Install-Native-Reading-Time-Optimized.sh', 'v4/cleanup.sh'):
        assert PRODUCT_VERSION.encode() in files[n] and RUNTIME_VERSION.encode() in files[n]
    binary = files['native-reading-time-package/cover-image']
    assert binary == (ROOT/'native-reading-time-package/cover-image').read_bytes()
    assert binary[:6] == b'\x7fELF\x01\x01' and int.from_bytes(binary[18:20], 'little') == 40
    # ARM EABI5, soft-float calling convention and no dynamic loader.
    flags = int.from_bytes(binary[36:40], 'little')
    assert flags >> 24 == 5 and flags & 0x200 and not flags & 0x400
    off = int.from_bytes(binary[28:32], 'little'); size = int.from_bytes(binary[42:44], 'little')
    count = int.from_bytes(binary[44:46], 'little')
    assert all(int.from_bytes(binary[off+i*size:off+i*size+4], 'little') != 3 for i in range(count))
    assert b'P6\n240 360\n255\n' in binary
    # Every packaged production file except generated install adapters/ownership
    # metadata must match the exact current checkout used by the regressions.
    generated = {'native-reading-time-package/resources/kual/reading-records-installer/bin/action.sh',
                 'native-reading-time-package/migration-manifest.tsv'}
    for n, raw in files.items():
        if n.startswith(('native-reading-time-package/', 'v4/')) and n not in generated:
            assert raw == (ROOT/n).read_bytes(), ('Stale packaged file', n)
    return {'result': 'PASS', 'product_version': PRODUCT_VERSION, 'variant': 'standard',
            'runtime_version': RUNTIME_VERSION, 'build_id': info['build_id'],
            'zip_file': archive.name, 'zip_size': archive.stat().st_size,
            'zip_sha256': sha(archive.read_bytes()), 'payload_sha256': sha(payload),
            'payload_files': len(files), 'changed_payload_files': sorted(changed),
            'unchanged_payload_files': len(files)-len(changed), 'baseline_zip_sha256': BASELINE_SHA,
            'development_base_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'helper_sha256': sha(binary), 'helper_bytes': len(binary),
            'c_source_sha256': sha((ROOT/'native/custom-cover/cover-image.c').read_bytes()),
            'hardware_display_verified': False, 'publication_actions': []}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip', type=Path, default=SIMPLE_ARCHIVE)
    parser.add_argument('--baseline', type=Path, default=ROOT/'build/idle-startup-candidate/9.8.1-5.20-vera-test10.zip')
    options = parser.parse_args()
    print(json.dumps(verify(options.zip, options.baseline), ensure_ascii=True, indent=2))
