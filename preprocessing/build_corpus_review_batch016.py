"""Add three final transcription repairs without changing earlier patches."""
import pymupdf
import correct_extraction as io
from corpus.common import *
from corpus.final_text_repairs_v6 import REGIONS


def main():
    s=SourceStore(check=False);parent=ROOT/s.config['correction_ledger'];ledger=read_json(parent)
    out=BASE/'corrections/batch-016'
    if (out/'correction-log.json').exists():raise ValueError('Use a new batch')
    out.mkdir(exist_ok=True);(out/'evidence').mkdir(exist_ok=True)
    for p in ledger['corrections']:
        dest=out/p['evidence_crop']
        if not dest.exists():dest.write_bytes((parent.parent/p['evidence_crop']).read_bytes())
    regions=[]
    with pymupdf.open(ROOT/s.config['source_pdf']) as pdf:
        for pn,entries in REGIONS.items():
            rid=f'P{pn:04d}:ocr';raw=s.before[rid]['text'];end=raw.index('TEST PROCEOURES') if pn==128 else len(raw)
            texts=[];pos=0
            for name,value,box in entries:
                regions.append({'name':name,'record_id':rid,'pdf_page':pn,'start':pos,'end':pos+len(value),'text':value,'bbox':box})
                texts.append(value);pos+=len(value)+2
            after='\n\n'.join(texts)+ ('\n\n' if pn==128 else '')
            assert all(p['end']<=0 or p['start']>=end for p in s.patches[rid])
            image=out/f'evidence/V16-P{pn:04d}.png';clip=list(pdf[pn-1].rect)
            pdf[pn-1].get_pixmap(dpi=180,alpha=False).save(image)
            ledger['corrections'].append({'id':f'FIX-V16-P{pn:04d}','record_id':rid,'pdf_page':pn,'start':0,'end':end,
              'before':raw[:end],'after':after,'bbox':clip,'render_clip':clip,'kind':'PDF_REGION_TRANSCRIPTION',
              'reason':'명판의 표 값·교범 사용법에서 서로 다른 열이 섞인 문장을 원본 영역별로 다시 전사했다. 그림의 연결 관계는 설명문으로 생성하지 않았다.',
              'source_check':'CODEX_PDF_VISUAL_CHECK','human_review':'NOT_PERFORMED','evidence_crop':image.relative_to(out).as_posix(),'evidence_sha256':sha(image)})
    ledger.update(batch='batch-016-final-column-transcription',date='2026-09-25',parent={'path':parent.relative_to(ROOT).as_posix(),'sha256':sha(parent)})
    io.validate_ledger(io.source_records(io.check_inputs(ledger)),ledger)
    write_json(out/'correction-log.json',ledger);write_json(out/'regions.json',regions);write_json(out/'reviewed-boxes.json',[])
    print({'new_patches':3,'active_corrections':len(ledger['corrections'])})


if __name__=='__main__':main()
