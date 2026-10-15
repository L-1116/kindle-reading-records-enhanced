"""Current Standard two-file package migration/rollback acceptance.
Historical filename is retained for callers; no KS build or device access.
"""
from pathlib import Path
import hashlib,io,json,os,shutil,subprocess,sys,tarfile,tempfile,zipfile
from service_fixture import service_fixture
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_v4 import PRODUCT_VERSION,RUNTIME_VERSION,SIMPLE_ARCHIVE,BOOT_NAME as BOOT,TAR_NAME as TAR,make_tar,posix_cksum
OUT=ROOT/'build/validation';OUT.mkdir(exist_ok=True)
SHELL=shutil.which('sh') or 'C:/Program Files/Git/usr/bin/sh.exe'
CLEAN='reading-records-install-cleanup.sh'

def put(path,raw):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)

def historical(tag,path):
    return subprocess.check_output(['git','show',tag+':'+path],cwd=ROOT)

def chmod(*paths):
    subprocess.run([SHELL,'-c','/usr/bin/chmod 755 "$@"','fixture',*[p.as_posix() for p in paths]],check=True)

def seed(session,previous):
    us=session/'us';base=us/'reading-time';docs=us/'documents';upstart=session/'upstart'
    docs.mkdir(parents=True);(base/'bin').mkdir(parents=True);upstart.mkdir()
    if previous:
        put(base/'bin/native-reading-time-daemon.sh',historical('b46407c','native-reading-time-package/native-reading-time-daemon.sh'))
        put(upstart/'native-reading-time.conf',(ROOT/'native-reading-time-package/native-reading-time.conf').read_bytes())
        if previous in ('normal','mixed','deleted-formal'):
            tag='v9.7.6-5.19-vera';prefix='native-reading-time-package/'
            manifest=historical(tag,prefix+'install-manifest.txt').decode()
            for line in manifest.splitlines():
                src,kind,dst,_=line.split('\t')
                if kind=='release': put(base/'releases/9.7.6-5.19-normal'/dst,historical(tag,prefix+src))
                elif kind=='docs': put(docs/dst,historical(tag,prefix+src))
        if previous in ('V4','mixed','deleted-formal'):
            with zipfile.ZipFile(ROOT/'build/standard-next-baseline/artifacts/9.7.6-5.20.1-vera.zip') as outer:
                with tarfile.open(fileobj=io.BytesIO(outer.read(TAR))) as payload:
                    files={m.name:payload.extractfile(m).read() for m in payload if m.isfile()}
            prefix='native-reading-time-package/'
            for src,dst in [('launch.sh','bin/launch.sh'),('service-manager.sh','bin/service-manager.sh'),('compat/lifecycle.sh','compat/lifecycle.sh'),('compat/detect_env.sh','compat/detect_env.sh'),('native-reading-time.conf','service/native-reading-time.conf')]:put(base/dst,files[prefix+src])
            for src,dst in [('阅读记录-optimized.sh','bin/reading-records.sh'),('阅读记录.sh','bin/reading-records-v9.6.3.sh')]:put(base/'releases/9.7.5-test'/dst,files[prefix+src])
            put(docs/'reading-records-uninstall.sh',files[prefix+'resources/reading-records-uninstall.sh'])
            put(docs/'安装好之后，确认无误了再点这个.sh',files['v4/cleanup.sh'])
            if previous!='deleted-formal':put(docs/'阅读记录.sh',files[prefix+'阅读记录-entry.sh'])
            put(base/'release-info',b'release_family=V4\nvariant=standard\n')
        if previous in ('V1','V2','V3','9.7.4'):
            tag={'V1':'v9.7.5-test.1','V2':'v9.7.5-compat-v2','V3':'v9.7.5-compat-v3','9.7.4':'v9.7.4'}[previous]
            src='阅读记录-optimized.sh' if previous=='9.7.4' else '阅读记录-entry.sh'
            put(docs/'阅读记录.sh',historical(tag,'native-reading-time-package/'+src))
            if previous!='9.7.4':put(docs/'reading-records-uninstall.sh',historical(tag,'documents/reading-records-uninstall.sh'))
        put(base/'VERSION',(str(previous)+'\n').encode())
    protected={
        base/'reading-time.tsv':b'date\tbook_id\tseconds\ttitle\n2026-10-01\told\t120\tHistory\n',
        base/'user.conf':b'preference=keep\n',base/'reading-time.tsv.bak':b'previous backup',
        base/'book-covers/cover.jpg':b'cover',base/'book-cover-cache.tsv':b'cover cache',
        base/'book-cover-misses.tsv':b'miss cache',base/'service.log':b'core service evidence',
        base/'upstart.log':b'core upstart evidence',base/'touch-last.log':b'core touch evidence',
    }
    if previous is None:protected={}
    for p,raw in protected.items():put(p,raw)
    return us,base,docs,upstart,protected

