"""Execute the shipped resolver against duplicate cc.db-shaped catalog rows."""

from pathlib import Path
import os
import shlex
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
VIEWER = Path(os.environ.get("READING_TEST_RESOLVER", ROOT / "native-reading-time-package" / "阅读记录-optimized.sh"))
SH = shutil.which("sh") or "C:/Program Files/Git/usr/bin/sh.exe"
OUT = ROOT / "build" / "validation"
OUT.mkdir(parents=True, exist_ok=True)


def quote(path: Path) -> str:
    return shlex.quote(path.relative_to(ROOT).as_posix())


with tempfile.TemporaryDirectory(prefix="cover-regression-", dir=OUT) as directory:
    session = Path(directory)
    functions = session / "functions.sh"
    source = VIEWER.read_text(encoding="utf-8")
    definitions = source[: source.index("\ndetect_screen; find_touch_device")]
    definitions = definitions.replace('if [ "${READING_LAUNCHER_CAPTURE:-0}" != 1 ]; then exec >> "$LOG" 2>&1; fi', "")
    definitions = definitions.replace('echo "$(date): optimized dashboard launch, uid=$(id -u), pid=$$"', "")
    functions.write_text(definitions, encoding="utf-8", newline="\n")
    covers = session / "covers"
    books = session / "books"
    covers.mkdir()
    books.mkdir()
    good = covers / "thumbnail_GvykvB.jpg"
    other = covers / "other.jpg"
    good.write_bytes(b"valid Kindle thumbnail")
    other.write_bytes(b"different book thumbnail")
    kfx = books / "北平无战事.kfx"
    epub = books / "extractable.epub"
    kfx.write_bytes(b"fixture")
    epub.write_bytes(b"fixture")
    missing = covers / "missing.jpg"
    catalog = session / "catalog.tsv"
    cache = session / "book-cover-cache.tsv"
    book_id = "ED75D9F42E4042E4B0BFE2BF179ECE20"
    title = "北平无战事(上下册)"

    setup = f"""
PATH="/usr/bin:$PATH"
. {quote(functions)}
SESSION_DIR={quote(session)}
CATALOG={quote(catalog)}
COVER_CACHE={quote(cache)}
COVER_CACHE_DIR={quote(covers)}
BOOK_DIR={quote(books)}
catalog_loaded=1
TEST_TITLE="$(awk -F '\t' 'NR==1{{print $2}}' "$CATALOG")"
cover_path_allowed() {{ case "$1" in "$COVER_CACHE_DIR"/*) [ -s "$1" ];; *) return 1;; esac; }}
book_path_allowed() {{ case "$1" in "$BOOK_DIR"/*.epub|"$BOOK_DIR"/*.mobi) [ -f "$1" ];; *) return 1;; esac; }}
"""

    def run(commands: str) -> str:
        result = subprocess.run(
            [SH, "-c", setup + commands],
            cwd=ROOT,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        assert result.returncode == 0, (result.stdout, result.stderr, commands)
        return result.stdout.rstrip("\r\n")

    def rows(*items: tuple[str, str, str, str]) -> None:
        catalog.write_text("".join("-1\t" + "\t".join(item) + "\t\n" for item in items), encoding="utf-8")
        cache.unlink(missing_ok=True)

    def picked(row_id: str = book_id) -> list[str]:
        output = run(f'catalog_row_for_book {shlex.quote(row_id)} "$TEST_TITLE" || true\n')
        return output.split("\t") if output else []

    # The real Kindle failure: first same-ID row is empty, second has a real
    # native thumbnail and a KFX location. Start with no Reading Time cache.
    rows((title, book_id, "", ""), (title, book_id, quote(good).strip("'"), quote(kfx).strip("'")))
    assert picked()[3:5] == [good.relative_to(ROOT).as_posix(), kfx.relative_to(ROOT).as_posix()]
    assert run(f'resolveBookCover {shlex.quote(book_id)} "$TEST_TITLE"\n') == good.relative_to(ROOT).as_posix()
    assert cache.read_text(encoding="utf-8").strip() == f"{book_id}\t{good.relative_to(ROOT).as_posix()}"

    # Upgrades must still serve a pre-existing Reading Time cover mapping.
    rows((title, book_id, "", ""))
    cache.write_text(f"{book_id}\t{good.relative_to(ROOT).as_posix()}\n", encoding="utf-8")
    assert run(f'resolveBookCover {shlex.quote(book_id)} "$TEST_TITLE"\n') == good.relative_to(ROOT).as_posix()

    # Row order must not let an empty later row erase a usable earlier row.
    rows((title, book_id, good.relative_to(ROOT).as_posix(), kfx.relative_to(ROOT).as_posix()), (title, book_id, "", ""))
    assert picked()[3:5] == [good.relative_to(ROOT).as_posix(), kfx.relative_to(ROOT).as_posix()]

    # A real thumbnail outranks a nonempty path to a missing file.
    rows((title, book_id, missing.relative_to(ROOT).as_posix(), ""), (title, book_id, good.relative_to(ROOT).as_posix(), kfx.relative_to(ROOT).as_posix()))
    assert picked()[3] == good.relative_to(ROOT).as_posix()

    # An EPUB location is passed unchanged to the existing extraction chain.
    rows((title, book_id, "", ""), (title, book_id, "", epub.relative_to(ROOT).as_posix()))
    assert picked()[4] == epub.relative_to(ROOT).as_posix()
    output = run(f'cache_embedded_cover() {{ printf "EXTRACT_SOURCE=%s\\n" "$2"; }}\nresolveBookCover {shlex.quote(book_id)} "$TEST_TITLE"\n')
    assert output == f"EXTRACT_SOURCE={epub.relative_to(ROOT).as_posix()}"

    # Even an unsupported KFX source remains attached to the correct ID.
    rows((title, book_id, "", ""), (title, book_id, "", kfx.relative_to(ROOT).as_posix()))
    assert picked()[4] == kfx.relative_to(ROOT).as_posix()

    # Equal titles never borrow metadata from another known book ID.
    rows((title, "OTHER_ID", other.relative_to(ROOT).as_posix(), ""), (title, book_id, good.relative_to(ROOT).as_posix(), ""))
    assert picked()[2] == book_id
    assert picked("ABSENT_ID") == []

    # All-empty metadata preserves the existing downstream fallback result.
    rows((title, book_id, "", ""), (title, book_id, "", ""))
    assert picked()[3:5] == ["", ""]
    assert run(f'resolveBookCover {shlex.quote(book_id)} "$TEST_TITLE" || printf "NO_COVER\\n"\n') == "NO_COVER"
    assert not cache.exists()

print("duplicate catalog row regression and empty-cache resolver: PASS")
