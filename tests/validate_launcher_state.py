"""Current launcher preserves saved power and excludes a live old-style UI lock."""
from pathlib import Path
import os,subprocess,tempfile,json
from validate_runtime_probe import ROOT,OUT,SH,setup,run,shell_path
checks=[]
with tempfile.TemporaryDirectory(prefix='launcher-state-',dir=OUT) as directory:
    root=Path(directory);launcher,env,_,_=setup(root,'standard')
    code,log=run(launcher,env,READING_TEST_ORIGINAL_POWER='1')
    assert code==0,log
    assert 'com.lab126.powerd preventScreenSaver 1' in (root/'lipc.txt').read_text(encoding='utf-8')
    checks.append({'scenario':'saved power=1 restored','result':'PASS'})
    (root/'lipc.txt').write_text('')
    code,log=run(launcher,env,READING_TEST_ORIGINAL_POWER='invalid')
    assert code==33 and 'ui_process_entered=1' not in log,log
    assert 'preventScreenSaver' not in (root/'lipc.txt').read_text(encoding='utf-8')
    checks.append({'scenario':'invalid power snapshot fails before UI','result':'PASS'})
    lock=root/'reading-records-ui.lock'
    holder_script=root/'holder.sh'
    holder_script.write_text(f'''LOCK="{shell_path(lock)}"
. "{shell_path(ROOT/'native-reading-time-package/compat/runtime-lock.sh')}"
trap release_runtime_lock EXIT
acquire_runtime_lock || exit 1
echo ready
/bin/sleep 3
''',encoding='utf-8',newline='\n')
    holder=subprocess.Popen([SH,holder_script.as_posix()],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={**os.environ,'PATH':'/usr/bin:/bin'})
    assert holder.stdout.readline().strip()==b'ready'
    before=(lock/'pid').read_bytes()
    result=subprocess.run([SH,launcher.as_posix()],env=env,capture_output=True,timeout=5)
    assert result.returncode==75 and (lock/'pid').read_bytes()==before,(result.returncode,result.stderr)
    assert holder.wait(timeout=6)==0 and not lock.exists()
    checks.append({'scenario':'live shared UI lock rejects second launcher without reaping owner','result':'PASS'})
    # The normal bound never needs fractional sleep or a successful fractional probe.
    source=launcher.read_text(encoding='utf-8').replace('if sleep 0.01 2>/dev/null;', 'if false;')
    launcher.write_text(source,encoding='utf-8',newline='\n')
    code,log=run(launcher,env)
    assert code==0 and 'lua_primary_result=ok' in log,log
    checks.append({'scenario':'integer-only sleep retains fast foreground completion and watchdog','result':'PASS'})
(OUT/'launcher-state-results.json').write_text(json.dumps({'result':'PASS','checks':checks},indent=2),encoding='utf-8')
print('Launcher state/concurrency:',len(checks),'PASS')
