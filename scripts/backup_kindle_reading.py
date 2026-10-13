"""Read an already mounted Kindle USB tree; copy/verify only plugin-owned files."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kindle_root',type=Path)
    parser.add_argument('backup',type=Path)
    args=parser.parse_args()
    source=args.kindle_root.resolve(); destination=args.backup.resolve()
    if not (source/'reading-time/reading-time.tsv').is_file(): parser.error('reading-time.tsv not found in the mounted Kindle root')
    if destination==source or destination.is_relative_to(source): parser.error('backup must be on the computer, outside the Kindle tree')
    if destination.exists(): parser.error('choose a new backup directory; existing backups are never overwritten')
    files=list((source/'reading-time').rglob('*'))
    files.extend(source/'documents'/name for name in ('阅读记录.sh','reading-records-ks-force-exit.sh'))
    files.extend((source/'documents').glob('reading-records-evidence-*.txt'))
    if any(p.is_symlink() for p in files): parser.error('unexpected symbolic link; inspect before backing up')
    destination.mkdir(parents=True)
    hashes={}
    for file in files:
        if not file.is_file(): continue
        relative=file.relative_to(source); copied=destination/relative
        copied.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,copied)
        digest=hashlib.sha256(file.read_bytes()).hexdigest()
        if hashlib.sha256(copied.read_bytes()).hexdigest()!=digest: raise RuntimeError(f'backup verification failed: {relative}')
        hashes[relative.as_posix()]=digest
    (destination/'backup-manifest.json').write_text(json.dumps({'source':str(source),'files':hashes,'verified':True,'system_config':'USB cannot expose /etc; save the read-only evidence report separately'},ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Verified {len(hashes)} files in {destination}')


if __name__=='__main__': main()
