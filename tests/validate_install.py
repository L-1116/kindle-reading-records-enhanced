"""5.19 normal: bootstrap, firmware gates, transactional install/upgrade/repair."""
from normal_fixture import *
import json

checks=[]
def passed(name, detail=""):
    checks.append({"check":name,"result":"PASS","detail":detail})
    print("PASS: " + name, flush=True)

with zipfile.ZipFile(ARCHIVE) as z:
    assert z.namelist() == [BOOTSTRAP, PAYLOAD] and z.testzip() is None
    boot=z.read(BOOTSTRAP); payload=z.read(PAYLOAD)
    assert BOOTSTRAP.isascii() and boot.decode("utf-8").splitlines()[1]=='# Name: 安装阅读记录'
    assert len(boot)<8192 and len(payload)>1_000_000
    checksum,size=cksum(payload)
    assert f"EXPECTED_CKSUM={checksum}".encode() in boot and f"EXPECTED_SIZE={size}".encode() in boot
    assert python_cksum(b"test\n")==cksum(b"test\n")
    with tarfile.open(fileobj=io.BytesIO(payload)) as t:
        assert all(m.isfile() and m.name.startswith('native-reading-time-package/') and '..' not in m.name for m in t.getmembers())
passed('ZIP two entries, short ASCII installer, Chinese display name, POSIX payload checksum and size')

for mode in ('missing','corrupt','tar-failure','internal-failure'):
    d=Device();d.seed('9.7.5-test');before=d.preserved();runtime=digest(d.base/'bin/native-reading-time-daemon.sh')
    if mode=='missing':d.payload.unlink()
    elif mode=='corrupt':d.payload.write_bytes(d.payload.read_bytes()[:-100])
    elif mode=='tar-failure':
        d.command('tar','exit 3');d.command('busybox','exit 4');d.chmod([d.mock/'tar',d.mock/'busybox'])
    else:d.flag('fail-root')
    d.install(ok=False)
    assert d.preserved()==before and digest(d.base/'bin/native-reading-time-daemon.sh')==runtime
    assert (d.docs/BOOTSTRAP).exists() and (mode=='missing' or d.payload.exists())
    assert not (d.docs/'reading-records-install-cleanup.sh').exists()
    if mode=='missing':assert '缺少阅读记录安装数据' in d.install_log()
    if mode=='corrupt':assert '安装数据损坏' in d.install_log()
    d.no_temporary();passed('bootstrap failure: '+mode)

for firmware,model in [('5.19.0','Kindle 青春版'),('5.19.1','Paperwhite'),('5.19.6','KPW Signature'),('5.19.10','Unexpected Standard marketing name')]:
    d=Device();d.firmware(firmware);write(d.root/'var/local/deviceType.txt',model)
    d.install();d.no_temporary()
    assert (d.docs/'reading-records.sh').exists()
    assert '# Name: 阅读记录' in (d.docs/'reading-records.sh').read_text(encoding='utf-8')
    assert (d.root/'running').exists()
    assert (d.base/'VERSION').read_text().strip()=='9.7.6-5.19-normal'
    release=d.base/'releases/9.7.6-5.19-normal'
    assert all((release/path).is_file() for path in ['bin/reading-records-ui.sh','bin/reading-insights-touch-ui.lua','ui-calendar/book_detail.png','ui-calendar/daily.png'])
    assert digest(d.base/'assets/launcher-icon.png')==digest(PKG/'launcher-icon.png')
    assert digest(d.base/'bin/native-reading-time-daemon.sh')==hashlib.sha256(d.transform((PKG/'native-reading-time-daemon.sh').read_bytes())).hexdigest()
    d.run(d.docs/'reading-records.sh');d.no_temporary()
    passed('fresh install + real UI shell: '+firmware+' '+model)

for firmware in ['5.17.1','5.18.1.1.1','5.18.10','5.20.0','5.190.1','unknown']:
    d=Device();d.seed('9.7.4');d.firmware(firmware);before=d.preserved()
    d.install(ok=False);assert '仅适用于 Kindle firmware 5.19.x' in d.install_log()
    assert d.preserved()==before and not (d.docs/'reading-records.sh').exists()
    d.no_temporary();passed('firmware rejected: '+firmware)

for mode in ['name','pen','geometry','landscape-geometry','installed-ks']:
    d=Device();d.seed('9.7.5-test');before=d.preserved()
    if mode=='name':write(d.root/'var/local/deviceType.txt','Kindle Scribe')
    if mode=='pen':write(d.sys/'class/input/event2/device/name','Wacom I2C Digitizer')
    if 'geometry' in mode:d.flag('scribe-geometry')
    if mode=='landscape-geometry':d.flag('orientation','R')
    if mode=='installed-ks':write(d.base/'VERSION','v4-test.3-ks')
    d.install(ok=False);assert 'KS' in d.install_log() or 'Scribe' in d.install_log()
    assert d.preserved()==before;d.no_temporary();passed('Scribe/mixed install rejected: '+mode)

