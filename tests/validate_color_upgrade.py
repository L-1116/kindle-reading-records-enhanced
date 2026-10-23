"""Real test10 ZIP -> test11 transaction, repeated install, cleanup and rollback."""
from pathlib import Path
import json, os, tempfile

# Slow Windows/MSYS process creation needs a host-only budget. Device runtime
# watchdogs and failure behavior remain unchanged.
if os.name == 'nt': os.environ.setdefault('READING_TEST_INSTALL_TIMEOUT', '300')
from validate_v4 import run, ROOT
from historical_packages import CATALOG

CATALOG.append({'id': '9.8.1-test10',
                'path': 'build/idle-startup-candidate/9.8.1-5.20-vera-test10.zip',
                'sha256': 'a195a3f6320d1ca3f523d6b5d2354d923faccf8f67d6575ba9fa809fed19ff52',
                'official': True})
OUT = ROOT/'build/validation/color-test11'
OUT.mkdir(exist_ok=True)
cases = [(None, '', True), ('9.8.1-test10', '', True), ('9.8.1-test10-cleaned', '', True)]
cases += [('9.8.1-test10', fault, False) for fault in
          ('core_failure', 'activation_failure', 'interrupted', 'ks_residue', 'wrong_device', 'busy_ui')]
rows = []
for previous, fault, cleanup in cases:
    with tempfile.TemporaryDirectory(prefix='color-upgrade-', dir=OUT) as tmp:
        rows.append(run(Path(tmp), previous=previous, mutation=fault, cleanup=cleanup))
    print(previous or 'fresh', fault or 'install/repeat/cleanup', 'PASS', flush=True)
    (OUT/'upgrade-results.json').write_text(json.dumps({'result': 'RUNNING', 'checks': rows}, indent=2), encoding='utf-8')
(OUT/'upgrade-results.json').write_text(json.dumps({'result': 'PASS', 'checks': rows, 'hardware_verified': False}, indent=2), encoding='utf-8')
