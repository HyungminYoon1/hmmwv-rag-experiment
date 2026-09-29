"""Back up v3 and render every unresolved native/OCR alignment for review."""
from __future__ import annotations
import datetime
import hashlib
import json
from pathlib import Path
import zipfile
import pymupdf
import correct_extraction as io


def prepare():
    target = io.BASE / 'review-557'
    if target.exists():
        raise ValueError('Review folder already exists; do not overwrite')
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = io.BASE / 'backups' / ('v3-before-review557-' + stamp)
    backup.mkdir(parents=True)
    roots = [io.BASE/'output/corrected-v3-a', io.BASE/'corrections/batch-003',
             io.BASE/'review-v2/verified-v3-a']
    paths = [p for root in roots for p in root.rglob('*') if p.is_file()]
    paths += [io.BASE/name for name in [
        'correct_extraction.py','verify_corrections.py','build_reviewed_structures.py',
        'verify_whole_manual_review.py','build_review_batch003.py','README.md',
        'PDF_텍스트_추출_오류_보정.md','전체교범_추가검토와_전후비교.md',
        'audit/corrections-v3-a.json','audit/corrections-v3-a.diff','audit/whole-manual-review-v3.json']]
    manifest = {p.relative_to(io.ROOT).as_posix(): io.sha(p) for p in sorted(paths)}
    archive = backup / 'corrected-v3-and-evidence.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(paths):
            z.write(p, p.relative_to(io.ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        restored = {name:hashlib.sha256(z.read(name)).hexdigest() for name in z.namelist()}
    assert restored == manifest
    verification = {'status':'PASS','files':manifest,'backup_zip_sha256':io.sha(archive),
                    'archive_contents_reopened_and_verified':True,
                    'source_pdf_sha256':'4606773be7d6914f23fa9f9d51dcdb1f4b054dea99db9cd4109fb5d412a21c7d'}
    (backup/'backup-verification.json').write_bytes(io.json_bytes(verification))
    target.mkdir()
    (target/'sheets').mkdir()
    (target/'source-crops').mkdir()
    rows = [r for r in io.load_records(io.BASE/'review-v2/verified-v3-a/alignment-triage.jsonl')
            if r['status']=='UNRESOLVED_LAYER_DISAGREEMENT_NOT_AUTO_REPLACED']
    assert len(rows)==557
    ledger = json.loads((io.BASE/'corrections/batch-003/correction-log.json').read_text(encoding='utf-8'))
    with pymupdf.open(io.ROOT/ledger['inputs']['pdf']['path']) as pdf:
        for batch in range(0,len(rows),14):
            sheetdoc = pymupdf.open(); page = sheetdoc.new_page(width=1400,height=1960)
            for j,row in enumerate(rows[batch:batch+14]):
                original = pdf[row['pdf_page']-1]; b=row['bbox']
                clip = pymupdf.Rect(20,max(0,b[1]-8),original.rect.width-15,min(original.rect.height,b[3]+8))
                pix=original.get_pixmap(dpi=180,alpha=False,clip=clip)
                rel='source-crops/'+row['id']+'.png'; pix.save(target/rel)
                row['source_crop']=rel;row['crop_sha256']=io.sha(target/rel);row['render_clip']=list(clip)
                row['sheet']=f'sheets/sheet-{batch//14+1:02d}.png'
                y=j*140
                page.insert_text((5,y+13),f"{batch+j+1:03d} {row['id']} PDF {row['pdf_page']}",fontsize=12)
                # Raw JSONL remains authoritative for characters unsupported by Helvetica.
                page.insert_text((5,y+28),'N: '+row['native'],fontsize=10)
                page.insert_text((5,y+42),'O: '+row['ocr'],fontsize=10)
                page.insert_image(pymupdf.Rect(5,y+48,1395,y+136),stream=pix.tobytes('png'),keep_proportion=True)
            page.get_pixmap().save(target/f'sheets/sheet-{batch//14+1:02d}.png')
    (target/'candidates.jsonl').write_bytes(io.records_bytes(rows))
    (target/'preparation.json').write_bytes(io.json_bytes({'backup_folder':str(backup),
        'backup_files':len(manifest),'backup_sha256':io.sha(archive),'candidate_count':len(rows),
        'pages':len({r['pdf_page'] for r in rows}),'sheets':(len(rows)+13)//14,
        'program_sha256':io.sha(__file__)}))
    print(json.dumps({'backup_folder':str(backup),'backup_files':len(manifest),'candidates':len(rows),'sheets':40},ensure_ascii=False))


if __name__=='__main__':
    prepare()
