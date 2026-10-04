"""Background-only Kindle filesystem/command simulator for production scripts."""
from __future__ import annotations
import atexit
import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.package_release import ARCHIVE, cksum as python_cksum, BOOTSTRAP, PAYLOAD
CKSUM = shutil.which("cksum") or "C:/Program Files/Git/usr/bin/cksum.exe"
def cksum(data):
    return tuple(map(int, subprocess.run([CKSUM], input=data, capture_output=True, check=True).stdout.split()))
ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "native-reading-time-package"
OUT = ROOT / "build/validation"
OUT.mkdir(parents=True, exist_ok=True)
ASCII_ROOT = Path(tempfile.gettempdir()) / "reading-records-normal-tests"
ASCII_ROOT.mkdir(exist_ok=True)
SH = shutil.which("sh") or "C:/Program Files/Git/usr/bin/sh.exe"
DASH = shutil.which("dash") or "C:/Program Files/Git/usr/bin/dash.exe"

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path, text):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")

class Device:
    def __init__(self, shell=SH):
        self.shell = shell
        self.root = Path(tempfile.mkdtemp(prefix="normal-", dir=ASCII_ROOT))
        assert self.root.resolve().is_relative_to(ASCII_ROOT.resolve())
        atexit.register(shutil.rmtree, self.root, ignore_errors=True)
        self.us = self.root / "us"; self.base = self.us / "reading-time"
        self.docs = self.us / "documents"; self.tmp = self.root / "tmp"
        self.etc = self.root / "etc"; self.sys = self.root / "sys"
        self.mock = self.root / "mockbin"
        for d in (self.base, self.docs, self.tmp, self.etc / "upstart", self.mock): d.mkdir(parents=True)
        self.env = os.environ.copy(); self.env.update(SIM=("/"+self.root.drive[0].lower()+self.root.as_posix()[2:] if os.name=="nt" else self.root.as_posix()), PYTHON_BIN=sys.executable.replace("\\", "/"))
        self.env["PATH"] = str(self.mock) + os.pathsep + self.env["PATH"]
        self.flag("orientation", "U"); self.flag("eatTapMode", "0"); self.flag("preventScreenSaver", "0")
        self.flag("actions", "exit"); self.firmware("5.19.6")
        write(self.root / "var/local/deviceType.txt", "Paperwhite Signature Edition\n")
        write(self.sys / "class/input/event1/device/name", "cyttsp touch\n")
        write(self.root / "touch", "input device")
        self.commands()
        with zipfile.ZipFile(ARCHIVE) as z:
            self.original_tar = z.read(PAYLOAD); self.original_boot = z.read(BOOTSTRAP)
        self.prepare_payload()

    def flag(self, name, value="1"): write(self.root / name, str(value) + "\n")
    def unflag(self, name): (self.root / name).unlink(missing_ok=True)
    def firmware(self, version): write(self.etc / "prettyversion.txt", f"Kindle {version} (build 519999999)\n")
    def read(self, name): return (self.root / name).read_text(encoding="utf-8").strip()
    def command(self, name, body): write(self.mock / name, "#!/bin/sh\n" + body + "\n")
    def commands(self):
        write(self.root / "unzip.py", "import sys,zipfile\nwith zipfile.ZipFile(sys.argv[2]) as z: sys.stdout.buffer.write(z.read(sys.argv[3]))\n")
        self.command("unzip", 'exec "$PYTHON_BIN" "$SIM/unzip.py" "$@"')
        self.command("id", "echo 0")
        self.command("mntroot", 'echo "root $*" >> "$SIM/calls"; case "$1" in rw) [ ! -f "$SIM/fail-root" ];; ro) [ ! -f "$SIM/fail-root-ro" ];; esac')
        self.command("sleep", "exit 0")
        # Real host free space is unrelated to Kindle partitions. Individual
        # preflight cases override this deterministic POSIX/BusyBox df fixture.
        self.command("df", r'''echo "df $*" >> "$SIM/calls"
echo 'Filesystem 1024-blocks Used Available Capacity Mounted on'
echo 'kindle 1048576 1024 1047552 1% /'
''')
        self.command("lipc-get-prop", '\n'.join([
            '[ ! -f "$SIM/fail-get-$2" ] || exit 1', 'case "$2" in orientationLock) cat "$SIM/orientation";; *) cat "$SIM/$2";; esac']))
        self.command("lipc-set-prop", r'''echo "set $*" >> "$SIM/calls"
[ ! -f "$SIM/fail-set-$2" ] || exit 1
case "$2" in
 orientationLock)
    [ ! -f "$SIM/orientation-timeout" ] || exit 0
    printf '%s\n' "$3" > "$SIM/orientation";;
 eatTapMode|preventScreenSaver) printf '%s\n' "$3" > "$SIM/$2";;
esac
''')
        self.command("fbset", r'''[ ! -f "$SIM/fail-geometry" ] || exit 1
if [ -f "$SIM/scribe-geometry" ]; then echo 'geometry 2480 1860 2480 1860 8'; exit; fi
case "$(cat "$SIM/orientation")" in R|L) echo 'geometry 1696 1272 1696 1272 8';; *) echo 'geometry 1272 1696 1272 1696 8';; esac
''')
        self.command("initctl", r'''echo "service $*" >> "$SIM/calls"
case "$1" in
 status) if [ -f "$SIM/running" ]; then echo 'native-reading-time start/running, process 123'; else echo 'native-reading-time stop/waiting'; fi;;
 stop) rm -f "$SIM/running"; exit 0;;
 start)
   if [ -f "$SIM/fail-service" ]; then rm -f "$SIM/fail-service"; exit 1; fi
   : > "$SIM/running"
   [ -f "$SIM/us/reading-time/reading-time.tsv" ] || printf 'date\tbook_id\tseconds\ttitle\n' > "$SIM/us/reading-time/reading-time.tsv"
   exit 0;;
 reload-configuration) [ ! -f "$SIM/fail-reload" ];;
esac
''')
        self.command("fbink", r'''echo "fbink $*" >> "$SIM/calls"
case " $* " in *' -e '*) exit 99;; esac
[ ! -f "$SIM/fail-fbink" ] || exit 1
case " $* " in *GC16_FAST*) [ ! -f "$SIM/fail-fast" ] || exit 1;; esac
exit 0
''')
        self.command("lua", r'''case "$1" in
 *reading-insights-touch*.lua)
    echo "$$" > "$SIM/touch-pid"
    [ ! -f "$SIM/fail-touch" ] || exit 7
    while [ -f "$SIM/block-touch" ]; do /usr/bin/sleep 0.05; done
    head -n 1 "$SIM/actions"
    tail -n +2 "$SIM/actions" > "$SIM/actions.next"; mv "$SIM/actions.next" "$SIM/actions";;
 *) exec "$PYTHON_BIN" "''' + (OUT / "lua_runner.py").as_posix() + r'''" "$@";;
esac
''')
        self.command("busybox", '[ "$1" = tar ] || exit 1; shift; /usr/bin/tar "$@"')
        self.chmod(self.mock.glob("*"))

    def chmod(self, paths):
        paths = [p.as_posix() for p in paths]
        subprocess.run([SH, "-c", 'export PATH="/usr/bin:/bin:$PATH"; chmod 755 "$@"', "chmod", *paths], check=True, capture_output=True)

    def transform(self, raw):
        text = raw.decode("utf-8")
        replacements = {"/mnt/us": self.us.as_posix(), "/tmp": self.tmp.as_posix(), "/etc/upstart": (self.etc / "upstart").as_posix(),
                        "/etc/prettyversion.txt": (self.etc / "prettyversion.txt").as_posix(), "/etc/version.txt": (self.etc / "version.txt").as_posix(),
                        "/var/local/deviceType.txt": (self.root / "var/local/deviceType.txt").as_posix(),
                        "/proc/device-tree/model": (self.root / "model").as_posix(), "/sys/class/input": (self.sys / "class/input").as_posix(),
                        "/sys/class/graphics": (self.sys / "class/graphics").as_posix(), "/dev/input/event1": (self.root / "touch").as_posix(),
                        "/sbin/initctl": (self.mock / "initctl").as_posix(), "/var/local/kmc/bin/fbink": (self.mock / "fbink").as_posix()}
        for old, new in replacements.items(): text = text.replace(old, new)
        text=text.replace("/bin/sh ", '"'+self.shell.replace("\\", "/")+'" ')
        return text.encode("utf-8")

    def prepare_payload(self):
        sources = {}
        with tarfile.open(fileobj=io.BytesIO(self.original_tar)) as t:
            for m in t.getmembers():
                name = m.name.split("/", 1)[1]
                if name == "payload-manifest.tsv": continue
                raw = t.extractfile(m).read()
                if name.endswith((".sh", ".conf", ".txt")): raw = self.transform(raw)
                sources[name] = raw
        manifest = "".join(f"{cksum(b)[0]}\t{len(b)}\t{n}\n" for n, b in sorted(sources.items()))
        sources["payload-manifest.tsv"] = manifest.encode("utf-8")
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as t:
            for name, raw in sorted(sources.items()):
                m = tarfile.TarInfo("native-reading-time-package/" + name); m.size = len(raw); m.mode = 0o755 if name.endswith(".sh") else 0o644
                t.addfile(m, io.BytesIO(raw))
        raw = buffer.getvalue(); self.payload = self.docs / PAYLOAD; self.payload.write_bytes(raw)
        boot = self.transform(self.original_boot).decode("utf-8")
        import re
        checksum, size = cksum(raw)
        boot = re.sub(r"EXPECTED_CKSUM=\d+", f"EXPECTED_CKSUM={checksum}", boot)
        boot = re.sub(r"EXPECTED_SIZE=\d+", f"EXPECTED_SIZE={size}", boot)
        write(self.docs / BOOTSTRAP, boot)
        self.package_sources = sources

    def run(self, path, ok=True, timeout=120):
        command = [self.shell, "-c", 'export PATH="$SIM/mockbin:/usr/bin:/bin:$PATH"; exec "$1" "$2"', "run", self.shell, Path(path).as_posix()]
        # Files avoid a timed-out MSYS descendant retaining inherited pipe handles.
        with (self.root / "process.stdout").open("wb") as stdout, (self.root / "process.stderr").open("wb") as stderr:
            process = subprocess.Popen(command, env=self.env, stdout=stdout, stderr=stderr, cwd=ROOT)
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    process.kill()
                process.wait(timeout=5)
                raise
        p = subprocess.CompletedProcess(command, code, (self.root / "process.stdout").read_text(encoding="utf-8", errors="replace"), (self.root / "process.stderr").read_text(encoding="utf-8", errors="replace"))
        if ok: assert p.returncode == 0, (p.returncode, p.stdout, p.stderr, self.install_log())
        else: assert p.returncode != 0, (p.stdout, p.stderr)
        return p

    def install(self, ok=True): return self.run(self.docs / BOOTSTRAP, ok=ok)
    def install_log(self):
        p = self.base / "install-last.log"; return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    def preserved(self):
        return {p.relative_to(self.base).as_posix(): digest(p) for p in self.base.rglob("*") if p.is_file() and
                (p.name in {"reading-time.tsv", "reading-time.tsv.bak", "user.conf", "book-cover-cache.tsv", "book-cover-misses.tsv"} or
                 any(folder in p.parts for folder in {"history", "book-covers", "statistics-cache"}))}
    def seed(self, version):
        self.flag("running")
        for name, content in {"VERSION": version, "reading-time.tsv": "date\tbook_id\tseconds\ttitle\n2026-09-06\tb1\t14760\tBook\n",
                              "reading-time.tsv.bak": "original backup", "user.conf": "custom=true", "book-cover-cache.tsv": "b1\t" + (self.base / "book-covers/cover.jpg").as_posix(),
                              "book-cover-misses.tsv": "b2\tsignature", "book-covers/cover.jpg": "existing cover bytes",
                              "history/2025.tsv": "old history", "statistics-cache/summary.tsv": "cached statistics",
                              "bin/native-reading-time-daemon.sh": "old daemon", "fonts/NotoSansCJKsc-Regular.otf": "old font",
                              "assets/launcher-icon.png": "old icon", "releases/old/marker": "old release"}.items():
            write(self.base / name, content)
        write(self.docs / "阅读记录.sh", "old launcher")
        write(self.etc / "upstart/native-reading-time.conf", "old service")
    def no_temporary(self):
        assert not list(self.tmp.iterdir()), list(self.tmp.iterdir())
        assert not list(self.base.glob(".install-*"))
        assert not list(self.base.glob("install-last.log.tar-list.*"))
    def calls(self):
        p=self.root / "calls"; return p.read_text(encoding="utf-8") if p.exists() else ""
