"""Real published-package direct upgrades, with and without install media."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import zipfile

from validate_v4 import ROOT, OUT, run
from historical_packages import CATALOG, package
from build_v4 import SIMPLE_ARCHIVE, TAR_NAME, BOOT_NAME, posix_cksum


def contracts():
    # Reproduce the exact KPW6 rejection using the delivered test1 inventory.
    old=next(row for row in CATALOG if row['id']=='v9.7.6-5.20-vera')
    _,files=package(old)
    entry=files['native-reading-time-package/阅读记录-entry.sh']
    key=f'entry\treading-records.sh\t{posix_cksum(entry)}\t{len(entry)}\t'.encode()
    with zipfile.ZipFile(ROOT/'build/standard-9.8.1-test1/9.8.1-5.20-vera-test1.zip') as z:
        with tarfile.open(fileobj=io.BytesIO(z.read(TAR_NAME))) as t:
            assert key not in t.extractfile('native-reading-time-package/migration-manifest.tsv').read()
    with zipfile.ZipFile(SIMPLE_ARCHIVE) as z:
        assert set(z.namelist())=={BOOT_NAME,TAR_NAME}
        assert BOOT_NAME=='reading-records-9.8.1-install.sh'
        with tarfile.open(fileobj=io.BytesIO(z.read(TAR_NAME))) as t:
            assert key in t.extractfile('native-reading-time-package/migration-manifest.tsv').read()
    # Only the installer and migration helper may change within the payload.
    # In particular daemon, idle helpers, touch/UI code and images stay exact.
    with zipfile.ZipFile(ROOT/'build/standard-9.8.1-test1/9.8.1-5.20-vera-test1.zip') as z:
        with tarfile.open(fileobj=io.BytesIO(z.read(TAR_NAME))) as t:
            accepted={m.name:t.extractfile(m).read() for m in t if m.isfile()}
    names=subprocess.check_output(['git','ls-tree','-r','--name-only','-z','5f7d896','native-reading-time-package'],cwd=ROOT).decode().rstrip('\0').split('\0')
    allowed={'native-reading-time-package/Install-Native-Reading-Time-Optimized.sh','native-reading-time-package/compat/migration.sh'}
    for name in names:
        if name not in allowed and name!='native-reading-time-package/resources/kual/reading-records-installer/bin/action.sh':
            assert (ROOT/name).read_bytes()==accepted[name],name


def inventory_extension(baseline):
    # An additive ownership revision can reuse completed runtime/installer
    # regression only when every executable/asset and every old fingerprint
    # remain exact. New paths would require the whole migration matrix again.
    def unpack(path):
        with zipfile.ZipFile(path) as z:
            boot=z.read(BOOT_NAME)
            with tarfile.open(fileobj=io.BytesIO(z.read(TAR_NAME))) as t:
                return boot,{m.name:t.extractfile(m).read() for m in t if m.isfile()}
    import re
    old_boot,old=unpack(baseline);new_boot,new=unpack(SIMPLE_ARCHIVE)
    pattern=rb"^(BUILD_ID|PAYLOAD_SIZE|PAYLOAD_CKSUM)='[^']*'"
    assert re.sub(pattern,rb"\1='VALUE'",old_boot,flags=re.M)==re.sub(pattern,rb"\1='VALUE'",new_boot,flags=re.M)
    key='native-reading-time-package/migration-manifest.tsv'
    before=set(old[key].splitlines());after=set(new[key].splitlines())
    assert before<=after
    assert {r.split(b'\t')[1] for r in before if r.startswith(b'entry\t')}=={r.split(b'\t')[1] for r in after if r.startswith(b'entry\t')}
    ignored={key,'BUILD-INFO','PACKAGE-MANIFEST.json'}
    assert {k:v for k,v in old.items() if k not in ignored}=={k:v for k,v in new.items() if k not in ignored}
    return {'baseline_sha256':hashlib.sha256(Path(baseline).read_bytes()).hexdigest(),
            'package_sha256':hashlib.sha256(SIMPLE_ARCHIVE.read_bytes()).hexdigest(),
            'old_fingerprints_preserved':len(before),'added_fingerprints':len(after-before),'result':'PASS'}


def check(case):
    ident,cleaned=case
    with tempfile.TemporaryDirectory(prefix='real-upgrade-',dir=OUT) as directory:
        row=run(Path(directory),previous=ident+('-cleaned' if cleaned else ''),cleanup=True)
    return {**row,'source_id':ident,'old_install_media_removed':cleaned}


def safety(case):
    previous,mutation,unknown=case
    with tempfile.TemporaryDirectory(prefix='real-upgrade-safety-',dir=OUT) as directory:
        return run(Path(directory),previous=previous,mutation=mutation,
                   cleanup=unknown or previous is None,cleanup_unknown=unknown)


if __name__=='__main__':
    contracts()
    extension=next((a.split('=',1)[1] for a in sys.argv if a.startswith('--inventory-baseline=')),None)
    if extension:
        result=inventory_extension(extension)
        (OUT/'historical-inventory-extension.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print('Additive inventory, identical installer/runtime:',result,flush=True)
        raise SystemExit(0)
    selected=next((a.split('=',1)[1] for a in sys.argv if a.startswith('--id=')),None)
    start=next((a.split('=',1)[1] for a in sys.argv if a.startswith('--from=')),None)
    ids=[r['id'] for r in CATALOG if r.get('upgrade_5201',True) and (selected is None or r['id']==selected)]
    if start:ids=ids[ids.index(start):]
    assert ids,selected
    rows=[]
    failures=[]
    cases=[(ident,cleaned) for ident in ids for cleaned in (False,True)]
    worker=check
    if '--safety' in sys.argv:
        worker=safety
        cases=[(None,'',False),('V4','',True),('deleted-formal','',False)]
        cases += [('V4',mutation,False) for mutation in
                  ('core_failure','activation_failure','interrupted','unknown_formal','unknown_alias',
                   'ks_residue','wrong_device','duplicate','orphan','lost_service','stopped_service','busy_ui')]
    report=OUT/('historical-upgrades'+('-safety' if '--safety' in sys.argv else '-'+(selected or start) if selected or start else '')+'.json')
    workers=int(next((a.split('=',1)[1] for a in sys.argv if a.startswith('--workers=')),3))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(worker,case):case for case in cases}
        for future in as_completed(futures):
            try:
                row=future.result()
            except Exception as exc:
                row={'case':futures[future],'result':'FAIL','error':repr(exc)}
                failures.append(row)
            rows.append(row)
            print(futures[future],row['result'],row.get('error',''),flush=True)
            report.write_text(json.dumps({'result':'IN_PROGRESS','checks':rows,'hardware':'PENDING'},indent=2),encoding='utf-8')
    assert not failures,failures
    assert len({r['package_sha256'] for r in rows})==1
    report.write_text(json.dumps({'result':'PASS','checks':rows,'hardware':'PENDING'},indent=2),encoding='utf-8')
    print(len(rows),'real-package upgrades PASS',flush=True)
