"""Inject denied read permissions without changing host ACLs or requiring root."""
from pathlib import Path
import json, os, shutil, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/standard-test2-audit'
OUT.mkdir(parents=True,exist_ok=True)
LIB=ROOT/'native-reading-time-package/compat/device_variant.sh'
SH=shutil.which('sh') or 'C:/Program Files/Git/usr/bin/sh.exe'
DASH=shutil.which('dash') or 'C:/Program Files/Git/usr/bin/dash.exe'
checks=[]
for shell in (SH,DASH):
    for label,code,deny_usid,expected in [('unreadable-all',None,False,'unknown'),
        ('unreadable-model-KS-usid','27J',False,'ks'),('unreadable-usid','27J',True,'unknown')]:
        with tempfile.TemporaryDirectory(prefix='device-permission-',dir=OUT) as name:
            folder=Path(name);model=folder/'model';model.write_bytes(b'Kindle Scribe')
            usid=folder/'usid'
            if code:usid.write_bytes(('G00'+code+'PRIVACY123').encode())
            env={**os.environ,'PATH':'/usr/bin:/bin:'+os.environ.get('PATH',''),
                'READING_DEVICETYPE_PATH':model.as_posix(),'READING_USID_PATH':usid.as_posix(),
                'READING_PROC_MODEL_PATH':(folder/'no-tree').as_posix(),'READING_SYS_MODEL_PATH':(folder/'no-sys-tree').as_posix(),
                'DENY_USID':'1' if deny_usid else '0'}
            # Override only the read-access predicate when sourcing the library.
            # This deterministically models EACCES on MSYS and privileged Linux,
            # where chmod(000) alone cannot prove a read is denied.
            program='''
rr_test() {
    if command '[' "$1" = '-r' ]; then
        command '[' "$2" != "$READING_DEVICETYPE_PATH" ] || return 1
        if command '[' "$DENY_USID" = 1 ]; then command '[' "$2" != "$READING_USID_PATH" ] || return 1; fi
    fi
    command '[' "$@"
}
alias '['='rr_test'
. "$1"
rr_device_log() { printf '%s\\n' "$*"; }
rr_detect_device_variant
printf 'FINAL=%s\\n' "$RR_DEVICE_VARIANT"
'''
            child=subprocess.run([shell,'-c',program,'fixture',LIB.as_posix()],env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=10)
            assert child.returncode==0 and 'FINAL='+expected in child.stdout,(child.stdout,child.stderr)
            assert 'device_source=deviceType status=unreadable classification=unknown' in child.stdout
            if deny_usid:assert 'device_source=proc_usid status=unreadable classification=unknown' in child.stdout
            assert 'PRIVACY123' not in child.stdout+child.stderr
            checks.append({'scenario':label,'shell':Path(shell).name,'classification':expected,'result':'PASS'})
(OUT/'device-permission-results.json').write_text(json.dumps({'result':'PASS','checks':checks},indent=2),encoding='utf-8')
print('Denied device-source read permissions:',len(checks),'PASS')
