"""Adversarial tests for unrecorded changes, including rehashed tampered files."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import correct_extraction as io
from verify_corrections import audit_changes, verify


class ChangeAuditTests(unittest.TestCase):
    def setUp(self):
        self.before = [{'id': 'P1:native', 'pdf_page': 1, 'text': 'Set 90 Ib-ft. Do not remove.'}]
        self.after = copy.deepcopy(self.before)
        self.after[0]['text'] = 'Set 90 lb-ft. Do not remove.'
        self.patches = [{'id': 'F1', 'record_id': 'P1:native', 'start': 7, 'end': 12,
                         'before': 'Ib-ft', 'after': 'lb-ft'}]

    def errors(self, before=None, after=None, patches=None):
        return audit_changes(self.before if before is None else before,
                             self.after if after is None else after,
                             self.patches if patches is None else patches)[0]

    def test_recorded_change_passes(self):
        self.assertEqual(self.errors(), [])

    def test_unrecorded_addition(self):
        self.after[0]['text'] += ' Recommended extra step.'
        self.assertTrue(self.errors())

    def test_unrecorded_deletion_of_negation(self):
        self.after[0]['text'] = self.after[0]['text'].replace('not ', '')
        self.assertTrue(self.errors())

    def test_unrecorded_numeric_change(self):
        self.after[0]['text'] = self.after[0]['text'].replace('90', '99')
        self.assertTrue(self.errors())

    def test_missing_recorded_change(self):
        self.assertTrue(self.errors(after=self.before))

    def test_wrong_before_in_ledger(self):
        self.patches[0]['before'] = 'wrong'
        self.assertTrue(self.errors())

    def test_duplicate_or_overlapping_patch(self):
        self.assertTrue(self.errors(patches=self.patches * 2))
        extra = copy.deepcopy(self.patches[0])
        extra['id'] = 'F2'
        self.assertTrue(self.errors(patches=self.patches + [extra]))

    def test_extra_record_or_metadata_change(self):
        self.assertTrue(self.errors(after=self.after + [{'id': 'new', 'pdf_page': 1, 'text': 'Invented'}]))
        self.after[0]['pdf_page'] = 2
        self.assertTrue(self.errors())

    def test_record_order_change(self):
        other = {'id': 'P2:native', 'pdf_page': 2, 'text': 'Keep this.'}
        self.assertTrue(self.errors(before=self.before + [other], after=[other] + self.after))

    def test_unicode_and_variable_length_replacement(self):
        before = [{'id': 'K', 'pdf_page': 1, 'text': '조건 가X 끝'}]
        after = [{'id': 'K', 'pdf_page': 1, 'text': '조건 가정확 끝'}]
        patches = [{'id': 'K1', 'record_id': 'K', 'start': 4, 'end': 5, 'before': 'X', 'after': '정확'}]
        self.assertEqual(self.errors(before, after, patches), [])


class SavedArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kidet-correction-test-')
        self.folder = Path(self.temp.name) / 'copy'
        shutil.copytree(io.BASE / 'output/corrected-v1-a', self.folder)
        self.ledger = io.BASE / 'corrections/batch-001/correction-log.json'

    def tearDown(self):
        self.temp.cleanup()

    def rehash(self, name):
        path = self.folder / 'manifest.json'
        meta = json.loads(path.read_text(encoding='utf-8'))
        meta['files'][name] = io.sha(self.folder / name)
        path.write_bytes(io.json_bytes(meta))

    def test_rehashed_text_insertion_still_fails(self):
        name = 'units-corrected.jsonl'
        records = io.load_records(self.folder / name)
        records[100]['text'] += '\nInvented extra technical information.'
        (self.folder / name).write_bytes(io.records_bytes(records))
        self.rehash(name)
        result, _ = verify(self.folder, self.ledger)
        self.assertFalse(result['checks']['actual_changes_exactly_match_ledger'])

    def test_rehashed_export_only_tampering_still_fails(self):
        name = 'Codex_보정본.txt'
        with (self.folder / name).open('ab') as f:
            f.write(b'Unrecorded addition\r\n')
        self.rehash(name)
        result, _ = verify(self.folder, self.ledger)
        self.assertFalse(result['checks']['text_export:' + name])

    def test_copied_log_tampering_fails(self):
        path = self.folder / 'correction-log.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['corrections'].pop()
        path.write_bytes(io.json_bytes(data))
        self.rehash('correction-log.json')
        result, _ = verify(self.folder, self.ledger)
        self.assertFalse(result['checks']['frozen_ledger_matches'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
