"""Verify test12 original ZIP, source correspondence and bounded test11 changes."""
from pathlib import Path
import argparse,datetime,hashlib,io,json,subprocess,tarfile,zipfile
ROOT=Path(__file__).resolve().parents[1]
ZIP=ROOT/'dist/standard-9.8.1-test12/Kindle-Reading-Records-v9.8.1-5.20-vera-test12.zip'
BASELINE=ROOT/'dist/standard-9.8.1-test11/Kindle-Reading-Records-v9.8.1-5.20-vera-test11.zip'
BASE_SHA='689bdfd6449d517eba7d1b30e0869cf39ec83a188571f3264ce18ba03ff0c7c5'
PRODUCT='9.8.1-5.20-vera-test12'
RUNTIME='9.8.1-5.20-vera-test1'
BOOT='reading-records-v4-install.sh';TAR='阅读记录安装数据.tar'
EXPECTED={'BUILD-INFO','PACKAGE-MANIFEST.json','README.txt','V4-PAYLOAD','v4/cleanup.sh',
 'native-reading-time-package/Install-Native-Reading-Time-Optimized.sh',
 'native-reading-time-package/install.sh','native-reading-time-package/launch.sh',
 'native-reading-time-package/阅读记录-entry.sh','native-reading-time-package/diagnostics.sh',
 'native-reading-time-package/compat/migration.sh','native-reading-time-package/migration-manifest.tsv'}
def sha(raw):return hashlib.sha256(raw).hexdigest()
def unpack(path):
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None and z.namelist()==[BOOT,TAR]
        boot=z.read(BOOT);raw=z.read(TAR);stamps=[x.date_time for x in z.infolist()]
    with tarfile.open(fileobj=io.BytesIO(raw)) as t:
        ms=t.getmembers()
        assert all(m.isfile() and not m.issym() and not m.islnk() and not m.name.startswith('/') and '..' not in Path(m.name).parts for m in ms)
        assert len(ms)==len({m.name for m in ms})
        files={m.name:t.extractfile(m).read() for m in ms}
        for n in ('native-reading-time-package/cover-image','native-reading-time-package/idle-input'):
            assert t.getmember(n).mode==0o755
    return boot,raw,files,stamps
def verify(archive=ZIP):
    assert sha(BASELINE.read_bytes())==BASE_SHA
    _,_,old,_=unpack(BASELINE);boot,raw,files,stamps=unpack(archive)
    assert files.keys()==old.keys()
    changed={n for n in files if files[n]!=old[n]}
    assert changed==EXPECTED,sorted(changed^EXPECTED)
    info=dict(line.split('=',1) for line in files['BUILD-INFO'].decode().splitlines())
    assert info['product_version']==PRODUCT and info['variant']=='standard' and info['release_status']=='local_unpublished'
    assert info['source_baseline']=='eead585fb3ed499fc3effd6fe93e29893cfbbbc2'
    dt=datetime.datetime.fromtimestamp(int(info['build_epoch']),datetime.timezone.utc)
    stamp=(dt.year,dt.month,dt.day,dt.hour,dt.minute,dt.second//2*2)
    assert stamps==[stamp,stamp] and stamp!=(2026,10,3,0,0,0)
    inputs={n:r for n,r in files.items() if n not in ('BUILD-INFO','PACKAGE-MANIFEST.json')}
    assert info['build_id']==sha(b''.join(n.encode()+b'\0'+sha(r).encode() for n,r in sorted(inputs.items())))[:20]
    manifest=json.loads(files['PACKAGE-MANIFEST.json'])
    assert manifest['variant']=='standard' and manifest['product_version']==PRODUCT
    assert set(files)=={r['path'] for r in manifest['files']}|{'PACKAGE-MANIFEST.json'}
    for row in manifest['files']:
        data=files[row['path']];assert len(data)==row['size'] and sha(data)==row['sha256'],row['path']
    assert f"PRODUCT_VERSION='{PRODUCT}'".encode() in boot and f"RUNTIME_VERSION='{RUNTIME}'".encode() in boot
    assert b'REPORT_DIR="$BASE/install-logs"' in boot and b'LOG="$REPORT_DIR/' in boot and b'RESULT="$REPORT_DIR/' in boot
    assert b'REPORTS_READY=0' in boot and b'rr_archive_legacy_reports' in boot
    assert b'READING_DIAGNOSTIC_INTERNAL=install' in files['native-reading-time-package/install.sh']
    assert not any(n.startswith('ks-package/') for n in files)
    generated={'native-reading-time-package/migration-manifest.tsv','native-reading-time-package/resources/kual/reading-records-installer/bin/action.sh'}
    for n,data in files.items():
        if n.startswith(('native-reading-time-package/','v4/')) and n not in generated:
            assert data==(ROOT/n).read_bytes(),('stale source',n)
    # ARM color and input helpers are the exact accepted test11 bytes.
    for n in ('native-reading-time-package/cover-image','native-reading-time-package/idle-input'):
        binary=files[n];assert binary==old[n] and binary[:6]==b'\x7fELF\x01\x01'
        assert int.from_bytes(binary[18:20],'little')==40
        flags=int.from_bytes(binary[36:40],'little');assert flags>>24==5 and flags&0x200 and not flags&0x400
        off=int.from_bytes(binary[28:32],'little');size=int.from_bytes(binary[42:44],'little');count=int.from_bytes(binary[44:46],'little')
        assert all(int.from_bytes(binary[off+i*size:off+i*size+4],'little')!=3 for i in range(count))
    return {'result':'PASS','product_version':PRODUCT,'runtime_version':RUNTIME,'variant':'standard',
      'zip_file':archive.name,'zip_sha256':sha(archive.read_bytes()),'zip_size':archive.stat().st_size,
      'payload_sha256':sha(raw),'payload_files':len(files),'build_id':info['build_id'],'build_epoch':int(info['build_epoch']),
      'zip_entry_time_utc':list(stamp),'baseline_sha256':BASE_SHA,'changed_payload_files':sorted(changed),
      'unchanged_payload_files':len(files)-len(changed),'hardware_verified':False,'publication_actions':[]}
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--zip',type=Path,default=ZIP)
    args=parser.parse_args();print(json.dumps(verify(args.zip),indent=2,ensure_ascii=True))

