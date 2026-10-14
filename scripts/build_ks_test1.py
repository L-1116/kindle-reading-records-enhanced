"""Build a new local KS candidate without rebuilding or replacing Standard."""
from pathlib import Path
import json
import io
import tarfile
import zipfile
from build_v4 import make_tar, make_zip, posix_cksum, sha, BOOT_NAME, TAR_NAME
from package_ks_release import source_map
from ks_migration_inventory import ownership_manifest

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_VERSION = '9.7.6-5.20.1-vera-KS-test1'
RUNTIME_VERSION = '9.7.5-ks-test1'  # Existing internal KS path, not product identity.
OUT = ROOT / 'build/ks-test1'
ARCHIVE = OUT / (PRODUCT_VERSION + '.zip')


def sources():
    files = {name: path.read_bytes() for name, path in source_map().items()}
    for name in ('device_variant.sh', 'runtime-lock.sh', 'scanner.sh', 'performance.sh'):
        files['native-reading-time-package/compat/' + name] = (ROOT / 'native-reading-time-package/compat' / name).read_bytes()
    # Keep current KS migration and guard overrides from its own source map.
    bootstrap = '/mnt/us/documents/' + BOOT_NAME
    files['RUNME.sh'] = f'#!/bin/sh\n# READING_RECORDS_V4_RUNME\nexec /bin/sh "{bootstrap}"\n'.encode()
    files['README.txt'] = f'Kindle 阅读记录 {PRODUCT_VERSION}\n仅适用于 Kindle Scribe。解压外层 ZIP 一次，将两个文件复制到 documents 后点击安装。\n已有 KS 直接覆盖升级，不要先卸载；历史统计保留。\n'.encode()
    files['documents/reading-records-ks-install.sh'] = f'#!/bin/sh\n# Name: 安装阅读记录 KS\nexec /bin/sh "{bootstrap}"\n'.encode()
    kual = f'''#!/bin/sh
ACTION="${{1:-diagnostics}}"
case "$ACTION" in
    install|upgrade|repair) exec /bin/sh "{bootstrap}";;
    cleanup) exec /bin/sh /mnt/us/documents/reading-records-install-cleanup.sh;;
    force-exit) exec /bin/sh /mnt/us/reading-time/bin/force-exit-ks.sh;;
    diagnostics) exec /bin/sh /mnt/us/reading-time/bin/diagnostics-ks.sh;;
esac
exit 127
'''.encode()
    for name in ('extensions/reading-records-installer/bin/action.sh', 'native-reading-time-package/resources/kual/reading-records-installer/bin/action.sh'):
        files[name] = kual
    files['V4-PAYLOAD'] = f'installer_format=two-file-1\nproduct_version={PRODUCT_VERSION}\nvariant=ks\n'.encode()
    files['v4/cleanup.sh'] = (ROOT / 'ks-package/v4/cleanup.sh').read_bytes()
    files['native-reading-time-package/migration-manifest.tsv'] = ownership_manifest(files, posix_cksum)
    build_id = sha(b''.join(name.encode() + b'\0' + sha(raw).encode() for name, raw in sorted(files.items())))[:20]
    files['BUILD-INFO'] = f'product_version={PRODUCT_VERSION}\nvariant=ks\nbuild_id={build_id}\n'.encode()
    entries = [{'path': name, 'size': len(raw), 'sha256': sha(raw)} for name, raw in sorted(files.items())]
    files['PACKAGE-MANIFEST-KS.json'] = (json.dumps({'format': 4, 'product_version': PRODUCT_VERSION, 'variant': 'ks', 'files': entries}, ensure_ascii=False, indent=2) + '\n').encode()
    return files


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    files = sources()
    assert 'native-reading-time-package/阅读记录-optimized.sh' not in files
    assert 'native-reading-time-package/Install-Native-Reading-Time-Optimized.sh' not in files
    raw = make_tar(files)
    template = (ROOT / 'ks-package/v4/bootstrap.template.sh').read_text(encoding='utf-8')
    device = (ROOT / 'native-reading-time-package/compat/device_variant.sh').read_text(encoding='utf-8') + '\n' + (ROOT / 'ks-package/native-reading-time-package/compat/ks_guard.sh').read_text(encoding='utf-8')
    build_id = files['BUILD-INFO'].decode().split('build_id=')[1].strip()
    substitutions = {'@DEVICE_VARIANT@': device, '@RUNTIME_VERSION@': RUNTIME_VERSION,
        '@LIFECYCLE@': (ROOT / 'native-reading-time-package/compat/lifecycle.sh').read_text(encoding='utf-8'),
        '@PRODUCT_VERSION@': PRODUCT_VERSION, '@BUILD_ID@': build_id, '@VARIANT@': 'ks',
        '@SIZE@': str(len(raw)), '@CKSUM@': str(posix_cksum(raw))}
    for key, value in substitutions.items():
        template = template.replace(key, value)
    boot = template.encode()
    make_zip(ARCHIVE, {BOOT_NAME: boot, TAR_NAME: raw})
    # Developer-only source archive for tests, not a third user delivery.
    make_zip(OUT / 'ks-payload.zip', files)
    report = {'product_version': PRODUCT_VERSION, 'variant': 'ks', 'build_id': build_id,
              'path': str(ARCHIVE), 'sha256': sha(ARCHIVE.read_bytes()), 'size': ARCHIVE.stat().st_size,
              'zip_top_level': [BOOT_NAME, TAR_NAME], 'payload_files': len(files)}
    (OUT / 'build-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
