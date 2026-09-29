"""Replay recorded PDF extraction corrections without invoking a language model."""
from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
COLUMNS = ['ITEM NO.', 'INTERVAL', 'ITEM TO BE INSPECTED', 'PROCEDURES', 'NOT FULLY MISSION CAPABLE IF']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encoded(text):
    return text.replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8')


def json_bytes(value):
    return encoded(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def records_bytes(records):
    return encoded(''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in records))


def load_records(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line]


def source_records(pages_path):
    """Copy exact strings; do not normalize, select, summarize, or deduplicate."""
    records = []
    for page in load_records(pages_path):
        common = {k: page[k] for k in ('pdf_page', 'printed_page', 'in_scope')}
        for layer in ('native', 'ocr'):
            value = page[layer + '_body_text']
            if value is not None:
                records.append({**common, 'id': f'P{page["pdf_page"]:04d}:{layer}',
                                'layer': layer, 'text': value})
        for table in page['tables']:
            for field in COLUMNS:
                records.append({**common, 'id': table['row_id'] + ':' + field,
                                'layer': 'table', 'row_id': table['row_id'],
                                'table': table['table'], 'field': field,
                                'bbox': table['field_bboxes'][field],
                                'text': table['fields'][field]})
    return records


def validate_ledger(records, ledger):
    by_id = {r['id']: r for r in records}
    if len(by_id) != len(records):
        raise ValueError('Duplicate source record ID')
    seen, grouped = set(), {}
    for patch in ledger['corrections']:
        if patch['id'] in seen:
            raise ValueError('Duplicate correction ID')
        seen.add(patch['id'])
        record = by_id[patch['record_id']]
        start, end = patch['start'], patch['end']
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(record['text']):
            raise ValueError('Invalid correction range')
        if record['text'][start:end] != patch['before']:
            raise ValueError('Before text mismatch: ' + patch['id'])
        if not isinstance(patch['after'], str) or patch['before'] == patch['after']:
            raise ValueError('Invalid or empty correction')
        if '\r' in patch['after']:
            raise ValueError('Use LF within JSON text fields')
        if record['pdf_page'] != patch['pdf_page']:
            raise ValueError('Correction page mismatch')
        if patch['source_check'] != 'CODEX_PDF_VISUAL_CHECK':
            raise ValueError('Unconfirmed correction')
        if patch['human_review'] != 'NOT_PERFORMED':
            raise ValueError('This batch must not claim human review')
        if len(patch['bbox']) != 4 or not patch['reason']:
            raise ValueError('Missing source evidence')
        grouped.setdefault(record['id'], []).append(patch)
    for patches in grouped.values():
        patches.sort(key=lambda p: p['start'])
        for left, right in zip(patches, patches[1:]):
            if left['end'] > right['start']:
                raise ValueError('Overlapping corrections')
    return grouped


def apply_records(records, ledger):
    grouped = validate_ledger(records, ledger)
    result = copy.deepcopy(records)
    for record in result:
        for patch in reversed(grouped.get(record['id'], [])):
            record['text'] = record['text'][:patch['start']] + patch['after'] + record['text'][patch['end']:]
    return result


def text_export(records, scope_only=False):
    parts = []
    for record in records:
        if scope_only and not record['in_scope']:
            continue
        parts.append(f'[{record["id"]} | PDF {record["pdf_page"]} | PRINTED {record["printed_page"] or "UNRESOLVED"} | '
                     f'SCOPE {"YES" if record["in_scope"] else "NO"}]\n{record["text"]}\n\n')
    return encoded(''.join(parts))


def check_inputs(ledger):
    for key in ('pdf', 'pages'):
        info = ledger['inputs'][key]
        path = (ROOT / info['path']).resolve()
        if not path.is_relative_to(ROOT) or sha(path) != info['sha256']:
            raise ValueError('Input hash/path mismatch: ' + key)
    return ROOT / ledger['inputs']['pages']['path']


