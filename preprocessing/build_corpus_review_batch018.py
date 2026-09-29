"""Repair final sampled column failures; retain superseded intermediate patches."""
import pymupdf
import correct_extraction as io
from corpus.common import *
from corpus.late_exception_pages_v6 import PAGES


def main():
    s=SourceStore(check=False);parent=ROOT/s.config['correction_ledger'];ledger=read_json(parent)
    out=BASE/'corrections/batch-018'
    if out.exists():raise ValueError('Use a new batch')
    out.mkdir();(out/'evidence').mkdir()
    superseded=[p for p in ledger['corrections'] if p['record_id'] in {f'P{pn:04d}:ocr' for pn in PAGES}]
    assert all(p['id'].startswith(('FIX-V12-','FIX-V14-')) for p in superseded)
    ledger['corrections']=[p for p in ledger['corrections'] if p not in superseded]
    for p in ledger['corrections']:
        dest=out/p['evidence_crop']
        if not dest.exists():dest.write_bytes((parent.parent/p['evidence_crop']).read_bytes())
    regions=[];nodes=[]
    with pymupdf.open(ROOT/s.config['source_pdf']) as pdf:
        def patch(pn,start,end,after,name,clip):
            rid=f'P{pn:04d}:ocr';image=out/f'evidence/{name}.png'
            pdf[pn-1].get_pixmap(clip=pymupdf.Rect(clip),dpi=180,alpha=False).save(image)
            ledger['corrections'].append({'id':'FIX-'+name,'record_id':rid,'pdf_page':pn,'start':start,'end':end,
              'before':s.before[rid]['text'][start:end],'after':after,'bbox':clip,'render_clip':clip,
              'kind':'PDF_REGION_TRANSCRIPTION','reason':'최종 PDF 대조에서 확인한 문장 혼합·조건 오독을 원문의 박스별 문구로 복원했다.',
              'source_check':'CODEX_PDF_VISUAL_CHECK','human_review':'NOT_PERFORMED',
              'evidence_crop':image.relative_to(out).as_posix(),'evidence_sha256':sha(image)})
        for pn,(title,entries,inlet,outlet) in PAGES.items():
            parts=[];pos=0
            def add(name,text,box,role):
                nonlocal pos
                if not text:return None
                r={'name':name,'record_id':f'P{pn:04d}:ocr','pdf_page':pn,'start':pos,'end':pos+len(text),'text':text,'bbox':box,'role':role}
                regions.append(r);parts.append(text);pos+=len(text)+2;return r
            heading=add('title',title,[25,72,198,125],'heading');add('layout','DIAGNOSTIC FLOWCHART',[380,75,565,108],'heading')
            add('inlet',inlet,[210,80,325,140],'navigation')
            for step,top,bottom,known,possible,q,options,reason,action in entries:
                context=[heading,add(step+'-id',step,[155,top,212,top+20],'step')]
                for name,value,y0,y1 in [('known',known,top,top+(bottom-top)/2),('possible',possible,top+(bottom-top)/2,bottom)]:
                    # H3 has a printed empty POSSIBLE PROBLEMS header.
                    if value or (pn==390 and step=='H3' and name=='possible'):
                        context.append(add(step+'-'+name,('KNOWN INFO' if name=='known' else 'POSSIBLE PROBLEMS')+ ('\n'+value if value else ''),[30,y0,168,y1],'condition'))
                body=[add(step+'-question',q,[158,top+12,372,bottom-33],'question')]
                if options:body.append(add(step+'-options','TEST OPTIONS\n'+options,[335,top,525,top+(bottom-top)/2],'options'))
                if reason:body.append(add(step+'-reason','REASON FOR QUESTION\n'+reason,[340,top+(bottom-top)/2,525,bottom],'reason'))
                node={'pdf_page':pn,'step':step,'context':context,'body':body}
                if action:
                    node['no']=add(step+'-no','NO',[195,bottom-38,245,bottom],'branch')
                    node['action']=add(step+'-action',action,[235,bottom-38,385,bottom+10],'action')
                    add(step+'-yes','YES',[160,bottom-12,210,bottom+17],'navigation')
                nodes.append(node)
            add('exit',outlet,[145,710,280,755],'navigation')
            patch(pn,0,len(s.before[f'P{pn:04d}:ocr']['text']),'\n\n'.join(parts),f'V18-P{pn:04d}',list(pdf[pn-1].rect))
        raw=s.before['P0619:ocr']['text']
        for before,after,clip,name in [('STEACE-R','STE/ICE-R',[360,160,567,194],'title'),('Repair tead','Repair lead',[140,590,270,619],'repair')]:
            a=raw.index(before);patch(619,a,a+len(before),after,f'V18-P0619-{name}',clip)
    ledger.update(batch='batch-018-final-artifact-source-check',date='2026-09-25',parent={'path':parent.relative_to(ROOT).as_posix(),'sha256':sha(parent),'superseded_ids':[p['id'] for p in superseded]})
    io.validate_ledger(io.source_records(io.check_inputs(ledger)),ledger)
    write_json(out/'correction-log.json',ledger);write_json(out/'regions.json',regions);write_json(out/'nodes.json',nodes);write_json(out/'superseded-corrections.json',superseded)
    print({'superseded_intermediate':len(superseded),'new_patches':6,'active':len(ledger['corrections'])})


if __name__=='__main__':main()
