"""Freeze the image-table transcription verified against PDF page 856."""
import json
import pymupdf
import correct_extraction as io

TABLE = '''ITEM NO. | TK NO. | PART NO. | QTY | ITEM
1 | 10 | 11669227 | 1 | Hose and fitting assy (spark plug adapter)
2 | 11 | 12258878 | 1 | Current probe
3 | 12 | 12258853-1 | 1 | Pipe thread reducer, 3/4 MPT to 1/4 FPT
4 | 13 | 12258853-3 | 1 | Pipe thread reducer, 1/2 MPT to 1/4 FPT
5 | 14 | 12258853-2 | 2 | Pipe thread reducer, 3/8 MPT to 1/4 FPT
6 | 15 | 444620 | 1 | Hex head plug, 1/4 MPT
7 | 16 | 5327970 | 1 | Hex head plug, 1/8 MPT
8 | 17 | 12258876 | 1 | Pressure transducer, 0-1000 psig
9 | 21 | 12258881 | 1 | Snubber
10 | 20 | 3204X2 | 2 | Adapter, 1/8 MPT to 1/4 FPT
11 | 19 | 3304X2 | 1 | Coupling reducer, 1/8 FPT to 1/4 FPT
12 | 18 | 234X5 | 1 | Male connector, 5/16 tube to 1/4 MPT
13 | 22 | 12258877 | 1 | Pressure transducer, -30 in. Hg to 25 psig
14 | 23 | 444152 | 1 | Street tee, 1/2 pipe thread
15 | 24 | 3750X4 | 1 | Street tee, 1/4 pipe thread
16 | 25 | 547002 | 1 | Street tee, 1/8 pipe thread
17 | 26 | 12258879-2 | 1 | Street elbow, 1/4 pipe thread
18 | 27 | 12258879-1 | 1 | Street elbow, 1/8 pipe thread
19 | 34 | 12258875 | 1 | Pulse tachometer
20 | 32 | 12258880 | 1 | Fuel line adapter
21 | 31 | MS53099-2 | 1 | Tachometer drive adapter
22 | 30 | 7540877 | 1 | Ignition adapter
23 | 29 | MS3119E14-19 | 1 | Adapter (connector-to-connector)
24 | 28 | 12258762 | 1 | Tee, inverted flare
25 | 33 | 8840543 | 1 | Air chuck
26 | 35 | 11669236 | 1 | Hose assembly, 1/8 MPT
27 | 36 | 12258852 | 1 | Pipe nipple, 1/8 MPT'''


def build():
    parent = io.BASE / 'corrections/batch-002/correction-log.json'
    out = io.BASE / 'corrections/batch-003'
    if out.exists():
        raise ValueError('Frozen batch already exists')
    ledger = json.loads(parent.read_text(encoding='utf-8'))
    records = io.source_records(io.check_inputs(ledger))
    rec = next(r for r in records if r['id'] == 'P0856:ocr')
    start = rec['text'].index('TEM—(isK')
    out.mkdir(parents=True)
    for p in ledger['corrections']:
        dest = out / p['evidence_crop']; dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((parent.parent / p['evidence_crop']).read_bytes())
    clip = [100,390,575,742]
    crop = 'evidence/FIX-0110.png'
    with pymupdf.open(io.ROOT / ledger['inputs']['pdf']['path']) as pdf:
        pdf[855].get_pixmap(dpi=180, alpha=False, clip=pymupdf.Rect(clip)).save(out / crop)
    ledger['corrections'].append({'id': 'FIX-0110', 'record_id': rec['id'], 'pdf_page': 856,
        'start': start, 'end': len(rec['text']), 'before': rec['text'][start:], 'after': TABLE,
        'bbox': clip, 'render_clip': clip,
        'reason': '원문 이미지의 Table 2-4를 27행 5열로 직접 대조 전사. OCR에서 사라지거나 섞인 ITEM NO/TK NO/QTY, 품번 및 분수를 복원. |는 열 구분자이며 새 정보가 아니다. 요약·번역·수치 환산은 하지 않음.',
        'source_check': 'CODEX_PDF_VISUAL_CHECK', 'human_review': 'NOT_PERFORMED',
        'evidence_crop': crop, 'evidence_sha256': io.sha(out / crop)})
    ledger['batch'] = 'batch-003-whole-manual-review-image-table'
    ledger['parent'] = {'path': parent.relative_to(io.ROOT).as_posix(), 'sha256': io.sha(parent), 'preserved_corrections': 109}
    io.validate_ledger(records, ledger)
    assert len(TABLE.splitlines()) == 28
    assert [int(s.split(' | ')[0]) for s in TABLE.splitlines()[1:]] == list(range(1,28))
    assert all(len(s.split(' | ')) == 5 for s in TABLE.splitlines())
    (out / 'correction-log.json').write_bytes(io.json_bytes(ledger))
    print(json.dumps({'corrections': len(ledger['corrections']), 'table_rows_restored': 27}))


if __name__ == '__main__':
    build()