def check_crops(folder, ledger):
    for patch in ledger['corrections']:
        path = (folder / patch['evidence_crop']).resolve()
        if not path.is_relative_to(folder.resolve()) or sha(path) != patch['evidence_sha256']:
            raise ValueError('Evidence crop hash/path mismatch: ' + patch['id'])


def report_html(ledger):
    rows = []
    for p in ledger['corrections']:
        rows.append('<article><h2>' + html.escape(p['id']) + ' · PDF ' + str(p['pdf_page']) + '</h2>'
                    '<p>' + html.escape(p['record_id']) + '</p><img src="' + html.escape(p['evidence_crop'], quote=True)
                    + '" alt="PDF 원문 발췌"><div class="pair"><pre>' + html.escape(p['before'])
                    + '</pre><pre>' + html.escape(p['after']) + '</pre></div><p>' + html.escape(p['reason']) + '</p></article>')
    return encoded('<!doctype html><html lang="ko"><meta charset="utf-8"><title>PDF 텍스트 추출 오류 보정</title>'
                   '<style>body{font:16px/1.65 system-ui;max-width:1100px;margin:32px auto;padding:0 20px;background:#f5f6f8}'
                   'article,header{background:white;padding:24px;margin:16px 0;border:1px solid #ddd}'
                   'img{max-width:100%;height:auto}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}'
                   'pre{white-space:pre-wrap;overflow-wrap:anywhere;padding:12px;background:#f1f3f5}'
                   '@media(max-width:700px){.pair{grid-template-columns:1fr}}</style><header><h1>PDF 텍스트 추출 오류 보정</h1>'
                   '<p>왼쪽은 규칙 기반 추출 텍스트, 오른쪽은 보정 내용입니다. 각 원문 이미지는 PDF에서 직접 잘라낸 것입니다.</p>'
                   '<p>Codex의 원문 이미지 대조 결과를 기록했습니다. 사람의 원문 검증은 수행하지 않았습니다. '
                   '수정 기록과 실제 변경의 일치 여부는 별도 검증 프로그램으로 확인합니다. '
                   '이 목록은 전체 교범의 오류가 모두 해결되었다는 뜻이 아닙니다.</p></header>' + ''.join(rows) + '</html>')


def run(ledger_path, output):
    ledger_path, output = ledger_path.resolve(), output.resolve()
    ledger = json.loads(ledger_path.read_text(encoding='utf-8'))
    source = check_inputs(ledger)
    check_crops(ledger_path.parent, ledger)
    if output.exists():
        raise ValueError('Output must be a new directory')
    before = source_records(source)
    after = apply_records(before, ledger)
    output.mkdir(parents=True)
    files = {'units-before.jsonl': records_bytes(before), 'units-corrected.jsonl': records_bytes(after),
             'correction-log.json': ledger_path.read_bytes(),
             '규칙파싱_보정전.txt': text_export(before), 'Codex_보정본.txt': text_export(after),
             '실험범위_보정전.txt': text_export(before, True), '실험범위_보정본.txt': text_export(after, True),
             '보정내역.html': report_html(ledger)}
    for name, data in files.items():
        (output / name).write_bytes(data)
    for patch in ledger['corrections']:
        dest = output / patch['evidence_crop']
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((ledger_path.parent / patch['evidence_crop']).read_bytes())
    meta = {'schema': 1, 'batch': ledger['batch'], 'source_records': len(before),
            'corrections': len(ledger['corrections']), 'changed_records': sum(a != b for a, b in zip(before, after)),
            'human_source_review': 'NOT_PERFORMED', 'corpus_ready_for_index': False,
            'replay_invokes_llm': False, 'correction_proposals_by': ledger['tool'],
            'ledger_sha256': sha(ledger_path), 'program_sha256': sha(__file__),
            'files': {p.relative_to(output).as_posix(): sha(p) for p in sorted(output.rglob('*')) if p.is_file()}}
    (output / 'manifest.json').write_bytes(json_bytes(meta))
    print(json.dumps({'output': str(output), 'corrections': meta['corrections'],
                      'changed_records': meta['changed_records']}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.ledger, args.output)
