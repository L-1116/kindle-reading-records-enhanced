#!/bin/sh
# Requests are asynchronous. Never write cc.db or remove Scriptlet .sdr caches.
rr_scan_documents() {
    rr_scan_status=request_failed
    if rr_run 2 lipc-set-prop com.lab126.scanner doFullScan 1 >> "$BASE/install.log" 2>&1 ||
       rr_run 2 lipc-set-prop com.lab126.scanner triggerUpdate 1 >> "$BASE/install.log" 2>&1; then
        rr_scan_status=request_accepted
    fi
    printf 'scanner_request=%s index_completion=unverified\n' "$rr_scan_status" >> "${LOG:-$BASE/install.log}"
    # A failed request leaves the valid runtime installed and is reported.
    [ "$rr_scan_status" != request_failed ] || {
        rr_run 1 lipc-set-prop com.lab126.system toasterMessage '阅读记录已安装；书库更新请求失败，旧图标可能暂时残留' >/dev/null 2>&1 || true
    }
    return 0
}
