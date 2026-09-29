"""Render all in-scope OCR PDF pages as overview sheets (not proofreading)."""
from pathlib import Path
import argparse
import pymupdf
from corpus.common import SourceStore, ROOT, write_json, sha


def main(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    store=SourceStore();pdf=pymupdf.open(ROOT/store.config['source_pdf'])
    pages=sorted(r['pdf_page'] for r in store.records.values() if r['layer']=='ocr' and r['in_scope'])
    manifest=[]
    for start in range(0,len(pages),16):
        batch=pages[start:start+16];doc=pymupdf.open();page=doc.new_page(width=960,height=1300)
        for n,pn in enumerate(batch):
            x=(n%4)*240;y=(n//4)*325
            page.insert_text((x+7,y+15),f'PDF {pn}',fontsize=11)
            pix=pdf[pn-1].get_pixmap(dpi=32,alpha=False)
            page.insert_image(pymupdf.Rect(x+3,y+19,x+237,y+322),stream=pix.tobytes('png'))
        path=output/f'sheet-{start//16+1:02d}.png'
        page.get_pixmap(dpi=72,alpha=False).save(path);doc.close()
        manifest.append({'file':path.name,'pages':batch,'sha256':sha(path)})
    write_json(output/'manifest.json',{'source_pdf_sha256':sha(ROOT/store.config['source_pdf']),
        'review_scope':'LAYOUT_OVERVIEW_ONLY_NOT_TEXT_PROOFREADING','pages':pages,'sheets':manifest})
    print({'pages':len(pages),'sheets':len(manifest)})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    main(parser.parse_args().output)
