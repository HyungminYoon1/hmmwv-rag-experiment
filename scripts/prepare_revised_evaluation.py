"""Apply the selected versioned rubric to a new generation/evaluation run.

Preparation only: no model, embedding or paid API request is made here.
The existing revision evaluator executes the resulting immutable packet.
"""
import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiment.evaluation.common import BASE, EXPERIMENT, read, save, sha, fingerprint, utc, valid_id, EvaluationError
from experiment.evaluation.inputs import source_packet, environment
from experiment.evaluation.runner import profile_named
from experiment.evaluation.revision_runner import revision_code
from experiment.evaluation.report import summarize


def prepare(run_id, parent_id, gold_version='gold-v3'):
    if gold_version not in ('gold-v2', 'gold-v3'):
        raise EvaluationError('UNKNOWN_GOLD_VERSION')
    destination = BASE / 'runs' / valid_id(run_id)
    if destination.exists():
        raise EvaluationError('RUN_ALREADY_EXISTS')
    parent = BASE / 'runs' / valid_id(parent_id)
    pm = read(parent / 'manifest.json')
    summary = read(parent / 'summary.json')
    if pm['mode'] != 'benchmark' or summary['status'] != 'COMPLETED':
        raise EvaluationError('COMPLETE_BASELINE_REQUIRED')
    source_run = valid_id(pm['source_run'])
    rows, _, sources = source_packet(source_run)
    old_rows = {r['attempt_key']: r for r in read(parent / 'inputs.json')['rows']}
    if len(old_rows) != 120:
        raise EvaluationError('EXPECTED_120_PARENT_ANSWERS')
    gold_dir = EXPERIMENT / gold_version
    gm = read(gold_dir / 'manifest.json')
    for name, digest in gm['files'].items():
        if sha(gold_dir / name) != digest:
            raise EvaluationError('GOLD_CHANGED')
        sources[(gold_dir / name).relative_to(ROOT).as_posix()] = digest
    for path in (gold_dir / 'manifest.json', parent / 'manifest.json', parent / 'inputs.json', parent / 'summary.json', Path(__file__)):
        sources[path.relative_to(ROOT).as_posix()] = sha(path)
    gold = {q['id']: q for q in read(gold_dir / 'questions.json')}
    previous = {}
    for row in rows:
        old = old_rows[row['attempt_key']]
        for field in ('user_input', 'response', 'raw_response', 'retrieved_contexts', 'retrieved_chunk_ids', 'type', 'condition'):
            if row[field] != old[field]:
                raise EvaluationError('PARENT_ANSWERS_DIFFER')
        q = gold[row['question_id']]
        if q['question'] != row['user_input']:
            raise EvaluationError('QUESTION_CHANGED')
        row.update(oracle_evidence=q['oracle_evidence'], required_elements=q['required_elements'],
                   allowed_partial_answer=q['allowed_partial_answer'], predeclared_note=q['review_note'],
                   evaluation_status='REPLICATION_WITH_' + gold_version.upper().replace('-', '_'), rubric_timing='AFTER_ORIGINAL_STUDY_RESULTS')
        path = parent / 'results' / (row['attempt_key'] + '.json')
        record = read(path)
        if record['result_hash'] != fingerprint(record['result']) or record['identity_hash'] != pm['identity_hash']:
            raise EvaluationError('PARENT_RESULT_INTEGRITY_MISMATCH')
        sources[path.relative_to(ROOT).as_posix()] = sha(path)
        previous[row['attempt_key']] = record['result']
    profile = profile_named('openai-sol')
    if pm['profile'] != profile:
        raise EvaluationError('PARENT_JUDGE_PROFILE_DIFFERS')
    packet = {'rows': rows, 'policy': read(gold_dir / 'evaluation-policy.json')}
    identity = {'profile': profile, 'source_hashes': sources, 'inputs_hash': fingerprint(packet),
                'previous_hash': fingerprint(previous), 'code': revision_code(), 'environment': environment(),
                'concurrency': 1, 'maximum_attempts_per_stage': 3, 'parent_evaluation': parent_id,
                'preparation_tool': {'path': Path(__file__).relative_to(ROOT).as_posix(), 'sha256': sha(__file__)}}
    manifest = {'id': run_id, 'mode': 'benchmark', 'created_at': utc(), 'profile': profile,
                'identity': identity, 'identity_hash': fingerprint(identity), 'source_run': source_run,
                'source_evaluation': parent_id, 'gold_version': gold_version, 'post_review_revision': True,
                'evaluator_configured_after_generation': True, 'researcher_source_review': 'PENDING',
                'human_evaluator_validation': 'PENDING', 'replication_preparation': True}
    destination.mkdir(parents=True)
    for name in identity['code']['files']:
        target = destination / 'code-snapshot' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    helper_copy = destination / 'preparation-tool' / Path(__file__).name
    helper_copy.parent.mkdir()
    shutil.copy2(__file__, helper_copy)
    save(destination / 'inputs.json', packet)
    save(destination / 'previous-results.json', previous)
    save(destination / 'manifest.json', manifest)
    summarize(destination)
    print('PREPARED', run_id, 'SOURCE_GENERATION', source_run, 'PARENT_EVALUATION', parent_id, 'API_CALLS', 0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--id', required=True)
    parser.add_argument('--source-evaluation', required=True)
    parser.add_argument('--gold-version', choices=['gold-v2', 'gold-v3'], default='gold-v3')
    args = parser.parse_args()
    prepare(args.id, args.source_evaluation, args.gold_version)
