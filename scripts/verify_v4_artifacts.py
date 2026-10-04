"""Verify the two user-facing V4 release candidates against current sources."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tarfile
import zipfile

from build_v4 import BOOT_NAME, TAR_NAME, posix_cksum, sources


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    results = []
    for variant, name in (("standard", "ReadingTime-V4.zip"), ("ks", "ReadingTime-V4-KS.zip")):
        path = ROOT / "dist" / name
        with zipfile.ZipFile(path) as archive:
            assert archive.namelist() == [BOOT_NAME, TAR_NAME]
            assert archive.testzip() is None
            bootstrap = archive.read(BOOT_NAME).decode("utf-8")
            assert "# Name: 安装阅读记录" in bootstrap
            assert BOOT_NAME.isascii() and len(BOOT_NAME) < 40
            assert "@VARIANT@" not in bootstrap and f"VARIANT='{variant}'" in bootstrap
            payload = archive.read(TAR_NAME)
        assert f"PAYLOAD_SIZE='{len(payload)}'" in bootstrap
        assert f"PAYLOAD_CKSUM='{posix_cksum(payload)}'" in bootstrap
        expected = sources(variant)
        with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
            assert set(archive.getnames()) == set(expected)
            for member in archive:
                assert member.isfile() and not member.issym() and not member.islnk()
                raw = archive.extractfile(member).read()
                assert raw == expected[member.name], member.name
                assert not raw.startswith(b"\x7fELF"), member.name
        results.append({"variant": variant, "archive": path.name, "size": path.stat().st_size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "top_level": [BOOT_NAME, TAR_NAME], "payload_files": len(expected),
                        "payload_sha256": hashlib.sha256(payload).hexdigest(),
                        "source_equals_package": True, "bundled_elf_count": 0, "result": "PASS"})
    output = ROOT / "build/validation/v4-stable-artifacts.json"
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
