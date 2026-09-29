"""Regression checks for missing table cells, column mixing and wrong branches."""
from copy import deepcopy
import unittest
from corpus.common import SourceStore, PACKAGE, read_jsonl
from corpus.structure import Units, manual_tables
from corpus.boxes import reviewed_boxes
from corpus.verify_boxes import verify_box_contracts
from corpus.verify_tables import verify_table_contracts


class RepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store=SourceStore(); units=Units(cls.store)
        manual_tables(cls.store,units);reviewed_boxes(cls.store,units)
        cls.units=units.items
        cls.rules=PACKAGE/cls.store.config['rules_path']
        cls.tables=read_jsonl(cls.rules/'manual-table-units.jsonl')

    def table_errors(self,rows):
        errors=[]
        verify_table_contracts(rows,lambda ok,code,detail='':errors.append(code) if not ok else None)
        return errors

    def box_errors(self,units):
        errors=[]
        verify_box_contracts(self.store,units,lambda ok,code,detail='':errors.append(code) if not ok else None)
        return errors

    def test_all_repaired_contracts(self):
        self.assertEqual(self.table_errors(self.tables),[])
        self.assertEqual(self.box_errors(self.units),[])

    def test_missing_steering_combination_is_detected(self):
        rows=[r for r in self.tables if r['key']!='P0575:answers:row:3']
        self.assertIn('TABLE_EXPECTED_ROWS',self.table_errors(rows))

    def test_swapping_boolean_columns_is_detected(self):
        rows=deepcopy(self.tables); row=next(r for r in rows if r['key']=='P0575:answers:row:2')
        row['fields'][1]['text'],row['fields'][2]['text']=row['fields'][2]['text'],row['fields'][1]['text']
        self.assertIn('TABLE_PDF_VALUE',self.table_errors(rows))

    def test_letter_B_cannot_be_replaced_by_digit_8(self):
        rows=deepcopy(self.tables); row=next(r for r in rows if r['key']=='P0502:connections:row:6')
        row['fields'][2]['text']='3258'
        self.assertIn('TABLE_PDF_VALUE',self.table_errors(rows))

    def test_low_high_context_mix_is_detected(self):
        units=deepcopy(self.units); u=next(u for u in units if u['key']=='P0547:branch:H2:NO')
        u['prefix_text']=u['prefix_text'].replace('RESISTANCE TOO HIGH','RESISTANCE TOO LOW')
        self.assertIn('PDF_BOX_WRONG_LINK',self.box_errors(units))

    def test_reference_paragraph_tail_cannot_move_to_another_step(self):
        units=deepcopy(self.units); u=next(u for u in units if u['key']=='P0829:B1-reference')
        u['body_text']+='\noil pump drive could be too worn'
        self.assertIn('PDF_BOX_WRONG_LINK',self.box_errors(units))

    def test_unprinted_tolerance_cannot_be_invented(self):
        row=next(r for r in self.tables if r['key']=='P0408:pin:row:1')
        self.assertEqual(row['fields'][2]['text'],'130 Ω ± Ω')
        self.assertIn('P0408_MISSING_TOLERANCE_NUMBER',row['metadata']['source_issues'])

    def test_partial_diagram_ocr_is_not_certified(self):
        decisions=[r for r in read_jsonl(self.rules/'box-dispositions.jsonl')
                   if r['source']['pdf_page']==613 and 'SPARE FUSE' in r['source']['text']]
        self.assertTrue(decisions)
        self.assertTrue(all(d['status']=='EXCLUDED_NON_TEXT' for d in decisions))


if __name__=='__main__':unittest.main()
