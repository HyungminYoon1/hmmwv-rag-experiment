"""Checks for the v6 source, diagram-scope and conditional-context repairs."""
from copy import deepcopy
import unittest
from corpus.common import SourceStore,PACKAGE,read_json,read_jsonl
from corpus.structure import Units,manual_tables
from corpus.boxes import reviewed_boxes
from corpus.review_resolution import NORMAL_CODES,signature,verify_history


class FreezeRulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store=SourceStore();u=Units(cls.store);manual_tables(cls.store,u);reviewed_boxes(cls.store,u)
        cls.by={x['key']:x for x in u.items};cls.rules=PACKAGE/cls.store.config['rules_path']

    def test_source_choice_and_token_failures_cannot_be_closed_as_layout(self):
        for code in ['TOKEN_BUDGET','LAYER_ALIGNMENT','SELECTION_CONFLICT','UNASSIGNED_TEXT','CROSS_REGION_TEXT']:
            self.assertNotIn(code,NORMAL_CODES)

    def test_changed_source_invalidates_closure_signature(self):
        item={'code':'OCR_REGION_STRUCTURE','pdf_page':33,'unit_key':'example','detail':'boundary',
              'source_refs':[{'record_id':'P0033:ocr','start':2,'end':5,'text':'abc'}]}
        changed=deepcopy(item);changed['source_refs'][0]['text']='abd'
        self.assertNotEqual(signature(item),signature(changed))

    def test_no_condition_is_invented_for_alternator_C1(self):
        self.assertNotIn('KNOWN INFO',self.by['V15:P0291:C1']['prefix_text'])
        self.assertNotIn('WIRING',self.by['V15:P0291:C1']['prefix_text'])

    def test_voltage_and_resistance_test_references_remain_distinct(self):
        self.assertIn('PAGE 2-750',self.by['V15:P0463:H1']['body_text'])
        self.assertNotIn('PAGE 2-752',self.by['V15:P0463:H1']['body_text'])
        self.assertIn('PAGE 2-752',self.by['V15:P0463:H2']['body_text'])

    def test_conditional_repair_retains_question_and_NO(self):
        item=self.by['V15:P0463:H1:NO']
        self.assertIn('BATTERY VOLTAGE AT WIRE 27H?',item['prefix_text'])
        self.assertTrue(item['prefix_text'].rstrip().endswith('NO'))
        self.assertIn('REPAIR 27H',item['body_text'])

    def test_left_and_right_guide_columns_are_not_interleaved(self):
        value=self.by['V16:P0128:question-info']['body_text']
        self.assertIn('you don’t usually need them to answer the question.',value)
        self.assertNotIn('BOLD FACE',value)

    def test_speed_table_three_ranges_are_preserved(self):
        u=self.by['V16:P0052:speed:R']
        self.assertIn('L Low Lock: 11 MPH',u['body_text'])
        self.assertIn('H High: 29 MPH',u['body_text'])
        self.assertIn('H/L High Lock: 11 MPH',u['body_text'])

    def test_power_test_notes_and_pretest_stay_with_procedure(self):
        u=next(x for x in self.by.values() if x['metadata'].get('card_page')==832 and x['metadata'].get('is_test_procedure'))
        self.assertIn('Run Confidence Test.',u['prefix_text'])
        self.assertIn('625-675 RPM',u['prefix_text'])
        self.assertNotIn('E009',u['prefix_text'])

    def test_faded_plate_has_explicit_source_issue_and_legible_instruction(self):
        u=self.by['V6:P0050:sling-instruction']
        self.assertIn('THRU GUIDES',u['body_text'])
        self.assertIn('P0050_FADED_DATA_PLATE',u['metadata']['source_issues'])
        self.assertNotIn('MAX TOWED',u['body_text'])

    def test_hidden_native_text_is_not_a_question_condition(self):
        u=self.by['P0303:question:E3']
        self.assertNotIn('KNOWN INFO',u['prefix_text'])

    def test_terminal_instruction_is_not_a_known_condition(self):
        u=self.by['V19:P0201:D6']
        self.assertIn('POSSIBLE PROBLEMS\nFUEL PUMP',u['prefix_text'])
        self.assertNotIn('TEST YOU CAME FROM',u['prefix_text'])
        terminal=self.by['V19:P0201:terminal']
        self.assertIn('TEST YOU CAME FROM',terminal['body_text'])
        self.assertEqual(terminal['metadata']['branch_interpretation'],'PDF_ONLY_NO_PRINTED_BRANCH_LABEL')

    def test_missing_condition_and_reason_are_restored_from_pdf(self):
        u=self.by['V19:P0479:N1']
        self.assertIn('POSSIBLE PROBLEMS\nWIRING',u['prefix_text'])
        self.assertIn('These contacts provide power',u['body_text'])
        self.assertIn('LEAD 799 A OK',self.by['V19:P0718:15']['prefix_text'])

    def test_multimeter_title_is_attached_but_printed_typo_preserved(self):
        u=self.by['V19:P0361:multimeter']
        self.assertIn('BATTERY VOLTAGE\nMULTIMETER',u['prefix_text'])
        self.assertIn('at least 40 volts.',u['body_text'].replace('\n',' '))
        self.assertIn('reed the correct scale.',u['body_text'])


if __name__=='__main__':unittest.main()
