"""KS exclusions, privacy, formal failure reproduction, and real install routes.

All hardware/service operations use isolated fixtures. No desktop or Kindle IO.
"""
from pathlib import Path
import hashlib, io, json, os, shutil, subprocess, sys, tarfile, tempfile, zipfile
from service_fixture import service_fixture
from validate_v4 import seed, put, chmod, SHELL, ROOT, OUT
sys.path.insert(0, str(ROOT/'scripts'))
from build_v4 import SIMPLE_ARCHIVE, BOOT_NAME, TAR_NAME, PRODUCT_VERSION, RUNTIME_VERSION

LIB=ROOT/'native-reading-time-package/compat/device_variant.sh'
AUDIT=ROOT/'build/standard-test2-audit'; AUDIT.mkdir(exist_ok=True)
SERIAL_SUFFIX='PRIVACY123'  # Synthetic only, never a real device identifier.
def usid(code): return ('G00'+code+SERIAL_SUFFIX).encode()

def inputs(folder, model=None, code=None, proc=None, sysmodel=None):
    env={}
    for key,name,raw in [('READING_DEVICETYPE_PATH','device',model),('READING_USID_PATH','usid',code),
                         ('READING_PROC_MODEL_PATH','proc-model',proc),('READING_SYS_MODEL_PATH','sys-model',sysmodel)]:
        path=folder/name
        if raw==b'DIRECTORY':path.mkdir()
        elif raw is not None:put(path,raw)
        env[key]=path.as_posix()
    return env

checks=[]
def receipt(kind, scenario, **extra):
    checks.append({'kind':kind,'scenario':scenario,'result':'PASS',**extra})

ks_codes=['27J','2BL','263','227','2BM','23L','23M','270','3V0','3V1','3X5','3UV','3X4','3X3','41E','41D',
          '4PG','4PE','4PL','4F8','4FA','454','4VX','4PF','4PH','4F9','4FB','46P']
cases=[('no-information',None,None,None,None,'unknown'),('empty-model',b'',None,None,None,'unknown'),
       ('whitespace-model',b' \r\n',None,None,None,'unknown'),('unreadable-source',b'DIRECTORY',None,None,None,'unknown'),
       ('future-model',b'Kindle Future 2030',usid('ZZZ'),None,None,'unknown'),
       ('generic-kindlename',b'Kindle',None,None,None,'unknown'),
       ('KC-blank-model',b'',usid('3H9'),None,None,'standard'),
       ('PW6-missing-model',None,usid('3HA'),None,None,'standard'),
       ('basic-model',b'Kindle Basic 2024',None,None,None,'standard'),
       ('old-scheme',None,b'B024'+('X'*12).encode(),None,None,'standard'),
       ('old-9-scheme',None,b'9024'+('X'*12).encode(),None,None,'standard'),
       ('short-usid-known-KS-prefix',None,b'G0027J',None,None,'ks'),
       ('unknown-usid-suffix-known-KS-prefix',None,b'G0027J'+b'!'*10,None,None,'ks'),
       ('invalid-short-usid',None,b'G0027',None,None,'unknown'),
       ('invalid-usid-prefix',None,b'G00!7J'+b'A'*10,None,None,'unknown'),
       ('empty-usid',None,b'',None,None,'unknown'),
       ('KS-model',b'KindleScribe',None,None,None,'ks'),
       ('KS-lowercase',b'kindle scribe 2024\r\n',None,None,None,'ks'),
       ('KS-short',b'KS2',None,None,None,'ks'),
       ('KS-tree',None,None,b'Kindle Scribe\0',None,'ks'),
       ('KS-sys-tree',None,None,None,b'Kindle Scribe Colorsoft\0','ks'),
       ('ordinary-colorsoft',b'Kindle Colorsoft',None,None,None,'standard'),
       ('color-scribe',b'Kindle Scribe Colorsoft',None,None,None,'ks'),
       ('no-substring-KS-false-positive',b'UNKNOWNBOOKS',None,None,None,'unknown'),
       ('KS-vs-KC',b'KindleColorsoft',usid('27J'),None,None,'conflict'),
       ('KS-vs-PW6',b'KindleScribe',usid('3HA'),None,None,'conflict'),
       ('KS-vs-basic',b'KindleScribe',usid('3L5'),None,None,'conflict'),
       ('tree-conflict',b'KPW6',None,b'Kindle Scribe\0',None,'conflict'),
       ('tree-tree-conflict',None,None,b'Kindle Colorsoft\0',b'Kindle Scribe\0','conflict'),
       ('ks-and-unknown',b'New unknown device',usid('27J'),None,None,'ks'),
       ('sources-agree',b'KS',usid('27J'),b'Kindle Scribe\0',None,'ks'),
       ('usid-lowercase-crlf',None,usid('27J').lower()+b'\r\n',None,None,'ks'),
       ('usid-nul-terminated',None,usid('27J')+b'\0',None,None,'ks')]