def run(session,variant='standard',previous=None,mutation='',cleanup=False,legacy_tag=None,legacy_archive=None,cleanup_unknown=False):
    assert variant=='standard'
    package_sha=hashlib.sha256(SIMPLE_ARCHIVE.read_bytes()).hexdigest()
    us,base,docs,upstart,protected=seed(session,previous)
    tmp=session/'tmp';tmp.mkdir();mock=session/'mockbin';mock.mkdir()
    for name,body in [('fbink','exit 0'),('lua','exit 0'),('lipc-get-prop','echo active'),('lipc-set-prop','echo "$*" >> "$SCANNER_CALLS"\n[ "${SCANNER_FAIL:-0}" != 1 ]')]:put(mock/name,('#!/bin/sh\n'+body+'\n').encode())
    chmod(*mock.iterdir())
    env={**os.environ,'PATH':mock.as_posix()+':/usr/bin:/bin:'+os.environ.get('PATH',''),'READING_MNT_US':us.as_posix(),'READING_BASE':base.as_posix(),'READING_DOCUMENTS':docs.as_posix(),'READING_TMPDIR':tmp.as_posix(),'READING_ALLOW_NONROOT_TEST':'1','READING_UI_LOCK':(tmp/'ui.lock').as_posix(),'SCANNER_CALLS':(session/'scanner-calls').as_posix()}
    env.update(service_fixture(session/'service-fixture',base,upstart,SHELL,running=bool(previous)))
    model=session/'device';put(model,b'KPW6');env['READING_DEVICETYPE_PATH']=model.as_posix()
    for key,name in [('READING_USID_PATH','usid'),('READING_PROC_MODEL_PATH','proc-model'),('READING_SYS_MODEL_PATH','sys-model')]:env[key]=(session/name).as_posix()
    pretty=session/'pretty';put(pretty,b'Kindle 5.20.1');env['READING_PRETTYVERSION_PATH']=pretty.as_posix()
    env['READING_ARMHF_LOADER_PATH']=(session/'loader').as_posix();put(session/'loader',b'loader')
    if previous in ('test1','test1-cleaned'):
        with zipfile.ZipFile(ROOT/'dist/standard-test1/9.7.6-5.20.1-vera-test1.zip') as old:
            old.extractall(docs)
        installed=subprocess.run([SHELL,(docs/BOOT).as_posix()],env=env,capture_output=True,timeout=130)
        assert installed.returncode==0,(installed.stdout,installed.stderr)
        assert (docs/CLEAN).read_text(encoding='utf-8').splitlines()[1]=='# Name: 安装文件清理'
        if previous=='test1-cleaned':
            cleared=subprocess.run([SHELL,(docs/CLEAN).as_posix()],env=env,capture_output=True,timeout=90)
            assert cleared.returncode==0,cleared.stderr
            assert not (docs/CLEAN).exists()
    if mutation=='lost_service':(upstart/'native-reading-time.conf').unlink(missing_ok=True)
    if mutation=='stopped_service':(session/'service-fixture/running').unlink(missing_ok=True);put(session/'service-fixture/proc/123/cmdline',b'')
    if mutation=='initial_rw':put(session/'service-fixture/mounts',b'/dev/root / ext3 rw,relatime 0 0\n')
    if mutation=='scanner_failure':env['SCANNER_FAIL']='1'
    if mutation=='cross_variant':put(base/'release-info',b'variant=ks\n')
    if mutation=='ks_residue':put(base/'bin/launch-ks.sh',b'known KS marker')
    if mutation=='wrong_device':put(model,b'Kindle Scribe')
    if mutation=='unknown_formal':put(docs/'reading-records.sh','#!/bin/sh\n# Name: 阅读记录\necho personal\n'.encode())
    if mutation=='unknown_alias':put(docs/'阅读记录.sh',b'personal file must survive')
    if mutation in ('orphan','duplicate'):
        pid='124' if mutation=='duplicate' else '123'
        put(session/f'service-fixture/proc/{pid}/cmdline',b'/bin/sh\0'+(base/'bin/native-reading-time-daemon.sh').as_posix().encode()+b'\0')
        put(session/f'service-fixture/proc/{pid}/stat',b'124 (daemon) S 1 0\n')
        if mutation=='orphan':(session/'service-fixture/running').unlink(missing_ok=True)
    if mutation=='busy_ui':
        put(tmp/'ui.lock/owner.1/sentinel',b'foreign');put(tmp/'ui.lock/pid',b'1')
    with zipfile.ZipFile(SIMPLE_ARCHIVE) as archive:archive.extractall(docs)
    script=docs/BOOT
    if mutation=='missing_payload':(docs/TAR).unlink()
    if mutation=='bad_checksum':raw=(docs/TAR).read_bytes();put(docs/TAR,bytes([raw[0]^1])+raw[1:])
    if mutation in ('core_failure','activation_failure','interrupted'):
        with tarfile.open(docs/TAR) as archive:files={m.name:archive.extractfile(m).read() for m in archive if m.isfile()}
        key='native-reading-time-package/install.sh' if mutation=='core_failure' else 'native-reading-time-package/Install-Native-Reading-Time-Optimized.sh'
        if mutation=='core_failure':files[key]=files[key].replace(b'STAGE=install',b'exit 73\nSTAGE=install')
        else:files[key]=files[key].replace(b'echo "$(date): final sanity resolver=ok', (b'kill -TERM $$\n' if mutation=='interrupted' else b'fail "injected failure"\n')+b'echo "$(date): final sanity resolver=ok')
        raw=make_tar(files);put(docs/TAR,raw)
        text=script.read_text(encoding='utf-8');import re
        text=re.sub(r"PAYLOAD_SIZE='[0-9]+'",f"PAYLOAD_SIZE='{len(raw)}'",text);text=re.sub(r"PAYLOAD_CKSUM='[0-9]+'",f"PAYLOAD_CKSUM='{posix_cksum(raw)}'",text);script.write_text(text,encoding='utf-8',newline='\n')
    # Installation reports record the attempted upgrade, including a failure.
    # They must retain new fault evidence rather than roll back to an old success.
    old_evidence_log=(docs/'reading-records-v4-install.log').read_bytes() if (docs/'reading-records-v4-install.log').is_file() else b''
    before={p.relative_to(us).as_posix():p.read_bytes() for folder in [base/'bin',base/'releases',base/'compat',base/'service',docs] for p in folder.rglob('*') if p.is_file() and p.name not in (BOOT,TAR,'reading-records-v4-install-result.txt','reading-records-v4-install.log')}
    before_metadata={p:p.read_bytes() for p in (base/'VERSION',base/'release-info') if p.is_file()}
    result=subprocess.run([SHELL,script.as_posix()],env=env,capture_output=True,timeout=130)
    log=(docs/'reading-records-v4-install.log').read_text(encoding='utf-8',errors='replace')
    failed=mutation in ('core_failure','activation_failure','interrupted','missing_payload','bad_checksum','cross_variant','ks_residue','wrong_device','unknown_formal','orphan','duplicate','busy_ui')
    assert (result.returncode!=0)==failed,(previous,mutation,result.returncode,result.stderr,log,(base/'install.log').read_text(errors='replace')[-2500:] if (base/'install.log').exists() else '')
    assert all(p.read_bytes()==raw for p,raw in protected.items())
    if failed:
        assert all((us/path).is_file() and (us/path).read_bytes()==raw for path,raw in before.items()),(mutation,[path for path,raw in before.items() if not (us/path).is_file() or (us/path).read_bytes()!=raw])
        assert (docs/CLEAN).exists()==('documents/'+CLEAN in before)
        assert all(p.read_bytes()==raw for p,raw in before_metadata.items()),mutation
        assert (docs/'reading-records-v4-install.log').read_bytes().startswith(old_evidence_log)
        assert 'installation_status=failed' in (docs/'reading-records-v4-install-result.txt').read_text(encoding='utf-8')
    else:
        assert (docs/'reading-records.sh').read_bytes()==(ROOT/'native-reading-time-package/阅读记录-entry.sh').read_bytes()
        if previous is None:assert (base/'reading-time.tsv').read_bytes()==b'date\tbook_id\tseconds\ttitle\n'
        assert (base/'VERSION').read_text().strip()==PRODUCT_VERSION
        assert (base/f'releases/{RUNTIME_VERSION}/bin/reading-records.sh').read_bytes()==(ROOT/'native-reading-time-package/阅读记录-optimized.sh').read_bytes()
        assert (docs/CLEAN).is_file() and (base/'.previous-install').is_dir()
        assert (docs/CLEAN).read_text(encoding='utf-8').splitlines()[1]=='# Name: 确认无误之后，再点这个'
        owned_viewers=[p.name for p in docs.glob('*.sh') if '# Name: 阅读记录' in p.read_text(encoding='utf-8',errors='replace').splitlines()]
        assert owned_viewers==['reading-records.sh']
        known_cleanup_names=('# Name: 安装文件清理','# Name: 确认无误之后，再点这个','# Name: 安装好之后，确认无误了再点这个')
        visible_cleanups=[p.name for p in docs.glob('*.sh') if any(name in p.read_text(encoding='utf-8',errors='replace').splitlines() for name in known_cleanup_names)]
        assert visible_cleanups==[CLEAN],visible_cleanups
        if mutation!='unknown_alias':assert not (docs/'阅读记录.sh').exists()
        assert not (docs/'reading-records-uninstall.sh').exists() and not (docs/'安装好之后，确认无误了再点这个.sh').exists()
        if previous in ('mixed','deleted-formal','V4','test1','test1-cleaned'):
            again=subprocess.run([SHELL,script.as_posix()],env=env,capture_output=True,timeout=130);assert again.returncode==0,again.stderr
            assert len(list(base.glob('.previous-install')))==1 and not list(base.glob('.v4-rollback.*'))
        if mutation=='scanner_failure':assert 'scanner_request=request_failed index_completion=unverified' in log
        if cleanup:
            backup=session/'cleanup-copy.sh';shutil.copy2(docs/CLEAN,backup)
            active_runtime={p:p.read_bytes() for folder in (base/f'releases/{RUNTIME_VERSION}',base/'compat',base/'service') for p in folder.rglob('*') if p.is_file()}
            active_runtime.update({p:p.read_bytes() for p in (base/'bin/launch.sh',base/'bin/service-manager.sh',base/'bin/native-reading-time-daemon.sh',upstart/'native-reading-time.conf')})
            scanner_before=len((session/'scanner-calls').read_text(encoding='utf-8').splitlines())
            if cleanup_unknown:put(us/'native-reading-time-package/user-extra.txt',b'user unknown')
            if legacy_tag:
                names=subprocess.check_output(['git','ls-tree','-r','--name-only',legacy_tag,'native-reading-time-package'],cwd=ROOT).decode().splitlines()
                for name in names:put(us/name,historical(legacy_tag,name))
            c=subprocess.run([SHELL,(docs/CLEAN).as_posix()],env=env,capture_output=True,timeout=90)
            if cleanup_unknown:assert c.returncode!=0 and (us/'native-reading-time-package/user-extra.txt').read_bytes()==b'user unknown'
            else:
                assert c.returncode==0,(c.stdout,c.stderr,(base/'cleanup-last.log').read_text(errors='replace'))
                assert not (docs/CLEAN).exists() and not (docs/BOOT).exists() and not (docs/TAR).exists()
                assert not (base/'.previous-install').exists() and not (us/'native-reading-time-package').exists(), ((base/'cleanup-last.log').read_text(errors='replace'),(base/'.previous-install/snapshot-files').read_text(errors='replace') if (base/'.previous-install/snapshot-files').exists() else '')
                assert not (base/'releases/9.7.6-5.19-normal').exists(), (base/'cleanup-last.log').read_text(errors='replace')
                assert not (base/'releases/9.7.5-test').exists()
                assert not (base/'releases/9.7.4').exists()
                assert not (base/'releases/9.7.6-5.20.1-vera-test1').exists()
                assert (docs/'reading-records.sh').read_bytes()==(ROOT/'native-reading-time-package/阅读记录-entry.sh').read_bytes()
                assert all(p.read_bytes()==raw for p,raw in active_runtime.items())
                assert len((session/'scanner-calls').read_text(encoding='utf-8').splitlines())>scanner_before
                if mutation=='scanner_failure':assert 'scanner_request=request_failed index_completion=unverified' in (base/'cleanup-last.log').read_text(encoding='utf-8')
                c=subprocess.run([SHELL,backup.as_posix()],env=env,capture_output=True,timeout=90);assert c.returncode==0,c.stderr
            assert all(p.read_bytes()==raw for p,raw in protected.items())
    calls=(session/'service-fixture/calls').read_text(errors='replace') if (session/'service-fixture/calls').exists() else ''
    if previous and not failed:
        assert 'stop native-reading-time' in calls and 'start native-reading-time' in calls,(mutation,calls)
    return {'package_sha256':package_sha,'scenario':str(previous or 'fresh')+' '+mutation,'result':'PASS','scanner_index_completion':'UNVERIFIED','protected_files':len(protected)}

