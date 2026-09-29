"""Search orchestration and local records. No HTTP or presentation logic."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import threading
import time
import uuid

from .common import PACKAGE, load_config, local_path, read_json, write_json, sha, environment
from .source import Corpus
from .index import SearchIndex
from .benchmark import Holdout


class BusyError(RuntimeError):
    pass


class SearchService:
    def __init__(self, encoder=None):
        self.config = load_config()
        from .cpu_affinity import apply_cpu_policy
        apply_cpu_policy(self.config)
        self.corpus = Corpus(self.config)
        self.index = SearchIndex(local_path(self.config['index']), self.corpus, self.config)
        if environment() != self.index.manifest['identity']['environment']:
            raise ValueError('Runtime environment differs from the verified index build')
        verification = read_json(PACKAGE / 'reports' / 'index-verification.json')
        if (verification.get('status') != 'PASS'
            or verification.get('index_manifest_sha256') != self.index.manifest_sha256
            or not verification.get('full_embedding_replay')
            or verification.get('replayed_document_count') != len(self.corpus.chunks)
            or not verification.get('replayed_document_bytes_identical')):
            raise ValueError('This index has not passed independent full embedding replay')
        self.holdout = Holdout(local_path(self.config['holdout']))
        self.encoder = encoder
        self.lock = threading.Lock()
        self.records = PACKAGE / 'runs' / 'development'
        self.load_error = None

    def load_model(self):
        from .model import DenseEncoder
        self.encoder = DenseEncoder(self.config)

    def status(self):
        return {'application': 'kidet-retrieval', 'ready': self.encoder is not None,
                'error': self.load_error, 'corpus': Path(self.config['corpus']).name,
                'chunks': len(self.corpus.chunks), 'pages': self.corpus.audit['scope_pages'],
                'model': self.config['model_id'], 'device': self.config['device'],
                'top_k': self.config['top_k'], 'index': Path(self.config['index']).name,
                'index_manifest_sha256': self.index.manifest_sha256,
                'corpus_manifest_sha256': self.corpus.manifest_sha256,
                'evaluation_questions': self.holdout.manifest['question_count'],
                'evaluation_status': 'NOT_RUN', 'ground_truth': self.holdout.manifest['ground_truth_status']}

    def search(self, question):
        if not isinstance(question, str) or not question.strip() or len(question) > 16000:
            raise ValueError('검색할 질문을 1~16,000자로 입력해주세요.')
        self.holdout.require_development(question)
        if self.encoder is None:
            raise BusyError('검색 모델을 준비하고 있습니다. 잠시 후 다시 시도해주세요.')
        if not self.lock.acquire(blocking=False):
            raise BusyError('다른 검색이 진행 중입니다. 완료 후 다시 시도해주세요.')
        try:
            start = time.perf_counter()
            vector = self.encoder.encode([question])
            encoded = time.perf_counter()
            items = self.index.search_vector(vector)
            finished = time.perf_counter()
            record_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:10]
            result = {
                'schema': 1, 'id': record_id, 'created_at': datetime.now(timezone.utc).isoformat(),
                'purpose': 'DEVELOPMENT_ONLY', 'question': question, 'items': items,
                'timing_ms': {'query_embedding': (encoded - start) * 1000,
                              'search_and_materialization': (finished - encoded) * 1000,
                              'retrieval_total': (finished - start) * 1000},
                'timing_scope': 'Warm/cold state may vary; not a formal benchmark. Excludes queue wait and record writing.',
                'index_manifest_sha256': self.index.manifest_sha256,
                'corpus_manifest_sha256': self.corpus.manifest_sha256,
                'model_revision': self.config['model_revision'], 'top_k': self.config['top_k'],
                'runtime_environment': environment(),
                'search_code': {name: sha(PACKAGE / name) for name in
                                ('service.py', 'model.py', 'index.py', 'source.py', 'common.py', 'benchmark.py')},
                'generated_answer': None}
            write_json(self.records / (record_id + '.json'), result)
            return result
        finally:
            self.lock.release()

    def history(self):
        if not self.records.exists():
            return []
        records = []
        for path in self.records.glob('*.json'):
            row = read_json(path)
            records.append({k: row[k] for k in ('id', 'created_at', 'question', 'timing_ms', 'purpose')})
        return sorted(records, key=lambda row: (row['created_at'], row['id']), reverse=True)[:100]

    def record(self, record_id):
        if not re.fullmatch(r'\d{8}T\d{6}-[a-f0-9]{10}', record_id):
            raise ValueError('Invalid search record ID')
        return read_json(self.records / (record_id + '.json'))

    def information(self):
        return {'status': self.status(), 'config': self.config,
                'environment': self.index.manifest['identity']['environment'],
                'tokens': {k: v for k, v in read_json(self.index.path / 'token-lengths.json').items() if k != 'by_chunk'},
                'benchmark': {k: v for k, v in self.holdout.manifest.items()
                              if k in ('question_set_status', 'question_count', 'types', 'ground_truth_status', 'change_policy')}}
