"""Export reviewed PMCS relationships and a whole-manual review register.

This sidecar describes source structure. It never silently rewrites corrected
text or turns diagram geometry into prose. It is not the retrieval index.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import copy
import difflib
import json
from pathlib import Path
import re
import correct_extraction as io
from verify_corrections import audit_changes

ACTUAL_TABLES = {
    60: ('model_matrix', '세로로 회전된 차종 머리글 16개와 기능 행을 좌표로 대응. x의 줄 순서만으로 대응하면 안 됨.'),
    61: ('tabulated_data', 'STANDARD/METRIC와 항목·소항목·각주를 함께 유지. 11 qt/13.2 L는 원문 표기 그대로 보존.'),
    62: ('tabulated_data', '동명 ENGINE 항목을 6.2 L, 6.5 L 조건별로 분리하고 단위 열 유지.'),
    63: ('tabulated_data', '3L80/4L80-E 및 전륜/후륜 등 상위 조건을 하위 행에 연결.'),
    64: ('tabulated_data', '차종 목록이 여러 줄로 감긴 행을 하나의 조건으로 유지.'),
    119: ('parts_lists', '반기/연간 표 분리. ITEM NO 기준 11행/12행. 열 전체를 한 행으로 묶으면 안 됨.'),
    120: ('parts_and_lubrication', '부품표 16행. 연식 괄호는 같은 부품 행에 속함. 윤활표의 온도·유종·용량 및 표 아래 각주 유지.'),
    121: ('lubrication_continued', 'PDF 120에서 이어진 표. 변속기 모델·건식/교환주입·극지 조건 구분. 빈 셀에 값을 추정해 넣지 않음.'),
    196: ('pump_part_cross_reference', '열: Model Pump P/N (NSN), Serial Number Break, Original P/N, New P/N (NSN). 본문에 있는 교환 조건을 표와 연결.'),
    272: ('oil_pressure', 'STOP, 6.2L IDLE, 6.5L IDLE, 6.5L DETUNED IDLE, 2000의 5행. DETUNED 줄바꿈을 별도 행으로 만들지 않음.'),
    276: ('oil_pressure', 'PDF 272와 같은 5행 구조. 각 표의 원래 페이지 출처는 별도로 보존.'),
    277: ('alternator_adaption', '100/200/400 Amp 3행. 400 Amp 행의 No를 반드시 유지.'),
    300: ('wire_terminal_table_in_image', '그림 위에 인쇄된 5행 대응표는 문자로 전사 가능. 아래 배선 그림의 선 연결을 문자로 추론하지 않음.'),
    329: ('ignition_diagnostics', 'OFF/RUN/START, PCB/Distribution Box, 엔진 정지/작동 조건별 7개 묶음. 순서대로 문장을 이어 붙이면 조건이 섞임.'),
    531: ('dtc85_ratio_table_in_image', 'DTC 85의 기어별 LESS THAN/MORE THAN 4행. DTC 86/87 문단과 분리. native 텍스트에 표 값이 없어 OCR 필요.'),
    532: ('j1_measurements_with_flow', '시동 OFF/ON 두 표, 5행/4행. PIN 대소문자 유지. 오른쪽 No 분기 화살표는 일반 데이터 열이 아님.'),
    830: ('test_index', 'TEST NAME/TEST #/PAGE # 19행. 텍스트 추출에서 뒤로 몰린 PAGE #를 y좌표에 따라 대응.'),
    854: ('status_readouts', '표 번호만으로 식별하지 않음: 이 절의 Table 2-1은 PMCS가 아님. PASS/FAIL은 공통 설명을 가짐.'),
    855: ('prompting_and_error_readouts', '위쪽 5개 prompting 행과 아래쪽 14개 error 행을 별도 표로 구분. 원문 E01l 표기와 문장 오류는 추정 수정하지 않음.'),
    856: ('transducer_components_in_image', '27행 5열. ITEM NO, TK NO, PART NO, QTY, ITEM을 구분. native에는 본 표 데이터가 없으므로 OCR만 누락 없이 추출해야 함.'),
    887: ('dca_tk_cross_reference', '실험 범위 밖 접지. 오른쪽 표와 왼쪽 전기 배선도를 분리.'),
    888: ('conversion_factors', '실험 범위 밖. 변환 방향별 두 표, TO CHANGE/TO/MULTIPLY BY 3열.'),
}

SOURCE_ISSUES = [
    (97, 'OD_SYMBOL', 'OCR의 (QD)는 원문의 타원 안 D 기호를 온전히 표현하지 못함. 기호를 임의의 다른 약어로 확정하지 않음.', 'SYMBOL_TRANSCRIPTION_UNRESOLVED'),
    (98, 'MISPLACED_BELT', 'Belt가 원문에서 INTERVAL 열에 배치되어 있음. 내부 공백만 보정하고 열 이동은 하지 않음.', 'SOURCE_LAYOUT_ANOMALY'),
    (99, 'PRINTED_Z_CARON', '글머리표 위치의 Ž는 PDF 화면에서도 Ž로 보임. 일반 글머리표로 추정 교체하지 않음.', 'SOURCE_TEXT_PRESERVED'),
    (101, 'TORQUE_PUNCTUATION', '21 lb-ft 29 (N•m)의 괄호 배치는 원문 그대로임.', 'SOURCE_TEXT_PRESERVED'),
    (103, 'THROUGHLY', 'Throughly는 원문 오탈자. 추출 오류 보정 범위에서 철자를 고치지 않음.', 'SOURCE_TEXT_PRESERVED'),
    (106, 'REEFER', 'reefer to Appendix B는 원문 표기임.', 'SOURCE_TEXT_PRESERVED'),
    (107, 'MISSING_MILES', 'every 3,000 (4,800 km)에 miles가 원문에서 생략됨. 추정 보충하지 않음.', 'SOURCE_TEXT_PRESERVED'),
    (111, 'OPTIMUMLY', 'optimumly는 원문 표기임. 타이어 회전/조임 순서는 그림에 의존.', 'SOURCE_TEXT_AND_DIAGRAM_DEPENDENCY'),
    (115, 'REEFER_CASE', 'Reefer to para. 2-39는 원문 표기임.', 'SOURCE_TEXT_PRESERVED'),
    (118, 'TRUNCATED_ITEM32', 'Change fluid every 12,000 miles 및 Metal particles are에서 원문 문장이 끝남. 다음 PDF 119쪽은 부품 목록으로 전환됨.', 'SOURCE_INCOMPLETE_NO_INFERRED_COMPLETION'),
    (61, 'CAPACITY_INCONSISTENCY', '3L80 W/Dry Converter: 11 qt와 13.2 L가 함께 인쇄됨. 단위를 재계산해 교체하지 않음.', 'SOURCE_NUMERIC_INCONSISTENCY'),
    (296, 'TORQUE_UNIT_INCONSISTENCY', '10-15 lb-in. (14-20 N•m)는 원문 표기. Ib-in OCR만 기존 batch-001에서 보정.', 'SOURCE_NUMERIC_INCONSISTENCY'),
    (267, 'TEAT', 'Teat가 PDF 화면에도 인쇄됨.', 'SOURCE_TEXT_PRESERVED'),
    (398, 'CURRANT', 'battery currant가 PDF 화면에도 인쇄됨.', 'SOURCE_TEXT_PRESERVED'),
    (836, 'TEAT', 'Teat requires가 PDF 화면에도 인쇄됨.', 'SOURCE_TEXT_PRESERVED'),
    (841, 'PROCEDUREAS', 'Pre-Test Procedureas가 PDF 화면에도 인쇄됨.', 'SOURCE_TEXT_PRESERVED'),
    (846, 'TEAT', 'Teat Procedure가 PDF 화면에도 인쇄됨.', 'SOURCE_TEXT_PRESERVED'),
    (848, 'CURRANT', 'DC currant가 PDF 화면에도 인쇄됨.', 'SOURCE_TEXT_PRESERVED'),
    (850, 'TEAT_AND_STATUE', 'Simplified Teat 및 Statue Readout은 PDF 화면에도 인쇄됨.', 'SOURCE_TEXT_PRESERVED'),
    (855, 'ERROR_CODE_AND_TEXT', 'E01l, Signal to ECT switches, CI ower 등 원문 표기를 임의로 추정 복원하지 않음.', 'SOURCE_IDENTIFIER_REQUIRES_CAUTION'),
]


def build(out, revision=3):
    if out.exists():
        raise ValueError('Output must be new')
    inventory = io.BASE / 'review-v2/inventory'
    rawpath = io.BASE / 'output/full-manual-v2-a/pages.jsonl'
    correctedpath = io.BASE / f'output/corrected-v{revision}-a/units-corrected.jsonl'
    parsed = io.load_records(rawpath)
    fixed = {r['id']: r for r in io.load_records(correctedpath)}
    oldledgerpath = io.BASE / 'corrections/batch-001/correction-log.json'
    ledgerpath = io.BASE / f'corrections/batch-{revision:03d}/correction-log.json'
    oldledger = json.loads(oldledgerpath.read_text(encoding='utf-8'))
    ledger = json.loads(ledgerpath.read_text(encoding='utf-8'))
    before_v1 = io.load_records(io.BASE / 'output/corrected-v1-a/units-corrected.jsonl')
    after_v2 = list(fixed.values())
    original_patches = {p['id']: p for p in oldledger['corrections']}
    assert all(p == original_patches[p['id']] for p in ledger['corrections'] if p['id'] in original_patches)
    delta_patches = copy.deepcopy([p for p in ledger['corrections'] if p['id'] not in original_patches])
    for p in delta_patches:
        shift = sum(len(q['after']) - len(q['before']) for q in oldledger['corrections']
                    if q['record_id'] == p['record_id'] and q['end'] <= p['start'])
        p['start'] += shift; p['end'] += shift
    errors, deltas = audit_changes(before_v1, after_v2, delta_patches)
    assert not errors, errors

    table_rows = [t for p in parsed for t in p['tables']]
    pmcs, groups = [], defaultdict(list)
    context_targets = {'P0096-T2_1-R01': '1', 'P0100-T2_1-R01': '7', 'P0102-T2_1-R01': '10'}
    for t in table_rows:
        fields = {c: fixed[t['row_id'] + ':' + c]['text'] for c in io.COLUMNS}
        item = t['item']
        role = 'item' if item else ('context' if t['row_id'] in context_targets else 'empty_extraction_row')
        # Keep every original row, including the spurious empty one, auditable.
        assert role != 'empty_extraction_row' or not any(fields.values())
        entry = {'row_id': t['row_id'], 'pdf_page': t['pdf_page'], 'item': item, 'role': role,
                 'fields': fields, 'source_field_bboxes': t['field_bboxes'],
                 'context_for_item': context_targets.get(t['row_id']),
                 'source_check': 'CODEX_PDF_VISUAL_CHECK', 'human_review': 'NOT_PERFORMED',
                 'blank_cells': [k for k, v in fields.items() if not v],
                 'source_issues': [i[1] for i in SOURCE_ISSUES if i[0] == t['pdf_page']],
                 'previous_row_in_item': None, 'next_row_in_item': None}
        pmcs.append(entry)
        if item:
            groups[item].append(entry)
    for entries in groups.values():
        for i, row in enumerate(entries):
            row['previous_row_in_item'] = entries[i - 1]['row_id'] if i else None
            row['next_row_in_item'] = entries[i + 1]['row_id'] if i + 1 < len(entries) else None
    # These references select exact corrected source spans; they do not add prose.
    contexts = []
    for row in pmcs:
        if row['role'] == 'context':
            rid = row['row_id'] + ':PROCEDURES'
            contexts.append({'id': row['row_id'] + ':CONTEXT', 'source_record': rid,
                             'start': 0, 'end': len(fixed[rid]['text']), 'text': fixed[rid]['text'],
                             'applies_to_items': [row['context_for_item']], 'relation': 'preceding_context'})
    for rid, marker, items, relation in [
        ('P0114-T2_1-R01:PROCEDURES', 'SPECIAL PURPOSE KITS', ['22','23','24','25','26'], 'section_heading'),
        ('P0116-T2_1-R01:PROCEDURES', 'NOTE\nIf Annual/Biennial', ['27'], 'final_road_test_timing'),
    ]:
        text = fixed[rid]['text']; start = text.index(marker)
        contexts.append({'id': rid + ':CONTEXT', 'source_record': rid, 'start': start, 'end': len(text),
                         'text': text[start:], 'applies_to_items': items, 'relation': relation})
    for c in contexts:
        assert fixed[c['source_record']]['text'][c['start']:c['end']] == c['text']
        assert all(item in groups for item in c['applies_to_items'])
    assert len(pmcs) == 55 and len(groups) == 36
    # Preserve and account for all 275 original cells exactly, including empties.
    assert sum(len(r['fields']) for r in pmcs) == 275
    assert all(r['fields'][col] == fixed[r['row_id'] + ':' + col]['text'] for r in pmcs for col in io.COLUMNS)
    assert pmcs[[r['row_id'] for r in pmcs].index('P0109-T2_1-R01')]['fields']['INTERVAL'] == 'Semi-\nAnnual'
    assert fixed['P0117-T2_1-R03:PROCEDURES']['text'].endswith('model transmissions.')
    assert fixed['P0117-T2_1-R04:PROCEDURES']['text'].startswith('CAUTION')

    candidates = io.load_records(inventory / 'table-candidates.jsonl')
    candidate_pages = {r['pdf_page'] for r in candidates}
    registry = []
    for n in sorted(candidate_pages | set(ACTUAL_TABLES) | set(range(526, 531))):
        if 96 <= n <= 118:
            kind, note = 'pmcs', '5열 모든 셀 원문 대조. 동일 항목의 페이지 연결과 앞선 경고·주의·NOTE 관계를 별도 저장.'
        elif n in ACTUAL_TABLES:
            kind, note = ACTUAL_TABLES[n]
        elif 860 <= n <= 863:
            kind, note = 'flowchart_with_table_caption', 'Table 제목이지만 YES/NO 분기 흐름도. 행/열 텍스트 표로 변환하지 않음.'
        elif 868 <= n <= 871:
            kind, note = 'administrative_form', '실험 범위 밖 양식. native 폰트 매핑 오류가 있어 OCR 대안을 보존.'
        elif 526 <= n <= 530:
            kind, note = 'two_column_prose', 'DTC별 두 단 본문. x좌표별로 단을 나누고 각 단 안에서 y순서로 읽어야 함.'
        else:
            kind, note = 'diagram_not_data_table', '선 검출기가 도식·시험 절차 상자를 표 후보로 반환. 행/열 표가 아니며 연결 관계를 추정하여 직렬화하지 않음.'
        registry.append({'pdf_page': n, 'in_scope': parsed[n-1]['in_scope'], 'kind': kind,
                         'from_automatic_table_detector': n in candidate_pages,
                         'review': 'CODEX_SOURCE_LAYOUT_REVIEW', 'handling': note,
                         'indexed_by_this_review': False})
    assert candidate_pages <= {r['pdf_page'] for r in registry}
    decisions = []
    patchpages = defaultdict(list)
    for p in ledger['corrections'][51:]:
        patchpages[p['pdf_page']].append(p)
    for c in io.load_records(inventory / 'text-candidates.jsonl'):
        matched = [p['id'] for p in patchpages[c['pdf_page']]
                   if p['record_id'] == c['record_id'] and p['start'] <= c['start'] < p['end']]
        if matched:
            status = 'CORRECTED'; note = '원문 대조 후 수정 기록에 반영.'
        elif c['pdf_page'] == 26:
            status = 'OUT_OF_SCOPE_THUMBNAIL_OCR_NO_GUESS'; note = '본문에 삽입된 축소 예시의 OCR. 실험 범위 밖이며 작아 추정 수정하지 않음.'
        else:
            status = 'SOURCE_TYPO_PRESERVED'; note = 'PDF 렌더링에도 같은 표기가 있어 추출 오류로 교정하지 않음.'
        decisions.append({**c, 'status': status, 'correction_ids': matched, 'decision': note})
    # The alignment report is triage, not a correctness certificate.
    def compact(s):
        return re.sub(r'[^\w]', '', s.casefold())
    alignments = []
    for r in io.load_records(inventory / 'native-ocr-disagreements.jsonl'):
        row = dict(r)
        patches = [p['id'] for p in ledger['corrections'] if p['record_id'] == r['record_id']
                   and r['offset'] <= p['start'] < r['offset'] + len(r['native'])]
        if patches:
            status = 'SOURCE_CHECKED_CORRECTION_RECORDED'
        elif compact(r['native']) == compact(r['ocr']):
            status = 'TYPOGRAPHY_ONLY_AUTOMATIC_TRIAGE'
        else:
            status = 'UNRESOLVED_LAYER_DISAGREEMENT_NOT_AUTO_REPLACED'
        row.update(status=status, correction_ids=patches)
        alignments.append(row)
    # A traceable reading-order projection for the six checked DTC pages.
    # Every character in a projected line is an exact span in the corrected
    # source record. No generation, punctuation correction or dehyphenation.
    from audit_whole_manual import line_positions
    layout_units = []
    for n in range(526,532):
        rid = f'P{n:04d}:native'
        refs = []
        for start, line in line_positions(parsed[n-1], 'native'):
            end = start + len(line['text'])
            left_shift = sum(len(p['after']) - len(p['before']) for p in ledger['corrections']
                             if p['record_id'] == rid and p['end'] <= start)
            length_shift = sum(len(p['after']) - len(p['before']) for p in ledger['corrections']
                               if p['record_id'] == rid and start <= p['start'] < end)
            a, b = start + left_shift, end + left_shift + length_shift
            refs.append({'record_id': rid, 'start': a, 'end': b, 'bbox': line['bbox'],
                         'text': fixed[rid]['text'][a:b]})
        assert len(refs) == sum(len(b['lines']) for b in parsed[n-1]['native_blocks'])
        groups_by_column = defaultdict(list)
        for ref in refs:
            box = ref['bbox']; cx = (box[0] + box[2]) / 2
            group = 'header' if box[1] < 115 else ('left' if cx < 320 else 'right')
            groups_by_column[group].append(ref)
        for group in ('header', 'left', 'right'):
            selected = sorted(groups_by_column[group], key=lambda r: (round(r['bbox'][1],1), r['bbox'][0]))
            if selected:
                layout_units.append({'id': f'P{n:04d}:layout:{group}', 'pdf_page': n, 'kind': 'coordinate_reading_order',
                                     'source_spans': selected, 'text': '\n'.join(r['text'] for r in selected),
                                     'source_image_review': 'CODEX_LAYOUT_CHECK',
                                     'text_quality': 'SOURCE_CHARACTERS_PRESERVED_NOT_ALL_GLYPHS_CORRECTED',
                                     'table_child_ids': ['P0531:ratio-table'] if n == 531 and group == 'left' else []})
        assert sum(len(r['source_spans']) for r in layout_units if r['pdf_page']==n) == len(refs)
    # Structured rows restored from the logged OCR table corrections.
    restored_tables = []
    rid = 'P0856:ocr'; text = fixed[rid]['text']
    if revision >= 3:
        start = text.index('ITEM NO. | TK NO.')
        lines = text[start:].splitlines(); headers = lines[0].split(' | ')
        rows = [dict(zip(headers, line.split(' | '))) for line in lines[1:]]
        assert len(rows) == 27 and all(len(line.split(' | '))==5 for line in lines)
        assert [int(r['ITEM NO.']) for r in rows] == list(range(1,28))
        restored_tables.append({'id': 'P0856:components', 'pdf_page': 856, 'source_record': rid,
                                'start': start, 'end': len(text), 'source_text': text[start:],
                                'headers': headers, 'rows': rows, 'correction_ids': ['FIX-0110']})
    rid = 'P0531:ocr'; text = fixed[rid]['text']; start = text.index('COMMANDED IF CALCULATED')
    end = text.index('REV 1.97 2.17', start) + len('REV 1.97 2.17')
    data = text[start:end].splitlines()[2:]
    assert len(data)==4
    restored_tables.append({'id': 'P0531:ratio-table', 'pdf_page': 531, 'source_record': rid,
                            'start': start, 'end': end, 'source_text': text[start:end],
                            'headers': ['COMMANDED GEAR', 'LESS THAN', 'MORE THAN'],
                            'rows': [dict(zip(['COMMANDED GEAR','LESS THAN','MORE THAN'], line.split())) for line in data],
                            'parent_condition': 'DTC 85 Will Set When', 'parent_pdf_page': 531})
    for unit in layout_units:
        assert unit['text'] == '\n'.join(fixed[s['record_id']]['text'][s['start']:s['end']] for s in unit['source_spans'])
    for t in restored_tables:
        assert t['source_text'] == fixed[t['source_record']]['text'][t['start']:t['end']]
    out.mkdir(parents=True)
    files = {'pmcs-structure.jsonl': pmcs, 'pmcs-context-links.jsonl': contexts,
             'table-layout-review.jsonl': registry, 'text-candidate-decisions.jsonl': decisions,
             'alignment-triage.jsonl': alignments, 'reading-order-units.jsonl': layout_units,
             'restored-image-tables.jsonl': restored_tables,
             'source-issues.jsonl': [{'pdf_page': n, 'id': k, 'description': d, 'status': s} for n,k,d,s in SOURCE_ISSUES]}
    for name, values in files.items():
        (out / name).write_bytes(io.records_bytes(values))
    delta_result = {'status': 'PASS', 'errors': errors, 'from': 'corrected-v1-a', 'to': f'corrected-v{revision}-a',
                    'additional_corrections': len(delta_patches), 'changed_records': len({d['record_id'] for d in deltas}),
                    'changed_pages': sorted({d['pdf_page'] for d in deltas}), 'diff_hunks': len(deltas),
                    'actual_diffs': deltas, 'independent_audit': 'audit_changes; untouched spans compared too'}
    (out / f'v1-to-v{revision}-comparison.json').write_bytes(io.json_bytes(delta_result))
    diff = ''.join(difflib.unified_diff(io.text_export(before_v1).decode('utf-8').splitlines(True),
                                      io.text_export(after_v2).decode('utf-8').splitlines(True),
                                      fromfile='corrected-v1-a/Codex_보정본.txt', tofile=f'corrected-v{revision}-a/Codex_보정본.txt', n=2))
    (out / f'v1-to-v{revision}.diff').write_bytes(io.encoded(diff))
    # Save the exact replayable metadata projection and its counts/hashes.
    result = {'status': 'PASS', 'pages_screened': len(parsed), 'in_scope_pages': sum(p['in_scope'] for p in parsed),
              'pmcs_pages_visually_compared': list(range(96,119)), 'pmcs_rows': len(pmcs), 'pmcs_cells': 275,
              'pmcs_items': len(groups), 'context_links': len(contexts), 'table_candidate_pages_reviewed': len(candidates),
              'reading_order_pages': list(range(526,532)), 'reading_order_units': len(layout_units),
              'restored_image_table_rows': sum(len(t['rows']) for t in restored_tables),
              'additional_layout_pages': sorted({r['pdf_page'] for r in registry} - candidate_pages),
              'layout_kinds': dict(Counter(r['kind'] for r in registry)),
              'text_candidate_dispositions': dict(Counter(r['status'] for r in decisions)),
              'alignment_dispositions': dict(Counter(r['status'] for r in alignments)),
              'remaining_ocr_signals': 'Not all low-confidence OCR words have been visually checked; retain original signals.',
              'all_pages_character_verified': False, 'corpus_ready_for_index': False,
              'human_source_review': 'NOT_PERFORMED', 'evaluation_questions_read': False,
              'inputs': {'source_pages_sha256': io.sha(rawpath), 'corrected_units_sha256': io.sha(correctedpath),
                         'ledger_sha256': io.sha(ledgerpath)}, 'program_sha256': io.sha(__file__)}
    (out / 'structure-audit.json').write_bytes(io.json_bytes(result))
    (out / 'manifest.json').write_bytes(io.json_bytes({'files': {p.name: io.sha(p) for p in sorted(out.iterdir()) if p.is_file()}}))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--revision', type=int, choices=[2,3], default=3)
    args = ap.parse_args()
    build(args.output.resolve(), args.revision)
