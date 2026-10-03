"""Offline KS evdev discovery, ABI framing, mapping and failure checks."""
from __future__ import annotations

import os
from pathlib import Path
import struct
import tempfile

from lupa import LuaRuntime, LuaError


ROOT = Path(__file__).resolve().parents[1]
PROBE = (ROOT / "ks-package/native-reading-time-package/reading-insights-touch-probe-ks.lua").read_text(encoding="utf-8")
READER = (ROOT / "ks-package/native-reading-time-package/reading-insights-touch-ks.lua").read_text(encoding="utf-8")


def execute(source: str, args: list[str], *, listing: Path | None = None) -> str:
    lua = LuaRuntime()
    if listing:
        args = [*args, listing.as_posix()]
    lua.globals().arg = lua.table_from({i + 1: value for i, value in enumerate(args)})
    lua.execute('os.exit=function(code) error("TEST_EXIT:" .. tostring(code)) end')
    try:
        lua.execute(source)
    except LuaError as exc:
        return str(exc)
    return "success"


def candidate(root: Path, number: int, name: str, ev: str, abs_cap: str, prop: str = "0") -> Path:
    node = root / "sys" / f"event{number}" / "device"
    (node / "capabilities").mkdir(parents=True)
    (node / "name").write_text(name)
    (node / "capabilities/ev").write_text(ev)
    (node / "capabilities/abs").write_text(abs_cap)
    (node / "properties").write_text(prop)
    path = root / "dev" / f"event{number}"
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(b"")
    return path


def event(size: int, typ: int, code: int, value: int) -> bytes:
    return bytes(8 if size == 16 else 16) + struct.pack("<HHi", typ, code, value)


def reader_case(root: Path, label: str, *, size: int = 16, codes=(53, 54),
                raw=(100, 100), bounds=("unknown",) * 4,
                screen=(1860, 2480), hint="auto", short=False) -> str:
    device = root / (label + ".events")
    payload = b"" if short else b"".join((event(size, 3, codes[0], raw[0]),
                                           event(size, 3, codes[1], raw[1]), event(size, 0, 0, 0)))
    device.write_bytes(payload)
    report = root / (label + ".log")
    report.write_text("selected_touch=test\nevent_struct_size=" + str(size) + "\n")
    args = [device.as_posix(), (root / "debug.log").as_posix(), "daily", "0", "31",
            "0", "0", str(screen[0]), str(screen[1]), "1", "1", "2000", "week", "7d",
            hint, str(size), str(screen[0]), str(screen[1]), report.as_posix(), *map(str, bounds)]
    result = execute(READER, args)
    log = report.read_text()
    if short:
        assert "TEST_EXIT:2" in result and "reader_error=short_read" in log, (label, result, log)
    elif label == "outside":
        assert "TEST_EXIT:2" in result and "last_action=ignore_outside" in log
    else:
        assert "TEST_EXIT:0" in result, (label, result, log)
    return log


