"""Build a standalone diagnostic zip; never packages or installs a release."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parents[1]
TARGET = ROOT / "dist" / "reading-records-cover-debug-v3.zip"
FILES = {
    "cover-debug.sh": SOURCE / "cover-debug.sh",
    "documents/阅读记录封面诊断.sh": SOURCE / "documents/阅读记录封面诊断.sh",
    "extensions/reading-records-cover-debug/config.xml": SOURCE / "extensions/reading-records-cover-debug/config.xml",
    "extensions/reading-records-cover-debug/menu.json": SOURCE / "extensions/reading-records-cover-debug/menu.json",
    "extensions/reading-records-cover-debug/bin/action.sh": SOURCE / "extensions/reading-records-cover-debug/bin/action.sh",
    "COVER-DEBUG-README.txt": SOURCE / "README.txt",
}


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(TARGET, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for name, source in FILES.items():
            info = ZipInfo(name)
            info.compress_type = ZIP_DEFLATED
            info.external_attr = (0o755 if name.endswith(".sh") else 0o644) << 16
            archive.writestr(info, source.read_bytes())
    with ZipFile(TARGET) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(FILES)
    print(TARGET)


if __name__ == "__main__":
    main()
