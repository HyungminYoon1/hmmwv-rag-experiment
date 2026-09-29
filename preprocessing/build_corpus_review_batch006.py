"""Extend batch 005 with visually confirmed symbol repairs found during QA."""
import json
import pymupdf
import correct_extraction as io


def main():
    parent=io.BASE/'corrections/batch-005/correction-log.json'
    out=io.BASE/'corrections/batch-006'
    if out.exists():raise ValueError('Use a new frozen batch')
    ledger=json.loads(parent.read_text(encoding='utf-8'))
    records={r['id']:r for r in io.source_records(io.check_inputs(ledger))}
    added=[]
    cases=[('P0097-T2_1-R01:PROCEDURES','(QD)','Ⓓ',[225,155,412,199]),
           ('P0097:ocr','“ Oy','“Ⓓ”',[225,155,412,199]),
           ('P0849:native','G Continuity checks','• Continuity checks',[94,374,214,392]),
           ('P0849:native','G Resistance measurements','• Resistance measurements',[94,385,224,403]),
           ('P0849:native','G Switch and relay functions','• Switch and relay functions',[94,397,224,415])]
    for rid,before,after,box in cases:
        text=records[rid]['text'];assert text.count(before)==1
        a=text.index(before)
        added.append({'id':f'FIX-V6-{len(added)+1:04d}','record_id':rid,'pdf_page':records[rid]['pdf_page'],
            'start':a,'end':a+len(before),'before':before,'after':after,'bbox':box,'render_clip':box,
            'reason':'원문 PDF에서 확인한 원형 D를 Ⓓ로 통일하여 복원했다.' if records[rid]['pdf_page']==97 else
                     'native 문자층에서 G로 추출된 글머리표를 화면에 보이는 원형 글머리표 •로 복원했다.',
            'kind':'SYMBOL_EXTRACTION_CORRECTION','source_check':'CODEX_PDF_VISUAL_CHECK','human_review':'NOT_PERFORMED'})
    out.mkdir(parents=True);(out/'evidence').mkdir()
    for p in ledger['corrections']:
        (out/p['evidence_crop']).write_bytes((parent.parent/p['evidence_crop']).read_bytes())
    with pymupdf.open(io.ROOT/ledger['inputs']['pdf']['path']) as pdf:
        for p in added:
            rel=f"evidence/{p['id']}.png"
            pdf[p['pdf_page']-1].get_pixmap(clip=pymupdf.Rect(p['render_clip']),dpi=180,alpha=False).save(out/rel)
            p.update(evidence_crop=rel,evidence_sha256=io.sha(out/rel))
    ledger['parent']={'path':parent.relative_to(io.ROOT).as_posix(),'sha256':io.sha(parent),'preserved_corrections':len(ledger['corrections'])}
    ledger['corrections']+=added;ledger['batch']='batch-006-symbol-review';ledger['date']='2026-09-24'
    ledger['additional_symbol_review']={'date':'2026-09-24','pages':[97,849],'evaluation_questions_read':False}
    io.validate_ledger(list(records.values()),ledger)
    (out/'correction-log.json').write_bytes(io.json_bytes(ledger))
    print(json.dumps({'added':len(added),'cumulative':len(ledger['corrections'])}))


if __name__=='__main__':main()
