"""Reproduce preprocessing from the original PDF and a versioned OCR transcript.

Native extraction, cleanup, table parsing and source checks run again. OCR is an
explicit fixed input, not recomputed or claimed to be bitwise deterministic.
"""
import argparse
import hashlib
import json
from pathlib import Path

import preprocess as pipeline


def replay(config_path, snapshot, output):
    config = json.loads(config_path.read_text(encoding='utf-8'))
    meta_path = snapshot / 'manifest.json'
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    checks = {
        'source': meta['source_sha256'] == config['input_sha256'],
        'config': meta['config_sha256'] == pipeline.sha(config_path),
        'ocr_data': meta['ocr_data_sha256'] == config['ocr']['data_sha256'],
        'renderer': meta['capture_pymupdf_version'] == pipeline.pymupdf.VersionBind,
    }
    for name, digest in meta['files'].items():
        checks[f'file:{name}'] = pipeline.sha(snapshot / name) == digest
    if not all(checks.values()):
        raise ValueError(f'OCR snapshot input mismatch: {[k for k,v in checks.items() if not v]}')
    pages = {r['pdf_page']: r for r in
             map(json.loads, (snapshot / 'pages.jsonl').read_text(encoding='utf-8').splitlines())}
    tables = {}
    for row in map(json.loads, (snapshot / 'tables.jsonl').read_text(encoding='utf-8').splitlines()):
        tables.setdefault(row['pdf_page'], []).append(row)
    native_table_extractor = pipeline.pmcs_rows
    live_page_ocr = pipeline.full_ocr_lines
    reused_pages, reused_tables = set(), set()

    def fixed_page_ocr(page, tessdata, dpi, language):
        number = page.number + 1
        if number not in pages:
            raise ValueError(f'The snapshot does not contain page {number}')
        record = pages[number]
        pix = page.get_pixmap(dpi=dpi, colorspace=pipeline.pymupdf.csRGB, alpha=False)
        digest = hashlib.sha256(pix.samples).hexdigest()
        if digest != record['raster_sha256']:
            raise ValueError(f'Rendered pixels changed on page {number}; do not reuse its OCR transcript.')
        reused_pages.add(number)
        return record['lines'], digest

    def table_extractor(page, cfg, tessdata):
        number = page.number + 1
        if str(number) in cfg['pmcs_scanned_pages']:
            if number not in tables:
                raise ValueError(f'The snapshot does not contain the scanned table on page {number}')
            reused_tables.add(number)
            return tables[number]
        return native_table_extractor(page, cfg, tessdata)

    # Explicit extraction-stage dependency substitution. Neither native extraction
    # nor the normalization/validation stages are loaded from previous outputs.
    pipeline.full_ocr_lines = fixed_page_ocr
    pipeline.pmcs_rows = table_extractor
    try:
        pipeline.run(config_path, output)
    finally:
        pipeline.full_ocr_lines = live_page_ocr
        pipeline.pmcs_rows = native_table_extractor

    summary_path = output / 'summary.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    summary.update({
        'execution_mode': 'REPLAY_FIXED_OCR', 'ocr_newly_computed_pages': 0,
        'ocr_reused_pages': len(reused_pages), 'ocr_reused_table_pages': sorted(reused_tables),
        'ocr_snapshot_sha256': pipeline.sha(meta_path),
        'snapshot_status': meta['status'],
        'fresh_pdf_to_ocr_determinism': 'NOT_ESTABLISHED',
    })
    pipeline.dump(summary_path, summary)
    html_path = output / '검토용_원문대조.html'
    page = html_path.read_text(encoding='utf-8')
    page = page.replace('<h1>험비 교범 전처리 원문 대조</h1>',
                        '<h1>험비 교범 전처리 원문 대조</h1><p><strong>이 결과는 원본 PDF와 고정된 OCR 추출본으로 다시 생성했습니다. '
                        'OCR을 새로 계산해 같은 결과가 나왔다는 뜻은 아닙니다.</strong></p>')
    pipeline.write(html_path, page)
    manifest_path = output / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest.update({'execution_mode': 'REPLAY_FIXED_OCR',
                     'replay_program_sha256': pipeline.sha(Path(__file__)),
                     'ocr_worker_used_this_run': False,
                     'ocr_snapshot_sha256': pipeline.sha(meta_path)})
    manifest['files'] = {p.relative_to(output).as_posix(): pipeline.sha(p)
                         for p in sorted(output.rglob('*')) if p.is_file() and p != manifest_path}
    pipeline.dump(manifest_path, manifest)
    print(json.dumps({'mode': 'REPLAY_FIXED_OCR', 'pages_reused': len(reused_pages),
                      'snapshot_sha256': pipeline.sha(meta_path)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=pipeline.BASE / 'config.json')
    parser.add_argument('--snapshot', type=Path, default=pipeline.BASE / 'assets/ocr-snapshot')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    replay(args.config.resolve(), args.snapshot.resolve(), args.output.resolve())
