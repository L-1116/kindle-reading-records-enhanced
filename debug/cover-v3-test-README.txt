Compatibility V3 / cover regression fix - TEST PACKAGE ONLY

This is not a formal release. It restores usable same-book-ID catalog row
selection while keeping the existing thumbnail and extraction chain.

Install: extract this ZIP at the Kindle USB root, then use the existing
"阅读记录安装" Scriptlet, KUAL "阅读记录 > 安装 / 升级", or RUNME route.
The installer replaces the dashboard resolver at
/mnt/us/reading-time/releases/9.7.5-test/bin/reading-records.sh and verifies
that it matches the packaged source byte-for-byte. It preserves reading-time.tsv,
book-cover-cache.tsv, book-cover-misses.tsv, and existing cover image files.

Expected V3 installed resolver cksum: 459377751 90742
Verify it in /mnt/us/documents/reading-records-diagnostic.txt after using
KUAL "阅读记录 > 生成诊断". The install log also records source and installed
resolver checksums.

Problem-device tests:
1. Open 北平无战事(上下册), which had no Reading Records cover cache. Its native
   Kindle thumbnail should display.
2. Read a different book with no Reading Records cover cache; check its cover.
3. On a device upgraded from 9.7.4, check one old cached cover and one new book.
4. For one book only, remove its Reading Records cover mapping during a
   controlled test; reopen it and check that the native cover is found again.

The ZIP also updates the one-click "阅读记录：生成封面调试日志" KUAL entry. Run it after
opening the problem book and send /mnt/us/reading-time/cover-debug.log plus
/mnt/us/documents/reading-records-cover-debug-result.txt. The debug replay
loads catalog_row_for_book() from the installed resolver, so the checksum in
that log identifies the code actually tested.
