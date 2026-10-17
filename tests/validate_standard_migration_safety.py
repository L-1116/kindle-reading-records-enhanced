"""Unknown files, live references and symlinks cannot be retired by name."""
from pathlib import Path
import io,json,os,shutil,subprocess,sys,tarfile,tempfile,zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_v4 import SIMPLE_ARCHIVE,TAR_NAME,BOOT_NAME
from service_fixture import service_fixture
SH=shutil.which('sh') or 'C:/Program Files/Git/usr/bin/sh.exe'
OUT=ROOT/'build/validation'
TEST_ENV={**os.environ,'PATH':'/usr/bin:/bin:'+os.environ.get('PATH','')}
if os.name=='nt':TEST_ENV['MSYS']='winsymlinks:sys'
checks=[]
with zipfile.ZipFile(SIMPLE_ARCHIVE) as outer:
    current_boot=outer.read(BOOT_NAME)
    with tarfile.open(fileobj=io.BytesIO(outer.read(TAR_NAME))) as archive:
        ownership=archive.extractfile('native-reading-time-package/migration-manifest.tsv').read()
for scenario in ('known-unreferenced','unknown-file','empty-unknown-directory','live-reference','symlink','unknown-entry'):
    with tempfile.TemporaryDirectory(prefix='migration-safety-',dir=OUT) as directory:
        root=Path(directory);base=root/'reading-time';docs=root/'documents';tmp=root/'tmp'
        for p in (base/'releases/9.7.5-test/bin',base/'bin',docs,tmp):p.mkdir(parents=True,exist_ok=True)
        old=base/'releases/9.7.5-test';known=old/'bin/reading-records.sh'
        known.write_bytes(subprocess.check_output(['git','show','v9.7.5-compat-v3:native-reading-time-package/阅读记录-optimized.sh'],cwd=ROOT))
        inventory=base/'migration-manifest.tsv';inventory.write_bytes(ownership)
        if scenario=='empty-unknown-directory':(old/'personal-empty').mkdir()
        if scenario=='unknown-file':(old/'personal.txt').write_text('must survive')
        if scenario=='live-reference':(docs/'personal.sh').write_text('RELEASE="$BASE/releases/9.7.5-test"\n')
        if scenario=='unknown-entry':(docs/'阅读记录.sh').write_text('# Name: 阅读记录\necho user file\n',encoding='utf-8')
        if scenario=='symlink':
            target=root/'personal';target.write_text('keep')
            subprocess.run([SH,'-c','/usr/bin/ln -s "$1" "$2" && test -L "$2"','fixture',target.as_posix(),(old/'link').as_posix()],check=True,env=TEST_ENV)
        script=root/'check.sh'
        script.write_text(f'''BASE="{base.as_posix()}"
DOCS="{docs.as_posix()}"
TMP="{tmp.as_posix()}"
RELEASE="$BASE/releases/current"
OWNERSHIP="$BASE/migration-manifest.tsv"
note() {{ printf '%s\\n' "$*"; }}
. "{(ROOT/'native-reading-time-package/compat/migration.sh').as_posix()}"
rr_entry_names > "$TMP/entry-names"
rr_migrate_entries || exit 1
rr_retire_releases || exit 1
''',encoding='utf-8',newline='\n')
        result=subprocess.run([SH,script.as_posix()],capture_output=True,timeout=20,env=TEST_ENV)
        assert result.returncode==0,result.stderr
        assert old.exists()==(scenario in ('unknown-file','empty-unknown-directory','live-reference','symlink')),(scenario,result.stdout,result.stderr)
        if scenario=='unknown-entry':assert (docs/'阅读记录.sh').read_text(encoding='utf-8').endswith('echo user file\n')
        if scenario=='symlink':assert target.read_text()=='keep'
        checks.append({'scenario':scenario,'result':'PASS'})
