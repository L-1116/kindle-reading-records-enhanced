"""Run the complete offline validation suite in a stable order."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
CHECKS = [
    ROOT / "tests/validate_ui.py",
    ROOT / "tests/validate_stats_filters.py",
    ROOT / "tests/validate_day_detail.py",
    ROOT / "tests/validate_period_details.py",
    ROOT / "tests/validate_book_detail.py",
    ROOT / "tests/validate_install.py",
    ROOT / "scripts/package_release.py",
]


def main() -> None:
    for check in CHECKS:
        print(f"\n==> {check.relative_to(ROOT)}", flush=True)
        subprocess.run([sys.executable, str(check)], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
