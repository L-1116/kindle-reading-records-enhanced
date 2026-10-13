"""Validate and deliver the Standard device-identification test without publication."""
from pathlib import Path
import datetime, hashlib, io, json, subprocess, tarfile, zipfile
from build_v4 import ROOT, PRODUCT_VERSION, RUNTIME_VERSION, SIMPLE_ARCHIVE, BOOT_NAME, TAR_NAME, sources, posix_cksum

AUDIT=ROOT/'build/standard-test2-audit'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def unpack(path):
    with zipfile.ZipFile(path) as z:
        assert z.namelist()==[BOOT_NAME,TAR_NAME] and z.testzip() is None
        boot=z.read(BOOT_NAME); raw=z.read(TAR_NAME)
    with tarfile.open(fileobj=io.BytesIO(raw)) as t:
        assert all(m.isfile() and not m.issym() and not m.islnk() for m in t)
        files={m.name:t.extractfile(m).read() for m in t}
    return boot,raw,files

def main():
    assert PRODUCT_VERSION=='9.7.6-5.20.1-vera-test2'
    protected=read(AUDIT/'protected-before.json')
    for name,sha in {**protected['files'],**protected['ks_support_files']}.items():assert digest(ROOT/name)==sha,name
    assert subprocess.check_output(['git','show-ref','--tags'],cwd=ROOT).decode()==protected['tags']
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()==protected['head']
    ks_names={p.relative_to(ROOT).as_posix() for p in (ROOT/'ks-package').rglob('*') if p.is_file()}
    assert ks_names=={n for n in protected['files'] if n.startswith('ks-package/')}
    regression=read(AUDIT/'regression-results.json'); devices=read(AUDIT/'device-identification-results.json')
    installs=read(ROOT/'build/validation/standard-install-results.json')
    permissions=read(AUDIT/'device-permission-results.json')
    assert permissions['result']=='PASS' and len(permissions['checks'])==6
    assert regression['result']==devices['result']==installs['result']=='PASS'
    assert len(regression['checks'])==12 and all(r['exit_code']==0 for r in regression['checks'])
    package_sha=digest(SIMPLE_ARCHIVE)
    assert regression['package_sha256']==package_sha
    assert devices['package_sha256']==package_sha
    assert all(r['package_sha256']==package_sha for r in installs['checks'])
    boot,raw,current=unpack(SIMPLE_ARCHIVE)
    assert current==sources('standard')
    assert (ROOT/'native-reading-time-package/compat/device_variant.sh').read_bytes() in boot
    assert b'@DEVICE_VARIANT@' not in boot and b'@RUNTIME_VERSION@' not in boot
    assert f"PRODUCT_VERSION='{PRODUCT_VERSION}'".encode() in boot and f"RUNTIME_VERSION='{RUNTIME_VERSION}'".encode() in boot
    assert f"PAYLOAD_CKSUM='{posix_cksum(raw)}'".encode() in boot
    identity=dict(line.split('=',1) for line in current['BUILD-INFO'].decode().splitlines())
    assert identity['variant']=='standard' and identity['product_version']==PRODUCT_VERSION
    _,_,formal=unpack(ROOT/'build/formal-candidate/9.7.6-5.20.1-vera.zip')
    differences=[n for n in sorted(set(current)|set(formal)) if current.get(n)!=formal.get(n)]
    allowed={'README.txt','V4-PAYLOAD','BUILD-INFO','PACKAGE-MANIFEST.json','v4/cleanup.sh',
        'native-reading-time-package/migration-manifest.tsv','native-reading-time-package/install.sh',
        'native-reading-time-package/compat/device_variant.sh'}
    assert set(differences)==allowed,differences
    # This asserts every UI, renderer, touch helper, daemon, service, launcher,
    # environment detector and lifecycle helper is exactly the released bytecode/source.
    protected_runtime=[n for n in formal if n.startswith('native-reading-time-package/') and n not in allowed]
    assert all(current[n]==formal[n] for n in protected_runtime)
    target=ROOT/'dist/standard-test2'/SIMPLE_ARCHIVE.name
    target.parent.mkdir(exist_ok=True)
    assert not target.exists(),'Never overwrite an existing test package'
    with target.open('xb') as f:f.write(SIMPLE_ARCHIVE.read_bytes())
    assert digest(target)==package_sha and current==sources('standard')
    report={'result':'OFFLINE_PASS_HARDWARE_PENDING','generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'product_version':PRODUCT_VERSION,'runtime_version':RUNTIME_VERSION,'variant':'standard','build_id':identity['build_id'],
        'zip_path':str(target),'zip_bytes':target.stat().st_size,'zip_sha256':package_sha,'zip_top_level':[BOOT_NAME,TAR_NAME],
        'regression_checks':len(regression['checks']),'device_identification_cases':len(devices['checks']),
        'denied_read_permission_cases':len(permissions['checks']),
        'installation_migration_rollback_cleanup_cases':len(installs['checks']),
        'changed_payload_files':differences,'unchanged_runtime_files':len(protected_runtime),
        'formal_and_test1_preserved':True,'ks_workspace_preserved':True,'tags_and_head_preserved':True,
        'publication_actions':[], 'hardware_pending':['KC 5.20.1 actual install, FBInk, display, touch, native timing and resume',
            'other 5.20.1 device actual install and identify model without personal serial data','KPW6 5.20.1 timing recovery and startup regression']}
    (AUDIT/'final-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (AUDIT/'SHA256SUMS.txt').write_text(package_sha+'  '+target.name+'\n',encoding='ascii')
    doc=ROOT/'docs/standard-test2-device-identification.md'
    text=doc.read_text(encoding='utf-8')
    text+=f"\n## 最终离线结果\n\n状态：离线通过，真实设备待验证。\n\n构建：`{identity['build_id']}`；ZIP：`{target.relative_to(ROOT).as_posix()}`；大小：{target.stat().st_size} 字节。\n\nSHA-256：`{package_sha}`。\n\n设备识别/入口测试 {len(devices['checks'])} 个用例、6 个读取权限拒绝用例、原安装迁移/rollback/cleanup 的必要子集 {len(installs['checks'])} 个场景，以及 12 项相关 Standard 回归全部通过。新增设备测试包含两种 shell 的识别用例及各实际安装入口；成功安装场景保持原数据，拒绝场景不修改运行文件。生产运行 payload 的 {len(protected_runtime)} 个文件与已发布正式包逐字节一致。完整差异白名单、测试记录与保护校验见 `build/standard-test2-audit/final-validation.json`。本轮未重新运行所有无关统计/UI 检查，采用逐字节保护和与本次变更相关的必要回归；未把上轮结果称为本轮完整测试。\n"
    doc.write_text(text,encoding='utf-8',newline='\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
