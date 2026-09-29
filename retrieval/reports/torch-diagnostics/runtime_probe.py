"""Repeat a small fixed document sample before the expensive corpus build."""
from __future__ import annotations

import time
import numpy as np
from .common import PACKAGE, load_config, local_path, read_jsonl, environment, write_json
from .model import DenseEncoder


def main():
    config = load_config()
    corpus = read_jsonl(local_path(config['corpus']) / 'chunks.jsonl')
    encoder = DenseEncoder(config)
    report = {'environment': environment(), 'cases': [],
              'training_modules': [type(m).__name__ for m in encoder.model.modules() if m.training],
              'status': 'RUNNING', 'evaluation_questions_used': False}
    report_path = PACKAGE / 'reports' / 'runtime-preflight.json'
    write_json(report_path, report)
    for start in [0, 56]:
        texts = [r['text'] for r in corpus[start:start + 8]]
        begin = time.perf_counter()
        first = encoder.encode(texts).copy()
        second = encoder.encode(texts).copy()
        item = {'start': start, 'finite': bool(np.isfinite(first).all() and np.isfinite(second).all()),
                'bytes_equal': bool(np.array_equal(first, second)),
                'max_difference': float(np.max(np.abs(first - second))),
                'seconds': round(time.perf_counter() - begin, 3)}
        report['cases'].append(item)
        write_json(report_path, report)
        print(item, flush=True)
        if not item['bytes_equal']:
            report['status'] = 'FAIL'
            write_json(report_path, report)
            raise ValueError('Repeated embeddings differ; do not start the full build')
    report['status'] = 'PASS'
    write_json(report_path, report)


if __name__ == '__main__':
    main()
