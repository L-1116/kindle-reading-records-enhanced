"""Write the local 26-point delivery report from verified build/test artifacts."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/validation'
BASELINE = 'e41707492b985284d77e0ec5ec5ceffe98209a89'
HARDENING_START = '93b6e791ca39dc3dbc233b6ea9fedb15ce243374'

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8').strip()

def main():
    execution = json.loads((OUT / "suite-results.json").read_text(encoding="utf-8"))
    assert execution["result"] == "PASS" and execution["complete"] and len(execution["stages"]) == 11
    package = json.loads((OUT / 'package-results.json').read_text(encoding='utf-8'))
    names = ['results.json', 'stats-filters-results.json', 'day-detail-results.json',
             'period-detail-results.json', 'book-detail-results.json', 'cover-fallback-results.json',
             'audit-results.json', 'installer-results.json', 'runtime-results.json', 'pre-hardware-results.json']
    suites = {}
    for name in names:
        result = json.loads((OUT / name).read_text(encoding='utf-8'))
        assert result.get('result', 'PASS') == 'PASS', name
        checks = result['checks']
        assert all(not isinstance(c, dict) or c['result'] == 'PASS' for c in checks), name
        suites[name] = len(checks)
    archive = Path(package['archive'])
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == package['zip_sha256']
    for name, info in package['files'].items():
        if name != 'payload-manifest.tsv':
            assert hashlib.sha256((ROOT/'native-reading-time-package'/name).read_bytes()).hexdigest() == info['sha256'], name
    head = git('rev-parse', 'HEAD')
    branch = git('branch', '--show-current')
    commits = git('log', '--reverse', '--format=%H %s', BASELINE + '..HEAD')
    diff = git('diff', '--stat', BASELINE, 'HEAD')
    hardening_diff = git('diff', '--stat', HARDENING_START, 'HEAD')
    whitelist = (ROOT / 'native-reading-time-package/cleanup-manifest.txt').read_text(encoding='utf-8')
    lines = [
        '# 9.7.6-5.19-normal 本地交付报告',
        '',
        '结论：**A. 当前代码已经达到“除真机物理行为外，无已知代码 blocker”。** 尚无 Kindle 真机验证；横屏完整链路、电源键、触摸与实际 e-ink 刷新仍须按清单验收。没有 push、tag 或发布 Release。静态问题证据与本轮修改见 `docs/5.19-normal-pre-hardware-audit.md`。',
        '',
        f'1. **Baseline SHA：** `{BASELINE}`，tag `v9.7.5-测试版`。第一个空提交与该 tag 的 Git tree 相同；初始字节核对发现宽度表原 blob 为 CRLF，之后在运行修复提交中明确规范化为 LF，数值未改。',
        f'2. **分支与工作树：** `{branch}`，`{ROOT}`。原 V4 工作树及其未提交修改保留。',
        f'3. **当前 HEAD：** `{head}`。',
        '4. **Baseline 到 HEAD 的提交：**',
        '', '```text', commits, '```', '',
        '5. **选择性移植：** 从 `53a0044`（compat-v3）审阅 catalog 候选排序，最小重写为有效 thumbnail 优先、有效 location 次优；从后续横屏排障记录吸收保存方向、提前安装退出 trap、等待 owned child 和退出恢复的原则。没有 cherry-pick 整个后续 commit。安装事务与数据保护原则来自既有工程实践，独立实现为单一 5.19 installer。',
        '6. **明确排除：** 5.18 hard-float workaround、特殊 framebuffer/GC16、KPW4 evdev、5.17、KS touch/UI/force-exit/installer、Scribe UI/resolution adaptation、多 ABI runtime/Lua/FBInk 搜索矩阵、probe/watchdog、diagnostic 大礼包。ZIP/tar 没有这些模块。Scribe 检测只用于拒绝安装。',
        '7. **duplicate-row 位置：** `native-reading-time-package/阅读记录-optimized.sh` 的 `catalog_row_for_book()`。扫描全部同 ID 行，每条用可读非空缩略图得 2 分、可用本体路径得 1 分；最高分胜出，同分保留 catalog 原顺序。存在同 ID 行时不借用不同 ID 的同名书封面；完全找不到对应 ID 时保留基线按标题 fallback。已有 cache、EPUB/MOBI 提取及 PDF/default fallback 不变。',
        '8. **FBInk：** 原固定 KMC runtime 继续执行真正的显示命令，不执行 `-e`、help/info 或独立 capability probe；图片、文字、矩形及最终 refresh 的失败均安全退出。保留基线 GC16_FAST → GC16 同一次刷新 fallback。renderer 错误可进入基线旧 UI；真正 FBInk 失败退出，不用失败的 FBInk 做清理刷新。',
        '9. **orientation：** launcher 获得排他锁后读取 geometry 和 orientationLock。L/R 或横向 geometry 触发保存 U/D/L/R → 请求 U → 最多四次一秒等待 → 运行 UI。未知原方向且需要旋转时安全拒绝，不先旋转。退出先结束 UI/reader，打开原生 Library，再请求恢复原方向；正常、Lua/FBInk/touch 初始化失败、launcher 失败和 INT/TERM/HUP 共用入口。',
        '10. **统一 runtime cleanup：** `launch.sh:cleanup_runtime_state()` 的唯一顺序：回收 owned UI/reader → 恢复原 preventScreenSaver → 恢复原 eatTapMode → 打开 Library → sleep 1 → 恢复临时 orientation → 释放锁。仅处理已设置 pending 的属性；CLEANED 保证重复调用无副作用。两个 runtime 只回收自己的直接 child 与 /tmp 会话。Lua readers 保持只读，无 EVIOCGRAB，不改电源键处理。fork/PID 窗口保留原私有交接；没有修改其他长期系统属性或新增长期进程。',
        '11. **安装完整链：** documents Scriptlet → mkdir 私有安装锁（PID owner 目录，覆盖日志/解包/事务）→ 同目录 ASCII tar → cksum+size → /tmp df -Pk 预检（tar 大小 + 4 MiB）→ 系统 tar/BusyBox tar → `/tmp/reading-records-9.7.6-installer.$$` → 内部 `install.sh` → firmware/KS gate → 原有 UI/事务排他锁 → 资源 manifest → /mnt/us df -Pk 预检（2×payload du + 旧部署目标/同版本 release du + 8 MiB）→ 暂存 release/回滚快照 → stop daemon 并确认停止 → 发布 runtime/入口/service → cmp+daemon status verified activation → VERSION/activation marker → 生成清理入口 → scanner → bootstrap 回收 /tmp/安装锁。容量未知/空间不足均提前拒绝；失败保留原两个文件。',
        '12. **Payload 结构：**', '',
        '```text',
        'native-reading-time-package/',
        '  install.sh / install-manifest.txt / payload-manifest.tsv / cleanup-manifest.txt',
        '  launch.sh / runtime-child.sh / runtime-lock.sh',
        '  阅读记录-optimized.sh / 阅读记录.sh  (私有源，部署为短 ASCII runtime)',
        '  native-reading-time-daemon.sh / native-reading-time.conf',
        '  reading-insights-*.lua / reading-insights-cache.awk',
        '  NotoSansCJKsc-Regular.otf / FONT-LICENSE.txt / launcher-icon.png',
        '  ui/ / ui-calendar/ / render-assets/',
        '  resources/reading-records-install-cleanup.sh',
        '```', '',
        f'共 {package["payload_files"]} 个 regular files。Lua helpers 使用原 9.7.5 的设备 Lua/FBInk 环境；不捆绑多 ABI 二进制或兼容探测器。正式 documents 入口是 `reading-records.sh`，显示名“阅读记录”。',
        '13. **Fresh install：** 无需先运行旧 base installer；单一正式 installer 暂存全部运行资源，部署原 daemon/service/font/icon、版本化 UI 和正式入口，daemon 按原逻辑初始化 TSV。',
        '14. **Upgrade：** 9.7.4/9.7.5 test/compat Standard/V3/V4 都走同一事务；旧 release 保留，shared runtime 部署前备份；历史/config/cover/statistics 不参与部署。成功后移除旧中文正式 launcher，换为短 ASCII 入口。',
        '15. **Repair：** 同版本 release 先移动到事务备份，再整体发布暂存目录；shared runtime 同样备份并 cmp 校验。journal 记录目标原来是否存在，事务开始前保存校验值/记录总数，回滚前后校验并核对读取数；缺失/截断/提前读取失败及缺失 backup 均不能按成功删除恢复快照。rollback 删除失败不得继续 mv；文件、rootfs、配置重载或旧服务重启失败保留 STAGE，记录 RECOVERY_REQUIRED snapshot=位置。恢复未完成时不启动混合 runtime。',
        '16. **Cleanup 精确白名单：** 以下路径仅指安装残留；最后删除 `/mnt/us/documents/reading-records-install-cleanup.sh`，之后触发 scanner。RUNME/README/PACKAGE-MANIFEST 需满足已知安装器内容标记才删。',
        '', '```text', whitelist.rstrip(), '/mnt/us/documents/reading-records-install-cleanup.sh  (最后删除自身)', '```', '',
        '17. **永久保护：** `reading-time.tsv`、`.bak`、用户历史/history、`user.conf`、`book-cover-cache.tsv`、`book-cover-misses.tsv`、`book-covers/`、封面缓存、统计缓存/数据、正式 runtime/release/launcher、daemon、service、正式“阅读记录”入口及核心日志。cleanup 不进入 reading-time 数据目录删除任何文件。',
        '18. **Firmware：** 合并 `/etc/prettyversion.txt`、`/etc/version.txt`，要求只有一个唯一纯数字 dotted version；相同版本重复可接受，不同版本歧义拒绝。仅 `5.19.*`（至少含 patch，允许更多数字 patch levels）允许。引号、Kindle/build/Firmware Version 前缀、空白、LF/CRLF 覆盖；旧固件、5.190、空值/garbage、畸形 patch 与附着乱码拒绝。',
        '19. **KS 排除：** 名称含 Scribe/KS，sysfs 输入名称带 Wacom/stylus/digitizer/hanvon，或 framebuffer 短边 ≥1500 的大屏设备拒绝；检测已有 VERSION/PACKAGE_VARIANT/release-info 的 KS 标记防混装。没有 Standard 型号/序列号白名单。笔输入作为 KS 排除依据参考 [KOReader Kindle 设备实现](https://github.com/koreader/koreader/blob/master/frontend/device/kindle/device.lua)；大屏阈值是本包保守排除策略，需真机确认各目标设备识别结果。',
        '20. **ZIP 顶层：** 恰好 `reading-records-9.7.6-install.sh` 和 `reading-records-9.7.6-data.tar`，无其他文件/目录。两个 USB/MTP 物理文件名均为短 ASCII，中文仅作 Scriptlet 显示名。旧中文 tar 只保留为历史 cleanup 白名单条目。',
        f'21. **ZIP 大小：** {package["zip_bytes"]:,} bytes。',
        f'22. **Payload 大小：** {package["payload_bytes"]:,} bytes；POSIX cksum `{package["payload_cksum"]}`；bootstrap {package["bootstrap_bytes"]:,} bytes。',
        '23. **SHA-256：**', '',
        '```text',
        'ZIP       ' + package['zip_sha256'],
        'Payload   ' + package['payload_sha256'],
        'Bootstrap ' + package['bootstrap_sha256'],
        '```', '',
        '24. **自动测试：** 以下最终报告全部 PASS；覆盖用户 1–56 项的离线可验证部分，包括真实 archive/manifest/deploy/rollback、真实 POSIX shell 控制流与 Lua 渲染/封面 fixtures。逐项覆盖映射见 `docs/5.19-normal-regression-matrix.md`。硬件命令模拟通过不等于 Kindle 真机通过，尤其第 55 项只验证电源状态恢复契约。',
        '', '| 报告 | PASS 检查数 |', '|---|---:|',
        *[f'| {name} | {count} |' for name, count in suites.items()],
        f'| 合计 | {sum(suites.values())} |', '',
        '另：最终 ZIP/tar 每个归档字节、checksums、顶层条目、regular-file 类型与全部脚本的 sh/dash syntax 已校验。完整日志 `final-complete-suite.log`，包内逐文件 SHA 在 `package-results.json`。',
        '25. **git diff --stat：**', '', '```text', diff, '```', '',
        '26. **真机风险/发布 blocker：** orientationLock 的实际可读性、切到 U 后 framebuffer 及触摸坐标是否同步、恢复方向后原生阅读器偏好、原生 Library 的旋转时序、实体电源键在运行前/中/后、自动休眠、e-ink 波形/残影、真实新书 catalog/封面与目标设备 capability 识别。POSIX trap 不能保证 SIGKILL、断电或系统 LIPC 不响应时的恢复。清单为 `docs/5.19-normal-kpw-checklist.md`。未经横屏完整链路 KPW 5.19 真机通过，不得发布。',
        '', f'本轮起点 `{HARDENING_START}`；原 172 项全部重新执行，新增 {sum(suites.values())-172} 项，最终 {sum(suites.values())} 项 PASS。',
        '', '本轮相对起点的 git diff --stat：', '', '```text', hardening_diff, '```', '',
    ]
    report = OUT / '9.7.6-5.19-normal-report.md'
    report.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    summary = {'result': 'PASS', 'state': 'A: no known code blocker beyond physical hardware validation',
               'baseline_sha': BASELINE, 'branch': branch, 'head_sha': head,
               'suite_counts': suites, 'checks': sum(suites.values()), 'package': package,
               'hardening_start_sha': HARDENING_START, 'new_checks': sum(suites.values())-172, 'hardening_diff_stat': hardening_diff,
               'release_published': False, 'push_performed': False, 'tag_created': False}
    (OUT / 'normal-final-results.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'report': str(report), 'checks': summary['checks'], 'head': head}, ensure_ascii=True))

if __name__ == '__main__':
    main()
