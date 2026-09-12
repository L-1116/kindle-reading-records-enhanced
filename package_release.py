"""Build the installer hotfix archive and verify its contents against v9.7.1."""
from pathlib import Path
import hashlib
import json
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parent
TAG = "v9.7.1-day-detail"
PACKAGE_DIR = ROOT / "native-reading-time-package"
ARCHIVE = ROOT / "Kindle安装包-v9.7.1-install-fix.zip"
OUT = ROOT / "validation"

files = [ROOT / "RUNME.sh", *sorted(path for path in PACKAGE_DIR.rglob("*") if path.is_file())]
relative_names = [path.relative_to(ROOT).as_posix() for path in files]
assert {name.split("/", 1)[0] for name in relative_names} == {
    "RUNME.sh",
    "native-reading-time-package",
}

# The installer hotfix may change RUNME only. Every runtime payload byte must
# remain identical to the stable v9.7.1-day-detail tag.
tag_name_bytes = subprocess.run(
    [
        "git",
        "-c",
        "core.quotepath=false",
        "ls-tree",
        "-rz",
        "--name-only",
        TAG,
        "--",
        "native-reading-time-package",
    ],
    cwd=ROOT,
    check=True,
    capture_output=True,
).stdout
tag_names = [name.decode("utf-8") for name in tag_name_bytes.split(b"\0") if name]
package_names = [name for name in relative_names if name.startswith("native-reading-time-package/")]
assert set(package_names) == set(tag_names), (package_names, tag_names)
for name in package_names:
    tagged = subprocess.run(
        ["git", "show", f"{TAG}:{name}"], cwd=ROOT, check=True, capture_output=True
    ).stdout
    assert (ROOT / name).read_bytes() == tagged, f"payload changed from {TAG}: {name}"

with zipfile.ZipFile(ARCHIVE, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in files:
        archive.write(path, path.relative_to(ROOT).as_posix())

with zipfile.ZipFile(ARCHIVE) as archive:
    assert archive.testzip() is None
    assert archive.namelist() == relative_names
    assert {name.split("/", 1)[0] for name in archive.namelist()} == {
        "RUNME.sh",
        "native-reading-time-package",
    }
    for path in files:
        name = path.relative_to(ROOT).as_posix()
        assert archive.read(name) == path.read_bytes(), name

manifest = {
    path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in files
}
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "release-sha256.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
)
result = {
    "result": "PASS",
    "archive": ARCHIVE.name,
    "archive_files": len(files),
    "archive_bytes": ARCHIVE.stat().st_size,
    "sha256": hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
    "checks": [
        "ZIP contains only RUNME.sh and native-reading-time-package/ at its top level.",
        "Every ZIP entry matches its source byte-for-byte.",
        "Every native-reading-time-package payload file and byte matches v9.7.1-day-detail.",
    ],
}
(OUT / "package-results.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(result, ensure_ascii=False, indent=2))
