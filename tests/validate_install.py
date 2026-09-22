"""Exercise the installer in a workspace sandbox with all device operations mocked."""
from pathlib import Path
import atexit, hashlib, json, os, shutil, subprocess, tempfile

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
install_entry=docs/'reading-records-install.sh'
uninstall_entry=docs/'reading-records-uninstall.sh'
kual=us/'extensions/reading-records-installer'
conf=etc/'native-reading-time.conf'
data=state/'reading-time.tsv'
data.write_text('date\tbook_id\tseconds\ttitle\n2026-09-05\tb1\t14760\tKeep reading history\n',encoding='utf-8')
shutil.copy2(BASELINE/'阅读记录-optimized.sh',viewer)
shutil.copy2(ROOT/'documents/reading-records-install.sh',install_entry)
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
    result=result.replace('lipc-set-prop','"'+lipc.as_posix()+'"')
    return result.replace('PKG="'+us.as_posix()+'/native-reading-time-package"','PKG="'+package.as_posix()+'"')
installer=sandbox_installer(PKG)
prelude='''#!/bin/sh
export PATH="'''+mockbin.as_posix()+''':/usr/bin:$PATH"
id() { echo 0; }
mntroot() { return 0; }
sleep() { return 0; }
sync() { return 0; }
'''
script=SANDBOX/'installer-test.sh'; script.write_text(prelude+installer,encoding='utf-8',newline='\n')
sh=shutil.which('sh') or 'C:/Program Files/Git/usr/bin/sh.exe'
subprocess.run([sh,'-c','/usr/bin/chmod 755 "$1" "$2"','test',initctl.as_posix(),lipc.as_posix()],check=True)
# RUNME is now a thin legacy entry and delegates every invocation to one core.
route_us=SANDBOX/'runme-us'; route_pkg=route_us/'native-reading-time-package'; route_state=route_us/'reading-time'
route_pkg.mkdir(parents=True); (route_us/'documents').mkdir(parents=True)
route_calls=SANDBOX/'runme-route.log'
(route_pkg/'install.sh').write_text('#!/bin/sh\necho "$1" >> "'+route_calls.as_posix()+'"\n',encoding='utf-8',newline='\n')
runme_source=(ROOT/'RUNME.sh').read_text(encoding='utf-8')
route_script=SANDBOX/'runme-route.sh'; route_script.write_text('export PATH="/usr/bin:/bin:$PATH"\n'+runme_source.replace('/mnt/us',route_us.as_posix()),encoding='utf-8',newline='\n')
p=subprocess.run([sh,route_script.as_posix()],capture_output=True)
assert p.returncode==0,(p.stdout,p.stderr)
assert route_calls.read_text().splitlines()==['install']
p=subprocess.run([sh,route_script.as_posix()],capture_output=True)
assert p.returncode==0 and route_calls.read_text().splitlines()==['install','install']
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
assert not (state/'releases/9.7.5-test/assets/launcher-icon.png').exists()
scanner_log=SANDBOX/'scanner-calls.log'
assert scanner_log.exists(),((state/'install.log').read_text(encoding='utf-8'),(SANDBOX/'lipc-calls.log').read_text() if (SANDBOX/'lipc-calls.log').exists() else 'no lipc calls')
assert digest(data)==before[str(data)] and 'scanner-restored' in scanner_log.read_text()
assert not (state/'bin/launch.sh').exists()
assert not (state/'bin/diagnostics.sh').exists()
assert not (state/'bin/uninstall.sh').exists()
assert not (state/'install-manifest.txt').exists()
assert not (state/'compat/detect_env.sh').exists()
assert not (state/'releases/9.7.5-test/bin/reading-records.sh').exists()
assert install_entry.exists() and not uninstall_entry.exists() and not kual.exists()
p=subprocess.run([sh,script.as_posix()],capture_output=True)
assert p.returncode==0,(p.stdout,p.stderr,(state/'install.log').read_text(encoding='utf-8'))
release=state/'releases/9.7.5-test'
assert digest(viewer)==digest(PKG/'阅读记录-entry.sh')
assert digest(release/'bin/reading-records.sh')==digest(PKG/'阅读记录-optimized.sh')
assert digest(state/'bin/launch.sh')==digest(PKG/'launch.sh')
assert digest(state/'bin/diagnostics.sh')==digest(PKG/'diagnostics.sh')
assert digest(state/'bin/uninstall.sh')==digest(PKG/'uninstall.sh')
assert digest(state/'install-manifest.txt')==digest(PKG/'install-manifest.txt')
assert digest(state/'compat/detect_env.sh')==digest(PKG/'compat/detect_env.sh')
assert digest(uninstall_entry)==digest(PKG/'resources/reading-records-uninstall.sh')
assert digest(kual/'bin/action.sh')==digest(PKG/'resources/kual/reading-records-installer/bin/action.sh')
assert digest(kual/'config.xml')==digest(PKG/'resources/kual/reading-records-installer/config.xml')
assert digest(kual/'menu.json')==digest(PKG/'resources/kual/reading-records-installer/menu.json')
assert digest(daemon)==digest(PKG/'native-reading-time-daemon.sh')
assert digest(conf)==digest(PKG/'native-reading-time.conf')
assert digest(data)==before[str(data)]
assert digest(state/'reading-time.tsv.bak')==before[str(data)]
assert (state/'VERSION').read_text(encoding='utf-8').strip()=='9.7.5-test'
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
for f in ['reading-insights-touch-ui.lua','reading-insights-titles.lua','reading-insights-title-widths.lua','reading-insights-cache.awk','reading-insights-cover.lua','reading-insights-render.lua']:
    assert digest(release/'bin'/f)==digest(PKG/f),f
