"""Stateful, relocated Upstart/mount/process fixture; never touch host services."""
from pathlib import Path
import os
import subprocess


def msys(path: Path) -> str:
    return f"/{path.drive[0].lower()}{path.as_posix()[2:]}" if path.drive else path.as_posix()


def service_fixture(folder: Path, base: Path, upstart: Path, shell: str, *, running=True):
    folder.mkdir(parents=True, exist_ok=True)
    upstart.mkdir(parents=True, exist_ok=True)
    proc = folder / 'proc'; (proc / '123').mkdir(parents=True, exist_ok=True)
    (proc / '123/cmdline').write_bytes((b'/bin/sh\0' + (base / 'bin/native-reading-time-daemon.sh').as_posix().encode() + b'\0') if running else b'')
    (proc / '123/stat').write_text('123 (native-reading-time) S ' + '1 '*18 + '12345\n')
    state = folder / 'running'
    if running: state.write_text('1')
    mounts = folder / 'mounts'; mounts.write_text('/dev/root / ext3 ro,relatime 0 0\n')
    calls = folder / 'calls'
    initctl = folder / 'initctl'
    initctl.write_text(f'''#!/bin/sh
printf '%s\\n' "$*" >> "{calls.as_posix()}"
case "$1" in
 status)
  [ ! -f "{folder.as_posix()}/query-hang" ] || exec /bin/sleep 30
  [ ! -f "{folder.as_posix()}/query-fail" ] || exit 1
  if [ -f "{state.as_posix()}" ]; then echo 'native-reading-time start/running, process 123'; else echo 'native-reading-time stop/waiting'; fi;;
 start)
  [ ! -f "{folder.as_posix()}/start-fail" ] || exit 7
  [ -f "{upstart.as_posix()}/native-reading-time.conf" ] || exit 8
  printf '/bin/sh\\0%s\\0' "{(base/'bin/native-reading-time-daemon.sh').as_posix()}" > "{(proc/'123/cmdline').as_posix()}"
  printf 1 > "{state.as_posix()}"
  [ -f "{base.as_posix()}/reading-time.tsv" ] || printf 'date\\tbook_id\\tseconds\\ttitle\\n' > "{base.as_posix()}/reading-time.tsv";;
 stop) rm -f "{state.as_posix()}"; : > "{(proc/'123/cmdline').as_posix()}";;
 reload-configuration) [ ! -f "{folder.as_posix()}/reload-fail" ] || exit 6;;
esac
''', encoding='utf-8', newline='\n')
    mntroot = folder / 'mntroot'
    mntroot.write_text(f'''#!/bin/sh
echo "mntroot $*" >> "{calls.as_posix()}"
[ ! -f "{folder.as_posix()}/mntroot-fail" ] || exit 4
[ ! -f "{folder.as_posix()}/mount-lie" ] || exit 0
[ ! -f "{folder.as_posix()}/restore-fail" ] || [ "$1" != ro ] || exit 5
printf '/dev/root / ext3 %s,relatime 0 0\\n' "$1" > "{mounts.as_posix()}"
''', encoding='utf-8', newline='\n')
    mount = folder / 'mount'
    mount.write_text(f'''#!/bin/sh
echo "mount $*" >> "{calls.as_posix()}"
[ ! -f "{folder.as_posix()}/mount-fail" ] || exit 5
mode=${{2#remount,}}
[ ! -f "{folder.as_posix()}/restore-fail" ] || [ "$mode" != ro ] || exit 5
printf '/dev/root / ext3 %s,relatime 0 0\\n' "$mode" > "{mounts.as_posix()}"
''', encoding='utf-8', newline='\n')
    subprocess.run([shell, '-c', '/usr/bin/chmod 755 "$@"', 'fixture', *(p.as_posix() for p in (initctl,mntroot,mount))], check=True)
    return {'READING_INITCTL': initctl.as_posix(), 'READING_MNTROOT_COMMAND': mntroot.as_posix(),
            'READING_MOUNT_COMMAND': mount.as_posix(), 'READING_MOUNTS_PATH': mounts.as_posix(),
            'READING_PROC_ROOT': proc.as_posix(), 'READING_LIFECYCLE_LOCK': (folder/'lock').as_posix(),
            'READING_UPSTART_DIR': upstart.as_posix()}
