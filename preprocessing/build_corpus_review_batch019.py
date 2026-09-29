"""Record source transcriptions after checking condition-panel ends."""
import pymupdf
import correct_extraction as io
from corpus.common import *
from corpus.end_panel_pages_v6 import PAGES


def main():
    s=SourceStore(check=False);parent=ROOT/s.config['correction_ledger'];ledger=read_json(parent)
    out=BASE/'corrections/batch-019'
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
        for pn,(title,entries,inlet,outlet) in PAGES.items():
            parts=[];pos=0
            def add(name,text,box,role):
                nonlocal pos
                r={'name':name,'record_id':f'P{pn:04d}:ocr','pdf_page':pn,'start':pos,'end':pos+len(text),'text':text,'bbox':box,'role':role}
                regions.append(r);parts.append(text);pos+=len(text)+2;return r
            heading=add('title',title,[25,62,205,115],'heading')
            add('layout','DIAGNOSTIC FLOWCHART',[380,65,565,108],'heading')
            add('inlet',inlet,[200,70,340,128],'navigation')
            for step,top,bottom,known,possible,q,options,reason,action in entries:
                context=[heading,add(step+'-id',step,[155,top,212,top+20],'step')]
                context.append(add(step+'-known','KNOWN INFO\n'+known,[30,top,168,top+(bottom-top)/2],'condition'))
                context.append(add(step+'-possible','POSSIBLE PROBLEMS\n'+possible,[30,top+(bottom-top)/2,168,bottom],'condition'))
                body=[add(step+'-question',q,[158,top+12,372,bottom-33],'question'),
                      add(step+'-options','TEST OPTIONS\n'+options,[335,top,525,top+(bottom-top)/2],'options'),
                      add(step+'-reason','REASON FOR QUESTION\n'+reason,[340,top+(bottom-top)/2,525,bottom],'reason')]
                no=add(step+'-no','NO',[195,bottom-38,245,bottom],'branch')
                act=add(step+'-action',action,[235,bottom-38,385,bottom+10],'action')
                if (pn,step)!=(201,'D6'):add(step+'-yes','YES',[160,bottom-12,210,bottom+17],'navigation')
                nodes.append({'pdf_page':pn,'step':step,'context':context,'body':body,'no':no,'action':act})
            add('exit',outlet,[125,685,285,746] if pn==201 else [125,510 if pn==479 else 702,285,752],
                'flow_annotation' if pn==201 else 'navigation')
            image=out/f'evidence/V19-P{pn:04d}.png';clip=list(pdf[pn-1].rect)
            pdf[pn-1].get_pixmap(clip=pymupdf.Rect(clip),dpi=180,alpha=False).save(image)
            raw=s.before[f'P{pn:04d}:ocr']['text']
            ledger['corrections'].append({'id':f'FIX-V19-P{pn:04d}','record_id':f'P{pn:04d}:ocr','pdf_page':pn,
              'start':0,'end':len(raw),'before':raw,'after':'\n\n'.join(parts),'bbox':clip,'render_clip':clip,
              'kind':'PDF_REGION_TRANSCRIPTION','reason':'조건 박스 하단 검토에서 발견한 누락·혼합·오독을 원문의 박스별 문구로 복원. 원문 오기는 보존.',
              'source_check':'CODEX_PDF_VISUAL_CHECK','human_review':'NOT_PERFORMED',
              'evidence_crop':image.relative_to(out).as_posix(),'evidence_sha256':sha(image)})
    ledger.update(batch='batch-019-condition-panel-end-check',date='2026-09-25',
                  parent={'path':parent.relative_to(ROOT).as_posix(),'sha256':sha(parent),'superseded_ids':[p['id'] for p in superseded]})
    io.validate_ledger(io.source_records(io.check_inputs(ledger)),ledger)
    for name,value in [('correction-log',ledger),('regions',regions),('nodes',nodes),('superseded-corrections',superseded)]:write_json(out/f'{name}.json',value)
    print({'superseded_intermediate':len(superseded),'new_patches':len(PAGES),'active':len(ledger['corrections'])})


if __name__=='__main__':main()
