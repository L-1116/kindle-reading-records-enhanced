#!/bin/sh
# One-shot, diagnostic-only replay of v9.7.4 and the installed cover selector.
# Does not change the installed resolver, reading history, or cover mappings.
BASE="${COVER_DEBUG_BASE:-/mnt/us/reading-time}"
DATA="${COVER_DEBUG_DATA:-$BASE/reading-time.tsv}"
SELECT_MODE="${1:-uncached}"
CC_DB="${COVER_DEBUG_CC_DB:-/var/local/cc.db}"
LOG="${COVER_DEBUG_LOG:-$BASE/cover-debug.log}"
CACHE="$BASE/book-cover-cache.tsv"
MISS_CACHE="$BASE/book-cover-misses.tsv"
CACHE_DIR="$BASE/book-covers"
NATIVE_TEST_PREFIX="${COVER_DEBUG_NATIVE_PREFIX:-}"
HELPER="$BASE/releases/9.7.5-test/bin/reading-insights-cover.lua"
INSTALLED_RESOLVER="$BASE/releases/9.7.5-test/bin/reading-records.sh"
TMP="/tmp/reading-cover-debug.$$"
WRITE_PROBE="$BASE/.cover-debug-write.$$"
IMAGE_PROBE="$CACHE_DIR/.cover-debug-image.$$"
EXPECTED_RESOLVER_CKSUM='459377751 90742'
TAB="$(printf '\t')"
SQL_LEGACY="SELECT -1,replace(replace(COALESCE(p_titles_0_nominal,''),char(9),' '),char(10),' '),replace(replace(COALESCE(p_cdeKey,''),char(9),' '),char(10),' '),replace(replace(COALESCE(p_thumbnail,''),char(9),' '),char(10),' ') FROM Entries WHERE p_cdeKey IS NOT NULL ORDER BY p_lastAccess DESC;"
SQL_CURRENT="SELECT -1,replace(replace(COALESCE(p_titles_0_nominal,''),char(9),' '),char(10),' '),replace(replace(COALESCE(p_cdeKey,''),char(9),' '),char(10),' '),replace(replace(COALESCE(p_thumbnail,''),char(9),' '),char(10),' '),replace(replace(COALESCE(p_location,''),char(9),' '),char(10),' '),'' FROM Entries WHERE p_cdeKey IS NOT NULL OR p_location IS NOT NULL ORDER BY p_lastAccess DESC;"
SQL_COMPAT="SELECT -1,replace(replace(COALESCE(p_titles_0_nominal,''),char(9),' '),char(10),' '),replace(replace(COALESCE(p_cdeKey,''),char(9),' '),char(10),' '),replace(replace(COALESCE(p_thumbnail,''),char(9),' '),char(10),' '),'','' FROM Entries WHERE p_cdeKey IS NOT NULL ORDER BY p_lastAccess DESC;"

