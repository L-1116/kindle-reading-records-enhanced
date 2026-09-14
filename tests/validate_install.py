"""Exercise the installer in a workspace sandbox with all device operations mocked."""
from pathlib import Path
import atexit, hashlib, json, shutil, subprocess, tempfile

ROOT=Path(__file__).resolve().parents[1]
PKG=ROOT/'native-reading-time-package'
BASELINE=ROOT/'tests/baselines/v9.6.10'
OUT=ROOT/'build/validation'; OUT.mkdir(parents=True,exist_ok=True)
SANDBOX=Path(tempfile.mkdtemp(prefix='install-sandbox-',dir=OUT))
assert SANDBOX.resolve().is_relative_to(OUT.resolve())
atexit.register(shutil.rmtree,SANDBOX,ignore_errors=True)
us=SANDBOX/'us'; state=us/'reading-time'; bin_dir=state/'bin'; docs=us/'documents'; assets=state/'assets'
etc=SANDBOX/'etc/upstart'; mockbin=SANDBOX/'mockbin'
for folder in (bin_dir,docs,etc,mockbin):folder.mkdir(parents=True,exist_ok=True)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
daemon=bin_dir/'native-reading-time-daemon.sh'
viewer=docs/'阅读记录.sh'
conf=etc/'native-reading-time.conf'
data=state/'reading-time.tsv'
data.write_text('date\tbook_id\tseconds\ttitle\n2026-09-05\tb1\t14760\tKeep reading history\n',encoding='utf-8')
shutil.copy2(BASELINE/'阅读记录-optimized.sh',viewer)
shutil.copy2(PKG/'native-reading-time.conf',conf)
old_release=state/'releases/9.6.10-ui-layout-fix'; old_release.mkdir(parents=True)
(old_release/'preserved-marker').write_text('old release stays available')
before={str(p):digest(p) for p in (viewer,conf,data,old_release/'preserved-marker')}
fake_ld=SANDBOX/'ld-linux-armhf.so.3'; fake_ld.write_bytes(b'test')
initctl=mockbin/'initctl'
initctl.write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "'''+(SANDBOX/'service-calls.log').as_posix()+'''"
case "$1" in status) echo 'native-reading-time start/running, process 123';; esac
exit 0
''',encoding='utf-8',newline='\n')
lipc=mockbin/'lipc-set-prop'
lipc.write_text('''#!/bin/sh
echo "$*" >> "'''+(SANDBOX/'lipc-calls.log').as_posix()+'''"
if [ "$1" = com.lab126.scanner ]; then
    if [ -f "'''+(assets/'launcher-icon.png').as_posix()+'''" ] && grep -q '^# Icon: /mnt/us/reading-time/assets/launcher-icon.png$' "'''+viewer.as_posix()+'''"; then
        echo scanner-ready >> "'''+(SANDBOX/'scanner-calls.log').as_posix()+'''"
    else
        echo scanner-restored >> "'''+(SANDBOX/'scanner-calls.log').as_posix()+'''"
    fi
