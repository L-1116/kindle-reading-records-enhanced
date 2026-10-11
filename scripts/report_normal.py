"""Generate the current 5.18 local-only report from verified artifacts."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import zipfile
from package_release import cksum, BOOTSTRAP, PAYLOAD
from validate_all import CHECKS

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / 'native-reading-time-package'
OUT = ROOT / 'build/validation'
START = '01109630d1b03c693eef587b494c2bafe00c60e3'
REPORTS = ['results.json', 'stats-filters-results.json', 'day-detail-results.json',
           'period-detail-results.json', 'book-detail-results.json', 'cover-fallback-results.json',
           'audit-results.json', 'installer-results.json', 'runtime-results.json',
           '518-eattapmode-results.json', 'pre-hardware-results.json', 'final-freeze-results.json']

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def payload(raw):
    with tarfile.open(fileobj=io.BytesIO(raw)) as t:
        members = t.getmembers()
        assert all(m.isfile() and m.name.startswith('native-reading-time-package/') for m in members)
        assert len({m.name for m in members}) == len(members)
        return {m.name.removeprefix('native-reading-time-package/'): t.extractfile(m).read() for m in members}

def main():
    execution = json.loads((OUT / 'suite-results.json').read_text(encoding='utf-8'))
    assert execution['result'] == 'PASS' and execution['complete']
    assert [r['script'].replace(chr(92), '/') for r in execution['stages']] == [p.relative_to(ROOT).as_posix() for p in CHECKS]
    counts = {}
    for name in REPORTS:
        result = json.loads((OUT / name).read_text(encoding='utf-8'))
        assert result.get('result', 'PASS') == 'PASS'
        assert all(not isinstance(c, dict) or c['result'] == 'PASS' for c in result['checks'])
        counts[name] = len(result['checks'])
    package = json.loads((OUT / 'package-results.json').read_text(encoding='utf-8'))
    archive = Path(package['archive'])
    assert package['version'] == '9.7.6-5.18-vera' and sha(archive.read_bytes()) == package['zip_sha256']
    with zipfile.ZipFile(archive) as z:
        assert z.namelist() == [BOOTSTRAP, PAYLOAD] and z.testzip() is None
        boot, raw = z.read(BOOTSTRAP), z.read(PAYLOAD)
    files = payload(raw)
    assert set(files) == set(package['files'])
    for name, data in files.items():
        assert sha(data) == package['files'][name]['sha256']
        if name != 'payload-manifest.tsv': assert data == (PKG / name).read_bytes(), name
    manifest = files['payload-manifest.tsv'].decode('utf-8').splitlines()
    assert len(manifest) == len(files) - 1
    for line in manifest:
        checksum, size, name = line.split('\t')
        assert cksum(files[name]) == (int(checksum), int(size)), name
    checksum, size = cksum(raw)
    assert (checksum, size) == (package['payload_cksum'], package['payload_bytes'])
    assert f'EXPECTED_CKSUM={checksum}'.encode() in boot and f'EXPECTED_SIZE={size}'.encode() in boot
    template = (ROOT / 'documents' / BOOTSTRAP).read_bytes()
    assert boot == template.replace(b'@PAYLOAD_CKSUM@', str(checksum).encode()).replace(b'@PAYLOAD_SIZE@', str(size).encode())
    old_zip = OUT / '518-eattapmode-before' / archive.name
    with zipfile.ZipFile(old_zip) as z:
        old_files, old_boot = payload(z.read(PAYLOAD)), z.read(BOOTSTRAP)
    assert old_files.keys() == files.keys()
    changed = [n for n in sorted(files) if old_files[n] != files[n]]
    assert changed == ['launch.sh', 'payload-manifest.tsv'], changed
    normalize = lambda b: re.sub(rb'EXPECTED_(CKSUM|SIZE)=\d+', rb'EXPECTED_\1=<generated>', b)
    assert normalize(boot) == normalize(old_boot)
    paths = filter(None, git('ls-tree', '-r', '-z', '--name-only', START, 'native-reading-time-package', 'documents').decode('utf-8').split('\0'))
    source_changes = [p for p in paths if (ROOT / p).read_bytes() != git('show', START + ':' + p)]
    assert source_changes == ['native-reading-time-package/launch.sh'], source_changes
    head = git('rev-parse', 'HEAD').decode().strip()
    branch = git('branch', '--show-current').decode().strip()
    assert branch == '9.7.6-5.18-vera'
    git('merge-base', '--is-ancestor', START, 'HEAD')
    origin_head = git('rev-parse', 'origin/' + branch).decode().strip()
    committed = head != START
    pushed = committed and origin_head == head
    before = json.loads((OUT / '518-eattapmode-before.json').read_text(encoding='utf-8'))
    assert before['production_unmodified'] and len(before['reproduction']) == 12
    history_path = OUT / '518-run-history.json'
    history = json.loads(history_path.read_text(encoding='utf-8')) if history_path.exists() else []
    assert history and history[-1]['command'] == 'python scripts/validate_all.py' and history[-1]['exit_code'] == 0
    failures = sum(r['exit_code'] != 0 for r in history)
    complete_runs = sum(r['command'] == 'python scripts/validate_all.py' for r in history)
    status = git('status', '--short', '--untracked-files=all').decode().strip()
    diff = git('diff', '--stat', START).decode().strip()
    lines = [
        '# 9.7.6-5.18-vera eatTapMode 本地交付报告', '',
        f'本轮开始：2026-10-10；完整回归完成：{history[-1]["recorded_at"]}（Asia/Shanghai）。状态：**Pre-hardware candidate**；本轮尚无 5.18 真机验证，不称为正式发布就绪。5.19 真机成功和测试计数不是本分支通过证据。', '',
        f'工作树：{ROOT}；分支：{branch}；修复起点：{START}；当前 HEAD：{head}；本地 origin 跟踪引用：{origin_head}。修复已提交：{committed}；与 origin 同步：{pushed}（远端实际 SHA 另行核对）。2026-10-11 用户另行授权提交/push 源码备份，不创建 tag、Release 或 PR，不修改其他 worktree。', '',
        '## 静态问题与修改前复现', '',
        '原 launcher 强制读取只写 eatTapMode，继而写入 0/退出写回；旧模拟器误当 rw。9.7.5 两套入口仅尽力写 0，无原值保存，不能称为恢复原状态。两个真实 Lua reader 均 io.open(device, "rb")，由 runtime-child 调用，只读 evdev，无 EVIOCGRAB 或设备写入。', '',
        '修改生产前，未修改的 5.18 launcher 在 sh/dash × U/R × 缺原值/隐藏 0/隐藏 7 共 12 组合均退出码 1、ERROR: 无法保存触摸状态；监听尚未启动，横屏清理恢复方向。证据为 518-eattapmode-before.json / 518-eattapmode-reproduce.log；旧包及上一轮报告保留在 518-eattapmode-before/。最终回归重复原入口失败，作为预期断言。', '',
        '## 修复与生产 payload', '',
        '仅 launch.sh 移除 eatTapMode 的全部 get/set、ORIGINAL_EAT/EAT_PENDING 和虚假恢复。保持未知状态不变；orientationLock/preventScreenSaver 实际原值保存、校验、请求前 pending、正常/失败/INT/TERM/HUP 幂等清理均保留。owned UI/reader 的终止与 wait、fork/PID、会话锁、安装互斥、Library 后恢复方向顺序不变。', '',
        f'与本轮旧包归档比较仅 {changed} 改变；bootstrap 仅生成校验字段改变。生产源仅 {source_changes} 改变。65 个 payload 条目集合相同，全部受保护文件逐字节一致。', '',
        '统计、历史格式、配置/封面/缓存、Lua 渲染/坐标/触摸、daemon/service、电源键、安装事务/rollback/repair/清理、runtime-child/runtime-lock、所有 UI 资产均未改。5.18.x gate、内部 9.7.6-5.18-vera、真实 UI FBInk 命令及 GC16_FAST → GC16 fallback 保留。未新增 ABI 搜索、二进制、probe、watchdog 或诊断包。', '',
        '工具修复：ls-tree -z，不改全局 Git；路径按原字符串一次替换；CI 分支为 9.7.6-5.18-vera；publishing 仍 40 秒，其他超时未放宽，失败断言保留阶段/进程/安装日志。当前文档和工程约束撤销 eatTapMode 恢复承诺；历史审计保留并标记更正。详见 docs/5.18-vera-eattapmode-fix.md。', '',
        '## 定向和完整验证', '',
        '定向验证覆盖只写读取失败/无 stdout、无原值、隐藏非零、拒绝写入、两套 UI 启动/导航/退出且无 eatTapMode 请求、非零 power 和横屏恢复；真实旧包原地同版更新确认 launcher 替换及历史/备份/配置/封面/统计缓存/核心日志保留，清理后再启动。', '',
        '完整入口为本分支 scripts/validate_all.py；保留原 12 stage，加一项只写属性 stage。保留安装、回滚、repair、清理、信号、fork/PID、锁和统计渲染断言；新增 power 写失败/无效/空值及请求返回窗口信号。eat 写失败必须退出的旧预期被“禁止写入、拒写仍正常且无请求”取代；幂等清理仍覆盖完整/部分/无修改。', '',
        '| 结果文件 | PASS 检查数 |', '|---|---:|',
        *[f'| {n} | {c} |' for n, c in counts.items()],
        f'| 合计 | {sum(counts.values())} |', '',
        f'最终 {len(execution["stages"])} stage PASS，complete=true。未套用 5.19 的 407 项。完整日志 518-complete-suite.log，stage 用时见 suite-results.json。', '',
        f'本轮实际测试失败 {failures} 次；完整入口执行 {complete_runs} 次。所有运行日志保留，失败后重跑（若有）见下方记录。', '',
        '实际运行及失败/重跑记录（旧入口的预期失败复现不算测试失败）：', '',
        '```json', json.dumps(history, ensure_ascii=False, indent=2), '```', '',
        '## 安装包', '',
        f'绝对路径：{archive.resolve()}', '',
        f'大小：{package["zip_bytes"]:,} bytes；SHA-256：{package["zip_sha256"]}', '',
        f'Payload：{size:,} bytes，POSIX checksum {checksum}，SHA-256 {package["payload_sha256"]}，{len(files)} regular files。', '',
        f'ZIP 顶层严格只有 {BOOTSTRAP} 和 {PAYLOAD}。归档 CRC、manifest 每项 POSIX checksum/size、tar 类型、源 SHA-256、bootstrap 模板和整体 checksum 均重新核对。', '',
        '## 尚缺的 5.18 真机证据', '',
        '- 正常启动、真实 FBInk/GC16 刷新，两套 UI。',
        '- 触摸命中、穿透、退出后原生触摸。',
        '- 横屏阅读后进入/退出，L/R 原方向和 Library 时序恢复。',
        '- 实体电源键、运行中及退出后的自动休眠。',
        '- 连续启动退出，无残留 owned child 或锁。', '',
        '以上尚未取得证据，不要求普通用户执行 LIPC 命令、选择 runtime 或承担兼容性排障。后续提交/push 仅用于源码备份，仍无发布授权。SIGKILL、断电、不响应 LIPC 不受 POSIX trap 保证。', '',
        '## 修改文件', '', '```text', status, '```', '', '```text', diff, '```', '',
    ]
    report = OUT / '5.18-vera-eattapmode-report.md'
    report.write_text('\n'.join(lines), encoding='utf-8')
    result = {'result': 'PASS', 'state': 'Pre-hardware candidate', 'hardware_verified': False,
              'start_sha': START, 'head_sha': head, 'branch': branch, 'suite_counts': counts,
              'checks': sum(counts.values()), 'stage_count': len(execution['stages']),
              'payload_changes': changed, 'production_source_changes': source_changes,
              'package': package, 'run_history': history, 'commit_performed': committed,
              'test_failures': failures, 'complete_runs': complete_runs,
              'push_performed': pushed, 'origin_tracking_sha': origin_head,
              'tag_created': False, 'release_published': False, 'pr_created': False}
    (OUT / '518-final-results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'report': str(report), 'checks': result['checks'], 'sha256': package['zip_sha256']}, ensure_ascii=True))

if __name__ == '__main__':
    main()
