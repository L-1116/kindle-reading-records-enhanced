"""Build only the current Standard two-file installer. Historical module name retained."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tarfile
import zipfile

from migration_inventory import ownership_manifest
from package_release import FILES as STANDARD_FILES


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_VERSION = "9.8.2-5.20-vera"
# Product/UI revision only: keep the verified daemon/helper runtime paths.
RUNTIME_VERSION = "9.8.1-5.20-vera-test1"
DIST = ROOT / "dist/v9.8.2"
SIMPLE_ARCHIVE = DIST / "Kindle-Reading-Records-v9.8.2-5.20-vera.zip"
BOOT_NAME = "reading-records-v4-install.sh"
TAR_NAME = "阅读记录安装数据.tar"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _crc_table() -> tuple[int, ...]:
    values = []
    for byte in range(256):
        crc = byte << 24
        for _ in range(8):
            crc = ((crc << 1) ^ (0x04C11DB7 if crc & 0x80000000 else 0)) & 0xFFFFFFFF
        values.append(crc)
    return tuple(values)


CRC_TABLE = _crc_table()


def posix_cksum(data: bytes) -> int:
    crc = 0
    length = len(data)
    for byte in data:
        crc = ((crc << 8) ^ CRC_TABLE[((crc >> 24) ^ byte) & 255]) & 0xFFFFFFFF
    while length:
        byte = length & 255
        crc = ((crc << 8) ^ CRC_TABLE[((crc >> 24) ^ byte) & 255]) & 0xFFFFFFFF
        length >>= 8
    return (~crc) & 0xFFFFFFFF


def sources(variant: str) -> dict[str, bytes]:
    if variant != "standard":
        raise ValueError("KS development and builds are paused")
    paths = {path.relative_to(ROOT).as_posix(): path for path in STANDARD_FILES}
    assert all(path.is_file() for path in paths.values())
    result = {name: path.read_bytes() for name, path in paths.items()}
    bootstrap_path = f"/mnt/us/documents/{BOOT_NAME}"
    cleanup_path = "/mnt/us/documents/reading-records-install-cleanup.sh"
    result["RUNME.sh"] = f'#!/bin/sh\n# READING_RECORDS_V4_RUNME\nexec /bin/sh "{bootstrap_path}"\n'.encode()
    result["README.txt"] = (f"Kindle 阅读记录 {PRODUCT_VERSION} Standard 安装包\n只解压外层 ZIP 一次，把安装脚本和数据 TAR 一起复制到 documents。\n不要继续解压 TAR。\n").encode()
    legacy_document = "documents/reading-records-install.sh" if variant == "standard" else "documents/reading-records-ks-install.sh"
    result[legacy_document] = f'#!/bin/sh\n# Name: 安装阅读记录\nexec /bin/sh "{bootstrap_path}"\n'.encode()
    kual = f'''#!/bin/sh
ACTION="${{1:-diagnostics}}"
case "$ACTION" in
    install|upgrade|repair) exec /bin/sh "{bootstrap_path}";;
    cleanup) exec /bin/sh "{cleanup_path}";;
esac
if [ "$ACTION" = diagnostics ]; then
    if [ -r /mnt/us/reading-time/bin/diagnostics.sh ]; then exec /bin/sh /mnt/us/reading-time/bin/diagnostics.sh; fi
fi
exit 127
'''.encode()
    result["extensions/reading-records-installer/bin/action.sh"] = kual
    result["native-reading-time-package/resources/kual/reading-records-installer/bin/action.sh"] = kual
    result["V4-PAYLOAD"] = f"installer_format=two-file-1\nproduct_version={PRODUCT_VERSION}\nvariant={variant}\n".encode()
    result["v4/cleanup.sh"] = (ROOT / "v4/cleanup.sh").read_bytes()
    result["native-reading-time-package/migration-manifest.tsv"] = ownership_manifest(result, posix_cksum, make_tar)
    build_id = sha(b"".join(name.encode() + b"\0" + sha(raw).encode() for name, raw in sorted(result.items())))[:20]
    result["BUILD-INFO"] = f"product_version={PRODUCT_VERSION}\nvariant=standard\nbuild_id={build_id}\nsource_baseline=fd9a417d12539f0a9997ba57f60cdb9e7b1edbc8\n".encode()
    entries = [{"path": name, "size": len(raw), "sha256": sha(raw)} for name, raw in sorted(result.items())]
    manifest_name = "PACKAGE-MANIFEST.json" if variant == "standard" else "PACKAGE-MANIFEST-KS.json"
    result[manifest_name] = (json.dumps({"format": 4, "installer_format": "two-file-1", "product_version": PRODUCT_VERSION, "variant": variant, "files": entries}, ensure_ascii=False, indent=2) + "\n").encode()
    return result


def make_tar(files: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, raw in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            info.mode = 0o755 if (name.endswith(".sh") or name.endswith("/cover-image")) else 0o644
            info.mtime = 0
            archive.addfile(info, io.BytesIO(raw))
    return stream.getvalue()


def make_zip(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 3, 0, 0, 0))
            info.create_system = 3
            info.external_attr = ((0o100755 if (name.endswith(".sh") or name.endswith("/cover-image")) else 0o100644) << 16)
            archive.writestr(info, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(files)
        for name, raw in files.items():
            assert archive.read(name) == raw


def build(variant: str) -> dict:
    payload_files = sources(variant)
    if variant == "standard":
        assert "native-reading-time-package/阅读记录-ks.sh" not in payload_files
        assert "native-reading-time-package/阅读记录-optimized.sh" in payload_files
    else:
        assert "native-reading-time-package/阅读记录-optimized.sh" not in payload_files
        assert "native-reading-time-package/阅读记录-ks.sh" in payload_files
    tar_bytes = make_tar(payload_files)
    cksum = str(posix_cksum(tar_bytes))
    bootstrap = (ROOT / "v4/bootstrap.template.sh").read_text(encoding="utf-8")
    bootstrap = bootstrap.replace("@DEVICE_VARIANT@", (ROOT / "native-reading-time-package/compat/device_variant.sh").read_text(encoding="utf-8")).replace("@RUNTIME_VERSION@", RUNTIME_VERSION).replace("@LIFECYCLE@", (ROOT / "native-reading-time-package/compat/lifecycle.sh").read_text(encoding="utf-8")).replace("@PRODUCT_VERSION@", PRODUCT_VERSION).replace("@BUILD_ID@", payload_files["BUILD-INFO"].decode().split("build_id=")[1].splitlines()[0]).replace("@VARIANT@", variant).replace("@SIZE@", str(len(tar_bytes))).replace("@CKSUM@", cksum).encode("utf-8")
    simple = SIMPLE_ARCHIVE
    make_zip(simple, {BOOT_NAME: bootstrap, TAR_NAME: tar_bytes})
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as archive:
        assert all(member.isfile() and not member.issym() and not member.islnk() for member in archive)
        assert set(archive.getnames()) == set(payload_files)
        for name, raw in payload_files.items():
            assert archive.extractfile(name).read() == raw
    return {"variant": variant, "simple": str(simple), "simple_sha256": sha(simple.read_bytes()), "payload_size": len(tar_bytes), "payload_cksum": cksum, "payload_sha256": sha(tar_bytes), "payload_files": len(payload_files)}


def main() -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    results = [build("standard")]
    (DIST / "V4-SHA256SUMS.txt").write_text("".join(f"{item[key]}  {Path(item[path_key]).name}\n" for item in results for key, path_key in (("simple_sha256", "simple"),)), encoding="ascii")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
