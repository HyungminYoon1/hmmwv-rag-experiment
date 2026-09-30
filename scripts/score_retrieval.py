"""Score saved first-round retrieval with an explicit gold version; no models."""
import argparse
import json
import sys
from pathlib import Path
from artifact_io import ROOT, read, sha, safe_path
sys.path.insert(0, str(ROOT))
from experiment.correction_statistics import retrieval

def score(source_run, gold_version):
    from experiment.evaluation.common import valid_id
    valid_id(source_run)
    if gold_version not in ('gold-v1', 'gold-v2', 'gold-v3'):
        raise ValueError('Unknown gold version')
    folder = ROOT / 'experiment/runs' / source_run
    gold_file = ROOT / 'experiment' / gold_version / 'questions.json'
    gold = read(gold_file)
    rows, sources = {}, {}
    for q in gold:
        if q['type'] == 'unanswerable':
            continue
        path = folder / 'attempts' / ('r1-' + q['id'] + '-rag.json')
        r = read(path)
        if r['question'] != q['question'] or r['status'] != 'OK' or r['condition'] != 'RAG':
            raise ValueError('Question or successful retrieval differs: ' + q['id'])
        ids = [c['id'] for c in r['retrieval']['items']]
        if len(ids) != 5 or len(set(ids)) != 5:
            raise ValueError('Expected five distinct retrieved chunks')
        rows['r1-' + q['id'] + '-rag'] = {'retrieved_chunk_ids': ids}
        sources[path.relative_to(ROOT).as_posix()] = sha(path)
    return {'source_run': source_run, 'gold_version': gold_version, 'gold_sha256': sha(gold_file),
            'source_hashes': sources, 'retrieval': retrieval(gold, rows), 'new_api_calls': 0}

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-run', required=True)
    p.add_argument('--gold-version', choices=['gold-v1', 'gold-v2', 'gold-v3'], default='gold-v3')
    p.add_argument('--output', default='validation/local/retrieval-gold-v3.json')
    args = p.parse_args()
    result = score(args.source_run, args.gold_version)
    target = safe_path(ROOT, args.output)
    if not target.is_relative_to(ROOT / 'validation/local'):
        raise ValueError('Reports must go to validation/local')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\r\n')
    print(json.dumps(result['retrieval']['summary'], ensure_ascii=False, indent=2))
