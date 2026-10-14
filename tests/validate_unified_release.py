"""Release engineering safety tests; no Kindle access or GitHub writes."""
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import unified_release as release


class ArchiveTests(unittest.TestCase):
    def fixture(self):
        names = ['install.sh', 'install-manifest.txt', 'cleanup-manifest.txt', 'launch.sh',
                 'native-reading-time-daemon.sh', 'native-reading-time.conf', '阅读记录-optimized.sh',
                 '阅读记录.sh', 'reading-insights-touch-ui.lua', 'reading-insights-render.lua',
                 'launcher-icon.png', 'NotoSansCJKsc-Regular.otf']
        files = {release.PREFIX + n: b'fixture\n' for n in names}
        files[release.PREFIX + 'install.sh'] = b'9.7.6-5.19-normal 5.19.* no-mixed-install\n'
        source = dict(files)
        manifest = ''.join(f'{release.cksum(raw)}\t{len(raw)}\t{name.removeprefix(release.PREFIX)}\n'
                           for name, raw in sorted(files.items())).encode()
        files[release.PREFIX + 'payload-manifest.tsv'] = manifest
        template = '#!/bin/sh\n# Name: Install\nTAR=reading-records-data.tar\nEXPECTED_CKSUM=@PAYLOAD_CKSUM@\nEXPECTED_SIZE=@PAYLOAD_SIZE@\n'
        source['documents/reading-records-install.sh'] = template.encode()
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w') as t:
            for name, raw in sorted(files.items()):
                member = tarfile.TarInfo(name); member.size = len(raw)
                t.addfile(member, io.BytesIO(raw))
        payload = buffer.getvalue()
        boot = template.replace('@PAYLOAD_CKSUM@', str(release.cksum(payload))).replace('@PAYLOAD_SIZE@', str(len(payload))).encode()
        buffer = io.BytesIO()
        top = ['reading-records-install.sh', 'reading-records-data.tar']
        with zipfile.ZipFile(buffer, 'w') as z:
            z.writestr(top[0], boot); z.writestr(top[1], payload)
        raw = buffer.getvalue()
        v = dict(id='fixture', sha256=release.sha(raw), size=len(raw), top_level=top,
                 bootstrap_sha256=release.sha(boot), payload_sha256=release.sha(payload),
                 payload_files=len(files), variant='standard', source_commit='a' * 40,
                 format='standard-976', product_version='9.7.6-5.19-normal',
                 installer_markers=['5.19.*', 'no-mixed-install'])
        return raw, v, source

    def test_valid_legacy_source_bound_package(self):
        raw, v, source = self.fixture()
        with patch.object(release, 'blob', side_effect=lambda c, n: source[n]):
            self.assertTrue(release.verify_archive(raw, v)['source_commit_verified'])

    def test_changed_archive_rejected(self):
        raw, v, _ = self.fixture()
        with self.assertRaisesRegex(ValueError, 'approved bytes'):
            release.verify_archive(raw + b'changed', v)

    def test_wrong_firmware_markers_rejected(self):
        raw, v, _ = self.fixture(); v['installer_markers'] = ['5.20.1']
        with self.assertRaisesRegex(ValueError, 'guard mismatch'):
            release.verify_archive(raw, v)

    def test_ks_identity_rejected(self):
        raw, v, _ = self.fixture(); v['variant'] = 'ks'
        with self.assertRaisesRegex(ValueError, 'variant'):
            release.verify_archive(raw, v)

    def test_source_commit_mismatch_rejected(self):
        raw, v, source = self.fixture(); source[release.PREFIX + 'launch.sh'] = b'wrong branch'
        with patch.object(release, 'blob', side_effect=lambda c, n: source[n]):
            with self.assertRaisesRegex(ValueError, 'pinned source'):
                release.verify_archive(raw, v)

    def test_wrong_entry_rejected(self):
        raw, v, _ = self.fixture(); v['top_level'] = ['other.sh', 'data.tar']
        with self.assertRaisesRegex(ValueError, 'structure'):
            release.verify_archive(raw, v)

    def test_unsafe_paths_rejected(self):
        for name in ('../outside', '/absolute', 'C:/file', 'a\\b', './file', 'a/../b'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                release.safe_name(name)


class MatrixTests(unittest.TestCase):
    def altered(self, edit):
        matrix = release.read_json(release.DEFAULT_MATRIX); edit(matrix)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'matrix.json'; release.write_json(path, matrix)
            return release.load_matrix(path)

    def test_unified_tag_required(self):
        with self.assertRaisesRegex(ValueError, 'canonical tag'):
            self.altered(lambda m: m.update(tag='v9.7.6-5.19-vera'))

    def test_automated_cannot_become_formal(self):
        with self.assertRaisesRegex(ValueError, 'hardware evidence'):
            self.altered(lambda m: m['variants'][3].update(publish=True))

    def test_duplicate_name_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            self.altered(lambda m: m['variants'].append({**m['variants'][0], 'id': 'collision'}))

    def test_older_product_not_relabelled(self):
        with self.assertRaisesRegex(ValueError, 'older product'):
            self.altered(lambda m: m['variants'][0].update(product_version='9.7.5-KS-test1'))

    def test_notes_list_only_approved_files(self):
        m = release.load_matrix(release.DEFAULT_MATRIX)
        text = release.notes(m, [v for v in m['variants'] if v['publish']])
        self.assertNotIn(m['variants'][3]['asset_name'], text)
        self.assertNotIn(m['variants'][4]['asset_name'], text)
        for v in m['variants'][:3]:
            self.assertIn(v['sha256'] + '  ' + v['asset_name'], text)
            self.assertIn(v['source_commit'], text)
        self.assertIn('Source code', text)

    def test_default_dry_run_has_no_remote_writes(self):
        m = release.load_matrix(release.DEFAULT_MATRIX)
        with tempfile.TemporaryDirectory() as d:
            def approved(v, *args): return v['id'].encode()
            with patch.object(release, 'resolve_archive', side_effect=approved), \
                 patch.object(release, 'verify_archive', return_value={'fixture': True}), \
                 patch.object(release, 'gh') as gh:
                release.prepare(m, Path(d) / 'out', {})
                gh.assert_not_called()

    def test_dirty_output_and_changed_staging_rejected(self):
        m = release.load_matrix(release.DEFAULT_MATRIX)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d); (out / 'old-test.zip').write_bytes(b'old')
            with self.assertRaisesRegex(ValueError, 'unexpected'):
                release.prepare(m, out, {})
        with tempfile.TemporaryDirectory() as d:
            out = Path(d); (out / 'RELEASE.md').write_bytes(b'stale')
            with patch.object(release, 'resolve_archive', return_value=b'fixture'), \
                 patch.object(release, 'verify_archive', return_value={}):
                with self.assertRaisesRegex(ValueError, 'overwrite'):
                    release.prepare(m, out, {})

    def release_commit_fixture(self, changed=b''):
        m = release.load_matrix(release.DEFAULT_MATRIX); commit = 'a' * 40
        def git(*args, **kwargs):
            if args[0] == 'rev-parse': return (commit + '\n').encode()
            if args[0] == 'merge-base': return (m['baseline_commit'] + '\n').encode()
            if args[0] == 'diff': return changed
            raise AssertionError(args)
        def blob(c, name):
            if name == 'scripts/unified_release.py': return (ROOT / name).read_bytes()
            if name == 'release/9.7.6.json': return json.dumps(m).encode()
            if name == '.github/workflows/unified-release.yml': return b'workflow fixture'
            raise AssertionError(name)
        return m, commit, git, blob

    def test_tooling_tag_preserves_runtime_and_variant_sources(self):
        m, commit, git, blob = self.release_commit_fixture()
        with patch.object(release, 'git', side_effect=git), patch.object(release, 'blob', side_effect=blob):
            selected = release.select_release_commit(m, commit)
        self.assertEqual(selected['baseline_commit'], commit)
        self.assertEqual(selected['runtime_baseline_commit'], m['baseline_commit'])
        self.assertEqual(selected['variants'], m['variants'])

    def test_tooling_tag_cannot_change_production_sources(self):
        m, commit, git, blob = self.release_commit_fixture(b'native-reading-time-package/install.sh\n')
        with patch.object(release, 'git', side_effect=git), patch.object(release, 'blob', side_effect=blob):
            with self.assertRaisesRegex(ValueError, 'approved runtime'):
                release.select_release_commit(m, commit)

    def test_tooling_tag_requires_exact_reviewed_script(self):
        m, commit, git, _ = self.release_commit_fixture()
        with patch.object(release, 'git', side_effect=git), patch.object(release, 'blob', return_value=b'old script'):
            with self.assertRaisesRegex(ValueError, 'exact reviewed'):
                release.select_release_commit(m, commit)


