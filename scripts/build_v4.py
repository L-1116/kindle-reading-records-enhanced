"""Build the two-file V4 installers and the legacy-route compatibility ZIPs."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tarfile
import zipfile

from package_ks_release import source_map as ks_source_map
from package_release import FILES as STANDARD_FILES


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BOOT_NAME = "点这个安装，然后确认插件正常之前不要删文件.sh"
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
    if variant == "standard":
        paths = {path.relative_to(ROOT).as_posix(): path for path in STANDARD_FILES}
    else:
        paths = ks_source_map()
    assert all(path.is_file() for path in paths.values())
    result = {name: path.read_bytes() for name, path in paths.items()}
    bootstrap_path = f"/mnt/us/documents/{BOOT_NAME}"
    cleanup_path = "/mnt/us/documents/安装好之后，确认无误了再点这个.sh"
    result["RUNME.sh"] = f'#!/bin/sh\n# READING_RECORDS_V4_RUNME\nexec /bin/sh "{bootstrap_path}"\n'.encode()
    result["README.txt"] = ("Kindle 阅读记录 V4 安装包\n优先使用 documents 中的两个简易安装文件。\n此完整包保留 ;log runme 和 KUAL 入口。\n").encode()
    legacy_document = "documents/reading-records-install.sh" if variant == "standard" else "documents/reading-records-ks-install.sh"
    result[legacy_document] = f'#!/bin/sh\n# Name: 阅读记录 V4 安装\nexec /bin/sh "{bootstrap_path}"\n'.encode()
    kual = f'''#!/bin/sh
ACTION="${{1:-diagnostics}}"
case "$ACTION" in
    install|upgrade) exec /bin/sh "{bootstrap_path}";;
    cleanup) exec /bin/sh "{cleanup_path}";;
esac
if [ -r /mnt/us/native-reading-time-package/install.sh ]; then
    exec /bin/sh /mnt/us/native-reading-time-package/install.sh "$ACTION"
fi
if [ "$ACTION" = diagnostics ]; then
    if [ -r /mnt/us/reading-time/bin/diagnostics-ks.sh ]; then exec /bin/sh /mnt/us/reading-time/bin/diagnostics-ks.sh; fi
    if [ -r /mnt/us/reading-time/bin/diagnostics.sh ]; then exec /bin/sh /mnt/us/reading-time/bin/diagnostics.sh; fi
fi
exit 127
'''.encode()
    result["extensions/reading-records-installer/bin/action.sh"] = kual
    result["native-reading-time-package/resources/kual/reading-records-installer/bin/action.sh"] = kual
    result["V4-PAYLOAD"] = f"release_family=V4\nvariant={variant}\n".encode()
    result["v4/cleanup.sh"] = (ROOT / "v4/cleanup.sh").read_bytes()
    entries = [{"path": name, "size": len(raw), "sha256": sha(raw)} for name, raw in sorted(result.items())]
    manifest_name = "PACKAGE-MANIFEST.json" if variant == "standard" else "PACKAGE-MANIFEST-KS.json"
    result[manifest_name] = (json.dumps({"format": 4, "release_family": "V4", "variant": variant, "files": entries}, ensure_ascii=False, indent=2) + "\n").encode()
    return result


def make_tar(files: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, raw in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            info.mode = 0o755 if name.endswith(".sh") else 0o644
            info.mtime = 0
            archive.addfile(info, io.BytesIO(raw))
    return stream.getvalue()


def make_zip(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 3, 0, 0, 0))
            info.create_system = 3
            info.external_attr = ((0o100755 if name.endswith(".sh") else 0o100644) << 16)
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
    bootstrap = bootstrap.replace("@VARIANT@", variant).replace("@SIZE@", str(len(tar_bytes))).replace("@CKSUM@", cksum).encode("utf-8")
    label = "V4" if variant == "standard" else "V4-KS"
    simple = DIST / f"ReadingTime-{label}-Test.zip"
    full = DIST / f"ReadingTime-{label}-Full-Compatibility.zip"
    make_zip(simple, {BOOT_NAME: bootstrap, TAR_NAME: tar_bytes})
    full_files = dict(payload_files)
    full_files[f"documents/{BOOT_NAME}"] = bootstrap
    full_files[f"documents/{TAR_NAME}"] = tar_bytes
    # The legacy entry points stay available for ;log runme and KUAL.
    make_zip(full, full_files)
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as archive:
        assert all(member.isfile() and not member.issym() and not member.islnk() for member in archive)
        assert set(archive.getnames()) == set(payload_files)
        for name, raw in payload_files.items():
            assert archive.extractfile(name).read() == raw
    return {"variant": variant, "simple": str(simple), "simple_sha256": sha(simple.read_bytes()), "full": str(full), "full_sha256": sha(full.read_bytes()), "payload_size": len(tar_bytes), "payload_cksum": cksum, "payload_sha256": sha(tar_bytes), "payload_files": len(payload_files)}


def main() -> None:
    DIST.mkdir(exist_ok=True)
    results = [build(variant) for variant in ("standard", "ks")]
    (DIST / "V4-SHA256SUMS.txt").write_text("".join(f"{item[key]}  {Path(item[path_key]).name}\n" for item in results for key, path_key in (("simple_sha256", "simple"), ("full_sha256", "full"))), encoding="ascii")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
