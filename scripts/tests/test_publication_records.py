"""Publication bookkeeping must retain scientific records and detect later changes."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_artifacts import verify


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        def record(path, text):
            raw = text.encode()
            return {'path': path, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        old = record('research/note.md', 'local source location')
        public = record('research/note.md', '<PROJECT_ROOT>')
        answer = record('experiment/result.json', '{"score":0.7}')
        empty = record('experiment/worker.log', '')
        saved = record('experiment/save.json.tmp', '{"status":"OK"}')
        archive = dict(saved, path='experiment/archive/save.json')
        data = record('preprocessing/chunks.json', '[1,2,3]')
        source_bundle = {'id':'runtime-data', 'files':[data]}
        self.write('artifacts/original-files.json', {'files':[old, answer, empty, saved]})
        self.write('artifacts/source-bundles.json', {'bundles':[source_bundle]})
        self.write('artifacts/manifest.json', {'publication_revision':'test-v2', 'bundles':[source_bundle]})
        self.ledger = {'schema':1, 'publication_revision':'test-v2', 'changes':[
            dict(public, original_path=old['path'], original_sha256=old['sha256'], original_bytes=old['bytes'], kind='local_path_redaction'),
            dict(archive, original_path=saved['path'], original_sha256=saved['sha256'], original_bytes=saved['bytes'], kind='archive_interrupted_save')],
            'excluded':[dict(empty,reason='empty_worker_log')], 'bundle_additions':[]}
        self.write('artifacts/publication-changes.json', self.ledger)
        for path, text in [('research/note.md','<PROJECT_ROOT>'),('experiment/result.json','{"score":0.7}'),
                           ('experiment/archive/save.json','{"status":"OK"}'),('preprocessing/chunks.json','[1,2,3]')]:
            target = self.root/path; target.parent.mkdir(parents=True,exist_ok=True); target.write_text(text,encoding='utf-8')

    def write(self, name, value):
        path = self.root/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value),encoding='utf-8')

    def test_declared_derivative_and_archive_pass(self):
        result = verify(self.root,'all')
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['checked_files'],4)
        self.assertEqual(result['publication']['excluded_empty_logs'],1)

    def test_answer_tampering_is_detected(self):
        (self.root/'experiment/result.json').write_text('{"score":1.0}',encoding='utf-8')
        self.assertEqual(verify(self.root,'core')['status'],'FAIL')

    def test_archive_is_still_checked(self):
        (self.root/'experiment/archive/save.json').unlink()
        self.assertEqual(verify(self.root,'core')['status'],'FAIL')

    def test_cannot_exclude_nonempty_results(self):
        changed = copy.deepcopy(self.ledger)
        original = json.loads((self.root/'artifacts/original-files.json').read_text())['files'][1]
        changed['excluded'].append(dict(original,reason='empty_worker_log'))
        self.write('artifacts/publication-changes.json',changed)
        self.assertEqual(verify(self.root,'core')['status'],'FAIL')

    def test_wrong_original_hash_is_rejected(self):
        self.ledger['changes'][0]['original_sha256']='0'*64
        self.write('artifacts/publication-changes.json',self.ledger)
        self.assertEqual(verify(self.root,'core')['status'],'FAIL')

    def test_undeclared_bundle_change_is_rejected(self):
        manifest=json.loads((self.root/'artifacts/manifest.json').read_text())
        manifest['bundles'][0]['files'][0]['sha256']='0'*64
        self.write('artifacts/manifest.json',manifest)
        self.assertEqual(verify(self.root,'all')['status'],'FAIL')

    def test_scope_does_not_require_unrestored_data(self):
        (self.root/'preprocessing/chunks.json').unlink()
        self.assertEqual(verify(self.root,'core')['status'],'PASS')
        self.assertEqual(verify(self.root,'all')['status'],'FAIL')

    def test_documentation_derivative_is_checked(self):
        self.ledger['changes'][0]['kind'] = 'standalone_documentation'
        self.write('artifacts/publication-changes.json', self.ledger)
        self.assertEqual(verify(self.root, 'all')['status'], 'PASS')
        (self.root/'research/note.md').write_text('undeclared later edit', encoding='utf-8')
        self.assertEqual(verify(self.root, 'all')['status'], 'FAIL')

    def test_documentation_label_cannot_hide_result_changes(self):
        result = json.loads((self.root/'artifacts/original-files.json').read_text())['files'][1]
        self.ledger['changes'].append(dict(result, original_path=result['path'],
            original_sha256=result['sha256'], original_bytes=result['bytes'], kind='standalone_documentation'))
        self.write('artifacts/publication-changes.json', self.ledger)
        self.assertEqual(verify(self.root, 'all')['status'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
