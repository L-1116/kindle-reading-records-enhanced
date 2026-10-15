"""Frozen Standard 9.8.1 acceptance, scoped to the requested 9.7.6 upgrade."""
from pathlib import Path
import concurrent.futures, hashlib, json, shutil, subprocess, sys, time
from validate_all import ROOT, CHECKS

OUT=ROOT/'build/validation'; OUT.mkdir(parents=True,exist_ok=True)
REPORT=OUT/'idle-release-results.json'
# Historical migration permutations and comparisons with old host startup
# chains remain available through validate_all; this target uses the actual
# accepted 9.7.6 daemon and the same transaction/cleanup fixtures.
PACKAGED={'validate_device_variant.py','validate_device_variant_permissions.py','check_v4_runtime.py','verify_v4_artifacts.py','audit_v4_startup.py','validate_standard_migration_safety.py','validate_launcher_state.py','validate_v4.py'}
OMIT={'build_v4.py','validate_v4.py','validate_5201_install.py','validate_startup_performance.py','validate_device_variant.py','validate_device_variant_permissions.py'}
PRE=[c for c in CHECKS if c.name not in OMIT and c.name not in {'check_v4_runtime.py','verify_v4_artifacts.py','audit_v4_startup.py','validate_standard_migration_safety.py','validate_launcher_state.py'}]
POST=[c for c in CHECKS if c.name in PACKAGED and c.name!='validate_v4.py']
HASHES={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('native-reading-time-package','v4') for p in (ROOT/folder).rglob('*') if p.is_file()}
old=json.loads(REPORT.read_text()) if '--retry-failed' in sys.argv and REPORT.exists() else {}
changed={name for name in set(old.get('source_hashes',{}))|set(HASHES) if old.get('source_hashes',{}).get(name)!=HASHES.get(name)} if old else set()
idle_only={'native-reading-time-package/reading-idle.sh','native-reading-time-package/reading-idle-touch.lua','native-reading-time-package/reading-config.sh'}
if changed and not changed<=idle_only: raise SystemExit('UI/installer source changed; start a fresh run')
prior={r['check']:r for r in old.get('checks',[])}
if changed:
    # Dashboards never load the daemon's private idle helpers. Reuse their
    # proven unchanged inputs; rerun timing, process lifetime, installation,
    # packaging and all checks that consume the ZIP after a helper-only fix.
    affected=PACKAGED|{'validate_idle_pause.py','validate_idle_guard.py','validate_settings_ui.py','validate_install.py','build_v4.py'}
    prior={name:{**row,'reused_after_private_idle_fix':True} for name,row in prior.items()
           if Path(name.split(' ')[0]).name not in affected}
recheck={arg.split('=',1)[1] for arg in sys.argv if arg.startswith('--recheck=')}
rows=[]
def run(item):
    check,args=item if isinstance(item,tuple) else (item,[])
    name=check.relative_to(ROOT).as_posix()+(' '+' '.join(args) if args else '')
    from build_v4 import SIMPLE_ARCHIVE
    package_sha=hashlib.sha256(SIMPLE_ARCHIVE.read_bytes()).hexdigest() if check.name in PACKAGED and SIMPLE_ARCHIVE.exists() else None
    if name in prior and prior[name]['exit_code']==0 and name not in recheck and (check.name not in PACKAGED or prior[name].get('package_sha256')==package_sha):return prior[name]
    started=time.monotonic()
    interpreter=sys.executable if check.suffix=='.py' else (shutil.which('sh') or 'C:/Program Files/Git/bin/sh.exe')
    with (OUT/('idle-'+check.stem+'.log')).open('wb') as log:
        p=subprocess.run([interpreter,str(check),*args],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    row={'check':name,'exit_code':p.returncode,'seconds':round(time.monotonic()-started,2)}
    if package_sha:row['package_sha256']=package_sha
    print(name,'PASS' if p.returncode==0 else 'FAIL',flush=True)
    return row
phases=[(PRE,3),([ROOT/'scripts/build_v4.py'],1),
        ([(ROOT/'tests/validate_v4.py',['--idle-upgrade']),*POST],3),
        ([(ROOT/'tests/validate_startup_performance.py',['--current-only'])],1)]
for checks,workers in phases:
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool: rows.extend(pool.map(run,checks))
    REPORT.write_text(json.dumps({'result':'IN_PROGRESS','checks':rows,'source_hashes':HASHES},indent=2),encoding='utf-8')
    if any(r['exit_code'] for r in rows): break
assert HASHES=={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in HASHES},'Production source changed during validation'
passed=all(r['exit_code']==0 for r in rows) and len(rows)==sum(len(phase[0]) for phase in phases)
REPORT.write_text(json.dumps({'result':'PASS' if passed else 'FAIL','checks':rows,'source_hashes':HASHES},indent=2),encoding='utf-8')
print('Standard idle release:', 'PASS' if passed else 'FAIL',len(rows),'checks',flush=True)
if not passed:raise SystemExit(1)
