"""Preserve the legible instruction on the faded sling data plate."""
import pymupdf
import correct_extraction as io
from corpus.common import *


def main():
    s=SourceStore(check=False);parent=ROOT/s.config['correction_ledger'];ledger=read_json(parent)
    out=BASE/'corrections/batch-017'
    if out.exists():raise ValueError('Use a new batch')
    out.mkdir();(out/'evidence').mkdir()
    for p in ledger['corrections']:
        dest=out/p['evidence_crop']
        if not dest.exists():dest.write_bytes((parent.parent/p['evidence_crop']).read_bytes())
    rid='P0050:ocr';raw=s.before[rid]['text'];a=raw.index('THAU');before=raw[a:a+4]
    clip=[55,440,215,478];image=out/'evidence/V17-P0050.png'
    with pymupdf.open(ROOT/s.config['source_pdf']) as pdf:pdf[49].get_pixmap(clip=pymupdf.Rect(clip),dpi=180,alpha=False).save(image)
    ledger['corrections'].append({'id':'FIX-V17-P0050','record_id':rid,'pdf_page':50,'start':a,'end':a+4,'before':before,'after':'THRU',
      'bbox':clip,'render_clip':clip,'kind':'PDF_TEXT_CORRECTION','reason':'읽을 수 있는 원문 REAR SLINGS MUST PASS THRU GUIDES를 복원. 명판의 희미한 수치는 추정하지 않았다.',
      'source_check':'CODEX_PDF_VISUAL_CHECK','human_review':'NOT_PERFORMED','evidence_crop':image.relative_to(out).as_posix(),'evidence_sha256':sha(image)})
    ledger.update(batch='batch-017-legible-plate-instruction',date='2026-09-25',parent={'path':parent.relative_to(ROOT).as_posix(),'sha256':sha(parent)})
    io.validate_ledger(io.source_records(io.check_inputs(ledger)),ledger)
    write_json(out/'correction-log.json',ledger);write_json(out/'reviewed-boxes.json',[])
    print({'active_corrections':len(ledger['corrections'])})


if __name__=='__main__':main()
