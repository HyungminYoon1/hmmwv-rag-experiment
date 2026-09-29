"""Create/resume a reproducible dense index without reading evaluation questions."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from .common import (PACKAGE, ROOT, load_config, local_path, sha, read_json,
                     write_json, environment, pipeline_hashes)
from .source import Corpus
from .model import DenseEncoder
from .cpu_affinity import apply_cpu_policy


def build(output: Path, resume=False):
    import numpy as np
    import faiss
    config = load_config()
    apply_cpu_policy(config)
    output = output.resolve()
    if not output.is_relative_to((PACKAGE / 'indexes').resolve()) or output == (PACKAGE / 'indexes').resolve():
        raise ValueError('Index output must be inside retrieval/indexes')
    if (output / 'manifest.json').exists():
        raise ValueError('Completed indexes are immutable; use a new directory')
    if output.exists() and not resume:
        raise ValueError('Partial output exists; use --resume or a new directory')
    print('Verifying frozen corpus and model...', flush=True)
    started = time.perf_counter()
    corpus = Corpus(config)
    identity = {'config': config, 'corpus_manifest_sha256': corpus.manifest_sha256,
                'model_lock_sha256': sha(local_path(config['model_lock'])),
                'environment': environment(), 'pipeline': pipeline_hashes()}
    state_path = output / 'build-state.json'
    if state_path.exists() and read_json(state_path) != identity:
        raise ValueError('Partial build inputs/code/environment changed; use a new directory')
    output.mkdir(parents=True, exist_ok=True)
    write_json(state_path, identity)
    encoder = DenseEncoder(config)
    texts = [c['text'] for c in corpus.chunks]
    lengths = encoder.token_lengths(texts)
    if max(lengths) > config['max_input_tokens']:
        raise ValueError('A document would be truncated by the embedding tokenizer')
    write_json(output / 'token-lengths.json', {
        'tokenizer': config['model_id'], 'special_tokens_included': True,
        'max_allowed': config['max_input_tokens'], 'max_observed': max(lengths),
        'truncated_count': 0, 'by_chunk': dict(zip([c['id'] for c in corpus.chunks], lengths))})
    size = config['document_batch_size']
    order = sorted(range(len(texts)), key=lambda i: (-lengths[i], corpus.chunks[i]['id']))
    write_json(output / 'batch-order.json', {'order': config['document_batch_order'], 'row_indices': order})
    work = output / 'batches'
    work.mkdir(exist_ok=True)
    vectors = np.empty((len(texts), config['embedding_dimension']), dtype=np.float32)
    reused = 0
    for start in range(0, len(texts), size):
        end = min(start + size, len(texts))
        positions = order[start:end]
        data_path = work / f'{start:06d}.npy'
        receipt_path = data_path.with_suffix('.json')
        if data_path.exists() and receipt_path.exists():
            receipt = read_json(receipt_path)
            if receipt != {'start': start, 'end': end, 'positions': positions, 'sha256': sha(data_path)}:
                raise ValueError('A saved embedding batch was modified')
            batch = np.load(data_path, allow_pickle=False)
            reused += 1
        else:
            batch = encoder.encode([texts[i] for i in positions])
            temporary = data_path.with_suffix('.tmp')
            with temporary.open('wb') as stream:
                np.save(stream, batch, allow_pickle=False)
            temporary.replace(data_path)
            write_json(receipt_path, {'start': start, 'end': end, 'positions': positions, 'sha256': sha(data_path)})
        if batch.shape != (end - start, config['embedding_dimension']) or batch.dtype != np.float32:
            raise ValueError('Invalid saved batch shape/dtype')
        if not np.isfinite(batch).all() or not np.allclose(np.linalg.norm(batch, axis=1), 1, atol=2e-6, rtol=0):
            raise ValueError('Invalid saved batch normalization')
        vectors[positions] = batch
        if start % (size * 20) == 0 or end == len(texts):
            progress = {'completed': end, 'total': len(texts), 'elapsed_seconds': round(time.perf_counter() - started, 2)}
            write_json(output / 'progress.json', progress)
            print(json.dumps(progress), flush=True)
    with (output / 'vectors.npy').open('wb') as stream:
        np.save(stream, vectors, allow_pickle=False)
    index = faiss.IndexFlatIP(config['embedding_dimension'])
    index.add(vectors)
    (output / 'index.faiss').write_bytes(faiss.serialize_index(index).tobytes())
    write_json(output / 'rows.json', [{'id': c['id'], 'text_sha256': c['text_sha256']} for c in corpus.chunks])
    artifacts = ['vectors.npy', 'index.faiss', 'rows.json', 'token-lengths.json', 'batch-order.json']
    write_json(output / 'manifest.json', {'schema': 1, 'status': 'READY', 'identity': identity,
               'count': len(texts), 'dimension': config['embedding_dimension'],
               'files': {name: sha(output / name) for name in artifacts}})
    write_json(output / 'build-run.json', {'finished_at': datetime.now(timezone.utc).isoformat(),
               'elapsed_seconds': round(time.perf_counter() - started, 3), 'reused_batches': reused,
               'evaluation_questions_used': False, 'llm_calls': 0, 'inference_network': False})
    print('Index complete: ' + str(output.relative_to(ROOT)), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    build(local_path(args.output or load_config()['index']), args.resume)
