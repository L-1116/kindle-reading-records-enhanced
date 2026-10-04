"""Run the complete offline validation suite in a stable order."""

from pathlib import Path
import json
import shutil
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
CHECKS = [
    ROOT / "tests/validate_ui.py",
    ROOT / "tests/validate_stats_filters.py",
    ROOT / "tests/validate_day_detail.py",
    ROOT / "tests/validate_period_details.py",
    ROOT / "tests/validate_book_detail.py",
    ROOT / "tests/validate_cover_fallbacks.py",
    ROOT / "tests/validate_cover_regression.py",
    ROOT / "tests/validate_compat.py",
    ROOT / "tests/validate_runtime_probe.py",
    ROOT / "tests/validate_fbink_resolver.py",
    ROOT / "tests/validate_fbink_actual_use.py",
    ROOT / "tests/validate_startup_refresh.py",
    ROOT / "tests/validate_orientation_startup.py",
    ROOT / "tests/validate_install.py",
    ROOT / "tests/validate_uninstall.py",
    # Cleanup validates the current packaged resolver, not an earlier build.
    ROOT / "scripts/package_cover_v3_test.py",
    ROOT / "tests/validate_cleanup.py",
    ROOT / "scripts/audit_native.py",
    ROOT / "tests/validate_upgrade_matrix.py",
    ROOT / "scripts/package_release.py",
    ROOT / "scripts/package_ks_release.py",
    ROOT / "tests/validate_ks.py",
    ROOT / "tests/validate_ks_touch_compat.py",
    ROOT / "tests/validate_ks_compat_sync.py",
    ROOT / "tests/validate_ks_layout_flow.py",
    ROOT / "tests/validate_ks_renderer_contract.py",
    ROOT / "tests/validate_ks_install.py",
    ROOT / "scripts/build_v4.py",
    ROOT / "tests/validate_v4.py",
    ROOT / "scripts/check_v4_runtime.py",
    ROOT / "scripts/audit_v4_startup.py",
    ROOT / "scripts/verify_v4_artifacts.py",
    ROOT / "tests/validate_cover_debug.sh",
]


def main() -> None:
    results = []
    for check in CHECKS:
        print(f"\n==> {check.relative_to(ROOT)}", flush=True)
        started = time.monotonic()
        interpreter = sys.executable if check.suffix == ".py" else (shutil.which("sh") or r"C:\Program Files\Git\bin\sh.exe")
        result = subprocess.run([interpreter, str(check)], cwd=ROOT)
        results.append({"check": check.relative_to(ROOT).as_posix(), "exit_code": result.returncode,
                        "elapsed_seconds": round(time.monotonic() - started, 2)})
    output = ROOT / "build/validation/stable-suite-results.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"result": "PASS" if all(x["exit_code"] == 0 for x in results) else "FAIL",
                                  "checks": results}, indent=2), encoding="utf-8")
    if any(x["exit_code"] for x in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
