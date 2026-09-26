"""Build and byte-verify the self-contained Compatibility V3 release ZIP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
VALIDATION = ROOT / "build/validation"
VERSION = "v9.7.5-compat-v3"
ARCHIVE = DIST / f"kindle-reading-records-{VERSION}.zip"
RESOLVER = "native-reading-time-package/阅读记录-optimized.sh"
MANIFEST = "PACKAGE-MANIFEST.json"
FILES = [
    ROOT / "RUNME.sh",
    ROOT / "README.txt",
    ROOT / "documents/reading-records-install.sh",
    ROOT / "documents/reading-records-uninstall.sh",
    *sorted(p for p in (ROOT / "extensions/reading-records-installer").rglob("*") if p.is_file()),
    *sorted(p for p in (ROOT / "native-reading-time-package").rglob("*") if p.is_file()),
]
CANONICAL_PAIRS = {
    "documents/reading-records-uninstall.sh": "native-reading-time-package/resources/reading-records-uninstall.sh",
    "extensions/reading-records-installer/bin/action.sh": "native-reading-time-package/resources/kual/reading-records-installer/bin/action.sh",
    "extensions/reading-records-installer/config.xml": "native-reading-time-package/resources/kual/reading-records-installer/config.xml",
    "extensions/reading-records-installer/menu.json": "native-reading-time-package/resources/kual/reading-records-installer/menu.json",
}
REQUIRED = {
    RESOLVER,
    "native-reading-time-package/cleanup-manifest.txt",
    "native-reading-time-package/uninstall.sh",
    "native-reading-time-package/reading-insights-cover.lua",
    "native-reading-time-package/launcher-icon.png",
    "documents/reading-records-install.sh",
    "documents/reading-records-uninstall.sh",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    for deployed, canonical in CANONICAL_PAIRS.items():
        assert (ROOT / deployed).read_bytes() == (ROOT / canonical).read_bytes(), deployed
    sources = {path.relative_to(ROOT).as_posix(): path for path in FILES}
    assert REQUIRED <= sources.keys(), sorted(REQUIRED - sources.keys())
    assert len(sources) == len(FILES)

    payload = []
    for name, path in sorted(sources.items()):
        raw = path.read_bytes()
        payload.append({
            "path": name,
            "size": len(raw),
            "sha256": sha256(raw),
            "executable": name.endswith(".sh"),
        })
    manifest_bytes = (json.dumps({"format": 1, "files": payload}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    DIST.mkdir(exist_ok=True)
    VALIDATION.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for item in payload + [{"path": MANIFEST, "executable": False}]:
            name = item["path"]
            raw = manifest_bytes if name == MANIFEST else sources[name].read_bytes()
            entry = zipfile.ZipInfo(name, date_time=(2026, 9, 26, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = ((0o100755 if item["executable"] else 0o100644) << 16)
            package.writestr(entry, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    with zipfile.ZipFile(ARCHIVE) as package:
        assert package.testzip() is None
        assert set(package.namelist()) == set(sources) | {MANIFEST}
        assert package.read(MANIFEST) == manifest_bytes
        for item in payload:
            name = item["path"]
            raw = package.read(name)
            assert raw == sources[name].read_bytes(), name
            assert len(raw) == item["size"] and sha256(raw) == item["sha256"], name
            assert ((package.getinfo(name).external_attr >> 16) & 0o777) == (0o755 if item["executable"] else 0o644), name
        packaged_resolver = package.read(RESOLVER)
    source_resolver = sources[RESOLVER].read_bytes()
    assert packaged_resolver == source_resolver
    assert "# Name: 安装文件清理" in sources["documents/reading-records-uninstall.sh"].read_text(encoding="utf-8")

    archive_hash = sha256(ARCHIVE.read_bytes())
    (DIST / "SHA256SUMS.txt").write_text(f"{archive_hash}  {ARCHIVE.name}\n", encoding="ascii")
    (DIST / f"kindle-reading-records-{VERSION}.manifest.json").write_bytes(manifest_bytes)
    result = {
        "result": "PASS",
        "archive": str(ARCHIVE),
        "archive_files": len(payload) + 1,
        "archive_sha256": archive_hash,
        "source_resolver_sha256": sha256(source_resolver),
        "packaged_resolver_sha256": sha256(packaged_resolver),
        "source_equals_package": source_resolver == packaged_resolver,
    }
    (VALIDATION / "package-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