cases += [('KS-code-'+c,None,usid(c),None,None,'ks') for c in ks_codes]
cases += [('KC-code-'+c,None,usid(c),None,None,'standard') for c in ('3H9','3H4','3HB','3H6','3H2','34X','3H7','3JT','3J6','456','455','4EP')]

def assert_private(folder, captured=''):
    text=captured+'\n'+'\n'.join(p.read_text(encoding='utf-8',errors='replace') for p in folder.rglob('*')
        if p.is_file() and (p.suffix in ('.log','.txt') or p.name=='calls'))
    assert SERIAL_SUFFIX not in text and SERIAL_SUFFIX.lower() not in text, text[-1000:]
    assert 'G0027J'+SERIAL_SUFFIX not in text

def test_library():
    for shell in (SHELL,shutil.which('dash') or 'C:/Program Files/Git/usr/bin/dash.exe'):
        subprocess.run([shell,'-n',LIB.as_posix()],check=True,capture_output=True)
        for label,model,code,proc,sysmodel,expected in cases:
            with tempfile.TemporaryDirectory(prefix='device-unit-',dir=OUT) as name:
                folder=Path(name); env={**os.environ,**inputs(folder,model,code,proc,sysmodel),'PATH':'/usr/bin:/bin:'+os.environ.get('PATH','')}
                child=subprocess.run([shell,'-c','. "$1"; rr_device_log() { printf "%s\\n" "$*"; }; rr_detect_device_variant; printf "FINAL=%s\\n" "$RR_DEVICE_VARIANT"','test',LIB.as_posix()],env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=10)
                assert child.returncode==0 and 'FINAL='+expected in child.stdout,(label,child.stdout,child.stderr)
                assert child.stdout.count('device_source=')==4
                assert_private(folder,child.stdout+child.stderr)
                if expected=='unknown':assert 'device_decision=allow_unconfirmed' in child.stdout and 'model_confirmation=unconfirmed' in child.stdout
                if label=='unreadable-source':assert 'status=unreadable' in child.stdout
                receipt('detector',label,shell=Path(shell).name,classification=expected)
    # Force an actual read failure independent of host ACL/root semantics.
    with tempfile.TemporaryDirectory(prefix='device-read-fail-',dir=OUT) as name:
        folder=Path(name); env={**os.environ,**inputs(folder,b'KPW6')}
        child=subprocess.run([SHELL,'-c','. "$1"; awk() { return 1; }; rr_device_log() { printf "%s\\n" "$*"; }; rr_detect_device_variant','test',LIB.as_posix()],env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=10)
        assert 'device_source=deviceType status=read_failed classification=unknown' in child.stdout
        receipt('detector','read-system-call-failure')