with tempfile.TemporaryDirectory(prefix="ks-touch-") as directory:
    root = Path(directory)
    sys = root / "sys"
    sys.mkdir()
    stylus = candidate(root, 0, "WacomDigitizer", "b", "f000003", "2")
    accel = candidate(root, 1, "bma4xy_acc", "9", "1000007")
    finger = candidate(root, 4, "pt_mt", "f", "ee18000 0", "2")
    listing = root / "events.txt"
    listing.write_text("event0\nevent1\nevent4\n", newline="\n")
    os.environ.update(READING_INPUT_SYSFS=sys.as_posix(), READING_INPUT_DEV=(root / "dev").as_posix(),
                      READING_EVENT_STRUCT_SIZE="16", READING_TOUCH_FIRMWARE="5.19.6")
    result = execute(PROBE, [root.as_posix()], listing=listing)
    log = (root / "touch-last.log").read_text()
    assert result == "success" and f"selected_touch={finger.as_posix()}" in log, (result, log)
    assert "candidate_0_classification=pen_digitizer" in log
    assert "candidate_1_classification=sensor_or_button" in log
    assert "candidate_2_classification=finger_mt" in log
    for elf_class, expected in ((1, "16"), (2, "24")):
        binary = root / f"lua-elf-{elf_class}"
        binary.write_bytes(b"\x7fELF" + bytes((elf_class, 1)))
        del os.environ["READING_EVENT_STRUCT_SIZE"]
        os.environ["READING_LUA_BINARY"] = binary.as_posix()
        assert execute(PROBE, [root.as_posix()], listing=listing) == "success"
        assert f"event_struct_size={expected}" in (root / "touch-last.log").read_text()
        os.environ["READING_EVENT_STRUCT_SIZE"] = "16"
    del os.environ["READING_LUA_BINARY"]
    os.environ.update(READING_TOUCH_ABS_X_MIN="0", READING_TOUCH_ABS_X_MAX="5559",
                      READING_TOUCH_ABS_Y_MIN="0", READING_TOUCH_ABS_Y_MAX="7439")
    assert execute(PROBE, [root.as_posix()], listing=listing) == "success"
    assert "coordinate_mode=normalized_configured_range" in (root / "touch-last.log").read_text()
    for key in ("READING_TOUCH_ABS_X_MIN", "READING_TOUCH_ABS_X_MAX",
                "READING_TOUCH_ABS_Y_MIN", "READING_TOUCH_ABS_Y_MAX"):
        del os.environ[key]
    os.environ["READING_TOUCH_DEVICE"] = accel.as_posix()
    result = execute(PROBE, [root.as_posix()], listing=listing)
    assert "TEST_EXIT:2" in result and "selection_reason=override_rejected" in (root / "touch-last.log").read_text()
    del os.environ["READING_TOUCH_DEVICE"]
    finger.unlink()
    result = execute(PROBE, [root.as_posix()], listing=listing)
    assert "TEST_EXIT:2" in result and "selected_touch=none" in (root / "touch-last.log").read_text()
    print("A/B/C/M capability based discovery and no event1 fallback: PASS")

    for size in (16, 24):
        log = reader_case(root, f"mt-{size}", size=size, raw=(100, 100))
        assert "last_action=exit" in log and f"event_struct_size={size}" in log, log
    log = reader_case(root, "legacy-xy", codes=(0, 1))
    assert "last_action=exit" in log
    print("D/E/F/G 16/24 byte records and MT/ABS coordinates: PASS")

    log = reader_case(root, "swapped", screen=(1860, 2480), raw=(2400, 100), hint="swap")
    assert "last_action=exit" in log and "last_transform=swap" in log
    log = reader_case(root, "scaled", raw=(300, 400), bounds=(0, 5559, 0, 7439))
    assert "last_action=exit" in log
    log = reader_case(root, "outside", raw=(50000, 50000))
    assert "last_action=ignore_outside" in log
    print("H/I/J/K swap, pixel range, raw range and ignored outside touch: PASS")

    reader_case(root, "short", short=True)
    corrupt = root / "corrupt.events"
    corrupt.write_bytes(event(16, 255, 0, 0) * 16)
    corrupt_log = root / "corrupt.log"
    corrupt_log.write_text("selected_touch=test\n")
    corrupt_args = [corrupt.as_posix(), (root / "debug.log").as_posix(), "daily", "0", "31",
                    "0", "0", "1860", "2480", "1", "1", "2000", "week", "7d", "auto",
                    "16", "1860", "2480", corrupt_log.as_posix()]
    assert "TEST_EXIT:2" in execute(READER, corrupt_args)
    assert "reader_error=corrupt_event_stream" in corrupt_log.read_text()
    print("L short read fails with diagnostic: PASS")
    assert "sleep" not in READER and "timeout" not in READER
    print("N waiting has no idle countdown: PASS")
