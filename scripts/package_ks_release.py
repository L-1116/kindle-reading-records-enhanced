"""Build and verify the standalone Kindle Scribe test package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
STANDARD = ROOT / "native-reading-time-package"
KS = ROOT / "ks-package"
DIST = ROOT / "dist"
VERSION = "v9.7.5-KS-touch-compat-hotfix"
ARCHIVE = DIST / f"ReadingTime-{VERSION}.zip"
MANIFEST = "PACKAGE-MANIFEST-KS.json"


def files_under(root: Path, prefix: str) -> dict[str, Path]:
    return {f"{prefix}/{path.relative_to(root).as_posix()}": path for path in root.rglob("*") if path.is_file()}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_map() -> dict[str, Path]:
    sources: dict[str, Path] = {
        "RUNME.sh": KS / "RUNME.sh",
        "README.txt": KS / "README.txt",
        **files_under(KS / "documents", "documents"),
        **files_under(KS / "extensions", "extensions"),
    }
    common_files = [
        "Install-Native-Reading-Time.sh", "native-reading-time-daemon.sh", "native-reading-time.conf",
        "阅读记录.sh", "reading-insights-touch.lua", "reading-insights-render.lua",
        "reading-insights-cache.awk", "reading-insights-cover.lua", "reading-insights-titles.lua",
        "reading-insights-title-widths.lua", "NotoSansCJKsc-Regular.otf", "FONT-LICENSE.txt",
        "launcher-icon.png", "uninstall.sh", "cleanup-manifest.txt",
        "compat/detect_env.sh",
        "resources/reading-records-uninstall.sh", "resources/kual/reading-records-installer/config.xml",
    ]
    for relative in common_files:
        sources[f"native-reading-time-package/{relative}"] = STANDARD / relative
    for folder in ("ui", "render-assets"):
        sources.update(files_under(STANDARD / folder, f"native-reading-time-package/{folder}"))
    sources.update(files_under(KS / "native-reading-time-package", "native-reading-time-package"))
    # KUAL must route to the KS installer and force-exit helper, not the standard package.
    sources["native-reading-time-package/resources/kual/reading-records-installer/bin/action.sh"] = KS / "extensions/reading-records-installer/bin/action.sh"
    sources["native-reading-time-package/resources/kual/reading-records-installer/menu.json"] = KS / "extensions/reading-records-installer/menu.json"
    return sources


def main() -> None:
    sources = source_map()
    missing = [name for name, path in sources.items() if not path.is_file()]
    assert not missing, missing
    required = {
        "RUNME.sh", "README.txt", "documents/reading-records-ks-install.sh",
        "documents/reading-records-ks-force-exit.sh", "native-reading-time-package/install.sh",
        "native-reading-time-package/Install-Native-Reading-Time-KS.sh",
        "native-reading-time-package/阅读记录-ks.sh",
        "native-reading-time-package/reading-insights-touch-ks.lua",
        "native-reading-time-package/reading-insights-touch-probe-ks.lua",
        "native-reading-time-package/force-exit-ks.sh",
        "native-reading-time-package/ui-scribe/daily.png",
    }
    assert required <= sources.keys(), sorted(required - sources.keys())
    assert "native-reading-time-package/Install-Native-Reading-Time-Optimized.sh" not in sources

    payload = []
    for name, path in sorted(sources.items()):
        raw = path.read_bytes()
        executable = name.endswith(".sh")
        payload.append({"path": name, "size": len(raw), "sha256": sha256(raw), "executable": executable})
    manifest_bytes = (json.dumps({"format": 1, "variant": "kindle-scribe", "version": VERSION, "files": payload}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    DIST.mkdir(exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for item in payload + [{"path": MANIFEST, "executable": False}]:
            name = item["path"]
            raw = manifest_bytes if name == MANIFEST else sources[name].read_bytes()
            entry = zipfile.ZipInfo(name, date_time=(2026, 9, 28, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = ((0o100755 if item["executable"] else 0o100644) << 16)
            package.writestr(entry, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    with zipfile.ZipFile(ARCHIVE) as package:
        assert package.testzip() is None
        assert set(package.namelist()) == set(sources) | {MANIFEST}
        for item in payload:
            raw = package.read(item["path"])
            assert len(raw) == item["size"] and sha256(raw) == item["sha256"], item["path"]
            mode = (package.getinfo(item["path"]).external_attr >> 16) & 0o777
            assert mode == (0o755 if item["executable"] else 0o644), item["path"]

    digest = sha256(ARCHIVE.read_bytes())
    (DIST / "SHA256SUMS-KS.txt").write_text(f"{digest}  {ARCHIVE.name}\n", encoding="ascii")
    (DIST / f"ReadingTime-{VERSION}.manifest.json").write_bytes(manifest_bytes)
    print(json.dumps({"result": "PASS", "archive": str(ARCHIVE), "files": len(payload) + 1, "sha256": digest}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
