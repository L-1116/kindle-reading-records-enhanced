"""All Scribe generations and future-year model names; no year whitelist."""
from pathlib import Path
import json, os, re, shutil, subprocess, tempfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/ks-test1-audit'
OUT.mkdir(parents=True, exist_ok=True)
SH = shutil.which('sh') or 'C:/Program Files/Git/bin/sh.exe'
SHELLS = [SH, 'C:/Program Files/Git/usr/bin/dash.exe'] if os.name == 'nt' else [SH, shutil.which('dash')]
COMMON = ROOT / 'native-reading-time-package/compat/device_variant.sh'
GUARD = ROOT / 'ks-package/native-reading-time-package/compat/ks_guard.sh'
cases = []
codes = ['27J','2BL','263','227','2BM','23L','23M','270','3V0','3V1','3X5','3UV','3X4','3X3','41E','41D','4PG','4PE','4PL','4F8','4FA','454','4VX','4PF','4PH','4F9','4FB','46P']
for code in codes:
    cases.append(('known Scribe code ' + code, '', 'G0G' + code + 'PRIVATE_SUFFIX', '', '', True))
for name in ['Kindle Scribe', 'Kindle Scribe 2022', 'Kindle Scribe 2024', 'Kindle Scribe 2025',
             'Kindle Scribe 2026', 'Kindle Scribe 2030', 'Kindle Scribe Colorsoft', 'KS', 'KS2035']:
    cases.append(('model ' + name, name, 'G0GZZZPRIVATE_SUFFIX', '', '', True))
cases.extend([
    ('missing model but tree Scribe', None, '', 'Amazon Kindle Scribe 2036\0', '', True),
    ('missing model and USID but sys tree Scribe', None, '', '', 'Kindle Scribe 2040', True),
    ('ordinary Colorsoft', 'Kindle Colorsoft', 'G0G3H9PRIVATE_SUFFIX', '', '', False),
    ('Paperwhite', 'KPW6', '', '', '', False),
    ('unknown all sources', None, '', '', '', False),
    ('model/USID conflict', 'Kindle Scribe', 'G0G349PRIVATE_SUFFIX', '', '', False),
    ('tree conflict', 'Kindle Scribe', '', 'Kindle Paperwhite', '', False),
    ('malformed USID but Scribe name', 'Kindle Scribe 2040', 'invalid!', '', '', True),
    ('Scribe code shortened suffix', None, 'G0G27J', '', '', True),
    ('Scribe code NUL suffix', None, 'G0G27J\0anything', '', '', True),
])
results = []
for shell in SHELLS:
    assert shell and Path(shell).is_file(), shell
    for label, model, usid, proc_model, sys_model, expected in cases:
        with tempfile.TemporaryDirectory(dir=OUT) as directory:
            folder = Path(directory)
            base = folder / 'reading-time'; base.mkdir()
            env = {**os.environ, 'PATH': '/usr/bin:/bin', 'BASE': base.as_posix()}
            for key, filename, content in [('READING_DEVICETYPE_PATH','device',model), ('READING_USID_PATH','usid',usid),
                                           ('READING_PROC_MODEL_PATH','proc-model',proc_model), ('READING_SYS_MODEL_PATH','sys-model',sys_model)]:
                env[key] = (folder / filename).as_posix()
                if content is not None:
                    (folder / filename).write_bytes(content.encode())
            body = '. "$1"\n. "$2"\nrr_device_log() { printf "%s\\n" "$*"; }\nrr_ks_install_guard\n'
            result = subprocess.run([shell, '-c', body, 'fixture', COMMON.as_posix(), GUARD.as_posix()], env=env, capture_output=True, timeout=8)
            assert (result.returncode == 0) == expected, (label, result.stdout, result.stderr)
            assert b'PRIVATE_SUFFIX' not in result.stdout + result.stderr
            results.append({'shell':Path(shell).name, 'case':label, 'result':'PASS'})
(OUT / 'devices.json').write_text(json.dumps({'result':'PASS','checks':results}, indent=2), encoding='utf-8')
print('KS all-generations and unknown-year eligibility:', len(results), 'PASS')
