"""Independently audit actual changes against a frozen correction ledger."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path

import pymupdf

import correct_extraction as io


def audit_changes(before, after, corrections):
    """Compare untouched spans and each recorded replacement in both directions.

    Does not call the correction application's replacement function. The actual
    character diff is also collected independently for inspection.
    """
    errors, diffs = [], []
    if [r['id'] for r in before] != [r['id'] for r in after]:
        return ['Record IDs/order differ'], []
    groups, seen = {}, set()
    for p in corrections:
        if p['id'] in seen:
            errors.append('Duplicate correction ID: ' + p['id'])
        seen.add(p['id'])
        groups.setdefault(p['record_id'], []).append(p)
    known = {r['id'] for r in before}
    if set(groups) - known:
        errors.append('Unknown correction record')
    for old, new in zip(before, after):
        rid = old['id']
        if {k: v for k, v in old.items() if k != 'text'} != {k: v for k, v in new.items() if k != 'text'}:
            errors.append('Metadata changed: ' + rid)
        left, right = old['text'], new['text']
        patches = sorted(groups.get(rid, []), key=lambda p: p['start'])
        a = b = 0
        for p in patches:
            start, end = p['start'], p['end']
            if type(start) is not int or type(end) is not int or not a <= start < end <= len(left):
                errors.append('Invalid/overlapping range: ' + p['id'])
                continue
            if left[start:end] != p['before'] or p['before'] == p['after']:
                errors.append('Invalid before/after: ' + p['id'])
            unchanged = left[a:start]
            if right[b:b + len(unchanged)] != unchanged:
                errors.append('Unrecorded change before: ' + p['id'])
            b += len(unchanged)
            if right[b:b + len(p['after'])] != p['after']:
                errors.append('Recorded correction missing or different: ' + p['id'])
            a, b = end, b + len(p['after'])
        if left[a:] != right[b:]:
            errors.append('Unrecorded change in remaining text: ' + rid)
        if left != right:
            matcher = difflib.SequenceMatcher(None, left, right, autojunk=False)
            for tag, a1, a2, b1, b2 in matcher.get_opcodes():
                if tag != 'equal':
                    diffs.append({'record_id': rid, 'pdf_page': old['pdf_page'], 'operation': tag,
                                  'before_start': a1, 'before_end': a2, 'after_start': b1, 'after_end': b2,
                                  'before': left[a1:a2], 'after': right[b1:b2]})
    return errors, diffs


def verify(folder, ledger_path):
    folder, ledger_path = folder.resolve(), ledger_path.resolve()
    ledger = json.loads(ledger_path.read_text(encoding='utf-8'))
    errors, checks = [], {}

    def check(name, condition):
        checks[name] = bool(condition)
        if not condition:
            errors.append(name)

    source = io.check_inputs(ledger)
    io.check_crops(ledger_path.parent, ledger)
    before = io.load_records(folder / 'units-before.jsonl')
    after = io.load_records(folder / 'units-corrected.jsonl')
    expected_before = io.source_records(source)
    io.validate_ledger(expected_before, ledger)
    check('baseline_matches_original_parser_records', before == expected_before)
    check('baseline_bytes_match', (folder / 'units-before.jsonl').read_bytes() == io.records_bytes(expected_before))
    check('corrected_records_encoding_matches', (folder / 'units-corrected.jsonl').read_bytes() == io.records_bytes(after))
    check('frozen_ledger_matches', (folder / 'correction-log.json').read_bytes() == ledger_path.read_bytes())
    delta_errors, diffs = audit_changes(expected_before, after, ledger['corrections'])
    check('actual_changes_exactly_match_ledger', not delta_errors)
    errors.extend(delta_errors)
    for name, records, scope in [('규칙파싱_보정전.txt', expected_before, False), ('Codex_보정본.txt', after, False),
                                 ('실험범위_보정전.txt', expected_before, True), ('실험범위_보정본.txt', after, True)]:
        check('text_export:' + name, (folder / name).read_bytes() == io.text_export(records, scope))
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    check('manifest_ledger_hash', manifest['ledger_sha256'] == io.sha(ledger_path))
    check('manifest_application_hash', manifest['program_sha256'] == io.sha(io.__file__))
    check('html_matches_ledger', (folder / '보정내역.html').read_bytes() == io.report_html(ledger))
    for patch in ledger['corrections']:
        check('crop:' + patch['id'], io.sha(folder / patch['evidence_crop']) == patch['evidence_sha256'])
    with pymupdf.open(io.ROOT / ledger['inputs']['pdf']['path']) as pdf:
        for patch in ledger['corrections']:
            image = pdf[patch['pdf_page'] - 1].get_pixmap(clip=pymupdf.Rect(patch['render_clip']), dpi=180, alpha=False)
            check('crop_matches_source_pdf:' + patch['id'],
                  hashlib.sha256(image.tobytes('png')).hexdigest() == patch['evidence_sha256'])
    for name, digest in manifest['files'].items():
        p = (folder / name).resolve()
        check('output_hash:' + name, p.is_relative_to(folder) and p.is_file() and io.sha(p) == digest)
    actual_files = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    check('no_unmanifested_outputs', actual_files == set(manifest['files']) | {'manifest.json'})
    diff_text = ''.join(difflib.unified_diff(io.text_export(expected_before).decode('utf-8').splitlines(True),
                                            io.text_export(after).decode('utf-8').splitlines(True),
                                            fromfile='규칙파싱_보정전.txt', tofile='Codex_보정본.txt', n=2))
    result = {'status': 'PASS' if not errors else 'FAIL', 'checks': checks, 'errors': errors,
              'records_checked': len(expected_before), 'recorded_corrections': len(ledger['corrections']),
              'changed_records': len({d['record_id'] for d in diffs}), 'actual_diff_hunks': len(diffs),
              'actual_diffs': diffs, 'verifier_sha256': io.sha(__file__), 'ledger_sha256': io.sha(ledger_path),
              'source_correctness_proven_by_this_program': False, 'human_source_review': 'NOT_PERFORMED'}
    return result, diff_text


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.resolve().is_relative_to(args.output.resolve()):
        raise SystemExit('Save the audit outside the frozen output directory')
    try:
        result, diff = verify(args.output, args.ledger)
    except (ValueError, KeyError, OSError, TypeError) as exc:
        result, diff = {'status': 'FAIL', 'errors': [str(exc)]}, ''
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_bytes(io.json_bytes(result))
    args.report.with_suffix('.diff').write_bytes(io.encoded(diff))
    print(json.dumps({k: v for k, v in result.items() if k not in ('checks', 'actual_diffs')}, ensure_ascii=False))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
