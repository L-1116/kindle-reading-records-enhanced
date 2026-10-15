"""Execute real historical installers, relocating only execution/system paths.

Payload programs, library entries, service configs and assets are never edited.
The old scripts' root/loader/Upstart operations use isolated host fixtures.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from historical_packages import CATALOG, package
from service_fixture import msys


def install_history(session, env, ident, *, cleaned=False):
    row = next(r for r in CATALOG if r['id'] == ident)
    outer, files = package(row)
    us=Path(env['READING_MNT_US']); docs=Path(env['READING_DOCUMENTS'])
    base=Path(env['READING_BASE']); upstart=Path(env['READING_UPSTART_DIR'])
    shell=shutil.which('sh') or 'C:/Program Files/Git/usr/bin/sh.exe'
    execution=session/'historical-execution'; execution.mkdir(exist_ok=True)
    for name,raw in (outer if any(n.endswith('.tar') for n in outer) else files).items():
        dst=(docs if '/' not in name and name.endswith(('.sh','.tar')) and any(n.endswith('.tar') for n in outer) else us)/name
        dst.parent.mkdir(parents=True,exist_ok=True); dst.write_bytes(raw)
    # Execution copies only: nested installers are redirected to this folder.
    prefix='native-reading-time-package/'
    names=[n for n in files if n.startswith(prefix) and n.endswith('.sh') and
           (n[len(prefix):] in ('install.sh','Install-Native-Reading-Time.sh','Install-Native-Reading-Time-Optimized.sh','compat/detect_env.sh','compat/lifecycle.sh','service-manager.sh'))]
    if any(n.endswith('.tar') for n in outer):
        boot=next(n for n in outer if n.endswith('.sh'))
        # V4 installers already expose all filesystem/system seams; run exact
        # public bootstrap and exact embedded payload, without relocation edits.
        if b'READING_MNT_US' in outer[boot]:
            child=subprocess.run([shell,(docs/boot).as_posix()],env=env,capture_output=True,timeout=180)
            assert child.returncode==0,(ident,child.stderr, (docs/'reading-records-v4-install.log').read_text(errors='replace'))
            installed_entry=files[prefix+'阅读记录-entry.sh']
            assert (docs/'reading-records.sh').read_bytes()==installed_entry
            if cleaned:
                cleanup=next(p for p in docs.glob('*.sh') if p.name!=boot and b'READING_RECORDS_V4_CLEANUP' in p.read_bytes())
                child=subprocess.run([shell,cleanup.as_posix()],env=env,capture_output=True,timeout=120)
                assert child.returncode==0,(ident,child.stderr)
            return row
        # Manifest-based 5.18/5.19 bootstraps install only the native payload.
        for name,raw in files.items():
            if name.startswith(prefix):
                dst=us/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(raw)
    loader=session/'loader';loader.write_bytes(b'fixture loader')
    for name in names:
        raw=files[name].decode('utf-8')
        for old,new in [('/sbin/initctl',env['READING_INITCTL']),('/usr/sbin/mntroot',env['READING_MNTROOT_COMMAND']),('/sbin/mntroot',env['READING_MNTROOT_COMMAND']),('/etc/upstart',upstart.as_posix()),('/lib/ld-linux-armhf.so.3',loader.as_posix()),('/etc/prettyversion.txt',(session/'historical-firmware').as_posix()),('/etc/version.txt',(session/'historical-firmware').as_posix()),('/mnt/us',msys(us)),('/tmp/',msys(Path(env['READING_TMPDIR']))+'/')]:
            raw=raw.replace(old,new)
        raw=raw.replace('$(id -u)','0')
        # All copies still source immutable assets from the original package.
        for target in names:
            rel=target[len(prefix):]
            raw=raw.replace('"$PKG/'+rel+'"', '"'+(execution/rel).as_posix()+'"') if rel in ('Install-Native-Reading-Time.sh','Install-Native-Reading-Time-Optimized.sh','compat/detect_env.sh','compat/lifecycle.sh','service-manager.sh') else raw
        if 'Install-Native-' not in name:
            # Manifest installer resolves PKG from its own location. Keep that
            # pointing at immutable delivered resources, not execution copies.
            raw=raw.replace('PKG="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"',
                            'PKG="'+(us/'native-reading-time-package').as_posix()+'"')
        # System process existence checks refer to the mocked Upstart process.
        raw=raw.replace('/proc/$DAEMON_PID/',env['READING_PROC_ROOT']+'/$DAEMON_PID/')
        raw=raw.replace('kill -0 "$DAEMON_PID"', 'test -s "'+env['READING_PROC_ROOT']+'/$DAEMON_PID/cmdline"')
        dst=execution/name[len(prefix):];dst.parent.mkdir(parents=True,exist_ok=True);dst.write_text(raw,encoding='utf-8',newline='\n')
    subprocess.run([shell,'-c','/usr/bin/chmod 755 "$@"','fixture',*[p.as_posix() for p in execution.rglob('*.sh')]],check=True)
    # Historical manifest installers check their own firmware before deployment.
    # This is the original installation environment; upgrade later runs 5.20.1.
    (session/'historical-firmware').write_text('Kindle 5.18.1.1.1' if '5.18' in ident else 'Kindle 5.19.6')
    if '5.18' in ident or '5.19' in ident:
        fbset=session/'mockbin/fbset';fbset.write_text('#!/bin/sh\necho geometry 1264 1680 1264 1680 8\n',encoding='utf8',newline='\n')
        subprocess.run([shell,'-c','/usr/bin/chmod 755 "$1"','fixture',fbset.as_posix()],check=True)
    local_env={**env,'READING_PACKAGE_DIR':(us/'native-reading-time-package').as_posix()}
    # Older rootfs commands use PATH, while newer scripts expose overrides.
    mntroot=Path(env['READING_MNTROOT_COMMAND'])
    local_env['PATH']=msys(mntroot.parent)+':'+msys(session/'mockbin')+':/usr/bin:/bin'
    for name in ('Install-Native-Reading-Time.sh','Install-Native-Reading-Time-Optimized.sh') if prefix+'Install-Native-Reading-Time-Optimized.sh' in files else ('install.sh',):
        child=subprocess.run([shell,(execution/name).as_posix()],env=local_env,capture_output=True,timeout=180)
        assert child.returncode==0,(ident,name,child.stdout,child.stderr,(base/'install.log').read_text(errors='replace')[-4000:] if (base/'install.log').exists() else '')
    # Verify the actual deployed entry against original release bytes.
    entry=docs/('reading-records.sh' if (docs/'reading-records.sh').exists() else '阅读记录.sh')
    assert entry.read_bytes() in [raw for name,raw in files.items() if name.endswith('.sh')], (ident,entry)
    assert (base/'bin/native-reading-time-daemon.sh').read_bytes()==files[prefix+'native-reading-time-daemon.sh']
    if cleaned:
        # Pre-V3 removers could uninstall the runtime; never execute them as
        # "installation cleanup". Removing extracted delivery files models a
        # user who kept the installed runtime and discarded install media.
        shutil.rmtree(us/'native-reading-time-package')
        for name in outer:
            path=(docs if '/' not in name and name.endswith(('.sh','.tar')) and any(n.endswith('.tar') for n in outer) else us)/name
            if path.is_file():path.unlink()
        for path in docs.glob('*.sh'):
            if path!=entry and b'/native-reading-time-package/' in path.read_bytes():path.unlink()
    return row
