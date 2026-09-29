"""Freeze source-checked corrections from the whole-manual review; never call an LLM."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import pymupdf
import correct_extraction as io

REVIEW = io.BASE / 'review-v2'
OUT = io.BASE / 'corrections/batch-002'


def build():
    if OUT.exists():
        raise ValueError('Use a new batch folder; frozen batches must not be overwritten')
    previous = io.BASE / 'corrections/batch-001/correction-log.json'
    ledger = json.loads(previous.read_text(encoding='utf-8'))
    source = io.check_inputs(ledger)
    records = io.source_records(source)
    byid = {r['id']: r for r in records}
    pages = {p['pdf_page']: p for p in io.load_records(source)}
    doc = pymupdf.open(io.ROOT / ledger['inputs']['pdf']['path'])
    OUT.mkdir(parents=True)
    (OUT / 'evidence').mkdir()
    for p in ledger['corrections']:
        target = OUT / p['evidence_crop']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((previous.parent / p['evidence_crop']).read_bytes())

    def add(rid, before, after, reason, bbox=None, occurrence=0):
        r = byid[rid]
        positions, start = [], 0
        while True:
            pos = r['text'].find(before, start)
            if pos < 0:
                break
            positions.append(pos)
            start = pos + len(before)
        if not positions or occurrence >= len(positions):
            raise ValueError(f'Cannot locate {rid}: {before!r}')
        pos = positions[occurrence]
        if bbox is None:
            if r['layer'] == 'table':
                bbox = r['bbox']
            else:
                # Use the original line positions, not corrected offsets.
                from audit_whole_manual import line_positions
                lines = [(a, l) for a, l in line_positions(pages[r['pdf_page']], r['layer'])
                         if a <= pos < a + len(l['text'])]
                if not lines:
                    raise ValueError('No original line coordinates: ' + rid)
                bbox = lines[0][1]['bbox']
        clip = pymupdf.Rect(bbox)
        clip.x0 -= 4; clip.x1 += 4; clip.y0 -= 5; clip.y1 += 5
        clip &= doc[r['pdf_page'] - 1].rect
        pid = f'FIX-{len(ledger["corrections"]) + 1:04d}'
        crop = 'evidence/' + pid + '.png'
        doc[r['pdf_page'] - 1].get_pixmap(dpi=180, alpha=False, clip=clip).save(OUT / crop)
        ledger['corrections'].append({
            'id': pid, 'record_id': rid, 'pdf_page': r['pdf_page'],
            'start': pos, 'end': pos + len(before), 'before': before, 'after': after,
            'bbox': list(bbox), 'render_clip': list(clip), 'reason': reason,
            'source_check': 'CODEX_PDF_VISUAL_CHECK', 'human_review': 'NOT_PERFORMED',
            'evidence_crop': crop, 'evidence_sha256': io.sha(OUT / crop)})

    table = lambda page, row, field: f'P{page:04d}-T2_1-R{row:02d}:{field}'
    # Actual OCR / column-boundary errors, checked against PDF 96-118.
    fixes = [
        (97, 1, 'ITEM NO.', '1\ni', '1'),
        (97, 2, 'NOT FULLY MISSION CAPABLE IF', 'ec. Any', 'c. Any'),
        (97, 2, 'PROCEDURES', 'loose o1', 'loose or'),
        (97, 3, 'INTERVAL', '| Semi-', 'Semi-'),
        (97, 3, 'ITEM TO BE INSPECTED', 'System\n|', 'System'),
        (103, 2, 'INTERVAL', 'Semi-\nAnnual\n\n|\n|', 'Semi-\nAnnual'),
        (103, 2, 'ITEM NO.', '11\n|', '11'),
        (103, 2, 'ITEM TO BE INSPECTED', 'System\n|', 'System'),
        (103, 2, 'PROCEDURES', 'installing |', 'installing'),
        (103, 2, 'PROCEDURES', 'cylinder. |', 'cylinder.'),
        (103, 2, 'PROCEDURES', 'cylinder |', 'cylinder'),
        (103, 2, 'PROCEDURES', 'necessary. |', 'necessary.'),
        (109, 1, 'INTERVAL', '\nCENTER\nSUPPORT\nBEARING\nRUBBER\nBLOCK', ''),
        (111, 1, 'ITEM TO BE INSPECTED', "(Cont'd)\n|", "(Cont'd)"),
        (114, 1, 'PROCEDURES', '.WARNING.', 'WARNING'),
        (118, 2, 'PROCEDURES', '\nTRANSFER CASE', ''),
    ]
    for page, row, field, before, after in fixes:
        reason = 'PDF 원문과 대조하여 OCR 문자 오인식 또는 표 선의 문자 혼입을 보정.'
        if page == 109:
            reason = 'INTERVAL 열로 들어간 그림의 부품명 제거. 부품명은 원시 페이지 텍스트에 보존되며 점검 주기가 아니다.'
        if page == 118:
            reason = '그림 캡션이 PROCEDURES의 끊긴 문장 뒤에 붙은 부분 제거. 원문에서 누락된 문장 내용은 채우지 않음.'
        add(table(page, row, field), before, after, reason)
    rid = table(103, 2, 'PROCEDURES')
    for i in range(byid[rid]['text'].count('¢')):
        add(rid, '¢', '•', '원문 PDF의 원형 글머리표가 센트 기호로 OCR된 부분 보정.', occurrence=i)

    # Restore a line assigned to the next item's cell. Both sides are logged.
    add(table(117, 3, 'PROCEDURES'), 'use OEA in both', 'use OEA in both\nmodel transmissions.',
        '30.2 항목의 마지막 줄이 다음 31 항목 셀로 잘못 들어가 있어 원문 위치에 따라 복원.',
        bbox=[230, 465, 425, 496])
    add(table(117, 4, 'PROCEDURES'), 'model transmissions.\n', '',
        '31 항목 앞에 잘못 붙은 30.2 항목의 문장 끝을 원래 셀로 이동. 대응하는 복원 기록과 함께 검증.',
        bbox=[230, 465, 425, 505])

    # Source PDF renders these words without artificial internal spaces.
    spaced = [
        (98, 2, 'INTERVAL', 'B e l t', 'Belt'),
        (98, 2, 'PROCEDURES', 'p u l l e y s .', 'pulleys.'),
        (98, 2, 'PROCEDURES', 'Te n s i o n', 'Tension'),
        (106, 3, 'PROCEDURES', 'e q u i p m e n t .', 'equipment.'),
        (108, 1, 'PROCEDURES', 'l o o s e', 'loose'),
        (108, 1, 'PROCEDURES', '( 2 2-24 N•m )', '(22-24 N•m)'),
        (113, 2, 'PROCEDURES', 'm o n t h s .', 'months.'),
        (115, 1, 'ITEM TO BE INSPECTED', '( M 9 9 6 ,', '(M996,'),
        (116, 1, 'ITEM TO BE INSPECTED', 'Wi n t e r i z a t i o n', 'Winterization'),
        (117, 3, 'ITEM TO BE INSPECTED', 'Tr a n s m i s s i o n', 'Transmission'),
        (117, 4, 'ITEM TO BE INSPECTED', 'Tr a n s m i s s i o n', 'Transmission'),
        (117, 3, 'PROCEDURES', '( 5 . 7 L)', '(5.7 L)'),
        (117, 4, 'PROCEDURES', '( 5 . 7 L)', '(5.7 L)'),
        (117, 4, 'PROCEDURES', 't r a n s m i s s i o n s .', 'transmissions.'),
    ]
    for page, row, field, before, after in spaced:
        rid = table(page, row, field)
        for i in range(byid[rid]['text'].count(before)):
            add(rid, before, after, '원문에서 한 단어/수치인 부분에 추출기가 삽입한 내부 공백 제거. 수치·단위·열 위치는 유지.', occurrence=i)

    # Targeted glyph errors. Source typos such as Teat/currant/Procedureas stay unchanged.
    glyphs = [(49, 'PlATES', 'PLATES'), (86, 'PATlENT', 'PATIENT'),
              (188, 'Air lntake', 'Air Intake'), (192, 'Iift pump', 'lift pump'),
              (198, 'lntake/Exhaust', 'Intake/Exhaust'), (350, 'lf you', 'If you'),
              (352, 'cIip', 'clip'), (398, 'Iooking', 'looking'),
              (510, 'lf the', 'If the'), (528, 'vaIve', 'valve'),
              (563, 'Iinkage', 'linkage'), (569, 'Iines', 'lines'),
              (569, 'lf adding', 'If adding'), (569, 'Ioose', 'loose'),
              (579, 'Iower', 'lower'), (842, 'FlRST', 'FIRST'),
              (844, 'lf offset', 'If offset'), (846, 'lf not', 'If not')]
    for page, before, after in glyphs:
        add(f'P{page:04d}:native', before, after, 'PDF 원문 렌더링을 대조하여 대문자 I·소문자 l의 추출 혼동을 보정.')
    add('P0823:ocr', 'lf you', 'If you', '원문 PDF에서 If로 확인한 OCR 혼동 보정.')
    add('P0823:ocr', 'hamess', 'harness', '원문 PDF에서 harness로 확인한 rn/m OCR 혼동 보정.')
    add('P0531:ocr', 'Ist 2.38 2.63', '1st 2.38 2.63', '원문 기어비 표의 1st가 Ist로 OCR된 부분 보정. 기어비 수치는 유지.')
    rid = 'P0300:ocr'
    before = byid[rid]['text'].split('WIRE TERM. FUNCTION', 1)[1].split('\n\nNOTE', 1)[0]
    before = 'WIRE TERM. FUNCTION' + before
    after = ('WIRE TERM. FUNCTION\nNO. LTR.\n#6 to V - BATTERY\n#7 to P + BATTERY\n'
             '#8 to Y - FIELD COIL\n#10 to W + FIELD COIL\n#11 to Z SENSOR (AC)\n\n'
             'FULL FIELD TEST\n1. Disconnect battery ground cable.')
    add(rid, before, after, '그림 위에 인쇄된 배선 대응표의 문자를 직접 대조해 복원하고 왼쪽 본문과 섞인 읽기 순서 분리. 배선 그림의 연결을 추론한 것이 아님.',
        bbox=[137, 132, 483, 209])

    ledger['batch'] = 'batch-002-whole-manual-review'
    ledger['date'] = '2026-09-22'
    ledger['parent'] = {'path': previous.relative_to(io.ROOT).as_posix(), 'sha256': io.sha(previous), 'preserved_corrections': 51}
    ledger['selection'] = '890쪽 전체 자동 검사 후 PMCS 23쪽 전체 셀, 표 후보 레이아웃, 문자 혼동 후보를 PDF 렌더링과 대조. 평가질의는 읽지 않음.'
    ledger['instructions'] = '추출 오류만 보정. 원문 오탈자·불완전한 문장·단위 모순은 추정 수정하지 않음. 원본과 batch-001 보존.'
    ledger['remaining_review'] = '모든 글자의 무오류 인증이 아님. 원문 결함, 도해 의존 범위, 미검토 OCR 경고와 표의 최종 직렬화는 review-v2 보고서 참조.'
    io.validate_ledger(records, ledger)
    (OUT / 'correction-log.json').write_bytes(io.json_bytes(ledger))
    print(json.dumps({'corrections': len(ledger['corrections']), 'new': len(ledger['corrections']) - 51}, ensure_ascii=False))


if __name__ == '__main__':
    build()
