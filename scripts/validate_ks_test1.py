"""KS-only offline acceptance; existing artifacts are never rebuilt or replaced."""
from pathlib import Path
import concurrent.futures, hashlib, json, subprocess, sys, time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/ks-test1-audit'; OUT.mkdir(exist_ok=True)
CHECKS = [
    ['tests/validate_ks.py'], ['tests/validate_ks_install.py'],
    ['tests/validate_ks_touch_compat.py'], ['tests/validate_ks_compat_sync.py'],
    ['tests/validate_ks_layout_flow.py'], ['tests/validate_ks_renderer_contract.py'],
    ['tests/validate_ks_test1_launcher.py'],
    ['tests/validate_ks_test1_devices.py'], ['tests/validate_ks_test1_install.py'],
    ['tests/validate_ks_test1_runtime.py','runtime'],
    ['tests/validate_ks_test1_runtime.py','framebuffer'],
    ['tests/validate_ks_test1_runtime.py','service'],
]
hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('ks-package','native-reading-time-package') for p in (ROOT/folder).rglob('*') if p.is_file()}
path=OUT/'regression.json'
previous=json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
retry='--retry-failed' in sys.argv
if previous:
    (OUT/f'prior-attempt-{time.time_ns()}.json').write_text(json.dumps(previous,indent=2),encoding='utf-8')
if retry and (not previous or previous['source_hashes']!=hashes):raise SystemExit('Production source changed: run all checks again')
old={r['check']:r for r in previous['checks']} if previous else {}

def execute(command):
    name=' '.join(command)
    if retry and name in old and old[name]['exit_code']==0:return {**old[name],'reused_identical_sources':True}
    started=time.monotonic()
    log=OUT/('check-'+Path(command[0]).stem+('-'+command[1] if len(command)>1 else '')+'.log')
    with log.open('wb') as output:
        result=subprocess.run([sys.executable,*command],cwd=ROOT,stdout=output,stderr=subprocess.STDOUT)
    row={'check':name,'exit_code':result.returncode,'seconds':round(time.monotonic()-started,2),'log':str(log)}
    if name in old:row['previous_attempt']=old[name]
    print(name,'PASS' if result.returncode==0 else 'FAIL',flush=True)
    return row

# Package acceptance uses its own three independent fixtures; run separately
# to avoid host-load timeouts concealing device-side bounded-command failures.
package=[c for c in CHECKS if c[0]=='tests/validate_ks_test1_install.py']
others=[c for c in CHECKS if c not in package]
rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    rows.extend(pool.map(execute,others))
rows.extend(execute(c) for c in package)
for name,digest in hashes.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,'Source changed during tests: '+name
report={'result':'PASS' if all(row['exit_code']==0 for row in rows) else 'FAIL','checks':rows,'source_hashes':hashes,
        'package_sha256':hashlib.sha256((ROOT/'build/ks-test1/9.7.6-5.20.1-vera-KS-test1.zip').read_bytes()).hexdigest()}
path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if report['result']!='PASS':raise SystemExit(1)