fi
exit 0
''',encoding='utf-8',newline='\n')
raw_installer=(PKG/'Install-Native-Reading-Time-Optimized.sh').read_text(encoding='utf-8')
def sandbox_installer(package: Path) -> str:
    result=raw_installer.replace('/mnt/us',us.as_posix()).replace('/etc/upstart',etc.as_posix())
    result=result.replace('/sbin/initctl','"'+initctl.as_posix()+'"').replace('/lib/ld-linux-armhf.so.3',fake_ld.as_posix())
    return result.replace('PKG="'+us.as_posix()+'/native-reading-time-package"','PKG="'+package.as_posix()+'"')
installer=sandbox_installer(PKG)
prelude='''#!/bin/sh
export PATH="'''+mockbin.as_posix()+''':/usr/bin:$PATH"
id() { echo 0; }
mntroot() { return 0; }
lipc-set-prop() { "'''+lipc.as_posix()+'''" "$@"; }
sleep() { return 0; }
sync() { return 0; }
'''
script=SANDBOX/'installer-test.sh'; script.write_text(prelude+installer,encoding='utf-8',newline='\n')
sh=shutil.which('sh') or 'C:/Program Files/Git/usr/bin/sh.exe'
subprocess.run([sh,'-c','/usr/bin/chmod 755 "$1" "$2"','test',initctl.as_posix(),lipc.as_posix()],check=True)
# RUNME retains the v9.7.1-install-fix fresh-install route: on an empty device
# it runs base then optimized, while an existing daemon skips straight to optimized.
route_us=SANDBOX/'runme-us'; route_pkg=route_us/'native-reading-time-package'; route_state=route_us/'reading-time'
route_pkg.mkdir(parents=True)
route_calls=SANDBOX/'runme-route.log'
(route_pkg/'Install-Native-Reading-Time.sh').write_text('#!/bin/sh\nmkdir -p "'+(route_state/'bin').as_posix()+'"\nprintf daemon > "'+(route_state/'bin/native-reading-time-daemon.sh').as_posix()+'"\necho base >> "'+route_calls.as_posix()+'"\n',encoding='utf-8',newline='\n')
(route_pkg/'Install-Native-Reading-Time-Optimized.sh').write_text('#!/bin/sh\necho optimized >> "'+route_calls.as_posix()+'"\n',encoding='utf-8',newline='\n')
runme_source=(ROOT/'RUNME.sh').read_text(encoding='utf-8')
route_script=SANDBOX/'runme-route.sh'; route_script.write_text('export PATH="/usr/bin:/bin:$PATH"\n'+runme_source.replace('/mnt/us',route_us.as_posix()),encoding='utf-8',newline='\n')
p=subprocess.run([sh,route_script.as_posix()],capture_output=True)
assert p.returncode==0,(p.stdout,p.stderr)
assert route_calls.read_text().splitlines()==['base','optimized']
p=subprocess.run([sh,route_script.as_posix()],capture_output=True)
assert p.returncode==0 and route_calls.read_text().splitlines()==['base','optimized','optimized']
assert 'continuing to optimized 9.7.4 installation' in (route_state/'install.log').read_text(encoding='utf-8')
# Missing launcher art is rejected by the pre-activation payload gate.
missing_pkg=SANDBOX/'missing-icon-package'
shutil.copytree(PKG,missing_pkg,ignore=shutil.ignore_patterns('launcher-icon.png'))
missing_script=SANDBOX/'installer-missing-icon.sh'
missing_script.write_text(prelude+sandbox_installer(missing_pkg),encoding='utf-8',newline='\n')
p=subprocess.run([sh,missing_script.as_posix()],capture_output=True)
assert p.returncode==1,(p.stdout,p.stderr)
assert 'missing payload: launcher-icon.png' in (state/'install.log').read_text(encoding='utf-8')
assert not (SANDBOX/'service-calls.log').exists()
# The negative case must reject a changed daemon before activating anything.
daemon.write_bytes(b'not the validated daemon\n')
p=subprocess.run([sh,script.as_posix()],capture_output=True)
assert p.returncode==1,(p.stdout,p.stderr)
assert all(digest(Path(path))==sha for path,sha in before.items())
assert 'payload daemon differs' in (state/'install.log').read_text(encoding='utf-8')
assert not (SANDBOX/'service-calls.log').exists()
shutil.copy2(PKG/'native-reading-time-daemon.sh',daemon)
# A failure after publishing the icon but before replacing the launcher removes
# the new shared icon and restores the previous launcher before rescanning.
failed_installer=installer.replace(
    'atomic_file "$STAGE/viewer" "$VIEWER" 755 || fail "cannot activate optimized dashboard"',
    'false || fail "injected launcher activation failure"',
)
failed_script=SANDBOX/'installer-rollback-icon.sh'
failed_script.write_text(prelude+failed_installer,encoding='utf-8',newline='\n')
p=subprocess.run([sh,failed_script.as_posix()],capture_output=True)
assert p.returncode==1,(p.stdout,p.stderr)
assert digest(viewer)==before[str(viewer)] and not (assets/'launcher-icon.png').exists()
assert not (state/'releases/9.7.4/assets/launcher-icon.png').exists()
scanner_log=SANDBOX/'scanner-calls.log'
assert scanner_log.exists(),((state/'install.log').read_text(encoding='utf-8'),(SANDBOX/'lipc-calls.log').read_text() if (SANDBOX/'lipc-calls.log').exists() else 'no lipc calls')
assert digest(data)==before[str(data)] and 'scanner-restored' in scanner_log.read_text()
p=subprocess.run([sh,script.as_posix()],capture_output=True)
assert p.returncode==0,(p.stdout,p.stderr,(state/'install.log').read_text(encoding='utf-8'))
release=state/'releases/9.7.4'
assert digest(viewer)==digest(PKG/'阅读记录-optimized.sh')
assert digest(daemon)==digest(PKG/'native-reading-time-daemon.sh')
assert digest(conf)==digest(PKG/'native-reading-time.conf')
assert digest(data)==before[str(data)]
assert digest(state/'reading-time.tsv.bak')==before[str(data)]
assert (state/'VERSION').read_text(encoding='utf-8').strip()=='9.7.4'
assert digest(old_release/'preserved-marker')==before[str(old_release/'preserved-marker')]
icon=assets/'launcher-icon.png'
assert digest(icon)==digest(PKG/'launcher-icon.png')
assert digest(release/'assets/launcher-icon.png')==digest(PKG/'launcher-icon.png')
assert viewer.read_text(encoding='utf-8').splitlines()[:4]==[
    '#!/bin/sh', '# Name: 阅读记录', '# Author: Kindle Reading Records Enhanced',
    '# Icon: /mnt/us/reading-time/assets/launcher-icon.png',
]
assert 'scanner-ready' in (SANDBOX/'scanner-calls.log').read_text()
assert raw_installer.index('atomic_file "$STAGE/release/assets/launcher-icon.png" "$LAUNCHER_ICON" 644') < raw_installer.index('atomic_file "$STAGE/viewer" "$VIEWER" 755') < raw_installer.index('com.lab126.scanner doFullScan 1',raw_installer.index('atomic_file "$STAGE/viewer" "$VIEWER" 755'))
for f in ['reading-insights-touch-ui.lua','reading-insights-titles.lua','reading-insights-title-widths.lua','reading-insights-cache.awk','reading-insights-render.lua']:
    assert digest(release/'bin'/f)==digest(PKG/f),f
for f in ['daily.png','books.png','total.png','day_detail.png','month_detail.png','week_trend.png','book_detail.png']:
    assert digest(release/'ui-calendar'/f)==digest(PKG/'ui-calendar'/f)
for f in ['daily.png','books.png','total.png']:
    assert digest(state/'ui'/f)==digest(PKG/'ui'/f)
assert digest(state/'bin/reading-insights-touch.lua')==digest(PKG/'reading-insights-touch.lua')
assert digest(release/'bin/reading-records-v9.6.3.sh')==digest(PKG/'阅读记录.sh')
result={'result':'PASS','checks':['RUNME performs base then optimized installation on a fresh device and skips base when a daemon already exists.','Missing launcher icon and mismatched daemon are rejected before activation.','Launcher icon is staged in the self-contained release and atomically published before the launcher and scanner.','A post-icon/pre-launcher failure restores the prior launcher and removes newly introduced shared/release icon files before rescanning.','Daemon/config remain identical; reading history, backup and original release are preserved.'],'limitation':'Installer paths redirected into workspace; Kindle service/root/toaster commands mocked, not an on-device install.'}
(OUT/'installer-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
