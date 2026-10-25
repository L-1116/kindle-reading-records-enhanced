"""Report placement, exact legacy conservation and automatic/manual diagnostics."""
from pathlib import Path
import hashlib, io, json, os, shutil, subprocess, sys, tarfile, tempfile, zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_v4 import SIMPLE_ARCHIVE, BOOT_NAME, TAR_NAME, make_tar, posix_cksum
SHELL=shutil.which('sh') or 'C:/Program Files/Git/usr/bin/sh.exe'
if '--dash' in sys.argv:
    SHELL=shutil.which('dash') or 'C:/Program Files/Git/usr/bin/dash.exe'
OUT=ROOT/'build/validation/install-test12';OUT.mkdir(parents=True,exist_ok=True)
checks=[]
def check(name):
    checks.append(name);print('PASS:',name,flush=True)
def shell(body,env,expect=0):
    p=subprocess.run([SHELL,'-c',body],env=env,capture_output=True,timeout=100)
    assert p.returncode==expect,(body,p.returncode,p.stdout[-1000:],p.stderr[-2000:])
    return p
with tempfile.TemporaryDirectory(prefix='reports-',dir=OUT) as tmp:
    root=Path(tmp); base=root/'reading-time';docs=root/'documents'
    base.mkdir();docs.mkdir()
    env={**os.environ,'PATH':'/usr/bin:/bin:'+os.environ.get('PATH',''),'READING_BASE':base.as_posix(),'READING_DOCUMENTS':docs.as_posix(),
         'READING_PACKAGE_DIR':(root/'missing-package').as_posix(),'READING_MNT_US':root.as_posix(),
         'READING_DETECT_ENV':(root/'missing-detector').as_posix(),
         'MSYS':'winsymlinks:sys','BASE':base.as_posix(),'DOCS':docs.as_posix(),
         'LIB':(ROOT/'native-reading-time-package/compat/migration.sh').as_posix(),
         'DIAG':(ROOT/'native-reading-time-package/diagnostics.sh').as_posix()}
    diag_cmd='/bin/sh "$DIAG"'
    shell(diag_cmd,{**env,'READING_DIAGNOSTIC_INTERNAL':'install','READING_DIAGNOSTIC_PATH':(docs/'override.txt').as_posix()})
    install_diag=base/'install-logs/last-install-diagnostic.txt'
    assert install_diag.is_file() and not list(docs.iterdir())
    shell(diag_cmd,{**env,'READING_DIAGNOSTIC_INTERNAL':'1','READING_DIAGNOSTIC_PATH':(docs/'override.txt').as_posix()})
    assert (base/'last-launch-diagnostic.txt').is_file() and not list(docs.iterdir())
    check('install and launch automatic diagnostics ignore manual overrides and never create library documents')
    shell(diag_cmd,env)
    diagnostic=(docs/'reading-records-diagnostic.txt').read_bytes()
    assert (docs/'阅读记录诊断.txt').read_bytes()==diagnostic
    check('explicit manual diagnostic export remains available with original names')
    result=('timestamp=Fri Oct 23 12:00:00 UTC 2026\nexit_code=0\nerror=none\nvariant=standard\n'
            'timing_status=unverified\ninstallation_status=installed\nproduct_version=9.8.1-5.20-vera-test11\n'
            'build_id=f50171a113490014541f\nformal_entry='+docs.as_posix()+'/reading-records.sh\n'
            'device_variant=standard\ndevice_decision=allow\ndevice_reason=recognized\ndevice_sources=fixture\n').encode()
    log=b'Fri Oct 23 12:00:00 UTC 2026: two-file bootstrap started variant=standard\nmode=upgrade installed_variant=standard\n'
    legacy={'reading-records-v4-install-result.txt':result,'reading-records-v4-install.log':log,
            'reading-records-diagnostic.txt':diagnostic,'阅读记录诊断.txt':diagnostic}
    for n,raw in legacy.items():(docs/n).write_bytes(raw)
    source='. "$LIB"; note() { printf "%s\\n" "$*" >> "$BASE/archive-test.log"; }; rr_archive_legacy_reports'
    archive_run=shell(source,env)
    assert not list(docs.iterdir()), ([p.name for p in docs.iterdir()], archive_run.stderr.decode(errors='replace'), (base/'archive-test.log').read_text(encoding='utf-8'))
    for n,raw in legacy.items(): assert any(p.read_bytes()==raw for p in (base/'install-logs/legacy').rglob(n))
    assert install_diag.is_file()
    shell(source,env)
    check('all recognized old reports archived byte-for-byte; current internal evidence retained; repeat is safe')
    for n in legacy:(docs/n).write_bytes(b'user document with a reserved-looking name')
    shell(source,env)
    assert all((docs/n).read_bytes()==b'user document with a reserved-looking name' for n in legacy)
    for n in legacy:(docs/n).unlink()
    (docs/'reading-records-diagnostic.txt').mkdir()
    target=root/'personal.txt';target.write_bytes(b'private target')
    env['TARGET']=target.as_posix()
    shell('ln -s "$TARGET" "$DOCS/reading-records-v4-install-result.txt"; test -L "$DOCS/reading-records-v4-install-result.txt"',env)
    shell(source,env)
    shell('test -L "$DOCS/reading-records-v4-install-result.txt"',env)
    assert target.read_bytes()==b'private target'
    shell('rm "$DOCS/reading-records-v4-install-result.txt"',env)
    (docs/'reading-records-diagnostic.txt').rmdir()
    check('unknown contents, directories and symlinks are preserved')
    for name,override in [('copy_failure','cp() { return 1; }; '),
                          ('verification_failure','cp() { command cp "$@"; printf X >> "$2"; }; '),
                          ('source_changed','cp() { command cp "$@"; printf X >> "$1"; }; ')]:
        p=docs/'reading-records-v4-install-result.txt';p.write_bytes(result)
        shell(override+source,env)
        expected=result+b'X' if name=='source_changed' else result
        assert p.read_bytes()==expected
        p.unlink()
    check('copy failure, changed destination and changed source never remove the original')
    legacy_dir=base/'install-logs/legacy'
    # Keep all prior evidence; replace only the isolated test's directory location.
    legacy_dir.rename(base/'saved-legacy')
    legacy_dir.write_bytes(b'foreign file at archive path')
    p=docs/'reading-records-v4-install-result.txt';p.write_bytes(result)
    shell(source,env)
    assert p.read_bytes()==result and legacy_dir.read_bytes()==b'foreign file at archive path'
    p.unlink()
    check('unavailable archive preserves reports and foreign archive-path content')
    with zipfile.ZipFile(SIMPLE_ARCHIVE) as z:
        boot=z.read(BOOT_NAME); payload=z.read(TAR_NAME)
    for name in ('missing','mixed_test10','mixed_test11','bad_checksum','bad_identity'):
        case=root/name;d=case/'documents';b=case/'reading-time';d.mkdir(parents=True)
        script=d/BOOT_NAME;script.write_bytes(boot)
        e={**env,'READING_BASE':b.as_posix(),'READING_DOCUMENTS':d.as_posix()}
        if name!='missing':
            raw=payload
            if name.startswith('mixed_'):
                old=ROOT/('build/idle-startup-candidate/9.8.1-5.20-vera-test10.zip' if name.endswith('10') else
                          'dist/standard-9.8.1-test11/Kindle-Reading-Records-v9.8.1-5.20-vera-test11.zip')
                with zipfile.ZipFile(old) as z:raw=z.read(TAR_NAME)
            elif name=='bad_checksum':raw=bytes([raw[0]^1])+raw[1:]
            elif name=='bad_identity':
                with tarfile.open(fileobj=io.BytesIO(raw)) as t:files={m.name:t.extractfile(m).read() for m in t}
                files['V4-PAYLOAD']=files['V4-PAYLOAD'].replace(b'test12',b'test99')
                raw=make_tar(files)
                import re
                altered=re.sub(rb"PAYLOAD_CKSUM='[0-9]+'",b"PAYLOAD_CKSUM='"+str(posix_cksum(raw)).encode()+b"'",boot)
                altered=re.sub(rb"PAYLOAD_SIZE='[0-9]+'",b"PAYLOAD_SIZE='"+str(len(raw)).encode()+b"'",altered)
                script.write_bytes(altered)
            (d/TAR_NAME).write_bytes(raw)
        # Identity check follows device guard. Isolate only the synthetic device
        # detector function, leaving the packaged payload checksum/identity logic exact.
        if name=='bad_identity':
            current=script.read_bytes().replace(b"rr_standard_install_guard || fail",b"true || fail")
            script.write_bytes(current)
        run=subprocess.run([SHELL,script.as_posix()],env=e,capture_output=True,timeout=120)
        assert run.returncode!=0,(name,run.stdout,run.stderr)
        report=(b/'install-logs/reading-records-v4-install-result.txt').read_text(encoding='utf-8')
        assert 'installation_status=failed' in report
        if name=='bad_identity':assert 'error=payload identity invalid' in report
        assert not list(d.glob('*.txt')) and not list(d.glob('*.log'))
        assert not (b/'bin').exists()
    check('missing, mixed test10/test11, corrupt and mismatched-identity payloads fail before activation; evidence stays internal')
    # Unsafe evidence storage must fail before writing through any linked path.
    for kind in ('file','link'):
        case=root/('report-dir-'+kind);d=case/'documents';b=case/'reading-time';d.mkdir(parents=True);b.mkdir()
        script=d/BOOT_NAME;script.write_bytes(boot)
        outside=case/'outside';outside.mkdir()
        if kind=='file':(b/'install-logs').write_bytes(b'personal data')
        else:
            e={**env,'REPORT_LINK':(b/'install-logs').as_posix(),'TARGET':outside.as_posix()}
            shell('ln -s "$TARGET" "$REPORT_LINK"',e)
        run=subprocess.run([SHELL,script.as_posix()],env={**env,'READING_BASE':b.as_posix(),'READING_DOCUMENTS':d.as_posix()},capture_output=True,timeout=60)
        assert run.returncode!=0 and not list(outside.iterdir())
        assert not list(d.glob('*.txt')) and not list(d.glob('*.log'))
        if kind=='file':assert (b/'install-logs').read_bytes()==b'personal data'
    check('occupied or linked report directory aborts safely without touching outside paths or creating library reports')
(OUT/('report-results-dash.json' if '--dash' in sys.argv else 'report-results.json')).write_text(json.dumps({'result':'PASS','shell':SHELL,'checks':checks,'hardware_verified':False},indent=2)+'\n',encoding='utf-8')