def environment(folder, previous, spec):
    us,base,docs,upstart,protected=seed(folder,previous)
    tmp=folder/'tmp';tmp.mkdir();mock=folder/'mockbin';mock.mkdir()
    for name,body in [('fbink','exit 0'),('lua','exit 0'),('lipc-get-prop','echo active'),('lipc-set-prop','exit 0')]:put(mock/name,('#!/bin/sh\n'+body+'\n').encode())
    chmod(*mock.iterdir())
    env={**os.environ,'PATH':mock.as_posix()+':/usr/bin:/bin:'+os.environ.get('PATH',''),
         'READING_MNT_US':us.as_posix(),'READING_BASE':base.as_posix(),'READING_DOCUMENTS':docs.as_posix(),
         'READING_TMPDIR':tmp.as_posix(),'READING_ALLOW_NONROOT_TEST':'1','READING_UI_LOCK':(tmp/'ui.lock').as_posix(),
         'READING_PRODUCT_VERSION':PRODUCT_VERSION}
    env.update(service_fixture(folder/'service-fixture',base,upstart,SHELL,running=bool(previous)))
    env.update(inputs(folder,*spec))
    put(folder/'pretty',b'Kindle 5.20.1');env['READING_PRETTYVERSION_PATH']=(folder/'pretty').as_posix()
    put(folder/'loader',b'loader');env['READING_ARMHF_LOADER_PATH']=(folder/'loader').as_posix()
    return env,us,base,docs,protected

def test_routes():
    integration=[c for c in cases if c[0] in ('no-information','KC-blank-model','unreadable-source','future-model',
        'KS-model','KS-code-3V0','KS-tree','KS-vs-KC','KS-vs-PW6')]
    integration += [('KS-residue',None,None,None,None,'residue'),('KS-version-conflict',None,None,None,None,'residue')]
    with zipfile.ZipFile(SIMPLE_ARCHIVE) as z:bootstrap=z.read(BOOT_NAME);raw=z.read(TAR_NAME)
    # Bootstrap calls the same library embedded before extraction.
    assert LIB.read_bytes() in bootstrap
    for previous in (None,'V4'):
        for row in integration:
            label,*spec,expected=row
            with tempfile.TemporaryDirectory(prefix='device-bootstrap-',dir=OUT) as name:
                folder=Path(name);env,us,base,docs,protected=environment(folder,previous,spec)
                put(docs/BOOT_NAME,bootstrap);put(docs/TAR_NAME,raw)
                if expected=='residue':
                    put(base/'release-info',b'variant=standard\n')
                    put(base/('bin/launch-ks.sh' if label=='KS-residue' else 'VERSION'),b'9.7.5-ks-test1\n')
                before={p:p.read_bytes() for tree in (base/'bin',base/'releases',base/'compat',base/'service') for p in tree.rglob('*') if p.is_file()}
                child=subprocess.run([SHELL,(docs/BOOT_NAME).as_posix()],env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=130)
                blocked=expected in ('ks','conflict','residue')
                log=(docs/'reading-records-v4-install.log').read_text(encoding='utf-8',errors='replace')
                result=(docs/'reading-records-v4-install-result.txt').read_text(encoding='utf-8')
                assert (child.returncode!=0)==blocked,(label,previous,child.stderr,log)
                assert all(p.read_bytes()==v for p,v in protected.items())
                if blocked:
                    assert 'installation_status=failed' in result and not (docs/'reading-records-install-cleanup.sh').exists()
                    assert all(p.read_bytes()==v for p,v in before.items())
                    assert not (folder/'service-fixture/calls').exists(),'Blocked device reached system service operations'
                    assert not list(base.glob('.v4-rollback.*'))
                else:
                    assert 'installation_status=installed' in result and f'product_version={PRODUCT_VERSION}' in result
                    assert f'runtime_release={base.as_posix()}/releases/{RUNTIME_VERSION}' in (base/'release-info').read_text(encoding='utf-8')
                    assert 'device variant unknown' not in log
                    # Successful rerun is the packaged repair path; same unknown evidence.
                    again=subprocess.run([SHELL,(docs/BOOT_NAME).as_posix()],env=env,capture_output=True,timeout=130)
                    assert again.returncode==0,again.stderr
                assert_private(folder,child.stdout+child.stderr)
                receipt('bootstrap-upgrade' if previous else 'bootstrap-fresh',label,classification=expected,repair_rerun=not blocked)
                print('bootstrap',previous or 'fresh',label,'PASS',flush=True)
    with tempfile.TemporaryDirectory(prefix='device-core-payload-',dir=OUT) as name:
        payload=Path(name)
        with tarfile.open(fileobj=io.BytesIO(raw)) as t:t.extractall(payload,filter='data')
        pkg=payload/'native-reading-time-package'
        assert (pkg/'compat/device_variant.sh').read_bytes()==LIB.read_bytes()
        for action in ('install','upgrade','repair'):
            for row in integration:
                label,*spec,expected=row
                with tempfile.TemporaryDirectory(prefix='device-core-',dir=OUT) as name:
                    folder=Path(name);env,us,base,docs,protected=environment(folder,None if action=='install' else 'V4',spec)
                    env['READING_PACKAGE_DIR']=pkg.as_posix()
                    if expected=='residue':
                        put(base/'release-info',b'variant=standard\n')
                        put(base/('bin/launch-ks.sh' if label=='KS-residue' else 'VERSION'),b'9.7.5-ks-test1\n')
                    child=subprocess.run([SHELL,(pkg/'install.sh').as_posix(),action],env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=130)
                    blocked=expected in ('ks','conflict','residue');log=(base/'install.log').read_text(encoding='utf-8',errors='replace')
                    assert (child.returncode!=0)==blocked,(label,action,child.stderr,log)
                    assert all(p.read_bytes()==v for p,v in protected.items())
                    assert 'device variant unknown' not in log
                    if blocked:
                        calls=folder/'service-fixture/calls'
                        rows=calls.read_text(encoding='utf-8').splitlines() if calls.exists() else []
                        # Failure diagnostics may inspect service status, but
                        # must not remount, start, stop, or reload anything.
                        assert all(r.startswith('status ') for r in rows),rows
                    else:assert (base/f'releases/{RUNTIME_VERSION}/bin/reading-records.sh').is_file()
                    assert_private(folder,child.stdout+child.stderr)
                    receipt('core-'+action,label,classification=expected)
                    print('core',action,label,'PASS',flush=True)

