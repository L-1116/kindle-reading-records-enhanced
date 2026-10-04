"""Run the complete offline validation suite in a stable order."""

from pathlib import Path
import subprocess
import json
import time
import sys


ROOT = Path(__file__).resolve().parents[1]
CHECKS = [
    ROOT / "tests/validate_ui.py",
    ROOT / "tests/validate_stats_filters.py",
    ROOT / "tests/validate_day_detail.py",
    ROOT / "tests/validate_period_details.py",
    ROOT / "tests/validate_book_detail.py",
    ROOT / "tests/validate_cover_fallbacks.py",
    ROOT / "scripts/package_release.py",
    ROOT / "tests/validate_normal_audit.py",
    ROOT / "tests/validate_install.py",
    ROOT / "tests/validate_normal_runtime.py",
    ROOT / "tests/validate_pre_hardware.py",
]


def main() -> None:
    out = ROOT / "build/validation"
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / "suite-results.json"
    summary_path.unlink(missing_ok=True)
    results = []
    for check in CHECKS:
        print(f"\n==> {check.relative_to(ROOT)}", flush=True)
        started = time.time()
        completed = subprocess.run([sys.executable, str(check)], cwd=ROOT)
        results.append({"script": str(check.relative_to(ROOT)), "result": "PASS" if completed.returncode == 0 else "FAIL", "seconds": round(time.time() - started, 2)})
        summary_path.write_text(json.dumps({"result": "PASS" if all(r["result"] == "PASS" for r in results) else "FAIL", "complete": len(results) == len(CHECKS), "stages": results}, indent=2), encoding="utf-8")
        if completed.returncode:
            raise subprocess.CalledProcessError(completed.returncode, completed.args)


if __name__ == "__main__":
    main()
