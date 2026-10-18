"""An environment ZIP remains verifiable as other firmware assets are added."""
from copy import deepcopy
import json
import hashlib
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from verify_published_release import release_asset
import verify_published_release as verifier

report=json.loads((ROOT/'docs/releases/v9.8.1-verification.json').read_text(encoding='utf-8'))
asset={'name':report['zip_file'],'size':report['zip_size'],'state':'uploaded',
       'digest':'sha256:'+report['zip_sha256']}
release={'tag_name':report['tag'],'name':report['release_title'],'draft':False,'prerelease':False,
         'assets':[{'name':'another-firmware.zip'},asset,{'name':'SHA256SUMS.txt'}]}
assert release_asset(release,report)==asset

for fault in ('missing','duplicate','digest','size','state','tag','draft','prerelease'):
    bad=deepcopy(release)
    if fault=='missing':bad['assets'].pop(1)
    elif fault=='duplicate':bad['assets'].append(deepcopy(asset))
    elif fault=='digest':bad['assets'][1]['digest']='sha256:'+'0'*64
    elif fault=='size':bad['assets'][1]['size']+=1
    elif fault=='state':bad['assets'][1]['state']='new'
    elif fault=='tag':bad['tag_name']='v9.7.6'
    else:bad[fault]=True
    try:release_asset(bad,report)
    except AssertionError:pass
    else:raise AssertionError('Accepted invalid release asset: '+fault)
print('PASS: future firmware assets coexist; missing/duplicate/tampered/unpublished assets rejected')

# A Windows checkout can preserve the accepted XML's CRLF bytes. Linux CI
# must accept only its recorded exact Git blob, without normalizing other data.
with tempfile.TemporaryDirectory(prefix='release-source-') as name:
    verifier.ROOT=Path(name)
    raw=b'approved\r\n'
    sample={'variant':'standard','tag':'v9.8.1','release_version':'9.8.1','product_version':'9.8.1-5.20-vera',
            'production_source_sha256':{'sample.xml':hashlib.sha256(raw).hexdigest()},
            'source_checkout_line_endings':{'sample.xml':{'git_blob_sha256':hashlib.sha256(b'approved\n').hexdigest()}}}
    p=verifier.ROOT/'sample.xml'
    for data in (raw,b'approved\n'):
        p.write_bytes(data);verifier.verify_source(sample)
    p.write_bytes(b'changed\n')
    try:verifier.verify_source(sample)
    except AssertionError:pass
    else:raise AssertionError('Accepted changed production source')
print('PASS: exact recorded Windows/Linux source bytes accepted; changed source rejected')
