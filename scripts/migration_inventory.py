"""Derive ownership from actual historical bytes, never from display names."""
from functools import lru_cache
import io
import re
from pathlib import Path
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def ownership_manifest(current, checksum, make_tar):
    records = set()
    sums = {}
    def add(kind, path, raw, origin):
        key = __import__('hashlib').sha256(raw).digest()
        if key not in sums:
            sums[key] = checksum(raw)
        records.add((kind, path, str(sums[key]), str(len(raw)), origin))

    def inventory(files, origin, normal=False):
        prefix = 'native-reading-time-package/'
        for path, raw in files.items():
            if path.startswith('documents/'):
                # Unsubstituted historical bootstrap templates aren't installed bytes.
                if b'@PAYLOAD_' not in raw:
                    add('entry', path.removeprefix('documents/'), raw, origin)
            if path.startswith(prefix):
                add('payload', path.removeprefix(prefix), raw, origin)
            elif path in ('RUNME.sh', 'README.txt', 'PACKAGE-MANIFEST.json', 'V4-PAYLOAD') or path.startswith('extensions/'):
                add('root', path, raw, origin)
        if normal:
            required={'install.sh','install-manifest.txt','cleanup-manifest.txt','resources/reading-records-install-cleanup.sh'}
            manifest=files.get(prefix+'install-manifest.txt',b'').decode('utf-8')
            required.update(line.split('\t')[0] for line in manifest.splitlines() if len(line.split('\t'))==4)
            old_sources={name:files[prefix+name] for name in sorted(required)}
            old_manifest=''.join(f"{checksum(raw)}\t{len(raw)}\t{name}\n" for name,raw in old_sources.items()).encode()
            old_sources['payload-manifest.tsv']=old_manifest
            old_tar=make_tar({prefix+name:raw for name,raw in old_sources.items()})
            template=files['documents/reading-records-9.7.6-install.sh'].decode()
            compiled=template.replace('@PAYLOAD_CKSUM@',str(checksum(old_tar))).replace('@PAYLOAD_SIZE@',str(len(old_tar))).encode()
            add('entry','reading-records-9.7.6-install.sh',compiled,origin)
            add('archive','reading-records-9.7.6-data.tar',old_tar,origin)
            add('payload','payload-manifest.tsv',old_manifest,origin)
            if prefix + "resources/reading-records-install-cleanup.sh" in files:
                add("entry", "reading-records-install-cleanup.sh", files[prefix + "resources/reading-records-install-cleanup.sh"], origin)
            manifest = files.get(prefix + 'install-manifest.txt', b'').decode('utf-8')
            for line in manifest.splitlines():
                fields = line.split('\t')
                if len(fields) != 4:
                    continue
                src, category, dst, _ = fields
                if prefix + src not in files:
                    continue
                if category == 'docs':
                    add('entry', dst, files[prefix + src], origin)
                elif category == 'release':
                    add('release', '9.7.6-5.19-normal/' + dst, files[prefix + src], origin)
            return
        ui_source=files.get(prefix+'阅读记录-optimized.sh',b'').decode('utf-8',errors='replace')
        match=re.search(r'\$BASE/releases/([0-9A-Za-z.-]+)',ui_source)
        release_id=match.group(1) if match else '9.7.5-test'
        for path, raw in files.items():
            if not path.startswith(prefix):
                continue
            rel = path.removeprefix(prefix)
            dst = None
            if rel == '阅读记录-optimized.sh':
                dst = 'bin/reading-records.sh'
            elif rel == '阅读记录.sh':
                dst = 'bin/reading-records-v9.6.3.sh'
            elif rel.startswith('reading-insights-') and rel.endswith(('.lua', '.awk', '.sh')):
                dst = 'bin/' + rel
            elif rel.startswith(('ui/', 'ui-calendar/', 'render-assets/')):
                dst = rel
            elif rel == 'launcher-icon.png':
                dst = 'assets/' + rel
            if dst:
                add('release', release_id + '/' + dst, raw, origin)
        for src, dst in [('阅读记录-entry.sh', '阅读记录.sh'), ('resources/reading-records-uninstall.sh', 'reading-records-uninstall.sh')]:
            if prefix + src in files:
                add('entry', dst, files[prefix + src], origin)
        for src in ('阅读记录-entry.sh','阅读记录-optimized.sh'):
            if prefix+src in files:
                add('entry',src,files[prefix+src],origin)
        if origin == 'v9.7.4':
            add('entry', '阅读记录.sh', files[prefix + '阅读记录-optimized.sh'], origin)

    for tag in ('v9.7.4', 'v9.7.5-test.1', 'v9.7.5-compat-v2', 'v9.7.5-compat-v3', 'v9.7.6-5.19-vera'):
        names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', '-z', tag], cwd=ROOT).decode('utf-8').rstrip('\0').split('\0')
        files = {name: subprocess.check_output(['git', 'show', tag + ':' + name], cwd=ROOT)
                 for name in names if name.startswith(('native-reading-time-package/', 'documents/', 'extensions/')) or name in ('RUNME.sh', 'README.txt')}
        inventory(files, tag, normal=tag.endswith('5.19-vera'))
    for path in sorted((ROOT / 'dist').glob('kindle-reading-records-v9.7*.zip')):
        with zipfile.ZipFile(path) as archive:
            inventory({n: archive.read(n) for n in archive.namelist() if not n.endswith('/')}, path.stem)
    baseline = ROOT / 'build/standard-next-baseline/artifacts/9.7.6-5.20.1-vera.zip'
    with zipfile.ZipFile(baseline) as outer:
        boot = outer.read('reading-records-v4-install.sh')
        payload = outer.read('阅读记录安装数据.tar')
        with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
            files = {m.name: archive.extractfile(m).read() for m in archive if m.isfile()}
        inventory(files, '9.7.6-5.20.1-vera')
        add('entry', 'reading-records-v4-install.sh', boot, '9.7.6-5.20.1-vera')
        add('entry', '安装好之后，确认无误了再点这个.sh', files['v4/cleanup.sh'], '9.7.6-5.20.1-vera')
    # Prior Standard test releases become part of the next build's ownership
    # history. Skip this same product version to avoid self-referential hashes.
    current_version=current['V4-PAYLOAD'].decode().split('product_version=')[1].splitlines()[0]
    for previous in sorted((ROOT/'dist').rglob('9.7.6-*-test*.zip')):
        with zipfile.ZipFile(previous) as outer:
            if '阅读记录安装数据.tar' not in outer.namelist():
                continue
            with tarfile.open(fileobj=io.BytesIO(outer.read('阅读记录安装数据.tar'))) as archive:
                files={m.name:archive.extractfile(m).read() for m in archive if m.isfile()}
            identity=files.get('BUILD-INFO',b'').decode('utf-8')
            if 'variant=standard\n' not in identity or f'product_version={current_version}\n' in identity:
                continue
            origin=identity.split('product_version=')[1].splitlines()[0]
            inventory(files,origin)
            add('entry','reading-records.sh',files['native-reading-time-package/阅读记录-entry.sh'],origin)
            add('entry','reading-records-install-cleanup.sh',files['v4/cleanup.sh'],origin)
    # Earlier 5.19-normal revisions used the same deployed product directory.
    # Accept actual historical bytes, including launcher/lock safety refinements.
    revisions=subprocess.check_output(['git','log','--all','--format=%H','--','native-reading-time-package/launch.sh'],cwd=ROOT).decode().splitlines()
    for revision in revisions:
        launcher=subprocess.check_output(['git','show',revision+':native-reading-time-package/launch.sh'],cwd=ROOT)
        if b'releases/9.7.6-5.19-normal' not in launcher:
            continue
        add('entry','reading-records.sh',launcher,revision[:12])
        for src,dst in [('阅读记录-optimized.sh','reading-records-ui.sh'),('runtime-child.sh','runtime-child.sh'),('runtime-lock.sh','runtime-lock.sh'),('reading-insights-touch-ui.lua','reading-insights-touch-ui.lua')]:
            item=subprocess.run(['git','show',revision+':native-reading-time-package/'+src],cwd=ROOT,capture_output=True)
            if item.returncode==0:
                add('release','9.7.6-5.19-normal/bin/'+dst,item.stdout,revision[:12])
    inventory(current, 'current')
    # Current formal entry deliberately keeps the old short ASCII path.
    add('entry', 'reading-records.sh', current['native-reading-time-package/阅读记录-entry.sh'], 'current')
    add('entry', 'reading-records-install-cleanup.sh', current['v4/cleanup.sh'], 'current')
    return ''.join('\t'.join(row) + '\n' for row in sorted(records)).encode('utf-8')
