"""Versioned gold-v3 recalculation from saved judgments, without model calls."""
import argparse
import copy
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import sys

from .evaluation.common import ROOT, read, save, sha, fingerprint, utc
from .evaluation.report import completed, summarize
from .correction_statistics import retrieval, quality

SOURCE_ID = 'sol-revision-formal-20260929-v3'
RUN_ID = 'gold-v3-formal-20260929'
SOURCE = ROOT / 'experiment/evaluation/runs' / SOURCE_ID
GOLD = ROOT / 'experiment/gold-v3'
SHIPPED = ROOT / 'experiment/evaluation/runs' / RUN_ID


def check_gold(old, new):
    if len(old) != 60 or len(new) != 60:
        raise ValueError('Expected 60 questions')
    if Counter(q['type'] for q in new) != {'single-evidence': 20, 'multi-evidence': 30, 'unanswerable': 10}:
        raise ValueError('Question types changed')
    additions = {('S15', 'white'): ['C001838'], ('S17', 'black'): ['C001993'], ('M05', 'black'): ['C001993']}
    for a, b in zip(old, new):
        for key in ('id', 'question', 'type', 'oracle_evidence', 'missing_information', 'allowed_partial_answer'):
            if a[key] != b[key]:
                raise ValueError('Unapproved question or oracle change: ' + b['id'])
        expected = [e for e in a['required_elements'] if not (a['id'] == 'S16' and e['id'] == 'S16-A02')]
        if expected != b['required_elements'] or len(a['evidence']) != len(b['evidence']):
            raise ValueError('Unapproved rubric change: ' + b['id'])
        for g1, g2 in zip(a['evidence'], b['evidence']):
            if g1['id'] != g2['id']:
                raise ValueError('Evidence group changed')
            sets = copy.deepcopy(g1['sufficient_chunk_sets'])
            if b['id'] in ('S16', 'M06') and g2['id'] == 'blue':
                sets = [['C002436'], ['C001647', 'C001648']]
            if (b['id'], g2['id']) in additions:
                sets.append(additions[(b['id'], g2['id'])])
            if b['id'] == 'M24' and 'C000926' in g1['primary_chunks']:
                sets.append(['C005773'])
            if sets != g2['sufficient_chunk_sets']:
                raise ValueError('Unapproved evidence combination: ' + b['id'])
    notes = {q['id']: q['review_note'] for q in new}
    if 'They remain required in S16-A02.' in notes['M06'] or 'routes are also optional in S16' not in notes['M06']:
        raise ValueError('Obsolete required-element note')


def corrected_result(original):
    result = copy.deepcopy(original)
    if result['question_id'] == 'S16':
        old = result['stages']['coverage']['elements']
        keep = [e for e in old if e['id'] != 'S16-A02']
        if len(old) != 2 or len(keep) != 1 or keep[0]['fulfilled'] != 1:
            raise ValueError('Unexpected S16 cached judgments')
        result['stages']['coverage']['elements'] = keep
        result['metrics']['required_coverage'] = {'value': 1.0, 'status': 'OK_DECLARED_RUBRIC_FILTER'}
    return result


def load_sources():
    old = read(ROOT / 'experiment/gold-v2/questions.json')
    new = read(GOLD / 'questions.json')
    check_gold(old, new)
    gm = read(GOLD / 'manifest.json')
    for name, digest in gm['files'].items():
        if sha(GOLD / name) != digest:
            raise ValueError('Gold-v3 file changed: ' + name)
    manifest = read(SOURCE / 'manifest.json')
    original = completed(SOURCE, manifest)
    packet = read(SOURCE / 'inputs.json')
    if len(original) != 120 or len(packet['rows']) != 120:
        raise ValueError('Expected 120 cached answers')
    by_key = {r['attempt_key']: r for r in packet['rows']}
    for r in original:
        if r['errors'] or r['attempt_key'] not in by_key:
            raise ValueError('Incomplete source evaluation')
    return old, new, packet, original, manifest


