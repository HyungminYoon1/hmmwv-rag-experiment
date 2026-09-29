"""Validate extraction coverage, preservation of earlier data and replay files."""
import argparse
import json
from pathlib import Path
import re

import preprocess as base
from parse_full_manual import read_jsonl, invalid_native_mapping


def inspect(folder):
    pages = read_jsonl(folder / 'pages.jsonl')
    coverage = read_jsonl(folder / 'page_coverage.jsonl')
    raw = read_jsonl(folder / 'raw_native_pages.jsonl')
    ocr = read_jsonl(folder / 'ocr-snapshot/pages.jsonl')
    old_raw = read_jsonl(base.BASE / 'output/run-a/raw_native_pages.jsonl')
    old_ocr = read_jsonl(base.BASE / 'assets/ocr-snapshot/pages.jsonl')
    old_tables = read_jsonl(base.BASE / 'output/run-a/pmcs_table_rows.jsonl')
    summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    by_page = {p['pdf_page']: p for p in pages}
    by_ocr = {p['pdf_page']: p for p in ocr}
    checks = []

    def check(name, condition):
        checks.append({'check': name, 'passed': bool(condition)})

    check('all_890_pages_once_in_source_order', [p['pdf_page'] for p in pages] == list(range(1, 891)))
    check('coverage_records_for_all_890_pages', [p['pdf_page'] for p in coverage] == list(range(1, 891)))
    check('native_records_for_all_890_pages', [p['pdf_page'] for p in raw] == list(range(1, 891)))
    check('research_scope_stays_chapter1_and2', [p['pdf_page'] for p in pages if p['in_scope']] == list(range(31, 864)))
    check('scope_count_is_833', summary['scope_pages'] == 833)
    check('outside_scope_count_is_57', summary['outside_scope_pages'] == 57)
    check('all_raster_image_pages_have_ocr', all(p['pdf_page'] in by_ocr for p in pages if p['image_count']))
    check('sparse_vector_pages_have_ocr', all(p['pdf_page'] in by_ocr for p in pages if p['vector_drawing_count'] and len(p['native_body_text']) < 350))
    check('invalid_native_mapping_pages_have_ocr', all(p['pdf_page'] in by_ocr for p in raw if invalid_native_mapping(p['lines'])))
    check('ocr_page_ids_are_unique', len(by_ocr) == len(ocr))
    check('all_old_501_ocr_records_preserved', len(old_ocr) == 501 and all(by_ocr.get(r['pdf_page']) == r for r in old_ocr))
    check('all_old_native_lines_words_and_coordinates_preserved', len(raw) == len(old_raw) and all(
        all(new.get(k) == value for k, value in old.items()) for new, old in zip(raw, old_raw)))
    check('pmcs_rows_preserved', read_jsonl(folder / 'pmcs_table_rows.jsonl') == old_tables)
    check('p570_remains_a_blank_not_ocr_failure', 'BLANK_PAGE' in by_page[570]['review_flags'] and 570 not in by_ocr)
    check('p810_original_printed_typo_preserved', by_page[810]['printed_page'] == '3-710')
    check('full_text_export_has_all_890_page_headers', re.findall(r'^PDF PAGE (\d+)',
        (folder / '교범_전체_추출텍스트.txt').read_text(encoding='utf-8'), re.M) == [f'{n:03d}' for n in range(1, 891)])
    check('scope_text_export_has_all_833_page_headers', re.findall(r'^PDF PAGE (\d+)',
        (folder / '실험범위_본문과표_검토본.txt').read_text(encoding='utf-8'), re.M) == [f'{n:03d}' for n in range(31, 864)])
    check('ocr_and_native_not_silently_fused', all('native_body_text' in p and 'ocr_body_text' in p for p in pages))
    check('no_claim_that_review_data_is_frozen', not summary['corpus_frozen'] and not summary['chunking_performed']
          and all(p['included_in_final_corpus'] is None for p in pages))
    check('no_runtime_llm_or_network_claim', not summary['llm_used_for_parsing_or_correction'] and not summary['network_used_during_run'])
    check('question_independent_selection', summary['evaluation_questions_read'] is False)
    check('no_undocumented_content_corrections', summary['automatic_content_corrections'] == 0)
    config = json.loads((base.BASE / 'config.json').read_text(encoding='utf-8'))
    check('original_pdf_unchanged', base.sha((base.BASE / config['input']).resolve()) == config['input_sha256'])
    check('output_file_hashes_match_manifest', all(base.sha(folder / name) == digest for name, digest in manifest['files'].items()))
    check('current_parser_matches_executed_code', base.sha(base.BASE / 'parse_full_manual.py') == manifest['program_sha256'])
    text_files = [p for p in folder.rglob('*') if p.is_file() and p.suffix in ('.json', '.jsonl', '.txt', '.html')]
    check('utf8_without_bom', all(not p.read_bytes().startswith(b'\xef\xbb\xbf') for p in text_files))
    check('crlf_text_line_endings', all(b'\n' not in p.read_bytes().replace(b'\r\n', b'') for p in text_files))
    return {'checks': checks, 'passed': sum(c['passed'] for c in checks),
            'total': len(checks), 'all_passed': all(c['passed'] for c in checks)}


def compare(first, second):
    def inventory(folder):
        return {p.relative_to(folder).as_posix(): base.sha(p) for p in folder.rglob('*') if p.is_file()}
    a, b = inventory(first), inventory(second)
    files = [{'file': name, 'sha256_a': a.get(name), 'sha256_b': b.get(name),
              'identical': name in a and name in b and a[name] == b[name]} for name in sorted(set(a) | set(b))]
    return {'all_identical': all(r['identical'] for r in files),
            'identical': sum(r['identical'] for r in files), 'compared': len(files), 'files': files}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('first', type=Path)
    cli.add_argument('second', type=Path, nargs='?')
    cli.add_argument('--report', type=Path, required=True)
    args = cli.parse_args()
    result = {'first': inspect(args.first)}
    if args.second:
        result['second'] = inspect(args.second)
        result['reproducibility'] = compare(args.first, args.second)
    base.dump(args.report, result)
    print(json.dumps({key: {k: v for k, v in item.items() if k not in ('checks', 'files')}
                      for key, item in result.items()}))
    raise SystemExit(0 if all(item['all_passed'] for key, item in result.items() if key != 'reproducibility')
                     and result.get('reproducibility', {}).get('all_identical', True) else 1)
