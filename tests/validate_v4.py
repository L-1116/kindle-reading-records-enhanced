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
INSTALL_TIMEOUT=int(os.environ.get('READING_TEST_INSTALL_TIMEOUT','130'))
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
    protected={
        base/'reading-time.tsv':b'date\tbook_id\tseconds\ttitle\n2026-10-01\told\t120\tHistory\n',
        base/'user.conf':b'preference=keep\nidle_pause_enabled=1\nidle_pause_minutes=17\ncustom_cover_enabled=0\n',base/'reading-time.tsv.bak':b'previous backup',
        base/'book-covers/cover.jpg':b'cover',base/'book-cover-cache.tsv':b'cover cache',
        base/'book-cover-misses.tsv':b'miss cache',base/'service.log':b'core service evidence',
        base/'custom-covers/中文 cover.png':b'original user picture',
        base/'custom-cover-associations.tsv':b'# custom associations preserved byte for byte\n',
        base/'custom-cover-previews/retained.pgm':b'isolated preview cache',
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
    env.update(service_fixture(session/'service-fixture',base,upstart,SHELL,running=False))
    model=session/'device';put(model,b'KPW6');env['READING_DEVICETYPE_PATH']=model.as_posix()
    for key,name in [('READING_USID_PATH','usid'),('READING_PROC_MODEL_PATH','proc-model'),('READING_SYS_MODEL_PATH','sys-model')]:env[key]=(session/name).as_posix()
    pretty=session/'pretty';put(pretty,b'Kindle 5.20.1');env['READING_PRETTYVERSION_PATH']=pretty.as_posix()
    env['READING_ARMHF_LOADER_PATH']=(session/'loader').as_posix();put(session/'loader',b'loader')
    if previous:
        from historical_install_fixture import install_history
        aliases={'V4':'v9.7.6-5.20-vera','mixed':'v9.7.6-5.20-vera','deleted-formal':'v9.7.6-5.20-vera',
                 '9.7.4':'v9.7.4','V3':'v9.7.5-compat-v3','normal':'v9.7.6-5.19-vera'}
        ident=aliases.get(previous,previous.removesuffix('-cleaned'))
        install_history(session,env,ident,cleaned=previous.endswith('-cleaned'))
        if previous=='deleted-formal':(docs/'reading-records.sh').unlink()
        if previous=='mixed':
            # Deliberate known leftover alias, after a real V4 installation.
            put(docs/'阅读记录.sh',historical('v9.7.4','native-reading-time-package/阅读记录-optimized.sh'))
    covers=base/'custom-covers'
    if mutation=='legacy_diagnostics':
        manual=subprocess.run([SHELL,(base/'bin/diagnostics.sh').as_posix()],env=env,capture_output=True,timeout=100)
        assert manual.returncode==0,manual.stderr
    if mutation in ('cover_dir_missing','cover_dir_file','cover_dir_symlink'):
        # Remove only the fixture's own picture and empty directory, modeling
        # an installation whose dashboard has never initialized this storage.
        picture=covers/'中文 cover.png'
        if picture in protected:picture.unlink();protected.pop(picture);covers.rmdir()
        if mutation=='cover_dir_file':
            put(covers,b'user file at the requested directory path');protected[covers]=covers.read_bytes()
        elif mutation=='cover_dir_symlink':
            target=session/'cover-link-target';put(target/'keep.jpg',b'linked user picture')
            protected[target/'keep.jpg']=b'linked user picture'
            if os.name=='nt':env['MSYS']='winsymlinks:sys'
            subprocess.run([SHELL,'-c','/usr/bin/ln -s "$1" "$2" && test -L "$2"','fixture',target.as_posix(),covers.as_posix()],env=env,check=True)
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
    report_dir=base/'install-logs'
    old_evidence_log=(report_dir/'reading-records-v4-install.log').read_bytes() if (report_dir/'reading-records-v4-install.log').is_file() else b''
    report_names=('reading-records-v4-install-result.txt','reading-records-v4-install.log','reading-records-diagnostic.txt','阅读记录诊断.txt')
    legacy_reports={p:p.read_bytes() for p in (docs/n for n in report_names) if p.is_file()}
    before={p.relative_to(us).as_posix():p.read_bytes() for folder in [base/'bin',base/'releases',base/'compat',base/'service',docs] for p in folder.rglob('*') if p.is_file() and p.name not in (BOOT,TAR,'reading-records-v4-install-result.txt','reading-records-v4-install.log')}
    before_metadata={p:p.read_bytes() for p in (base/'VERSION',base/'release-info') if p.is_file()}
    result=subprocess.run([SHELL,script.as_posix()],env=env,capture_output=True,timeout=INSTALL_TIMEOUT)
    log=(report_dir/'reading-records-v4-install.log').read_text(encoding='utf-8',errors='replace')
    failed=mutation in ('core_failure','activation_failure','interrupted','missing_payload','bad_checksum','cross_variant','ks_residue','wrong_device','unknown_formal','orphan','duplicate','busy_ui','cover_dir_file','cover_dir_symlink')
    assert (result.returncode!=0)==failed,(previous,mutation,result.returncode,result.stderr,log,(base/'install.log').read_text(errors='replace')[-2500:] if (base/'install.log').exists() else '')
    assert all(p.read_bytes()==raw for p,raw in protected.items())
    if failed:
        if mutation in ('cover_dir_file','cover_dir_symlink'):
            assert 'custom cover image directory path is occupied' in (base/'install.log').read_text(errors='replace')
            if mutation=='cover_dir_symlink':subprocess.run([SHELL,'-c','test -L "$1"','fixture',covers.as_posix()],env=env,check=True)
        assert all((us/path).is_file() and (us/path).read_bytes()==raw for path,raw in before.items()),(mutation,[path for path,raw in before.items() if not (us/path).is_file() or (us/path).read_bytes()!=raw])
        assert (docs/CLEAN).exists()==('documents/'+CLEAN in before)
        assert all(p.read_bytes()==raw for p,raw in before_metadata.items()),mutation
        assert (report_dir/'reading-records-v4-install.log').read_bytes().startswith(old_evidence_log)
        assert 'installation_status=failed' in (report_dir/'reading-records-v4-install-result.txt').read_text(encoding='utf-8')
    else:
        assert covers.is_dir() and not covers.is_symlink(), 'directory must exist before the dashboard is launched'
        if (base/'user.conf').exists():assert 'custom_cover_enabled=1' not in (base/'user.conf').read_text()
        assert (docs/'reading-records.sh').read_bytes()==(ROOT/'native-reading-time-package/阅读记录-entry.sh').read_bytes()
        if previous is None:assert (base/'reading-time.tsv').read_bytes()==b'date\tbook_id\tseconds\ttitle\n'
        assert (base/'VERSION').read_text().strip()==PRODUCT_VERSION
        assert (base/f'releases/{RUNTIME_VERSION}/bin/reading-records.sh').read_bytes()==(ROOT/'native-reading-time-package/阅读记录-optimized.sh').read_bytes()
        probe_path=base/f'releases/{RUNTIME_VERSION}/bin/reading-insights-touch-probe.lua'
        assert probe_path.read_bytes()==(ROOT/'native-reading-time-package/reading-insights-touch-probe.lua').read_bytes()
        assert (docs/CLEAN).is_file() and (base/'.previous-install').is_dir()
        assert script.is_file(), 'current same-name bootstrap was removed during migration'
        assert not ('PROTECTED unknown entry='+script.as_posix()) in log,log
        assert (docs/CLEAN).read_text(encoding='utf-8').splitlines()[1]=='# Name: 确认无误之后，再点这个'
        owned_viewers=[p.name for p in docs.glob('*.sh') if '# Name: 阅读记录' in p.read_text(encoding='utf-8',errors='replace').splitlines()]
        assert owned_viewers==['reading-records.sh']
        known_cleanup_names=('# Name: 安装文件清理','# Name: 确认无误之后，再点这个','# Name: 安装好之后，确认无误了再点这个')
        visible_cleanups=[p.name for p in docs.glob('*.sh') if any(name in p.read_text(encoding='utf-8',errors='replace').splitlines() for name in known_cleanup_names)]
        assert visible_cleanups==[CLEAN],visible_cleanups
        if mutation!='unknown_alias':assert not (docs/'阅读记录.sh').exists()
        assert not (docs/'reading-records-uninstall.sh').exists() and not (docs/'安装好之后，确认无误了再点这个.sh').exists()
        if previous in ('mixed','deleted-formal','V4','9.8.1-test2','9.8.1-test2-cleaned','9.8.1-test4','9.8.1-test4-cleaned','9.8.1-test5','9.8.1-test5-cleaned','9.8.1-test6','9.8.1-test6-cleaned','9.8.1-test7','9.8.1-test7-cleaned','9.8.1-test8','9.8.1-test8-cleaned','9.8.1-test10','9.8.1-test10-cleaned','9.8.1-test11','9.8.1-test11-cleaned','9.8.1','9.8.1-cleaned'):
            if mutation=='cover_dir_missing':covers.rmdir() # Repair must recreate it too.
            again=subprocess.run([SHELL,script.as_posix()],env=env,capture_output=True,timeout=INSTALL_TIMEOUT);assert again.returncode==0,again.stderr
            assert covers.is_dir()
            assert probe_path.read_bytes()==(ROOT/'native-reading-time-package/reading-insights-touch-probe.lua').read_bytes()
            assert len(list(base.glob('.previous-install')))==1 and not list(base.glob('.v4-rollback.*'))
        if mutation=='scanner_failure':assert 'scanner_request=request_failed index_completion=unverified' in log
        if cleanup:
            backup=session/'cleanup-copy.sh';shutil.copy2(docs/CLEAN,backup)
            active_runtime={p:p.read_bytes() for folder in (base/f'releases/{RUNTIME_VERSION}',base/'compat',base/'service') for p in folder.rglob('*') if p.is_file()}
            active_runtime.update({p:p.read_bytes() for p in (base/'bin/launch.sh',base/'bin/service-manager.sh',base/'bin/native-reading-time-daemon.sh',upstart/'native-reading-time.conf')})
            scanner_before=len((session/'scanner-calls').read_text(encoding='utf-8').splitlines())
            if cleanup_unknown:put(us/'native-reading-time-package/user-extra.txt',b'user unknown')
            if legacy_tag:
                from historical_packages import CATALOG,package
                ident={'v9.7.5-test.1':'V1','v9.7.5-compat-v2':'V2'}.get(legacy_tag,legacy_tag)
                _,old_files=package(next(row for row in CATALOG if row['id']==ident))
                for name,raw in old_files.items():
                    if name.startswith('native-reading-time-package/'):put(us/name,raw)
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
    archived_reports=[p.read_bytes() for p in (report_dir/'legacy').rglob('*') if p.is_file()]
    for p,raw in legacy_reports.items():
        assert (p.is_file() and p.read_bytes()==raw) or raw in archived_reports, ('lost legacy evidence',p)
    assert not any((docs/n).exists() for n in report_names if docs/n not in legacy_reports), 'automatic report entered library'
    assert (report_dir/'reading-records-v4-install-result.txt').is_file(), 'cleanup must retain internal evidence'
    if not failed:assert covers.is_dir(), 'installation cleanup must preserve the user image directory'
    calls=(session/'service-fixture/calls').read_text(errors='replace') if (session/'service-fixture/calls').exists() else ''
    if previous and not failed:
        assert 'stop native-reading-time' in calls and 'start native-reading-time' in calls,(mutation,calls)
    return {'package_sha256':package_sha,'scenario':str(previous or 'fresh')+' '+mutation,'result':'PASS','scanner_index_completion':'UNVERIFIED','protected_files':len(protected)}

def main():
    global SIMPLE_ARCHIVE
    results=[]
    cases=[(p,'',True) for p in (None,'9.7.4','V1','V2','V3','normal','V4','mixed','deleted-formal')]
    cases += [('mixed',m,False) for m in ('core_failure','activation_failure','interrupted','missing_payload','bad_checksum','cross_variant','ks_residue','wrong_device','unknown_formal','unknown_alias','duplicate','orphan','scanner_failure','lost_service','stopped_service','initial_rw','busy_ui')]
    cases += [('9.8.1-test1','',True),('9.8.1-test1-cleaned','',True),(None,'scanner_failure',True)]
    cases += [('9.8.1-test1',m,False) for m in ('core_failure','activation_failure','interrupted')]
    if '--device-fix' in sys.argv:
        # Same real package/transaction fixture; focus this device-only change
        # on fresh install, accepted-release upgrade, repair, and safety faults.
        cases=[(None,'',True),('V4','',True),('9.8.1-test1-cleaned','',True)]
        cases += [('mixed',m,False) for m in ('core_failure','activation_failure','interrupted','missing_payload','bad_checksum','cross_variant','ks_residue','wrong_device','unknown_formal','unknown_alias','duplicate','orphan','lost_service','stopped_service','initial_rw','busy_ui')]
    if '--smoke' in sys.argv:
        cases=[('V4','',True)]
    if '--power-upgrade' in sys.argv:
        cases=[('9.8.1-test4','',True),('9.8.1-test4-cleaned','',True)]
        cases += [('9.8.1-test4',m,False) for m in ('core_failure','activation_failure','interrupted','ks_residue','wrong_device','busy_ui')]
    if '--settings-upgrade' in sys.argv:
        cases=[(None,'',True),('9.8.1-test7','',True),('9.8.1-test7-cleaned','',True)]
        cases += [('9.8.1-test7',m,False) for m in ('core_failure','activation_failure','interrupted','ks_residue','wrong_device','busy_ui')]
    if '--idle-upgrade' in sys.argv:
        cases=[('V4','',True)]
        cases += [('V4',m,False) for m in ('core_failure','activation_failure','interrupted','lost_service','stopped_service','ks_residue','wrong_device','orphan','duplicate','busy_ui')]
    if '--cover-directory' in sys.argv or '--formal-release' in sys.argv:
        cases=[(None,'',True),('9.8.1-test8','cover_dir_missing',True),('9.8.1-test8','',True),
               ('9.8.1-test8','activation_failure',False),(None,'cover_dir_file',False),(None,'cover_dir_symlink',False)]
    if '--formal-release' in sys.argv:
        cases += [('V4','',True),('9.8.1-test8-cleaned','',True)]
        cases += [('9.8.1-test8',m,False) for m in ('core_failure','interrupted','ks_residue','wrong_device','busy_ui')]
    if '--touch-patch' in sys.argv:
        cases=[(None,'',True),('9.8.1','',True),('9.8.1-cleaned','',True)]
        cases += [('9.8.1',m,False) for m in ('core_failure','activation_failure','interrupted','missing_payload','bad_checksum','ks_residue','wrong_device','busy_ui')]
    if '--archive' in sys.argv:SIMPLE_ARCHIVE=Path(sys.argv[sys.argv.index('--archive')+1]).resolve()
    for p,m,c in cases:
        with tempfile.TemporaryDirectory(prefix='standard-install-',dir=OUT) as name:results.append(run(Path(name),previous=p,mutation=m,cleanup=c))
        print(p or 'fresh',m or 'install + cleanup','PASS',flush=True)
    for tag in (() if '--touch-patch' in sys.argv or '--formal-release' in sys.argv or '--cover-directory' in sys.argv or '--device-fix' in sys.argv or '--idle-upgrade' in sys.argv or '--smoke' in sys.argv or '--power-upgrade' in sys.argv or '--settings-upgrade' in sys.argv else ('v9.7.4','v9.7.5-test.1','v9.7.5-compat-v2','v9.7.5-compat-v3')):
        with tempfile.TemporaryDirectory(prefix='standard-legacy-',dir=OUT) as name:results.append(run(Path(name),previous='V3',cleanup=True,legacy_tag=tag))
        print('legacy payload',tag,'PASS',flush=True)
    if '--cover-directory' not in sys.argv:
        with tempfile.TemporaryDirectory(prefix='standard-unknown-',dir=OUT) as name:results.append(run(Path(name),previous='9.8.1' if '--touch-patch' in sys.argv else 'V4' if '--idle-upgrade' in sys.argv else 'V3',cleanup=True,cleanup_unknown=True))
    assert len({row['package_sha256'] for row in results})==1, 'Package changed during matrix; rerun against frozen ZIP'
    result_name='touch-patch-install-results.json' if '--touch-patch' in sys.argv else 'formal-release-install-results.json' if '--formal-release' in sys.argv else ('custom-cover-directory-install-results.json' if '--cover-directory' in sys.argv else 'standard-install-results.json')
    (OUT/result_name).write_text(json.dumps({'result':'PASS','checks':results,'hardware':'PENDING'},indent=2),encoding='utf-8')
if __name__=='__main__':main()
