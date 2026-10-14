"""Verify the renamed package without overstating historical test evidence."""
from pathlib import Path
import ast, hashlib, io, json, subprocess, sys, tarfile, zipfile
from package_release import ARCHIVE, BOOTSTRAP, PAYLOAD, VERSION, cksum
from validate_all import CHECKS
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from springbreak_archives import BASE, TESTED, TEST2, historical_zip, members, git_file
OUT=ROOT/'build/validation'
REPORTS=['results.json','stats-filters-results.json','day-detail-results.json','period-detail-results.json',
 'book-detail-results.json','cover-fallback-results.json','audit-results.json','installer-results.json',
 'runtime-results.json','518-eattapmode-results.json','pre-hardware-results.json','final-freeze-results.json',
 'springbreak-candidate-results.json','springbreak-naming-results.json']
def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def main():
 package=load(OUT/'package-results.json')
 assert package['version']==VERSION and package['zip_sha256']==sha(ARCHIVE.read_bytes())
 with zipfile.ZipFile(ARCHIVE) as z:
  assert z.namelist()==[BOOTSTRAP,PAYLOAD] and z.testzip() is None
  boot,raw=z.read(BOOTSTRAP),z.read(PAYLOAD)
 with tarfile.open(fileobj=io.BytesIO(raw)) as t:
  entries=t.getmembers();assert len(entries)==65 and len({m.name for m in entries})==65
  assert all(m.isfile() and m.name.startswith('native-reading-time-package/') and '..' not in m.name for m in entries)
 files=members(raw);assert files.keys()==package['files'].keys()
 for name,data in files.items():
  assert sha(data)==package['files'][name]['sha256'],name
  if name!='payload-manifest.tsv':assert data==(ROOT/'native-reading-time-package'/name).read_bytes(),name
 manifest=files['payload-manifest.tsv'].decode().splitlines();assert len(manifest)==64
 for line in manifest:
  checksum,size,name=line.split('\t');assert cksum(files[name])==(int(checksum),int(size))
 checksum,size=cksum(raw)
 assert (checksum,size)==(package['payload_cksum'],package['payload_bytes']) and sha(raw)==package['payload_sha256']
 template=(ROOT/'documents'/BOOTSTRAP).read_bytes()
 assert boot==template.replace(b'@PAYLOAD_CKSUM@',str(checksum).encode()).replace(b'@PAYLOAD_SIZE@',str(size).encode())
 tested_zip=historical_zip('test2')
 with zipfile.ZipFile(io.BytesIO(tested_zip)) as z:old=members(z.read(PAYLOAD))
 assert old.keys()==files.keys()
 for name,data in files.items():
  if name!='payload-manifest.tsv':assert data.replace(VERSION.encode(),TEST2.encode())==old[name],name
 assert template.replace(VERSION.encode(),TEST2.encode())==git_file(TESTED,'documents/'+BOOTSTRAP)
 evidence=load(ROOT/'docs/springbreak-test2-validation.json')
 assert evidence['checkpoint']==TESTED and evidence['checks']==709 and evidence['stages']==16
 assert evidence['zip_sha256']==sha(tested_zip) and evidence['offline_result']=='PASS'
 naming=load(OUT/'springbreak-naming-results.json')
 assert naming['result']=='PASS' and naming['version']==VERSION and naming['archive_sha256']==package['zip_sha256']
 assert all(c['result']=='PASS' for c in naming['checks'])
 suite=load(OUT/'suite-results.json') if (OUT/'suite-results.json').exists() else {}
 full_current=suite.get('version')==VERSION and suite.get('complete') and suite.get('result')=='PASS'
 counts={}
 if full_current:
  assert [r['script'].replace('\\','/') for r in suite['stages']]==[p.relative_to(ROOT).as_posix() for p in CHECKS]
  for name in REPORTS:
   data=load(OUT/name);assert data.get('result','PASS')=='PASS'
   assert all(not isinstance(c,dict) or c['result']=='PASS' for c in data['checks'])
   counts[name]=len(data['checks'])
  for path in [ROOT/'build/springbreak-audit/input-evidence.json',ROOT/'build/test2-audit/touch-results.json']:
   data=load(path);assert data['result']=='PASS';counts[path.name]=len(data['checks'])
 integrity={}
 for path in filter(None,git('ls-tree','-rz','--name-only',TESTED,'tests').decode().split('\0')):
  if not path.endswith('.py'):continue
  a=sum(isinstance(n,ast.Assert) for n in ast.walk(ast.parse(git_file(TESTED,path).decode())))
  b=sum(isinstance(n,ast.Assert) for n in ast.walk(ast.parse((ROOT/path).read_text(encoding='utf-8'))))
  assert b>=a,(path,a,b);integrity[path]={'test2_asserts':a,'current_asserts':b}
 for ref in (BASE,TESTED):subprocess.run(['git','merge-base','--is-ancestor',ref,'HEAD'],cwd=ROOT,check=True)
 assert git('branch','--show-current').decode().strip()==VERSION
 result={'result':'PASS','version':VERSION,'package':package,'tested_source':evidence,
  'runtime_delta':'Only version identity; all other runtime bytes match hardware-tested checkpoint.',
  'naming_checks':len(naming['checks']),'current_full_suite_verified':bool(full_current),
  'current_full_case_counts':counts,'test_assert_integrity':integrity,
  'hardware_feedback':'2026-10-14: user confirms this version runs successfully on one KPW4 / 5.18.1.1.1 / SpringBreak device; no broader hardware claim.',
  'head':git('rev-parse','HEAD').decode().strip(),'github_release_created':False}
 (OUT/'springbreak-final-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (ARCHIVE.parent/(ARCHIVE.stem+'.sha256.txt')).write_text(package['zip_sha256']+'  '+ARCHIVE.name+'\n',encoding='ascii')
 lines=[f'# {VERSION} 源码同步与包校验','',f'ZIP：`{ARCHIVE.resolve()}`',
  f'大小：{package["zip_bytes"]:,} bytes；SHA-256：`{package["zip_sha256"]}`。','',
  'ZIP CRC、两文件顶层、65 个 regular TAR 条目、manifest 全项、bootstrap 校验和/大小、源文件字节均通过。',
  f'Test 2 检查点 `{TESTED}`；原 ZIP SHA-256 `{evidence["zip_sha256"]}`。',
  '用户 2026-10-14 确认本版本在一台 KPW4 / 5.18.1.1.1 / SpringBreak 实机运行成功；未推断其他设备/固件或逐项异常场景均已通过。',
  '当前包除版本身份外全部运行字节与 Test 2 相同；120 秒保护、触摸/Lua/坐标/绘制/安装架构保持。',
  f'原 Test 2 完整离线回归：16 阶段 / 709 项 PASS。当前命名/精确 Test 2 升级专项：{len(naming["checks"])} 项 PASS。',
  f'当前名称完整回归单独核验：{bool(full_current)}'+(f'；{len(suite["stages"])} 阶段 / {sum(counts.values())} 项 PASS。' if full_current else '；不把历史全回归冒充当前重新执行。'),
  '全部 Test 2 测试文件 assert 数保留或增加；历史归档由固定 Git 重建并保持原 SHA，克隆后可重现。',
  '仅推送同名源码分支，不创建 GitHub Release、tag、PR 或 merge。','']
 (OUT/'springbreak-final-report.md').write_text('\n\n'.join(lines),encoding='utf-8')
 print(json.dumps({'result':'PASS','sha256':package['zip_sha256'],'current_full_suite_verified':bool(full_current),'naming_checks':len(naming['checks'])}))
if __name__=='__main__':main()