def analysis(old, new, packet, before, after):
    rows = {r['attempt_key']: r for r in packet['rows']}
    first, last = retrieval(old, rows), retrieval(new, rows)
    narrow = copy.deepcopy(new)
    for q in narrow:
        if q['id'] in ('S15', 'S17'):
            for g in q['evidence']:
                g['sufficient_chunk_sets'] = [s for s in g['sufficient_chunk_sets'] if s not in (['C001838'], ['C001993'])]
    broad = copy.deepcopy(new)
    next(g for q in broad if q['id'] == 'M01' for g in q['evidence'] if g['id'] == 'crank_voltage')['sufficient_chunk_sets'].extend([['C003397'], ['C003398']])
    sensitivity = {'direct_statement_only': retrieval(narrow, rows),
                   'allow_M01_unspecified_measurement_point': retrieval(broad, rows)}
    for excluded in (['M11'], ['M01', 'M11']):
        s = retrieval(new, rows, excluded)
        sensitivity['exclude_' + '_'.join(excluded)] = {'retrieval': s, 'quality': quality(after, s, excluded)}
    return {'source_run': SOURCE_ID, 'run_id': RUN_ID, 'new_api_calls': 0,
            'retrieval_before': first, 'retrieval_after': last,
            'quality_before': quality(before, first), 'quality_after': quality(after, last),
            'sensitivity': sensitivity,
            'retrieval_changes': [{'id': a['id'], 'before': a, 'after': b} for a, b in zip(first['details'], last['details']) if a != b]}


def build(output):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Output exists; choose a new directory')
    if not output.is_relative_to(ROOT):
        raise ValueError('Output must be inside the checkout')
    old, new, parent_packet, before, parent_manifest = load_sources()
    questions = {q['id']: q for q in new}
    packet = copy.deepcopy(parent_packet)
    packet['policy'] = read(GOLD / 'evaluation-policy.json')
    for row in packet['rows']:
        q = questions[row['question_id']]
        if q['question'] != row['user_input']:
            raise ValueError('Question text differs')
        row.update(required_elements=q['required_elements'], predeclared_note=q['review_note'],
                   oracle_evidence=q['oracle_evidence'], evaluation_status='GOLD_V3_CACHED_RECALCULATION')
    after = [corrected_result(r) for r in before]
    files = [SOURCE / 'manifest.json', SOURCE / 'inputs.json', ROOT / 'experiment/gold-v2/questions.json', GOLD / 'manifest.json']
    files += list((SOURCE / 'results').glob('*.json')) + [GOLD / n for n in read(GOLD / 'manifest.json')['files']]
    source_hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(set(files))}
    code_hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in (Path(__file__), Path(__file__).with_name('correction_statistics.py'))}
    identity = {'source_hashes': source_hashes, 'code_hashes': code_hashes,
                'inputs_hash': fingerprint(packet), 'operation': 'REMOVE_S16_A02_AND_RECALCULATE_RETRIEVAL', 'new_api_calls': 0}
    now = utc()
    manifest = {'id': RUN_ID, 'mode': 'benchmark', 'created_at': now, 'profile': parent_manifest['profile'],
                'identity': identity, 'identity_hash': fingerprint(identity), 'source_run': 'formal-v1',
                'source_evaluation': SOURCE_ID, 'gold_version': 'gold-v3', 'derivation': 'CACHED_JUDGMENTS',
                'new_api_calls': 0, 'researcher_source_review': 'PENDING', 'human_evaluator_validation': 'PENDING'}
    output.mkdir(parents=True)
    save(output / 'manifest.json', manifest)
    save(output / 'inputs.json', packet)
    keyed = {r['attempt_key']: r for r in packet['rows']}
    for r in after:
        original = SOURCE / 'results' / (r['attempt_key'] + '.json')
        save(output / 'results' / original.name, {'identity_hash': manifest['identity_hash'],
             'input_hash': fingerprint(keyed[r['attempt_key']]), 'at': now, 'result_hash': fingerprint(r),
             'result': r, 'source_file': original.relative_to(ROOT).as_posix(), 'source_sha256': sha(original), 'new_api_calls': 0})
    details = analysis(old, new, parent_packet, before, after)
    save(output / 'analysis.json', details)
    summary = summarize(output)
    summary.update(gold_version='gold-v3', derivation='CACHED_JUDGMENTS', new_api_calls=0,
                   source_evaluation=SOURCE_ID, retrieval=details['retrieval_after']['summary'])
    save(output / 'summary.json', summary)
    report = (output / 'report.md').read_text(encoding='utf-8')
    report += '\n## 원문 대조에 따른 정정\n\n이 기록은 gold-v3와 기존 Sol 판정을 사용한 재집계다. 새 API 호출은 0회다. S16에서 질문에 없는 유입 경로 요소만 제외했고, 나머지 판정은 보존했다. 검색 근거 Recall@5는 78.0%, 전체 근거 확보는 31/50이다. 좁은 동등 근거 기준에서는 74.0%·29/50이다.\n\n판정 원본과 API 호출 이력은 `../' + SOURCE_ID + '/`에 있고, 이 기록의 results/는 파생 결과다. 상세 검색·민감도 결과는 analysis.json을 따른다.\n'
    report = report.replace('원본 평가 응답과 재시도 이력은 calls/에 보관한다.', '원본 평가 응답과 재시도 이력은 위 부모 평가 기록에 보관한다.')
    from .evaluation.common import write_text
    write_text(output / 'report.md', report)
    return verify(output)


