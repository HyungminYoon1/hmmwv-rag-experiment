"""Meaningful regression cases for the declared gold-v3 corrections."""
import copy
import http.client
import json
from pathlib import Path
import sys
import threading
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from experiment.correction import check_gold, corrected_result
from experiment.gold import retrieval_score
from artifact_io import read
from serve_results import make_server


class CorrectionTests(unittest.TestCase):
    def setUp(self):
        self.old = read(ROOT / 'experiment/gold-v2/questions.json')
        self.new = read(ROOT / 'experiment/gold-v3/questions.json')
        self.q = {q['id']: q for q in self.new}

    def test_only_declared_corrections_allowed(self):
        check_gold(self.old, self.new)
        altered = copy.deepcopy(self.new)
        altered[0]['required_elements'][0]['text'] = 'Unapproved answer requirement'
        with self.assertRaises(ValueError):
            check_gold(self.old, altered)

    def test_unasked_route_is_not_required_but_split_sentence_still_needs_both_chunks(self):
        s = self.q['S16']
        self.assertEqual(len(s['required_elements']), 1)
        self.assertEqual(retrieval_score(s, ['C002436'])['evidence_recall_at_5'], 1)
        self.assertEqual(retrieval_score(s, ['C001647'])['evidence_recall_at_5'], 0)
        self.assertEqual(retrieval_score(s, ['C001647', 'C001648'])['evidence_recall_at_5'], 1)
        self.assertEqual(retrieval_score(self.q['M06'], ['C002436'])['evidence_recall_at_5'], .5)

    def test_equivalent_evidence_is_question_specific(self):
        self.assertEqual(retrieval_score(self.q['S15'], ['C001838'])['evidence_recall_at_5'], 1)
        self.assertEqual(retrieval_score(self.q['S17'], ['C001993'])['evidence_recall_at_5'], 1)
        self.assertEqual(retrieval_score(self.q['M04'], ['C001838'])['evidence_recall_at_5'], 0)
        self.assertEqual(retrieval_score(self.q['M24'], ['C005773'])['evidence_recall_at_5'], .5)
        self.assertEqual(retrieval_score(self.q['M13'], ['C000540', 'C000941', 'C005549'])['evidence_recall_at_5'], 0)

    def test_cached_judgments_are_not_rewritten(self):
        for condition in ('rag', 'llm_only'):
            path = ROOT / f'experiment/evaluation/runs/sol-revision-formal-20260929-v3/results/r1-S16-{condition}.json'
            before = read(path)['result']
            after = corrected_result(before)
            self.assertEqual(before['metrics']['required_coverage']['value'], .5)
            self.assertEqual(after['metrics']['required_coverage']['value'], 1)
            self.assertEqual(after['stages']['coverage']['elements'][0], before['stages']['coverage']['elements'][0])
            self.assertEqual(after['metrics']['oracle_support'], before['metrics']['oracle_support'])

    def test_current_view_and_historical_gold_are_both_accessible(self):
        with make_server(0) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection('127.0.0.1', server.server_address[1], timeout=30)
            try:
                def get(path):
                    connection.request('GET', path)
                    response = connection.getresponse()
                    data = response.read()
                    self.assertEqual(response.status, 200)
                    return json.loads(data)
                overview = get('/api/evaluation')
                self.assertEqual(overview['runs'][0]['id'], 'gold-v3-formal-20260929')
                current = get('/api/evaluation-run?id=gold-v3-formal-20260929')['summary']
                self.assertEqual(current['retrieval']['all']['complete'], 31)
                gold = get('/api/gold')
                old = get('/api/gold?version=gold-v2')
                self.assertEqual(len(next(q for q in gold if q['id'] == 'S16')['required_elements']), 1)
                self.assertEqual(len(next(q for q in old if q['id'] == 'S16')['required_elements']), 2)
            finally:
                connection.close()
                server.shutdown()
                thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
