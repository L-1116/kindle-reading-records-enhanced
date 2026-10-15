"""Compare frozen runtime payloads with checkpoint 982ea713."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import zipfile


from build_v4 import SIMPLE_ARCHIVE
ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = "982ea7131c81a198997315602a79c684bb4f3d7d"
EXCLUDED = {
    "native-reading-time-package/install.sh",
    "native-reading-time-package/Install-Native-Reading-Time.sh",
    "native-reading-time-package/Install-Native-Reading-Time-Optimized.sh",
    "ks-package/native-reading-time-package/install.sh",
    "ks-package/native-reading-time-package/Install-Native-Reading-Time-KS.sh",
    "native-reading-time-package/resources/kual/reading-records-installer/bin/action.sh",
}
ALLOWED_CHANGED = {
    "native-reading-time-package/native-reading-time-daemon.sh",
    "native-reading-time-package/reading-insights-touch-probe.lua",
    "native-reading-time-package/阅读记录-entry.sh",
    "native-reading-time-package/diagnostics.sh",
    "ks-package/native-reading-time-package/diagnostics-ks.sh",
    "native-reading-time-package/compat/detect_env.sh",
    "native-reading-time-package/阅读记录.sh",
    "native-reading-time-package/阅读记录-optimized.sh",
    "native-reading-time-package/reading-insights-touch-ui.lua",
    "ks-package/native-reading-time-package/阅读记录-ks.sh",
    "native-reading-time-package/launch.sh",
    "ks-package/native-reading-time-package/launch-ks.sh",
    "ks-package/native-reading-time-package/force-exit-ks.sh",
}
BOOT_TAR = "阅读记录安装数据.tar"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    names = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", CHECKPOINT, "--", "native-reading-time-package", "ks-package/native-reading-time-package"], cwd=ROOT).decode().splitlines()
    runtime = [name for name in names if name not in EXCLUDED and (name.endswith((".sh", ".lua", ".awk", ".png", ".pgm", ".tsv", ".otf", ".conf")) or "/ui" in name or "/render-assets/" in name)]
    changed = []
    allowed_changed = []
    hashes = {}
    for name in runtime:
        baseline = subprocess.check_output(["git", "show", f"{CHECKPOINT}:{name}"], cwd=ROOT)
        current = (ROOT / name).read_bytes()
        hashes[name] = sha(current) if name in ALLOWED_CHANGED else sha(baseline)
        if current != baseline:
            entry = {"file": name, "checkpoint_sha256": sha(baseline), "current_sha256": sha(current)}
            (allowed_changed if name in ALLOWED_CHANGED else changed).append(entry)
    packaged = {}
    for variant, archive_name in (("standard", SIMPLE_ARCHIVE.name),):
        with zipfile.ZipFile(SIMPLE_ARCHIVE) as outer:
            tar_bytes = outer.read(BOOT_TAR)
        with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as archive:
            names_in_tar = set(archive.getnames())
            mismatches = []
            checked = 0
            for name in runtime:
                if variant == "standard" and name.startswith("native-reading-time-package/"):
                    member = name
                elif variant == "ks" and name.startswith("ks-package/native-reading-time-package/"):
                    member = name.removeprefix("ks-package/")
                elif variant == "ks" and name.startswith("native-reading-time-package/"):
                    member = name
                else:
                    continue
                if member not in names_in_tar:
                    if name in ALLOWED_CHANGED and ((variant == "standard" and name.startswith("native-reading-time-package/")) or (variant == "ks" and name.startswith("ks-package/"))):
                        mismatches.append(f"missing: {name}")
                    continue
                checked += 1
                expected_hash = hashes[name]
                if variant == "ks" and name == "native-reading-time-package/阅读记录.sh":
                    expected_hash = sha((ROOT / "ks-package/native-reading-time-package/阅读记录.sh").read_bytes())
                if sha(archive.extractfile(member).read()) != expected_hash:
                    mismatches.append(name)
            packaged[variant] = {"checked_files": checked, "mismatches": mismatches}
    report = {"checkpoint": CHECKPOINT, "checked_files": len(runtime), "allowed_changed": allowed_changed, "changed": changed, "packaged_runtime": packaged, "key_hashes": {name: digest for name, digest in hashes.items() if name.endswith(("阅读记录-optimized.sh", "阅读记录-ks.sh", "reading-insights-touch.lua", "reading-insights-touch-ks.lua", "reading-insights-touch-probe-ks.lua", "native-reading-time-daemon.sh", "reading-insights-cache.awk"))}}
    output = ROOT / "build/validation/v4-runtime-hashes.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if changed or any(value["mismatches"] for value in packaged.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
