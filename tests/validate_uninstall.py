"""Guard the legacy uninstall paths against reintroducing app deletion."""

from pathlib import Path

root = Path(__file__).resolve().parents[1]
package = root / "native-reading-time-package"
core = (package / "uninstall.sh").read_text(encoding="utf-8")
entry = (package / "resources/reading-records-uninstall.sh").read_text(encoding="utf-8")
installed_entry = (root / "documents/reading-records-uninstall.sh").read_text(encoding="utf-8")
installer = (package / "install.sh").read_text(encoding="utf-8")
kual = (package / "resources/kual/reading-records-installer/bin/action.sh").read_text(encoding="utf-8")
menu = (package / "resources/kual/reading-records-installer/menu.json").read_text(encoding="utf-8")

assert core.startswith("#!/bin/sh\n# READING_RECORDS_CLEANUP_CORE_V1")
assert "stop_owned_processes" not in core and "initctl stop" not in core
assert "manifest_pass" not in core and "kill -TERM" not in core
assert "reading-time.tsv" in core and "DETECT PROTECTED" in core
assert entry == installed_entry and "# Name: 安装文件清理" in entry
assert "# READING_RECORDS_CLEANUP_CORE_V1" in entry
assert "# READING_RECORDS_CLEANUP_CORE_V1" in installer
assert "# READING_RECORDS_CLEANUP_CORE_V1" in kual
assert "uninstall-keep-data" in installer and "uninstall-keep-data" in kual
assert "安装文件清理" in menu and "卸载程序" not in menu
print("legacy uninstall entry is a cleanup-only compatibility alias: PASS")
