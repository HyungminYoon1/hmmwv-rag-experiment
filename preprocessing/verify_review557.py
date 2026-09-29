"""Audit frozen 557 decisions, source references, replay, and v3-to-v4 changes."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import zipfile

import pymupdf
import correct_extraction as io
from verify_corrections import audit_changes


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def file_map(folder):
    return {p.relative_to(folder).as_posix(): io.sha(p)
            for p in sorted(folder.rglob('*')) if p.is_file()}


def valid_span(span, records):
    rid = span.get('record_id')
    if rid not in records:
        return False
    start, end = span.get('start'), span.get('end')
    text = records[rid]['text']
    return (type(start) is int and type(end) is int
            and 0 <= start <= end <= len(text) and text[start:end] == span['text'])


MIXED = {'OCR_CROSS_REGION_MERGE', 'TABLE_COLUMN_MERGE',
         'TABLE_ROW_ALIGNMENT', 'FLOWCHART_BRANCH'}


def valid_rule(rule, records):
    return (valid_span(rule['native_span'], records)
            and valid_span(rule['ocr_span'], records)
            and all(valid_span(s, records) for s in rule.get('native_adjacent_spans', []))
            and rule['ocr_allowed_as_single_prose_span'] == (rule['category'] not in MIXED)
            and rule['preferred_layer_for_aligned_span'] == (
                'ocr' if rule['category'] == 'IMAGE_TEXT_WITH_NATIVE_REFERENCE' else 'native')
            and rule['scope'] == 'THIS_ALIGNED_REGION_ONLY_NOT_THE_ENTIRE_PAGE'
            and rule['deduplicate_alternative_layers'] is True)


def valid_fragment(issue, records):
    return (issue['added_completion'] is False
            and issue['external_edition_substituted'] is False
            and len(issue['affected_spans']) == 3
            and all(valid_span(s, records) and s['text'] == 'Metal particles are'
                    and s['allow_as_sufficient_answer_evidence'] is False
                    for s in issue['affected_spans'])
            and issue['right_column_native_text'] == 'Metal particles are'
            and issue['source_text_preserved'] == 'Change fluid every 12,000 miles')


def main():
    review = io.BASE / 'review-557'
    structures = review / 'verified-v4-a'
    ledger_path = io.BASE / 'corrections/batch-004/correction-log.json'
    ledger = read(ledger_path)
    checks = {}

    def check(name, result):
        checks[name] = bool(result)

    backup = io.BASE / 'backups/v3-before-review557-20260922-194016'
    backup_meta = read(backup / 'backup-verification.json')
    archive = backup / 'corrected-v3-and-evidence.zip'
    check('backup_zip_hash', io.sha(archive) == backup_meta['backup_zip_sha256'])
    with zipfile.ZipFile(archive) as z:
        content = {n: hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}
    check('all_253_backup_files', content == backup_meta['files'] and len(content) == 253)
    prefixes = ('preprocessing/output/corrected-v3-a/',
                'preprocessing/corrections/batch-003/',
                'preprocessing/review-v2/verified-v3-a/')
    for name, digest in backup_meta['files'].items():
        if name.startswith(prefixes):
            check('prior_version_preserved:' + name, io.sha(io.ROOT / name) == digest)
    for name, info in ledger['inputs'].items():
        check('immutable_input:' + name, io.sha(io.ROOT / info['path']) == info['sha256'])

    folders = [io.BASE / 'output/full-manual-v2-a',
               io.BASE / 'output/corrected-v4-a', io.BASE / 'output/corrected-v4-b',
               structures, review / 'verified-v4-b']
    for folder in folders:
        manifest = read(folder / 'manifest.json')['files']
        actual = file_map(folder)
        check('manifest_exact:' + folder.name,
              {n: h for n, h in actual.items() if n != 'manifest.json'} == manifest)
    correction_files = file_map(folders[1])
    structure_files = file_map(structures)
    check('correction_replay_all_files', correction_files == file_map(folders[2]))
    check('structure_replay_all_files', structure_files == file_map(folders[4]))

    freeze = read(review / 'freeze.json')
    for label, path in [('ledger', ledger_path), ('decision_file', review / 'decisions.jsonl'),
                        ('decision_program', io.BASE / 'review557_decisions.py'),
                        ('builder', io.BASE / 'build_review557_batch.py')]:
        check('frozen_' + label, io.sha(path) == freeze[label + '_sha256'])
    candidates = io.load_records(review / 'candidates.jsonl')
    decisions = io.load_records(review / 'decisions.jsonl')
    ids = [c['id'] for c in candidates]

    def full_coverage(rows):
        return len(rows) == len(ids) == 557 and [d['id'] for d in rows] == ids

    check('all_557_dispositions', full_coverage(decisions))
    check('all_557_source_checks_recorded', all(
        d['status'] == 'SOURCE_REVIEWED' and d['reason']
        and d['source_check'] == 'CODEX_PDF_VISUAL_CHECK'
        and d['human_review'] == 'NOT_PERFORMED' for d in decisions))
    with pymupdf.open(io.ROOT / ledger['inputs']['pdf']['path']) as pdf:
        for candidate, decision in zip(candidates, decisions):
            check('frozen_candidate:' + candidate['id'],
                  candidate['status'] == 'UNRESOLVED_LAYER_DISAGREEMENT_NOT_AUTO_REPLACED'
                  and candidate['correction_ids'] == []
                  and all(decision[k] == v for k, v in candidate.items()
                          if k not in ('status', 'correction_ids')))
            pix = pdf[candidate['pdf_page'] - 1].get_pixmap(
                dpi=180, alpha=False, clip=pymupdf.Rect(candidate['render_clip']))
            digest = hashlib.sha256(pix.tobytes('png')).hexdigest()
            check('source_crop:' + candidate['id'], digest == candidate['crop_sha256']
                  == io.sha(review / candidate['source_crop']))

    parent = read(io.BASE / 'corrections/batch-003/correction-log.json')['corrections']
    check('prior_110_patches_unchanged', ledger['corrections'][:110] == parent)
    extra = ledger['corrections'][110:]
    linked = {d['id']: d['correction_ids'] for d in decisions}
    check('exactly_269_additional_patches', len(extra) == 269)
    check('patch_link_coverage', sorted(p['id'] for p in extra)
          == sorted(p for values in linked.values() for p in values))
    check('patch_candidate_identity', all(p['id'] in linked[p['candidate_id']] for p in extra))
    for suffix in ('a', 'b'):
        audit = read(io.BASE / f'audit/corrections-v4-{suffix}.json')
        check('core_audit:' + suffix, audit['status'] == 'PASS' and not audit['errors']
              and all(audit['checks'].values()) and audit['recorded_corrections'] == 379
              and audit['verifier_sha256'] == io.sha(io.BASE / 'verify_corrections.py')
              and audit['ledger_sha256'] == io.sha(ledger_path))

    corrected = io.load_records(folders[1] / 'units-corrected.jsonl')
    records = {r['id']: r for r in corrected}
    old = io.load_records(io.BASE / 'output/corrected-v3-a/units-corrected.jsonl')
    delta = copy.deepcopy(extra)
    for patch in delta:
        offset = sum(len(p['after']) - len(p['before']) for p in parent
                     if p['record_id'] == patch['record_id'] and p['end'] <= patch['start'])
        patch['start'] += offset
        patch['end'] += offset
    errors, diffs = audit_changes(old, corrected, delta)
    check('v3_to_v4_no_unrecorded_changes', not errors)
    check('v3_to_v4_report_matches_actual',
          read(structures / 'v3-to-v4-comparison.json')['actual_diffs'] == diffs)
    rules = io.load_records(structures / 'review557-adoption-rules.jsonl')
    check('557_adoption_rules_in_order', [r['candidate_id'] for r in rules] == ids)
    pmcs = io.load_records(structures / 'pmcs-structure.jsonl')
    pmcs_by_id = {r['row_id']: r for r in pmcs}
    tables = io.load_records(structures / 'review557-tables.jsonl')
    table_ids = {t['id'] for t in tables}
    for rule, decision in zip(rules, decisions):
        cid = rule['candidate_id']
        check('valid_adoption_rule:' + cid, valid_rule(rule, records))
        check('decision_rule_link:' + cid, rule['category'] == decision['category']
              and rule['correction_ids'] == decision['correction_ids'])
        if rule['category'] == 'TABLE_COLUMN_MERGE':
            check('pmcs_link:' + cid, bool(rule['pmcs_cell_refs']) and all(
                link['row_id'] in pmcs_by_id and link['record_id'] in records
                and records[link['record_id']]['text']
                == pmcs_by_id[link['row_id']]['fields'][link['field']]
                for link in rule['pmcs_cell_refs']))
        if rule['category'] == 'TABLE_ROW_ALIGNMENT':
            check('table_link:' + cid, rule['table_id'] in table_ids)
        if rule['category'] == 'FLOWCHART_BRANCH':
            check('branch_link:' + cid, rule['branch_label'] == 'No'
                  and rule['target_text'] == rule['native_span']['text'])
    check('four_tables_33_rows', {t['pdf_page']: len(t['rows']) for t in tables}
          == {272: 5, 276: 5, 830: 19, 854: 4})
    for table in tables:
        for index, row in enumerate(table['rows']):
            for field, cell in row.items():
                check(f'table_cell:{table["id"]}:{index}:{field}',
                      cell['text'] == '\n'.join(s['text'] for s in cell['source_spans'])
                      and all(valid_span(s, records) for s in cell['source_spans']))
    for row in pmcs:
        for field, text in row['fields'].items():
            check('pmcs_cell:' + row['row_id'] + ':' + field,
                  records[row['row_id'] + ':' + field]['text'] == text)
    for unit in io.load_records(structures / 'reading-order-units.jsonl'):
        check('reading_order:' + unit['id'], all(valid_span(s, records) for s in unit['source_spans'])
              and unit['text'] == '\n'.join(s['text'] for s in unit['source_spans']))
    for table in io.load_records(structures / 'restored-image-tables.jsonl'):
        check('existing_image_table:' + table['id'],
              records[table['source_record']]['text'][table['start']:table['end']] == table['source_text'])
    issue = read(structures / 'source118-review.json')
    check('source118_fragment_rule', valid_fragment(issue, records))
    check('source118_valid_imperative_retained',
          'Change fluid every 12,000 miles' in records['P0118:native']['text'])
    structure_audit = read(structures / 'structure-audit.json')
    check('structure_program_hash', structure_audit['program_sha256']
          == io.sha(io.BASE / 'build_review557_structures.py'))
    check('base_structure_program_hash', structure_audit['base_program_sha256']
          == io.sha(io.BASE / 'build_reviewed_structures.py'))
    check('no_557_unreviewed', structure_audit['unreviewed_within_557'] == 0)
    markup = (structures / '557건_검토내역.html').read_text(encoding='utf-8')
    image_links = re.findall(r'<img[^>]+src="([^"]+)"', markup)
    check('html_source_images_resolve', len(image_links) == 557
          and all((structures / link).is_file() for link in image_links))

    # Negative controls are in-memory only and never modify stored artifacts.
    controls = {}
    altered = copy.deepcopy(corrected)
    altered[0]['text'] += '\nUNRECORDED CONTENT'
    controls['unlogged_text_addition_detected'] = bool(audit_changes(old, altered, delta)[0])
    changed_span = copy.deepcopy(tables[0]['rows'][0]['ENGINE RPM']['source_spans'][0])
    changed_span['text'] += ' CHANGED'
    controls['table_cell_text_change_detected'] = not valid_span(changed_span, records)
    mixed = copy.deepcopy(next(r for r in rules if r['category'] in MIXED))
    mixed['ocr_allowed_as_single_prose_span'] = True
    controls['mixed_ocr_prose_adoption_detected'] = not valid_rule(mixed, records)
    controls['missing_candidate_detected'] = not full_coverage(decisions[:-1])
    changed_issue = copy.deepcopy(issue)
    changed_issue['affected_spans'][0]['allow_as_sufficient_answer_evidence'] = True
    controls['incomplete_fragment_eligibility_change_detected'] = not valid_fragment(changed_issue, records)
    for name, passed in controls.items():
        check('negative_control:' + name, passed)

    failures = [name for name, passed in checks.items() if not passed]
    report = {
        'status': 'FAIL' if failures else 'PASS', 'checks': checks, 'errors': failures,
        'reviewed_candidates': len(decisions), 'candidate_pages': len({d['pdf_page'] for d in decisions}),
        'candidates_with_text_corrections': sum(bool(d['correction_ids']) for d in decisions),
        'new_corrections': len(extra), 'cumulative_corrections': len(ledger['corrections']),
        'v3_to_v4_changed_records': len({d['record_id'] for d in diffs}),
        'v3_to_v4_changed_pages': len({d['pdf_page'] for d in diffs}),
        'v3_to_v4_diff_hunks': len(diffs), 'backup_files_verified': len(content),
        'correction_replay_files': len(correction_files), 'structure_replay_files': len(structure_files),
        'negative_controls': controls, 'verifier_sha256': io.sha(__file__),
        'ledger_sha256': io.sha(ledger_path),
        'source_correctness_proven_by_this_program': False,
        'source_visual_review_by': 'Codex', 'human_source_review': 'NOT_PERFORMED',
    }
    (io.BASE / 'audit/review557-v4.json').write_bytes(io.json_bytes(report))
    print(json.dumps({k: v for k, v in report.items() if k not in ('checks',)}, ensure_ascii=False))
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
