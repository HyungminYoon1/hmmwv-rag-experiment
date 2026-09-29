"""Protect corrected glyphs, condition scope, table blanks and no-guess cases."""
from copy import deepcopy
import unittest
from corpus.common import SourceStore,read_json,read_jsonl,PACKAGE,BASE
from corpus.structure import Units
from corpus.boxes import reviewed_boxes
from corpus.verify_boxes import verify_box_contracts
from corpus.verify_tables import verify_table_contracts
from corpus.compare_versions import corrected_source


class BoxContractsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store=SourceStore();u=Units(cls.store);reviewed_boxes(cls.store,u);cls.units=u.items

    def errors(self,units):
        errors=[]
        verify_box_contracts(self.store,units,lambda ok,code,detail='':errors.append(code) if not ok else None)
        return errors

    def test_contracts_and_separate_pdf_assertions_pass(self):self.assertEqual(self.errors(self.units),[])

    def test_warning_cannot_leak_into_neighbouring_meter_box(self):
        units=deepcopy(self.units);by={u['key']:u for u in units}
        by['P0389:multimeter']['prefix_text']+=by['P0389:pcb-replacement']['prefix_text']
        self.assertIn('PDF_BOX_WRONG_LINK',self.errors(units))

    def test_later_state_on_287_is_not_used_as_B3_entry(self):
        units=deepcopy(self.units);by={u['key']:u for u in units}
        by['P0287:question:B3']['prefix_text']=by['P0287:question:B3']['prefix_text'].replace('WIRING','')
        self.assertIn('PDF_BOX_REQUIRED_TEXT',self.errors(units))

    def test_caution_survives_step_partition(self):
        units=deepcopy(self.units);u=next(u for u in units if u['key']=='P0573:step:22')
        u['prefix_text']=u['prefix_text'].replace('Do not leave analyzer valve fully closed for more than 5 seconds.','')
        self.assertIn('PDF_BOX_REQUIRED_TEXT',self.errors(units))

    def test_pretest_and_power_off_condition_survive_test_card_partition(self):
        units=deepcopy(self.units);u=next(u for u in units if u['key']=='P0849:procedure')
        u['prefix_text']='RESISTANCE TEST 91\n\n'
        self.assertIn('PDF_BOX_REQUIRED_TEXT',self.errors(units))

    def test_circled_d_not_plain_d(self):
        units=deepcopy(self.units);u=next(u for u in units if u['key']=='P0517:road')
        u['body_text']=u['body_text'].replace('Ⓓ','D')
        self.assertIn('PDF_BOX_REQUIRED_TEXT',self.errors(units))

    def test_source_133_does_not_keep_mixed_ocr_fragments(self):
        full=self.store.records['P0133:ocr']['text']
        self.assertIn('100 RPM, STARTER DISENGAGES)',full)
        self.assertNotIn('STENCE FEST',full)
        patch=next(p for p in self.store.patches['P0133:ocr'] if p['id']=='FIX-V5-0001')
        self.assertEqual(patch['kind'],'PDF_REGION_RETRANSCRIPTION')

    def test_restored_page_cell_coordinates_include_the_printed_value(self):
        text=self.store.records['P0124:native']['text'];a=text.index('2-79')
        ref=self.store.ref('P0124:native',a,a+4)
        self.assertGreaterEqual(ref['bbox'][2],310)
        self.assertEqual(ref['coordinate_precision'],'correction_region')

    def test_all_analyzer_steps_are_distinct_and_figure_labels_stay_separate(self):
        group=[u for u in self.units if u['key'].startswith('P0573:step:')]
        self.assertEqual([int(u['metadata']['step']) for u in group],list(range(8,30)))
        self.assertTrue(all('BYPASS HOSE' not in u['body_text'] for u in group))


class AdditionalTablesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rows=read_jsonl(PACKAGE/read_json(PACKAGE/'config.json')['rules_path']/'manual-table-units.jsonl')
    def errors(self,rows):
        errors=[];verify_table_contracts(rows,lambda ok,code,detail='':errors.append(code) if not ok else None)
        return errors
    def test_all_52_added_rows_match_separate_pdf_facts(self):self.assertEqual(self.errors(self.rows),[])
    def test_blank_foldout_does_not_become_no(self):
        rows=deepcopy(self.rows);r=next(r for r in rows if r['key']=='P0123:foldouts:row:7')
        next(f for f in r['fields'] if f['name']=='FOLDOUT NUMBER')['text']='No'
        self.assertIn('TABLE_PDF_VALUE',self.errors(rows))
    def test_original_wrong_page_number_is_not_silently_fixed(self):
        rows=deepcopy(self.rows);r=next(r for r in rows if r['key']=='P0124:system:row:15')
        next(f for f in r['fields'] if f['name']=='PAGE')['text']='2-411'
        self.assertIn('TABLE_PDF_VALUE',self.errors(rows))
    def test_rpm_tolerance_sign_is_protected(self):
        rows=deepcopy(self.rows);r=next(r for r in rows if r['key']=='P0573:idle:row:1')
        next(f for f in r['fields'] if f['name']=='Idle speed')['text']='650+25 RPM'
        self.assertIn('TABLE_PDF_VALUE',self.errors(rows))


if __name__=='__main__':unittest.main()
