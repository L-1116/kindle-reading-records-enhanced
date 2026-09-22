"""Find real ELF payloads by magic bytes, including files inside ZIP archives."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/validation"
OUT.mkdir(parents=True, exist_ok=True)
SKIP_DIRS = {".git", "build", "dist", "__pycache__"}


def iter_files() -> list[Path]:
    result: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        result.append(path)
    return result


elf_entries: list[str] = []
archives_checked: list[str] = []
for path in iter_files():
    if path.read_bytes()[:4] == b"\x7fELF":
        elf_entries.append(path.relative_to(ROOT).as_posix())
    if path.suffix.lower() == ".zip":
        archives_checked.append(path.relative_to(ROOT).as_posix())
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if not info.is_dir():
                    with archive.open(info) as member:
                        if member.read(4) == b"\x7fELF":
                            elf_entries.append(f"{path.relative_to(ROOT).as_posix()}!{info.filename}")

tooling = {name: shutil.which(name) for name in ("file", "readelf")}
details: dict[str, dict[str, str]] = {}
for entry in elf_entries:
    if "!" in entry:
        continue
    absolute = ROOT / entry
    details[entry] = {}
    if tooling["file"]:
        details[entry]["file"] = subprocess.run([tooling["file"], str(absolute)], capture_output=True, text=True).stdout.strip()
    if tooling["readelf"]:
        for flag, label in (("-h", "header"), ("-A", "attributes"), ("-l", "program_headers"), ("-d", "dynamic")):
            result = subprocess.run([tooling["readelf"], flag, str(absolute)], capture_output=True, text=True)
            details[entry][label] = (result.stdout + result.stderr).strip()

result = {
    "result": "PASS",
    "elf_entries": elf_entries,
    "elf_count": len(elf_entries),
    "archives_checked": archives_checked,
    "host_tools": tooling,
    "details": details,
    "conclusion": "No project-shipped ELF/native binary." if not elf_entries else "ELF entries require ABI review.",
}
(OUT / "native-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
if elf_entries and not (tooling["file"] and tooling["readelf"]):
    raise SystemExit("ELF found but host file/readelf tooling is incomplete")