class RemoteTests(unittest.TestCase):
    def setUp(self):
        self.m = release.load_matrix(release.DEFAULT_MATRIX)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        self.desired = {v['asset_name']: v['id'].encode() for v in self.m['variants'] if v['publish']}
        selected = [v for v in self.m['variants'] if v['publish']]
        for v in selected:
            v['sha256'] = release.sha(self.desired[v['asset_name']]); v['size'] = len(self.desired[v['asset_name']])
        sums = ''.join(f"{v['sha256']}  {v['asset_name']}\n" for v in selected).encode('ascii')
        manifest = {'tag': self.m['tag'], 'baseline_commit': self.m['baseline_commit'], 'assets': selected}
        self.desired.update({'SHA256SUMS.txt': sums, 'release-manifest.json': json.dumps(manifest).encode()})
        for name, raw in self.desired.items(): (self.out / name).write_bytes(raw)
        (self.out / 'RELEASE.md').write_text(release.notes(self.m, selected), encoding='utf-8')
        self.state = None; self.writes = []; self.ref = self.m['baseline_commit']

    def asset(self, name, raw):
        return dict(name=name, size=len(raw), state='uploaded', digest='sha256:' + release.sha(raw), id=1)

    def api(self, repo, path):
        if path.startswith('git/ref/'): return {'object': {'type': 'commit', 'sha': self.ref}}
        if path == 'immutable-releases': return {'enabled': True, 'enforced_by_owner': False}
        if path.startswith('releases/tags/'): return copy.deepcopy(self.state)
        self.fail('Unexpected API request: ' + path)

    def gh(self, *args, **kwargs):
        if args[0] == 'api': return json.dumps([[self.state] if self.state else []])
        self.writes.append(args)
        self.assertNotIn('--clobber', args)
        self.assertNotIn('--draft=false', args)
        if args[:2] == ('release', 'create'):
            self.assertIn('--draft', args); self.assertIn('--verify-tag', args)
            self.state = dict(tag_name=self.m['tag'], name=self.m['title'], draft=True, immutable=False,
                              prerelease=False, assets=[], body='', html_url='https://example.invalid/draft')
        elif args[:2] == ('release', 'upload'):
            p = Path(args[3]); self.state['assets'].append(self.asset(p.name, p.read_bytes()))
        elif args[:2] == ('release', 'edit'):
            self.state['body'] = (self.out / 'RELEASE.md').read_text(encoding='utf-8')
        else: self.fail('Unexpected write: ' + str(args))
        return ''

    def invoke(self):
        with patch.object(release, 'gh_api', side_effect=self.api), patch.object(release, 'gh', side_effect=self.gh):
            return release.upload_draft(self.m, self.out)

    def test_create_upload_verify_draft_only(self):
        result = self.invoke()
        self.assertTrue(result['draft']); self.assertFalse(result['published'])
        self.assertEqual(len(self.state['assets']), len(self.desired))

    def test_resume_identical_assets_skips_upload(self):
        self.invoke(); self.writes.clear(); self.invoke()
        self.assertEqual([a[:2] for a in self.writes], [('release', 'edit')])

    def test_conflicting_asset_keeps_existing_bytes(self):
        self.invoke(); self.state['assets'][0]['digest'] = 'sha256:' + '0' * 64; self.writes.clear()
        with self.assertRaisesRegex(ValueError, 'collision'): self.invoke()
        self.assertEqual(self.writes, [])

    def test_published_and_immutable_rejected(self):
        self.invoke()
        for field, value in [('draft', False), ('immutable', True)]:
            old = self.state[field]; self.state[field] = value; self.writes.clear()
            with self.assertRaisesRegex(ValueError, 'drafts'): self.invoke()
            self.assertEqual(self.writes, []); self.state[field] = old

    def test_wrong_baseline_rejected_before_writes(self):
        self.ref = '0' * 40
        with self.assertRaisesRegex(ValueError, 'baseline'): self.invoke()
        self.assertEqual(self.writes, [])

    def test_unknown_remote_asset_rejected(self):
        self.invoke(); self.state['assets'].append(self.asset('old.zip', b'old')); self.writes.clear()
        with self.assertRaisesRegex(ValueError, 'Unexpected remote'): self.invoke()
        self.assertEqual(self.writes, [])

    def test_upload_failure_is_resumable_without_deletion(self):
        original = self.gh
        def fail(*args, **kwargs):
            if args[:2] == ('release', 'upload') and len(self.state['assets']) == 1:
                raise OSError('simulated interrupted upload')
            return original(*args, **kwargs)
        with patch.object(release, 'gh_api', side_effect=self.api), patch.object(release, 'gh', side_effect=fail):
            with self.assertRaises(OSError): release.upload_draft(self.m, self.out)
        self.assertEqual(len(self.state['assets']), 1)
        self.invoke(); self.assertEqual(len(self.state['assets']), len(self.desired))

    def test_changed_staged_zip_rejected_before_writes(self):
        name = self.m['variants'][0]['asset_name']; (self.out / name).write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'changed before upload'): self.invoke()
        self.assertEqual(self.writes, [])

    def test_stale_notes_rejected_before_writes(self):
        (self.out / 'RELEASE.md').write_text('old notes', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'notes differ'): self.invoke()
        self.assertEqual(self.writes, [])

    def test_stale_provenance_rejected_before_writes(self):
        p = self.out / 'release-manifest.json'; data = release.read_json(p)
        data['assets'][0]['source_commit'] = '0' * 40; release.write_json(p, data)
        with self.assertRaisesRegex(ValueError, 'provenance differs'): self.invoke()
        self.assertEqual(self.writes, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
