"""Build a local standalone read-only collector, never a user installation ZIP."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def main():
    target = ROOT/'build/firmware-5201/reading-records-evidence.sh'
    target.parent.mkdir(parents=True,exist_ok=True)
    template = (ROOT/'debug/firmware-5201/reading-records-evidence.template.sh').read_text(encoding='utf-8')
    library = (ROOT/'native-reading-time-package/compat/lifecycle.sh').read_text(encoding='utf-8')
    # Ship only timeout helpers in this collector. It cannot repair/mount/lock.
    library = library[:library.index('rr_identity()')]
    target.write_text(template.replace('@LIFECYCLE@',library),encoding='utf-8',newline='\n')
    target.chmod(0o755)
    print(target)


if __name__=='__main__': main()
