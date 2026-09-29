"""Version an OCR transcript as an explicit input for reproducible preprocessing.

This does not certify OCR accuracy or freeze the final RAG corpus.
"""
import argparse
import json
from pathlib import Path

from preprocess import dump, jsonline, sha, write


def freeze(source, target):
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    for name, digest in manifest['files'].items():
        if sha(source / name) != digest:
            raise ValueError(f'Capture result changed: {name}')
    if target.exists() and any(target.iterdir()):
        raise ValueError('Choose an empty snapshot directory; existing snapshots are preserved.')
    target.mkdir(parents=True, exist_ok=True)
    text = (source / 'raw_ocr_pages.jsonl').read_text(encoding='utf-8')
    write(target / 'pages.jsonl', text)
    rows = [json.loads(line) for line in (source / 'pmcs_table_rows.jsonl').read_text(encoding='utf-8').splitlines()]
    scans = [r for r in rows if r['method'] == 'tesseract_column_crop']
    write(target / 'tables.jsonl', ''.join(jsonline(r) for r in scans))
    frozen = {
        'status': 'OCR_TRANSCRIPT_FIXED_NOT_REVIEWED',
        'source_sha256': manifest['input_sha256'],
        'config_sha256': manifest['config_sha256'],
        'ocr_data_sha256': manifest['ocr_data_sha256'],
        'capture_manifest_sha256': sha(source / 'manifest.json'),
        'capture_program_sha256': manifest['program_sha256'],
        'capture_ocr_worker_sha256': manifest.get('ocr_worker_sha256'),
        'capture_ocr_engine': manifest.get('ocr_engine'),
        'capture_pymupdf_version': manifest['pymupdf_version'],
        'page_count': len(text.splitlines()), 'table_row_count': len(scans),
        'files': {name: sha(target / name) for name in ['pages.jsonl', 'tables.jsonl']},
        'llm_used': False,
    }
    dump(target / 'manifest.json', frozen)
    print(json.dumps(frozen, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-run', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    freeze(args.from_run.resolve(), args.output.resolve())
