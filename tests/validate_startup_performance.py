"""Measure whole real shell/Lua startup chains; FBInk and input are host mocks."""
from pathlib import Path
import json
import os
import shutil
import statistics
import subprocess
import tempfile
import time
from runtime_fixture import install_python_fixture
from validate_runtime_probe import setup, executable, SH, ROOT, OUT, shell_path
from service_fixture import service_fixture

RESULTS=[]
baseline=ROOT/'build/standard-next-baseline'
for chain in ('normal-5.19', 'baseline-5.20.1', 'current'):
    with tempfile.TemporaryDirectory(prefix='reading-startup-perf-') as directory:
        root=Path(directory); launcher,env,pretty,_=setup(root,'standard')
        base=launcher.parent.parent
        release=base/'releases/9.7.6-5.20.1-vera'
        main=release/'bin/reading-records.sh'
        pkg=ROOT/'native-reading-time-package'
        for folder in ('ui','ui-calendar','render-assets'):
            shutil.copytree(pkg/folder,release/folder,dirs_exist_ok=True)
        for p in pkg.glob('*.lua'):shutil.copy2(p,release/'bin'/p.name)
        for p in pkg.glob('*.awk'):shutil.copy2(p,release/'bin'/p.name)
        shutil.copy2(pkg/'reading-insights-touch-preflight.sh',release/'bin/reading-insights-touch-preflight.sh')
        shutil.copy2(pkg/'NotoSansCJKsc-Regular.otf',base/'fonts/NotoSansCJKsc-Regular.otf')
        shutil.copy2(pkg/'compat/performance.sh',base/'compat/performance.sh')
        shutil.copy2(pkg/'compat/lifecycle.sh',base/'compat/lifecycle.sh')
        shutil.copy2(pkg/'service-manager.sh',base/'bin/service-manager.sh')
        (base/'service').mkdir()
        shutil.copy2(pkg/'native-reading-time.conf',base/'service/native-reading-time.conf')
        upstart=root/'upstart';upstart.mkdir()
        shutil.copy2(pkg/'native-reading-time.conf',upstart/'native-reading-time.conf')
        executable(base/'bin/native-reading-time-daemon.sh','exit 99\n')
        env.update(service_fixture(root/'service-fixture',base,upstart,SH))
        (base/'reading-time.tsv').write_text('date\tbook_id\tseconds\ttitle\n2026-10-12\tAAAA\t7200\tExample\n2026-10-13\tAAAA\t600\tExample\n',encoding='utf-8')
        touch=root/'input';touch.write_bytes(b'')
        env.update(READING_TOUCH_DEVICE=touch.as_posix(),READING_PERF='1',READING_PERF_LOG=(root/'stages').as_posix(),READING_TEST_LIPC=(root/'lipc').as_posix())
        executable(root/'mockbin/lipc-get-prop','case "$2" in preventScreenSaver) echo 0;; orientationLock) echo U;; *) echo active;; esac\n')
        executable(root/'mockbin/fbink','printf "%s\\n" "$*" >> "$READING_TEST_FB_CALLS"\n[ "$1" != -e ] || exit 139\n')
        # No missing fallback resources; a fallback would be a failed comparison.
        executable(release/'bin/reading-records-v9.6.3.sh','exit 99\n')
        install_python_fixture(ROOT/'tests/fixtures/standard-lua.py',root/'mockbin/lua')
        if chain=='current':
            ui=(pkg/'阅读记录-optimized.sh').read_text(encoding='utf-8')
        elif chain=='baseline-5.20.1':
            shutil.copy2(baseline/'native-reading-time-package/service-manager.sh',base/'bin/service-manager.sh')
            shutil.copy2(baseline/'native-reading-time-package/compat/lifecycle.sh',base/'compat/lifecycle.sh')
            ui=(baseline/'native-reading-time-package/阅读记录-optimized.sh').read_text(encoding='utf-8')
            source=(baseline/'native-reading-time-package/launch.sh').read_text(encoding='utf-8')
            source=source.replace('RELEASE="$BASE/releases/9.7.5-test"',f'RELEASE="{shell_path(release)}"')
            source=source.replace('fbink_candidate_add /var/local/kmc/bin/fbink',f'fbink_candidate_add {shell_path(root/"mockbin/fbink")}')
            source=source.replace('BASE="${READING_BASE:-/mnt/us/reading-time}"','BASE="${READING_BASE:-/mnt/us/reading-time}"\n. "$BASE/compat/performance.sh"\nrr_perf entry')
            for stage in ('environment','preflight','runtime_probe','ui'):
                source=source.replace('STAGE='+stage+'\n','STAGE='+stage+'\nrr_perf '+stage+'\n',1)
            launcher.write_text(source,encoding='utf-8',newline='\n')
        else:
            names=subprocess.check_output(['git','ls-tree','-r','--name-only','v9.7.6-5.19-vera','native-reading-time-package'],cwd=ROOT).decode().splitlines()
            for name in names:
                rel=name.removeprefix('native-reading-time-package/')
                if rel.startswith(('ui/','ui-calendar/','render-assets/')):dst=release/rel
                elif rel.endswith(('.lua','.awk')):dst=release/'bin'/rel
                else:continue
                dst.parent.mkdir(parents=True,exist_ok=True)
                dst.write_bytes(subprocess.check_output(['git','show','v9.7.6-5.19-vera:'+name],cwd=ROOT))
            ui=(baseline/'old-normal-ui.sh').read_text(encoding='utf-8')
            source=subprocess.check_output(['git','show','v9.7.6-5.19-vera:native-reading-time-package/launch.sh'],cwd=ROOT).decode()
            source=source.replace('BASE="/mnt/us/reading-time"','BASE="${READING_BASE:-/mnt/us/reading-time}"\n. "$BASE/compat/performance.sh"\nrr_perf entry')
            source=source.replace('RELEASE="$BASE/releases/9.7.6-5.19-normal"',f'RELEASE="{shell_path(release)}"').replace('MAIN="$RELEASE/bin/reading-records-ui.sh"','MAIN="$RELEASE/bin/reading-records.sh"')
            source=source.replace('LOCK="/tmp/reading-records-ui.lock"',f'LOCK="{shell_path(root)}/normal.lock"').replace('INSTALL_LOCK="/tmp/reading-records-9.7.6-install.lock"',f'INSTALL_LOCK="{shell_path(root)}/normal-install.lock"')
            launcher.write_text(source,encoding='utf-8',newline='\n')
            (release/'bin/runtime-child.sh').write_bytes(subprocess.check_output(['git','show','v9.7.6-5.19-vera:native-reading-time-package/runtime-child.sh'],cwd=ROOT))
            ui=ui.replace('FBINK="/var/local/kmc/bin/fbink"','FBINK="$READING_FBINK"')
            ui=ui.replace('BASE="/mnt/us/reading-time"','BASE="${READING_BASE:-/mnt/us/reading-time}"')
        if chain!='current':
            ui=ui.replace('RELEASE="$BASE/releases/9.7.5-test"',f'RELEASE="{shell_path(release)}"').replace('RELEASE="$BASE/releases/9.7.6-5.19-normal"',f'RELEASE="{shell_path(release)}"')
            ui=ui.replace('DATA="$BASE/reading-time.tsv"','DATA="$BASE/reading-time.tsv"\n. "$BASE/compat/performance.sh"\nrr_perf ui_begin',1)
            ui=ui.replace('build_cache ||','rr_perf data_begin; build_cache ||',1)
            ui=ui.replace('selected_date="$today_date"; draw_background','rr_perf data_end; selected_date="$today_date"; rr_perf background_begin; draw_background',1)
            ui=ui.replace('draw_dynamic 1 ||','rr_perf background_end; rr_perf dynamic_begin; draw_dynamic 1 ||',1)
            ui=ui.replace('refresh_region 0 0 1272 1696','rr_perf dynamic_end; rr_perf refresh_begin; refresh_region 0 0 1272 1696; rr_perf refresh_end',1)
        ui=ui.replace('/tmp/native-reading-dashboard.',shell_path(root)+'/native-reading-dashboard.')
        main.write_text(ui,encoding='utf-8',newline='\n')
        subprocess.run([SH,'-c','/usr/bin/chmod 755 "$@"','fixture',launcher.as_posix(),main.as_posix()],check=True)
        pretty.write_text('Kindle 5.20.1\n',encoding='utf-8')
        for sample in range(4):
            (root/'stages').write_text('');(root/'fb-calls.txt').write_text('')
            begin=time.monotonic()
            result=subprocess.run([SH,launcher.as_posix()],env=env,capture_output=True,timeout=45)
            end=time.monotonic()
            text=(root/'stages').read_text(encoding='utf-8')
            log=(base/('launch-last.log' if chain!='normal-5.19' else 'dashboard-launch.log')).read_text(encoding='utf-8',errors='replace')
            assert result.returncode==0,(chain,result.returncode,result.stderr,log[-5000:])
            assert 'stage=software_interactive_ready' in text and 'stage=refresh_end' in text,(chain,text)
            assert text.index('stage=refresh_end')<text.index('stage=software_interactive_ready'),text
            calls=(root/'fb-calls.txt').read_text().splitlines()
            assert calls and not any(line=='-e' for line in calls)
            ready=float(next(line.split('uptime=')[1].split()[0] for line in text.splitlines() if 'stage=software_interactive_ready' in line))
            RESULTS.append({'chain':chain,'sample':'cold-process' if sample==0 else 'warm-repeat','entry_to_mock_interactive_seconds':round(ready-begin,3),'whole_process_seconds':round(end-begin,3),'fbink_calls':len(calls),'stages':text.splitlines(),'hardware':'MOCK; host filesystem cache not flushed'})
        # Healthy service path never mounts or reloads during these launches.
        service_calls=(root/'service-fixture/calls').read_text() if (root/'service-fixture/calls').exists() else ''
        assert 'mntroot' not in service_calls and 'start native' not in service_calls and 'reload-configuration' not in service_calls
summary={chain:round(statistics.median(x['entry_to_mock_interactive_seconds'] for x in RESULTS if x['chain']==chain),3) for chain in ('normal-5.19','baseline-5.20.1','current')}
report={'result':'PASS','samples':RESULTS,'median_seconds':summary,'limitation':'Windows/MSYS real shell+Lua with mocked FBInk/input; excludes Scriptlet pre-exec click overhead and cannot certify Kindle 3–4s.'}
(OUT/'startup-performance-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='samples'},ensure_ascii=False,indent=2))
