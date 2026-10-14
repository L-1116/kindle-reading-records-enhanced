"""Freeze the tested KS ZIP, verify protected files, and deliver locally."""
from pathlib import Path
import datetime, difflib, hashlib, io, json, subprocess, tarfile, zipfile
from build_ks_test1 import ROOT, ARCHIVE, PRODUCT_VERSION, RUNTIME_VERSION, BOOT_NAME, TAR_NAME, sources, posix_cksum

OUT=ROOT/'build/ks-test1-audit'
BASELINE=ROOT/'build/ks-5201-test1-baseline'

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    baseline=read(BASELINE/'before.json')
    changed=[]
    for name,before in baseline['files'].items():
        now=digest(ROOT/name)
        if before!=now:changed.append(name)
        if name.startswith(('native-reading-time-package/','v4/')):assert before==now,name
    for name,before in baseline['artifacts'].items():assert digest(ROOT/name)==before,name
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()==baseline['head']
    assert subprocess.check_output(['git','show-ref','--tags'],cwd=ROOT).decode()==baseline['tags']
    # Protect every KS UI/resource/touch file; only its lifecycle shell changed.
    allowed={
        'ks-package/native-reading-time-package/install.sh',
        'ks-package/native-reading-time-package/Install-Native-Reading-Time-KS.sh',
        'ks-package/native-reading-time-package/launch-ks.sh',
        'ks-package/native-reading-time-package/diagnostics-ks.sh',
        'ks-package/native-reading-time-package/阅读记录-KS-entry.sh',
        'tests/validate_ks_install.py','tests/validate_ks_compat_sync.py',
    }
    assert set(changed)<=allowed,changed
    regression=read(OUT/'regression.json')
    assert regression['result']=='PASS' and len(regression['checks'])==12
    assert all(row['exit_code']==0 for row in regression['checks'])
    for name,sha in regression['source_hashes'].items():assert digest(ROOT/name)==sha,name
    package_sha=digest(ARCHIVE)
    assert package_sha==regression['package_sha256']
    installations=read(OUT/'installation.json'); devices=read(OUT/'devices.json')
    framebuffer=read(OUT/'framebuffer.json'); service=read(OUT/'service-recovery-results.json')
    launcher=read(OUT/'launcher.json')
    for report in [installations,devices,framebuffer,service,launcher]:assert report['result']=='PASS'
    assert installations['package_sha256']==package_sha and len(installations['checks'])==26
    assert all(row['package_sha256']==package_sha for row in installations['checks'])
    with zipfile.ZipFile(ARCHIVE) as archive:
        assert archive.namelist()==[BOOT_NAME,TAR_NAME] and archive.testzip() is None
        boot=archive.read(BOOT_NAME);raw=archive.read(TAR_NAME)
    assert b'# DontUseFBInk' in boot.splitlines()[:6]
    assert f"PRODUCT_VERSION='{PRODUCT_VERSION}'".encode() in boot
    assert f"PAYLOAD_CKSUM='{posix_cksum(raw)}'".encode() in boot
    assert not any(key in boot for key in [b'@DEVICE_VARIANT@',b'@LIFECYCLE@',b'@VARIANT@'])
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        assert all(m.isfile() and not m.issym() and not m.islnk() for m in archive)
        files={m.name:archive.extractfile(m).read() for m in archive}
    assert files==sources(),'Final payload must equal current source builder'
    manifest=json.loads(files['PACKAGE-MANIFEST-KS.json'])
    assert manifest['variant']=='ks' and manifest['product_version']==PRODUCT_VERSION
    for item in manifest['files']:
        data=files[item['path']]
        assert len(data)==item['size'] and hashlib.sha256(data).hexdigest()==item['sha256']
    assert not any(data.startswith(b'\x7fELF') for data in files.values())
    identity=dict(line.split('=',1) for line in files['BUILD-INFO'].decode().splitlines())
    assert identity['variant']=='ks' and identity['product_version']==PRODUCT_VERSION
    target=ROOT/'dist/ks-test1'/ARCHIVE.name
    target.parent.mkdir(parents=True,exist_ok=True)
    assert not target.exists(),'Never overwrite an existing delivery'
    with target.open('xb') as output:output.write(ARCHIVE.read_bytes())
    assert digest(target)==package_sha
    # Self-inventory exclusion keeps a future rebuild deterministic.
    assert files==sources(),'Delivered candidate must not become self-referential ownership'
    report={'result':'OFFLINE_PASS_KS_HARDWARE_PENDING','generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'product_version':PRODUCT_VERSION,'variant':'ks','runtime_release':RUNTIME_VERSION,'build_id':identity['build_id'],
        'zip_path':str(target),'zip_bytes':target.stat().st_size,'sha256':package_sha,'zip_top_level':[BOOT_NAME,TAR_NAME],
        'regression_checks':12,'device_cases':len(devices['checks']),'installation_cases':26,
        'framebuffer_ui_cases':len(framebuffer['checks']),'service_cases':len(service['checks']),'launcher_cases':len(launcher['checks']),
        'modified_existing_files':changed,'standard_and_shared_production_unchanged':True,
        'existing_archives_preserved':len(baseline['artifacts']),'ks_touch_ui_assets_unchanged':True,'head_and_tags_unchanged':True,
        'publication_actions':[],
        'hardware_pending':['KS 5.20.1/Vera actual first install and upgrade','different Scribe generations, including color panels',
            'native reader detection and actual new TSV writes','book index convergence after migration and cleanup',
            'touch/display/rotation/exit/suspend/resume','click-to-visible startup latency and standby consumption']}
    (OUT/'final-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'SHA256SUMS.txt').write_text(package_sha+'  '+target.name+'\n',encoding='ascii')
    patch=[]
    for name in changed:
        old=(BASELINE/'source'/name).read_text(encoding='utf-8').splitlines(keepends=True)
        new=(ROOT/name).read_text(encoding='utf-8').splitlines(keepends=True)
        patch.extend(difflib.unified_diff(old,new,fromfile='a/'+name,tofile='b/'+name))
    new_files=[p for folder in ['ks-package/v4','ks-package/native-reading-time-package/compat'] for p in (ROOT/folder).rglob('*') if p.is_file() and p.relative_to(ROOT).as_posix() not in baseline['files']]
    new_files.extend(ROOT/name for name in ['scripts/build_ks_test1.py','scripts/ks_migration_inventory.py','scripts/validate_ks_test1.py',
        'scripts/finalize_ks_test1.py','tests/validate_ks_test1_devices.py','tests/validate_ks_test1_install.py',
        'tests/validate_ks_test1_runtime.py','tests/validate_ks_test1_launcher.py','docs/ks-5201-test1.md'])
    for path in new_files:
        patch.extend(difflib.unified_diff([],path.read_text(encoding='utf-8').splitlines(keepends=True),fromfile='/dev/null',tofile='b/'+path.relative_to(ROOT).as_posix()))
    (OUT/'task-changes.patch').write_text(''.join(patch),encoding='utf-8',newline='\n')
    (OUT/'source-inventory.json').write_text(json.dumps({'existing_changes':changed,'new_files':[p.relative_to(ROOT).as_posix() for p in new_files]},ensure_ascii=False,indent=2),encoding='utf-8')
    doc=ROOT/'docs/ks-5201-test1.md'
    with doc.open('a',encoding='utf-8',newline='\n') as output:
        output.write(f"\n## 最终本地结果\n\n12 项 KS 验收检查全部通过：{len(devices['checks'])} 个设备资格用例、26 个最终包安装/回滚/清理场景、{len(framebuffer['checks'])} 个完整 UI/实际 framebuffer 命令场景、{len(service['checks'])} 个服务及实际 daemon 受控计时场景、3 个额外启动锁/电源状态场景；原 KS 触摸、横屏、布局与真实 Lua 渲染回归通过。所有硬件均为模拟，KS 真机尚待验证。\n\nZIP：`{target.relative_to(ROOT).as_posix()}`；{target.stat().st_size} 字节；build_id：`{identity['build_id']}`。\n\nSHA-256：`{package_sha}`。\n\n27 份既有 ZIP、Standard/共用生产源码、KS 原 UI/触摸/素材、HEAD 及 tags 保持不变。未提交、push、创建 tag 或发布。完整报告见 `build/ks-test1-audit/final-validation.json`。\n")
    subprocess.run(['git','diff','--check'],cwd=ROOT,check=True)
    print(json.dumps(report,ensure_ascii=True,indent=2))

if __name__=='__main__':main()
