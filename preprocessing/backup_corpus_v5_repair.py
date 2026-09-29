"""Preserve the final repair state with a self-contained, hash-checked backup."""
from datetime import datetime
from pathlib import Path
import hashlib
import zipfile
from corpus.common import BASE, ROOT, PACKAGE, read_json, write_json, sha


def main():
    work=PACKAGE/'reports/rules-v5-work'
    execution=read_json(work/'execution.json')
    assert execution['mechanical_status']=='PASS' and execution['deterministic_replica']
    assert read_json(work/'runtime.json')['status']=='PASS'
    baseline_path=BASE/'backups/ocr-repair-before-20260924-223152/manifest.json'
    baseline=read_json(baseline_path)
    selected={ROOT/name for name in baseline['files']}
    prefixes=[
        'corrections/batch-008','corrections/batch-009',
        'output/corrected-v8-a','output/corrected-v9-a','output/corrected-v9-b',
        'output/corpus-v5-rules-a','output/corpus-v5-rules-c','output/corpus-v5-rules-d',
        'corpus/rules/v5','corpus/rules/v5-final',
        'corpus/reports/rules-v5-work','corpus/reports/rules-v5-final-comparison']
    for relative in prefixes:
        selected.update(p for p in (BASE/relative).rglob('*') if p.is_file())
    selected.update(BASE.glob('*.py'))
    selected.update(p for p in (PACKAGE).rglob('*.py') if '__pycache__' not in p.parts)
    selected.update(BASE.glob('*.md'))
    selected.update(PACKAGE.glob('*.md'))
    selected.update((PACKAGE/'reports').glob('*.md'))
    for name in ['audit/corrected-v8-a.json','audit/corrected-v8-a.diff',
                 'audit/corrected-v9-a.json','audit/corrected-v9-a.diff']:
        selected.add(BASE/name)
    selected.discard(work/'completion.json')
    for p in selected:
        assert p.resolve().is_relative_to(ROOT.resolve()) and p.is_file(),p
        assert not p.name.startswith('.env'),p
    names={p.relative_to(ROOT).as_posix() for p in selected}
    lock=read_json(PACKAGE/'inputs.lock.json')
    assert set(lock['files']).issubset(names),'Backup missing a locked input'
    target=BASE/'backups'/('ocr-repair-after-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    target.mkdir(parents=True,exist_ok=False)
    archive=target/'backup.zip'
    entries={p.relative_to(ROOT).as_posix():{'sha256':sha(p),'size_bytes':p.stat().st_size} for p in sorted(selected)}
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
        for p in sorted(selected):z.write(p,p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist())==set(entries)
        for name,entry in entries.items():
            assert hashlib.sha256(z.read(name)).hexdigest()==entry['sha256'],name
            assert sha(ROOT/name)==entry['sha256'],'Changed during backup: '+name
    report={'status':'PASS','archive':archive.relative_to(ROOT).as_posix(),
        'archive_sha256':sha(archive),'file_count':len(entries),'files':entries,
        'source_bytes':sum(v['size_bytes'] for v in entries.values()),'zip_bytes':archive.stat().st_size,
        'zip_crc_and_all_entry_hashes_verified':True,'source_hashes_verified_after_backup':True,
        'all_locked_inputs_present':True,'kind':'SELF_CONTAINED_REPAIR_STATE',
        'before_backup_manifest':baseline_path.relative_to(ROOT).as_posix(),
        'before_backup_sha256':baseline['archive_sha256']}
    write_json(target/'manifest.json',report)
    completion={'status':execution['status'],'active_source':execution['active_source'],
        'active_corpus':execution['active_corpus'],'corpus_ready_for_index':False,
        'execution':'preprocessing/corpus/reports/rules-v5-work/execution.json',
        'backup':{k:v for k,v in report.items() if k!='files'},
        'backup_manifest':(target/'manifest.json').relative_to(ROOT).as_posix(),
        'receipt_outside_archive':True}
    write_json(work/'completion.json',completion)
    print({k:v for k,v in report.items() if k!='files'})


if __name__=='__main__':main()
