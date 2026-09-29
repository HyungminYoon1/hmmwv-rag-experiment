"""Independent arithmetic, provenance and source-image checks. No model calls."""
from pathlib import Path
import sys
import json
import hashlib
import math
import copy
from decimal import Decimal, localcontext
from collections import Counter

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from experiment.evaluation.common import read, save, sha, fingerprint, utc

HERE = Path(__file__).resolve().parent
ACTIVE = read(HERE/'active-evaluation.json') if (HERE/'active-evaluation.json').exists() else {'run_id': 'sol-revision-formal-20260929-v2'}
RUN = ROOT/'experiment/evaluation/runs'/ACTIVE['run_id']
SOURCE = ROOT/'experiment/evaluation/runs'/ACTIVE.get('source_run_id', ACTIVE['run_id'])
OLD = ROOT/'experiment/evaluation/runs/sol-formal-20260928-numeric-v3'
GOLD = ROOT/'experiment/gold-v2'


def verify():
    errors = []; counts = Counter()
    def check(ok, message):
        if not ok: errors.append(message)
    protected = read(ROOT/'backups/before-evaluation-corrections-20260929/protected-inputs.json')
    for name, digest in protected.items(): check(sha(ROOT/name) == digest, 'ORIGINAL_CHANGED '+name)
    counts['original_hashes'] = len(protected)
    backup = ROOT/'backups/before-evaluation-corrections-20260929'
    backup_manifest = read(backup/'backup-manifest.json')
    for name, digest in backup_manifest.items(): check(sha(backup/name) == digest, 'BACKUP_CHANGED '+name)
    counts['backup_hashes'] = len(backup_manifest)
    manifest = read(RUN/'manifest.json'); packet = read(RUN/'inputs.json'); previous = read(RUN/'previous-results.json')
    ident = manifest['identity']
    check(fingerprint(ident) == manifest['identity_hash'], 'IDENTITY_HASH')
    check(fingerprint(packet) == ident['inputs_hash'], 'INPUTS_HASH')
    check(fingerprint(previous) == ident['previous_hash'], 'PREVIOUS_HASH')
    check(fingerprint(ident['code']['files']) == ident['code']['sha256'], 'CODE_FILES_HASH')
    for name, digest in ident['code']['files'].items():
        check(sha(RUN/'code-snapshot'/name) == digest, 'CODE_SNAPSHOT '+name)
    for name, digest in ident['source_hashes'].items(): check(sha(ROOT/name) == digest, 'SOURCE '+name)
    counts['source_hashes'] = len(ident['source_hashes'])
    gold_manifest = read(GOLD/'manifest.json')
    for name, digest in gold_manifest['files'].items(): check(sha(GOLD/name) == digest, 'GOLD '+name)
    rows = {r['attempt_key']: r for r in packet['rows']}
    if RUN != SOURCE:
        source_manifest = read(SOURCE/'manifest.json')
        source_summary = read(SOURCE/'summary.json')
        check(packet == read(SOURCE/'inputs.json'), 'DERIVATIVE_INPUTS_CHANGED')
        check(previous == read(SOURCE/'previous-results.json'), 'DERIVATIVE_PREVIOUS_CHANGED')
        check(manifest['derivation']['new_api_calls'] == 0, 'DERIVATIVE_API_CALLS')
        check(manifest['derivation']['source_api_responses'] == source_summary['provider_response_count'], 'INHERITED_API_COUNT')
        check(manifest['derivation']['source_usage'] == source_summary['usage'], 'INHERITED_API_USAGE')
        repairs = read(RUN/'citation-repairs.json')
        by_key = {}
        for repair in repairs: by_key.setdefault(repair['attempt_key'], []).append(repair)
        for path in sorted((RUN/'results').glob('*.json')):
            source_path = SOURCE/'results'/path.name
            original = read(source_path); derived = read(path)
            check(original['identity_hash'] == source_manifest['identity_hash'] and original['result_hash'] == fingerprint(original['result']), 'SOURCE_RESULT_HASH '+path.stem)
            check(derived['source_result_sha256'] == sha(source_path), 'DERIVATIVE_PARENT_HASH '+path.stem)
            expected = copy.deepcopy(original['result'])
            for repair in by_key.get(path.stem, []):
                stage = repair['stage']; attempt_path = ROOT/repair['source_attempt']
                attempt = read(attempt_path)
                check(sha(attempt_path) == repair['source_attempt_sha256'], 'REPAIRED_CALL_HASH')
                check(stage in expected['errors'] and attempt['error']['code'] == 'UNVERIFIABLE_SOURCE_QUOTE' and attempt['provider']['complete'], 'REPAIR_SCOPE')
                payload = json.loads(attempt['provider']['text'])
                claims = [c['text'] for c in expected['stages']['claims']]
                check([v['statement'] for v in payload['statements']] == claims, 'REPAIR_CLAIMS')
                row = rows[path.stem]
                sources = {'O:'+e['id']: e['text'] for e in row['oracle_evidence']} if stage == 'oracle_support' else dict(zip(row['retrieved_chunk_ids'], row['retrieved_contexts']))
                for change in repair['changes']:
                    verdict = payload['statements'][change['statement_index']]
                    qi = change['quote_index']; cid = change['source_id']
                    check(verdict['evidence_ids'][qi] == cid and verdict['evidence_quotes'][qi] == change['before'], 'REPAIR_ORIGINAL_QUOTE')
                    source = ' '.join(sources[cid].split())
                    after = change['after']
                    check(after == source[change['normalized_source_start']:change['normalized_source_end']], 'REPAIR_EXACT_SPAN')
                    cursor = 0
                    for line in change['before'].splitlines():
                        part = ' '.join(line.split())
                        if not part: continue
                        at = after.find(part, cursor)
                        check(at >= cursor, 'REPAIR_QUOTE_ORDER')
                        cursor = at + len(part)
                    verdict['evidence_quotes'][qi] = after
                    counts['reconstructed_quotes'] += 1
                score = sum(v['verdict'] for v in payload['statements'])/len(payload['statements'])
                expected['stages'][stage] = {'score': score, 'verdicts': payload}
                expected['metrics'][stage] = {'value': score, 'status': 'OK_SOURCE_QUOTE_RECONSTRUCTED'}
                del expected['errors'][stage]
                counts['recovered_stages'] += 1
            check(expected == derived['result'], 'UNDECLARED_RESULT_CHANGE '+path.stem)
            counts['derivative_diff_checks'] += 1
    original_rows = {r['attempt_key']: r for r in read(OLD/'inputs.json')['rows']}
    check(len(rows) == 120, 'INPUT_COUNT')
    counts['questions'] = len({r['question_id'] for r in rows.values()})
    for key, row in rows.items():
        for name in ('user_input', 'response', 'raw_response', 'retrieved_contexts', 'retrieved_chunk_ids', 'type', 'condition', 'attempt_file_sha256'):
            check(row[name] == original_rows[key][name], 'GENERATION_OR_SEARCH_CHANGED '+key+' '+name)
    result_rows = []
    def support_check(stage, claims, sources, tag):
        verdicts = stage['verdicts']['statements']
        check([x['statement'] for x in verdicts] == claims, 'CLAIMS '+tag)
        for v in verdicts:
            check(v['verdict'] in (0, 1), 'NONBINARY '+tag)
            check(len(v['evidence_ids']) == len(v['evidence_quotes']), 'CITATION_COUNT '+tag)
            if v['verdict'] == 1: check(bool(v['evidence_ids']), 'EMPTY_SUPPORTED_CITATION '+tag)
            for cid, quote in zip(v['evidence_ids'], v['evidence_quotes']):
                check(cid in sources and bool(quote.strip()) and ' '.join(quote.split()) in ' '.join(sources.get(cid, '').split()), 'CITATION '+tag+' '+cid)
                counts['source_quotes'] += 1
            counts['support_verdicts'] += 1
        return sum(x['verdict'] for x in verdicts)/len(verdicts) if verdicts else None
    for path in sorted((RUN/'results').glob('*.json')):
        record = read(path); result = record['result']; key = result['attempt_key']; row = rows[key]
        check(fingerprint(result) == record['result_hash'] and record['identity_hash'] == manifest['identity_hash'], 'RESULT_HASH '+key)
        check(record['input_hash'] == fingerprint(row), 'ROW_HASH '+key)
        check(not result['errors'], 'EVALUATOR_ERROR '+key)
        result_rows.append(result); counts['answers'] += 1
        oracle = {'O:'+e['id']: e['text'] for e in row['oracle_evidence']}
        actual = dict(zip(row['retrieved_chunk_ids'], row['retrieved_contexts']))
        stages = result['stages']; metrics = result['metrics']
        if row['type'] == 'unanswerable':
            a = stages.get('abstention')
            check(a is not None, 'ABSTENTION_STAGE_MISSING '+key)
            if not a: continue
            claims = a['partial_claims']
            for name, sources in [('oracle_verdicts', oracle), ('retrieved_verdicts', actual)]:
                support_check({'verdicts': a[name]}, claims, sources, key+'/'+name)
            passed = a['explicitly_withholds_missing'] and not a['supplies_missing_as_fact'] and not a['unrelated_refusal']
            if row['condition'] == 'RAG' and claims:
                passed = passed and a['partial_within_allowed'] and all(v['verdict'] == 1 for name in ['oracle_verdicts', 'retrieved_verdicts'] for v in a[name]['statements'])
            name = 'correct_abstention' if row['condition'] == 'RAG' else 'corpus_unanswerable_abstention'
            check(metrics[name]['value'] == int(passed), 'ABSTENTION_ARITHMETIC '+key)
            counts['abstention_scores'] += 1
        else:
            for name in ['ar_raw', 'ar_report', 'full_abstention']:
                check(metrics[name] == previous[key]['metrics'][name], 'INHERITED_SCORE_CHANGED '+key+'/'+name)
            claims = [c['text'] for c in stages.get('claims', [])]
            for claim in stages.get('claims', []):
                check(bool(claim['answer_quote']) and ' '.join(claim['answer_quote'].split()) in ' '.join(row['response'].split()), 'CLAIM_ANSWER_QUOTE '+key)
            for name, sources in [('oracle_support', oracle)] + ([('faithfulness', actual)] if row['condition'] == 'RAG' else []):
                check(name in stages if claims else name not in stages, 'SUPPORT_STAGE_APPLICABILITY '+key+'/'+name)
                if name in stages:
                    score = support_check(stages[name], claims, sources, key+'/'+name)
                    check(math.isclose(score, metrics[name]['value'], abs_tol=1e-12), 'SUPPORT_ARITHMETIC '+key+'/'+name)
                elif not claims:
                    check(metrics[name]['value'] == (0 if name == 'oracle_support' else None), 'NO_CLAIMS_SCORE '+key+'/'+name)
            coverage = stages.get('coverage', {}).get('elements', [])
            check({e['id'] for e in coverage} == {e['id'] for e in row['required_elements']}, 'COVERAGE_IDS '+key)
            check(len(coverage) == len(row['required_elements']), 'COVERAGE_COUNT '+key)
            if coverage:
                check(math.isclose(sum(e['fulfilled'] for e in coverage)/len(coverage), metrics['required_coverage']['value'], abs_tol=1e-12), 'COVERAGE_ARITHMETIC '+key)
            for e in coverage:
                check(e['fulfilled'] in (0, 1), 'COVERAGE_NONBINARY '+key)
                if e['fulfilled']: check(bool(e['answer_quote']) and ' '.join(e['answer_quote'].split()) in ' '.join(row['response'].split()), 'ANSWER_QUOTE '+key+'/'+e['id'])
                counts['coverage_verdicts'] += 1
    check(len(result_rows) == 120, 'RESULT_COUNT')
    summary = read(RUN/'summary.json')
    for aggregate in summary['aggregate']:
        subset = [r for r in result_rows if r['condition'] == aggregate['condition'] and (aggregate['type'] == 'all' or r['type'] == aggregate['type'])]
        values = [r['metrics'][aggregate['metric']]['value'] for r in subset if r['metrics'][aggregate['metric']]['value'] is not None]
        check(len(values) == aggregate['valid_n'], 'DENOMINATOR')
        with localcontext() as ctx:
            ctx.prec = 50
            expected = float(sum(Decimal(str(v)) for v in values)/Decimal(len(values))) if values else None
        check(expected == aggregate['mean'] if expected is None else math.isclose(expected, aggregate['mean'], abs_tol=1e-12), 'AGGREGATE')
        counts['aggregate_checks'] += 1
    for pair in summary['paired']:
        by_condition = {c: {r['question_id']: r['metrics'][pair['metric']]['value'] for r in result_rows if r['condition'] == c and r['type'] != 'unanswerable' and (pair['type'] == 'all' or r['type'] == pair['type']) and r['metrics'][pair['metric']]['value'] is not None} for c in ['LLM_ONLY', 'RAG']}
        ids = sorted(set(by_condition['LLM_ONLY']) & set(by_condition['RAG']))
        check(ids == pair['question_ids'] and len(ids) == pair['paired_n'], 'PAIRED_IDS')
        expected = math.fsum(by_condition['RAG'][qid]-by_condition['LLM_ONLY'][qid] for qid in ids)/len(ids) if ids else None
        check(expected == pair['mean_rag_minus_llm_only'] if expected is None else math.isclose(expected, pair['mean_rag_minus_llm_only'], abs_tol=1e-12), 'PAIRED_MEAN')
        counts['paired_checks'] += 1
    for request in (SOURCE/'calls').glob('*/claims-v2/request.json'):
        data = json.loads(read(request)['prompt'].split('\n\nDATA:\n', 1)[1])
        check(set(data) == {'user_input', 'response', 'policy'}, 'CLAIM_EXTRACTION_SOURCE_LEAK')
        counts['claim_isolation_checks'] += 1
    returned = set()
    for attempt in (SOURCE/'calls').rglob('attempt-*.json'):
        obj = read(attempt)
        check(obj['record_hash'] == fingerprint({k: v for k, v in obj.items() if k != 'record_hash'}), 'CALL_HASH')
        if obj.get('provider'):
            returned.add(obj['provider']['returned_model']); counts['provider_responses'] += 1
    check(len(returned) == 1, 'RETURNED_MODEL_MIXED')
    check(counts['provider_responses'] == read(SOURCE/'summary.json')['provider_response_count'], 'PROVIDER_RESPONSE_COUNT')
    if RUN != SOURCE:
        check(not list((RUN/'calls').rglob('attempt-*.json')) and summary['provider_response_count'] == 0, 'DERIVATIVE_HAS_NEW_API_CALLS')
    import pymupdf
    pdfpath = ROOT/'제출 논문 초안/논문참고자료/TM_9-2320-280-20-1_1996_Change2_2004_TFS_archive.pdf'
    check(sha(pdfpath) == gold_manifest['source_pdf_sha256'], 'PDF_CHANGED')
    with pymupdf.open(pdfpath) as pdf:
        for cap in read(GOLD/'source-captures.json'):
            check(sha(ROOT/cap['path']) == cap['sha256'], 'CAPTURE_CHANGED')
            png = pdf[cap['pdf_page']-1].get_pixmap(dpi=150, alpha=False).tobytes('png')
            check(hashlib.sha256(png).hexdigest() == cap['sha256'], 'CAPTURE_NOT_PDF_PAGE')
            counts['source_captures'] += 1
    # Separate independent implementation of evidence OR/AND coverage.
    golds = [read(ROOT/'experiment/gold-v1/questions.json'), read(GOLD/'questions.json')]
    retrieval = read(HERE/'retrieval-comparison.json')
    for label, gold in zip(['old', 'new'], golds):
        values = []; complete = 0
        for q in gold:
            if q['type'] == 'unanswerable': continue
            ids = set(original_rows['r1-'+q['id']+'-rag']['retrieved_chunk_ids'])
            flags = [any(all(cid in ids for cid in combo) for combo in g['sufficient_chunk_sets']) for g in q['evidence']]
            values.append(sum(flags)/len(flags)); complete += int(all(flags))
        check(math.isclose(math.fsum(values)/len(values), retrieval[label]['mean_evidence_recall_at_5'], abs_tol=1e-12), 'RETRIEVAL_RECALL')
        check(complete == retrieval[label]['complete_evidence_count'], 'RETRIEVAL_COMPLETE')
    output = {'status': 'PASS' if not errors else 'FAIL', 'at': utc(), 'run_id': RUN.name, 'source_run_id': SOURCE.name, 'checks': dict(counts), 'errors': errors,
              'returned_models': sorted(returned), 'source_semantics': 'AI source review; integrity and arithmetic checks are not human expertise',
              'researcher_direct_review': 'PENDING'}
    save(HERE/'verification.json', output)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if errors: raise SystemExit(1)


if __name__ == '__main__': verify()
