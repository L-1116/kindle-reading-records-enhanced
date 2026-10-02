#!/usr/bin/env -S py -3
"""Use the actual Lua compositor in the existing offline KS shell simulator."""

from __future__ import annotations

from pathlib import Path
import csv
import runpy
import sys

from lupa.lua51 import LuaRuntime


def native_path(value: str) -> Path:
    # Git Bash passes Windows drive paths as /d/path/to/file.
    if len(value) > 3 and value[0] == "/" and value[2] == "/" and value[1].isalpha():
        return Path(f"{value[1].upper()}:{value[2:]}")
    return Path(value)


if Path(sys.argv[1]).name != "reading-insights-render.lua":
    runpy.run_path(str(Path(__file__).with_name("lua-fake")), run_name="__main__")
else:
    renderer = native_path(sys.argv[1])
    assets = native_path(sys.argv[2])
    arguments = [str(assets), *sys.argv[3:]]
    if arguments[1] != "--measure":
        spec = native_path(arguments[1])
        lines = []
        for line in spec.read_text(encoding="utf-8").splitlines():
            fields = line.split("\t")
            if fields[0] == "canvas":
                fields[4] = native_path(fields[4]).as_posix()
            lines.append("\t".join(fields))
        translated = spec.with_name("render-spec-native.tsv")
        translated.write_text("\n".join(lines) + "\n", encoding="utf-8")
        arguments[1] = translated.as_posix()
    lua = LuaRuntime()
    lua.globals().arg = lua.table_from({i: value for i, value in enumerate(arguments, 1)})
    try:
        lua.execute(renderer.read_text(encoding="utf-8"))
    except Exception:
        if arguments[1] != "--measure":
            glyphs = set()
            with (assets / "dynamic-glyphs.tsv").open(encoding="utf-8", newline="") as source:
                for row in csv.DictReader(source, delimiter="\t"):
                    glyphs.add((row["style"], int(row["size"]), chr(int(row["char"], 16))))
            for line in lines:
                fields = line.split("\t")
                if fields[0] in {"text", "textfit"}:
                    style, size, message = fields[2], int(fields[3]), fields[8]
                    for char in message:
                        if (style, size, char) not in glyphs:
                            print(f"SPEC MISSING: {style}{size} U+{ord(char):04X} {char!r} in {message!r}", file=sys.stderr)
                            break
        raise
