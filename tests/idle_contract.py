"""Prove the default daemon path still contains the exact released sampler."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
def assert_legacy_timing():
    before=subprocess.check_output(['git','show','b46407c:native-reading-time-package/native-reading-time-daemon.sh'],cwd=ROOT).decode()
    after=(ROOT/'native-reading-time-package/native-reading-time-daemon.sh').read_text(encoding='utf-8')
    begin=after.index('IDLE_HELPERS='); end=after.index('mkdir -p "$BASE"',begin)
    after=after[:begin]+after[end:]
    after=after.replace('BASE="${READING_BASE:-/mnt/us/reading-time}"','BASE="/mnt/us/reading-time"')
    after=after.replace('cleanup() { idle_stop; flush;','cleanup() { flush;')
    after=after.replace('    if ! idle_dispatch; then\n','').replace('    fi # optional idle timing path\n\n','')
    assert after==before, 'Default-off foreground timing changed'