def main():
    results=[]
    cases=[(p,'',True) for p in (None,'9.7.4','V1','V2','V3','normal','V4','mixed','deleted-formal')]
    cases += [('mixed',m,False) for m in ('core_failure','activation_failure','interrupted','missing_payload','bad_checksum','cross_variant','ks_residue','wrong_device','unknown_formal','unknown_alias','duplicate','orphan','scanner_failure','lost_service','stopped_service','initial_rw','busy_ui')]
    cases += [('test1','',True),('test1-cleaned','',True),(None,'scanner_failure',True)]
    cases += [('test1',m,False) for m in ('core_failure','activation_failure','interrupted')]
    if '--device-fix' in sys.argv:
        # Same real package/transaction fixture; focus this device-only change
        # on fresh install, accepted-release upgrade, repair, and safety faults.
        cases=[(None,'',True),('V4','',True),('test1-cleaned','',True)]
        cases += [('mixed',m,False) for m in ('core_failure','activation_failure','interrupted','missing_payload','bad_checksum','cross_variant','ks_residue','wrong_device','unknown_formal','unknown_alias','duplicate','orphan','lost_service','stopped_service','initial_rw','busy_ui')]
    if '--idle-upgrade' in sys.argv:
        cases=[('V4','',True)]
        cases += [('V4',m,False) for m in ('core_failure','activation_failure','interrupted','lost_service','stopped_service','ks_residue','wrong_device','orphan','duplicate','busy_ui')]
    for p,m,c in cases:
        with tempfile.TemporaryDirectory(prefix='standard-install-',dir=OUT) as name:results.append(run(Path(name),previous=p,mutation=m,cleanup=c))
        print(p or 'fresh',m or 'install + cleanup','PASS',flush=True)
    for tag in (() if '--device-fix' in sys.argv or '--idle-upgrade' in sys.argv else ('v9.7.4','v9.7.5-test.1','v9.7.5-compat-v2','v9.7.5-compat-v3')):
        with tempfile.TemporaryDirectory(prefix='standard-legacy-',dir=OUT) as name:results.append(run(Path(name),previous='V3',cleanup=True,legacy_tag=tag))
        print('legacy payload',tag,'PASS',flush=True)
    with tempfile.TemporaryDirectory(prefix='standard-unknown-',dir=OUT) as name:results.append(run(Path(name),previous='V4' if '--idle-upgrade' in sys.argv else 'V3',cleanup=True,cleanup_unknown=True))
    assert len({row['package_sha256'] for row in results})==1, 'Package changed during matrix; rerun against frozen ZIP'
    (OUT/'standard-install-results.json').write_text(json.dumps({'result':'PASS','checks':results,'hardware':'PENDING'},indent=2),encoding='utf-8')
if __name__=='__main__':main()
