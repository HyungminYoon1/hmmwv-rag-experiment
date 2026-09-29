"""Behavioral checks using small known vectors; no evaluation questions are searched."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer

import numpy as np
import faiss

from retrieval.index import ranked_rows
from retrieval.benchmark import Holdout, normalized_question
from retrieval.common import sha, text_sha, write_json
from retrieval.app import handler_for
from retrieval.service import SearchService


class RankingTests(unittest.TestCase):
    def test_ties_beyond_fifth_are_sorted_by_id(self):
        vectors = np.tile(np.array([[1., 0.]], dtype=np.float32), (9, 1))
        ids = [f'C{i:06d}' for i in range(9, 0, -1)]
        index = faiss.IndexFlatIP(2); index.add(vectors)
        result = ranked_rows(index, vectors[:1], ids, 5)
        self.assertEqual([ids[i] for _, i in result], sorted(ids)[:5])

    def test_larger_cosine_first_and_no_duplicate_rows(self):
        vectors = np.array([[0., 1.], [1., 0.], [.6, .8], [-1., 0.]], dtype=np.float32)
        index = faiss.IndexFlatIP(2); index.add(vectors)
        result = ranked_rows(index, vectors[1:2], ['C1', 'C2', 'C3', 'C4'], 4)
        self.assertEqual([i for _, i in result], [1, 2, 0, 3])
        np.testing.assert_allclose([s for s, _ in result], [1, .6, 0, -1], atol=1e-7)

    def test_nonnormalized_query_rejected(self):
        index = faiss.IndexFlatIP(2); index.add(np.array([[1., 0.]], dtype=np.float32))
        with self.assertRaises(ValueError):
            ranked_rows(index, np.array([[2., 0.]], dtype=np.float32), ['C1'], 1)

    def test_nan_query_rejected(self):
        index = faiss.IndexFlatIP(2); index.add(np.array([[1., 0.]], dtype=np.float32))
        with self.assertRaises(ValueError):
            ranked_rows(index, np.array([[np.nan, 0.]], dtype=np.float32), ['C1'], 1)

    def test_missing_mapping_rejected(self):
        index = faiss.IndexFlatIP(2); index.add(np.array([[1., 0.]], dtype=np.float32))
        with self.assertRaises(ValueError):
            ranked_rows(index, np.array([[1., 0.]], dtype=np.float32), [], 1)


class HoldoutTests(unittest.TestCase):
    def test_normalization_preserves_guard(self):
        self.assertEqual(normalized_question('  WHAT is a TEST? '), normalized_question('what is a test'))

    def test_holdout_guard_and_snapshot_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            write_json(path/'question-hashes.json', {text_sha(normalized_question('Reserved test question?')): 'S01'})
            write_json(path/'manifest.json', {'files': {'question-hashes.json': sha(path/'question-hashes.json')}})
            holdout = Holdout(path)
            with self.assertRaises(ValueError): holdout.require_development('RESERVED test question!')
            holdout.require_development('An unrelated development check')
            write_json(path/'question-hashes.json', {})
            with self.assertRaises(ValueError): Holdout(path)


class HistoryTests(unittest.TestCase):
    def test_searches_in_same_second_follow_timestamp_not_random_id(self):
        with tempfile.TemporaryDirectory() as directory:
            service = SearchService.__new__(SearchService)
            service.records = Path(directory)
            earlier = {'id': '20260928T000000-ffffffffff', 'created_at': '2026-09-28T00:00:00.100000+00:00',
                       'question': 'Earlier development request', 'timing_ms': {}, 'purpose': 'DEVELOPMENT_ONLY'}
            later = {'id': '20260928T000000-0000000000', 'created_at': '2026-09-28T00:00:00.200000+00:00',
                     'question': 'Later development request', 'timing_ms': {}, 'purpose': 'DEVELOPMENT_ONLY'}
            for row in (earlier, later):
                write_json(service.records / (row['id'] + '.json'), row)
            self.assertEqual(service.history(), [later, earlier])


class FakeService:
    encoder = object()
    calls = []
    def search(self, question):
        self.calls.append(question)
        return {'question': question, 'items': []}


class HTTPBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = FakeService()
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(cls.service))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_address[1]}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def request(self, body, extra=None):
        headers = {'Content-Type': 'application/json', 'X-Retrieval-Request': '1'}
        headers.update(extra or {})
        return Request(self.url + '/api/search', json.dumps(body).encode(), headers, method='POST')

    def test_only_question_reaches_service(self):
        question = '<script>not executable</script> development text'
        with urlopen(self.request({'question': question})) as response:
            self.assertEqual(json.load(response)['question'], question)

    def test_oracle_fields_not_accepted(self):
        with self.assertRaises(HTTPError) as caught:
            urlopen(self.request({'question': 'test', 'oracle': 'answer'}))
        self.assertEqual(caught.exception.code, 400)

    def test_cross_origin_rejected(self):
        with self.assertRaises(HTTPError) as caught:
            urlopen(self.request({'question': 'test'}, {'Origin': 'https://example.invalid'}))
        self.assertEqual(caught.exception.code, 403)

    def test_nonlocal_host_rejected(self):
        with self.assertRaises(HTTPError) as caught:
            urlopen(self.request({'question': 'test'}, {'Host': 'example.invalid'}))
        self.assertEqual(caught.exception.code, 403)

    def test_missing_request_header_rejected(self):
        with self.assertRaises(HTTPError) as caught:
            urlopen(self.request({'question': 'test'}, {'X-Retrieval-Request': ''}))
        self.assertEqual(caught.exception.code, 403)


if __name__ == '__main__':
    unittest.main()
