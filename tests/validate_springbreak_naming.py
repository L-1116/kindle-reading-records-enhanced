"""Check the renamed package against the exact hardware-tested checkpoint."""
from normal_fixture import *
from springbreak_contract import VERSION
from springbreak_archives import historical_zip, members, git_file, TESTED, TEST2
import json
checks=[]
def passed(name):
    checks.append(dict(check=name,result='PASS'));print('PASS: '+name,flush=True)
tested=historical_zip('test2')
with zipfile.ZipFile(io.BytesIO(tested)) as z:old=members(z.read(PAYLOAD))
with zipfile.ZipFile(ARCHIVE) as z:
    assert z.namelist()==[BOOTSTRAP,PAYLOAD] and z.testzip() is None
    boot,raw=z.read(BOOTSTRAP),z.read(PAYLOAD)
current=members(raw)
assert current.keys()==old.keys() and len(current)==65
for name,data in current.items():
    if name=='payload-manifest.tsv':continue
    assert data.replace(VERSION.encode(),TEST2.encode())==old[name],name
    assert data==(PKG/name).read_bytes(),name
passed('all 64 runtime files match hardware-tested Test 2 exactly after identity normalization')
template=(ROOT/'documents'/BOOTSTRAP).read_bytes()
assert template.replace(VERSION.encode(),TEST2.encode())==git_file(TESTED,'documents/'+BOOTSTRAP)
passed('bootstrap only changes version identity, preserving log append and transaction behavior')
for line in current['payload-manifest.tsv'].decode().splitlines():
    crc,size,name=line.split('\t');assert cksum(current[name])==(int(crc),int(size))
crc,size=cksum(raw)
assert boot==template.replace(b'@PAYLOAD_CKSUM@',str(crc).encode()).replace(b'@PAYLOAD_SIZE@',str(size).encode())
passed('ZIP/TAR/manifest/outer CRC and size match; only two short ASCII install files')
for name,data in current.items():
    if name.endswith('.sh'):
        for shell in (SH,DASH):subprocess.run([shell,'-n'],input=data,capture_output=True,check=True)
passed('all shipped shell scripts pass sh and dash syntax after naming')
for shell in (SH,DASH):
    d=Device(shell);new_tar,new_boot=d.original_tar,d.original_boot
    with zipfile.ZipFile(io.BytesIO(tested)) as z:d.original_tar,d.original_boot=z.read(PAYLOAD),z.read(BOOTSTRAP)
    d.prepare_payload();d.seed(TEST2);d.install();assert d.read('us/reading-time/VERSION')==TEST2
    data=d.preserved();logs=(d.base/'install-last.log').read_bytes()
    paths=[d.base/'VERSION',d.docs/'reading-records.sh',d.base/'bin/native-reading-time-daemon.sh',d.etc/'upstart/native-reading-time.conf']
    before={p:digest(p) for p in paths}
    d.original_tar,d.original_boot=new_tar,new_boot;d.prepare_payload();d.flag('fail-service');d.install(ok=False)
    assert all(digest(p)==h for p,h in before.items()) and d.preserved()==data
    assert (d.base/'install-last.log').read_bytes().startswith(logs)
    assert (d.docs/BOOTSTRAP).exists() and d.payload.exists();d.no_temporary()
    passed(Path(shell).name+': exact Test 2 -> renamed package failure restores previous runtime and data/logs')
    d.install();assert d.read('us/reading-time/VERSION')==VERSION and d.preserved()==data
    assert (d.base/f'releases/{TEST2}/bin/reading-records-ui.sh').exists()
    broken=d.base/f'releases/{VERSION}/bin/reading-records-ui.sh';write(broken,'exit 99\n');d.install()
    assert broken.read_bytes()==d.transform((PKG/'阅读记录-optimized.sh').read_bytes())
    assert d.preserved()==data;d.no_temporary()
    passed(Path(shell).name+': renamed release retry and same-version repair preserve history/config/covers/cache')
    d.run(d.docs/'reading-records-install-cleanup.sh')
    assert d.preserved()==data and (d.base/'install-last.log').read_bytes().startswith(logs)
    assert (d.base/f'releases/{TEST2}/bin/reading-records-ui.sh').exists()
    assert not (d.docs/BOOTSTRAP).exists() and not d.payload.exists()
    passed(Path(shell).name+': cleanup preserves old Test 2 release and all user data')
write(OUT/'springbreak-naming-results.json',json.dumps(dict(result='PASS',version=VERSION,checks=checks,
    tested_checkpoint=TESTED,tested_zip_sha256=hashlib.sha256(tested).hexdigest(),
    archive_sha256=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()),ensure_ascii=False,indent=2))
