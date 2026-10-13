"""Frozen Standard acceptance; independent fixtures run in bounded parallel phases."""
from pathlib import Path
import concurrent.futures,hashlib,json,shutil,subprocess,sys,time
from validate_all import CHECKS,ROOT
OUT=ROOT/'build/validation';OUT.mkdir(exist_ok=True)
report_path=OUT/'stable-suite-results.json'
previous=json.loads(report_path.read_text()) if report_path.exists() else None
if previous:(OUT/f'standard-prior-attempt-{time.time_ns()}.json').write_text(json.dumps(previous,indent=2),encoding='utf-8')
old={x['check']:x for x in previous['checks']} if previous else {}
source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('native-reading-time-package','v4') for p in (ROOT/folder).rglob('*') if p.is_file()}
reuse='--retry-failed' in sys.argv and previous is not None and previous.get('source_hashes')==source_hashes
if '--retry-failed' in sys.argv and not reuse:raise SystemExit('Frozen source hashes changed: start a fresh full run')
results={}
def execute(check):
    name=check.relative_to(ROOT).as_posix();started=time.monotonic()
    if reuse and name in old and old[name]['exit_code']==0:
        return {**old[name], 'reused_identical_frozen_sources': True}
    interpreter=sys.executable if check.suffix=='.py' else (shutil.which('sh') or 'C:/Program Files/Git/bin/sh.exe')
    with (OUT/('frozen-'+check.stem+'.log')).open('wb') as log:
        result=subprocess.run([interpreter,str(check)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    row={'check':name,'exit_code':result.returncode,'elapsed_seconds':round(time.monotonic()-started,2)}
    if name in old:row['previous_attempt']=old[name]
    print(name,'PASS' if result.returncode==0 else 'FAIL',row['elapsed_seconds'],flush=True)
    return row
builder=next(c for c in CHECKS if c.name=='build_v4.py')
packages=[c for c in CHECKS if c.name in ('validate_v4.py','validate_5201_install.py','validate_device_variant.py')]
last=[c for c in CHECKS if c.name in ('check_v4_runtime.py','audit_v4_startup.py','verify_v4_artifacts.py','validate_standard_migration_safety.py','validate_startup_performance.py','validate_launcher_state.py')]
first=[c for c in CHECKS if c not in [builder,*packages,*last]]
for phase,workers in [(first,3),([builder],1),(packages,2),([c for c in last if c.name!='validate_startup_performance.py'],3),([c for c in last if c.name=='validate_startup_performance.py'],1)]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(execute,phase):results[row['check']]=row
    interim={'result':'IN_PROGRESS','checks':[results[c.relative_to(ROOT).as_posix()] for c in CHECKS if c.relative_to(ROOT).as_posix() in results]}
    (OUT/'standard-frozen-progress.json').write_text(json.dumps(interim,indent=2),encoding='utf-8')
    if any(row['exit_code'] for row in results.values()):
        # Do not advance into package delivery after a failed prerequisite.
        break
for name,digest in source_hashes.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,'Source changed during frozen validation: '+name
all_results=[results[c.relative_to(ROOT).as_posix()] for c in CHECKS if c.relative_to(ROOT).as_posix() in results]
passed=len(all_results)==len(CHECKS) and all(row['exit_code']==0 for row in all_results)
report={'result':'PASS' if passed else 'FAIL','scope':'Standard only; all registered checks verified against identical frozen source hashes','checks':all_results,'registered_checks':len(CHECKS),'source_hashes':source_hashes}
report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Frozen Standard acceptance:',report['result'],len(all_results),'/',len(CHECKS),flush=True)
if not passed:raise SystemExit(1)
