#!/bin/sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
TEMP="$(mktemp -d /tmp/cover-debug-test.XXXXXX)"
case "$TEMP" in /tmp/cover-debug-test.*) :;; *) exit 1;; esac
trap 'status=$?; if [ "$status" -ne 0 ] && [ -r "$TEMP/state/cover-debug.log" ]; then tail -n 90 "$TEMP/state/cover-debug.log"; fi; rm -rf "$TEMP"' EXIT
mkdir -p "$TEMP/bin" "$TEMP/state"
mkdir -p "$TEMP/state/releases/9.7.5-test/bin"
cp "$ROOT/native-reading-time-package/阅读记录-optimized.sh" "$TEMP/state/releases/9.7.5-test/bin/reading-records.sh"
cp "$ROOT/tests/fixtures/cover-debug/sqlite3" "$TEMP/bin/sqlite3"
chmod 755 "$TEMP/bin/sqlite3"
printf 'date\tbook_id\tseconds\ttitle\n2026-09-26\tNEWBOOK\t600\tTest Book\n' > "$TEMP/state/reading-time.tsv"
printf 'fixture\n' > "$TEMP/cc.db"
mkdir -p "$TEMP/system"
printf 'native thumbnail fixture\n' > "$TEMP/system/thumbnail_random.jpg"
for missing in 0 1; do
    MOCK_MISSING_LOCATION="$missing" MOCK_SECOND_THUMB="$TEMP/system/thumbnail_random.jpg" COVER_DEBUG_NATIVE_PREFIX="$TEMP/system" COVER_DEBUG_BASE="$TEMP/state" COVER_DEBUG_CC_DB="$TEMP/cc.db" PATH="$TEMP/bin:$PATH" /bin/sh "$ROOT/debug/cover-debug/cover-debug.sh"
    log="$TEMP/state/cover-debug.log"
    grep -F 'FIRST DIVERGENCE=none through native thumbnail resolution' "$log" >/dev/null
    grep -F "legacy_974_result=$TEMP/system/thumbnail_random.jpg" "$log" >/dev/null
    grep -F "current_native_result=$TEMP/system/thumbnail_random.jpg" "$log" >/dev/null
    grep -F 'current selector source=installed resolver function catalog_row_for_book()' "$log" >/dev/null
    grep -F 'legacy catalog row field count=4' "$log" >/dev/null
    grep -F 'current catalog row field count=6' "$log" >/dev/null
    grep -F 'FINAL RESULT=SUCCESS' "$log" >/dev/null
    if [ "$missing" -eq 1 ]; then
        grep -F 'COLUMN_MISSING: p_location' "$log" >/dev/null
        grep -F 'current catalog fallback entered=yes' "$log" >/dev/null
    fi
