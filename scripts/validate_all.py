"""Run the complete offline validation suite in a stable order."""

from pathlib import Path
import json
import shutil
import subprocess
import sys
import time
import argparse


ROOT = Path(__file__).resolve().parents[1]
CHECKS = [
    ROOT / "tests/validate_idle_pause.py",
    ROOT / "tests/validate_settings_ui.py",
    ROOT / "tests/validate_idle_guard.py",
    ROOT / "tests/validate_ui.py",
    ROOT / "tests/validate_standard_touch_compat.py",
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
    ROOT / "tests/validate_evidence_tools.py",
    ROOT / "tests/validate_service_recovery.py",
    ROOT / "tests/validate_install.py",
    ROOT / "tests/validate_uninstall.py",
    # Cleanup validates the current packaged resolver, not an earlier build.
    ROOT / "tests/validate_cleanup.py",
    ROOT / "scripts/audit_native.py",
    ROOT / "scripts/build_v4.py",
    ROOT / "tests/validate_v4.py",
    ROOT / "tests/validate_5201_install.py",
    ROOT / "tests/validate_device_variant.py",
    ROOT / "tests/validate_device_variant_permissions.py",
    ROOT / "scripts/check_v4_runtime.py",
    ROOT / "scripts/audit_v4_startup.py",
    ROOT / "scripts/verify_v4_artifacts.py",
    ROOT / "tests/validate_standard_migration_safety.py",
    ROOT / "tests/validate_startup_performance.py",
    ROOT / "tests/validate_launcher_state.py",
    ROOT / "tests/validate_cover_debug.sh",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retry-failed', action='store_true', help='Preserve prior attempts and rerun failed or newly added checks.')
    parser.add_argument('--recheck', action='append', default=[], help='Also rerun a named registered check after a relevant source change.')
    options = parser.parse_args()
    output = ROOT / "build/validation/stable-suite-results.json"
    previous = json.loads(output.read_text(encoding='utf-8')) if options.retry_failed and output.exists() else None
    registered = {check.relative_to(ROOT).as_posix(): check for check in CHECKS}
    if any(name not in registered for name in options.recheck): parser.error('recheck must name a registered check')
    old = {row['check']: row for row in previous['checks']} if previous else {}
    selected = [check for name, check in registered.items() if not previous or name not in old or old[name]['exit_code'] or name in options.recheck]
    if previous:
        archive = output.with_name(f'stable-suite-attempt-{time.time_ns()}.json')
        archive.write_text(json.dumps(previous, indent=2), encoding='utf-8')
    results = []
    for check in CHECKS:
        name = check.relative_to(ROOT).as_posix()
        if check not in selected:
            results.append(old[name]); continue
        print(f"\n==> {check.relative_to(ROOT)}", flush=True)
        started = time.monotonic()
        interpreter = sys.executable if check.suffix == ".py" else (shutil.which("sh") or r"C:\Program Files\Git\bin\sh.exe")
        result = subprocess.run([interpreter, str(check)], cwd=ROOT)
        row = {"check": name, "exit_code": result.returncode,
               "elapsed_seconds": round(time.monotonic() - started, 2)}
        if name in old: row['previous_attempt'] = old[name]
        results.append(row)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"result": "PASS" if all(x["exit_code"] == 0 for x in results) else "FAIL",
                                  "checks": results}, indent=2), encoding="utf-8")
    if any(x["exit_code"] for x in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
