"""Save the historical startup audit and verify protected compatibility code."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tests"))
from idle_contract import assert_legacy_timing
from legacy_runtime_contract import assert_legacy_core


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/validation"
BASELINE = "982ea7131c81a198997315602a79c684bb4f3d7d"
EARLY = "a48d8c7910cdf5cabff11828663f4fb2f142c322"


def historical(commit: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)


def function(source: str, name: str) -> str:
    start = source.index(name + "() {")
    return source[start:source.index("\n}\n", start) + 3]


def main() -> None:
    history = []
    for commit in (EARLY, BASELINE, "88164e9", "0dc8c1b"):
        source = historical(commit, "native-reading-time-package/launch.sh").decode("utf-8")
        history.append({"commit": commit,
                        "fbink_init_gate": "probe_fbink()" in source,
                        "bounded_probe": "PROBE_MAX_TICKS" in source,
                        "native_recovery": "restore_native()" in source,
                        "unified_log": 'LOG="$BASE/launch-last.log"' in source,
                        "requires_loader_heuristic": "requires kindlehf/hard-float runtime" in source})
    assert history[0]["fbink_init_gate"] is False
    assert history[1]["fbink_init_gate"] is True
    for path, touch in (("native-reading-time-package/launch.sh", ["reading-insights-touch-probe.lua", "reading-insights-touch-ui.lua"]),):
        source = (ROOT / path).read_text(encoding="utf-8")
        sources = re.findall(r'"\$RELEASE/bin/([^"\n]+\.lua)"', function(source, "probe_lua"))
        sources = list(dict.fromkeys(sources))
        assert sources == touch + ["reading-insights-render.lua", "reading-insights-cover.lua", "reading-insights-titles.lua", "reading-insights-title-widths.lua"], (path, sources)
    protected_paths = [
        "native-reading-time-package/compat/detect_env.sh",
        "native-reading-time-package/native-reading-time-daemon.sh",
        "native-reading-time-package/native-reading-time.conf",
        "native-reading-time-package/reading-insights-cache.awk",
        "native-reading-time-package/reading-insights-touch.lua",
        "ks-package/native-reading-time-package/reading-insights-touch-ks.lua",
        "ks-package/native-reading-time-package/reading-insights-touch-probe-ks.lua",
        "ks-package/native-reading-time-package/force-exit-ks.sh",
    ]
    protected = []
    for path in protected_paths:
        baseline_commit = "0dc8c1b" if path.startswith("v4/") else BASELINE
        raw = (ROOT / path).read_bytes()
        baseline_raw = historical(baseline_commit, path)
        if path.endswith('/native-reading-time-daemon.sh'):
            assert_legacy_timing()
            protected.append({"path":path,"default_off_sampler_exact":True,"idle_pause_opt_in":True})
        elif path.endswith("/force-exit-ks.sh"):
            removed = (b'FBINK="${READING_FBINK:-}"\n'
                       b'[ -x "$FBINK" ] || FBINK=/var/local/kmc/bin/fbink\n'
                       b'[ -x "$FBINK" ] || FBINK=/mnt/us/libkh/bin/fbink\n'
                       b'[ -x "$FBINK" ] && "$FBINK" -q -f -W GC16 -s >/dev/null 2>&1 || true\n')
            assert baseline_raw.count(removed) == 1, path
            assert raw == baseline_raw.replace(removed, b""), path
            protected.append({"path": path, "baseline": baseline_commit, "sha256": hashlib.sha256(raw).hexdigest(),
                              "unchanged": False, "only_unchecked_fbink_refresh_removed": True})
        elif path.endswith('/compat/detect_env.sh'):
            expected = baseline_raw.decode('utf-8').replace('    [ -n "$FIRMWARE_FULL" ] || FIRMWARE_FULL="$(extract_firmware_version "$VERSION_RAW")"', '    FIRMWARE_SOURCE="$PRETTYVERSION_PATH"\n    if [ -z "$FIRMWARE_FULL" ]; then FIRMWARE_FULL="$(extract_firmware_version "$VERSION_RAW")"; FIRMWARE_SOURCE="$VERSION_PATH"; fi').replace('export FIRMWARE_FULL FIRMWARE_MAJOR', 'export FIRMWARE_SOURCE FIRMWARE_FULL FIRMWARE_MAJOR').encode()
            assert raw == expected, path
            protected.append({"path": path, "only_firmware_source_annotation": True})
        else:
            assert raw == baseline_raw, path
            protected.append({"path": path, "baseline": baseline_commit, "sha256": hashlib.sha256(raw).hexdigest(), "unchanged": True})
    refresh = []
    for path in ("native-reading-time-package/阅读记录-optimized.sh",):
        source = (ROOT / path).read_text(encoding="utf-8")
        assert function(source, "refresh_region") == function(historical(BASELINE, path).decode("utf-8"), "refresh_region")
        refresh.append({"path": path, "refresh_region_unchanged": True})
    # Legacy statistics, layout and argv are unchanged apart from checked FBInk
    # calls, propagation of pipeline errors and the family-wide first refresh.
    path = "native-reading-time-package/阅读记录.sh"
    assert_legacy_core()
    report = {"result": "PASS", "first_fbink_gate_commit": BASELINE, "history": history,
              "protected": protected, "refresh": refresh, "legacy_statistics_layout_argv_preserved": True,
              "recovery": "LIPC only; no FBInk invocation in launcher/UI cleanup or KS force-exit"}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "v4-startup-history-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