done
printf 'NEWBOOK\t%s\n' "$TEMP/system/thumbnail_random.jpg" > "$TEMP/state/book-cover-cache.tsv"
cp "$TEMP/state/book-cover-cache.tsv" "$TEMP/cache-before.tsv"
MOCK_SECOND_THUMB="$TEMP/system/thumbnail_random.jpg" COVER_DEBUG_NATIVE_PREFIX="$TEMP/system" COVER_DEBUG_BASE="$TEMP/state" COVER_DEBUG_CC_DB="$TEMP/cc.db" PATH="$TEMP/bin:$PATH" /bin/sh "$ROOT/debug/cover-debug/cover-debug.sh" --latest
grep -F 'cache exists=yes (ignored for both diagnostic paths)' "$TEMP/state/cover-debug.log" >/dev/null
grep -F 'FIRST DIVERGENCE=none through native thumbnail resolution' "$TEMP/state/cover-debug.log" >/dev/null
cmp "$TEMP/state/book-cover-cache.tsv" "$TEMP/cache-before.tsv"
rm -f "$TEMP/state/book-cover-cache.tsv"
mkdir -p "$TEMP/state/book-covers"
printf 'image fixture\n' > "$TEMP/state/book-covers/cover.jpg"
MOCK_FIRST_THUMB="$TEMP/state/book-covers/cover.jpg" MOCK_SECOND_THUMB="$TEMP/system/thumbnail_random.jpg" COVER_DEBUG_NATIVE_PREFIX="$TEMP/system" COVER_DEBUG_BASE="$TEMP/state" COVER_DEBUG_CC_DB="$TEMP/cc.db" PATH="$TEMP/bin:$PATH" /bin/sh "$ROOT/debug/cover-debug/cover-debug.sh"
grep -F 'write attempted=yes (temporary atomic-write probe' "$TEMP/state/cover-debug.log" >/dev/null
grep -F 'write success=yes' "$TEMP/state/cover-debug.log" >/dev/null
grep -F 'FINAL RESULT=SUCCESS' "$TEMP/state/cover-debug.log" >/dev/null
real_id=ED75D9F42E4042E4B0BFE2BF179ECE20
real_title='北平无战事(上下册)'
real_location="/mnt/us/documents/Downloads/Items01/北平无战事(上下册)_${real_id}.kfx"
printf 'date\tbook_id\tseconds\ttitle\n2026-09-26\t%s\t600\t%s\n' "$real_id" "$real_title" > "$TEMP/state/reading-time.tsv"
printf 'real problem thumbnail fixture\n' > "$TEMP/system/thumbnail_GvykvB.jpg"
MOCK_BOOK_ID="$real_id" MOCK_TITLE="$real_title" MOCK_LOCATION="$real_location" MOCK_SECOND_THUMB="$TEMP/system/thumbnail_GvykvB.jpg" COVER_DEBUG_NATIVE_PREFIX="$TEMP/system" COVER_DEBUG_BASE="$TEMP/state" COVER_DEBUG_CC_DB="$TEMP/cc.db" PATH="$TEMP/bin:$PATH" /bin/sh "$ROOT/debug/cover-debug/cover-debug.sh"
grep -F "raw_book_id=$real_id" "$TEMP/state/cover-debug.log" >/dev/null
grep -F "p_location=$real_location" "$TEMP/state/cover-debug.log" >/dev/null
grep -F "legacy_974_result=$TEMP/system/thumbnail_GvykvB.jpg" "$TEMP/state/cover-debug.log" >/dev/null
grep -F "current_native_result=$TEMP/system/thumbnail_GvykvB.jpg" "$TEMP/state/cover-debug.log" >/dev/null
grep -F 'FIRST DIVERGENCE=none through native thumbnail resolution' "$TEMP/state/cover-debug.log" >/dev/null
git show 'v9.7.5-test.1:native-reading-time-package/阅读记录-optimized.sh' > "$TEMP/state/releases/9.7.5-test/bin/reading-records.sh"
MOCK_BOOK_ID="$real_id" MOCK_TITLE="$real_title" MOCK_LOCATION="$real_location" MOCK_SECOND_THUMB="$TEMP/system/thumbnail_GvykvB.jpg" COVER_DEBUG_NATIVE_PREFIX="$TEMP/system" COVER_DEBUG_BASE="$TEMP/state" COVER_DEBUG_CC_DB="$TEMP/cc.db" PATH="$TEMP/bin:$PATH" /bin/sh "$ROOT/debug/cover-debug/cover-debug.sh"
grep -F 'installed resolver cksum=283094174 86282' "$TEMP/state/cover-debug.log" >/dev/null
grep -F 'FIRST DIVERGENCE=catalog row selection / p_thumbnail' "$TEMP/state/cover-debug.log" >/dev/null
grep -F 'current value=<empty>' "$TEMP/state/cover-debug.log" >/dev/null
test ! -e "$TEMP/state/book-cover-cache.tsv"
test ! -e "$TEMP/state/book-cover-misses.tsv"
printf '%s\n' 'cover-debug diagnostic replay: PASS'
