"""Recreate pinned historical fixtures without ignored developer directories."""
from pathlib import Path
import ast, hashlib, io, subprocess, sys, tarfile, zipfile
from unittest.mock import patch
from zlib_ng import zlib_ng
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.package_release import BOOTSTRAP, PAYLOAD, cksum
BASE='3acda144ee7bf3a09d7472628efdffd9c09ab240'
TESTED='b7684a07715ac85eb9b0a58ef726c8b50e61131b'
TEST1='9.7.6-5.18-springbreak-kpw4-test1'
TEST2='9.7.6-5.18-springbreak-kpw4-test2'
HASHES={
    'vera':'2b2ad142542295627cfd7a6e4870dcff28d4445088320a728f46887af100693d',
    'test1':'11bf3309d509685e841a9ec39d76a831d717d2f020ac142343f253a2c372262d',
    'test2':'718517ed78953ec6e88acaed67a9ca049ee6a82300e3d7ec86ff73cb097ba59c',
}
def git_file(ref,name):return subprocess.check_output(['git','show',ref+':'+name],cwd=ROOT)
def members(raw):
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        return {m.name.split('/',1)[1]:archive.extractfile(m).read() for m in archive.getmembers()}
def historical_zip(kind):
    assert kind in HASHES
    ref=BASE if kind=='vera' else TESTED
    manifest=git_file(ref,'native-reading-time-package/install-manifest.txt').decode()
    names={'install.sh','install-manifest.txt','cleanup-manifest.txt','resources/reading-records-install-cleanup.sh'}
    names.update(line.split('\t')[0] for line in manifest.splitlines())
    files={name:git_file(ref,'native-reading-time-package/'+name) for name in sorted(names)}
    boot=git_file(ref,'documents/'+BOOTSTRAP)
    if kind=='test1':
        contract=ast.parse(git_file(TESTED,'tests/springbreak_contract.py').decode())
        block=next(ast.literal_eval(n.value) for n in contract.body if isinstance(n,ast.Assign)
                   and any(isinstance(t,ast.Name) and t.id=='TOUCH_BLOCK' for t in n.targets))
        for name in ('阅读记录-optimized.sh','阅读记录.sh'):
            current=files[name].decode();old=git_file(BASE,'native-reading-time-package/'+name).decode()
            assert current.count(block)==1
            selector=old[old.index('find_touch_device() {'):old.index('scale_len() {')]
            files[name]=current.replace(block,selector).encode()
        files={name:raw.replace(TEST2.encode(),TEST1.encode()) for name,raw in files.items()}
        boot=boot.replace(TEST2.encode(),TEST1.encode())
    files['payload-manifest.tsv']=''.join(f'{cksum(raw)[0]}\t{len(raw)}\t{name}\n' for name,raw in files.items()).encode()
    buffer=io.BytesIO()
    with tarfile.open(fileobj=buffer,mode='w',format=tarfile.USTAR_FORMAT) as archive:
        for name,raw in sorted(files.items()):
            entry=tarfile.TarInfo('native-reading-time-package/'+name);entry.size=len(raw)
            entry.mode=0o755 if name.endswith('.sh') else 0o644;entry.mtime=0
            archive.addfile(entry,io.BytesIO(raw))
    payload=buffer.getvalue();checksum,size=cksum(payload)
    boot=boot.replace(b'@PAYLOAD_CKSUM@',str(checksum).encode()).replace(b'@PAYLOAD_SIZE@',str(size).encode())
    buffer=io.BytesIO()
    # Original Windows archives used zlib-ng. Pin the fixture compressor only,
    # so Linux CI reproduces the same bytes without weakening any SHA assertion.
    # The production builder and the public release ZIP remain unchanged.
    with patch.object(zipfile,'zlib',zlib_ng), zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,raw,mode in ((BOOTSTRAP,boot,0o755),(PAYLOAD,payload,0o644)):
            entry=zipfile.ZipInfo(name,date_time=(2026,10,4,0,0,0));entry.create_system=3
            entry.external_attr=(0o100000|mode)<<16
            archive.writestr(entry,raw,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    result=buffer.getvalue()
    assert hashlib.sha256(result).hexdigest()==HASHES[kind],kind
    return result
if __name__=='__main__':
    for kind in HASHES:
        raw=historical_zip(kind)
        print('PASS: '+kind+' reconstructed from pinned Git, SHA-256='+hashlib.sha256(raw).hexdigest())
