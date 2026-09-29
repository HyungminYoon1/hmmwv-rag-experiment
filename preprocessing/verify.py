"""Verify extraction invariants and compare independently generated outputs."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

from preprocess import dump, compact, BASE, sha


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def verify(folder):
    summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    pages = {p['pdf_page']: p for p in read_jsonl(folder / 'pages.jsonl')}
    tables = read_jsonl(folder / 'pmcs_table_rows.jsonl')
    checks = []

    def check(name, condition, detail=''):
        checks.append({'check': name, 'passed': bool(condition), 'detail': detail})

    check('all_890_pages_have_unique_records', list(pages) == list(range(1, 891)))
    check('scope_is_pdf_31_through_863', [n for n, p in pages.items() if p['in_scope']] == list(range(31, 864)))
    check('chapter1_starts_at_printed_1_1', pages[31]['printed_page'] == '1-1')
    check('chapter2_starts_at_printed_2_1', pages[92]['printed_page'] == '2-1')
    check('chapter2_ends_at_printed_2_766', pages[863]['printed_page'] == '2-766')
    check('index_not_in_search_scope', not pages[864]['in_scope'])
    check('page570_is_blank', pages[570]['native_body_text'] == '' and pages[570]['image_count'] == 0)
    check('original_pdf_not_changed', summary['source_unchanged'])
    check('no_llm_or_run_network', not summary['llm_used'] and not summary['network_used_during_run'])
    check('no_claim_of_final_corpus', not summary['final_corpus_frozen']
          and all(p['included_in_final_corpus'] is None for p in pages.values()))
    check('manifest_file_hashes', all(sha(folder / name) == digest for name, digest in manifest['files'].items()))
    check('no_data_file_uses_utf8_bom', all(not (folder / name).read_bytes().startswith(b'\xef\xbb\xbf')
          for name in manifest['files'] if name.endswith(('.json', '.jsonl', '.html'))))
    check('no_bare_lf_in_text_outputs', all(b'\n' not in (folder / name).read_bytes().replace(b'\r\n', b'')
          for name in manifest['files'] if name.endswith(('.json', '.jsonl', '.html'))))
    pmcs = [r for r in tables if r['pdf_page'] == 100 and r['item'] == '7'][0]
    procedure = compact(pmcs['fields']['PROCEDURES'])
    unserviceable = compact(pmcs['fields']['NOT FULLY MISSION CAPABLE IF'])
    check('p100_cdr_prohibition_is_preserved', 'donotcleancdrvalvewithsolvent' in procedure)
    check('p100_cdr_failure_condition_in_correct_column', 'cdrfailswatermanometervacuumtest' in unserviceable)
    check('p100_failure_not_mixed_into_procedure', 'cdrfailswatermanometervacuumtest' not in procedure)
    check('p117_distinct_items_preserved', [r['item'] for r in tables if r['pdf_page'] == 117] == ['30', '30.1', '30.2', '31'])
    for n in [97, 103, 111]:
        selected = [r for r in tables if r['pdf_page'] == n]
        check(f'p{n}_scanned_table_extracted_with_ocr', bool(selected) and all(r['method'] == 'tesseract_column_crop' for r in selected))
        check(f'p{n}_ocr_is_not_silently_verified', all(r['review_status'] == 'OCR_UNREVIEWED' for r in selected))
    tires = [r for r in tables if r['pdf_page'] == 111][0]
    check('p111_visible_torque_digits_survive_ocr', '90110' in compact(tires['fields']['PROCEDURES'])
          and '122149' in compact(tires['fields']['PROCEDURES']))
    check('p111_masked_diagram_captions_not_merged_into_procedure',
          not any(line.strip() in ('ROTATION DIAGRAM', 'TIGHTENING SEQUENCE')
                  for line in tires['fields']['PROCEDURES'].splitlines()))
    for n in [180, 500, 610]:
        check(f'p{n}_image_information_flagged', 'IMAGE_CONTENT_NOT_SEMANTICALLY_RECONSTRUCTED' in pages[n]['review_flags'])
    candidate = read_jsonl(folder / 'candidate_anchor_audit.jsonl')
    check('all_60_candidate_ids_accounted_for', len({r['question_id'] for r in candidate}) == 60)
    check('anchor_match_not_presented_as_semantic_validation', all(r['semantic_coverage'] == 'NOT_VERIFIED' for r in candidate))
    return {'all_passed': all(c['passed'] for c in checks), 'checks': checks,
            'checks_total': len(checks), 'checks_passed': sum(c['passed'] for c in checks)}


def compare(first, second):
    a = {p.relative_to(first).as_posix(): sha(p) for p in first.rglob('*') if p.is_file()}
    b = {p.relative_to(second).as_posix(): sha(p) for p in second.rglob('*') if p.is_file()}
    keys = sorted(set(a) | set(b))
    results = [{'file': k, 'sha256_a': a.get(k), 'sha256_b': b.get(k),
                'identical': a.get(k) is not None and a.get(k) == b.get(k)} for k in keys]
    return {'all_identical': all(r['identical'] for r in results), 'files_compared': len(results),
            'files_identical': sum(r['identical'] for r in results),
            'method': 'SHA-256 byte comparison of every output file; independent fresh runs must be performed by the caller.',
            'files': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('first', type=Path)
    parser.add_argument('second', type=Path, nargs='?')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = {'first_run': verify(args.first)}
    if args.second:
        result['second_run'] = verify(args.second)
        result['reproducibility'] = compare(args.first, args.second)
    dump(args.report, result)
    ok = all(value.get('all_passed', value.get('all_identical', False)) for value in result.values())
    print(json.dumps({k: {a: b for a, b in v.items() if a not in ('checks', 'files')} for k, v in result.items()}, ensure_ascii=False))
    sys.exit(0 if ok else 1)
