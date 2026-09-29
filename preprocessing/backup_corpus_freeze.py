"""Create a self-contained, verified backup of the frozen corpus state."""
from datetime import datetime
import hashlib,zipfile
from corpus.common import *


def main():
    work=PACKAGE/'reports/rules-v6-freeze';frozen=read_json(work/'freeze.json')
    assert frozen['state']=='FROZEN_FOR_TEXT_RESEARCH' and frozen['audit']['corpus_ready_for_index']
    baseline_path=BASE/'backups/corpus-freeze-before-20260924-233201/manifest.json'
    baseline=read_json(baseline_path);lock=read_json(PACKAGE/'inputs.lock.json')
    selected={ROOT/name for name in baseline['files']}|{ROOT/name for name in lock['files']}
    for relative in ['output/corrected-v19-a','output/corrected-v19-b','corrections/batch-019',
                     'output/corpus-v6-final','output/corpus-v6-final-replica','corpus/rules/v6','corpus/rules/v6-final',
                     'corpus/reports/rules-v6-freeze']:
        selected.update(p for p in (BASE/relative).rglob('*') if p.is_file())
    selected.update(BASE.glob('*.py'));selected.update(BASE.glob('*.md'))
    selected.update(p for p in PACKAGE.rglob('*.py') if '__pycache__' not in p.parts)
    selected.update(PACKAGE.glob('*.md'));selected.update((PACKAGE/'reports').glob('*.md'))
    selected.update(p for p in (PACKAGE/'web').rglob('*') if p.is_file())
    selected.update([PACKAGE/'config.json',PACKAGE/'inputs.lock.json'])
    selected.discard(work/'completion.json')
    for p in selected:
        assert p.resolve().is_relative_to(ROOT.resolve()) and p.is_file(),p
        assert not p.name.startswith('.env'),p
    target=BASE/'backups'/('corpus-freeze-after-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    target.mkdir(parents=True,exist_ok=False);archive=target/'backup.zip'
    entries={p.relative_to(ROOT).as_posix():{'sha256':sha(p),'size_bytes':p.stat().st_size} for p in sorted(selected)}
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
        for p in sorted(selected):z.write(p,p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist())==set(entries)
        for name,entry in entries.items():
            assert hashlib.sha256(z.read(name)).hexdigest()==entry['sha256'],name
            assert sha(ROOT/name)==entry['sha256'],'Changed during backup: '+name
    report={'status':'PASS','archive':archive.relative_to(ROOT).as_posix(),'archive_sha256':sha(archive),
      'files':entries,'file_count':len(entries),'source_bytes':sum(x['size_bytes'] for x in entries.values()),
      'zip_bytes':archive.stat().st_size,'zip_crc_and_all_entry_hashes_verified':True,
      'source_hashes_verified_after_backup':True,'all_locked_inputs_present':set(lock['files'])<=set(entries),
      'kind':'SELF_CONTAINED_FROZEN_CORPUS','before_backup_manifest':baseline_path.relative_to(ROOT).as_posix(),
      'before_backup_sha256':baseline['archive_sha256']}
    write_json(target/'manifest.json',report)
    receipt={'state':frozen['state'],'corpus':frozen['corpus'],'corpus_ready_for_index':True,
      'freeze_record':(work/'freeze.json').relative_to(ROOT).as_posix(),'freeze_record_sha256':sha(work/'freeze.json'),
      'backup_manifest':(target/'manifest.json').relative_to(ROOT).as_posix(),
      'backup':{k:v for k,v in report.items() if k!='files'},'receipt_outside_archive':True}
    write_json(work/'completion.json',receipt)
    print({k:v for k,v in report.items() if k!='files'})


if __name__=='__main__':main()
