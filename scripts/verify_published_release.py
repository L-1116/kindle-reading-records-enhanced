"""Verify frozen formal-release sources and original asset without rebuilding."""
from pathlib import Path
import argparse,hashlib,io,json,tarfile,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[1]
REPO='L-1116/kindle-reading-records-enhanced'
HISTORICAL_REPORT=ROOT/'docs/releases/9.7.6-5.20.1-vera-verification.json'
REPLACEMENT_REPORT=ROOT/'docs/releases/9.7.6-5.20.1-vera-replacement-verification.json'
CURRENT_REPORT=ROOT/'docs/releases/v9.8.1-verification.json'
REPORT=CURRENT_REPORT if CURRENT_REPORT.exists() else (REPLACEMENT_REPORT if REPLACEMENT_REPORT.exists() else HISTORICAL_REPORT)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def verify_source(report):
    for name,expected in report['production_source_sha256'].items():
        actual=sha((ROOT/name).read_bytes())
        alternate=report.get('source_checkout_line_endings',{}).get(name,{}).get('git_blob_sha256')
        assert actual==expected or (alternate and actual==alternate),'Frozen production source differs: '+name
    assert report['variant']=='standard' and report['tag']=='v'+report.get('release_version',report['product_version'])
def verify_zip(raw,report):
    assert len(raw)==report['zip_size'] and sha(raw)==report['zip_sha256'],'Release ZIP differs from approved candidate'
    with zipfile.ZipFile(io.BytesIO(raw)) as outer:
        assert outer.testzip() is None and outer.namelist()==report['zip_top_level']
        with tarfile.open(fileobj=io.BytesIO(outer.read(report['zip_top_level'][1]))) as archive:
            assert all(m.isfile() and not m.issym() and not m.islnk() for m in archive)
            files={m.name:archive.extractfile(m).read() for m in archive}
    manifest=json.loads(files['PACKAGE-MANIFEST.json'])
    assert manifest['product_version']==report['product_version'] and manifest['variant']=='standard'
    assert set(files)=={f['path'] for f in manifest['files']}|{'PACKAGE-MANIFEST.json'}
    for entry in manifest['files']:
        data=files[entry['path']]
        assert len(data)==entry['size'] and sha(data)==entry['sha256'],entry['path']
    assert len(files)==report['payload_files']
    assert files['v4/cleanup.sh'].decode().splitlines()[1]=='# Name: 确认无误之后，再点这个'
    assert not any(name.startswith('ks-package/') or name.endswith(('launch-ks.sh','reading-records-ks.sh','阅读记录-ks.sh')) for name in files)
    identity=dict(line.split('=',1) for line in files['BUILD-INFO'].decode().splitlines())
    assert identity['product_version']==report['product_version'] and identity['build_id']==report['build_id'] and identity['variant']=='standard'
def fetch(url):
    request=urllib.request.Request(url,headers={'User-Agent':'Kindle-Release-Verification','Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(request,timeout=120) as response:return response.read()
def release_asset(release,report):
    assert release['tag_name']==report['tag'] and not release['draft'] and not release['prerelease']
    assert release['name']==report.get('release_title',report.get('release_version',report['product_version']))
    # A plugin release can gain independently verified firmware assets later.
    matches=[a for a in release['assets'] if a['name']==report['zip_file']]
    assert len(matches)==1,'Expected exactly one matching environment asset'
    asset=matches[0]
    assert asset['size']==report['zip_size'] and asset['state']=='uploaded'
    if asset.get('digest'):assert asset['digest']=='sha256:'+report['zip_sha256']
    return asset
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-only',action='store_true')
    parser.add_argument('--zip',type=Path)
    parser.add_argument('--github',action='store_true')
    parser.add_argument('--report',type=Path,default=REPORT,help='Use an explicit historical or replacement verification record')
    args=parser.parse_args()
    report=json.loads(args.report.read_text(encoding='utf-8'));verify_source(report)
    if args.zip:verify_zip(args.zip.read_bytes(),report)
    if args.github:
        release=json.loads(fetch('https://api.github.com/repos/'+REPO+'/releases/tags/'+report['tag']))
        asset=release_asset(release,report)
        verify_zip(fetch(asset['browser_download_url']),report)
    assert args.source_only or args.zip or args.github,'Select source or asset verification'
    print('PASS: frozen Standard release sources'+('; original ZIP verified' if args.zip or args.github else ''))
if __name__=='__main__':main()