# Only the unchanged file of the active invocation is exempt from migration.
# The real prior bootstrap is still owned; a same-name personal file is not.
from historical_packages import CATALOG,package
prior_outer,_=package(next(r for r in CATALOG if r['id']=='9.8.1-test2'))
prior_boot_name=next(name for name in prior_outer if name.endswith('.sh'))
for scenario in ('current-bootstrap','old-bootstrap','unknown-bootstrap','changed-bootstrap',
                 'symlink-bootstrap','other-location','unknown-formal-bootstrap'):
    with tempfile.TemporaryDirectory(prefix='bootstrap-safety-',dir=OUT) as directory:
        root=Path(directory);docs=root/'documents';tmp=root/'tmp'
        docs.mkdir();tmp.mkdir()
        inventory=root/'inventory';inventory.write_bytes(ownership)
        boot=docs/(prior_boot_name if scenario=='old-bootstrap' else BOOT_NAME)
        boot.write_bytes(prior_outer[prior_boot_name] if scenario=='old-bootstrap' else
                         b'personal file' if scenario=='unknown-bootstrap' else current_boot)
        formal=docs/'reading-records.sh'
        if scenario=='unknown-formal-bootstrap':formal.write_bytes(b'personal formal entry')
        if scenario=='symlink-bootstrap':
            target=root/'personal';target.write_bytes(current_boot);boot.unlink()
            subprocess.run([SH,'-c','/usr/bin/ln -s "$1" "$2" && test -L "$2"','fixture',target.as_posix(),boot.as_posix()],check=True,env=TEST_ENV)
        active=scenario in ('current-bootstrap','changed-bootstrap','symlink-bootstrap','unknown-formal-bootstrap')
        init='rr_installer_file="'+boot.as_posix()+'"; rr_installer_sum=$(cksum < "$rr_installer_file")' if active else ''
        if scenario=='changed-bootstrap':init+='\nprintf "changed" >> "$rr_installer_file"'
        if scenario=='other-location':
            copy=root/BOOT_NAME;copy.write_bytes(current_boot)
            init='rr_installer_file="'+copy.as_posix()+'"; rr_installer_sum=$(cksum < "$rr_installer_file")'
        code=f'''export PATH="/usr/bin:/bin:$PATH"
DOCS="{docs.as_posix()}"; TMP="{tmp.as_posix()}"; OWNERSHIP="{inventory.as_posix()}"
note() {{ :; }}
. "{(ROOT/'native-reading-time-package/compat/migration.sh').as_posix()}"
{init}
rr_migration_preflight; preflight=$?
printf '%s %s\\n' "$preflight" "$MIGRATION_PROTECTED"
[ "$preflight" != 0 ] || rr_migrate_entries
'''
        result=subprocess.run([SH],input=code,text=True,encoding='utf-8',capture_output=True,timeout=25,env=TEST_ENV)
        expected='1 1' if scenario=='unknown-formal-bootstrap' else '0 0' if scenario in ('current-bootstrap','old-bootstrap') else '0 1'
        assert result.returncode==0 and result.stdout.strip()==expected,(scenario,result.stdout,result.stderr)
        assert boot.exists()==(scenario!='old-bootstrap'),scenario
        if scenario=='unknown-formal-bootstrap':assert formal.read_bytes()==b'personal formal entry'
        if scenario=='symlink-bootstrap':assert target.read_bytes()==current_boot
        checks.append({'scenario':scenario,'result':'PASS'})
# Duplicate and orphan daemons are rejected before any start request.
for scenario in ('orphan','duplicate'):
    with tempfile.TemporaryDirectory(prefix='daemon-safety-',dir=OUT) as directory:
        root=Path(directory);base=root/'reading-time';upstart=root/'upstart';tmp=root/'tmp';tmp.mkdir()
        for p in (base/'bin',base/'compat',base/'service'):p.mkdir(parents=True,exist_ok=True)
        pkg=ROOT/'native-reading-time-package'
        for src,dst in [('service-manager.sh','bin/service-manager.sh'),('compat/lifecycle.sh','compat/lifecycle.sh'),('native-reading-time.conf','service/native-reading-time.conf'),('native-reading-time-daemon.sh','bin/native-reading-time-daemon.sh')]:shutil.copy2(pkg/src,base/dst)
        env={**os.environ,'PATH':'/usr/bin:/bin','READING_BASE':base.as_posix(),'READING_TMPDIR':tmp.as_posix()}
        env.update(service_fixture(root/'fixture',base,upstart,SH,running=scenario=='duplicate'))
        shutil.copy2(pkg/'native-reading-time.conf',upstart/'native-reading-time.conf')
        extra=root/'fixture/proc/124';extra.mkdir()
        (extra/'cmdline').write_bytes(b'/bin/sh\0'+(base/'bin/native-reading-time-daemon.sh').as_posix().encode()+b'\0')
        (extra/'stat').write_bytes(b'124 (daemon) S 1 0\n')
        result=subprocess.run([SH,(base/'bin/service-manager.sh').as_posix(),'ensure'],env=env,capture_output=True,timeout=20)
        assert result.returncode!=0 and b'duplicate_or_unmanaged_daemon' in result.stdout,(scenario,result.stdout,result.stderr)
        assert 'start native-reading-time' not in (root/'fixture/calls').read_text()
        checks.append({'scenario':scenario,'result':'PASS'})
(OUT/'standard-migration-safety-results.json').write_text(json.dumps({'result':'PASS','checks':checks},indent=2),encoding='utf-8')
print('Standard migration/process safety:',len(checks),'PASS')
