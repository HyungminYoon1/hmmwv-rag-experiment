"""Apply reviewed remaining alignment errors with an additive raw-source log."""
import copy
import difflib
import pymupdf
import correct_extraction as io
from corpus.common import SourceStore,PACKAGE,read_json,write_json,ROOT


def main():
    s=SourceStore(check=False);parent=ROOT/s.config['correction_ledger']
    ledger=read_json(parent);out=io.BASE/'corrections/batch-014'
    if out.exists():raise ValueError('Use a new correction batch')
    changes=[]
    for d in read_json(PACKAGE/'reports/rules-v6-work/alignment/decisions.json'):
        if d['action']=='CORRECT':changes.append((d['source_refs'][0],d['after'],d['image'],f'A{d["number"]:03d}'))
    extra=[(219,'ocr','er THE FUEL SOLENOID?','AT THE FUEL SOLENOID?'),
      (219,'ocr','a problem with the rotary switch','problem with the rotary switch'),
      (219,'ocr','DISCONNECT WIRE 29A AT THE','DISCONNECT WIRE 29A AT THE ROTARY SWITCH.'),
      (219,'ocr','STEACE-R','STE/ICE-R'),
      (476,'ocr','STEACE-R','STE/ICE-R'),
      (825,'ocr','STEACE-R','STE/ICE-R'),
      (825,'ocr','3 pel. It','3 psi. If'),
      (825,'ocr','1 CONNECT RED TRANSDUCER TO FUEL','1. CONNECT RED TRANSDUCER TO FUEL FILTER.'),
      (825,'ocr','resutt','result'),(825,'ocr','OCA','DCA'),
      (669,'native','pagea. 4-85','para. 4-85')]
    d=read_json(PACKAGE/'reports/rules-v6-work/alignment/decisions.json')[114]
    changes.append((d['source_refs'][1],'para 7-15',d['image'],'N114'))
    for i,(pn,layer,before,after) in enumerate(extra):
        rid=f'P{pn:04d}:{layer}';text=s.records[rid]['text'];assert text.count(before)==1,(pn,before)
        a=text.index(before);ref=s.ref(rid,a,a+len(before))
        image=PACKAGE/f'reports/rules-v6-work/profile-images/p{pn:04d}.png'
        if not image.exists():
            with pymupdf.open(ROOT/s.config['source_pdf']) as doc:doc[pn-1].get_pixmap(dpi=144).save(image)
        changes.append((ref,after,image.relative_to(ROOT).as_posix(),f'E{i:03d}'))
    patches=[]
    for ref,after,image,key in changes:
        rid=ref['record_id'];before=ref['text']
        for j,(tag,a,b,x,y) in enumerate(difflib.SequenceMatcher(a=before,b=after,autojunk=False).get_opcodes()):
            if tag=='equal':continue
            # An insertion uses one unchanged neighbouring character as the
            # anchor. This preserves the correction format's nonempty range.
            if a==b:
                if a:a-=1;x-=1
                else:b+=1;y+=1
            cs,ce=ref['start']+a,ref['start']+b
            run=next((r for r in s.runs[rid] if r[0]<=cs<ce<=r[1] and r[4] is None),None)
            if run is None:raise ValueError(('Existing patch overlap',key,cs,ce,before[a:b]))
            rs,re=run[2]+cs-run[0],run[2]+ce-run[0]
            patches.append({'id':f'FIX-V14-{key}-{j:03d}','record_id':rid,'pdf_page':ref['pdf_page'],
              'start':rs,'end':re,'before':before[a:b],'after':after[x:y],
              'bbox':ref['bbox'],'render_clip':ref['bbox'],'kind':'PDF_TEXT_EXTRACTION_CORRECTION',
              'reason':'PDF 원문 대조로 확인한 문자 오독·누락·그림 선 혼입을 보정했다. 새 정비 해석을 생성하지 않았다.',
              'source_check':'CODEX_PDF_VISUAL_CHECK','human_review':'NOT_PERFORMED',
              'evidence_crop':'evidence/V14-'+key+'.png','review_image':image})
    # Adjacent insertion anchors can overlap another edit within the same raw
    # line. Merge only those local recorded edits by replaying their diff.
    raw={r['id']:r for r in io.source_records(io.check_inputs(ledger))}
    ledger['parent']={'path':parent.relative_to(ROOT).as_posix(),'sha256':io.sha(parent),'preserved_corrections':len(ledger['corrections'])}
    ledger['corrections']+=patches;ledger.update(batch='batch-014-reviewed-alignment-errors',date='2026-09-25')
    io.validate_ledger(list(raw.values()),ledger)
    out.mkdir();(out/'evidence').mkdir()
    with pymupdf.open(ROOT/s.config['source_pdf']) as doc:
        for p in ledger['corrections']:
            dest=out/p['evidence_crop']
            if not dest.exists():
                if p in patches:
                    doc[p['pdf_page']-1].get_pixmap(clip=pymupdf.Rect(p['render_clip']),dpi=180,alpha=False).save(dest)
                else:dest.write_bytes((parent.parent/p['evidence_crop']).read_bytes())
            p['evidence_sha256']=io.sha(dest)
    (out/'correction-log.json').write_bytes(io.json_bytes(ledger))
    write_json(out/'reviewed-boxes.json',[])
    write_json(out/'changes.json',[{'source':r,'after':after,'image':img,'key':key} for r,after,img,key in changes])
    print({'new_patches':len(patches),'total_patches':len(ledger['corrections']),'reviewed_changes':len(changes)})


if __name__=='__main__':main()
