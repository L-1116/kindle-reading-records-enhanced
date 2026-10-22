"""Run the actual FIFO parent-death guard without any screen or input device."""
from pathlib import Path
import os, shutil, subprocess, tempfile, time

ROOT=Path(__file__).resolve().parents[1]; PKG=ROOT/'native-reading-time-package'
SH=shutil.which('sh') or 'C:/Program Files/Git/usr/bin/sh.exe'
with tempfile.TemporaryDirectory(prefix='idle-guard-') as tmp:
    root=Path(tmp); mock=root/'bin'; mock.mkdir(); sysfs=root/'sys'; sysfs.mkdir()
    # This test executes blocked host processes, so select the legacy shell
    # guard explicitly. The ARM multiplexer has its C lifecycle fixture.
    helpers=root/'helpers'; helpers.mkdir()
    for name in ('reading-idle.sh','reading-idle-touch.lua','reading-insights-touch-probe.lua'):
        shutil.copy2(PKG/name,helpers/name)
    blocked=root/'blocked-reader'
    subprocess.run([SH,'-c','/usr/bin/mkfifo "$1"','test',blocked.as_posix()],check=True)
    fake=mock/'lua'
    # Keep one blocked reader PID/start time. MSYS changes /proc start time on
    # exec (unlike Linux), so exec sleep can invalidate the guard's identity
    # snapshot and create a host-only orphan. A builtin FIFO read models the
    # same blocked input lifetime without that extra exec or a grandchild.
    fake.write_text('#!/bin/sh\ncase "$1" in *probe.lua) printf "/dev/fixture\\n16\\n";; *) exec 7<>"'+blocked.as_posix()+'"; IFS= read -r fixture_control <&7;; esac\n',encoding='utf-8',newline='\n')
    subprocess.run([SH,'-c','/usr/bin/chmod 755 "$1"','test',fake.as_posix()],check=True)
    env={**os.environ,'PATH':mock.as_posix()+':/usr/bin:/bin','READING_INPUT_SYSFS':sysfs.as_posix()}
    for signal in ('TERM','KILL','GUARD_KILL'):
        ready=root/f'ready-{signal}'
        script=f'''
BASE="{root.as_posix()}"; IDLE_HELPERS="{helpers.as_posix()}"; LOG="$BASE/log"
. "$IDLE_HELPERS/reading-idle.sh"
trap 'idle_stop; exit 0' TERM
now=$(date +%s); today=$(date +%Y-%m-%d); idle_minutes=3; book_id=AAAA; book_title=Book
idle_start || exit 3
printf '%s %s %s\n' "$$" "$idle_pid" "$idle_dir" > "{ready.as_posix()}"
IFS= read -r control
'''
        error_log=root/f'error-{signal}'; error_stream=error_log.open('w',encoding='utf-8')
        process=subprocess.Popen([SH],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=error_stream,env=env,text=True,encoding='utf-8')
        process.stdin.write('set -x\n'+script); process.stdin.flush()
        try:
            deadline=time.monotonic()+8
            while not ready.exists() and time.monotonic()<deadline:
                assert process.poll() is None,(process.returncode,error_log.read_text(encoding='utf-8')); time.sleep(.05)
            assert ready.exists(),'guard did not start'
            parent,guard,folder=ready.read_text().strip().split(' ',2)
            command=subprocess.check_output([SH,'-c','/usr/bin/cat "/proc/$1/cmdline"','test',guard]).split(b'\0')
            assert any(arg.endswith(b'/reading-idle.sh') for arg in command),command
            assert not any(arg.endswith(b'/native-reading-time-daemon.sh') for arg in command),command
            deadline=time.monotonic()+8
            while time.monotonic()<deadline:
                state=subprocess.run([SH,'-c','/usr/bin/cat "$1/listener.pid" 2>/dev/null','test',folder],capture_output=True,text=True)
                if state.returncode==0 and state.stdout.strip(): child=state.stdout.strip().split()[0]; break
                time.sleep(.05)
            else:raise AssertionError('reader did not start')
            if signal=='GUARD_KILL':
                subprocess.run([SH,'-c','kill -KILL "$1"','test',guard],check=True)
            subprocess.run([SH,'-c',f'kill -{"TERM" if signal=="GUARD_KILL" else signal} "$1"','test',parent],check=True)
            deadline=time.monotonic()+8
            while time.monotonic()<deadline:
                alive=subprocess.run([SH,'-c','kill -0 "$1" 2>/dev/null','test',child],capture_output=True)
                cleaned=subprocess.run([SH,'-c','test ! -d "$1"','test',folder]).returncode==0
                if alive.returncode!=0 and cleaned:break
                time.sleep(.05)
            else:raise AssertionError(('orphan listener',signal,child))
            process.wait(timeout=8)
            assert subprocess.run([SH,'-c','test ! -d "$1"','test',folder]).returncode==0,('temporary state leaked',signal,folder)
        finally:
            if process.poll() is None: process.kill()
            process.communicate(timeout=8)
            error_stream.close()
print('idle guard: PASS (TERM, daemon SIGKILL and guard SIGKILL; actual blocked processes)')
