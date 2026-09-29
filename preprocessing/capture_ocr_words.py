"""Capture word-coordinate evidence using the pinned OCR engine, without adoption.

This output is an alternative extraction sidecar. It never changes the frozen
OCR snapshot, corrected text, corpus, or review decisions.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
import pymupdf
from corpus.common import BASE, ROOT, read_json, read_jsonl, write_json, sha


def capture(pages, output):
    output = Path(output).resolve()
    if output.exists() or not output.is_relative_to(ROOT):
        raise ValueError('Use a new output directory inside the project')
    output.mkdir(parents=True)
    config = read_json(BASE/'config.json')
    pdf_path = (BASE/config['input']).resolve()
    data = BASE/config['ocr']['data']
    assert sha(pdf_path) == config['input_sha256']
    assert sha(data) == config['ocr']['data_sha256']
    old = {p['pdf_page']:p for p in read_jsonl(BASE/'assets/ocr-full-manual-v2/pages.jsonl')}
    results = []
    with pymupdf.open(pdf_path) as pdf:
        for n,pn in enumerate(pages):
            page = pdf[pn-1]
            pix = page.get_pixmap(dpi=300,colorspace=pymupdf.csRGB,alpha=False)
            raster = hashlib.sha256(pix.samples).hexdigest()
            # Only a disposable input image; completed results contain its hash.
            image = output/'ocr-input.png'; pix.save(image)
            # Tesseract's Windows file API needs ASCII relative asset paths.
            cmd = [sys.executable,'-X','utf8',str(BASE/'ocr_worker.py'),
                   image.relative_to(ROOT).as_posix(),data.parent.relative_to(ROOT).as_posix(),
                   '--dpi','300','--width',str(page.rect.width),'--include-words']
            process = subprocess.run(cmd,check=False,capture_output=True,text=True,encoding='utf-8',cwd=ROOT,
                                     timeout=120,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if process.returncode:
                raise RuntimeError(f'OCR failed on page {pn}: {process.stderr}')
            payload = json.loads(process.stdout)
            legacy = [{k:v for k,v in line.items() if k!='words'} for line in payload['lines']]
            same = pn in old and legacy == old[pn]['lines']
            record = {'schema':1,'pdf_page':pn,'page_rect':list(page.rect),'dpi':300,'psm':3,
                      'raster_sha256':raster,'raster_matches_frozen':pn in old and raster==old[pn]['raster_sha256'],
                      'legacy_lines_exactly_match':same,'lines':payload['lines'],'raw_text':payload['text'],
                      'stderr':process.stderr,'adopted':False}
            write_json(output/f'page-{pn:04d}.json',record)
            results.append({k:record[k] for k in ('pdf_page','raster_matches_frozen','legacy_lines_exactly_match')})
            if n%10==0 or n+1==len(pages):
                print(json.dumps({'done':n+1,'total':len(pages),'page':pn,'exact_match':same}),flush=True)
    image.unlink()  # Exact file created above inside the new output directory.
    write_json(output/'manifest.json',{'schema':1,'source_pdf':pdf_path.relative_to(ROOT).as_posix(),
        'pdf_sha256':sha(pdf_path),'traineddata_sha256':sha(data),'worker_sha256':sha(BASE/'ocr_worker.py'),
        'capture_sha256':sha(__file__),'pages':results,'llm_invoked':False,'adopted':False,
        'files':{p.name:sha(p) for p in sorted(output.glob('page-*.json'))}})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pages',required=True,help='Comma-separated pages or cross for current OCR cross-region pages')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.pages=='cross':
        queue=read_jsonl(BASE/'output/corpus-v3-rules-c/review_queue.jsonl')
        pages=sorted({r['pdf_page'] for r in queue if r['code']=='CROSS_REGION_TEXT'
                      and any(s['layer']=='ocr' for s in r['source_refs'])})
    else:pages=sorted({int(p) for p in args.pages.split(',')})
    capture(pages,args.output)
