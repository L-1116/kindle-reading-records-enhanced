"""Build an unpublished Compatibility V3 cover regression test package."""

from pathlib import Path
import hashlib
import json
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
REPORT = ROOT / "build" / "validation" / "cover-v3-package.json"
ARCHIVE = DIST / "kindle-reading-records-v9.7.5-compat-v3-cover-test.zip"
MANIFEST_NAME = "PACKAGE-MANIFEST.json"
MANIFEST_REPORT = DIST / "kindle-reading-records-v9.7.5-compat-v3-cover-test.manifest.json"
CHECKSUM_FILE = DIST / "kindle-reading-records-v9.7.5-compat-v3-cover-test.sha256"
RESOLVER = Path("native-reading-time-package/阅读记录-optimized.sh")
FILES = [
    ROOT / "RUNME.sh",
    ROOT / "README.txt",
    ROOT / "documents/reading-records-install.sh",
    ROOT / "documents/reading-records-uninstall.sh",
    *sorted(p for p in (ROOT / "extensions/reading-records-installer").rglob("*") if p.is_file()),
    *sorted(p for p in (ROOT / "native-reading-time-package").rglob("*") if p.is_file()),
]
DEBUG_FILES = {
    "cover-debug.sh": ROOT / "debug/cover-debug/cover-debug.sh",
    "documents/阅读记录封面诊断.sh": ROOT / "debug/cover-debug/documents/阅读记录封面诊断.sh",
    "extensions/reading-records-cover-debug/config.xml": ROOT / "debug/cover-debug/extensions/reading-records-cover-debug/config.xml",
    "extensions/reading-records-cover-debug/menu.json": ROOT / "debug/cover-debug/extensions/reading-records-cover-debug/menu.json",
    "extensions/reading-records-cover-debug/bin/action.sh": ROOT / "debug/cover-debug/extensions/reading-records-cover-debug/bin/action.sh",
    "COVER-V3-TEST-README.txt": ROOT / "debug/cover-v3-test-README.txt",
}
CANONICAL_PAIRS = {
    "documents/reading-records-uninstall.sh": "native-reading-time-package/resources/reading-records-uninstall.sh",
    "extensions/reading-records-installer/bin/action.sh": "native-reading-time-package/resources/kual/reading-records-installer/bin/action.sh",
    "extensions/reading-records-installer/config.xml": "native-reading-time-package/resources/kual/reading-records-installer/config.xml",
    "extensions/reading-records-installer/menu.json": "native-reading-time-package/resources/kual/reading-records-installer/menu.json",
}


def posix_cksum(data: bytes) -> str:
    """POSIX cksum CRC and size, matching Kindle's `cksum < file`."""
    crc = 0
    for value in data + bytes((len(data) >> shift) & 0xFF for shift in range(0, max(8, len(data).bit_length() + 7), 8)):
        crc ^= value << 24
        for _ in range(8):
            crc = ((crc << 1) ^ (0x04C11DB7 if crc & 0x80000000 else 0)) & 0xFFFFFFFF
    return f"{(~crc) & 0xFFFFFFFF} {len(data)}"


def main() -> None:
    for deployed, canonical in CANONICAL_PAIRS.items():
        assert (ROOT / deployed).read_bytes() == (ROOT / canonical).read_bytes(), deployed
    sources = {file.relative_to(ROOT).as_posix(): file for file in FILES}
    for name, file in DEBUG_FILES.items():
        assert name not in sources, f"duplicate package entry: {name}"
        sources[name] = file
    payload = []
    for name, file in sorted(sources.items()):
        raw = file.read_bytes()
        payload.append({
            "path": name,
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "executable": name.endswith(".sh"),
        })
    manifest_bytes = (json.dumps({"format": 1, "files": payload}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    def add_entry(package: zipfile.ZipFile, name: str, raw: bytes, executable: bool) -> None:
        entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
        entry.create_system = 3
        entry.external_attr = ((0o100755 if executable else 0o100644) << 16)
        package.writestr(entry, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    DIST.mkdir(exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for item in payload:
            add_entry(package, item["path"], sources[item["path"]].read_bytes(), item["executable"])
        add_entry(package, MANIFEST_NAME, manifest_bytes, False)
    source_bytes = (ROOT / RESOLVER).read_bytes()
    with zipfile.ZipFile(ARCHIVE) as package:
        assert package.testzip() is None
        assert set(package.namelist()) == set(sources) | {MANIFEST_NAME}
        assert package.read(MANIFEST_NAME) == manifest_bytes
        for item in payload:
            name = item["path"]
            packed = package.read(name)
            assert packed == sources[name].read_bytes(), name
            assert len(packed) == item["size"] and hashlib.sha256(packed).hexdigest() == item["sha256"], name
            assert ((package.getinfo(name).external_attr >> 16) & 0o777) == (0o755 if item["executable"] else 0o644), name
        packaged_bytes = package.read(RESOLVER.as_posix())
    assert source_bytes == packaged_bytes
    MANIFEST_REPORT.write_bytes(manifest_bytes)
    archive_sha256 = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    CHECKSUM_FILE.write_text(f"{archive_sha256}  {ARCHIVE.name}\n", encoding="ascii")
    result = {
        "package": str(ARCHIVE),
        "manifest": str(MANIFEST_REPORT),
        "checksum_file": str(CHECKSUM_FILE),
        "archive_sha256": archive_sha256,
        "archive_files": len(payload) + 1,
        "source_resolver_path": str(ROOT / RESOLVER),
        "packaged_resolver_path": f"{ARCHIVE}::{RESOLVER.as_posix()}",
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "packaged_sha256": hashlib.sha256(packaged_bytes).hexdigest(),
        "source_cksum": posix_cksum(source_bytes),
        "packaged_cksum": posix_cksum(packaged_bytes),
        "source_equals_package": source_bytes == packaged_bytes,
    }
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
