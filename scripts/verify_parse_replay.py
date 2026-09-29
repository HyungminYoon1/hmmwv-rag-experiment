"""Check frozen-OCR replay; expose historical unused worker metadata changes."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'preprocessing'))


def verify(reference, replay):
    spec = importlib.util.spec_from_file_location('preserved_parse_verifier', ROOT / 'preprocessing/verify_full_manual.py')
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    first, second = original.inspect(reference), original.inspect(replay)
    compared = original.compare(reference, replay)
    different_files = [r['file'] for r in compared['files'] if not r['identical']]
    old = json.loads((reference / 'manifest.json').read_text(encoding='utf-8'))
    new = json.loads((replay / 'manifest.json').read_text(encoding='utf-8'))
    metadata_changes = {key: {'reference': old.get(key), 'replay': new.get(key)}
                        for key in sorted(set(old) | set(new)) if old.get(key) != new.get(key)}
    summary = json.loads((replay / 'summary.json').read_text(encoding='utf-8'))
    no_new_ocr = summary['newly_computed_ocr_pages'] == []
    worker_hash = hashlib.sha256((ROOT / 'preprocessing/ocr_worker.py').read_bytes()).hexdigest()
    metadata_only = (different_files == ['manifest.json'] and set(metadata_changes) == {'ocr_worker_sha256'}
                     and new['ocr_worker_sha256'] == worker_hash and no_new_ocr)
    passed = first['all_passed'] and second['all_passed'] and (compared['all_identical'] or metadata_only)
    return {'status': 'PASS' if passed else 'FAIL', 'byte_identical': compared['all_identical'],
            'reference_checks': first, 'replay_checks': second, 'file_comparison': compared,
            'metadata_changes': metadata_changes, 'new_ocr_computed': not no_new_ocr,
            'accepted_metadata_difference': 'unused OCR worker source hash' if metadata_only else None,
            'explanation': 'Frozen OCR was replayed. The historical manifest records an older worker; all other files and metadata must match.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, default=ROOT / 'preprocessing/output/full-manual-v2-a')
    parser.add_argument('--replay', type=Path, required=True)
    parser.add_argument('--report', type=Path, default=ROOT / 'validation/local/parse-replay.json')
    args = parser.parse_args()
    if not args.report.resolve().is_relative_to((ROOT / 'validation/local').resolve()):
        parser.error('Save new reports under validation/local to preserve original reports')
    result = verify(args.reference.resolve(), args.replay.resolve())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_bytes((json.dumps(result, ensure_ascii=False, indent=2).replace('\n', '\r\n') + '\r\n').encode('utf-8'))
    print(json.dumps({k: v for k, v in result.items() if k not in ('reference_checks', 'replay_checks', 'file_comparison')}, ensure_ascii=False))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
