#!/bin/sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
BUILDER="$ROOT/native-reading-time-package/reading-insights-cache.awk"
TEMP_DIR="$(mktemp -d)"
TAB="$(printf '\t')"
trap 'rm -rf "$TEMP_DIR"' EXIT INT TERM HUP

run_builder() {
    input="$1"; output="$2"; mkdir -p "$output"
    : > "$output/summary"; : > "$output/months"; : > "$output/days"
    : > "$output/daybooks"; : > "$output/books"
    awk -F '\t' -v summary="$output/summary" -v months="$output/months" \
        -v days="$output/days" -v daybooks="$output/daybooks" \
        -v books="$output/books" -f "$BUILDER" "$input"
}

printf 'date\tid\tseconds\ttitle\n2024-02-29\tBOOK1\t60\t0123456789ABCDEF\n2024-02-29\tBOOK1\t120\t正常书名\n2026-09-03\tunknown\t30\t甲书\n2026-09-03\tunknown\t40\t乙书\n2026-09-04\tBOOK2\t0\t零时长书\n2026-09-04\tBOOK3\t0\t这是一个用于验证完整保留的很长中文书名\n2026-09-04\tBOOK4\t0\t第四本\n2026-09-04\tBOOK5\t0\t第五本\n2026-09-04\tBOOK6\t0\t第六本\n2026-09-04\tBOOK7\t0\t第七本\n2026-09-04\tBOOK8\t0\t第八本\n' > "$TEMP_DIR/input.tsv"
run_builder "$TEMP_DIR/input.tsv" "$TEMP_DIR/full"

[ "$(cat "$TEMP_DIR/full/summary")" = "250${TAB}2" ]
grep -F "180${TAB}正常书名${TAB}BOOK1" "$TEMP_DIR/full/books" >/dev/null
[ "$(grep -c 'unknown' "$TEMP_DIR/full/books")" -eq 2 ]
grep -F "2024-02${TAB}180" "$TEMP_DIR/full/months" >/dev/null
grep -F "2026-09${TAB}70" "$TEMP_DIR/full/months" >/dev/null
grep -F "2024-02-29${TAB}180" "$TEMP_DIR/full/days" >/dev/null
grep -F '这是一个用于验证完整保留的很长中文书名' "$TEMP_DIR/full/books" >/dev/null
[ "$(awk 'NF{n++}END{print n+0}' "$TEMP_DIR/full/books")" -ge 8 ]

printf 'date\tid\tseconds\ttitle\n' > "$TEMP_DIR/empty.tsv"
run_builder "$TEMP_DIR/empty.tsv" "$TEMP_DIR/empty"
[ "$(cat "$TEMP_DIR/empty/summary")" = "0${TAB}0" ]
[ ! -s "$TEMP_DIR/empty/books" ]

echo "cache builder tests passed"
