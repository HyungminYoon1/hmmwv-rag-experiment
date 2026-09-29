"""Prepare and run a separate post-review evaluation; old runs remain immutable."""
import argparse
import asyncio
import copy
import json
import os
import shutil
import sys
import time
from .common import BASE, ROOT, EXPERIMENT, read, save, sha, fingerprint, utc, valid_id, EvaluationError, safe_error
from .inputs import source_packet, code_identity, environment
from .runner import profile_named, run_lock
from .providers import Transport
from .judge import Journal
from .report import completed, summarize
from .revision_engine import RevisedEvaluator

PREVIOUS = 'sol-formal-20260928-numeric-v3'


def revision_code():
    c = code_identity()
    for p in [EXPERIMENT/'revision_gold.py', EXPERIMENT/'revisions/20260929-v2/DECISIONS.md']:
        c['files'][p.relative_to(ROOT).as_posix()] = sha(p)
    c['sha256'] = fingerprint(c['files'])
    return c


def smoke_rows():
    common = {'generation_status': 'OK', 'type': 'single-evidence', 'condition': 'RAG',
              'missing_information': None, 'allowed_partial_answer': None, 'predeclared_note': '',
              'retrieved_chunk_ids': ['fixture'], 'evaluation_status': 'SMOKE_ONLY'}
    data = [
        ('scope', 'In non-freezing storage, what fluid is required for the fictional sensor case?',
         'In non-freezing storage, use fluid A only. I was not supplied with manual excerpts.',
         'For the fictional sensor case, non-freezing storage requires fluid A only; freezing storage uses fluid B.',
         [{'id': 'fluid', 'text': 'Fluid A only for non-freezing storage.'}]),
        ('optional', 'What cleaning method is prohibited for the fictional sensor? Why is solvent harmful?',
         'Solvent is prohibited. It probably damages the seal. I cannot independently confirm that explanation.',
         'Do not use solvent for the fictional sensor. It damages the seal.',
         [{'id': 'prohibition', 'text': 'Do not use solvent.'}, {'id': 'reason', 'text': 'Solvent damages the seal.'}]),
        ('partial', 'Give the complete removal and installation sequence for the fictional sensor.',
         'The full removal and installation procedure is not provided. A visual crack inspection is described.',
         'The supplied manual describes a visual crack inspection. For the full replacement procedure, refer to volume 2 section 4.', [])
    ]
    rows = []
    for name, question, answer, context, elements in data:
        row = copy.deepcopy(common)
        row.update(attempt_key='fixture-'+name, question_id='fixture-'+name, user_input=question, response=answer,
                   raw_response=answer, oracle_evidence=[{'id': 'fixture', 'text': context, 'sources': []}],
                   retrieved_contexts=[context], required_elements=elements)
        if name == 'partial':
            row.update(type='unanswerable', missing_information='Complete removal and installation procedure.',
                       allowed_partial_answer='Visual crack inspection and volume 2 section 4 reference.')
        rows.append(row)
    return rows


def prepare(run_id, smoke=False):
    directory = BASE/'runs'/valid_id(run_id)
    if directory.exists(): raise EvaluationError('RUN_ALREADY_EXISTS')
    gold_dir = EXPERIMENT/'gold-v2'
    gold_manifest = read(gold_dir/'manifest.json')
    for name, expected in gold_manifest['files'].items():
        if sha(gold_dir/name) != expected: raise EvaluationError('GOLD_V2_CHANGED')
    policy = read(gold_dir/'evaluation-policy.json')
    sources = {(gold_dir/'manifest.json').relative_to(ROOT).as_posix(): sha(gold_dir/'manifest.json')}
    for name, digest in gold_manifest['files'].items():
        sources[(gold_dir/name).relative_to(ROOT).as_posix()] = digest
    previous = {}; parent = BASE/'runs'/PREVIOUS
    if smoke:
        rows = smoke_rows()
        for r in rows:
            previous[r['attempt_key']] = {'metrics': {k: {'value': v, 'status': 'SYNTHETIC_FIXED'} for k, v in [('ar_raw', 1), ('ar_report', 1), ('full_abstention', 0)]},
                                          'stages': {'answer_kind': {'kind': 'normal', 'contains_factual_claims': True, 'reason': 'synthetic fixture'}}}
    else:
        rows, _, original_sources = source_packet('formal-v1'); sources.update(original_sources)
        old_inputs = {r['attempt_key']: r for r in read(parent/'inputs.json')['rows']}
        gold = {q['id']: q for q in read(gold_dir/'questions.json')}
        parent_manifest = read(parent/'manifest.json')
        for row in rows:
            old = old_inputs[row['attempt_key']]
            for name in ('user_input', 'response', 'raw_response', 'retrieved_contexts', 'retrieved_chunk_ids', 'type', 'condition'):
                if row[name] != old[name]: raise EvaluationError('ORIGINAL_ROW_CHANGED')
            q = gold[row['question_id']]
            if q['question'] != row['user_input']: raise EvaluationError('QUESTION_CHANGED')
            row.update(oracle_evidence=q['oracle_evidence'], required_elements=q['required_elements'],
                       allowed_partial_answer=q['allowed_partial_answer'], predeclared_note=q['review_note'],
                       evaluation_status='POST_REVIEW_V2', rubric_timing='AFTER_INITIAL_RESULTS')
            path = parent/'results'/(row['attempt_key']+'.json'); record = read(path)
            if record['result_hash'] != fingerprint(record['result']) or record['identity_hash'] != parent_manifest['identity_hash']:
                raise EvaluationError('PARENT_RESULT_INTEGRITY_MISMATCH')
            sources[path.relative_to(ROOT).as_posix()] = sha(path)
            previous[row['attempt_key']] = record['result']
    profile = profile_named('openai-sol')
    packet = {'rows': rows, 'policy': policy}
    identity = {'profile': profile, 'source_hashes': sources, 'inputs_hash': fingerprint(packet),
                'previous_hash': fingerprint(previous), 'code': revision_code(), 'environment': environment(),
                'concurrency': 1, 'maximum_attempts_per_stage': 3, 'parent_evaluation': PREVIOUS if not smoke else None}
    manifest = {'id': run_id, 'mode': 'smoke' if smoke else 'benchmark', 'created_at': utc(),
                'profile': profile, 'identity': identity, 'identity_hash': fingerprint(identity),
                'source_run': None if smoke else 'formal-v1', 'source_evaluation': None if smoke else PREVIOUS,
                'gold_version': 'gold-v2', 'post_review_revision': True, 'evaluator_configured_after_generation': True,
                'researcher_source_review': 'PENDING', 'human_evaluator_validation': 'PENDING'}
    directory.mkdir(parents=True)
    for name in identity['code']['files']:
        p = directory/'code-snapshot'/name; p.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT/name, p)
    save(directory/'inputs.json', packet); save(directory/'previous-results.json', previous); save(directory/'manifest.json', manifest)
    summarize(directory)
    return {'id': run_id, 'status': 'PREPARED', 'answers': len(rows), 'stage_calls_expected': sum(1 if r['type'] == 'unanswerable' else 4 if r['condition'] == 'RAG' else 3 for r in rows)}


