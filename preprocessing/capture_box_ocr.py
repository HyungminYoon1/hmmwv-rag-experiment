"""Save per-box OCR alternatives for comparison with the reviewed transcription."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import pymupdf
from corpus.common import ROOT,BASE,read_json,write_json,sha


def capture(output):
    output=Path(output).resolve()
    if output.exists() or not output.is_relative_to(ROOT):raise ValueError('Use a new project folder')
    output.mkdir(parents=True)
    cfg=read_json(BASE/'config.json');pdf_path=(BASE/cfg['input']).resolve()
    data=BASE/cfg['ocr']['data'];assert sha(data)==cfg['ocr']['data_sha256']
    assert sha(pdf_path)==cfg['input_sha256']
    captures=[]
    with pymupdf.open(pdf_path) as pdf:
        for pn in [217,262,289]:
            for name,box,reviewed in read_json(BASE/f'corrections/batch-007/page-{pn}-regions.json'):
                if name.rsplit('-',1)[-1] not in ('known','possible','question','options','reason'):continue
                pix=pdf[pn-1].get_pixmap(clip=pymupdf.Rect(box),dpi=300,colorspace=pymupdf.csRGB,alpha=False)
                origin=[pix.x*72/300-20*72/300,pix.y*72/300-20*72/300]
                padded=pymupdf.Pixmap(pymupdf.csRGB,pymupdf.IRect(0,0,pix.width+40,pix.height+40),False)
                padded.clear_with(255);pix.set_origin(20,20);padded.copy(pix,pix.irect);padded.set_dpi(300,300)
                image=output/'ocr-input.png';padded.save(image)
                cmd=[sys.executable,'-X','utf8',str(BASE/'ocr_worker.py'),image.relative_to(ROOT).as_posix(),
                     data.parent.relative_to(ROOT).as_posix(),'--psm','6','--dpi','300','--include-words']
                run=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=120,
                                   creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if run.returncode:raise RuntimeError(run.stderr)
                payload=json.loads(run.stdout)
                record={'pdf_page':pn,'region':name,'bbox':box,'dpi':300,'psm':6,'padding_pixels':20,
                        'coordinate_origin':origin,'image_sha256':sha(image),'ocr':payload,
                        'pdf_reviewed_text':reviewed,'adopted_automatically':False}
                filename=f'page-{pn:04d}-{name}.json';write_json(output/filename,record)
                captures.append(filename)
            print(json.dumps({'page':pn,'boxes_done':len(captures)}),flush=True)
    image.unlink()
    write_json(output/'manifest.json',{'pdf_sha256':sha(pdf_path),'worker_sha256':sha(BASE/'ocr_worker.py'),
        'capture_sha256':sha(__file__),'traineddata_sha256':sha(data),'llm_invoked':False,
        'files':{name:sha(output/name) for name in captures},'adopted_automatically':False})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    capture(p.parse_args().output)
