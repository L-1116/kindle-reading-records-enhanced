"""Exercise real decoder pixels, v1 migration, cache repair and bounded pruning."""
from pathlib import Path
import hashlib, json, os, subprocess, tempfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / ('build/cover-image-host.exe' if os.name == 'nt' else 'build/cover-image-host')
assert HOST.is_file(), 'Build the host decoder with scripts/build_cover_helper.py first'
OUT = ROOT / 'build/validation/color-covers'
OUT.mkdir(parents=True, exist_ok=True)
results = []

def check(name):
    results.append(name)
    print('PASS:', name, flush=True)

def fnv(data):
    h = 14695981039346656037
    for b in data:
        h = ((h ^ b) * 1099511628211) & ((1 << 64) - 1)
    return f'{h:016x}'

def image(path):
    with Image.open(path) as im:
        return im.copy()

with tempfile.TemporaryDirectory(prefix='rgb-', dir=OUT) as tmp:
    base = Path(tmp); cache = base / 'cache'; cache.mkdir()
    def prepare(path, custom=False):
        args = ['prepare', str(base), path.name, str(cache)] if custom else ['real', str(path), str(cache)]
        run = subprocess.run([str(HOST), *args], capture_output=True, encoding='utf-8', timeout=10)
        assert run.returncode == 0, (args, run.returncode, run.stderr)
        output = Path(run.stdout.strip())
        assert output.parent == cache and output.suffix == '.ppm'
        assert output.read_bytes()[:15] == b'P6\n240 360\n255\n'
        assert output.stat().st_size == 240 * 360 * 3 + 15
        return output

    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    src = base / '彩色 cover.png'; stripes = Image.new('RGB', (240, 360))
    for n, color in enumerate(colors):
        stripes.paste(color, (n * 80, 0, (n + 1) * 80, 360))
    stripes.save(src)
    old = cache / (fnv(b'v1' + src.read_bytes()) + '.pgm')
    old_raw = b'P5\n240 360\n255\n' + bytes([76]) * (240 * 360)
    old.write_bytes(old_raw)
    for custom in (False, True):
        path = prepare(src, custom); im = image(path)
        assert im.mode == 'RGB' and im.size == (240, 360)
        assert [im.getpixel((x, 180)) for x in (40, 120, 200)] == colors
        assert path.stem == fnv(b'v2' + src.read_bytes())
        assert old.read_bytes() == old_raw
    check('RGB source preserved by real and prepare; v1 grayscale cache bypassed automatically')

    stamp = path.stat().st_mtime_ns
    assert prepare(src) == path and path.stat().st_mtime_ns == stamp
    check('warm cache hit retains pixels and modification time')
    correct = path.read_bytes()
    for broken in (b'broken', correct[:-1], correct + b'x', b'P5' + correct[2:], correct.replace(b'240 360', b'360 240', 1)):
        path.write_bytes(broken)
        assert prepare(src).read_bytes() == correct
    check('cache format, dimensions, truncation and excess length repaired')

    for fmt in ('JPEG', 'BMP', 'GIF'):
        source = base / ('rgb.' + fmt.lower()); stripes.save(source, format=fmt)
        decoded = image(prepare(source))
        for x, expected in zip((40, 120, 200), colors):
            assert max(abs(a-b) for a, b in zip(decoded.getpixel((x, 180)), expected)) <= (3 if fmt == 'JPEG' else 0)
    check('JPEG color retained; original BMP and GIF formats remain supported')

    alpha = base / 'alpha.png'; Image.new('RGBA', (240, 360), (255, 0, 0, 128)).save(alpha)
    assert image(prepare(alpha, True)).getpixel((120, 180)) == (255, 127, 127)
    Image.new('RGBA', (240, 360), (0, 80, 255, 0)).save(alpha)
    assert image(prepare(alpha)).getextrema() == ((255, 255),) * 3
    landscape = base / 'landscape.png'; Image.new('RGB', (480, 240), (11, 122, 233)).save(landscape)
    framed = image(prepare(landscape))
    assert framed.getpixel((120, 0)) == (255, 255, 255)
    assert framed.getpixel((120, 180)) == (11, 122, 233)
    gray = base / 'gray.png'; Image.new('L', (240, 360), 73).save(gray)
    assert image(prepare(gray)).getpixel((120, 180)) == (73, 73, 73)
    check('alpha composited on white; proportional white borders and grayscale inputs retained')

    before = src.stat(); stripes.paste((22, 33, 144), (0, 0, 240, 360)); stripes.save(src)
    os.utime(src, ns=(before.st_atime_ns, before.st_mtime_ns))
    updated = prepare(src)
    assert updated != path and image(updated).getpixel((120, 180)) == (22, 33, 144)
    check('source content replacement detected even with preserved modification time')

    # Old and new *validated generated files* share the limit. Never prune an
    # unknown file or follow a link merely because its name resembles a cache.
    protected = {cache / 'notes.txt': b'user notes', cache / ('f'*16 + '.ppm'): b'unconfirmed contents'}
    for p, raw in protected.items(): p.write_bytes(raw)
    folder = cache / ('e'*16 + '.pgm'); folder.mkdir()
    linked = cache / ('d'*16 + '.ppm')
    try: linked.symlink_to(updated)
    except OSError: linked = None
    for i in range(140):
        (cache / f'{i:016x}.pgm').write_bytes(old_raw)
    prepare(src)
    owned = []
    for p in cache.iterdir():
        if not p.is_file() or p.is_symlink(): continue
        raw = p.read_bytes()
        if (len(raw) == 86415 and raw[:15] == b'P5\n240 360\n255\n') or (len(raw) == 259215 and raw[:15] == b'P6\n240 360\n255\n'):
            owned.append(p)
    assert len(owned) == 128 and updated in owned
    assert all(p.read_bytes() == raw for p, raw in protected.items()) and folder.is_dir()
    if linked is not None: assert linked.is_symlink()
    check('mixed PGM/PPM cache bounded to 128; current image, unknown files, directories and links protected')

report = {'result': 'PASS', 'checks': results, 'host': 'Windows' if os.name == 'nt' else 'Linux',
          'c_source_sha256': hashlib.sha256((ROOT/'native/custom-cover/cover-image.c').read_bytes()).hexdigest(),
          'hardware_display_verified': False}
(OUT/'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