def verify(directory):
    m = read(directory/'manifest.json'); p = read(directory/'inputs.json'); previous = read(directory/'previous-results.json')
    i = m['identity']
    if fingerprint(i) != m['identity_hash'] or fingerprint(p) != i['inputs_hash'] or fingerprint(previous) != i['previous_hash']:
        raise EvaluationError('REVISION_IDENTITY_CHANGED')
    if revision_code() != i['code'] or environment() != i['environment']:
        raise EvaluationError('REVISION_CODE_OR_ENVIRONMENT_CHANGED')
    for name, digest in i['source_hashes'].items():
        if sha(ROOT/name) != digest: raise EvaluationError('ORIGINAL_SOURCE_CHANGED')
    for name, digest in i['code']['files'].items():
        if sha(directory/'code-snapshot'/name) != digest: raise EvaluationError('CODE_SNAPSHOT_CHANGED')
    return m, p, previous


async def execute(run_id, limit=None):
    directory = BASE/'runs'/valid_id(run_id)
    m, packet, previous = verify(directory)
    if not os.environ.get(m['profile']['api_key_env']): raise EvaluationError('API_KEY_NOT_CONFIGURED')
    transport = Transport(m['profile'])
    observed = {read(p)['provider']['returned_model'] for p in (directory/'calls').rglob('attempt-*.json') if read(p).get('provider', {}).get('returned_model')}
    if len(observed) > 1: raise EvaluationError('MIXED_RETURNED_MODELS')
    transport.expected_returned_model = next(iter(observed), None)
    evaluator = RevisedEvaluator(Journal(directory/'calls', transport, m['identity_hash']), packet['policy'])
    try:
        with run_lock(directory):
            done = {r['attempt_key'] for r in completed(directory, m)}
            remaining = [r for r in packet['rows'] if r['attempt_key'] not in done]
            if limit is not None: remaining = remaining[:limit]
            for row in remaining:
                start = time.perf_counter(); result = await evaluator.evaluate(row, previous[row['attempt_key']])
                result['evaluation_elapsed_seconds'] = time.perf_counter()-start
                save(directory/'results'/(row['attempt_key']+'.json'), {'identity_hash': m['identity_hash'],
                     'input_hash': fingerprint(row), 'at': utc(), 'result_hash': fingerprint(result), 'result': result})
                summary = summarize(directory)
                print(json.dumps({k: summary[k] for k in ('id', 'processed', 'expected', 'answers_with_evaluator_errors')}) , flush=True)
    finally:
        await transport.close()
    return summarize(directory)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('command', choices=['prepare', 'run', 'verify'])
    parser.add_argument('--id', required=True); parser.add_argument('--smoke', action='store_true'); parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    try:
        if args.command == 'prepare': out = prepare(args.id, args.smoke)
        elif args.command == 'verify':
            verify(BASE/'runs'/valid_id(args.id)); out = {'id': args.id, 'integrity': 'PASS'}
        else: out = asyncio.run(execute(args.id, args.limit))
        print(json.dumps(out, ensure_ascii=False, indent=2))
    except KeyboardInterrupt:
        print('{"status":"INTERRUPTED"}'); sys.exit(130)
    except Exception as e:
        print(json.dumps({'status': 'ERROR', **safe_error(e)})); sys.exit(1)


if __name__ == '__main__': main()
