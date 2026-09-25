"""Offline fixtures for the 9.7.5-test local-cover fallback and launcher art."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import struct
import subprocess
import sys
import tempfile
import zipfile

from PIL import Image, ImageStat


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "native-reading-time-package"
HELPER = PKG / "reading-insights-cover.lua"
OUT = ROOT / "build/validation"
OUT.mkdir(parents=True, exist_ok=True)


def run_lua(runner: Path, *args: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(runner.relative_to(ROOT)), str(HELPER.relative_to(ROOT)), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if ok:
        assert result.returncode == 0, (args, result.stdout, result.stderr)
    else:
        assert result.returncode != 0, (args, result.stdout, result.stderr)
    return result


def jpeg_bytes(path: Path, gray: int) -> bytes:
    Image.new("L", (48, 72), gray).save(path, "JPEG", quality=85)
    return path.read_bytes()


with tempfile.TemporaryDirectory(prefix="cover-fixtures-", dir=OUT) as tmp_name:
    tmp = Path(tmp_name)
    runner = tmp / "lua_runner.py"
    runner.write_text(
        """from pathlib import Path
import sys
from lupa.lua51 import LuaRuntime
lua=LuaRuntime()
lua.globals().arg=lua.table_from({i:v for i,v in enumerate(sys.argv[2:],1)})
lua.execute(Path(sys.argv[1]).read_text(encoding='utf-8'))
""",
        encoding="utf-8",
    )

    cover_jpg = tmp / "cover.jpg"
    cover_data = jpeg_bytes(cover_jpg, 96)
    epub = tmp / "usb-book.epub"
    container_xml = """<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""
    opf = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata><meta name="cover" content="legacy-cover"/></metadata>
  <manifest>
    <item id="legacy-cover" href="images/wrong.jpg" media-type="image/jpeg"/>
    <item id="official" href="images/front%20cover.jpg" media-type="image/jpeg" properties="nav cover-image"/>
  </manifest>
