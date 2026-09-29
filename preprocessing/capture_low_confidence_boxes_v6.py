"""Capture local OCR alternatives for review; never adopt candidates here."""
from concurrent.futures import ThreadPoolExecutor
import json
import subprocess
import sys
import pymupdf
from corpus.common import SourceStore,ROOT,BASE,PACKAGE,read_json,write_json,sha


def main():
    s=SourceStore(check=False);cfg=read_json(BASE/'config.json')
    out=PACKAGE/'reports/rules-v6-work/box-ocr-candidates'
    out.mkdir(exist_ok=False);candidates=[]
    with pymupdf.open(ROOT/s.config['source_pdf']) as doc:
        for path in sorted((BASE/'ocr-structure-review-20260924/full-audit-e').glob('page-*.json')):
            audit=read_json(path);pn=audit['summary']['pdf_page'];rid=f'P{pn:04d}:ocr'
            if len(s.records[f'P{pn:04d}:native']['text'])>.35*len(s.records[rid]['text']):continue
            if any(p['end']-p['start']>100 for p in s.patches[rid]):continue
            for r in audit['rectangles']:
                n=sum(len(w['text']) for w in r['words'])
                if n<30:continue
                score=sum(w['confidence']*len(w['text']) for w in r['words'])/n
                if score>=85:continue
                name=f'P{pn:04d}-{r["id"]}';box=pymupdf.Rect(r['bbox'])+(2,2,-2,-2)
                pix=doc[pn-1].get_pixmap(clip=box,dpi=300,colorspace=pymupdf.csRGB,alpha=False)
                origin=[pix.x*72/300-20*72/300,pix.y*72/300-20*72/300]
                padded=pymupdf.Pixmap(pymupdf.csRGB,pymupdf.IRect(0,0,pix.width+40,pix.height+40),False)
                padded.clear_with(255);pix.set_origin(20,20);padded.copy(pix,pix.irect);padded.set_dpi(300,300)
                image=out/(name+'.png');padded.save(image)
                candidates.append({'id':name,'pdf_page':pn,'rectangle':r['id'],'bbox':r['bbox'],
                    'old_score':round(score,3),'old_text':r['text'],'old_words':r['words'],
                    'image':image.relative_to(ROOT).as_posix(),'image_sha256':sha(image),'origin':origin,
                    'status':'NOT_ADOPTED','source_audit':path.relative_to(ROOT).as_posix()})
    write_json(out/'candidates.json',candidates)
    def run(c):
        cmd=[sys.executable,'-X','utf8',str(BASE/'ocr_worker.py'),c['image'],
             (BASE/cfg['ocr']['data']).parent.relative_to(ROOT).as_posix(),'--psm','6','--dpi','300','--include-words']
        r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
        if r.returncode:raise RuntimeError(r.stderr)
        result=json.loads(r.stdout);write_json(out/(c['id']+'.json'),result)
        return c['id']
    with ThreadPoolExecutor(max_workers=3) as pool:
        for i,name in enumerate(pool.map(run,candidates),1):
            if i%25==0:print({'completed':i,'total':len(candidates)},flush=True)
    write_json(out/'manifest.json',{'pdf_sha256':sha(ROOT/s.config['source_pdf']),
        'worker_sha256':sha(BASE/'ocr_worker.py'),'capture_sha256':sha(__file__),
        'traineddata_sha256':sha(BASE/cfg['ocr']['data']),'dpi':300,'psm':6,'llm_invoked':False,
        'files':{p.name:sha(p) for p in sorted(out.glob('*'))},'adopted_automatically':False})
    print({'candidates':len(candidates),'pages':len({r['pdf_page'] for r in candidates}),'adopted':False})

if __name__=='__main__':main()
