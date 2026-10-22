"""5.19.6 candidate integrity and upgrades from the real accepted 9.7.6 ZIP.

These are isolated host fixtures, never evidence of Kindle hardware support.
"""
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tarfile
import tempfile
import zipfile

from validate_v4 import ROOT, OUT, run
from build_v4 import (BOOT_NAME, TAR_NAME, PRODUCT_VERSION, RUNTIME_VERSION,
                      SIMPLE_ARCHIVE, sources, posix_cksum)
from historical_packages import CATALOG, package

BASELINE = 'fd9a417d12539f0a9997ba57f60cdb9e7b1edbc8'
VERSION = '9.8.1-5.19-vera-test1'


def original(name):
    return subprocess.check_output(['git', 'show', BASELINE + ':' + name], cwd=ROOT)


def integrity():
    assert PRODUCT_VERSION == RUNTIME_VERSION == VERSION
    with zipfile.ZipFile(SIMPLE_ARCHIVE) as archive:
        assert archive.testzip() is None
        assert sorted(archive.namelist()) == sorted([BOOT_NAME, TAR_NAME])
        bootstrap = archive.read(BOOT_NAME)
        payload = archive.read(TAR_NAME)
    assert f"PRODUCT_VERSION='{VERSION}'".encode() in bootstrap
    assert f"RUNTIME_VERSION='{VERSION}'".encode() in bootstrap
    assert f"PAYLOAD_CKSUM='{posix_cksum(payload)}'".encode() in bootstrap
    with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
        members = archive.getmembers()
        assert all(m.isfile() and not m.issym() and not m.islnk() for m in members)
        files = {m.name: archive.extractfile(m).read() for m in members}
        assert len(files) == len(members)
        assert archive.getmember('native-reading-time-package/cover-image').mode == 0o755
    identity = dict(line.split('=', 1) for line in files['BUILD-INFO'].decode().splitlines())
    assert identity['source_baseline'] == BASELINE
    assert identity['target_firmware'] == '5.19.6'
    assert identity['hardware_validation'] == 'pending'
    manifest = json.loads(files['PACKAGE-MANIFEST.json'])
    for row in manifest['files']:
        raw = files[row['path']]
        assert len(raw) == row['size'] and hashlib.sha256(raw).hexdigest() == row['sha256']
    # Runtime source is from v9.8.1, allowing only identity and Git text EOLs.
    # This protects all statistics, artwork, UI, sleep/idle and decoder behavior.
    protected = 0
    for name, raw in files.items():
        if not name.startswith('native-reading-time-package/') or name.endswith('migration-manifest.tsv'):
            continue
        before = original(name)
        if name.endswith('/resources/kual/reading-records-installer/bin/action.sh'):
            # build_v4 has always generated this dispatcher in both locations.
            assert (ROOT / name).read_bytes() == before
            assert raw == files['extensions/reading-records-installer/bin/action.sh']
            protected += 1
            continue
        expected = before.replace(b'9.8.1-5.20-vera-test1', VERSION.encode())
        expected = expected.replace(b'9.8.1-5.20-vera', VERSION.encode())
        if Path(name).suffix in ('.xml', '.json', '.txt', '.tsv', '.conf'):
            raw, expected = raw.replace(b'\r\n', b'\n'), expected.replace(b'\r\n', b'\n')
        assert raw == expected, name
        protected += 1
    # The decoder is static ARM EABI5 soft-float. It needs no 5.20 glibc/loader.
    # CPU instruction execution and framebuffer output still need the KPW6.
    binary = files['native-reading-time-package/cover-image']
    assert binary[:7] == b'\x7fELF\x01\x01\x01'
    assert struct.unpack_from('<H', binary, 18)[0] == 40
    flags = struct.unpack_from('<I', binary, 36)[0]
    assert flags & 0xff000000 == 0x05000000 and flags & 0x200 and flags & 0x400 == 0
    offset = struct.unpack_from('<I', binary, 28)[0]
    size, count = struct.unpack_from('<HH', binary, 42)
    headers = [struct.unpack_from('<I', binary, offset + i * size)[0] for i in range(count)]
    assert 3 not in headers and 2 not in headers, 'No interpreter or dynamic dependency allowed'
    # The actual 5.19 deployed release ID differs from the marketing version.
    _, accepted = package(next(r for r in CATALOG if r['id'] == 'v9.7.6-5.19-vera'))
    inventory = files['native-reading-time-package/migration-manifest.tsv']
    for line in accepted['native-reading-time-package/install-manifest.txt'].decode().splitlines():
        src, kind, destination, _ = line.split('\t')
        if kind not in ('release', 'docs'):
            continue
        raw = accepted['native-reading-time-package/' + src]
        kind, path = ('entry', destination) if kind == 'docs' else ('release', '9.7.6-5.19-normal/' + destination)
        key = f'{kind}\t{path}\t{posix_cksum(raw)}\t{len(raw)}\t'.encode()
        assert key in inventory, (src, path)
    assert files == sources('standard')
    print(f'PASS package, {protected} v9.8.1 runtime files, ARM ABI and accepted 5.19 ownership', flush=True)


def main():
    if '--install-only' not in sys.argv:
        integrity()
    if '--integrity-only' in sys.argv:
        return
    cases = [(None, '', True), ('normal', '', True), ('v9.7.6-5.19-vera-cleaned', '', True)]
    cases += [('normal', mutation, False) for mutation in (
        'core_failure', 'activation_failure', 'interrupted', 'bad_checksum',
        'ks_residue', 'wrong_device', 'busy_ui', 'unknown_formal',
        'cover_dir_file', 'cover_dir_symlink')]
    for previous, mutation, cleanup in cases:
        with tempfile.TemporaryDirectory(prefix='519-vera-', dir=OUT) as directory:
            row = run(Path(directory), previous=previous, mutation=mutation,
                      cleanup=cleanup, firmware='5.19.6')
            assert row['package_sha256'] == hashlib.sha256(SIMPLE_ARCHIVE.read_bytes()).hexdigest()
            print('PASS 5.19.6', row['scenario'], 'protected files', row['protected_files'], flush=True)
    print(f'PASS {len(cases)} install/upgrade/rollback/refusal cases; hardware pending', flush=True)


if __name__ == '__main__':
    main()
