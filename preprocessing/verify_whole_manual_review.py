"""Verify replay, source-span projections, table links, and negative controls."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import correct_extraction as io


def projection_errors(units, source):
    errors = []
    seen = set()
    for unit in units:
        lines = []
        for ref in unit['source_spans']:
            key = (ref['record_id'], ref['start'], ref['end'])
            if key in seen:
                errors.append('duplicated_source_span')
            seen.add(key)
            rec = source[ref['record_id']]
            if rec['pdf_page'] != unit['pdf_page']:
                errors.append('wrong_source_page')
            exact = rec['text'][ref['start']:ref['end']]
            if exact != ref['text']:
                errors.append('altered_source_text')
            lines.append(exact)
            cx = (ref['bbox'][0] + ref['bbox'][2]) / 2
            suffix = unit['id'].rsplit(':',1)[1]
            if suffix == 'left' and cx >= 320 or suffix == 'right' and cx < 320:
                errors.append('cross_column_mixing')
        if unit['text'] != '\n'.join(lines):
            errors.append('unrecorded_projection_change')
    return errors


def verify():
    checks = {}
    def check(name, truth):
        checks[name] = bool(truth)
    def inventory(folder):
        return {p.relative_to(folder).as_posix(): io.sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}
    def manifest_check(folder):
        m = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        return all(io.sha(folder/name)==digest for name,digest in m['files'].items())
    raw = io.BASE/'output/full-manual-v2-a'
    v1 = io.BASE/'output/corrected-v1-a'
    current = io.BASE/'output/corrected-v3-a'
    review = io.BASE/'review-v2/verified-v3-a'
    original_ledger = io.BASE/'corrections/batch-001/correction-log.json'
    check('original_raw_payload_unchanged', manifest_check(raw))
    check('previous_corrected_v1_payload_unchanged', manifest_check(v1))
    check('previous_ledger_unchanged', io.sha(original_ledger)=='458d6ab83e72db3898e05e4200610b20d43a69573e4f2a906469ee4ba2067e09')
    a, b = inventory(current), inventory(io.BASE/'output/corrected-v3-b')
    check('correction_replay_all_files_byte_identical', a==b)
    c, d = inventory(review), inventory(io.BASE/'review-v2/verified-v3-b')
    check('structure_replay_all_files_byte_identical', c==d)
    check('structure_manifest_valid', manifest_check(review))
    source = {r['id']:r for r in io.load_records(current/'units-corrected.jsonl')}
    rows = io.load_records(review/'pmcs-structure.jsonl')
    byrow = {r['row_id']:r for r in rows}
    check('all_55_original_pmcs_rows_present', set(byrow)=={t['row_id'] for p in io.load_records(raw/'pages.jsonl') for t in p['tables']})
    check('all_275_cells_match_logged_text', sum(len(r['fields']) for r in rows)==275 and all(
        value==source[r['row_id']+':'+field]['text'] for r in rows for field,value in r['fields'].items()))
    check('continuation_links_do_not_cross_items', all(
        byrow[r[key]]['item']==r['item'] for r in rows for key in ['previous_row_in_item','next_row_in_item'] if r[key]))
    links = io.load_records(review/'pmcs-context-links.jsonl')
    check('context_links_are_exact_source_spans', all(
        source[r['source_record']]['text'][r['start']:r['end']]==r['text'] for r in links))
    units = io.load_records(review/'reading-order-units.jsonl')
    check('reading_order_text_and_source_spans_match', not projection_errors(units,source))
    mutated = copy.deepcopy(units); mutated[0]['text'] += '\nUNRECORDED SENTENCE'
    check('detects_unrecorded_added_sentence', bool(projection_errors(mutated,source)))
    mutated = copy.deepcopy(units); mutated[0]['source_spans'][0]['text'] += 'x'
    check('detects_changed_source_excerpt', bool(projection_errors(mutated,source)))
    mutated = copy.deepcopy(units); unit = next(r for r in mutated if r['id'].endswith(':left'))
    unit['id'] = unit['id'].replace(':left', ':right')
    check('detects_left_right_column_mixing', bool(projection_errors(mutated,source)))
    tables = io.load_records(review/'restored-image-tables.jsonl')
    check('restored_tables_preserve_logged_source', all(
        source[t['source_record']]['text'][t['start']:t['end']]==t['source_text'] for t in tables))
    components = next(t for t in tables if t['pdf_page']==856)
    reconstructed = ' | '.join(components['headers'])+'\n'+'\n'.join(
        ' | '.join(row[h] for h in components['headers']) for row in components['rows'])
    check('27_component_rows_and_all_cells_losslessly_serialized', len(components['rows'])==27 and reconstructed==components['source_text'])
    for suffix in ['a','b']:
        verified = json.loads((io.BASE/f'audit/corrections-v3-{suffix}.json').read_text(encoding='utf-8'))
        check('correction_audit_'+suffix, verified['status']=='PASS' and all(verified['checks'].values()))
    result = {'status':'PASS' if all(checks.values()) else 'FAIL', 'checks':checks,
              'corrected_replay_files':len(a), 'structure_replay_files':len(c),
              'program_sha256':io.sha(__file__), 'corpus_ready_for_index':False,
              'scope_note':'Integrity and the selected reviewed structures; not a certificate that every OCR character is correct.'}
    report = io.BASE/'audit/whole-manual-review-v3.json'
    report.write_bytes(io.json_bytes(result))
    print(json.dumps(result,ensure_ascii=False))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__=='__main__':
    verify()
