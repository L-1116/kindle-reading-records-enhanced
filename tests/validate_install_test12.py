"""Exact test12 transactions using isolated real historical installers."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import argparse,hashlib,json,os,tempfile,time,traceback
if os.name=='nt':os.environ.setdefault('READING_TEST_INSTALL_TIMEOUT','300')
from validate_v4 import run,ROOT,SIMPLE_ARCHIVE
OUT=ROOT/'build/validation/install-test12';OUT.mkdir(exist_ok=True)
CASES=[(None,'',True),('9.8.1-test10','',True),('9.8.1-test10-cleaned','',True),
 ('9.8.1-test11','',True),('9.8.1-test11-cleaned','',True),('9.8.1-test11','legacy_diagnostics',True)]
CASES += [('9.8.1-test11',f,False) for f in ('core_failure','activation_failure','interrupted','ks_residue','wrong_device','busy_ui')]
def execute(case):
    previous,fault,cleanup=case;started=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='transactions-final-',dir=OUT) as tmp:
        row=run(Path(tmp),previous=previous,mutation=fault,cleanup=cleanup)
        if fault=='activation_failure':
            assert (Path(tmp)/'us/reading-time/install-logs/last-install-diagnostic.txt').is_file()
    row['elapsed_seconds']=round(time.monotonic()-started,2)
    return row
def key(case):return str(case[0] or 'fresh')+' '+case[1]
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--jobs',type=int,default=1,choices=(1,2,3))
    parser.add_argument('--resume',action='store_true');args=parser.parse_args()
    path=OUT/'transaction-final-results.json'
    candidate=hashlib.sha256(SIMPLE_ARCHIVE.read_bytes()).hexdigest();rows={}
    if args.resume and path.exists():
        raw=path.read_bytes();(OUT/('transaction-final-attempt-'+str(time.time_ns())+'.json')).write_bytes(raw)
        rows={r['scenario']:r for r in json.loads(raw)['checks'] if r['result']=='PASS' and r['package_sha256']==candidate}
    def save():
        path.write_text(json.dumps({'result':'RUNNING','candidate_sha256':candidate,'checks':list(rows.values()),'hardware_verified':False},indent=2)+'\n',encoding='utf-8')
    pending=[c for c in CASES if key(c) not in rows];save();errors=[]
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures={pool.submit(execute,c):c for c in pending}
        for future in as_completed(futures):
            c=futures[future]
            try:
                row=future.result();assert row['package_sha256']==candidate
                rows[key(c)]=row;print(key(c),'PASS',flush=True)
            except Exception:
                errors.append(key(c));print('FAIL:',key(c),traceback.format_exc(),flush=True)
            save()
    assert not errors,errors
    assert len(rows)==len(CASES)
    path.write_text(json.dumps({'result':'PASS','candidate_sha256':candidate,'checks':[rows[key(c)] for c in CASES],'hardware_verified':False},indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()