for f in ['daily.png','books.png','total.png','day_detail.png','month_detail.png','week_trend.png','book_detail.png']:
    assert digest(release/'ui-calendar'/f)==digest(PKG/'ui-calendar'/f)
for f in ['daily.png','books.png','total.png']:
    assert digest(state/'ui'/f)==digest(PKG/'ui'/f)
assert digest(state/'bin/reading-insights-touch.lua')==digest(PKG/'reading-insights-touch.lua')
assert digest(release/'bin/reading-records-v9.6.3.sh')==digest(PKG/'阅读记录.sh')

# Full PC/mock lifecycle: installer-created maintenance entries -> uninstall ->
# fresh-path reinstall -> uninstall -> fresh-path reinstall. Canonical resources,
# not the deleted deployed entries, must restore both Scriptlet and KUAL.
(state/'book-covers').mkdir(exist_ok=True); (state/'book-covers/cached.jpg').write_text('regenerable cover')
(state/'book-cover-cache.tsv').write_text('cache')
(state/'service.log').write_text('program log')
(state/'user.conf').write_text('user-setting')
history_before=data.read_bytes(); backup_before=(state/'reading-time.tsv.bak').read_bytes()
for name,body in {'mntroot':'#!/bin/sh\nexit 0\n','killall':'#!/bin/sh\nexit 0\n'}.items():
    path=mockbin/name; path.write_text(body,encoding='utf-8',newline='\n')
subprocess.run([sh,'-c','/usr/bin/chmod 755 "$@"','test',(mockbin/'mntroot').as_posix(),(mockbin/'killall').as_posix()],check=True)
uninstall_env={**os.environ,'PATH':mockbin.as_posix()+':/usr/bin:/bin:'+os.environ.get('PATH',''),'READING_PACKAGE_DIR':PKG.as_posix(),'READING_BASE':state.as_posix(),'READING_DOCUMENTS':docs.as_posix(),'READING_UPSTART_DIR':etc.as_posix(),'READING_MNT_US':us.as_posix(),'READING_TMPDIR':(SANDBOX/'tmp').as_posix(),'READING_SKIP_ROOT_CHECK':'1'}
(SANDBOX/'tmp').mkdir()
p=subprocess.run([sh,uninstall_entry.as_posix()],capture_output=True,env=uninstall_env)
assert p.returncode==0,(p.stdout,p.stderr,(docs/'reading-records-uninstall-diagnostic.txt').read_text(errors='replace'))
assert data.read_bytes()==history_before and (state/'reading-time.tsv.bak').read_bytes()==backup_before
assert (state/'user.conf').read_text()=='user-setting'
assert not viewer.exists() and not bin_dir.exists() and not (state/'releases').exists()
assert not (state/'book-covers').exists() and not (state/'book-cover-cache.tsv').exists() and not (state/'service.log').exists()
assert install_entry.exists() and not uninstall_entry.exists() and not kual.exists()
assert 'STATUS=uninstalled' in (docs/'reading-records-uninstall-result.txt').read_text(encoding='utf-8')

