"""Adversarial checks for protected values, table relationships and layout holds."""
from copy import deepcopy
import unittest
from corpus.common import SourceStore,read_json,read_jsonl,PACKAGE
from corpus.equivalence import norm,witness
from corpus.regions import is_section,bucket,group_regions
from corpus.verify_tables import verify_table_contracts


class EquivalenceTests(unittest.TestCase):
    def test_numbers_cannot_match_inside_signed_decimal_or_identifier_values(self):
        class Store:
            def __init__(self,text):self.text=text
            def ref(self,rid,a,b):return {'record_id':rid,'start':a,'end':b,'text':self.text[a:b]}
        for value in ['-10','+10','10.0','10-15','110','10°F','10/20']:
            s=Store(value);target=s.ref('r',0,len(value))
            self.assertIsNone(witness(s,{'text':'10'},[target]),value)
        s=Store('Value: 10 V');self.assertEqual(witness(s,{'text':'10'},[s.ref('r',0,len(s.text))])[0]['text'],'10')

    def test_whitespace_is_the_only_automatic_normalization(self):
        self.assertEqual(norm('  ON\n\t 12.0\u00a0V '),'ON 12.0 V')
        for a,b in [('12.0','120'),('ON','OFF'),('j','J'),('O','0'),('±25','+25'),
                    ('-15','15'),('not grounded','grounded'),('3L80','4L80'),('no pressure','NO PRESSURE')]:
            self.assertNotEqual(norm(a),norm(b))

    def test_source_preference_does_not_conflict_with_table_representation(self):
        s=object.__new__(SourceStore)
        s.decisions={'r':[(0,8,'PREFERRED','native',['S01']),
                          (0,8,'EXCLUDED_NON_TEXT','printed branch label',['G02'])]}
        self.assertEqual(s.decision({'record_id':'r','start':0,'end':8})[0],'EXCLUDED_NON_TEXT')
        s.decisions['r'].append((0,8,'LAYOUT_ONLY','other',['T01']))
        self.assertEqual(s.decision({'record_id':'r','start':0,'end':8})[0],'NEEDS_REVIEW')


class TableContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=read_jsonl(PACKAGE/read_json(PACKAGE/'config.json').get('rules_path','rules/v2')/'manual-table-units.jsonl')

    def errors(self,rows):
        errors=[]
        verify_table_contracts(rows,lambda ok,code,detail='':errors.append(code) if not ok else None)
        return errors

    def test_reviewed_protected_values_and_matrix(self):self.assertEqual(self.errors(self.rows),[])

    def test_changed_pin_case_is_detected(self):
        rows=deepcopy(self.rows)
        row=next(r for r in rows if r['key']=='P0532:engine-off:row:1')
        next(f for f in row['fields'] if f['name']=='PIN')['text']='J'
        self.assertIn('TABLE_PDF_VALUE',self.errors(rows))

    def test_swapping_matrix_cells_is_detected_without_changing_x_count(self):
        rows=deepcopy(self.rows)
        for column,value in [(3,'x'),(4,'')]:
            row=next(r for r in rows if r['key']==f'P0060:matrix:r1:c{column}')
            next(f for f in row['fields'] if f['name']=='Mark')['text']=value
        self.assertIn('MATRIX_CELL_ASSIGNMENT',self.errors(rows))

    def test_no_inferred_value_for_arctic_capacity(self):
        rows=deepcopy(self.rows)
        row=next(r for r in rows if r['key']=='P0121:transmission:arctic')
        next(f for f in row['fields'] if f['name']=='CAPACITIES')['text']='0'
        self.assertIn('TABLE_PDF_VALUE',self.errors(rows))

    def test_wrong_engine_condition_is_detected(self):
        rows=deepcopy(self.rows)
        row=next(r for r in rows if r['key']=='P0532:engine-off:row:1')
        row['context_refs'].append({'text':'Engine ON'})
        self.assertIn('TABLE_WRONG_CONDITION',self.errors(rows))


class RegionTests(unittest.TestCase):
    def ref(self,text,box,start=0):
        return {'text':text,'bbox':box,'fonts':['Helvetica-Bold'],
                'record_id':'P0200:native','layer':'native','source_blocks':[start],'start':start}

    def test_printed_page_reference_is_not_a_section(self):
        self.assertIsNone(is_section(self.ref('2-312 PCB',[100,200,200,211])))
        self.assertEqual(is_section(self.ref('1-23.3. GENERATING SYSTEM OPERATION',[50,70,530,84])),'1-23.3')

    def test_cross_column_line_stays_unresolved(self):
        r=self.ref('KNOWN INFO QUESTION TEST OPTIONS',[50,140,490,151])
        self.assertEqual(bucket(r,'diagnostic_flowchart'),'cross_column')

    def test_independent_columns_are_never_y_interleaved(self):
        refs=[self.ref('left 1',[50,150,140,161],0),self.ref('right 1',[370,151,490,162],8),
              self.ref('left 2',[50,165,140,176],16),self.ref('right 2',[370,166,490,177],24)]
        groups=group_regions(refs,'diagnostic_flowchart')
        self.assertEqual({tuple(r['text'] for r in items) for _,items in groups},
                         {('left 1','left 2'),('right 1','right 2')})


if __name__=='__main__':unittest.main()
