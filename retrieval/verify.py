"""Independently check every indexed row and replay embeddings offline."""
from __future__ import annotations

import argparse
from unittest.mock import patch

from .common import PACKAGE, load_config, local_path, read_json, sha, write_json, environment
from .source import Corpus
from .index import SearchIndex, ranked_rows
from .benchmark import Holdout


def verify(path, replay=False, full_replay=False):
    config = load_config()
    from .cpu_affinity import apply_cpu_policy
    apply_cpu_policy(config)
    import numpy as np
    import faiss
    corpus = Corpus(config)
    saved = SearchIndex(path, corpus, config)
    if environment() != saved.manifest['identity']['environment']:
        raise ValueError('Verification environment differs from the index build')
    vectors = np.load(path / 'vectors.npy', allow_pickle=False)
    if vectors.dtype != np.float32 or vectors.shape != (len(corpus.chunks), config['embedding_dimension']):
        raise ValueError('Embedding dimensions/dtype differ')
    if not np.isfinite(vectors).all() or not np.allclose(np.linalg.norm(vectors, axis=1), 1, rtol=0, atol=2e-6):
        raise ValueError('Embedding vectors are not finite unit vectors')
    reconstructed = saved.index.reconstruct_n(0, len(vectors))
    if not np.array_equal(vectors, reconstructed):
        raise ValueError('FAISS rows do not match the saved embedding matrix')
    replica = faiss.IndexFlatIP(config['embedding_dimension'])
    replica.add(vectors)
    if faiss.serialize_index(replica).tobytes() != (path / 'index.faiss').read_bytes():
        raise ValueError('Independent FAISS rebuild differs')
    lengths = read_json(path / 'token-lengths.json')
    if set(lengths['by_chunk']) != set(corpus.by_id) or max(lengths['by_chunk'].values()) != lengths['max_observed']:
        raise ValueError('Token length records are incomplete')
    if not 0 < lengths['max_observed'] <= config['max_input_tokens'] or lengths['truncated_count']:
        raise ValueError('Embedding input truncation detected')
    batch_order = read_json(path / 'batch-order.json')['row_indices']
    expected_order = sorted(range(len(vectors)), key=lambda i: (-lengths['by_chunk'][saved.ids[i]], saved.ids[i]))
    if batch_order != expected_order:
        raise ValueError('Document batch order differs from the recorded rule')
    probe_rows = sorted({0, len(vectors) // 4, len(vectors) // 2, len(vectors) - 1})
    max_score_error = 0.0
    for row in probe_rows:
        q = vectors[row:row + 1].copy()
        scored = ranked_rows(saved.index, q, saved.ids, len(saved.ids))
        reference = vectors @ q[0]
        error = max(abs(float(reference[i]) - score) for score, i in scored)
        max_score_error = max(max_score_error, error)
        if error > 2e-6:
            raise ValueError('FAISS scores differ from the independent NumPy dot products')
        if ranked_rows(saved.index, q, saved.ids, 5) != scored[:5]:
            raise ValueError('Top-five selection differs from full ranking')
    holdout = Holdout(local_path(config['holdout']))
    for name, expected in holdout.manifest['original_files'].items():
        if sha(local_path(name)) != expected:
            raise ValueError('An original evaluation-question file changed')
    result = {'status': 'PASS', 'rows_checked': len(vectors), 'dimension': vectors.shape[1],
              'all_rows_match_faiss': True, 'independent_index_bytes_identical': True,
              'score_probe_count': len(probe_rows), 'max_numpy_score_difference': max_score_error,
              'corpus_manifest_sha256': corpus.manifest_sha256, 'index_manifest_sha256': saved.manifest_sha256,
              'max_embedding_tokens': lengths['max_observed'], 'truncated_documents': 0,
              'evaluation_questions_preserved': 60, 'evaluation_queries_executed': 0,
              'relevance_evaluation': 'NOT_RUN', 'embedding_replay': 'NOT_RUN'}
    if replay or full_replay:
        from .model import DenseEncoder
        starts = (list(range(0, len(vectors), 8)) if full_replay else
                  [0, (len(vectors) // 2 // 8) * 8, ((len(vectors) - 8) // 8) * 8])
        compared = 0
        byte_equal = True
        max_difference = 0.0
        # This verifies Python network calls are unnecessary for loading and
        # inference; it is not a machine-wide network isolation certification.
        with patch('socket.socket.connect', side_effect=AssertionError('Unexpected network call during offline replay')):
            encoder = DenseEncoder(config)
            actual_lengths = encoder.token_lengths([c['text'] for c in corpus.chunks])
            if actual_lengths != [lengths['by_chunk'][c['id']] for c in corpus.chunks]:
                raise ValueError('Recomputed token lengths differ')
            for start in starts:
                end = min(start + 8, len(vectors))
                positions = batch_order[start:end]
                actual = encoder.encode([corpus.chunks[i]['text'] for i in positions])
                expected = vectors[positions]
                byte_equal &= np.array_equal(actual, expected)
                max_difference = max(max_difference, float(np.max(np.abs(actual - expected))))
                if full_replay and not np.array_equal(actual, expected):
                    raise ValueError(f'Full embedding replay differs at batch {start}')
                if not np.allclose(actual, expected, atol=2e-6, rtol=0):
                    raise ValueError('Embedding replay differs beyond the recorded tolerance')
                compared += end - start
                if start % 160 == 0 or compared == len(vectors):
                    print(f'Embedding replay: {compared}/{len(vectors) if full_replay else 24}', flush=True)
        result.update(embedding_replay='PASS', replayed_document_count=compared,
                      replayed_document_bytes_identical=bool(byte_equal),
                      maximum_replay_difference=max_difference,
                      full_embedding_replay=full_replay,
                      offline_python_socket_check='PASS', environment=environment())
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index')
    parser.add_argument('--replay-model', action='store_true')
    parser.add_argument('--full-replay', action='store_true')
    parser.add_argument('--report', default='retrieval/reports/index-verification.json')
    args = parser.parse_args()
    result = verify(local_path(args.index or load_config()['index']), args.replay_model, args.full_replay)
    write_json(local_path(args.report), result)
    print(result)
