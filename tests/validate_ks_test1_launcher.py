"""KS launcher ownership, power preservation and consolidated Lua checks."""
from pathlib import Path
import json, subprocess, tempfile
from validate_runtime_probe import setup, SH

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/ks-test1-audit'
results=[]
for case in ['normal nonzero power', 'failed Lua keeps power', 'busy UI rejects second launcher']:
    with tempfile.TemporaryDirectory(dir=OUT) as directory:
        folder=Path(directory);launcher,env,_,children=setup(folder,'ks')
        env['READING_TEST_ORIGINAL_POWER']='7'
        base=launcher.parent.parent
        if case=='failed Lua keeps power':
            env.update(PRIMARY_LUA_MODE='nonzero',FALLBACK_LUA_MODE='nonzero')
        if case=='busy UI rejects second launcher':
            owner=folder/'reading-records-ui.lock/owner.1'
            owner.mkdir(parents=True);(owner/'sentinel').write_bytes(b'other UI')
            (owner.parent/'pid').write_bytes(b'1')
        result=subprocess.run([SH,launcher.as_posix()],env=env,capture_output=True,timeout=25)
        if case=='normal nonzero power':
            assert result.returncode==0,result.stderr
            assert 'com.lab126.powerd preventScreenSaver 7' in (folder/'lipc.txt').read_text(encoding='utf-8')
            assert not (folder/'reading-records-ui.lock').exists()
            assert 'lua_probe_source_begin=' in (base/'launch-last.log').read_text(encoding='utf-8')
        elif case=='failed Lua keeps power':
            assert result.returncode==32,result.stderr
            assert 'com.lab126.powerd preventScreenSaver' not in (folder/'lipc.txt').read_text(encoding='utf-8')
            assert not (folder/'reading-records-ui.lock').exists()
        else:
            assert result.returncode==75,(result.returncode,result.stderr)
            assert (owner/'sentinel').read_bytes()==b'other UI'
            assert not children.exists(), 'No Lua or framebuffer operation while another UI is active'
        results.append({'case':case,'result':'PASS'})
(OUT/'launcher.json').write_text(json.dumps({'result':'PASS','checks':results},indent=2),encoding='utf-8')
print('KS launch mutex, power snapshot and single Lua preflight: PASS')
