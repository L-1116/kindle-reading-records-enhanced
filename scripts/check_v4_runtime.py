"""Compare frozen runtime payloads with checkpoint 982ea713."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import zipfile


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
BOOT_TAR = "阅读记录安装数据.tar"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    names = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", CHECKPOINT, "--", "native-reading-time-package", "ks-package/native-reading-time-package"], cwd=ROOT).decode().splitlines()
    runtime = [name for name in names if name not in EXCLUDED and (name.endswith((".sh", ".lua", ".awk", ".png", ".pgm", ".tsv", ".otf", ".conf")) or "/ui" in name or "/render-assets/" in name)]
    changed = []
    hashes = {}
    for name in runtime:
        baseline = subprocess.check_output(["git", "show", f"{CHECKPOINT}:{name}"], cwd=ROOT)
        current = (ROOT / name).read_bytes()
        hashes[name] = sha(baseline)
        if current != baseline:
            changed.append({"file": name, "checkpoint_sha256": sha(baseline), "current_sha256": sha(current)})
    packaged = {}
    for variant, archive_name in (("standard", "ReadingTime-V4-Test.zip"), ("ks", "ReadingTime-V4-KS-Test.zip")):
        with zipfile.ZipFile(ROOT / "dist" / archive_name) as outer:
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
                    continue
                checked += 1
                if sha(archive.extractfile(member).read()) != hashes[name]:
                    mismatches.append(name)
            packaged[variant] = {"checked_files": checked, "mismatches": mismatches}
    report = {"checkpoint": CHECKPOINT, "checked_files": len(runtime), "changed": changed, "packaged_runtime": packaged, "key_hashes": {name: digest for name, digest in hashes.items() if name.endswith(("阅读记录-optimized.sh", "阅读记录-ks.sh", "reading-insights-touch.lua", "reading-insights-touch-ks.lua", "reading-insights-touch-probe-ks.lua", "native-reading-time-daemon.sh", "reading-insights-cache.awk"))}}
    output = ROOT / "build/validation/v4-runtime-hashes.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if changed or any(value["mismatches"] for value in packaged.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
