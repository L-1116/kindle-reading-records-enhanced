"""Build the deterministic two-file 5.19 Standard ZIP and verify every byte."""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "native-reading-time-package"
VERSION = "9.7.6-5.19-normal"
BOOTSTRAP = "reading-records-9.7.6-install.sh"
PAYLOAD = "阅读记录安装数据.tar"
ARCHIVE = ROOT / "dist" / f"ReadingTime-{VERSION}.zip"
OUT = ROOT / "build/validation"

def cksum(data: bytes) -> tuple[int, int]:
    # POSIX CRC-32, including byte length. One lookup per byte.
    table = []
    for value in range(256):
        crc = value << 24
        for _ in range(8):
            crc = ((crc << 1) ^ (0x04C11DB7 if crc & 0x80000000 else 0)) & 0xFFFFFFFF
        table.append(crc)
    crc = 0
    for value in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ table[((crc >> 24) ^ value) & 255]
    length = len(data)
    while length:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ table[((crc >> 24) ^ length) & 255]
        length >>= 8
    return (~crc & 0xFFFFFFFF, len(data))

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def main() -> dict:
    ARCHIVE.parent.mkdir(exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    files = {"install.sh", "install-manifest.txt", "cleanup-manifest.txt",
             "resources/reading-records-install-cleanup.sh"}
    for line in (PKG / "install-manifest.txt").read_text(encoding="utf-8").splitlines():
        src, category, dst, mode = line.split("\t")
        assert category in {"release", "base", "docs", "service"}
        assert not Path(src).is_absolute() and ".." not in Path(src).parts
        files.add(src)
    sources = {name: (PKG / name).read_bytes() for name in sorted(files)}
    for name, raw in sources.items():
        if name.endswith((".sh", ".lua", ".awk", ".txt", ".tsv", ".conf")):
            assert b"\r\n" not in raw and not raw.startswith(b"\xef\xbb\xbf"), name
    manifest = "".join(f"{cksum(raw)[0]}\t{len(raw)}\t{name}\n" for name, raw in sources.items()).encode("utf-8")
    sources["payload-manifest.tsv"] = manifest
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, raw in sorted(sources.items()):
            entry = tarfile.TarInfo("native-reading-time-package/" + name)
            entry.size = len(raw)
            entry.mode = 0o755 if name.endswith(".sh") else 0o644
            entry.mtime = 0
            archive.addfile(entry, io.BytesIO(raw))
    payload = buffer.getvalue()
    checksum, size = cksum(payload)
    bootstrap = (ROOT / "documents" / BOOTSTRAP).read_text(encoding="utf-8")
    assert bootstrap.splitlines()[1] == "# Name: 安装阅读记录"
    bootstrap = bootstrap.replace("@PAYLOAD_CKSUM@", str(checksum)).replace("@PAYLOAD_SIZE@", str(size)).encode("utf-8")
    assert b"@PAYLOAD_" not in bootstrap and len(bootstrap) < 8192
    temporary = ARCHIVE.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw, mode in [(BOOTSTRAP, bootstrap, 0o755), (PAYLOAD, payload, 0o644)]:
            entry = zipfile.ZipInfo(name, date_time=(2026, 10, 4, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = (0o100000 | mode) << 16
            archive.writestr(entry, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    os.replace(temporary, ARCHIVE)
    with zipfile.ZipFile(ARCHIVE) as archive:
        assert archive.namelist() == [BOOTSTRAP, PAYLOAD]
        assert archive.testzip() is None
        assert archive.read(BOOTSTRAP) == bootstrap and archive.read(PAYLOAD) == payload
    with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
        assert all(member.isfile() for member in archive.getmembers())
        assert len(archive.getmembers()) == len(sources)
        for member in archive.getmembers():
            name = member.name.removeprefix("native-reading-time-package/")
            assert archive.extractfile(member).read() == sources[name]
    result = {"result": "PASS", "version": VERSION, "archive": str(ARCHIVE.resolve()),
              "zip_entries": [BOOTSTRAP, PAYLOAD], "zip_bytes": ARCHIVE.stat().st_size,
              "zip_sha256": sha(ARCHIVE.read_bytes()), "payload_bytes": size,
              "payload_cksum": checksum, "payload_sha256": sha(payload),
              "bootstrap_bytes": len(bootstrap), "bootstrap_sha256": sha(bootstrap),
              "payload_files": len(sources), "files": {name: {"size": len(raw), "sha256": sha(raw)} for name, raw in sorted(sources.items())}}
    (OUT / "package-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "files"}, ensure_ascii=True, indent=2))
    return result

if __name__ == "__main__":
    main()
