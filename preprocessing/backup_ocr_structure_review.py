"""Back up final OCR audit evidence and verify archived and current bytes."""
from pathlib import Path
from datetime import datetime
import zipfile
import hashlib
from corpus.common import BASE, ROOT, read_json, read_jsonl, write_json, sha


def main():
    audit=BASE/'ocr-structure-review-20260924'
    assert read_json(audit/'independent-verification.json')['status']=='PASS'
    assert read_json(audit/'negative-tests.json')['status']=='PASS'
    assert read_json(audit/'repeatability.json')['status']=='PASS'
    selected=set()
    final_folders={'full-audit-e','full-audit-f','ocr-words-remaining','layout-overview','source-code'}
    for path in audit.rglob('*'):
        if not path.is_file():continue
        rel=path.relative_to(audit)
        if path.name in {'completion.json','artifact-manifest.json'}:continue
        if len(rel.parts)==1 or rel.parts[0] in final_folders:selected.add(path)
    for row in read_json(audit/'visual-review.json')['pages']:
        p=ROOT/row['image'];assert sha(p)==row['image_sha256'];selected.add(p)
    for row in read_jsonl(audit/'page-review-results.jsonl'):
        p=ROOT/row['capture_file'];assert sha(p)==row['capture_sha256'];selected.add(p)
    selected.add(BASE/'corpus/reports/rules-v4-work/ocr-words-all/manifest.json')
    program_names=read_json(audit/'source-code-manifest.json')['files']
    for name in program_names:selected.add(BASE/name)
    selected.add(Path(__file__).resolve())
    docs=['README.md','corpus/README.md','corpus/DECISIONS.md',
          'corpus/reports/OCR_전체구조_검토결과_2026-09-24.md',
          'corpus/reports/잔여조건연결_OCR검토_실시기록_2026-09-24.md']
    for name in docs:selected.add(BASE/name)
    for p in selected:
        p.resolve().relative_to(BASE.resolve())
        assert p.is_file() and p.name!='.env' and not p.name.startswith('.env.')
    entries={p.relative_to(ROOT).as_posix():{'sha256':sha(p),'size_bytes':p.stat().st_size} for p in sorted(selected)}
    baseline=read_json(audit/'baseline.json')
    write_json(audit/'artifact-manifest.json',{'files':entries,'baseline':baseline,
       'excluded':'Intermediate full-audit-a/b/c/d except actually viewed images; analysis package binaries; original PDF and unchanged corpus dependencies are in the baseline backup.'})
    selected.add(audit/'artifact-manifest.json')
    name=(audit/'artifact-manifest.json').relative_to(ROOT).as_posix()
    entries[name]={'sha256':sha(audit/'artifact-manifest.json'),'size_bytes':(audit/'artifact-manifest.json').stat().st_size}
    target=BASE/'backups'/('ocr-structure-review-after-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    target.mkdir(parents=True,exist_ok=False);archive=target/'backup.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
        for p in sorted(selected):z.write(p,p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist())==set(entries)
        for name,entry in entries.items():
            assert hashlib.sha256(z.read(name)).hexdigest()==entry['sha256'],name
            assert sha(ROOT/name)==entry['sha256'],'Source changed during backup: '+name
    report={'status':'PASS','archive':archive.relative_to(ROOT).as_posix(),'archive_sha256':sha(archive),
       'file_count':len(entries),'zip_bytes':archive.stat().st_size,'files':entries,
       'source_bytes':sum(e['size_bytes'] for e in entries.values()),
       'zip_crc_and_all_entry_hashes_verified':True,'source_hashes_verified_after_backup':True,
       'baseline_backup':baseline,'kind':'AUDIT_EVIDENCE_DELTA_WITH_BASELINE_REFERENCE'}
    write_json(target/'manifest.json',report)
    completion={'status':'REVIEW_COMPLETE_CORRECTIONS_PENDING','scope_pdf_pages':[31,863],
       'ocr_pages_programmatically_checked':671,'layout_overview_pages':671,'detailed_review_pages':44,
       'all_text_and_all_branches_proofread':False,'confirmed_case_groups':7,
       'corpus_modified':False,'reviews_cleared':0,'corpus_ready_for_index':False,
       'final_audit':'full-audit-e','replica':'full-audit-f','repeatability_files':675,
       'independent_checks':read_json(audit/'independent-verification.json')['checks'],
       'backup':{k:v for k,v in report.items() if k not in {'files','baseline_backup'}},
       'backup_manifest':(target/'manifest.json').relative_to(ROOT).as_posix(),
       'receipt_outside_archive':True}
    write_json(audit/'completion.json',completion)
    print({k:v for k,v in report.items() if k not in {'files','baseline_backup'}})


if __name__=='__main__':main()