p=subprocess.run([sh,(PKG/'uninstall.sh').as_posix()],capture_output=True,env=uninstall_env)
assert p.returncode==0,(p.stdout,p.stderr)
assert 'STATUS=already_removed' in (docs/'reading-records-uninstall-result.txt').read_text(encoding='utf-8')
assert data.read_bytes()==history_before

raw_base=(PKG/'Install-Native-Reading-Time.sh').read_text(encoding='utf-8')
base_installer=raw_base.replace('/mnt/us',us.as_posix()).replace('/etc/upstart',etc.as_posix())
base_installer=base_installer.replace('/sbin/initctl','"'+initctl.as_posix()+'"').replace('/lib/ld-linux-armhf.so.3',fake_ld.as_posix()).replace('lipc-set-prop','"'+lipc.as_posix()+'"')
base_installer=base_installer.replace('PKG="'+us.as_posix()+'/native-reading-time-package"','PKG="'+PKG.as_posix()+'"')
base_script=SANDBOX/'base-reinstall.sh'; base_script.write_text(prelude+base_installer,encoding='utf-8',newline='\n')
p=subprocess.run([sh,base_script.as_posix()],capture_output=True)
assert p.returncode==0,(p.stdout,p.stderr,(state/'install.log').read_text(errors='replace'))
p=subprocess.run([sh,script.as_posix()],capture_output=True)
assert p.returncode==0,(p.stdout,p.stderr,(state/'install.log').read_text(errors='replace'))
assert data.read_bytes()==history_before and (state/'reading-time.tsv.bak').read_bytes()==backup_before
assert digest(state/'bin/uninstall.sh')==digest(PKG/'uninstall.sh') and viewer.exists()
assert digest(uninstall_entry)==digest(PKG/'resources/reading-records-uninstall.sh')
assert digest(kual/'bin/action.sh')==digest(PKG/'resources/kual/reading-records-installer/bin/action.sh')
assert install_entry.exists()
assert b'Keep reading history' in data.read_bytes()

# Second complete cycle proves repeated install/uninstall has no one-shot source
# dependency in documents/ or extensions/.
p=subprocess.run([sh,uninstall_entry.as_posix()],capture_output=True,env=uninstall_env)
assert p.returncode==0,(p.stdout,p.stderr)
assert install_entry.exists() and not uninstall_entry.exists() and not kual.exists() and not viewer.exists()
assert data.read_bytes()==history_before and (state/'reading-time.tsv.bak').read_bytes()==backup_before
p=subprocess.run([sh,base_script.as_posix()],capture_output=True)
assert p.returncode==0,(p.stdout,p.stderr)
p=subprocess.run([sh,script.as_posix()],capture_output=True)
assert p.returncode==0,(p.stdout,p.stderr,(state/'install.log').read_text(errors='replace'))
assert install_entry.exists() and uninstall_entry.exists() and viewer.exists()
assert digest(uninstall_entry)==digest(PKG/'resources/reading-records-uninstall.sh')
assert digest(kual/'menu.json')==digest(PKG/'resources/kual/reading-records-installer/menu.json')
assert data.read_bytes()==history_before and (state/'reading-time.tsv.bak').read_bytes()==backup_before

result={'result':'PASS','checks':['RUNME delegates to the single installer core.','Missing launcher icon and mismatched daemon are rejected before activation.','The installed library entry delegates to one launcher; the optimized UI is installed separately.','A post-icon/pre-entry failure restores the prior entry and removes newly introduced lifecycle/program files before rescanning.','Installer publishes uninstall Scriptlet and complete KUAL extension from canonical payload resources.','Independent Scriptlet uninstall removes program, KUAL and itself while preserving data and the install Scriptlet.','A repeated core uninstall is safe and reports already_removed.','Two consecutive uninstall/reinstall cycles restore launcher, uninstall Scriptlet and KUAL while preserving history byte-for-byte.'],'limitation':'Installer paths redirected into workspace; Kindle service/root/toaster/scanner commands mocked, not an on-device install.'}
(OUT/'installer-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
