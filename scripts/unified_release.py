"""Prepare a traceable release; remote writes are limited to explicit draft uploads.

No installer is executed by this tool. Approved archives are copied byte for byte.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX = ROOT / 'release/9.7.6.json'
PREFIX = 'native-reading-time-package/'
STATUSES = {'hardware': '已完成真机测试', 'automated': '通过自动化测试，等待真机验证',
            'experimental': '实验性构建', 'unbuilt': '尚未构建', 'paused': '暂停开发'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def git(*args, cwd=ROOT):
    return subprocess.check_output(['git', *args], cwd=cwd)


def blob(commit, name):
    return git('show', commit + ':' + name)


def safe_name(name):
    p = PurePosixPath(name)
    require(bool(name) and not p.is_absolute() and '..' not in p.parts
            and '\\' not in name and ':' not in name and str(p) == name,
            'Unsafe archive path: ' + name)


def cksum(data):
    table = []
    for v in range(256):
        crc = v << 24
        for _ in range(8):
            crc = ((crc << 1) ^ (0x04C11DB7 if crc & 0x80000000 else 0)) & 0xffffffff
        table.append(crc)
    crc = 0
    for v in data:
        crc = ((crc << 8) ^ table[((crc >> 24) ^ v) & 255]) & 0xffffffff
    length = len(data)
    while length:
        crc = ((crc << 8) ^ table[((crc >> 24) ^ length) & 255]) & 0xffffffff
        length >>= 8
    return (~crc) & 0xffffffff


def load_matrix(path):
    m = read_json(path)
    require(re.fullmatch(r'\d+\.\d+\.\d+', m['version']), 'Invalid formal version')
    require(m['tag'] == 'v' + m['version'], 'One formal version must use one canonical tag')
    require(re.fullmatch(r'[0-9a-f]{40}', m['baseline_commit']), 'Baseline must be a full commit')
    require(git('rev-parse', m['baseline_commit'] + '^{commit}').decode().strip() == m['baseline_commit'],
            'Baseline commit unavailable')
    ids, names = set(), set()
    for v in m['variants']:
        require(v['id'] not in ids, 'Duplicate variant ID'); ids.add(v['id'])
        require(v['status'] in STATUSES, 'Unknown verification status')
        expected = f"Kindle-Reading-Records-v{m['version']}-{v['firmware_label']}-{v['jailbreak']}"
        require(v['variant'] in ('standard', 'ks'), 'Unknown device variant')
        expected += '-KS.zip' if v['variant'] == 'ks' else '.zip'
        require(v['asset_name'] == expected and re.fullmatch(r'[A-Za-z0-9.-]+', expected), 'Invalid asset name')
        require(expected.lower() not in names, 'Conflicting asset filenames'); names.add(expected.lower())
        if v['publish']:
            require(v['status'] == 'hardware' and v.get('hardware_evidence'), 'Formal assets require hardware evidence')
            require(v.get('sha256') and re.fullmatch('[0-9a-f]{64}', v['sha256']), 'Approved SHA-256 required')
            require(re.fullmatch('[0-9a-f]{40}', v['source_commit']), 'Pinned source commit required')
            require(v['product_version'].startswith(m['version'] + '-'), 'Cannot relabel an older product version')
            require(v['variant'] != 'ks', 'KS builds and delivery are paused; enable only after a separately reviewed policy change')
    return m


def select_release_commit(m, commit):
    """Bind a reviewed tooling commit to the tag without relabelling ZIP sources."""
    require(re.fullmatch(r'[0-9a-f]{40}', commit), 'Release commit must be a full SHA')
    require(git('rev-parse', commit + '^{commit}').decode().strip() == commit, 'Release commit unavailable')
    runtime = m['baseline_commit']
    require(git('merge-base', runtime, commit).decode().strip() == runtime,
            'Release commit must descend from the approved Standard runtime baseline')
    protected = ('native-reading-time-package', 'v4', 'documents', 'extensions',
                 'RUNME.sh', 'README.txt', '.gitattributes', 'scripts/build_v4.py',
                 'scripts/package_release.py', 'scripts/migration_inventory.py')
    require(not git('diff', '--name-only', runtime, commit, '--', *protected).strip(),
            'Release commit changes approved runtime or mature build sources')
    require(blob(commit, 'scripts/unified_release.py') == Path(__file__).read_bytes(),
            'Release commit must contain the exact reviewed release script')
    require(json.loads(blob(commit, f"release/{m['version']}.json")) == m,
            'Release commit must contain the reviewed compatibility matrix')
    require(bool(blob(commit, '.github/workflows/unified-release.yml')),
            'Release commit must include the release workflow')
    return {**m, 'runtime_baseline_commit': runtime, 'baseline_commit': commit}


def verify_archive(raw, v):
    require(sha(raw) == v['sha256'] and len(raw) == v['size'], 'Archive differs from approved bytes: ' + v['id'])
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        require(z.testzip() is None and z.namelist() == v['top_level'], 'Unexpected ZIP structure')
        require(len(set(z.namelist())) == len(z.namelist()) == 2, 'ZIP must contain exactly two distinct files')
        for i in z.infolist():
            safe_name(i.filename)
            require(not i.is_dir() and ((i.external_attr >> 16) & 0o170000) != 0o120000, 'ZIP links prohibited')
        boot, payload = (z.read(n) for n in v['top_level'])
    require(sha(boot) == v['bootstrap_sha256'] and sha(payload) == v['payload_sha256'], 'Bootstrap/payload identity mismatch')
    require(boot.startswith(b'#!/bin/sh\n# Name: ') and b'@PAYLOAD_' not in boot, 'Invalid install entry')
    require(v['top_level'][1].encode() in boot, 'Install entry does not reference the packaged TAR')
    with tarfile.open(fileobj=io.BytesIO(payload)) as t:
        members = t.getmembers()
        require(len({i.name for i in members}) == len(members), 'Duplicate TAR member')
        files = {}
        for i in members:
            safe_name(i.name)
            require(i.isfile(), 'TAR contains a link, directory or special file')
            files[i.name] = t.extractfile(i).read()
    require(len(files) == v['payload_files'], 'Unexpected payload count')
    required = {PREFIX + n for n in ('install.sh', 'install-manifest.txt', 'cleanup-manifest.txt',
                'launch.sh', 'native-reading-time-daemon.sh', 'native-reading-time.conf',
                '阅读记录-optimized.sh', '阅读记录.sh', 'reading-insights-touch-ui.lua',
                'reading-insights-render.lua', 'launcher-icon.png', 'NotoSansCJKsc-Regular.otf')}
    require(required <= files.keys(), 'Missing Standard runtime resources')
    require(not any(n.startswith('ks-package/') or n.endswith(('launch-ks.sh', '阅读记录-ks.sh',
                    '阅读记录-KS-entry.sh')) for n in files), 'KS resource in Standard archive')
    require(v['variant'] == 'standard', 'Unsupported adapter for device variant')
    installer = files[PREFIX + 'install.sh'].decode('utf-8')
    for marker in v['installer_markers']:
        require(marker in installer, 'Installer environment guard mismatch: ' + marker)
    # Frozen source checks bind compatibility claims to actual runtime bytes.
    commit = v['source_commit']
    if v['format'] == 'standard-v4':
        manifest = json.loads(files['PACKAGE-MANIFEST.json'])
        require(manifest['variant'] == 'standard' and manifest['product_version'] == v['product_version'], 'Wrong payload identity')
        rows = manifest['files']
        require(len({i['path'] for i in rows}) == len(rows), 'Duplicate manifest record')
        require(set(files) == {i['path'] for i in rows} | {'PACKAGE-MANIFEST.json'}, 'Manifest file set mismatch')
        for i in rows:
            data = files[i['path']]
            require(len(data) == i['size'] and sha(data) == i['sha256'], 'Manifest integrity failure: ' + i['path'])
        report = json.loads(blob(commit, v['source_verification']))
        require(report['zip_sha256'] == v['sha256'], 'Frozen verification report differs')
        for name, digest in report['production_source_sha256'].items():
            require(sha(blob(commit, name)) == digest, 'Source commit differs from evidence: ' + name)
            # build_v4 generates the KUAL action wrapper instead of copying its
            # legacy source. The accepted whole-ZIP hash and payload manifest
            # above bind those generated bytes; all runtime files remain exact.
            if name in files and name != PREFIX + 'resources/kual/reading-records-installer/bin/action.sh':
                require(sha(files[name]) == digest, 'Runtime differs from verified source: ' + name)
        require(f"PRODUCT_VERSION='{v['product_version']}'".encode() in boot and b"VARIANT='standard'" in boot, 'Wrong bootstrap identity')
        require(f"PAYLOAD_SIZE='{len(payload)}'".encode() in boot and f"PAYLOAD_CKSUM='{cksum(payload)}'".encode() in boot, 'Bootstrap checksum mismatch')
    elif v['format'] == 'standard-976':
        manifest_name = PREFIX + 'payload-manifest.tsv'
        rows = [line.split('\t') for line in files[manifest_name].decode().splitlines()]
        require(all(len(i) == 3 for i in rows), 'Malformed payload manifest')
        require(len({i[2] for i in rows}) == len(rows), 'Duplicate payload manifest record')
        require(set(files) == {PREFIX + i[2] for i in rows} | {manifest_name}, 'Unlisted payload member')
        for crc, size, name in rows:
            raw_file = files[PREFIX + name]
            require(len(raw_file) == int(size) and cksum(raw_file) == int(crc), 'Payload checksum mismatch: ' + name)
            require(raw_file == blob(commit, PREFIX + name), 'Payload differs from pinned source: ' + name)
        template = blob(commit, 'documents/' + v['top_level'][0]).decode()
        expected_boot = template.replace('@PAYLOAD_CKSUM@', str(cksum(payload))).replace('@PAYLOAD_SIZE@', str(len(payload))).encode()
        require(boot == expected_boot, 'Bootstrap differs from source template')
        require(v['product_version'] in installer, 'Wrong installer product identity')
    else:
        raise ValueError('Unreviewed archive format: ' + v['format'])
    return {'sha256': sha(raw), 'size': len(raw), 'payload_files': len(files),
            'bootstrap_sha256': sha(boot), 'payload_sha256': sha(payload),
            'source_commit_verified': True, 'structure_verified': True}


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Kindle-Unified-Release'})
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read()


def resolve_archive(v, local, cache, allow_fetch):
    if v['id'] in local:
        return local[v['id']].read_bytes()
    path = cache / (v['sha256'] + '.zip')
    if path.exists():
        return path.read_bytes()
    require(allow_fetch, 'Missing approved archive; use --fetch or --local ' + v['id'] + '=PATH')
    raw = fetch(v['approved_asset_url'])
    require(sha(raw) == v['sha256'], 'Downloaded asset hash differs from approval')
    cache.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def rebuild(v):
    """Build an exact Git snapshot with only enumerated, hash-pinned external inputs."""
    require(v['variant'] == 'standard', 'KS builds are paused')
    spec = v['build']
    for i in spec.get('inputs', []):
        safe_name(i['destination'])
        p = ROOT / i['local_path']
        require(p.is_file() and sha(p.read_bytes()) == i['sha256'], 'Missing/changed sealed build input: ' + i['local_path'])
    with tempfile.TemporaryDirectory(prefix='kindle-release-build-') as temporary:
        snapshot = Path(temporary) / 'source'
        # A separate clone supplies history needed by migration_inventory without
        # touching existing branches or worktrees. No fetch, push or tag creation.
        subprocess.run(['git', '-c', 'core.autocrlf=false', 'clone', '--quiet', '--shared', '--no-checkout', str(ROOT), str(snapshot)], check=True)
        subprocess.run(['git', 'config', 'core.autocrlf', 'false'], cwd=snapshot, check=True)
        # XML has text=auto but no explicit eol in the existing repository.
        # Pin checkout line endings to the accepted LF bytes across platforms.
        subprocess.run(['git', 'config', 'core.eol', 'lf'], cwd=snapshot, check=True)
        subprocess.run(['git', 'checkout', '--quiet', '--detach', v['source_commit']], cwd=snapshot, check=True)
        if 'history_inventory' in spec:
            revisions = git('log', '--all', '--format=%H', '--', PREFIX + 'launch.sh', cwd=snapshot).decode().splitlines()
            inventory = sorted(c for c in revisions if b'releases/9.7.6-5.19-normal' in
                               git('show', c + ':' + PREFIX + 'launch.sh', cwd=snapshot))
            require(inventory == spec['history_inventory'], 'Migration history changed; rebuild inputs require review')
        for i in spec.get('inputs', []):
            target = snapshot / i['destination']; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / i['local_path'], target)
        safe_name(spec['script']); safe_name(spec['output'])
        subprocess.run([sys.executable, spec['script']], cwd=snapshot, check=True)
        raw = (snapshot / spec['output']).read_bytes()
        if sha(raw) != v['sha256']:
            # Diagnostic only: keep a source-vs-accepted comparison outside the
            # release output; the rebuilt ZIP is never staged or uploaded.
            approved = resolve_archive(v, {}, ROOT / 'build/release-cache', False)
            def contents(archive_bytes):
                with zipfile.ZipFile(io.BytesIO(archive_bytes)) as z:
                    with tarfile.open(fileobj=io.BytesIO(z.read(v['top_level'][1]))) as t:
                        return {i.name: t.extractfile(i).read() for i in t}
            old, new = contents(approved), contents(raw)
            differences = [n for n in sorted(set(old) | set(new)) if old.get(n) != new.get(n)]
            report = {'id': v['id'], 'result': 'REJECTED', 'accepted_sha256': v['sha256'],
                      'rebuilt_sha256': sha(raw), 'different_payload_files': differences}
            name = PREFIX + 'migration-manifest.tsv'
            if name in old and name in new:
                expected, actual = set(old[name].decode().splitlines()), set(new[name].decode().splitlines())
                report['missing_inventory_records'] = sorted(expected - actual)
                report['extra_inventory_records'] = sorted(actual - expected)
            diagnostic = ROOT / 'build/unified-release-audit'; diagnostic.mkdir(parents=True, exist_ok=True)
            write_json(diagnostic / (v['id'] + '-rebuild-mismatch.json'), report)
            raise ValueError('Rebuild differs from accepted ZIP; requires new validation before release')
        return raw


def notes(m, selected):
    rows = ['| 固件版本 | 越狱方式 | 适用机型 | 安装包名称 | 验证状态 |', '|---|---|---|---|---|']
    for v in selected:
        rows.append(f"| {v['firmware_scope']} | {v['jailbreak']} | {v['models']} | `{v['asset_name']}` | {STATUSES[v['status']]}：{v['hardware_scope']} |")
    parts = [f"# {m['title']}", '## 1. 版本介绍', m['introduction'],
             '## 2. 本次更新', '\n'.join('- ' + s for s in m['changes']),
             '## 3. 安装包选择指南', '\n'.join(rows),
             '文件名中的固件段是选择标签，实际兼容范围以表格为准。KS 表示 Kindle Scribe；普通版禁止覆盖 KS。',
             '### 尚未纳入正式下载', '\n'.join(f"- {v['firmware_scope']} / {v['jailbreak']} / {v['models']}：{STATUSES[v['status']]}。{v['reason']}" for v in m['variants'] if not v['publish']),
             '## 4. 安装与升级教程',
             '先备份 Kindle 的 `reading-time` 文件夹。解压所选 ZIP 一次，将得到的脚本与 TAR 一起复制到 Kindle `documents`；不要再解压 TAR。安全弹出后点击书库“安装阅读记录”。旧普通版使用相同步骤原地升级，保留原数据，无需先卸载。打开“阅读记录”，确认历史和新增计时正常，再执行安装文件清理。',
             '各包的真实文件名和入口要求如下：']
    for v in selected:
        parts.append(f"- **{v['firmware_scope']} / {v['jailbreak']}**：`{v['top_level'][0]}` + `{v['top_level'][1]}`。{v['entry_requirement']} 清理入口：**{v['cleanup_label']}**。")
    parts += ['未配置相应书库脚本执行支持的设备不能直接使用这些简易包；其他越狱环境须先独立确认其安装入口，不假定支持相同步骤。',
              '## 5. 注意事项',
              '- 从 Assets 下载匹配环境的安装 ZIP；GitHub 自动生成的 **Source code (zip / tar.gz) 不是 Kindle 安装包**。\n- 升级保留阅读历史、配置与封面缓存；不要手动删除 `reading-time`。清理不是卸载，归属不明的文件及必要回滚资源应保留。\n- 实机成功仅限表内所列证据，自动化测试不能替代设备验证。失败时保留安装文件和备份，通过仓库 Issues 提供机型、固件、越狱方式、步骤及已有错误信息；异常日志仅用于售后，不要求普通用户运行命令或选择 runtime。',
              '### 来源追溯', f"统一 Tag `{m['tag']}` 的发布基线：`{m['baseline_commit']}`；各包来自独立提交，未合并运行分支。"]
    for v in selected:
        parts.append(f"- `{v['asset_name']}`：来源提交 `{v['source_commit']}`，包内身份 `{v['product_version']}`；[原附件]({v['approved_asset_url']})，[验收证据]({v['hardware_evidence']})。")
    if 'runtime_baseline_commit' in m:
        parts.append(f"Tag 包含统一发布工程，Standard 运行源码基线仍为 `{m['runtime_baseline_commit']}`。Tag 不代表三个环境包均从同一运行分支构建；复现时按每个包的 source_commit 和固定构建输入检出。")
    parts += ['## 6. 文件校验', '下载同页 `SHA256SUMS.txt`，或核对以下 SHA-256：',
              '```text\n' + ''.join(f"{v['sha256']}  {v['asset_name']}\n" for v in selected) + '```']
    return '\n\n'.join(parts) + '\n'


def prepare(m, output, local, allow_fetch=False, do_rebuild=False):
    selected = [v for v in m['variants'] if v['publish']]
    require(selected, 'No verified formal assets')
    require(set(local) <= {v['id'] for v in selected}, 'Unknown or unapproved --local variant')
    expected = {v['asset_name'] for v in selected} | {'SHA256SUMS.txt', 'release-manifest.json', 'RELEASE.md'}
    if output.exists():
        require({p.name for p in output.iterdir()} <= expected, 'Output contains historical/test/unexpected files')
    prepared, records = {}, []
    for v in selected:
        raw = rebuild(v) if do_rebuild else resolve_archive(v, local, ROOT / 'build/release-cache', allow_fetch)
        verified = verify_archive(raw, v)
        prepared[v['asset_name']] = raw
        records.append({**{k: v[k] for k in ('id', 'asset_name', 'source_commit', 'source_branch', 'product_version',
                        'firmware_scope', 'jailbreak', 'models', 'variant', 'status', 'hardware_scope',
                        'hardware_evidence', 'approved_asset_url', 'top_level', 'entry_requirement')}, **verified})
    prepared['SHA256SUMS.txt'] = ''.join(f"{v['sha256']}  {v['asset_name']}\n" for v in selected).encode('ascii')
    prepared['RELEASE.md'] = notes(m, selected).encode('utf-8')
    provenance = {'format': 1, 'tag': m['tag'], 'version': m['version'],
                  'baseline_commit': m['baseline_commit'], 'assets': records}
    if 'runtime_baseline_commit' in m:
        provenance['runtime_baseline_commit'] = m['runtime_baseline_commit']
    prepared['release-manifest.json'] = (json.dumps(provenance, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    # A reviewed directory is immutable locally as well. Use a new output for changes.
    for name, raw in prepared.items():
        if (output / name).exists():
            require((output / name).read_bytes() == raw, 'Refusing to overwrite changed staged file: ' + name)
    output.mkdir(parents=True, exist_ok=True)
    for name, raw in prepared.items():
        if not (output / name).exists():
            (output / name).write_bytes(raw)
    return records


def gh(*args, binary=False):
    result = subprocess.run(['gh', *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout if binary else result.stdout.decode('utf-8')


def gh_api(repo, path):
    try:
        return json.loads(gh('api', f'repos/{repo}/{path}'))
    except subprocess.CalledProcessError as e:
        if b'HTTP 404' in e.stderr:
            return None
        raise


def verify_remote_assets(repo, release, desired, complete=False):
    assets = release['assets']
    names = [a['name'] for a in assets]
    require(len(set(names)) == len(names), 'Duplicate remote assets')
    require(set(names) <= set(desired), 'Unexpected remote asset; do not delete it automatically')
    if complete:
        require(set(names) == set(desired), 'Incomplete uploaded asset list')
    for a in assets:
        raw = desired[a['name']]
        require(a['state'] == 'uploaded' and a['size'] == len(raw), 'Remote asset is incomplete')
        if a.get('digest'):
            require(a['digest'] == 'sha256:' + sha(raw), 'Remote name collision with different bytes: ' + a['name'])
        else:
            downloaded = gh('api', f"repos/{repo}/releases/assets/{a['id']}", '-H', 'Accept: application/octet-stream', binary=True)
            require(sha(downloaded) == sha(raw), 'Remote asset download hash mismatch')
    return set(names)


def upload_draft(m, output):
    repo, tag = m['repository'], m['tag']
    ref = gh_api(repo, 'git/ref/tags/' + tag)
    require(ref is not None, 'Create and push the reviewed baseline tag separately; this tool never creates tags')
    obj = ref['object']
    while obj['type'] == 'tag':
        obj = gh_api(repo, 'git/tags/' + obj['sha'])['object']
    require(obj['type'] == 'commit' and obj['sha'] == m['baseline_commit'], 'Remote tag points to a different baseline')
    settings = gh_api(repo, 'immutable-releases')
    require(settings is not None and isinstance(settings.get('enabled'), bool), 'Cannot confirm release immutability setting')
    release = gh_api(repo, 'releases/tags/' + tag)
    # Match by tag and title across all pages, including hidden drafts.
    pages = json.loads(gh('api', f'repos/{repo}/releases?per_page=100', '--paginate', '--slurp'))
    matching = [r for page in pages for r in page if r['tag_name'] == tag or r['name'] == m['title']]
    require(len(matching) <= 1 and (not matching or matching[0]['tag_name'] == tag), 'Conflicting formal release')
    if matching:
        release = matching[0]
    if release is not None:
        require(release['draft'] and not release.get('immutable', False) and not release['prerelease'], 'Only mutable formal drafts may be changed')
    desired = {v['asset_name']: (output / v['asset_name']).read_bytes() for v in m['variants'] if v['publish']}
    for v in m['variants']:
        if v['publish']:
            require(sha(desired[v['asset_name']]) == v['sha256'] and len(desired[v['asset_name']]) == v['size'],
                    'Staged ZIP changed before upload: ' + v['asset_name'])
    desired['SHA256SUMS.txt'] = (output / 'SHA256SUMS.txt').read_bytes()
    desired['release-manifest.json'] = (output / 'release-manifest.json').read_bytes()
    sums = ''.join(f"{v['sha256']}  {v['asset_name']}\n" for v in m['variants'] if v['publish']).encode('ascii')
    require(desired['SHA256SUMS.txt'] == sums, 'Staged checksums differ from selected assets')
    require((output / 'RELEASE.md').read_text(encoding='utf-8') == notes(m, [v for v in m['variants'] if v['publish']]),
            'Staged notes differ from selected assets')
    manifest = json.loads(desired['release-manifest.json'])
    require(manifest['tag'] == tag and manifest['baseline_commit'] == m['baseline_commit'], 'Staged provenance has wrong baseline')
    require(manifest.get('runtime_baseline_commit') == m.get('runtime_baseline_commit'),
            'Staged provenance has wrong runtime baseline')
    rows = manifest['assets']
    require(len(rows) == len(desired) - 2 and {r['asset_name'] for r in rows} == set(desired) - {'SHA256SUMS.txt', 'release-manifest.json'},
            'Staged provenance asset set differs')
    for v in m['variants']:
        if v['publish']:
            row = next(r for r in rows if r['asset_name'] == v['asset_name'])
            for key in ('source_commit', 'sha256', 'firmware_scope', 'jailbreak', 'models', 'product_version'):
                require(row[key] == v[key], 'Staged provenance differs: ' + key)
    existing = verify_remote_assets(repo, release, desired) if release else set()
    if release is None:
        gh('release', 'create', tag, '--repo', repo, '--draft', '--verify-tag', '--title', m['title'],
           '--notes', '附件校验尚未完成；请勿公开发布。')
    for name in sorted(set(desired) - existing):
        # Recheck draft immediately before each mutation; no --clobber or deletion.
        current = gh_api(repo, 'releases/tags/' + tag)
        require(current and current['draft'] and not current.get('immutable', False), 'Draft state changed during upload')
        require((output / name).read_bytes() == desired[name], 'Staged asset changed during upload')
        gh('release', 'upload', tag, str(output / name), '--repo', repo)
    current = gh_api(repo, 'releases/tags/' + tag)
    require(current and current['draft'] and not current.get('immutable', False), 'Release is no longer a draft')
    verify_remote_assets(repo, current, desired, complete=True)
    gh('release', 'edit', tag, '--repo', repo, '--draft=true', '--title', m['title'], '--notes-file', str(output / 'RELEASE.md'))
    final = gh_api(repo, 'releases/tags/' + tag)
    require(final['draft'] and final['name'] == m['title'] and final['body'] == (output / 'RELEASE.md').read_text(encoding='utf-8'), 'Draft notes verification failed')
    verify_remote_assets(repo, final, desired, complete=True)
    return {'draft': True, 'url': final['html_url'], 'immutable_settings': settings,
            'assets_verified': sorted(desired), 'published': False}


def api_read(path, token=None):
    headers = {'User-Agent': 'Kindle-Release-Audit', 'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2026-03-10'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    with urllib.request.urlopen(urllib.request.Request('https://api.github.com/' + path, headers=headers), timeout=60) as response:
        return json.load(response)


def audit(repo, output, authenticated=False):
    token = None
    if authenticated:
        token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
        if not token:
            result = subprocess.run(['git', 'credential', 'fill'], input=b'protocol=https\nhost=github.com\n\n',
                capture_output=True, env={**os.environ, 'GCM_INTERACTIVE': 'never', 'GIT_TERMINAL_PROMPT': '0'})
            token = dict(line.split('=', 1) for line in result.stdout.decode().splitlines() if '=' in line).get('password')
        require(token, 'Noninteractive GitHub credentials unavailable')
    output.mkdir(parents=True, exist_ok=True)
    for name in ('releases', 'tags', 'branches'):
        rows, page = [], 1
        while True:
            data = api_read(f'repos/{repo}/{name}?per_page=100&page={page}', token)
            rows.extend(data)
            if len(data) < 100:
                break
            page += 1
        write_json(output / (name + '.json'), rows)
    settings = api_read(f'repos/{repo}/immutable-releases', token)
    write_json(output / 'immutability.json', settings)
    write_json(output / 'latest.json', api_read(f'repos/{repo}/releases/latest', token))
    write_json(output / 'local.json', {'head': git('rev-parse', 'HEAD').decode().strip(),
               'worktrees': git('worktree', 'list', '--porcelain').decode(),
               'status': git('status', '--short').decode('utf-8'), 'drafts_visible': authenticated})
    print(json.dumps({'releases': len(read_json(output / 'releases.json')), 'tags': len(read_json(output / 'tags.json')),
                     'immutable': settings, 'output': str(output)}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'audit'], nargs='?', default='prepare')
    parser.add_argument('--matrix', type=Path, default=DEFAULT_MATRIX)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--release-commit', help='Full reviewed tooling SHA for the tag; preserves each ZIP source SHA')
    parser.add_argument('--local', action='append', default=[], metavar='ID=PATH')
    parser.add_argument('--fetch', action='store_true', help='Download only hash-pinned approved assets')
    parser.add_argument('--rebuild', action='store_true', help='Build pinned isolated source snapshots; require exact approved hashes')
    parser.add_argument('--upload-draft', action='store_true', help='Explicitly create/resume a draft via gh; never publish')
    parser.add_argument('--authenticated', action='store_true', help='Audit hidden drafts using existing credentials')
    args = parser.parse_args()
    if args.action == 'audit':
        require(not args.upload_draft and not args.rebuild and not args.release_commit, 'Audit is read-only')
        return audit('L-1116/kindle-reading-records-enhanced', args.output or ROOT / 'build/unified-release-audit', args.authenticated)
    m = load_matrix(args.matrix)
    if args.release_commit:
        m = select_release_commit(m, args.release_commit)
    output = (args.output or ROOT / ('dist/unified/v' + m['version'])).resolve()
    local = {}
    for item in args.local:
        key, value = item.split('=', 1)
        require(key not in local, 'Duplicate --local variant')
        local[key] = Path(value)
    records = prepare(m, output, local, args.fetch, args.rebuild)
    result = {'result': 'PASS', 'mode': 'dry-run', 'tag': m['tag'], 'baseline': m['baseline_commit'],
              'output': str(output), 'archives': len(records), 'published': False}
    if args.upload_draft:
        result.update(upload_draft(m, output)); result['mode'] = 'draft-upload'
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, urllib.error.URLError) as error:
        # Do not include subprocess stdout/stderr, which may contain credentials.
        print('Release preparation failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