for version in ['9.7.4','9.7.5-test','9.7.5-compat-v3-standard','V3 Standard','V4 Test 3','9.7.6-5.19-normal']:
    d=Device();d.seed(version);before=d.preserved();d.install();d.no_temporary()
    assert d.preserved()==before and (d.base/'releases/old/marker').read_text()=='old release'
    assert not (d.docs/'阅读记录.sh').exists()
    if version=='9.7.6-5.19-normal':
        # Repair replaces corrupted runtime, while preserving data.
        write(d.base/'releases/9.7.6-5.19-normal/bin/reading-records-ui.sh','broken runtime')
        d.install();assert d.preserved()==before;d.no_temporary()
    passed('upgrade/repair preserves history, backup, config, cover cache and statistics: '+version)
    # Cleanup leaves exactly the formal entry and unrelated documents.
    write(d.docs/'user-book.epub','user book')
    write(d.us/'README.txt','personal README, must stay')
    write(d.docs/'安装好之后，确认无误了再点这个.sh','old V4 cleanup')
    write(d.docs/'reading-records-diagnostic.txt','old diagnostic')
    write(d.us/'native-reading-time-package/stale.txt','old install data')
    write(d.us/'extensions/reading-records-installer/menu.json','old installer')
    runtime_before={p.relative_to(d.base).as_posix():digest(p) for p in d.base.rglob('*') if p.is_file()}
    d.run(d.docs/'reading-records-install-cleanup.sh')
    assert not (d.docs/BOOTSTRAP).exists() and not d.payload.exists()
    assert not (d.docs/'reading-records-install-cleanup.sh').exists()
    assert not (d.docs/'安装好之后，确认无误了再点这个.sh').exists()
    assert not (d.docs/'reading-records-diagnostic.txt').exists()
    assert (d.us/'README.txt').read_text()=='personal README, must stay'
    assert (d.docs/'reading-records.sh').exists() and (d.docs/'user-book.epub').read_text()=='user book'
    assert not (d.us/'native-reading-time-package').exists() and not (d.us/'extensions/reading-records-installer').exists()
    assert {p.relative_to(d.base).as_posix():digest(p) for p in d.base.rglob('*') if p.is_file()}==runtime_before
    d.flag('actions','exit');d.run(d.docs/'reading-records.sh');assert d.preserved()==before;d.no_temporary()
    passed('cleanup whitelist, self-removal and working UI after cleanup: '+version)

# Snapshot every active runtime entry and force a post-publication service failure.
for version in ['9.7.5-test','9.7.6-5.19-normal']:
    d=Device();d.seed(version)
    if version=='9.7.6-5.19-normal':d.install()
    before=d.preserved()
    paths=[d.base/'VERSION',d.base/'bin/native-reading-time-daemon.sh',d.base/'fonts/NotoSansCJKsc-Regular.otf',d.base/'assets/launcher-icon.png',d.etc/'upstart/native-reading-time.conf']
    if version=='9.7.6-5.19-normal':paths.extend([d.docs/'reading-records.sh',d.docs/'reading-records-install-cleanup.sh',d.base/'releases/9.7.6-5.19-normal/bin/reading-records-ui.sh'])
    else:paths.append(d.docs/'阅读记录.sh')
    hashes={str(p):digest(p) for p in paths}
    d.flag('fail-service');d.install(ok=False)
    assert all(digest(path)==sha for path,sha in hashes.items()) and d.preserved()==before
    assert (d.root/'running').exists()
    if version=='9.7.5-test':assert not (d.docs/'reading-records-install-cleanup.sh').exists() and not (d.base/'releases/9.7.6-5.19-normal').exists()
    d.no_temporary();passed('post-activation rollback restores entire previous runtime: '+version)

# Standard metadata may mention books; 'ks' must be a standalone variant token.
d=Device();d.seed('9.7.5-compat-v3-standard');write(d.base/'release-info','variant=standard features=books calendar')
d.install();d.no_temporary();passed('Standard release metadata containing books is not mistaken for KS')

