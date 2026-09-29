"""Regression checks for actual condition, OCR and source-coordinate failures."""
from copy import deepcopy
from pathlib import Path
import unittest
from corpus.common import SourceStore,PACKAGE,ROOT,read_json,read_jsonl,sha
from corpus.structure import Units
from corpus.boxes import reviewed_boxes
from corpus.verify_boxes import verify_box_contracts


class ReviewedRelationsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store=SourceStore();units=Units(cls.store);reviewed_boxes(cls.store,units)
        cls.units=units.items;cls.by={u['key']:u for u in cls.units}

    def errors(self,units):
        errors=[]
        verify_box_contracts(self.store,units,lambda ok,c,d='':errors.append(c) if not ok else None)
        return errors

    def test_reviewed_contracts_and_independent_facts(self):
        self.assertEqual(self.errors(self.units),[])

    def test_continuation_is_not_last_question_condition(self):
        for pn,step,next_step in [(330,'12','13'),(332,'15','16'),(334,'18','19')]:
            u=self.by[f'P{pn:04d}:question:{step}']
            self.assertNotIn('GO TO',u['prefix_text'])
            self.assertIn('GO TO '+next_step,self.by[f'P{pn:04d}:continuation']['body_text'])

    def test_three_tall_first_boxes_have_their_actual_context(self):
        for pn,step in [(330,'10'),(332,'13'),(334,'16')]:
            self.assertIn('LEAD 57B GROUND OK',self.by[f'P{pn:04d}:question:{step}']['prefix_text'])
        self.assertNotIn('KNOWN INFO',self.by['P0287:question:B1']['prefix_text'])

    def test_branch_label_and_parent_cannot_change_together_unnoticed(self):
        units=deepcopy(self.units);u=next(u for u in units if u['key']=='P0332:branch:14:NO')
        u['metadata']['branch_label']='YES'
        self.assertIn('PDF_BOX_RELATION',self.errors(units))

    def test_warning_belongs_to_replacement_not_battery_or_lead_repair(self):
        for key in ['P0331:lead-repair','P0333:lead-repair','P0335:glowplug','P0335:battery']:
            self.assertNotIn('WARNING',self.by[key]['prefix_text'])
        self.assertIn('Disconnect negative battery cable',self.by['P0334:branch:16:NO']['prefix_text'])

    def test_580_ohms_and_wire_identifiers_are_not_raw_ocr_guesses(self):
        u=self.by['P0262:question:C6']
        self.assertIn('580Ω FROM WIRE 93B',u['body_text'])
        bad=deepcopy(self.units);v=next(x for x in bad if x['key']==u['key'])
        v['body_text']=v['body_text'].replace('580Ω','5802').replace('93B','938')
        self.assertIn('PDF_BOX_REQUIRED_TEXT',self.errors(bad))

    def test_retranscription_maps_to_its_box_not_the_whole_page(self):
        u=self.by['P0217:question:M3']
        r=next(p['source'] for p in u['body_parts'] if p['kind']=='source')
        self.assertEqual(r['coordinate_precision'],'reviewed_pdf_region')
        self.assertGreater(r['bbox'][1],500)
        self.assertLess(r['bbox'][2]-r['bbox'][0],210)
        self.assertTrue(any(p['correction_id']=='FIX-V7-0217' for p in r['raw_spans']))

    def test_previous_locked_inputs_are_unchanged(self):
        previous=read_json(ROOT/'preprocessing/output/corpus-v3-rules-c/manifest.json')['inputs']
        for name,digest in previous.items():self.assertEqual(sha(ROOT/name),digest,name)


class OCRCoordinateEvidenceTests(unittest.TestCase):
    def test_words_reconstruct_exact_line_offsets(self):
        base=PACKAGE/'reports/rules-v4-work/ocr-words-all';m=read_json(base/'manifest.json')
        for name,digest in m['files'].items():
            self.assertEqual(sha(base/name),digest)
            for line in read_json(base/name)['lines']:
                self.assertEqual(' '.join(w['text'] for w in line['words']),line['text'])
                for word in line['words']:
                    self.assertEqual(line['text'][word['start']:word['end']],word['text'])

    def test_coordinate_candidates_do_not_claim_semantic_approval(self):
        path=PACKAGE/'reports/rules-v4-work/coordinate-review/candidates.jsonl'
        for r in read_jsonl(path):
            self.assertFalse(r['adopted'])
            for group in r['segments']:self.assertEqual(group['semantic_role'],'UNASSIGNED')


if __name__=='__main__':unittest.main()
