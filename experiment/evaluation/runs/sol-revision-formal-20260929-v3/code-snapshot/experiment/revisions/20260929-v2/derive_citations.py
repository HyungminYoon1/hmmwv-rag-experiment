"""Repair strictly ordered source excerpts in a separate, zero-API derivative."""
from pathlib import Path
import sys
import copy
import json
import re
import shutil
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from experiment.evaluation.common import read, save, sha, fingerprint, utc, EvaluationError
from experiment.evaluation.schemas import SupportOutput
from experiment.evaluation.engine import quotes_valid, norm
from experiment.evaluation.report import summarize

HERE = Path(__file__).resolve().parent
SOURCE = ROOT/'experiment/evaluation/runs/sol-revision-formal-20260929-v2'
TARGET = ROOT/'experiment/evaluation/runs/sol-revision-formal-20260929-v3'


def exact_span(quote, source):
    text = norm(source); q = norm(quote)
    if q and q in text: return quote, None
    parts = [norm(line) for line in quote.splitlines() if norm(line)]
    if sum(len(p) >= 12 for p in parts) < 2:
        raise ValueError('Not enough exact segments')
    starts = [m.start() for m in re.finditer(re.escape(parts[0]), text)]
    spans = []
    for start in starts:
        end = start
        for part in parts:
            at = text.find(part, end)
            if at < 0: break
            end = at + len(part)
        else:
            if end-start <= 4*len(q)+100:
                spans.append((start, end))
    if not spans: raise ValueError('Segments absent, reordered or span too broad')
    start, end = min(spans, key=lambda p: (p[1]-p[0], p[0]))
    replacement = text[start:end]
    return replacement, {'before': quote, 'after': replacement, 'normalized_source_start': start, 'normalized_source_end': end,
                         'method': 'shortest ordered exact-line span; only intervening original text restored'}


def repair(payload, claims, sources):
    parsed = SupportOutput.model_validate(payload, strict=True)
    if [v.statement for v in parsed.statements] != claims:
        raise ValueError('Claim list changed')
    changes = []
    for si, v in enumerate(parsed.statements):
        if len(v.evidence_ids) != len(v.evidence_quotes): raise ValueError('Citation count mismatch')
        for qi, (cid, quote) in enumerate(zip(v.evidence_ids, v.evidence_quotes)):
            if cid not in sources: raise ValueError('Unknown source')
            fixed, detail = exact_span(quote, sources[cid])
            if detail:
                v.evidence_quotes[qi] = fixed
                changes.append({'statement_index': si, 'quote_index': qi, 'source_id': cid, **detail})
    quotes_valid(parsed, sources)
    return parsed, changes


def self_test():
    src = 'INTERVAL: Annually\nITEM NO.: 29\nPROCEDURES: Inspect the case.'
    fixed, detail = exact_span('INTERVAL: Annually\nPROCEDURES: Inspect the case.', src)
    assert fixed == norm(src) and detail
    assert exact_span('Inspect the case.', src)[1] is None
    for bad in ['INTERVAL: Biennially\nPROCEDURES: Inspect the case.', 'PROCEDURES: Inspect the case.\nINTERVAL: Annually', 'ITEM NO.: 30\nPROCEDURES: Inspect the case.']:
        try: exact_span(bad, src)
        except ValueError: pass
        else: raise AssertionError('Invalid excerpt accepted')
    original = {'statements': [{'statement': 'Inspect annually.', 'verdict': 1, 'reason': 'source', 'evidence_ids': ['wrong'], 'evidence_quotes': ['INTERVAL: Annually\nPROCEDURES: Inspect the case.']}]}
    try: repair(original, ['Inspect annually.'], {'right': src})
    except ValueError: pass
    else: raise AssertionError('Wrong source accepted')
    return 6


def recovered_result(record, row):
    result = copy.deepcopy(record['result']); audit = []
    claims = [c['text'] for c in result['stages'].get('claims', [])]
    for label in ['oracle_support', 'faithfulness']:
        if label not in result['errors']: continue
        sources = {'O:'+e['id']: e['text'] for e in row['oracle_evidence']} if label == 'oracle_support' else dict(zip(row['retrieved_chunk_ids'], row['retrieved_contexts']))
        directory = SOURCE/'calls'/row['attempt_key']/(label+'-v2')
        for p in sorted(directory.glob('attempt-*.json')):
            attempt = read(p)
            if attempt.get('error', {}).get('code') != 'UNVERIFIABLE_SOURCE_QUOTE' or not attempt.get('provider', {}).get('complete'): continue
            if attempt['record_hash'] != fingerprint({k: v for k, v in attempt.items() if k != 'record_hash'}):
                raise ValueError('Original attempt changed')
            try:
                payload = json.loads(attempt['provider']['text']); parsed, changes = repair(payload, claims, sources)
            except (ValueError, EvaluationError): continue
            if not changes: continue
            score = sum(v.verdict for v in parsed.statements)/len(parsed.statements)
            result['stages'][label] = {'score': score, 'verdicts': parsed.model_dump(mode='json')}
            result['metrics'][label] = {'value': score, 'status': 'OK_SOURCE_QUOTE_RECONSTRUCTED'}
            del result['errors'][label]
            audit.append({'stage': label, 'source_attempt': p.relative_to(ROOT).as_posix(), 'source_attempt_sha256': sha(p),
                          'changes': changes, 'verdicts_claims_reasons_ids_unchanged': True})
            break
    return result, audit


