"""Verify final bytes and report only completed candidate validation evidence."""
from pathlib import Path
import ast, datetime, hashlib, io, json, subprocess, sys, tarfile, zipfile
from package_release import ARCHIVE, BOOTSTRAP, PAYLOAD, VERSION, cksum
from validate_all import CHECKS

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/validation'
AUDIT=ROOT/'build/springbreak-audit'
BASE='3acda144ee7bf3a09d7472628efdffd9c09ab240'
REPORTS=['results.json','stats-filters-results.json','day-detail-results.json','period-detail-results.json',
         'book-detail-results.json','cover-fallback-results.json','audit-results.json','installer-results.json',
         'runtime-results.json','518-eattapmode-results.json','pre-hardware-results.json','final-freeze-results.json',
         'springbreak-candidate-results.json']

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def members(raw):
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        entries=archive.getmembers()
        assert len({m.name for m in entries})==len(entries)
        assert all(m.isfile() and m.name.startswith('native-reading-time-package/') and '..' not in m.name for m in entries)
        return {m.name.split('/',1)[1]:archive.extractfile(m).read() for m in entries}

def main():
    suite=json.loads((OUT/'suite-results.json').read_text(encoding='utf-8'))
    assert suite['result']=='PASS' and suite['complete']
    assert [r['script'].replace('\\','/') for r in suite['stages']]==[p.relative_to(ROOT).as_posix() for p in CHECKS]
    counts={}
    for name in REPORTS:
        result=json.loads((OUT/name).read_text(encoding='utf-8'))
        assert result.get('result','PASS')=='PASS'
        assert all(not isinstance(c,dict) or c['result']=='PASS' for c in result['checks'])
        counts[name]=len(result['checks'])
    result=json.loads((AUDIT/'input-evidence.json').read_text(encoding='utf-8'))
    assert result['result']=='PASS';counts['input-evidence.json']=len(result['checks'])
    touch=json.loads((ROOT/'build/test2-audit/touch-results.json').read_text(encoding='utf-8'))
    assert touch['result']=='PASS' and all(c['result']=='PASS' for c in touch['checks'])
    counts['touch-results.json']=len(touch['checks'])
    package=json.loads((OUT/'package-results.json').read_text(encoding='utf-8'))
    assert package['version']==VERSION and package['zip_sha256']==sha(ARCHIVE.read_bytes())
    with zipfile.ZipFile(ARCHIVE) as archive:
        assert archive.namelist()==[BOOTSTRAP,PAYLOAD] and archive.testzip() is None
        boot,raw=archive.read(BOOTSTRAP),archive.read(PAYLOAD)
    files=members(raw)
    assert set(files)==set(package['files']) and len(files)==65
    for name,data in files.items():
        assert sha(data)==package['files'][name]['sha256']
        if name!='payload-manifest.tsv':assert data==(ROOT/'native-reading-time-package'/name).read_bytes(),name
    manifest=files['payload-manifest.tsv'].decode().splitlines()
    assert len(manifest)==len(files)-1
    for line in manifest:
        checksum,size,name=line.split('\t');assert cksum(files[name])==(int(checksum),int(size))
    checksum,size=cksum(raw)
    assert (checksum,size)==(package['payload_cksum'],package['payload_bytes'])
    assert sha(raw)==package['payload_sha256']
    template=(ROOT/'documents'/BOOTSTRAP).read_bytes()
    assert boot==template.replace(b'@PAYLOAD_CKSUM@',str(checksum).encode()).replace(b'@PAYLOAD_SIZE@',str(size).encode())
    baseline=AUDIT/'baseline/ReadingTime-9.7.6-5.18-vera.zip'
    assert sha(baseline.read_bytes())=='2b2ad142542295627cfd7a6e4870dcff28d4445088320a728f46887af100693d'
    with zipfile.ZipFile(baseline) as archive:old=members(archive.read(PAYLOAD))
    assert files.keys()==old.keys()
    changed=[name for name in sorted(files) if files[name]!=old[name]]
    assert changed==['install.sh','launch.sh','payload-manifest.tsv','resources/reading-records-install-cleanup.sh','阅读记录-optimized.sh','阅读记录.sh'],changed
    # Preserve and compare the exact Test 1 artifact, not a reconstruction.
    test2_audit=ROOT/'build/test2-audit'
    before=json.loads((test2_audit/'before.json').read_text(encoding='utf-8'))
    test1=test2_audit/'ReadingTime-9.7.6-5.18-springbreak-kpw4-test1.zip'
    assert sha(test1.read_bytes())==before['test1_zip_sha256']=='11bf3309d509685e841a9ec39d76a831d717d2f020ac142343f253a2c372262d'
    assert sha((ROOT/'dist'/test1.name).read_bytes())==before['test1_zip_sha256']
    with zipfile.ZipFile(test1) as archive:prior=members(archive.read(PAYLOAD))
    assert prior.keys()==files.keys()
    test1_changes=[name for name in sorted(files) if files[name]!=prior[name]]
    assert test1_changes==changed
    sys.path.insert(0,str(ROOT/'tests'))
    from springbreak_contract import TOUCH_BLOCK
    for name in changed:
        if name=='payload-manifest.tsv':continue
        current=files[name].decode();previous=prior[name].decode()
        if name.startswith('阅读记录'):
            assert current.count(TOUCH_BLOCK)==1
            old_selector=previous[previous.index('find_touch_device() {'):previous.index('scale_len() {')]
            current=current.replace(TOUCH_BLOCK,old_selector)
        assert current.replace(VERSION,'9.7.6-5.18-springbreak-kpw4-test1')==previous,name
    template1=(test2_audit/'test1-source/documents'/BOOTSTRAP).read_bytes()
    assert template.replace(VERSION.encode(),b'9.7.6-5.18-springbreak-kpw4-test1')==template1
    assert git('show-ref').decode()==before['refs']
    for path,status_before in before['other_worktrees'].items():
        assert subprocess.check_output(['git','status','--porcelain=v1'],cwd=path).decode()==status_before,path
    # No historical test assert is removed. Target-specific expectations are
    # explicitly updated; broad parser tests execute pinned historical source.
    integrity={}
    for path in filter(None,git('ls-tree','-rz','--name-only',BASE,'tests').decode().split('\0')):
        if not path.endswith('.py'):continue
        old_ast=ast.parse(git('show',BASE+':'+path).decode())
        new_ast=ast.parse((ROOT/path).read_text(encoding='utf-8'))
        old_count=sum(isinstance(n,ast.Assert) for n in ast.walk(old_ast))
        new_count=sum(isinstance(n,ast.Assert) for n in ast.walk(new_ast))
        assert new_count>=old_count,(path,old_count,new_count)
        integrity[path]={'baseline_asserts':old_count,'candidate_asserts':new_count}
    branch=git('branch','--show-current').decode().strip();head=git('rev-parse','HEAD').decode().strip()
    assert branch=='9.7.6-5.18-springbreak-kpw4' and head==BASE
    assert git('rev-parse','9.7.6-5.18-vera').decode().strip()==BASE
    assert git('rev-parse','9.7.6-5.19-vera').decode().strip().startswith('341ee3d')
    # Snapshot other branch/worktree state read-only. Nothing is committed.
    worktrees=git('worktree','list','--porcelain').decode()
    status=git('status','--short').decode()
    history=json.loads((AUDIT/'run-history.json').read_text(encoding='utf-8'))
    assert history['runs'][-1]['command']=='python scripts/validate_all.py' and history['runs'][-1]['status']=='PASS'
    assert history['runs'][-1]['version']==VERSION
    development=json.loads((test2_audit/'development-notes.json').read_text(encoding='utf-8'))
    static=json.loads((test2_audit/'static-results.json').read_text(encoding='utf-8'))
    assert static['result']=='PASS' and static['other_worktrees_and_refs_unchanged']
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds')
    payload_sha=package['payload_sha256'];zip_sha=package['zip_sha256']
    (ARCHIVE.parent/(ARCHIVE.stem+'.sha256.txt')).write_text(zip_sha+'  '+ARCHIVE.name+'\n',encoding='ascii')
    final={'result':'PASS','state':'Pre-hardware candidate','hardware_verified':False,'base':BASE,'head':head,'branch':branch,
           'checks':sum(counts.values()),'case_counts':counts,'stages':len(suite['stages']),
           'suite':suite,'package':package,'payload_changes':changed,'test1_payload_changes':test1_changes,'test_assert_integrity':integrity,
           'test1_zip_sha256':before['test1_zip_sha256'],'other_worktrees_and_refs_unchanged':True,
           'run_history':history,'development_notes':development,'static_audit_vs_test1':static,
           'reported_at':now,'commit_push_tag_pr_release_performed':False}
    (OUT/'springbreak-final-results.json').write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# KPW4 / 5.18.1.1.1 / SpringBreak 本地候选交付报告','',
        f'生成：{now}（Asia/Shanghai）。**Pre-hardware candidate，尚无真机兼容成功证据。**','',
        f'独立分支 `{branch}`，HEAD/起点 `{head}`，工作树 `{ROOT}`。远端基线已核对。未提交、push、tag、merge、PR 或发布。','',
        '## 交付包','',f'ZIP：`{ARCHIVE.resolve()}`','',f'大小：{package["zip_bytes"]:,} bytes；SHA-256：`{zip_sha}`','',
        f'TAR：{size:,} bytes；POSIX cksum：{checksum}；SHA-256：`{payload_sha}`。{len(files)} 个 regular 条目，manifest 每项、bootstrap 整体 checksum/size、源字节、ZIP CRC 和两文件顶层重新核对。','',
        f'顶层仅 `{BOOTSTRAP}`、`{PAYLOAD}`。SHA-256 文本留在开发目录外层，不进入用户 ZIP。','',
        '## 测试','',f'完整命令 `python scripts/validate_all.py`：{len(suite["stages"])} 阶段全部 PASS、complete=true，{sum(counts.values())} 项。所有原 stage 和 assert 保留。','',
        '| 结果文件 | PASS 项数 |','|---|---:|',*[f'| {name} | {count} |' for name,count in counts.items()],
        f'| 合计 | {sum(counts.values())} |','',
        '原宽 5.18 parser 固定历史源回归保留；新分支精确固件及 21 个可靠型号代码另由实际当前安装器验证。原新装、覆盖升级、repair、rollback、清理、信号、锁、历史/封面/缓存/日志断言继续针对候选运行。真实最新 Vera 包及精确 Test 1 ZIP 均验证升级失败回滚和重试/repair/清理。新增两版 sh/dash 选择器及已安装完整 UI 的真实 KPW4 布局矩阵。','',
        '长 UI 超时模拟只加速 mock sleep；真实 sleep/2 秒字面量另验证 reader 回收。内核/LIPC/SIGKILL/断电不受离线保证。未执行真实 fbink -e 或崩溃二进制，139 为模拟返回码。','',
        '测试工具开发阶段的失败及修正如实记录，历史 Test 1 记录保留；不计为真机失败：','',
        '```json',json.dumps(history,ensure_ascii=False,indent=2),'```','',
        'Test 2 工具适配记录（Windows link fixture 和历史严格 selector 断言；后续完整结果另列）：','',
        '```json',json.dumps(development,ensure_ascii=False,indent=2),'```','',
        '## 结论及使用','',
        'Test 1 真机安装及首次优化绘制成功：2590ms / fbink_calls=5 / fallback=0。FBInk、字体及绘制代码不变，无 -e 启动探测；其他绘制/刷新路径仍需真机确认。','',
        '真实 sysfs event0=20cc000.snvs、event1=bd71827-power、event2=goodix-ts，证实 Test 1 漏识别并错误回退。两版离线复现旧故障，当前两版动态识别 goodix-ts 并选择 event2；不写死编号。正向匹配、power/snvs 排除、字符/非链接/可读节点校验用于自动扫描和 override；失败立即明确错误退出。原名称规则全部回归。','',
        'Lua 及坐标未改。16 字节 ABS/MT/SYN_REPORT 组合 fixture 通过，真实 goodix 事件格式与坐标没有原始证据。保留 Test 1 的 120 秒父 launcher 退出、统一清理和状态恢复、锁、事务及日志；仅同步 Test 2 身份。','',
        '静态审计、生产改动与边界：`docs/springbreak-kpw4-audit.md`。简单中文说明：`docs/中文说明.md`。失败保留两个安装文件，不点清理，不删除 reading-time；只复制 dashboard-launch.log、dashboard-touch.log、display-layout.txt、install-last.log，服务异常再补 service.log/upstart.log。','',
        '实机仍需确认 goodix-ts 的按钮动作、正常与到期退出、原生触摸/方向/休眠恢复、后续刷新。无需用户执行命令或替换系统依赖。','',
        '## 最终源码状态','', '```text',status,'```','', '```text',worktrees,'```','',
        '归档相对精确 Vera 包以及保留 Test 1 包只改变下列条目，其他 payload 字节保持一致；相对 Test 1 这五份脚本只允许身份同步及两版指定选择器替换：','',*[f'- `{name}`' for name in changed],'',
    ]
    report=OUT/'springbreak-final-report.md';report.write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'report':str(report.resolve()),'checks':sum(counts.values()),'stages':len(suite['stages']),'zip_bytes':package['zip_bytes'],'sha256':zip_sha},ensure_ascii=True))

if __name__=='__main__':main()