def reproduce_formal():
    formal=ROOT/'build/formal-candidate/9.7.6-5.20.1-vera.zip'
    before=hashlib.sha256(formal.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='device-formal-repro-',dir=OUT) as name:
        folder=Path(name);env,us,base,docs,protected=environment(folder,None,(b'',usid('3H9'),None,None))
        with zipfile.ZipFile(formal) as z:z.extractall(docs)
        child=subprocess.run([SHELL,(docs/BOOT_NAME).as_posix()],env=env,capture_output=True,timeout=130)
        result=(docs/'reading-records-v4-install-result.txt').read_text(encoding='utf-8')
        assert child.returncode==1 and 'error=device variant unknown' in result and 'build_id=fc4e9d8b7c1b4403436e' in result,result
        assert not (folder/'service-fixture/calls').exists()
        receipt('formal-reproduction','KC-empty-deviceType',exit_code=1,build_id='fc4e9d8b7c1b4403436e')
    assert hashlib.sha256(formal.read_bytes()).hexdigest()==before

if __name__=='__main__':
    test_library();print('Device detector cases PASS',len(checks),flush=True)
    reproduce_formal();print('Original formal failure reproduced PASS',flush=True)
    test_routes()
    report={'result':'PASS','product_version':PRODUCT_VERSION,'checks':checks,
        'package_sha256':hashlib.sha256(SIMPLE_ARCHIVE.read_bytes()).hexdigest(),'hardware':'PENDING'}
    (AUDIT/'device-identification-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Device identification:',len(checks),'PASS',flush=True)
