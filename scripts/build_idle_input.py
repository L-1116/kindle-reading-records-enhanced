"""Build the passive owner/input multiplexer; no Kindle toolchain is required at runtime."""
from pathlib import Path
import hashlib
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ZIG = os.environ.get('READING_ZIG') or shutil.which('zig') or str(ROOT/'build/toolchain/ziglang/zig.exe')

def build():
    assert subprocess.check_output([ZIG, 'version'], text=True).strip() == '0.13.0'
    target = ROOT/'native-reading-time-package/idle-input'
    subprocess.run([ZIG, 'cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-Os', '-fno-ident',
                    'native/idle-input/idle-input.c', '-target', 'arm-linux-musleabi',
                    '-mcpu=cortex_a7', '-static', '-s', '-o', str(target)], cwd=ROOT, check=True)
    raw = target.read_bytes()
    assert raw[:6] == b'\x7fELF\x01\x01' and int.from_bytes(raw[18:20], 'little') == 40
    off = int.from_bytes(raw[28:32], 'little')
    size = int.from_bytes(raw[42:44], 'little'); count = int.from_bytes(raw[44:46], 'little')
    assert all(int.from_bytes(raw[off+i*size:off+i*size+4], 'little') != 3 for i in range(count))
    print('static ARM input guard:', len(raw), 'bytes; sha256', hashlib.sha256(raw).hexdigest())

if __name__ == '__main__':
    build()
