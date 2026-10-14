"""Final KS ZIP: installs, old entries, service recovery, rollback and cleanup."""
from pathlib import Path
import concurrent.futures, hashlib, io, json, os, re, shutil, subprocess, sys, tarfile, tempfile, zipfile
from service_fixture import service_fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_ks_test1 import ARCHIVE, PRODUCT_VERSION, RUNTIME_VERSION, BOOT_NAME, TAR_NAME, make_tar, posix_cksum

OUT = ROOT / 'build/ks-test1-audit'; OUT.mkdir(exist_ok=True)
SH = shutil.which('sh') or 'C:/Program Files/Git/bin/sh.exe'
CLEAN = 'reading-records-install-cleanup.sh'
SHA = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()

def put(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)

def unpack(path):
    with zipfile.ZipFile(path) as outer:
        with tarfile.open(fileobj=io.BytesIO(outer.read(TAR_NAME))) as archive:
            return {m.name:archive.extractfile(m).read() for m in archive if m.isfile()}

CURRENT = unpack(ARCHIVE)
OLD = unpack(ROOT / 'dist/firmware-5201-fix/9.7.6-5.20.1-vera-KS.zip')
PREFIX = 'native-reading-time-package/'

def run_case(case):
    with tempfile.TemporaryDirectory(prefix='install-', dir=OUT) as directory:
        folder=Path(directory); us=folder/'us'; base=us/'reading-time'; docs=us/'documents'; tmp=folder/'tmp'; mock=folder/'mockbin'; upstart=folder/'upstart'
        for p in [base/'bin',docs,tmp,mock,upstart]: p.mkdir(parents=True)
        previous=case!='fresh'
        protected={}
        if previous:
            for name,raw in {'reading-time.tsv':b'date\tbook_id\tseconds\ttitle\n2026-10-01\told\t120\tHistory\n',
                             'reading-time.tsv.bak':b'old backup','user.conf':b'keep setting','book-covers/a.jpg':b'cover',
                             'book-cover-cache.tsv':b'cover mapping','service.log':b'old core log','upstart.log':b'old upstart log'}.items():
                p=base/name; put(p,raw); protected[p]=raw
            for src,dst in [('native-reading-time-daemon.sh','bin/native-reading-time-daemon.sh'),('launch-ks.sh','bin/launch-ks.sh'),
                            ('native-reading-time.conf','service/native-reading-time.conf'),('service-manager.sh','bin/service-manager.sh'),
                            ('compat/lifecycle.sh','compat/lifecycle.sh'),('compat/detect_env.sh','compat/detect_env.sh')]: put(base/dst,OLD[PREFIX+src])
            put(base/'VERSION',b'9.7.5-ks-test1-touch-compat\n')
            put(base/'release-info',b'variant=ks\nrelease_family=V4\n')
            put(docs/'阅读记录.sh',OLD[PREFIX+'阅读记录-KS-entry.sh'])
            put(docs/'安装好之后，确认无误了再点这个.sh',OLD['v4/cleanup.sh'])
            for name,raw in OLD.items():
                if not name.startswith(PREFIX): continue
                relative=name.removeprefix(PREFIX)
                target=None
                if relative=='阅读记录-ks.sh': target='bin/reading-records-ks.sh'
                elif relative.startswith('reading-insights-') and relative.endswith(('.lua','.awk','.sh')):target='bin/'+relative
                elif relative.startswith(('ui-scribe/','render-assets/')):target=relative
                elif relative=='launcher-icon.png':target='assets/'+relative
                if target:put(base/'releases'/RUNTIME_VERSION/target,raw)
        for name,body in [('lua','exit 0'),('fbink','exit 0'),('lipc-get-prop','echo 0'),('lipc-set-prop','printf "%s\\n" "$*" >> "$SCANNER_CALLS"\n[ "${SCANNER_FAIL:-0}" != 1 ]')]:
            put(mock/name,('#!/bin/sh\n'+body+'\n').encode())
        subprocess.run([SH,'-c','chmod 755 "$@"','fixture',*[p.as_posix() for p in mock.iterdir()],*[p.as_posix() for p in (base/'bin').glob('*.sh')]],check=True)
        env={**os.environ,'PATH':mock.as_posix()+':/usr/bin:/bin:','READING_BASE':base.as_posix(),'READING_MNT_US':us.as_posix(),
             'READING_DOCUMENTS':docs.as_posix(),'READING_TMPDIR':tmp.as_posix(),'READING_ALLOW_NONROOT_TEST':'1',
             'READING_UI_LOCK':(tmp/'ui.lock').as_posix(),'SCANNER_CALLS':(folder/'scanner').as_posix()}
        env.update(service_fixture(folder/'fixture',base,upstart,SH,running=previous))
        if previous:put(upstart/'native-reading-time.conf',CURRENT[PREFIX+'native-reading-time.conf'])
        for key,name,raw in [('READING_DEVICETYPE_PATH','model',b'Kindle Scribe 2030'),('READING_USID_PATH','usid',b'G0GZZZPRIVATE_SUFFIX'),
                             ('READING_PROC_MODEL_PATH','proc-model',b''),('READING_SYS_MODEL_PATH','sys-model',b''),
                             ('READING_PRETTYVERSION_PATH','pretty',b'Kindle 5.20.1')]: env[key]=(folder/name).as_posix();put(folder/name,raw)
        with zipfile.ZipFile(ARCHIVE) as archive:archive.extractall(docs)
        if case=='missing_model': (folder/'model').unlink();put(folder/'usid',b'G0G27JPRIVATE_SUFFIX')
        if case=='non_ks':put(folder/'model',b'Kindle Colorsoft');put(folder/'usid',b'G0G3H9PRIVATE_SUFFIX')
        if case=='unknown':put(folder/'model',b'');put(folder/'usid',b'')
        if case=='conflict':put(folder/'usid',b'G0G349PRIVATE_SUFFIX')
        if case=='standard_residue':put(base/'bin/launch.sh',b'other runtime must survive')
        if case=='unknown_formal':put(docs/'reading-records.sh',b'personal script must survive')
        if case=='unknown_force':put(docs/'reading-records-ks-force-exit.sh',b'personal force entry must survive')
        if case=='unknown_alias':put(docs/'阅读记录.sh',b'personal alias must survive')
        if case=='lost_service':(upstart/'native-reading-time.conf').unlink()
        if case=='stopped_service':(folder/'fixture/running').unlink();put(folder/'fixture/proc/123/cmdline',b'')
        if case=='root_rw':put(folder/'fixture/mounts',b'/dev/root / ext3 rw,relatime 0 0\n')
        if case in ('mount_fallback','mount_failure'):(folder/'fixture/mntroot-fail').touch()
        if case=='mount_failure':(folder/'fixture/mount-fail').touch()
        if case=='scanner_failure':env['SCANNER_FAIL']='1'
        if case=='busy_ui':put(tmp/'ui.lock/owner.1/sentinel',b'other UI');put(tmp/'ui.lock/pid',b'1')
        if case=='bad_checksum':raw=(docs/TAR_NAME).read_bytes();put(docs/TAR_NAME,bytes([raw[0]^1])+raw[1:])
        if case in ('activation_failure','interrupted'):
            files=dict(CURRENT);key=PREFIX+'Install-Native-Reading-Time-KS.sh'
            inject=b'kill -TERM $$\n' if case=='interrupted' else b'fail "injected activation failure"\n'
            files[key]=files[key].replace(b'rr_install_helpers || fail',inject+b'rr_install_helpers || fail')
            raw=make_tar(files);put(docs/TAR_NAME,raw)
            text=(docs/BOOT_NAME).read_text(encoding='utf-8');text=re.sub(r"PAYLOAD_SIZE='[0-9]+'",f"PAYLOAD_SIZE='{len(raw)}'",text);text=re.sub(r"PAYLOAD_CKSUM='[0-9]+'",f"PAYLOAD_CKSUM='{posix_cksum(raw)}'",text);(docs/BOOT_NAME).write_text(text,encoding='utf-8',newline='\n')
        before={p:p.read_bytes() for tree in [base/'bin',base/'releases',base/'compat',base/'service',docs] for p in tree.rglob('*') if p.is_file() and p.name not in (BOOT_NAME,TAR_NAME)}
        before.update({p:p.read_bytes() for p in [base/'VERSION',base/'release-info',upstart/'native-reading-time.conf'] if p.is_file()})
        if case=='closed_output':
            with open(os.devnull,'wb') as null:
                child=subprocess.Popen([SH,(docs/BOOT_NAME).as_posix()],env=env,stdout=subprocess.PIPE,stderr=null);child.stdout.close();child.wait(timeout=130);code=child.returncode
        else:code=subprocess.run([SH,(docs/BOOT_NAME).as_posix()],env=env,capture_output=True,timeout=130).returncode
        log=(docs/'reading-records-v4-install.log').read_text(encoding='utf-8',errors='replace')
        failed=case in ['non_ks','unknown','conflict','standard_residue','unknown_formal','unknown_force','bad_checksum','mount_failure','busy_ui','activation_failure','interrupted']
        assert (code!=0)==failed,(case,code,log,(base/'install.log').read_text(errors='replace')[-3500:] if (base/'install.log').exists() else '')
        assert all(p.read_bytes()==raw for p,raw in protected.items()),case
        assert 'PRIVATE_SUFFIX' not in log and 'PRIVATE_SUFFIX' not in (docs/'reading-records-v4-install-result.txt').read_text(encoding='utf-8'),case
        assert (' rw,' if case=='root_rw' else ' ro,') in (folder/'fixture/mounts').read_text(encoding='utf-8'),case
        if failed:
            assert all(p.is_file() and p.read_bytes()==raw for p,raw in before.items()),(case,[str(p) for p,raw in before.items() if not p.is_file() or p.read_bytes()!=raw])
            assert (docs/BOOT_NAME).is_file() and (docs/TAR_NAME).is_file()
            assert 'installation_status=failed' in (docs/'reading-records-v4-install-result.txt').read_text(encoding='utf-8')
        else:
            assert (docs/'reading-records.sh').read_bytes()==CURRENT[PREFIX+'阅读记录-KS-entry.sh']
            assert (base/'VERSION').read_text(encoding='utf-8').strip()==PRODUCT_VERSION
            assert (base/'releases'/RUNTIME_VERSION/'bin/reading-records-ks.sh').read_bytes()==CURRENT[PREFIX+'阅读记录-ks.sh']
            assert not (base/'bin/launch.sh').exists()
            assert not (docs/'安装好之后，确认无误了再点这个.sh').exists()
            assert (docs/CLEAN).read_text(encoding='utf-8').splitlines()[1]=='# Name: 安装文件清理'
            assert (docs/'reading-records-ks-force-exit.sh').is_file()
            if case=='unknown_alias':assert (docs/'阅读记录.sh').read_bytes()==b'personal alias must survive'
            else:assert not (docs/'阅读记录.sh').exists()
            assert 'timing_status=unverified' in (docs/'reading-records-v4-install-result.txt').read_text(encoding='utf-8')
            calls=(folder/'fixture/calls').read_text(encoding='utf-8')
            assert 'stop native-reading-time' not in calls, (case,calls)
            if previous and case!='stopped_service':assert 'start native-reading-time' not in calls,(case,calls)
            if case in ['repeat','cleanup','cleanup_unknown','cleanup_changed_snapshot','repair']:
                again=subprocess.run([SH,(docs/BOOT_NAME).as_posix()],env=env,capture_output=True,timeout=130);assert again.returncode==0,(case,again.stderr)
                assert not list(base.glob('.v4-rollback.*')) and (base/'.previous-install').is_dir()
            if case=='repair':
                payload=folder/'payload'
                with zipfile.ZipFile(ROOT/'build/ks-test1/ks-payload.zip') as z:z.extractall(payload)
                repair_env={**env,'READING_PACKAGE_DIR':(payload/'native-reading-time-package').as_posix(),'READING_SIMPLE_INSTALL':'1'}
                repair=subprocess.run([SH,(payload/'native-reading-time-package/install.sh').as_posix(),'repair'],env=repair_env,capture_output=True,timeout=130);assert repair.returncode==0,repair.stderr
            if case.startswith('cleanup'):
                active={p:p.read_bytes() for tree in [base/'bin',base/'releases',base/'compat',base/'service'] for p in tree.rglob('*') if p.is_file()}
                if case=='cleanup_unknown':put(us/'native-reading-time-package/extra.txt',b'personal file')
                if case=='cleanup_changed_snapshot':put(base/'.previous-install/personal.txt',b'unknown rollback file')
                cleared=subprocess.run([SH,(docs/CLEAN).as_posix()],env=env,capture_output=True,timeout=90)
                if case=='cleanup_unknown':assert cleared.returncode!=0 and (us/'native-reading-time-package/extra.txt').read_bytes()==b'personal file'
                else:
                    assert cleared.returncode==0,(case,cleared.stderr,(base/'cleanup-last.log').read_text(errors='replace'))
                    assert not (docs/CLEAN).exists() and not (docs/BOOT_NAME).exists() and not (docs/TAR_NAME).exists()
                    if case=='cleanup_changed_snapshot':assert (base/'.previous-install/personal.txt').read_bytes()==b'unknown rollback file'
                    else:assert not (base/'.previous-install').exists()
                    assert all(p.read_bytes()==raw for p,raw in active.items())
                    (upstart/'native-reading-time.conf').unlink()
                    ensure=subprocess.run([SH,(base/'bin/service-manager.sh').as_posix(),'ensure'],env={**env,'READING_VARIANT':'ks'},capture_output=True,timeout=18);assert ensure.returncode==0,ensure.stderr
                    assert (upstart/'native-reading-time.conf').exists()
                assert all(p.read_bytes()==raw for p,raw in protected.items())
        print(case,'PASS',flush=True)
        return {'case':case,'result':'PASS','package_sha256':SHA,'kindle_hardware':'UNVERIFIED'}

if __name__=='__main__':
    cases=['fresh','upgrade','missing_model','lost_service','stopped_service','root_rw','mount_fallback','closed_output',
           'non_ks','unknown','conflict','standard_residue','unknown_formal','unknown_force','unknown_alias','bad_checksum',
           'mount_failure','busy_ui','activation_failure','interrupted','scanner_failure','repeat','repair','cleanup','cleanup_unknown','cleanup_changed_snapshot']
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(run_case,case) for case in cases]
        for future in concurrent.futures.as_completed(futures):results.append(future.result())
    assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()==SHA
    (OUT/'installation.json').write_text(json.dumps({'result':'PASS','checks':results,'package_sha256':SHA},indent=2),encoding='utf-8')
    print('KS packaged acceptance:',len(results),'PASS')
