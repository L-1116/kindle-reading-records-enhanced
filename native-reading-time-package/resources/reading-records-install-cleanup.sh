#!/bin/sh
# Name: 安装好之后，确认无误了再点这个
# Author: Kindle Reading Records Enhanced
BASE="/mnt/us/reading-time"
[ "$(cat "$BASE/VERSION" 2>/dev/null)" = 9.7.6-5.19-normal ] && [ -f "$BASE/activation-verified" ] || exit 1
# Deliberately literal, reviewable paths. No globs and no runtime/data removal.
rm -f "/mnt/us/documents/reading-records-9.7.6-install.sh" || exit 1
rm -f "/mnt/us/documents/阅读记录安装数据.tar" || exit 1
rm -f "/mnt/us/RUNME.sh" || exit 1
rm -f "/mnt/us/README.txt" || exit 1
rm -f "/mnt/us/PACKAGE-MANIFEST.json" || exit 1
rm -rf "/mnt/us/native-reading-time-package" || exit 1
rm -f "/mnt/us/documents/reading-records-install.sh" || exit 1
rm -f "/mnt/us/documents/reading-records-v4-install.sh" || exit 1
rm -f "/mnt/us/documents/reading-records-uninstall.sh" || exit 1
rm -f "/mnt/us/documents/reading-records-diagnostic.sh" || exit 1
rm -f "/mnt/us/documents/reading-records-force-exit.sh" || exit 1
rm -f "/mnt/us/documents/reading-records-cover-debug.sh" || exit 1
rm -rf "/mnt/us/extensions/reading-records-installer" || exit 1
rm -f "/mnt/us/install-reading-records.log" || exit 1
lipc-set-prop com.lab126.scanner doFullScan 1 >/dev/null 2>&1 || true
# Self-removal is the final deletion; scanner updates again when it disappears.
rm -f /mnt/us/documents/reading-records-install-cleanup.sh