def verify(directory=SHIPPED, source_images=False):
    directory = Path(directory)
    old, new, parent_packet, before, _ = load_sources()
    manifest, packet = read(directory / 'manifest.json'), read(directory / 'inputs.json')
    ident = manifest['identity']
    if fingerprint(ident) != manifest['identity_hash'] or fingerprint(packet) != ident['inputs_hash']:
        raise ValueError('Derived identity differs')
    for name, digest in {**ident['source_hashes'], **ident['code_hashes']}.items():
        if sha(ROOT / name) != digest:
            raise ValueError('Source/code hash differs: ' + name)
    after = completed(directory, manifest)
    a = {r['attempt_key']: r for r in before}
    if len(after) != 120:
        raise ValueError('Missing derived answers')
    rows = {r['attempt_key']: r for r in parent_packet['rows']}
    for r in after:
        expected = corrected_result(a[r['attempt_key']])
        if r != expected:
            raise ValueError('Undeclared result change')
        record = read(directory / 'results' / (r['attempt_key'] + '.json'))
        row = next(x for x in packet['rows'] if x['attempt_key'] == r['attempt_key'])
        q = next(x for x in new if x['id'] == row['question_id'])
        expected_row = copy.deepcopy(rows[r['attempt_key']])
        expected_row.update(required_elements=q['required_elements'], predeclared_note=q['review_note'],
                            oracle_evidence=q['oracle_evidence'], evaluation_status='GOLD_V3_CACHED_RECALCULATION')
        if row != expected_row or record['input_hash'] != fingerprint(row):
            raise ValueError('Undeclared evaluation input change')
        if record['new_api_calls'] != 0 or record['source_sha256'] != sha(ROOT / record['source_file']):
            raise ValueError('Cached result source differs')
    actual = read(directory / 'analysis.json')
    if analysis(old, new, parent_packet, before, after) != actual:
        raise ValueError('Analysis differs from recalculation')
    # Separate Decimal/set implementation checks the principal aggregates.
    scores = []
    for q in new:
        if q['type'] == 'unanswerable':
            continue
        ids = frozenset(rows['r1-' + q['id'] + '-rag']['retrieved_chunk_ids'])
        hit = sum(any(not (set(c) - ids) for c in g['sufficient_chunk_sets']) for g in q['evidence'])
        scores.append(Decimal(hit) / Decimal(len(q['evidence'])))
    if sum(scores) / Decimal(50) != Decimal('0.78') or sum(v == 1 for v in scores) != 31:
        raise ValueError('Independent retrieval check failed')
    summary = read(directory / 'summary.json')
    for agg in summary['aggregate']:
        subset = [r for r in after if r['condition'] == agg['condition'] and (agg['type'] == 'all' or r['type'] == agg['type'])]
        values = [Decimal(str(r['metrics'][agg['metric']]['value'])) for r in subset if r['metrics'][agg['metric']]['value'] is not None]
        average = float(sum(values) / Decimal(len(values))) if values else None
        if agg['valid_n'] != len(values) or agg['processed_n'] != len(subset) or ((average is None) != (agg['mean'] is None)):
            raise ValueError('Aggregate denominator differs')
        if average is not None and abs(average - agg['mean']) > 1e-12:
            raise ValueError('Independent metric mean differs')
    for pair in summary['paired']:
        selected = [r for r in after if r['type'] != 'unanswerable' and (pair['type'] == 'all' or pair['type'] == r['type'])]
        groups = {c: {r['question_id']: r['metrics'][pair['metric']]['value'] for r in selected if r['condition'] == c and r['metrics'][pair['metric']]['value'] is not None} for c in ('LLM_ONLY', 'RAG')}
        ids = sorted(set(groups['LLM_ONLY']) & set(groups['RAG']))
        mean = float(sum(Decimal(str(groups['RAG'][i])) - Decimal(str(groups['LLM_ONLY'][i])) for i in ids) / Decimal(len(ids))) if ids else None
        if pair['question_ids'] != ids or pair['paired_n'] != len(ids) or (mean is not None and abs(mean - pair['mean_rag_minus_llm_only']) > 1e-12):
            raise ValueError('Independent paired comparison differs')
    if summary['provider_response_count'] != 0 or manifest['new_api_calls'] != 0 or any((directory / 'calls').rglob('*')):
        raise ValueError('Unexpected provider activity')
    for condition in ('LLM_ONLY', 'RAG'):
        subset = [r for r in after if r['condition'] == condition and r['type'] != 'unanswerable']
        values = [Decimal(sum(e['fulfilled'] for e in r['stages']['coverage']['elements'])) / Decimal(len(r['stages']['coverage']['elements'])) for r in subset]
        expected = sum(values) / Decimal(50)
        aggregate = next(x for x in summary['aggregate'] if x['condition'] == condition and x['type'] == 'all' and x['metric'] == 'required_coverage')
        if abs(float(expected) - aggregate['mean']) > 1e-12:
            raise ValueError('Independent coverage check failed')
    image_count = 0
    if source_images:
        import pymupdf
        captures = read(GOLD / 'source-captures.json')
        pdf = ROOT / '제출 논문 초안/논문참고자료/TM_9-2320-280-20-1_1996_Change2_2004_TFS_archive.pdf'
        if sha(pdf) != captures['source_pdf_sha256']:
            raise ValueError('Original PDF differs')
        with pymupdf.open(pdf) as document:
            for c in captures['pages']:
                path = ROOT / c['path']
                if sha(path) != c['sha256']:
                    raise ValueError('Source capture hash differs')
                image = pymupdf.Pixmap(str(path))
                rendered = document[c['page'] - 1].get_pixmap(dpi=c['dpi'], alpha=False)
                if (image.width, image.height, image.samples) != (rendered.width, rendered.height, rendered.samples):
                    raise ValueError('Source image pixels differ')
                image_count += 1
    return {'status': 'PASS', 'answers': 120, 'questions_unchanged': 60,
            'retrieval': {'recall': 0.78, 'complete': 31, 'n': 50}, 'source_images_checked': image_count,
            'new_api_calls': 0, 'human_validation': 'NOT_PERFORMED'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['recalculate', 'verify'])
    parser.add_argument('--output', type=Path, default=ROOT / 'validation/local/gold-v3-recalculation')
    parser.add_argument('--source-images', action='store_true')
    args = parser.parse_args()
    result = build(args.output) if args.command == 'recalculate' else verify(source_images=args.source_images)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
