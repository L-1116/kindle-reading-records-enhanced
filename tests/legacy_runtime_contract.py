"""Protect the legacy viewer's core while allowing its checked runtime calls."""
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def assert_legacy_core() -> None:
    before = subprocess.check_output([
        "git", "show", "982ea7131c81a198997315602a79c684bb4f3d7d:native-reading-time-package/阅读记录.sh"
    ], cwd=ROOT).decode("utf-8")
    after = (ROOT / "native-reading-time-package/阅读记录.sh").read_text(encoding="utf-8")
    start = "# Discover the visible framebuffer geometry."
    old_geometry = before[before.index(start):before.index("\not() {")]
    new_geometry = after[after.index(start):after.index("\n# The parent has already selected")]
    old_geometry = old_geometry.replace('[ -x "$FBINK" ] || fail "未找到 Véra/KPM 系统级 FBInk"\n', "")
    assert old_geometry == new_geometry, "legacy geometry/touch/resource checks changed"
    old_body = before[before.index("ot() {"):before.index("\n# Safety invariant:")]
    new_body = after[after.index("ot() {"):after.index("\n# Safety invariant:")]
    new_body = new_body.replace("fb -q", '"$FBINK" -q').replace("done || exit 31", "done")
    new_body = new_body.replace(
        '        if [ "$draw_count" -eq 1 ] && [ "${COMPAT_PROFILE:-default}" = fw518 ]; then "$FBINK" -q -W GC16 -s\n'
        '        else "$FBINK" -q -f -W GC16 -s; fi', '        "$FBINK" -q -f -W GC16 -s')
    assert old_body == new_body, "legacy statistics/layout/draw arguments changed"
    assert before[before.index('mode="total"; view_year='):] == after[after.index('mode="total"; view_year='):], "legacy interaction loop changed"
