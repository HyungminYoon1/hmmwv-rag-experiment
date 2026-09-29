import unittest
from .runner import schedule
from .generation import Generator,evaluation_copy,context_text
from .gold import minimum_chunks,retrieval_score
from .io import BASE,read_json

class ExperimentTests(unittest.TestCase):
    def test_schedule_pairs_and_reversal(self):
        ids=[q['id'] for q in read_json(BASE/'gold-v1/questions.json')]
        rows=schedule(ids);self.assertEqual(360,len(rows));self.assertEqual(360,len({r['key'] for r in rows}))
        rounds=[[r['question_id'] for r in rows if r['round']==n][::2] for n in (1,2,3)]
        self.assertEqual(rounds[0][::-1],rounds[1]);self.assertEqual(rounds[0],rounds[2])
        for a,b in zip(rows[::2],rows[1::2]):
            self.assertEqual(a['question_id'],b['question_id']);self.assertNotEqual(a['condition'],b['condition'])
        self.assertEqual(rows,schedule(ids))
    def test_source_only_inputs(self):
        gen=Generator();payload,tokens=gen.prepare('A development question?','No reference context is available.')
        self.assertTrue(payload['raw']);self.assertFalse(payload['stream']);self.assertGreater(tokens,1)
        self.assertNotIn('required_elements',payload['prompt']);self.assertNotIn('oracle',payload['prompt'].lower())
        self.assertTrue(payload['prompt'].endswith('<|im_start|>assistant\n'))
        self.assertEqual(1,payload['prompt'].count('<|im_start|>user'))
    def test_budget_never_truncates(self):
        with self.assertRaises(ValueError):Generator().prepare('Question?', 'very long text '*5000)
    def test_citation_copy_preserves_facts(self):
        result,ids=evaluation_copy('25 mΩ [C000001]; 2-24 [C1] [C999999]')
        self.assertEqual('25 mΩ ; 2-24 [C1] ',result);self.assertEqual(['[C000001]','[C999999]'],ids)
    def test_gold_and_or(self):
        q={'type':'single-evidence','evidence':[{'id':'e','sufficient_chunk_sets':[['A'],['B','C']]}]}
        self.assertEqual(1,retrieval_score(q,['A'])['evidence_recall_at_5'])
        self.assertEqual(0,retrieval_score(q,['B'])['evidence_recall_at_5'])
        self.assertEqual(1,retrieval_score(q,['B','C'])['complete_evidence_at_5'])
    def test_questions_preserved_and_max_chunks(self):
        rows=read_json(BASE/'gold-v1/questions.json')
        self.assertEqual(60,len(rows));self.assertEqual(3,max(r['min_sufficient_chunks'] or 0 for r in rows))
        self.assertEqual({'single-evidence':20,'multi-evidence':30,'unanswerable':10},
            {t:sum(q['type']==t for q in rows) for t in {q['type'] for q in rows}})
    def test_development_disjoint(self):
        dev=read_json(BASE/'development.json');gold=read_json(BASE/'gold-v1/questions.json')
        self.assertEqual(10,len(dev));self.assertFalse({x['question'] for x in dev}&{x['question'] for x in gold})
        used={c for q in gold for e in q['evidence'] for c in e['primary_chunks']}
        self.assertFalse(used & {c for q in dev for c in q['source_chunks']})
    def test_percentile_is_linear_and_empty_is_missing(self):
        from .report import distribution
        self.assertEqual(9.5,distribution([0,10])['p95'])
        self.assertIsNone(distribution([])['median'])
    def test_minimum_union_and_unanswerable(self):
        self.assertEqual(2,minimum_chunks([{'sufficient_chunk_sets':[['A','B'],['C']]},
            {'sufficient_chunk_sets':[['B'],['D','E']]}]))
        self.assertEqual('N/A_OUT_OF_SCOPE',retrieval_score({'type':'unanswerable'},[])['status'])

if __name__=='__main__':unittest.main()
