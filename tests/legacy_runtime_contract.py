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
    # Touch discovery is deliberately replaced; retain exact geometry/scaling.
    for begin, end in [(start, "\nfind_touch_device()"), ("scale_len()", "\ndetect_screen\n")]:
        assert before[before.index(begin):before.index(end)] == after[after.index(begin):after.index(end)], "legacy geometry/scaling changed"
    old_body = before[before.index("ot() {"):before.index("\n# Safety invariant:")]
    new_body = after[after.index("ot() {"):after.index("\n# Safety invariant:")]
    new_body = new_body.replace('    case "$mode" in settings*) settings_background="$SETTINGS_ASSETS/${mode}.png";; *) settings_background="$UI_DIR/${mode}.png";; esac\n', '')
    new_body = new_body.replace('file=$settings_background,', 'file=$UI_DIR/${mode}.png,').replace('    rr_settings_gear\n', '')
    new_body = new_body.replace('case "$mode" in settings*) rr_settings_draw;; total)', 'case "$mode" in total)')
    new_body = new_body.replace("fb -q", '"$FBINK" -q').replace("done || exit 31", "done")
    new_body = new_body.replace(
        '        if [ "$draw_count" -eq 1 ] && [ "${COMPAT_PROFILE:-default}" = fw518 ]; then "$FBINK" -q -W GC16 -s\n'
        '        else "$FBINK" -q -f -W GC16 -s; fi', '        "$FBINK" -q -f -W GC16 -s')
    assert old_body == new_body, "legacy statistics/layout/draw arguments changed"
    old_loop = before[before.index('mode="total"; view_year='):]
    new_loop = after[after.index('mode="total"; view_year='):]
    new_loop = new_loop.replace('    touch_pending=1\n', '')
    new_loop = new_loop.replace('        settings_*) rr_settings_action;;\n', '')
    # All action handling and statistics remain exact; only reader invocation
    # adds the preflight ABI/geometry and legacy hit-region selection.
    assert old_loop[:old_loop.index('    action=')] == new_loop[:new_loop.index('    lua "$TOUCH_READER"')]
    assert old_loop[old_loop.index('    echo "$(date): dashboard action='):] == new_loop[new_loop.index('    echo "$(date): dashboard action='):], "legacy action handling changed"
