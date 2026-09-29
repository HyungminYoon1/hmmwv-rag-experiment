"""Apply only PDF-reviewed box transcriptions; keep neighbouring words intact."""
import difflib
import json
from collections import defaultdict
from pathlib import Path
import pymupdf
import correct_extraction as io

WORK=io.BASE/'corpus/reports/rules-v6-work/box-ocr-candidates'


def main(parent=None,out=None,work=None,prefix='V12'):
    parent=parent or io.BASE/'corrections/batch-011/correction-log.json';out=out or io.BASE/'corrections/batch-012'
    work=work or WORK
    if out.exists():raise ValueError('Use a new batch')
    ledger=json.loads(parent.read_text(encoding='utf-8'))
    raw={r['id']:r for r in io.source_records(io.check_inputs(ledger))}
    decisions=json.loads((work/'review-decisions.json').read_text(encoding='utf-8'))['decisions']
    candidates=json.loads((work/'candidates.json').read_text(encoding='utf-8'))
    patches=[];boxes=[];touched=set()
    for c in candidates:
        decision=decisions[c['id']]
        if decision['decision'] not in ('TRANSCRIBE','USE_CANDIDATE'):continue
        pn=c['pdf_page'];rid=f'P{pn:04d}:ocr';words=c['old_words']
        if c['id']=='P0054-B003':
            audit=json.loads((io.BASE/f'ocr-structure-review-20260924/full-audit-e/page-{pn:04d}.json').read_text(encoding='utf-8'))
            box=c['bbox'];words=[w for w in audit['words'] if box[0]<=(w['bbox'][0]+w['bbox'][2])/2<=box[2] and box[1]<=(w['bbox'][1]+w['bbox'][3])/2<=box[3] and w.get('raw_start') is not None]
            words=sorted(words,key=lambda w:(w['bbox'][1],w['bbox'][0]))
        old=[w['text'] for w in words];new=decision['text'].split();values=list(old)
        for tag,a,b,x,y in difflib.SequenceMatcher(a=old,b=new,autojunk=False).get_opcodes():
            if tag=='equal':continue
            if a==b:
                if a:values[a-1]+=' '+' '.join(new[x:y])
                else:values[0]=' '.join(new[x:y])+' '+values[0]
            else:
                values[a]=' '.join(new[x:y])
                for i in range(a+1,b):values[i]=''
        assert ' '.join(v for v in values if v).split()==new,c['id']
        spans=[]
        for i,(w,after) in enumerate(zip(words,values)):
            a,b=w['raw_start'],w['raw_end'];before=raw[rid]['text'][a:b]
            assert before==w['text'],(c['id'],a,b,before,w['text'])
            key=(rid,a,b)
            if key in touched:raise ValueError('Box overlap: '+str(key))
            touched.add(key)
            if before!=after:
                patch={'id':f"FIX-{prefix}-{c['id']}-{i:03d}",'record_id':rid,'pdf_page':pn,
                  'start':a,'end':b,'before':before,'after':after,'bbox':c['bbox'],'render_clip':c['bbox'],
                  'kind':'PDF_BOX_WORD_CORRECTION','reason':'PDF 박스를 직접 대조한 전사문과 일치하도록 이 박스의 단어만 보정했다. 중간의 다른 박스 문자는 변경하지 않았다.',
                  'source_check':'CODEX_PDF_VISUAL_CHECK','human_review':'NOT_PERFORMED',
                  'evidence_crop':'evidence/'+c['id']+'.png','box_review':c['id']}
                patches.append(patch)
            spans.append({'raw_start':a,'raw_end':b,'text':after,'original_bbox':w['bbox']})
        boxes.append({'id':c['id'],'record_id':rid,'pdf_page':pn,'bbox':c['bbox'],
          'literal_text':decision['text'],'word_spans':spans,'decision':decision,'source_image':c['image'],
          'source_image_sha256':c['image_sha256'],'source_check':'CODEX_PDF_VISUAL_CHECK','human_review':'NOT_PERFORMED'})
    ledger['parent']={'path':parent.relative_to(io.ROOT).as_posix(),'sha256':io.sha(parent),'preserved_corrections':len(ledger['corrections'])}
    ledger['corrections']+=patches;ledger.update(batch=out.name+'-reviewed-box-word-corrections',date='2026-09-25')
    io.validate_ledger(list(raw.values()),ledger)
    out.mkdir();(out/'evidence').mkdir()
    for p in ledger['corrections'][:-len(patches)]:
        dest=out/p['evidence_crop']
        if not dest.exists():dest.write_bytes((parent.parent/p['evidence_crop']).read_bytes())
    with pymupdf.open(io.ROOT/ledger['inputs']['pdf']['path']) as doc:
        for p in patches:
            path=out/p['evidence_crop']
            if not path.exists():doc[p['pdf_page']-1].get_pixmap(clip=pymupdf.Rect(p['bbox']),dpi=180,alpha=False).save(path)
            p['evidence_sha256']=io.sha(path)
    (out/'correction-log.json').write_bytes(io.json_bytes(ledger))
    (out/'reviewed-boxes.json').write_bytes(io.json_bytes(boxes))
    print({'new_patches':len(patches),'cumulative':len(ledger['corrections']),'reviewed_boxes':len(boxes)})


if __name__=='__main__':main()
