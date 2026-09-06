"""Exercise the installer in a workspace sandbox with all device operations mocked."""
from pathlib import Path
import hashlib, json, shutil, subprocess

ROOT=Path(__file__).resolve().parent
PKG=ROOT/'native-reading-time-package'
BASELINE=ROOT.parent/'v9.6.5-ui-polish/native-reading-time-package'
SANDBOX=ROOT/'validation/install-sandbox'
assert SANDBOX.resolve().is_relative_to((ROOT/'validation').resolve())
# No recursive removal: tests can be rerun in a fresh numbered sandbox.
index=0
while SANDBOX.exists():
    index+=1; SANDBOX=ROOT/f'validation/install-sandbox-{index}'
us=SANDBOX/'us'; state=us/'reading-time'; bin_dir=state/'bin'; docs=us/'documents'
etc=SANDBOX/'etc/upstart'; mockbin=SANDBOX/'mockbin'
for folder in (bin_dir,docs,etc,mockbin):folder.mkdir(parents=True,exist_ok=True)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
daemon=bin_dir/'native-reading-time-daemon.sh'
viewer=docs/'阅读记录.sh'
conf=etc/'native-reading-time.conf'
data=state/'reading-time.tsv'
data.write_text('date\tbook_id\tseconds\ttitle\n2026-09-05\tb1\t14760\tKeep reading history\n',encoding='utf-8')
shutil.copy2(BASELINE/'阅读记录-optimized.sh',viewer)
shutil.copy2(BASELINE/'native-reading-time.conf',conf)
old_release=state/'releases/9.6.5-ui-polish'; old_release.mkdir(parents=True)
(old_release/'preserved-marker').write_text('old release stays available')
before={str(p):digest(p) for p in (viewer,conf,data,old_release/'preserved-marker')}
fake_ld=SANDBOX/'ld-linux-armhf.so.3'; fake_ld.write_bytes(b'test')
initctl=mockbin/'initctl'
initctl.write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "'''+(SANDBOX/'service-calls.log').as_posix()+'''"
case "$1" in status) echo 'native-reading-time start/running, process 123';; esac
exit 0
''',encoding='utf-8',newline='\n')
installer=(PKG/'Install-Native-Reading-Time-Optimized.sh').read_text(encoding='utf-8')
installer=installer.replace('/mnt/us',us.as_posix()).replace('/etc/upstart',etc.as_posix())
installer=installer.replace('/sbin/initctl','"'+initctl.as_posix()+'"').replace('/lib/ld-linux-armhf.so.3',fake_ld.as_posix())
installer=installer.replace('PKG="'+us.as_posix()+'/native-reading-time-package"','PKG="'+PKG.as_posix()+'"')
prelude='''#!/bin/sh
export PATH="/usr/bin:$PATH"
id() { echo 0; }
mntroot() { return 0; }
lipc-set-prop() { return 0; }
sleep() { return 0; }
sync() { return 0; }
'''
script=SANDBOX/'installer-test.sh'; script.write_text(prelude+installer,encoding='utf-8',newline='\n')
sh='C:/Program Files/Git/usr/bin/sh.exe'
subprocess.run([sh,'-c','/usr/bin/chmod 755 "$1"','test',initctl.as_posix()],check=True)
# The negative case must reject a changed daemon before activating anything.
daemon.write_bytes(b'not the validated daemon\n')
p=subprocess.run([sh,script.as_posix()],capture_output=True)
assert p.returncode==1,(p.stdout,p.stderr)
assert all(digest(Path(path))==sha for path,sha in before.items())
assert 'payload daemon differs' in (state/'install.log').read_text(encoding='utf-8')
assert not (SANDBOX/'service-calls.log').exists()
shutil.copy2(PKG/'native-reading-time-daemon.sh',daemon)
p=subprocess.run([sh,script.as_posix()],capture_output=True)
assert p.returncode==0,(p.stdout,p.stderr,(state/'install.log').read_text(encoding='utf-8'))
release=state/'releases/9.6.6-stats-filters'
assert digest(viewer)==digest(PKG/'阅读记录-optimized.sh')
assert digest(daemon)==digest(PKG/'native-reading-time-daemon.sh')
assert digest(conf)==digest(PKG/'native-reading-time.conf')
assert digest(data)==before[str(data)]
assert digest(state/'reading-time.tsv.bak')==before[str(data)]
assert (state/'VERSION').read_text().strip()=='9.6.6-stats-filters'
assert digest(old_release/'preserved-marker')==before[str(old_release/'preserved-marker')]
for f in ['reading-insights-touch-ui.lua','reading-insights-titles.lua','reading-insights-title-widths.lua','reading-insights-cache.awk','reading-insights-render.lua']:
    assert digest(release/'bin'/f)==digest(PKG/f),f
for f in ['daily.png','books.png','total.png']:
    assert digest(release/'ui-calendar'/f)==digest(PKG/'ui-calendar'/f)
    assert digest(state/'ui'/f)==digest(BASELINE/'ui'/f)
assert digest(state/'bin/reading-insights-touch.lua')==digest(BASELINE/'reading-insights-touch.lua')
assert digest(release/'bin/reading-records-v9.6.3.sh')==digest(BASELINE/'阅读记录.sh')
result={'result':'PASS','checks':['Mismatched daemon rejected before service stop or viewer/data changes.','Successful staging and activation include all new helpers and UI assets.','Daemon/config exact payload match; history preserved; initial backup created.','Original release retained; legacy background and touch resources still match baseline.'],'limitation':'Installer paths redirected into workspace; Kindle service/root/toaster commands mocked, not an on-device install.'}
(ROOT/'validation/installer-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
