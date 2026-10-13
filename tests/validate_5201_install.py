"""Packaged Standard/KS service-loss, original-rw and closed-output acceptance."""
from pathlib import Path
import json
import tempfile
import sys
import subprocess
import os
from service_fixture import service_fixture
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate_v4 import run, OUT, SHELL

results=[]
for variant,previous in (('standard','V4'),):
    for mutation in ('lost_service','stopped_service','initial_rw','closed_output'):
        with tempfile.TemporaryDirectory(prefix='5201-install-',dir=OUT) as name:
            result=run(Path(name),variant,previous,mutation=mutation)
            results.append({'variant':variant,'scenario':mutation,'result':'PASS'})
            print(variant,mutation,'PASS',flush=True)
    with tempfile.TemporaryDirectory(prefix='5201-cleanup-',dir=OUT) as name:
        folder=Path(name)
        run(folder,variant,previous,cleanup=True)
        base=folder/'us/reading-time'; upstart=folder/'upstart'
        history=(base/'reading-time.tsv').read_bytes()
        (upstart/'native-reading-time.conf').unlink()
        env={**os.environ,'PATH':'/usr/bin:/bin','READING_BASE':base.as_posix(),'READING_TMPDIR':(folder/'tmp').as_posix()}
        env.update(service_fixture(folder/'service-fixture',base,upstart,SHELL,running=False))
        child=subprocess.run([SHELL,(base/'bin/service-manager.sh').as_posix(),'ensure'],env=env,capture_output=True,timeout=18)
        assert child.returncode==0,(child.stdout,child.stderr)
        assert (upstart/'native-reading-time.conf').is_file()
        assert (base/'reading-time.tsv').read_bytes()==history
        results.append({'variant':variant,'scenario':'service recovery after installation cleanup','result':'PASS'})
        print(variant,'cleanup then service recovery PASS',flush=True)
(OUT/'firmware-5201-install-results.json').write_text(json.dumps({'result':'PASS','checks':results,'kindle_hardware':'PENDING'},indent=2),encoding='utf-8')