def preflight():
    checks = self_test(); packet = read(SOURCE/'inputs.json'); inputs = {r['attempt_key']: r for r in packet['rows']}
    found = []
    for p in sorted((SOURCE/'results').glob('*.json')):
        record = read(p)
        if record['result']['errors']:
            result, changes = recovered_result(record, inputs[p.stem])
            found.append({'key': p.stem, 'remaining_errors': result['errors'], 'repairs': changes})
    save(HERE/'citation-repair-preflight.json', {'self_tests_passed': checks, 'cases': found})
    print(json.dumps({'self_tests_passed': checks, 'failed_cases': len(found), 'recoverable': sum(bool(f['repairs']) and not f['remaining_errors'] for f in found)}))


def derive():
    self_test()
    if TARGET.exists(): raise FileExistsError('Derivative exists')
    source_summary = read(SOURCE/'summary.json')
    if source_summary['processed'] != source_summary['expected']: raise ValueError('Collection incomplete')
    sm = read(SOURCE/'manifest.json'); inputs = read(SOURCE/'inputs.json'); previous = read(SOURCE/'previous-results.json')
    rows = {r['attempt_key']: r for r in inputs['rows']}
    identity = copy.deepcopy(sm['identity'])
    for p in [SOURCE/'manifest.json', SOURCE/'inputs.json', SOURCE/'previous-results.json', *sorted((SOURCE/'results').glob('*.json'))]:
        identity['source_hashes'][p.relative_to(ROOT).as_posix()] = sha(p)
    for p in [Path(__file__), HERE/'인용_복원_결정.md']:
        identity['code']['files'][p.relative_to(ROOT).as_posix()] = sha(p)
    identity['code']['sha256'] = fingerprint(identity['code']['files'])
    identity['derivation'] = 'ordered exact-source quote-span reconstruction only; no new model judgments or API calls'
    manifest = copy.deepcopy(sm)
    manifest.update(id=TARGET.name, created_at=utc(), identity=identity, identity_hash=fingerprint(identity), source_evaluation=SOURCE.name,
                    derivation={'method': identity['derivation'], 'new_api_calls': 0, 'source_api_responses': source_summary['provider_response_count'], 'source_usage': source_summary['usage']})
    TARGET.mkdir(parents=True)
    for name, digest in identity['code']['files'].items():
        src = SOURCE/'code-snapshot'/name
        if not src.exists(): src = ROOT/name
        if sha(src) != digest: raise ValueError('Code hash changed')
        dest = TARGET/'code-snapshot'/name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dest)
    save(TARGET/'manifest.json', manifest); save(TARGET/'inputs.json', inputs); save(TARGET/'previous-results.json', previous)
    save(TARGET/'source-summary.json', source_summary)
    repairs = []
    for p in sorted((SOURCE/'results').glob('*.json')):
        old = read(p)
        if old['identity_hash'] != sm['identity_hash'] or old['result_hash'] != fingerprint(old['result']): raise ValueError('Original result changed')
        result, audit = recovered_result(old, rows[p.stem]); repairs.extend({'attempt_key': p.stem, **entry} for entry in audit)
        save(TARGET/'results'/p.name, {'identity_hash': manifest['identity_hash'], 'input_hash': fingerprint(rows[p.stem]),
             'at': utc(), 'source_result_sha256': sha(p), 'result_hash': fingerprint(result), 'result': result})
    save(TARGET/'citation-repairs.json', repairs)
    summary = summarize(TARGET)
    save(HERE/'active-evaluation.json', {'run_id': TARGET.name, 'source_run_id': SOURCE.name, 'new_api_calls_for_derivative': 0,
                                      'source_api_responses': source_summary['provider_response_count'], 'source_usage': source_summary['usage']})
    print(json.dumps({'run': TARGET.name, 'processed': summary['processed'], 'remaining_errors': summary['answers_with_evaluator_errors'], 'repaired_stages': len(repairs), 'new_api_calls': 0}))


if __name__ == '__main__':
    if '--preflight' in sys.argv: preflight()
    else: derive()
