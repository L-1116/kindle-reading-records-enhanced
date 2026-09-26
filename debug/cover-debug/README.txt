Cover Debug V3 diagnostic kit (not an installer or a formal release)

1. Read a book that has never shown a cover in Reading Records. Let a reading
   session be recorded, then close the book.
2. Extract this zip at the root of the Kindle USB drive. It adds only
   cover-debug.sh, a KUAL menu entry, and a library Scriptlet. It does not
   replace the installed plugin.
3. Run "阅读记录：生成封面调试日志" in KUAL, or tap "阅读记录封面诊断" in the library.
4. Reconnect USB and send these two files:
   /mnt/us/reading-time/cover-debug.log
   /mnt/us/documents/reading-records-cover-debug-result.txt

The one-click entry selects the most recently read book even if it already has
a Reading Records cover mapping. It records that mapping but bypasses it for
both comparisons. The current selector is loaded from the installed
reading-records.sh, and its checksum is recorded. The script does not delete
the book cache, reading history,
or cc.db. It only writes the log, a temporary cache-write probe, and the small
result file. The temporary probe is removed immediately.

The log includes book titles, IDs, local paths, and cc.db column names. Review
it before sharing if these are sensitive.
