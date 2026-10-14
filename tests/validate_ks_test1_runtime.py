"""Run existing runtime contracts for KS, keeping Standard reports separate."""
from pathlib import Path
import json, sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/ks-test1-audit'
OUT.mkdir(exist_ok=True)
mode = sys.argv[1]
if mode == 'runtime':
    import validate_runtime_probe as probe
    probe.OUT = OUT
    probe.check('ks')
elif mode == 'framebuffer':
    path = ROOT / 'tests/validate_fbink_actual_use.py'
    source = path.read_text(encoding='utf-8')
    # Retain every original assertion; broaden the KS real-UI version matrix.
    source = source.replace('versions = FIRMWARES if variant == "standard" else ("5.18", "5.18.1.1.1", "5.18.10", "5.19.6")', 'versions = FIRMWARES')
    namespace = {'__file__':str(path), '__name__':'ks_framebuffer_contract'}
    exec(compile(source,str(path),'exec'),namespace)
    namespace['OUT'] = OUT
    namespace['check']('ks')
    (OUT/'framebuffer.json').write_text(json.dumps({'result':'PASS','checks':namespace['RESULTS']},indent=2),encoding='utf-8')
elif mode == 'service':
    path = ROOT / 'tests/validate_service_recovery.py'
    source = path.read_text(encoding='utf-8').replace("OUT = ROOT/'build/validation'", "OUT = ROOT/'build/ks-test1-audit'")
    source = source.replace("for variant in ('standard',):", "for variant in ('ks',):")
    exec(compile(source,str(path),'exec'),{'__file__':str(path),'__name__':'ks_service_contract'})
else:
    raise SystemExit('unknown contract')
