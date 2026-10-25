"""Guard download choices, immutable identities, Unicode URLs and public cleanup."""
from copy import deepcopy
from pathlib import Path
import json, sys, urllib.parse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from verify_download_matrix import release_assets

matrix = json.loads((ROOT/'docs/releases/v9.8.1-downloads.json').read_text(encoding='utf-8'))
release = {'id': 416331823, 'tag_name': 'v9.8.1', 'name': matrix['release_title'],
           'draft': False, 'prerelease': False, 'assets': []}
for row in matrix['packages']:
    release['assets'].append({'name': row['asset_name'], 'size': row['zip_size'],
                             'label': row['asset_label'],
                             'digest': 'sha256:'+row['zip_sha256'], 'state': 'uploaded',
                             'browser_download_url': 'https://github.com/L-1116/kindle-reading-records-enhanced/releases/download/v9.8.1/'+urllib.parse.quote(row['asset_name'])})
assert set(release_assets(release, matrix)) == {'test12', '519', 'test11', 'test10'}

faults = ('missing', 'duplicate', 'extra_checksum', 'swapped_digest', 'bad_size', 'upload_pending', 'wrong_label',
          'old_filename', 'wrong_repository', 'wrong_host', 'wrong_tag', 'draft', 'prerelease')
for fault in faults:
    bad = deepcopy(release)
    if fault == 'missing': bad['assets'].pop()
    elif fault == 'duplicate': bad['assets'][-1] = deepcopy(bad['assets'][0])
    elif fault == 'extra_checksum': bad['assets'].append({'name': 'SHA256SUMS.txt'})
    elif fault == 'swapped_digest': bad['assets'][0]['digest'] = bad['assets'][2]['digest']
    elif fault == 'bad_size': bad['assets'][0]['size'] += 1
    elif fault == 'upload_pending': bad['assets'][0]['state'] = 'new'
    elif fault == 'wrong_label': bad['assets'][0]['label'] = '备用包'
    elif fault == 'old_filename': bad['assets'][0]['name'] = 'Kindle-Reading-Records-v9.8.1-5.20-vera.zip'
    elif fault == 'wrong_repository': bad['assets'][0]['browser_download_url'] = bad['assets'][0]['browser_download_url'].replace('/L-1116/', '/another-owner/')
    elif fault == 'wrong_host': bad['assets'][0]['browser_download_url'] = bad['assets'][0]['browser_download_url'].replace('github.com', 'example.com')
    elif fault == 'wrong_tag': bad['tag_name'] = 'v9.8.2'
    else: bad[fault] = True
    try:
        release_assets(bad, matrix)
    except AssertionError:
        pass
    else:
        raise AssertionError('Accepted bad public release: '+fault)

for name in ('README.md', 'docs/releases/v9.8.1.md', 'docs/安装与回滚.md'):
    text = (ROOT/name).read_text(encoding='utf-8')
    for asset in release['assets']:
        assert text.count(asset['browser_download_url']) == 1, (name, asset['name'])
    assert '5.20.1.0.2' in text and '不要混用' in text and 'SH Integration' in text
    assert '不推荐 KC 使用' in text and '青春版完整实测' in text
    assert '拒绝直接降级' in text and '不要手动删除入口或绕过校验' in text
    assert 'Source code' in text and '不是 Kindle 安装包' in text
    assert 'before-color-fix.zip' not in text and 'before-bluetooth-fix.zip' not in text

assert matrix['packages'][0]['zip_sha256'] == 'e9244390c95db80f1dd5b02ef6d76f38ef133a066548541364d5a9430af95562'
assert matrix['packages'][-1]['product_version'] == '9.8.1-5.20-vera'
assert len({r['source_commit'] for r in matrix['packages']}) == 4
print('PASS: four roles; 13 invalid release cases; three consistent choice/install pages; pinned originals')
