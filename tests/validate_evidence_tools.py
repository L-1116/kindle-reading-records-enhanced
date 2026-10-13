"""Developer-only evidence/backup tools cannot mutate runtime or service state."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from service_fixture import service_fixture

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/validation'
SH=shutil.which('sh') or 'C:/Program Files/Git/usr/bin/sh.exe'
subprocess.run([sys.executable,str(ROOT/'scripts/build_5201_evidence.py')],check=True,capture_output=True)
collector=ROOT/'build/firmware-5201/reading-records-evidence.sh'
source=collector.read_text(encoding='utf-8')
assert '# DontUseFBInk' in source.splitlines()[:6]
assert 'rr_root_rw()' not in source and 'rr_lock()' not in source and '"$SELF" ensure' not in source
subprocess.run([SH,'-n',collector.as_posix()],check=True)
with tempfile.TemporaryDirectory(prefix='evidence-tools-',dir=OUT) as name:
    folder=Path(name); usb=folder/'usb';base=usb/'reading-time'; docs=usb/'documents'
    base.mkdir(parents=True);docs.mkdir();(folder/'tmp').mkdir()
    history=base/'reading-time.tsv';history.write_bytes(b'date\tbook_id\tseconds\ttitle\n2026-10-12\tbook\t300\tExisting\n')
    (base/'user.conf').write_bytes(b'user configuration\n')
    (base/'state').write_bytes(b'state=waiting\npid=123\n')
    upstart=folder/'upstart'
    env={**os.environ,'PATH':'/usr/bin:/bin','READING_BASE':base.as_posix(),'READING_DOCUMENTS':docs.as_posix(),'READING_TMPDIR':(folder/'tmp').as_posix()}
    env.update(service_fixture(folder/'fixture',base,upstart,SH))
    shutil.copy2(ROOT/'native-reading-time-package/native-reading-time.conf',upstart/'native-reading-time.conf')
    report=docs/'reading-records-evidence-fixture.txt';env['REPORT']=report.as_posix()
    original={p:p.read_bytes() for p in (*base.iterdir(),upstart/'native-reading-time.conf')}
    quick=folder/'collector-quick.sh'
    quick.write_text(source.replace('/bin/sleep 35','true').replace('/bin/sleep 55','true'),encoding='utf-8',newline='\n')
    p=subprocess.run([SH,quick.as_posix(),'--worker'],env=env,capture_output=True,encoding='utf-8',errors='replace',timeout=20)
    assert p.returncode==0,(p.stdout,p.stderr)
    text=report.read_text(encoding='utf-8')
    assert text.count('[sample=')==4 and 'collector_complete=yes' in text and 'recovery_triggered=no' in text
    calls=(folder/'fixture/calls').read_text(encoding='utf-8')
    assert calls.splitlines()==['status native-reading-time']*4,calls
    assert all(path.read_bytes()==data for path,data in original.items())
    backup=folder/'backup';command=[sys.executable,str(ROOT/'scripts/backup_kindle_reading.py'),str(usb),str(backup)]
    result=subprocess.run(command,capture_output=True);assert result.returncode==0,result.stderr
    manifest=json.loads((backup/'backup-manifest.json').read_text(encoding='utf-8'))
    assert manifest['verified'] and manifest['files']['reading-time/reading-time.tsv']==hashlib.sha256(history.read_bytes()).hexdigest()
    repeated=subprocess.run(command,capture_output=True);assert repeated.returncode!=0
    assert all(path.read_bytes()==data for path,data in original.items())
(OUT/'evidence-tools-results.json').write_text(json.dumps({'result':'PASS','sparse_samples':4,'service_mutations':0,'runtime_mutations':0,'backup_verified':True,'existing_backup_overwrite':'refused','kindle_hardware':'PENDING'},indent=2),encoding='utf-8')
print('Read-only sparse evidence collection and verified computer backup: PASS')
