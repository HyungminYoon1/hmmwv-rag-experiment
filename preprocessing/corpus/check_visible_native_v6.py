"""Find native source lines with no visible ink in the authoritative PDF."""
import math
import pymupdf
from .common import SourceStore,ROOT,PACKAGE,write_json


def main():
    s=SourceStore(check=False);out=PACKAGE/s.config['rules_path']/'native-visibility.json'
    if out.exists():raise ValueError('Preserve earlier visibility evidence')
    empty=[];count=0;translation=bytes(1 if i<180 else 0 for i in range(256))
    with pymupdf.open(ROOT/s.config['source_pdf']) as doc:
        for pn,page in s.pages.items():
            if not page['in_scope']:continue
            pix=doc[pn-1].get_pixmap(dpi=144,colorspace=pymupdf.csGRAY,alpha=False)
            data=pix.samples_mv;stride=pix.stride;rid=f'P{pn:04d}:native'
            for a,b,box,_,_ in s.lines[rid]:
                raw=s.before[rid]['text'][a:b]
                if not raw.strip():continue
                x0,y0,x1,y1=box
                xa=max(0,math.floor(x0*2));xb=min(pix.width,math.ceil(x1*2))
                ya=max(0,math.floor(y0*2));yb=min(pix.height,math.ceil(y1*2))
                if xb<=xa or yb<=ya:continue
                ink=sum(bytes(data[y*stride+xa:y*stride+xb]).translate(translation).count(1) for y in range(ya,yb))
                count+=1
                if ink==0:empty.append({'record_id':rid,'pdf_page':pn,'raw_start':a,'raw_end':b,
                        'raw_text':raw,'bbox':box,'ink_pixels':0,'pixel_count':(xb-xa)*(yb-ya)})
    write_json(out,{'source_pdf':s.config['source_pdf'],'dpi':144,'ink_threshold':180,
                    'lines_checked':count,'invisible_candidates':empty,'automatic_source_text_edit':False})
    print({'lines_checked':count,'zero_ink_lines':len(empty),'pages':sorted({r['pdf_page'] for r in empty})})

if __name__=='__main__':main()
