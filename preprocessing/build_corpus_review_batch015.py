"""Re-transcribe failed page examples; retain explicit supersession history."""
import shutil
import pymupdf
import correct_extraction as io
from corpus.common import *
from corpus.exception_pages_v6 import PAGES


def main():
    s=SourceStore(check=False);parent=ROOT/s.config['correction_ledger'];ledger=read_json(parent)
    out=BASE/'corrections/batch-015'
    if out.exists():raise ValueError('Use a new batch')
    regions=[];page_text={};nodes=[]
    for pn,(title,entries,inlet,outlet) in PAGES.items():
        parts=[];pos=0
        def add(name,value,box,role):
            nonlocal pos
            r={'name':name,'record_id':f'P{pn:04d}:ocr','pdf_page':pn,'start':pos,'end':pos+len(value),
               'text':value,'bbox':box,'role':role}
            regions.append(r);parts.append(value);pos+=len(value)+2
            return r
        title_ref=add('title',title,[25,72,195,125],'heading')
        add('layout','DIAGNOSTIC FLOWCHART',[380,75,565,108],'heading')
        add('inlet',inlet,[210,80,325,140],'navigation')
        for step,top,bottom,known,possible,question,options,reason,action in entries:
            ident=add(step+'-id',step,[155,top,212,top+20],'step')
            contexts=[title_ref,ident]
            if known:contexts.append(add(step+'-known','KNOWN INFO\n'+known,[30,top,168,top+(bottom-top)/2],'condition'))
            if possible:contexts.append(add(step+'-possible','POSSIBLE PROBLEMS\n'+possible,[30,top+(bottom-top)/2,168,bottom],'condition'))
            q=add(step+'-question',question,[158,top+12,372,bottom-33],'question')
            opts=add(step+'-options','TEST OPTIONS\n'+options,[330,top,522,top+(bottom-top)/2],'options')
            why=add(step+'-reason','REASON FOR QUESTION\n'+reason,[340,top+(bottom-top)/2,522,bottom],'reason')
            no=add(step+'-no','NO',[195,bottom-38,245,bottom],'branch')
            act=add(step+'-action',action,[235,bottom-38,385,bottom+10],'action')
            yes=add(step+'-yes','YES',[160,bottom-12,210,bottom+17],'branch')
            nodes.append({'pdf_page':pn,'step':step,'context':contexts,'question':q,'options':opts,'reason':why,'no':no,'action':act,'yes':yes})
        add('exit',outlet,[145,715,250,755],'navigation')
        page_text[pn]='\n\n'.join(parts)
    superseded=[p for p in ledger['corrections'] if p['record_id'] in {f'P{pn:04d}:ocr' for pn in PAGES}]
    assert all(p['id'].startswith('FIX-V12-') for p in superseded), 'Do not silently supersede baseline corrections'
    ledger['corrections']=[p for p in ledger['corrections'] if p not in superseded]
    ledger['parent']={'path':parent.relative_to(ROOT).as_posix(),'sha256':sha(parent),'superseded_ids':[p['id'] for p in superseded]}
    out.mkdir();(out/'evidence').mkdir()
    for p in ledger['corrections']:
        dest=out/p['evidence_crop']
        if not dest.exists():dest.write_bytes((parent.parent/p['evidence_crop']).read_bytes())
    with pymupdf.open(ROOT/s.config['source_pdf']) as pdf:
        for pn,after in page_text.items():
            rid=f'P{pn:04d}:ocr';box=list(pdf[pn-1].rect);img=out/f'evidence/V15-P{pn:04d}.png'
            pdf[pn-1].get_pixmap(dpi=180,alpha=False).save(img)
            ledger['corrections'].append({'id':f'FIX-V15-P{pn:04d}','record_id':rid,'pdf_page':pn,
              'start':0,'end':len(s.before[rid]['text']),'before':s.before[rid]['text'],'after':after,
              'bbox':box,'render_clip':box,'kind':'PDF_PAGE_REGION_TRANSCRIPTION',
              'reason':'표본 재대조에서 OCR 누락과 문자 혼합을 확인하여 모든 질문·조건·시험·분기 문자를 PDF에서 영역별로 다시 전사했다. 기존 v12 부분 보정은 별도 이력으로 대체했다.',
              'source_check':'CODEX_PDF_VISUAL_CHECK','human_review':'NOT_PERFORMED',
              'evidence_crop':img.relative_to(out).as_posix(),'evidence_sha256':sha(img)})
    ledger.update(batch='batch-015-source-checked-exception-pages',date='2026-09-25')
    io.validate_ledger(io.source_records(io.check_inputs(ledger)),ledger)
    write_json(out/'correction-log.json',ledger);write_json(out/'superseded-corrections.json',superseded)
    write_json(out/'regions.json',regions);write_json(out/'nodes.json',nodes)
    print({'superseded_v12':len(superseded),'new_page_corrections':len(PAGES),'active_corrections':len(ledger['corrections']),'nodes':len(nodes)})


if __name__=='__main__':main()
