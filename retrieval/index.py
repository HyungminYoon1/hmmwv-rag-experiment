"""Exact FAISS search and strict artifact loading, independent of HTTP."""
from __future__ import annotations

from .common import read_json, sha, check_files, pipeline_hashes, local_path


def ranked_rows(index, query, chunk_ids, top_k):
    import numpy as np
    if query.shape != (1, index.d) or not np.isfinite(query).all():
        raise ValueError('Invalid query vector')
    if not np.allclose(np.linalg.norm(query, axis=1), 1, atol=2e-6, rtol=0):
        raise ValueError('Query vector must be L2-normalized')
    if not 1 <= top_k <= index.ntotal or len(chunk_ids) != index.ntotal:
        raise ValueError('Invalid result count or index mapping')
    # Search all rows so equal scores at the top-k boundary cannot depend on
    # FAISS's unspecified tie ordering. This is exact search over 8,344 rows.
    distances, indices = index.search(np.ascontiguousarray(query, dtype=np.float32), index.ntotal)
    candidates = [(float(score), int(row)) for score, row in zip(distances[0], indices[0])]
    if any(row < 0 or not np.isfinite(score) for score, row in candidates):
        raise ValueError('Invalid FAISS output')
    candidates.sort(key=lambda item: (-item[0], chunk_ids[item[1]]))
    return candidates[:top_k]


class SearchIndex:
    def __init__(self, path, corpus, config, check_code=True):
        import numpy as np
        import faiss
        self.path = path
        self.manifest = read_json(path / 'manifest.json')
        self.manifest_sha256 = sha(path / 'manifest.json')
        if self.manifest['status'] != 'READY':
            raise ValueError('Index is not complete')
        check_files(path, self.manifest['files'])
        identity = self.manifest['identity']
        if identity['corpus_manifest_sha256'] != corpus.manifest_sha256:
            raise ValueError('Index and corpus versions differ')
        if identity['config'] != config:
            raise ValueError('Index configuration differs; build a new index')
        if identity['model_lock_sha256'] != sha(local_path(config['model_lock'])):
            raise ValueError('Index was created from another model snapshot')
        if check_code and identity['pipeline'] != pipeline_hashes():
            raise ValueError('Index pipeline has changed; rebuild or restore the recorded version')
        self.rows = read_json(path / 'rows.json')
        self.ids = [r['id'] for r in self.rows]
        if self.ids != [c['id'] for c in corpus.chunks]:
            raise ValueError('Index IDs do not correspond to the frozen corpus')
        if any(r['text_sha256'] != c['text_sha256'] for r, c in zip(self.rows, corpus.chunks)):
            raise ValueError('Indexed text hashes differ from the corpus')
        # deserialize_index accepts bytes, unlike Windows narrow-path read_index.
        self.index = faiss.deserialize_index(np.frombuffer((path / 'index.faiss').read_bytes(), dtype=np.uint8))
        if type(self.index).__name__ != 'IndexFlatIP' or self.index.metric_type != faiss.METRIC_INNER_PRODUCT:
            raise ValueError('Expected an exact IndexFlatIP index')
        if self.index.ntotal != len(self.rows) or self.index.d != config['embedding_dimension']:
            raise ValueError('Index size/dimension mismatch')
        self.corpus = corpus
        self.config = config

    def search_vector(self, vector):
        matches = ranked_rows(self.index, vector, self.ids, self.config['top_k'])
        return [{'rank': rank, 'score': score, **self.corpus.by_id[self.ids[row]]}
                for rank, (score, row) in enumerate(matches, 1)]
