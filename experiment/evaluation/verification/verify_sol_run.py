"""Verify frozen Sol results and arithmetic without asking an LLM."""
import argparse
import math
from collections import Counter
from pathlib import Path
from statistics import mean
from experiment.evaluation.common import BASE, read, save, fingerprint, utc
from experiment.evaluation.runner import verify


def check(directory, require_complete=False):
    manifest, packet = verify(directory)
    expected = {r['attempt_key']: r for r in packet['rows']}
    records = [read(p) for p in sorted((directory / 'results').glob('*.json'))]
    by_key = {}
    maximum_ar_difference = 0.0
    support_claims = coverage_elements = checked_ar = 0
    for record in records:
        result = record['result']
        key = result['attempt_key']
        assert key in expected and key not in by_key
        assert record['identity_hash'] == manifest['identity_hash']
        assert record['input_hash'] == fingerprint(expected[key])
        assert record['result_hash'] == fingerprint(result)
        by_key[key] = result
        metrics, stages = result['metrics'], result['stages']
        for metric in metrics.values():
            assert metric['value'] is None or math.isfinite(metric['value'])
        for label in ('oracle_support', 'faithfulness'):
            if label in stages:
                statements = stages[label]['verdicts']['statements']
                assert [s['statement'] for s in statements] == [s['text'] for s in stages['claims']]
                calculated = sum(s['verdict'] for s in statements) / len(statements)
                assert abs(calculated - metrics[label]['value']) < 1e-12
                sources = ({'O:' + e['id']: e['text'] for e in expected[key]['oracle_evidence']}
                           if label == 'oracle_support' else dict(zip(expected[key]['retrieved_chunk_ids'], expected[key]['retrieved_contexts'])))
                for s in statements:
                    assert len(s['evidence_ids']) == len(s['evidence_quotes'])
                    assert s['verdict'] != 1 or s['evidence_ids']
                    for source, quote in zip(s['evidence_ids'], s['evidence_quotes']):
                        assert quote.strip() and ' '.join(quote.split()) in ' '.join(sources[source].split())
                support_claims += len(statements)
        if 'coverage' in stages:
            elements = stages['coverage']['elements']
            assert sorted(e['id'] for e in elements) == sorted(e['id'] for e in expected[key]['required_elements'])
            calculated = sum(e['fulfilled'] for e in elements) / len(elements)
            assert abs(calculated - metrics['required_coverage']['value']) < 1e-12
            for e in elements:
                assert not e['fulfilled'] or (e['answer_quote'].strip() and ' '.join(e['answer_quote'].split()) in ' '.join(expected[key]['response'].split()))
            coverage_elements += len(elements)
        if 'relevancy_numeric_recalculation' in stages:
            audit=stages['relevancy_numeric_recalculation']
            assert audit['reference_implementation']=='python_math_fsum_and_decimal50'
            calculated=math.fsum(audit['cosine_similarities'])/3*int(not all(audit['flags']))
            assert abs(calculated-metrics['ar_report']['value']) <= 1e-10
            assert all(abs(x-float(y))<=1e-10 for x,y in zip(audit['cosine_similarities'],audit['decimal50_cosines']))
            assert metrics['ar_raw']==metrics['ar_report'] and audit['model_calls']==0
            checked_ar+=1
            maximum_ar_difference=max(maximum_ar_difference,audit['maximum_implementation_difference'])
        elif 'answer_relevancy' in stages:
            audit = stages['relevancy_calculation_audit']
            assert audit['reference_implementation'] == 'python_math_fsum_cosine'
            assert len(audit['flags']) == len(audit['cosine_similarities']) == 3
            calculated = math.fsum(audit['cosine_similarities']) / 3 * int(not all(audit['flags']))
            difference = abs(calculated - metrics['ar_raw']['value'])
            assert difference <= 1e-10
            assert metrics['ar_raw'] == metrics['ar_report']
            maximum_ar_difference = max(maximum_ar_difference, difference)
            checked_ar += 1
    summary = read(directory / 'summary.json')
    assert summary['processed'] == len(records) and summary['expected'] == len(expected)
    if require_complete:
        assert set(by_key) == set(expected)
    aggregate_checks = paired_checks = 0
    for entry in summary['aggregate']:
        rows = [r for r in by_key.values() if r['condition'] == entry['condition'] and (entry['type'] == 'all' or r['type'] == entry['type'])]
        scores = [r['metrics'][entry['metric']]['value'] for r in rows if r['metrics'][entry['metric']]['value'] is not None]
        assert entry['valid_n'] == len(scores) and entry['processed_n'] == len(rows)
        assert (entry['mean'] is None and not scores) or abs(entry['mean'] - mean(scores)) < 1e-12
        aggregate_checks += 1
    for entry in summary['paired']:
        values = {}
        for condition in ('LLM_ONLY', 'RAG'):
            values[condition] = {r['question_id']: r['metrics'][entry['metric']]['value'] for r in by_key.values()
                                 if r['condition'] == condition and r['type'] != 'unanswerable'
                                 and (entry['type'] == 'all' or r['type'] == entry['type'])
                                 and r['metrics'][entry['metric']]['value'] is not None}
        ids = sorted(set(values['LLM_ONLY']) & set(values['RAG']))
        assert ids == entry['question_ids'] and len(ids) == entry['paired_n']
        if ids:
            difference = mean(values['RAG'][q] - values['LLM_ONLY'][q] for q in ids)
            assert abs(difference - entry['mean_rag_minus_llm_only']) < 1e-12
        else:
            assert entry['mean_rag_minus_llm_only'] is None
        paired_checks += 1
    calls_directory=directory
    counts_summary=summary
    calls_identity=manifest['identity_hash']
    if 'numerical_recalculation' in manifest['identity']:
        calls_directory=BASE/'runs'/manifest['source_evaluation']
        counts_summary=read(calls_directory/'summary.json')
        calls_identity=read(calls_directory/'manifest.json')['identity_hash']
        assert not list((directory/'calls').rglob('attempt-*.json'))
        assert summary['provider_response_count']==0 and summary['usage']=={}
        source_results={read(p)['result']['attempt_key']:read(p)['result'] for p in (calls_directory/'results').glob('*.json')}
        for key,result in by_key.items():
            for name,value in result['metrics'].items():
                if name not in ('ar_raw','ar_report'):assert value==source_results[key]['metrics'][name]
    attempts = list((calls_directory / 'calls').rglob('attempt-*.json'))
    models, statuses, usage = Counter(), Counter(), Counter()
    for path in attempts:
        record = read(path)
        assert record['record_hash'] == fingerprint({k: v for k, v in record.items() if k != 'record_hash'})
        request = read(path.parent / 'request.json')
        assert request['request_hash'] == fingerprint({k: v for k, v in request.items() if k != 'request_hash'})
        assert record['request_hash'] == request['request_hash'] and request['identity'] == calls_identity
        assert 1 <= record['attempt'] <= 3
        statuses[record['status']] += 1
        provider = record.get('provider')
        if provider:
            models[provider['returned_model']] += 1
            for name in ('input_tokens', 'output_tokens'):
                usage[name] += (provider.get('usage') or {}).get(name, 0)
        if require_complete:
            assert record['status'] != 'STARTED'
    assert len(models) == 1 and 'gpt-6-sol' in next(iter(models))
    assert dict(usage) == counts_summary['usage']
    assert sum(models.values()) == counts_summary['provider_response_count'] and len(attempts) == counts_summary['attempt_slots_used']
    assert summary['researcher_source_review'] == summary['human_evaluator_validation'] == 'PENDING'
    assert summary['final_quality_claims_ready'] is False
    result = {'at': utc(), 'run': manifest['id'], 'status': 'PASS', 'complete_required': require_complete,
              'answers': len(records), 'source_hashes_verified': len(manifest['identity']['source_hashes']),
              'code_files_verified': len(manifest['identity']['code']['files']), 'support_claim_checks': support_claims,
              'coverage_element_checks': coverage_elements, 'relevancy_checks': checked_ar,
              'maximum_relevancy_difference': maximum_ar_difference, 'aggregate_checks': aggregate_checks,
              'paired_checks': paired_checks, 'api_attempt_statuses': dict(statuses), 'returned_models': dict(models),
              'usage': dict(usage), 'api_call_source': calls_directory.name, 'answers_with_evaluator_errors': summary['answers_with_evaluator_errors'],
              'scope': 'Artifact hashes, citations and arithmetic only; not human semantic validation.'}
    save(directory / 'independent-verification.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--id', default='sol-formal-20260928-v1')
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    from experiment.evaluation.common import valid_id
    import json
    print(json.dumps(check(BASE / 'runs' / valid_id(args.id), args.require_complete), ensure_ascii=False, indent=2))