</package>"""
    with zipfile.ZipFile(epub, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", container_xml)
        archive.writestr("OEBPS/content.opf", opf)
        archive.writestr("OEBPS/images/front cover.jpg", cover_data)
        archive.writestr("OEBPS/images/wrong.jpg", jpeg_bytes(tmp / "wrong.jpg", 180))

    container_file = tmp / "container.xml"
    opf_file = tmp / "content.opf"
    container_file.write_text(container_xml, encoding="utf-8")
    opf_file.write_text(opf, encoding="utf-8")
    assert run_lua(runner, "epub-container", str(container_file.relative_to(ROOT))).stdout.strip() == "OEBPS/content.opf"
    candidates = run_lua(runner, "epub-opf", "OEBPS/content.opf", str(opf_file.relative_to(ROOT))).stdout.splitlines()
    assert candidates[:2] == ["OEBPS/images/front cover.jpg", "OEBPS/images/wrong.jpg"], candidates
    assert run_lua(runner, "image-extension", str(cover_jpg.relative_to(ROOT))).stdout.strip() == "jpg"

    # Minimal two-record PalmDB/MOBI: EXTH 201 points at resource record 1.
    record0 = bytearray(300)
    record0[16:20] = b"MOBI"
    record0[20:24] = struct.pack(">I", 232)
    record0[124:128] = struct.pack(">I", 1)  # first image record
    record0[144:148] = struct.pack(">I", 0x40)  # EXTH present
    exth = 16 + 232
    record0[exth : exth + 4] = b"EXTH"
    record0[exth + 4 : exth + 8] = struct.pack(">I", 24)
    record0[exth + 8 : exth + 12] = struct.pack(">I", 1)
    record0[exth + 12 : exth + 16] = struct.pack(">I", 201)
    record0[exth + 16 : exth + 20] = struct.pack(">I", 12)
    record0[exth + 20 : exth + 24] = struct.pack(">I", 0)
    pdb_header = bytearray(78)
    pdb_header[60:68] = b"BOOKMOBI"
    pdb_header[76:78] = struct.pack(">H", 2)
    first_offset = 96
    second_offset = first_offset + len(record0)
    table = struct.pack(">I", first_offset) + b"\0\0\0\1" + struct.pack(">I", second_offset) + b"\0\0\0\2"
    mobi = tmp / "usb-book.mobi"
    mobi.write_bytes(bytes(pdb_header) + table + b"\0\0" + bytes(record0) + cover_data)
    extracted = tmp / "mobi-cover.bin"
    run_lua(runner, "mobi", str(mobi.relative_to(ROOT)), str(extracted.relative_to(ROOT)))
    assert extracted.read_bytes() == cover_data

    invalid = tmp / "broken.mobi"
    invalid.write_bytes(b"not a mobi")
    run_lua(runner, "mobi", str(invalid.relative_to(ROOT)), str((tmp / "broken-cover").relative_to(ROOT)), ok=False)

launcher = Image.open(PKG / "launcher-icon.png").convert("RGB")
assert launcher.size == (600, 960)
assert launcher.width / launcher.height == 0.625
gray = launcher.convert("L")
gray_min, gray_max = ImageStat.Stat(gray).extrema[0]
assert gray_min < 120 and gray_max > 240

viewer = (PKG / "阅读记录-optimized.sh").read_text(encoding="utf-8")
assert 'case "$embedded_source" in' in viewer
assert "*.epub|*.EPUB" in viewer and "*.mobi|*.MOBI" in viewer and "*.pdf|*.PDF) return 1" in viewer
assert "cover_miss_known" in viewer and "COVER_CACHE_DIR" in viewer
assert all(name not in viewer for name in ("pdftoppm", "mutool", "poppler", "mupdf"))

# Firmware schemas that powered v9.7.4 may not expose the optional p_location
# field added to the v9.7.5 catalog query.  Exercise the exact shipped SQL:
# the rich query may fail, but the thumbnail-compatible query must still return
# the p_thumbnail row needed by a clean install with no persistent cache.
catalog_block = viewer[viewer.index("ensure_catalog()") : viewer.index("ensure_progress()")]
catalog_queries = re.findall(r'"(SELECT -1,.*?)" > "\$CATALOG\.new"', catalog_block)
assert len(catalog_queries) == 2, catalog_queries
location_query, thumbnail_query = catalog_queries
assert "p_location" in location_query and "p_mimeType" not in location_query
assert "p_location" not in thumbnail_query and "p_thumbnail" in thumbnail_query
with tempfile.TemporaryDirectory(prefix="cover-schema-", dir=OUT) as schema_tmp:
    schema_db = Path(schema_tmp) / "cc-old-schema.db"
    with closing(sqlite3.connect(schema_db)) as connection:
        connection.execute(
            "CREATE TABLE Entries (p_titles_0_nominal TEXT, p_cdeKey TEXT, "
            "p_thumbnail TEXT, p_lastAccess INTEGER, p_percentFinished REAL)"
        )
        connection.execute(
            "INSERT INTO Entries VALUES (?, ?, ?, ?, ?)",
            ("Clean install book", "clean-id", "/mnt/us/system/thumbnails/clean.jpg", 1, 25),
        )
        try:
            connection.execute(location_query).fetchall()
        except sqlite3.OperationalError as error:
            assert "p_location" in str(error)
        else:
            raise AssertionError("old-schema fixture unexpectedly accepted p_location")
        fallback_rows = connection.execute(thumbnail_query).fetchall()
        assert fallback_rows == [
            (-1, "Clean install book", "clean-id", "/mnt/us/system/thumbnails/clean.jpg", "", "")
        ]
        connection.execute("ALTER TABLE Entries ADD COLUMN p_location TEXT")
        connection.execute("UPDATE Entries SET p_location='/mnt/us/documents/clean.epub'")
        rich_rows = connection.execute(location_query).fetchall()
        assert rich_rows[0][4] == "/mnt/us/documents/clean.epub"

installer = (PKG / "Install-Native-Reading-Time-Optimized.sh").read_text(encoding="utf-8")
assert 'mkdir -p ' in installer and '"$COVER_CACHE_DIR"' in installer
assert 'chmod 700 "$COVER_CACHE_DIR"' in installer
assert 'cover helper is not readable after installation' in installer
assert 'COVER_DEBUG="${READING_COVER_DEBUG:-0}"' in viewer and "cover-debug.enabled" in viewer

result = {
    "result": "PASS",
    "checks": [
        "EPUB3 cover-image takes priority over EPUB2 metadata fallback and percent-decoded paths remain archive-safe.",
        "MOBI EXTH record 201 selects the formal embedded cover without loading the whole ebook or adding a library.",
        "Malformed MOBI exits cleanly; PDF has no bundled renderer and falls back after Kindle thumbnail lookup.",
        "A cc.db without optional p_location rejects the rich query but succeeds through the shipped thumbnail-compatible fallback.",
        "The installer creates a private writable cover cache and verifies the installed helper; cover tracing remains opt-in.",
        "Launcher art is a 600x960 (5:8) portrait RGB PNG with nontrivial grayscale contrast.",
    ],
}
(OUT / "cover-fallback-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=True, indent=2))