mkdir -p "$BASE" "$TMP" || exit 1
chmod 700 "$TMP" 2>/dev/null || true
touch "$LOG" || exit 1
chmod 600 "$LOG" 2>/dev/null || true
cleanup() { rm -f "$WRITE_PROBE" "$WRITE_PROBE.ready" "$IMAGE_PROBE" "$TMP"/*; rmdir "$TMP" 2>/dev/null || true; }
trap 'cleanup' EXIT
trap 'exit 130' HUP INT TERM
log() { printf '%s\n' "$*" >> "$LOG"; }
field() { printf '%s\n' "$1" | awk -F '\t' -v n="$2" '{print $n}'; }
native_cover() {
    case "$1" in /mnt/us/system/thumbnails/*|/mnt/us/system/bookcovers/*) [ -s "$1" ];;
        *) [ -n "$NATIVE_TEST_PREFIX" ] || return 1; case "$1" in "$NATIVE_TEST_PREFIX"/*) [ -s "$1" ];; *) return 1;; esac;;
    esac
}
current_cover() { native_cover "$1" && return 0; case "$1" in "$CACHE_DIR"/*) [ -s "$1" ];; *) return 1;; esac; }
book_allowed() { case "$1" in /mnt/us/documents/*.epub|/mnt/us/documents/*.EPUB|/mnt/us/documents/*.mobi|/mnt/us/documents/*.MOBI|/mnt/us/documents/*.pdf|/mnt/us/documents/*.PDF) [ -f "$1" ];; *) return 1;; esac; }
cache_lookup() { [ -r "$CACHE" ] && awk -F '\t' -v id="$1" '$1==id{print substr($0,index($0,"\t")+1);exit}' "$CACHE"; }
log_file() { if [ -s "$1" ]; then sed 's/^/  /' "$1" >> "$LOG"; else log '  <empty>'; fi; }
write_probe() {
    log "destination cache=$CACHE"
    log 'write attempted=yes (temporary atomic-write probe; persistent mapping untouched)'
    if { printf '%s\t%s\n' "$key" "$current_result" > "$WRITE_PROBE" && chmod 600 "$WRITE_PROBE" && mv "$WRITE_PROBE" "$WRITE_PROBE.ready"; } 2> "$TMP/write.err"; then
        log 'write success=yes'
        rm -f "$WRITE_PROBE.ready"
    else
        log 'write success=no'
        log 'cache write error='; log_file "$TMP/write.err"
    fi
}
command_result() {
    log "command=$1"
    log "exit code=$2"
    log 'stdout='; log_file "$TMP/command.stdout"
    log 'stderr='; log_file "$TMP/command.stderr"
}
extract_probe() {
    [ -r "$HELPER" ] || { log 'extraction result=helper unreadable'; return 1; }
    command -v lua >/dev/null 2>&1 || { log 'extraction result=lua missing'; return 1; }
    extract_out="$TMP/extracted-cover"
    case "$source" in
        *.epub|*.EPUB)
            command -v unzip >/dev/null 2>&1 || { log 'extraction result=unzip missing'; return 1; }
            unzip -p "$source" META-INF/container.xml > "$TMP/container.xml" 2> "$TMP/command.stderr"; rc=$?
            : > "$TMP/command.stdout"; command_result "unzip -p $source META-INF/container.xml > $TMP/container.xml" "$rc"
            [ "$rc" -eq 0 ] || return 1
            lua "$HELPER" epub-container "$TMP/container.xml" > "$TMP/command.stdout" 2> "$TMP/command.stderr"; rc=$?
            command_result "lua $HELPER epub-container $TMP/container.xml" "$rc"
            [ "$rc" -eq 0 ] || return 1
            opf_path="$(sed -n '1p' "$TMP/command.stdout")"
            [ -n "$opf_path" ] || return 1
            unzip -p "$source" "$opf_path" > "$TMP/package.opf" 2> "$TMP/command.stderr"; rc=$?
            : > "$TMP/command.stdout"; command_result "unzip -p $source $opf_path > $TMP/package.opf" "$rc"
            [ "$rc" -eq 0 ] || return 1
            lua "$HELPER" epub-opf "$opf_path" "$TMP/package.opf" > "$TMP/candidates.txt" 2> "$TMP/command.stderr"; rc=$?
            : > "$TMP/command.stdout"; command_result "lua $HELPER epub-opf $opf_path $TMP/package.opf > $TMP/candidates.txt" "$rc"
            [ "$rc" -eq 0 ] || return 1
            while IFS= read -r candidate; do
                [ -n "$candidate" ] || continue
                unzip -p "$source" "$candidate" > "$extract_out" 2> "$TMP/command.stderr"; rc=$?
                : > "$TMP/command.stdout"; command_result "unzip -p $source $candidate > $extract_out" "$rc"
                if [ "$rc" -eq 0 ] && [ -s "$extract_out" ] && lua "$HELPER" image-extension "$extract_out" > "$TMP/command.stdout" 2> "$TMP/command.stderr"; then
                    command_result "lua $HELPER image-extension $extract_out" 0
                    extracted_ext="$(sed -n '1p' "$TMP/command.stdout")"
                    return 0
                fi
                rm -f "$extract_out"
            done < "$TMP/candidates.txt"
            ;;
        *.mobi|*.MOBI)
            lua "$HELPER" mobi "$source" "$extract_out" > "$TMP/command.stdout" 2> "$TMP/command.stderr"; rc=$?
            command_result "lua $HELPER mobi $source $extract_out" "$rc"
            [ "$rc" -eq 0 ] && [ -s "$extract_out" ] || return 1
            lua "$HELPER" image-extension "$extract_out" > "$TMP/command.stdout" 2> "$TMP/command.stderr"; rc=$?
            command_result "lua $HELPER image-extension $extract_out" "$rc"
            if [ "$rc" -eq 0 ]; then extracted_ext="$(sed -n '1p' "$TMP/command.stdout")"; return 0; fi
            ;;
        *.pdf|*.PDF) log 'extraction result=PDF unsupported by current code';;
        *) log 'extraction result=unsupported book format by current code';;
    esac
    return 1
}
log_row() {
    label="$1"; row="$2"
    log "$label=$(printf '%s' "$row" | tr '\t' '|')"
    if [ -n "$row" ]; then
        printf '%s\n' "$row" | awk -F '\t' -v prefix="$label" '{print prefix " field count=" NF;for(i=1;i<=NF;i++)print prefix " field[" i "]=" $i}' >> "$LOG"
    else log "$label field count=0"; fi
}
sql_run() {
    sql_label="$1"; sql_text="$2"; sql_output="$3"
    log "cc.db SQL [$sql_label]=$sql_text"
    sqlite3 -readonly -separator "$TAB" "$TMP/cc.db" "$sql_text" > "$sql_output" 2> "$TMP/sql.err"
    sql_rc=$?
    log "cc.db SQL [$sql_label] exit code=$sql_rc"
    log "cc.db error [$sql_label]="; log_file "$TMP/sql.err"
    log "cc.db result [$sql_label] rows=$(wc -l < "$sql_output" | tr -d ' ')"
    return "$sql_rc"
}
fail() { log "FINAL RESULT=FAILED"; log "FAILURE REASON=$1"; log '==================================='; exit 1; }

log '========== COVER REQUEST =========='
log "timestamp=$(date)"
log "debug script=$0"
log "installed resolver=$INSTALLED_RESOLVER"
log "expected resolver cksum=$EXPECTED_RESOLVER_CKSUM"
if [ -r "$INSTALLED_RESOLVER" ]; then
    if command -v cksum >/dev/null 2>&1; then
        installed_cksum="$(cksum < "$INSTALLED_RESOLVER")"
        log "installed resolver cksum=$installed_cksum"
        [ "$installed_cksum" = "$EXPECTED_RESOLVER_CKSUM" ] || log 'WARNING: installed resolver differs from Compatibility V3 test source; selected function still comes from installed file'
    fi
else log 'installed resolver readable=no'; fi
log "catalog_file=$TMP/current-catalog.tsv"
log 'catalog_file_exists=no (before query)'
log "cc.db exists=$([ -r "$CC_DB" ] && echo yes || echo no)"
log "cache file=$CACHE"
log "destination cache=$CACHE"
log 'write attempted=no (before resolution)'
log 'write success=n/a (before resolution)'
log 'persistent cache write attempted=no (diagnostic replay)'
[ -r "$DATA" ] || fail "reading history unavailable: $DATA"
awk -F '\t' 'NR>1 && $2!="" && $3+0>0 {printf "%s\t%09d\t%s\t%s\n",$1,NR,$2,$4}' "$DATA" | sort -r > "$TMP/candidates"
[ -s "$TMP/candidates" ] || fail 'no read book in reading-time.tsv'
picked=0
while IFS="$TAB" read -r read_date read_line raw_id title; do
    [ -n "$raw_id" ] || continue
    if [ "$raw_id" = unknown ]; then key="title:$title"; else key="$raw_id"; fi
    cached="$(cache_lookup "$key")"
    if [ "$SELECT_MODE" = --latest ]; then picked=1; break; fi
    if [ -z "$cached" ] || ! current_cover "$cached"; then picked=1; break; fi
done < "$TMP/candidates"
if [ "$picked" -eq 0 ]; then
    fail 'no eligible book in reading history; open a book and rerun Cover Debug'
fi
log "selection mode=$SELECT_MODE"
log "selected reading date=$read_date"
log "title=$title"
log 'book_path=<pending catalog lookup>'
log 'book_format=<pending catalog lookup>'
log "raw_book_id=$raw_id"
log "normalized_book_id=$key"
log "catalog lookup key=$raw_id"
log "cache lookup path=${cached:-<none>}"
if [ -n "$cached" ] && current_cover "$cached"; then log 'cache exists=yes (ignored for both diagnostic paths)'; else log 'cache exists=no'; fi
[ "$raw_id" != unknown ] || log 'legacy 9.7.4 eligibility=no (unknown ID; v9.7.4 returns before catalog lookup)'
command -v sqlite3 >/dev/null 2>&1 || fail 'sqlite3 command missing'
[ -r "$CC_DB" ] || fail "cc.db unreadable: $CC_DB"
cp "$CC_DB" "$TMP/cc.db" 2> "$TMP/copy.err"; copy_rc=$?
log "cc.db copy exit code=$copy_rc"
log 'cc.db copy error='; log_file "$TMP/copy.err"
[ "$copy_rc" -eq 0 ] || fail 'cc.db snapshot copy failed'
log 'cc.db schema SQL=PRAGMA table_info(Entries);'
sqlite3 -readonly -separator "$TAB" "$TMP/cc.db" 'PRAGMA table_info(Entries);' > "$TMP/schema" 2> "$TMP/schema.err"
schema_rc=$?
log "cc.db schema exit code=$schema_rc"
log 'cc.db schema error='; log_file "$TMP/schema.err"
log 'cc.db schema='; log_file "$TMP/schema"
[ "$schema_rc" -eq 0 ] && [ -s "$TMP/schema" ] || fail 'Entries schema introspection failed'
for expected in p_titles_0_nominal p_cdeKey p_thumbnail p_lastAccess p_location; do
    if awk -F '\t' -v col="$expected" '$2==col{found=1}END{exit !found}' "$TMP/schema"; then
        log "COLUMN_PRESENT: $expected"
    else log "COLUMN_MISSING: $expected"; fi
done
log 'cc.db queried columns [legacy]=p_titles_0_nominal,p_cdeKey,p_thumbnail,p_lastAccess'
log 'cc.db queried columns [current]=p_titles_0_nominal,p_cdeKey,p_thumbnail,p_location,p_lastAccess'
if sql_run legacy "$SQL_LEGACY" "$TMP/legacy-catalog.tsv"; then :; else log 'legacy catalog query failed'; fi
if sql_run current-rich "$SQL_CURRENT" "$TMP/current-catalog.tsv" && [ -s "$TMP/current-catalog.tsv" ]; then
    log 'current catalog mode=location'
else
    log 'current catalog fallback entered=yes'
    log 'current catalog fallback reason=rich query failed or returned no rows'
    sql_run current-compatible "$SQL_COMPAT" "$TMP/current-catalog.tsv" || log 'current compatible query failed'
fi
log "catalog_file_exists=$([ -s "$TMP/current-catalog.tsv" ] && echo yes || echo no)"
log "catalog_file_legacy_exists=$([ -s "$TMP/legacy-catalog.tsv" ] && echo yes || echo no)"
log 'cc.db result [current, matching ID]='
if [ -r "$TMP/current-catalog.tsv" ]; then awk -F '\t' -v id="$raw_id" '$3==id{print "  " $0}' "$TMP/current-catalog.tsv" >> "$LOG"; fi
log 'cc.db result [legacy, matching ID]='
if [ -r "$TMP/legacy-catalog.tsv" ]; then awk -F '\t' -v id="$raw_id" '$3==id{print "  " $0}' "$TMP/legacy-catalog.tsv" >> "$LOG"; fi
if [ "$raw_id" != unknown ] && [ -n "$raw_id" ] && [ -r "$TMP/legacy-catalog.tsv" ]; then
    legacy_row="$(awk -F '\t' -v id="$raw_id" '$3==id&&$4!=""{print;exit}' "$TMP/legacy-catalog.tsv")"
else legacy_row=''; fi
current_row=''
if [ -r "$TMP/current-catalog.tsv" ] && [ -r "$INSTALLED_RESOLVER" ]; then
    sed -n '/^catalog_row_for_book() {/,/^}/p' "$INSTALLED_RESOLVER" > "$TMP/installed-selector.sh"
    if [ -s "$TMP/installed-selector.sh" ]; then
        CATALOG="$TMP/current-catalog.tsv"
        COVER_CACHE_DIR="$CACHE_DIR"
        cover_path_allowed() { current_cover "$1"; }
        book_path_allowed() { book_allowed "$1"; }
        cover_log() { log "[installed selector] $*"; }
        . "$TMP/installed-selector.sh"
        log 'current selector source=installed resolver function catalog_row_for_book()'
        current_row="$(catalog_row_for_book "$raw_id" "$title")"
    else log 'current selector error=catalog_row_for_book() not found in installed resolver'; fi
fi
log '[LEGACY 9.7.4]'
log "book id=$raw_id"
log_row 'legacy catalog row' "$legacy_row"
legacy_thumb="$(field "$legacy_row" 4)"
log "9.7.4-compatible field/value=field[4] p_thumbnail=${legacy_thumb:-<empty>}"
log "thumbnail candidate=${legacy_thumb:-<none>}"
if native_cover "$legacy_thumb"; then log 'legacy thumbnail candidate exists=yes'; legacy_result="$legacy_thumb"; else log 'legacy thumbnail candidate exists=no'; legacy_result=''; fi
if [ -z "$legacy_result" ]; then
    case "$raw_id" in *[!A-Za-z0-9_-]*|'') legacy_exact='';; *) legacy_exact="/mnt/us/system/thumbnails/thumbnail_${raw_id}_EBOK_portrait.jpg";; esac
    if native_cover "$legacy_exact"; then legacy_result="$legacy_exact"; fi
fi
log "resolved cover=${legacy_result:-<none>}"
log '[CURRENT]'
log "book id=$raw_id"
log_row 'current catalog row' "$current_row"
current_thumb="$(field "$current_row" 4)"
current_location="$(field "$current_row" 5)"
log "current-version field/value=field[4] p_thumbnail=${current_thumb:-<empty>}"
log "p_thumbnail=${current_thumb:-<empty>}"
log "p_location=${current_location:-<empty>}"
location_path="$current_location"
case "$location_path" in file://*) location_path="${location_path#file://}";; esac
log "p_location file exists=$([ -f "$location_path" ] && echo yes || echo no)"
log 'catalog matched rows [current, same book ID]='
if [ -r "$TMP/current-catalog.tsv" ]; then
    awk -F '\t' -v id="$raw_id" '$3==id{print "  line=" NR " fields=" NF " id=" $3 " p_thumbnail=" $4 " p_location=" $5}' "$TMP/current-catalog.tsv" >> "$LOG"
fi
log "kindle thumbnail candidate 1=${current_thumb:-<none>}"
if current_cover "$current_thumb"; then log 'kindle thumbnail candidate 1 exists=yes'; current_result="$current_thumb"; else log 'kindle thumbnail candidate 1 exists=no'; current_result=''; fi
case "$raw_id" in *[!A-Za-z0-9_-]*|'') exact='';; *) exact="/mnt/us/system/thumbnails/thumbnail_${raw_id}_EBOK_portrait.jpg";; esac
log "kindle thumbnail candidate 2=${exact:-<none>}"
if current_cover "$exact"; then log 'kindle thumbnail candidate 2 exists=yes'; [ -n "$current_result" ] || current_result="$exact"; else log 'kindle thumbnail candidate 2 exists=no'; fi
log 'other thumbnail/location candidates [legacy catalog, same book ID]='
if [ -r "$TMP/legacy-catalog.tsv" ]; then
    awk -F '\t' -v id="$raw_id" '$3==id{print "  line=" NR " fields=" NF " id=" $3 " p_thumbnail=" $4}' "$TMP/legacy-catalog.tsv" >> "$LOG"
fi
log "legacy_974_result=${legacy_result:-FAILED}"
log "current_native_result=${current_result:-FAILED}"
if [ "$legacy_thumb" != "$current_thumb" ]; then
    log 'FIRST DIVERGENCE=catalog row selection / p_thumbnail'
    log "9.7.4 value=${legacy_thumb:-<empty>}"
    log "current value=${current_thumb:-<empty>}"
elif [ "$legacy_result" != "$current_result" ]; then
    log 'FIRST DIVERGENCE=thumbnail path validation or exact filename fallback'
    log "9.7.4 value=${legacy_result:-FAILED}"
    log "current value=${current_result:-FAILED}"
else log 'FIRST DIVERGENCE=none through native thumbnail resolution'; fi
log "book_path=${current_location:-<none>}"
case "$current_location" in *.[Ee][Pp][Uu][Bb]) format=EPUB;; *.[Mm][Oo][Bb][Ii]) format=MOBI;; *.[Pp][Dd][Ff]) format=PDF;; *.[Kk][Ff][Xx]) format=KFX;; *.[Aa][Zz][Ww]3) format=AZW3;; *) format=unknown;; esac
log "book_format=$format"
miss_blocked=0
image_write_ok=1
if [ -n "$current_result" ]; then
    log 'fallback entered=no'
    log 'fallback reason=native thumbnail found'
    log "source cover=$current_result"
    log 'source exists=yes'
    write_probe
else
    log 'fallback entered=yes'
    log 'fallback reason=current catalog thumbnail and exact EBOK thumbnail unavailable'
    source="$current_location"
    case "$source" in file://*) source="${source#file://}";; esac
    if ! book_allowed "$source" && [ -n "$title" ]; then
        log 'source fallback=book path rejected; trying title as document filename'
        source="/mnt/us/documents/$title"
    fi
    log "source cover=${source:-<none>}"
    if [ -f "$source" ]; then log 'source exists=yes'; else log 'source exists=no'; fi
    if book_allowed "$source"; then log 'source allowed=yes'; else log 'source allowed=no (path or format rejected by current code)'; fi
    if book_allowed "$source"; then
        source_stat="$(stat -c '%s:%Y' "$source" 2> "$TMP/stat.err")"
        [ -n "$source_stat" ] || source_stat=present
        source_sig="$source|$source_stat"
        if [ -r "$MISS_CACHE" ] && awk -F '\t' -v key="$key" -v sig="$source_sig" '$1==key&&substr($0,index($0,"\t")+1)==sig{found=1;exit}END{exit !found}' "$MISS_CACHE"; then
            miss_blocked=1
            log 'current miss cache exists=yes; installed resolver would return before extraction'
            log 'diagnostic miss cache bypass=yes'
        else log 'current miss cache exists=no'; fi
        [ -s "$TMP/stat.err" ] && { log 'source stat error='; log_file "$TMP/stat.err"; }
    fi
    log "extractor=$HELPER"
    log "extractor exists=$([ -r "$HELPER" ] && echo yes || echo no)"
    log "extractor executable=lua:$([ -n "$(command -v lua 2>/dev/null)" ] && echo yes || echo no),unzip:$([ -n "$(command -v unzip 2>/dev/null)" ] && echo yes || echo no)"
    if book_allowed "$source"; then
        if extract_probe; then
            generated_size="$(wc -c < "$TMP/extracted-cover" | tr -d ' ')"
            log "generated file=$TMP/extracted-cover"
            log 'generated file exists=yes'
            log "generated file size=$generated_size"
            if [ "$generated_size" -gt 0 ] && [ "$generated_size" -le 8388608 ]; then
                embedded_token="$(printf '%s\n' "$key|$source_sig" | cksum | awk '{print $1}')"
                log "destination image cache=$CACHE_DIR/cover-${embedded_token}.${extracted_ext:-unknown}"
                log 'image cache write attempted=yes (temporary image probe)'
                if mkdir -p "$CACHE_DIR" 2> "$TMP/image-write.err" && cp "$TMP/extracted-cover" "$IMAGE_PROBE" 2>> "$TMP/image-write.err" && chmod 600 "$IMAGE_PROBE" 2>> "$TMP/image-write.err" && [ -s "$IMAGE_PROBE" ]; then
                    log 'image cache write success=yes'
                    rm -f "$IMAGE_PROBE"
                else image_write_ok=0; log 'image cache write success=no'; log 'image cache write error='; log_file "$TMP/image-write.err"; fi
                current_result="$TMP/extracted-cover"
                write_probe
            else log 'extraction result=generated image outside current size limits'; fi
        else log 'generated file=<none>'; log 'generated file exists=no'; log 'generated file size=0'; fi
    else log 'extraction command=not run; source rejected by current book_path_allowed()'; log 'generated file=<none>'; log 'generated file exists=no'; log 'generated file size=0'; fi
fi
log "final cover path=${current_result:-<none>}"
if [ -s "$current_result" ]; then log 'final exists=yes (native source or temporary extraction probe)'; else log 'final exists=no'; fi
if [ "$miss_blocked" -eq 1 ]; then
    log 'FINAL RESULT=FAILED'
    log 'FAILURE REASON=installed resolver is blocked by existing negative miss cache before extraction'
elif [ "$image_write_ok" -eq 0 ]; then
    log 'FINAL RESULT=FAILED'
    log 'FAILURE REASON=temporary image cache write probe failed'
elif [ -s "$current_result" ]; then log 'FINAL RESULT=SUCCESS'; log 'FAILURE REASON=<none>'
else log 'FINAL RESULT=FAILED'; log 'FAILURE REASON=current native-thumbnail and supported extraction paths did not resolve'; fi
log '==================================='
exit 0