# Extraction failure, not merely listing failure, must leave no temporary files.
d=Device();d.seed('9.7.5-test');before=d.preserved()
d.command('tar','case "$1" in -xf) exit 5;; *) /usr/bin/tar "$@";; esac');d.command('busybox','exit 6');d.chmod([d.mock/'tar',d.mock/'busybox'])
d.install(ok=False);assert d.preserved()==before;d.no_temporary();passed('tar extraction failure cleans tmp and preserves old installation')
d=Device();d.command('tar','exit 3');d.chmod([d.mock/'tar']);d.install();d.no_temporary();passed('BusyBox tar fallback installs successfully')

# Inner resource integrity is independent of the outer payload checksum.
d=Device();d.seed('9.7.5-test');before=d.preserved()
raw=d.payload.read_bytes();buffer=io.BytesIO()
with tarfile.open(fileobj=io.BytesIO(raw)) as source, tarfile.open(fileobj=buffer,mode='w',format=tarfile.USTAR_FORMAT) as target:
    for m in source.getmembers():
        data=source.extractfile(m).read()
        if m.name.endswith('/launcher-icon.png'):data+=b'corrupt'
        m.size=len(data);target.addfile(m,io.BytesIO(data))
raw=buffer.getvalue();d.payload.write_bytes(raw);checksum,size=cksum(raw)
import re
path=d.docs/BOOTSTRAP;script=path.read_text(encoding='utf-8')
script=re.sub(r'EXPECTED_CKSUM=\d+',f'EXPECTED_CKSUM={checksum}',script)
script=re.sub(r'EXPECTED_SIZE=\d+',f'EXPECTED_SIZE={size}',script);write(path,script)
d.install(ok=False);assert '安装资源损坏' in d.install_log() and d.preserved()==before;d.no_temporary()
passed('inner manifest detects corruption despite a valid outer cksum')

for version in ['9.7.5-test','9.7.6-5.19-normal']:
    d=Device();d.seed(version)
    if version=='9.7.6-5.19-normal':d.install()
    before=d.preserved()
    old_release=d.base/'releases/9.7.6-5.19-normal'
    release_hashes={p.relative_to(old_release).as_posix():digest(p) for p in old_release.rglob('*') if p.is_file()}
    d.flag('fail-launcher-once')
    d.command('mv',r'''case "$2" in */documents/reading-records.sh) if [ -f "$SIM/fail-launcher-once" ]; then rm -f "$SIM/fail-launcher-once"; exit 9; fi;; esac
exec /usr/bin/mv "$@"
''');d.chmod([d.mock/'mv'])
    d.install(ok=False);assert d.preserved()==before
    assert {p.relative_to(old_release).as_posix():digest(p) for p in old_release.rglob('*') if p.is_file()}==release_hashes
    assert (d.root/'running').exists();d.no_temporary()
    passed('atomic launcher failure restores all prior release bytes: '+version)

# A signal during publication reaches installer rollback through the bootstrap.
for signal in ['INT','TERM','HUP']:
    d=Device();d.seed('9.7.5-test');before=d.preserved()
    d.flag('interrupt-stop')
    boot=d.docs/BOOTSTRAP
    write(boot,boot.read_text(encoding='utf-8').replace('HERE=', 'echo "$$" > "$SIM/bootstrap-pid"\nHERE=',1))
    path=d.mock/'initctl';script=path.read_text(encoding='utf-8')
    script=script.replace('stop) rm -f', 'stop) if [ -f "$SIM/interrupt-stop" ]; then rm -f "$SIM/interrupt-stop"; kill -'+signal+' "$(cat "$SIM/bootstrap-pid")"; fi; rm -f')
    write(path,script);d.chmod([path])
    d.install(ok=False);assert d.preserved()==before and (d.docs/'阅读记录.sh').exists()
    assert not (d.docs/'reading-records-install-cleanup.sh').exists();d.no_temporary()
    passed('installer signal rolls back and bootstrap removes tmp: '+signal)

for signal in ['INT','TERM','HUP']:
    d=Device();d.seed('9.7.5-test');before=d.preserved()
    path=d.docs/BOOTSTRAP;script=path.read_text(encoding='utf-8').replace('INSTALL_PID=$!', 'kill -'+signal+' "$$"\nINSTALL_PID=$!')
    write(path,script);d.install(ok=False);assert d.preserved()==before
    assert not (d.docs/'reading-records-install-cleanup.sh').exists();d.no_temporary()
    passed('bootstrap signal between fork and installer PID assignment: '+signal)

result={'result':'PASS','checks':checks,'case_count':len(checks),'limits':['Hardware commands are simulated. File deployments, checksums, archive extraction, rollback and real UI shell control flow execute offline. Real power button and e-ink interaction require KPW verification.']}
write(OUT/'installer-results.json',json.dumps(result,ensure_ascii=False,indent=2))
