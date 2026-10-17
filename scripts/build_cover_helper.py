"""Reproducible static ARMv7 soft-float helper; Zig 0.13.0 is build-only."""
from pathlib import Path
import hashlib, os, shutil, subprocess

ROOT=Path(__file__).resolve().parents[1]
ZIG=os.environ.get('READING_ZIG') or shutil.which('zig') or str(ROOT/'build/toolchain/ziglang/zig.exe')
SOURCE=ROOT/'native/custom-cover/cover-image.c'
BIN=ROOT/'native-reading-time-package/cover-image'

def build():
    assert subprocess.check_output([ZIG,'version'],text=True).strip()=='0.13.0'
    common=[ZIG,'cc','-std=c99','-Os','-fno-ident','-DSTBI_NO_FAILURE_STRINGS',SOURCE.relative_to(ROOT).as_posix(),'-lc','-lm']
    subprocess.run(common+['-target','arm-linux-musleabi','-mcpu=cortex_a7','-static','-s','-o',str(BIN)],check=True,cwd=ROOT)
    # Host executable exercises exactly the same decoder and output pixels.
    host=ROOT/('build/cover-image-host.exe' if os.name=='nt' else 'build/cover-image-host')
    target=['-target','x86_64-windows-gnu','-lshell32'] if os.name=='nt' else []
    subprocess.run(common+target+['-s','-o',str(host)],check=True,cwd=ROOT)
    raw=BIN.read_bytes()
    assert raw[:4]==b'\x7fELF' and raw[4:6]==b'\x01\x01'
    assert int.from_bytes(raw[18:20],'little')==40
    # No PT_INTERP: no dependency on the Kindle's glibc or loader family.
    phoff=int.from_bytes(raw[28:32],'little'); size=int.from_bytes(raw[42:44],'little'); n=int.from_bytes(raw[44:46],'little')
    assert all(int.from_bytes(raw[phoff+i*size:phoff+i*size+4],'little')!=3 for i in range(n))
    print('static ARM helper',len(raw),'bytes, SHA256',hashlib.sha256(raw).hexdigest())

if __name__=='__main__':build()
