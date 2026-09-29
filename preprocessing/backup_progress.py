"""Back up project progress, then verify every archived file against its source."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent.parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    text = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    path.write_bytes(text.replace('\n', '\r\n').encode('utf-8'))


def run():
    base = ROOT / 'preprocessing'
    # A read-only integrity check before accepting the current v4 checkpoint.
    checked = 0
    for name in ('output/full-manual-v2-a', 'output/corrected-v4-a',
                 'output/corrected-v4-b', 'review-557/verified-v4-a',
                 'review-557/verified-v4-b'):
        folder = base / name
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        for relative, expected in manifest['files'].items():
            assert digest((folder / relative).read_bytes()) == expected, (name, relative)
            checked += 1
    ledger = json.loads((base / 'corrections/batch-004/correction-log.json').read_text(encoding='utf-8'))
    for item in ledger['inputs'].values():
        assert digest((ROOT / item['path']).read_bytes()) == item['sha256']
    audit = json.loads((base / 'audit/review557-v4.json').read_text(encoding='utf-8'))
    assert audit['status'] == 'PASS' and not audit['errors'] and all(audit['checks'].values())
    assert audit['verifier_sha256'] == digest((base / 'verify_review557.py').read_bytes())
    assert audit['ledger_sha256'] == digest((base / 'corrections/batch-004/correction-log.json').read_bytes())
    target = ROOT / 'backups' / ('progress-v4-before-manuscript-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    target.mkdir(parents=True, exist_ok=False)
    selected = []
    for path in ROOT.rglob('*'):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if relative.parts[0] == 'backups' or any(p in ('.venv', '__pycache__', '.git') for p in relative.parts):
            continue
        if path.name == '.env' or path.name.startswith('.env.'):
            continue
        selected.append(path)
    archive = target / 'project-progress.zip'
    manifest = {}
    total_bytes = 0
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=3) as z:
        for path in sorted(selected):
            data = path.read_bytes()
            relative = path.relative_to(ROOT).as_posix()
            manifest[relative] = {'sha256': digest(data), 'bytes': len(data)}
            total_bytes += len(data)
            z.writestr(relative, data)
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist()) == set(manifest)
        for name, entry in manifest.items():
            assert digest(z.read(name)) == entry['sha256'], name
            assert digest((ROOT / name).read_bytes()) == entry['sha256'], 'Source changed during backup: ' + name
    report = {
        'status': 'PASS', 'root': str(ROOT), 'archive': str(archive),
        'archive_sha256': digest(archive.read_bytes()), 'files': manifest,
        'file_count': len(manifest), 'source_bytes': total_bytes,
        'archive_bytes': archive.stat().st_size,
        'current_checkpoint_manifest_files_verified': checked,
        'excluded': ['root backups/ (avoid recursive archives)', '.venv/', '__pycache__/', '.git/', '.env and .env.*'],
        'included': 'All remaining project files, including manuals, drafts, historical evidence, scripts, OCR snapshots, outputs, and previous preprocessing backup.',
        'archive_reopened_and_all_files_verified': True,
        'source_files_rehashed_after_backup': True,
        'checkpoint': 'corrected-v4-a; verified-v4-a; manuscript before progress update',
    }
    write_json(target / 'backup-verification.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'files'}, ensure_ascii=False))


if __name__ == '__main__':
    run()
