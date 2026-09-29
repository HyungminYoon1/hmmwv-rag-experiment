"""Back up research artifacts with entry-by-entry SHA verification; no deletions."""
from datetime import datetime
import hashlib,zipfile
from .io import BASE,ROOT,read_json,save,sha,utc

def main():
    run=BASE/'runs/formal-v1'
    if read_json(run/'status.json')['state']!='COMPLETED' or read_json(run/'audit.json')['status']!='PASS':
        raise ValueError('Complete and audit the run before archiving it')
    target=ROOT/'backups'/('after-experiment-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    target.mkdir(parents=True,exist_ok=False);files=[];excluded=[]
    for p in BASE.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(BASE)
        if ('models' in rel.parts and rel.as_posix()!='models/model.lock.json') or '__pycache__' in rel.parts or p.suffix in ('.log','.tmp') or p.name.startswith('.env'):
            excluded.append(p.relative_to(ROOT).as_posix());continue
        files.append(p)
    files.append(ROOT/'research/2026-09-28_근거대응표와_로컬_비교실험_실시기록.md')
    entries={};output=target/'experiment-artifacts.zip'
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in sorted(files):
            name=p.relative_to(ROOT).as_posix();data=p.read_bytes()
            archive.writestr(name,data);entries[name]=hashlib.sha256(data).hexdigest()
    with zipfile.ZipFile(output) as archive:
        assert set(archive.namelist())==set(entries)
        for name,digest in entries.items():assert hashlib.sha256(archive.read(name)).hexdigest()==digest,name
    manifest={'at':utc(),'status':'PASS','archive':output.relative_to(ROOT).as_posix(),
      'archive_sha256':sha(output),'archive_bytes':output.stat().st_size,'verified_entries':len(entries),
      'files':entries,'excluded_files':excluded,
      'exclusion_policy':'Large model weights/caches, bytecode, active server logs, temporary files and any .env files. Model provenance and hashes remain included.'}
    save(target/'manifest.json',manifest)
    save(BASE/'reports/backup-after.json',{k:v for k,v in manifest.items() if k not in ('files','excluded_files')})
    print({k:manifest[k] for k in ('status','archive','archive_bytes','verified_entries')})

if __name__=='__main__':main()
