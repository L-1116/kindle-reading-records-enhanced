"""Check production resolver identity, order, locking and waveform failures."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from validate_runtime_probe import ROOT, OUT, SH, executable, shell_path


def run(source: str, root: Path, **env: str) -> subprocess.CompletedProcess:
    script = root / "run.sh"
    script.write_text(source, encoding="utf-8", newline="\n")
    return subprocess.run([SH, script.as_posix()], env={**os.environ, "PATH": "/usr/bin:/bin:" + os.environ.get("PATH", ""), **env},
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=12)


if __name__ == "__main__":
    launchers = [(ROOT / path).read_text(encoding="utf-8") for path in (
        "native-reading-time-package/launch.sh", "ks-package/native-reading-time-package/launch-ks.sh")]
    viewers = [(ROOT / path).read_text(encoding="utf-8") for path in (
        "native-reading-time-package/阅读记录-optimized.sh", "ks-package/native-reading-time-package/阅读记录-ks.sh",
        "native-reading-time-package/阅读记录.sh")]
    resolver = launchers[0].split("READING_FBINK_CANDIDATES=\n", 1)[1].split("\nfbink_candidate_add \"${READING_FBINK:-}\"", 1)[0]
    assert resolver == launchers[1].split("READING_FBINK_CANDIDATES=\n", 1)[1].split("\nfbink_candidate_add \"${READING_FBINK:-}\"", 1)[0]
    wrappers = [s[s.index("# Candidate resolution"):s.index("\not() {", s.index("# Candidate resolution"))] for s in viewers]
    assert len(set(wrappers)) == 1, "all framebuffer entry points must share the safety contract"
    for s in launchers:
        assert "probe_fbink" not in s and 'probe_process "$probe_candidate" -e\n' not in s
        assert '"$SELECTED_FBINK"' not in s
    with tempfile.TemporaryDirectory(prefix="fbink-resolver-", dir=OUT) as name:
        root = Path(name)
        a, b, copied, linked = [root / x for x in ("A", "B", "copy-A", "hardlink-A")]
        executable(a, 'echo "A $*" >> "$TRACE"\ncase "$*" in *GC16_FAST*) exit 6;; esac\nexit 0\n')
        executable(b, 'echo "B $*" >> "$TRACE"\nexit 0\n')
        shutil.copy2(a, copied)
        os.link(a, linked)
        prelude = 'READING_FBINK_CANDIDATES=\n' + resolver + "\n"
        additions = "\n".join(f'fbink_candidate_add "{shell_path(p)}"' for p in (a, b, copied, linked, a))
        for disable in ("", "realpath() { return 1; }; readlink() { return 1; }; stat() { return 1; };\n", "realpath() { return 1; }; readlink() { return 1; }; stat() { return 1; }; cksum() { return 1; };\n"):
            result = run(disable + prelude + additions + '\nprintf "FINAL=%s\\n" "$READING_FBINK_CANDIDATES"\n', root)
            assert result.returncode == 0 and result.stdout.count("duplicate_of=") == 3, result
            assert result.stdout.split("FINAL=", 1)[1].strip().splitlines() == [shell_path(a), shell_path(b)], result
        # Ordering must preserve both historical preferences and ABI fallback.
        block = launchers[0][launchers[0].index('fbink_candidate_add "${READING_FBINK:-}"'):launchers[0].index("\nexport READING_FBINK_CANDIDATES")]
        paths = [root / x for x in ("user", "kmc", "libkh", "armhf", "armel", "path")]
        for i, p in enumerate(paths):
            executable(p, f"# distinct candidate {i}\nexit 0\n")
        replacements = {"/var/local/kmc/bin/fbink": paths[1], "/mnt/us/libkh/bin/fbink": paths[2],
                        "/var/local/kmc/armhf/bin/fbink": paths[3], "/var/local/kmc/armel/bin/fbink": paths[4]}
        for old, p in replacements.items():
            block = block.replace(old, shell_path(p))
        block = block.replace('"$(command -v fbink 2>/dev/null || true)"', f'"{shell_path(paths[5])}"')
        for hf in ("0", "1"):
            result = run(f'HARD_FLOAT={hf}\nREADING_FBINK="{shell_path(paths[0])}"\n' + prelude + block + '\nprintf "FINAL=%s\\n" "$READING_FBINK_CANDIDATES"\n', root)
            assert result.stdout.split("FINAL=", 1)[1].strip().splitlines() == [shell_path(paths[i]) for i in (0, 1, 2, 3 if hf == "1" else 4, 5)]
        trace = root / "calls"
        source = f'FBINK="{shell_path(a)}"\nREADING_FBINK_CANDIDATES="{shell_path(a)}\n{shell_path(b)}"\nfbink_calls=0\n' + wrappers[0] + '\ntrap fbink_stop_child EXIT\n'
        result = run(source + 'fb -q -b -B WHITE -k top=0\nfb -q -W GC16_FAST -s || fb -q -W GC16 -s\n', root, TRACE=trace.as_posix())
        assert result.returncode == 0 and "fbink_waveform_fallback=GC16" in result.stdout
        assert trace.read_text().splitlines() == ['A -q -b -B WHITE -k top=0', 'A -q -W GC16_FAST -s', 'A -q -W GC16 -s']
        # Locked runtime failures must exit, not trigger another traversal.
        for rc in (6, 139, 127):
            executable(a, f'echo "A $*" >> "$TRACE"\n[ "$1" != -q ] || exit 0\nexit {rc}\n')
            trace.write_text("")
            result = run(source + 'fb -q -b -B WHITE -k top=0\nfb -B BLACK -k top=10\necho SHOULD_NOT_RUN\n', root, TRACE=trace.as_posix())
            assert result.returncode == 31 and "SHOULD_NOT_RUN" not in result.stdout
            assert "fbink_runtime_failure=1" in result.stdout and f"fbink_exit_code={rc}" in result.stdout
            assert len(trace.read_text().splitlines()) == 2 and not any(c.startswith("B ") for c in trace.read_text().splitlines())
        # Exercise a real SIGSEGV child, as well as a simulated exit 139.
        executable(a, 'ulimit -c 0 2>/dev/null || true\necho "A $*" >> "$TRACE"\nkill -SEGV "$$"\n')
        trace.write_text("")
        result = run(source + 'fb -q -b -B WHITE -k top=0\nfb -q -W GC16 -s\n', root, TRACE=trace.as_posix())
        assert result.returncode == 0 and "exit_code=139" in result.stdout
        assert f"selected_fbink={shell_path(b)}" in result.stdout
        assert trace.read_text().splitlines() == ['A -q -b -B WHITE -k top=0', 'B -q -b -B WHITE -k top=0', 'B -q -W GC16 -s']
    print("FBInk resolver: PASS (content/hardlink/path dedup; optional identity tools absent; ABI order; lock; GC16 fallback; locked failures)")
