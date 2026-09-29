"""Parse all manual pages; keep native text and OCR separate for source review.

The research scope stays Chapter 1/2. OCR selection does not read evaluation
questions. A frozen OCR transcript supports replay; fresh OCR is not assumed
bitwise deterministic. This exports review data, not ready-to-index chunks.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import platform
import re
import shutil
import tempfile

import preprocess as base

PROFILE = {
    'version': 'full-manual-v2',
    'parse_pages': [1, 890],
    'search_scope_pages': [31, 863],
    'ocr_rule': 'ALL_RASTER_IMAGE_PAGES_OR_SPARSE_VECTOR_PAGES_OR_INVALID_NATIVE_MAPPING_OR_EXISTING_OCR',
    'sparse_vector_max_native_chars': 350,
    'ocr_confidence_flag_below': 60,
    'preview_pages': [6, 38, 61, 66, 97, 100, 103, 111, 129, 300, 327, 610, 814, 864, 868, 885],
}


def invalid_native_mapping(lines):
    return any('\ufffd' in line['text'] or any(ord(c) < 32 and c not in '\t\r\n' for c in line['text']) for line in lines)


def needs_ocr(page, native, body, cached):
    return (bool(page.get_image_info()) or invalid_native_mapping(native)
            or (bool(page.get_drawings()) and len(body) < PROFILE['sparse_vector_max_native_chars'])
            or page.number + 1 in cached)


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def load_snapshot(folder, config, config_path):
    meta = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    expected = {
        'source_sha256': config['input_sha256'],
        'config_sha256': base.sha(config_path),
        'ocr_data_sha256': config['ocr']['data_sha256'],
        'capture_pymupdf_version': base.pymupdf.VersionBind,
    }
    for key, value in expected.items():
        if meta.get(key) != value:
            raise ValueError(f'Snapshot mismatch: {key}')
    for name, digest in meta['files'].items():
        if base.sha(folder / name) != digest:
            raise ValueError(f'Snapshot hash mismatch: {name}')
    rows = read_jsonl(folder / 'pages.jsonl')
    if len({row['pdf_page'] for row in rows}) != len(rows):
        raise ValueError('Duplicate OCR page records')
    return {r['pdf_page']: r for r in rows}


def quality_findings(number, native_lines, ocr_lines, table_rows):
    """Review signals only; no automatic spelling or technical-value correction."""
    findings = []
    for layer, lines in [('native', native_lines), ('ocr', ocr_lines)]:
        for line in lines:
            text = line['text']
            reasons = []
            confidences = [c for c in line.get('word_confidences', []) if c >= 0]
            if confidences and any(c < PROFILE['ocr_confidence_flag_below'] for c in confidences):
                reasons.append('LOW_OCR_WORD_CONFIDENCE')
            if '\ufffd' in text or any(ord(c) < 32 and c not in '\t\r\n' for c in text):
                reasons.append('REPLACEMENT_OR_CONTROL_CHARACTER')
            if re.search(r'\b(?:Ib|Ibs|1b|1bs)[ -]*(?:ft|in)\b', text):
                reasons.append('POSSIBLE_LB_UNIT_MISREAD')
            if re.search(r'\b(?:[A-Za-z] ){5,}[A-Za-z]\b', text):
                reasons.append('SPACED_LETTERS_NEED_REVIEW')
            if reasons:
                findings.append({'pdf_page': number, 'layer': layer, 'bbox': line['bbox'],
                                 'reasons': reasons, 'text': text,
                                 'min_word_confidence': min(confidences) if confidences else None,
                                 'status': 'REVIEW_SIGNAL_NOT_CONFIRMED_ERROR'})
    for row in table_rows:
        findings.append({'pdf_page': number, 'layer': 'table', 'row_id': row['row_id'],
                         'reasons': ['TABLE_CELL_AND_CONTEXT_REVIEW'],
                         'status': 'REVIEW_SIGNAL_NOT_CONFIRMED_ERROR'})
    return findings


def table_text(row):
    # Keep the source's English wording and explicit column labels.
    return '\n'.join([row['table']] + [f'{label}: {row["fields"][label]}' for label in base.COLUMNS])


def write_comparison(out, pages):
    panels = []
    for number in PROFILE['preview_pages']:
        row = pages[number - 1]
        cells = ''.join(f'<h4>{html.escape(t["row_id"])}</h4><pre>{html.escape(table_text(t))}</pre>'
                        for t in row['tables'])
        panels.append(f'<section id="p{number}"><h2>PDF {number} / {html.escape(row["printed_page"] or "면수 확인 필요")}</h2>'
                      f'<p>{html.escape(" · ".join(row["review_flags"]))}</p>'
                      f'<div class="pair"><img loading="lazy" src="previews/page-{number:03d}.png" alt="원본 {number}쪽">'
                      f'<div><h3>원래 텍스트</h3><pre>{html.escape(row["native_body_text"])}</pre>'
                      f'<h3>OCR — 검수 전</h3><pre>{html.escape(row["ocr_body_text"] or "OCR 대상 아님")}</pre>'
                      f'{cells}</div></div></section>')
    base.write(out / '원문대조.html', '<!doctype html><html lang="ko"><meta charset="utf-8">'
               '<title>교범 전체 파싱 대조</title><style>body{font:16px/1.6 system-ui;margin:24px;background:#f4f6f8}'
               'header,section{background:white;padding:24px;margin:20px 0}.pair{display:grid;grid-template-columns:1fr 1fr;gap:24px}'
               'img{width:100%;border:1px solid #ccc}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
               '@media(max-width:850px){.pair{grid-template-columns:1fr}}</style>'
               '<header><h1>교범 전체 파싱 원문 대조</h1><p>890쪽 전체를 처리하고 제1·2장 833쪽을 검색 범위로 표시했습니다. '
               '원래 텍스트와 OCR은 비교용으로 나란히 보관하며 검색 문맥으로 중복 합치지 않습니다. '
               '표본 16쪽이며 전체 문자 정확도를 수동 검증한 자료는 아닙니다. '
               '도면의 연결 관계와 전체 표 구조는 검수 전입니다. LLM에 의한 본문 재작성은 하지 않았습니다.</p>'
               '<nav>' + ' · '.join(f'<a href="#p{p}">{p}</a>' for p in PROFILE['preview_pages']) + '</nav></header>'
               + ''.join(panels) + '</html>')


def run(config_path, snapshot, output, capture_missing):
    config = json.loads(config_path.read_text(encoding='utf-8'))
    source = (base.BASE / config['input']).resolve()
    if base.sha(source) != config['input_sha256']:
        raise ValueError('Source PDF hash mismatch')
    if config['scope_pdf_pages'] != PROFILE['search_scope_pages']:
        raise ValueError('Research scope changed; review the extraction profile first')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a new or empty output directory')
    snapshot_pages = load_snapshot(snapshot, config, config_path)
    scanned_table_folder = base.BASE / 'assets/ocr-snapshot'
    table_meta = json.loads((scanned_table_folder / 'manifest.json').read_text(encoding='utf-8'))
    if base.sha(scanned_table_folder / 'tables.jsonl') != table_meta['files']['tables.jsonl']:
        raise ValueError('Scanned table transcript hash mismatch')
    if table_meta['source_sha256'] != config['input_sha256'] or table_meta['config_sha256'] != base.sha(config_path):
        raise ValueError('Scanned table source/config mismatch')
    scanned_tables = {}
    for row in read_jsonl(scanned_table_folder / 'tables.jsonl'):
        scanned_tables.setdefault(row['pdf_page'], []).append(row)
    language = base.BASE / config['ocr']['data']
    if base.sha(language) != config['ocr']['data_sha256']:
        raise ValueError('OCR language data hash mismatch')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'previews').mkdir()
    (output / 'ocr-snapshot').mkdir()
    pages, all_ocr, all_tables, findings, changes, coverage = [], [], [], [], [], []
    new_ocr, reused_ocr = [], []
    handles = {name: (output / name).open('w', encoding='utf-8', newline='\r\n') for name in
               ['raw_native_pages.jsonl', 'pages.jsonl', '교범_전체_추출텍스트.txt', '실험범위_본문과표_검토본.txt']}
    try:
        with tempfile.TemporaryDirectory(prefix='kidet-full-ocr-') as temp, base.pymupdf.open(source) as doc:
            if not str(temp).isascii():
                raise ValueError('The OCR temporary directory must use an ASCII path')
            shutil.copyfile(language, Path(temp) / 'eng.traineddata')
            if len(doc) != config['expected_pages']:
                raise ValueError('Unexpected page count')
            for page in doc:
                number = page.number + 1
                native = base.line_records(page)
                cleaned, native_changes = base.clean_lines(native, page.rect.height)
                native_body = '\n\n'.join(b['text'] for b in base.blocks_from_lines(cleaned))
                images = page.get_image_info()
                drawings = page.get_drawings()
                in_scope = PROFILE['search_scope_pages'][0] <= number <= PROFILE['search_scope_pages'][1]
                raw = {'pdf_page': number, 'width': page.rect.width, 'height': page.rect.height,
                       'lines': native, 'words': [list(w) for w in page.get_text('words')],
                       'image_bboxes': [[round(v, 4) for v in im['bbox']] for im in images],
                       'vector_drawing_count': len(drawings)}
                handles['raw_native_pages.jsonl'].write(base.jsonline(raw))
                need_ocr = needs_ocr(page, native, native_body, snapshot_pages)
                ocr, ocr_body = [], None
                if need_ocr:
                    if number in snapshot_pages:
                        rec = snapshot_pages[number]
                        pix = page.get_pixmap(dpi=config['ocr']['dpi'], colorspace=base.pymupdf.csRGB, alpha=False)
                        digest = hashlib.sha256(pix.samples).hexdigest()
                        if digest != rec['raster_sha256']:
                            raise ValueError(f'OCR input pixels changed: page {number}')
                        ocr = rec['lines']
                        reused_ocr.append(number)
                    else:
                        if not capture_missing:
                            raise ValueError(f'Page {number} needs OCR but is missing from the fixed transcript')
                        ocr, digest = base.full_ocr_lines(page, temp, config['ocr']['dpi'], config['ocr']['language'])
                        new_ocr.append(number)
                    all_ocr.append({'pdf_page': number, 'method': 'tesseract_full_page',
                                    'raster_sha256': digest, 'lines': ocr})
                    cleaned_ocr, ocr_changes = base.clean_lines(ocr, page.rect.height)
                    ocr_body = '\n\n'.join(b['text'] for b in base.blocks_from_lines(cleaned_ocr))
                    changes.extend({'pdf_page': number, 'layer': 'ocr', **c} for c in ocr_changes)
                else:
                    cleaned_ocr = []
                tables = scanned_tables.get(number, [])
                if number in config['pmcs_native_pages']:
                    tables = base.pmcs_rows(page, config, temp)
                all_tables.extend(tables)
                printed = base.page_label(native, page.rect.height) or base.page_label(ocr, page.rect.height)
                flags = []
                if not native_body and not images and not drawings:
                    flags.append('BLANK_PAGE')
                if images or drawings:
                    flags.append('GRAPHIC_RELATIONS_NOT_RECONSTRUCTED')
                if need_ocr:
                    flags.append('OCR_UNREVIEWED')
                if invalid_native_mapping(native):
                    flags.append('INVALID_NATIVE_TEXT_MAPPING')
                if tables:
                    flags.append('TABLE_STRUCTURE_REVIEW_REQUIRED')
                if not tables and re.search(r'\b(?:TABLE|CHART)\b', native_body + '\n' + (ocr_body or ''), re.I):
                    flags.append('POSSIBLE_OTHER_TABLE_REVIEW_REQUIRED')
                if in_scope and printed and not printed.startswith('1-' if number < 92 else '2-'):
                    flags.append('UNEXPECTED_PRINTED_CHAPTER_NUMBER')
                if in_scope and not printed and 'BLANK_PAGE' not in flags:
                    flags.append('PRINTED_PAGE_LABEL_REVIEW_REQUIRED')
                record = {'pdf_page': number, 'printed_page': printed, 'in_scope': in_scope,
                          'native_body_text': native_body, 'native_blocks': base.blocks_from_lines(cleaned),
                          'ocr_body_text': ocr_body, 'ocr_blocks': base.blocks_from_lines(cleaned_ocr),
                          'image_count': len(images), 'vector_drawing_count': len(drawings),
                          'tables': tables, 'review_flags': flags, 'included_in_final_corpus': None,
                          'extraction_status': 'REVIEW_DATA_NOT_SEARCH_CHUNKS'}
                pages.append(record)
                handles['pages.jsonl'].write(base.jsonline(record))
                local_findings = quality_findings(number, cleaned, cleaned_ocr, tables)
                findings.extend(local_findings)
                changes.extend({'pdf_page': number, 'layer': 'native', **c} for c in native_changes)
                coverage.append({'pdf_page': number, 'printed_page': printed, 'in_scope': in_scope,
                                 'image_count': len(images), 'vector_drawing_count': len(drawings),
                                 'native_chars': len(native_body), 'ocr_chars': len(ocr_body or ''),
                                 'ocr_done': need_ocr, 'pmcs_rows': len(tables),
                                 'review_signals': len(local_findings), 'flags': flags})
                heading = f'\n{"=" * 76}\nPDF PAGE {number:03d} / PRINTED {printed or "UNRESOLVED"} / SEARCH_SCOPE {"YES" if in_scope else "NO"}\n'
                body = heading + '\n[NATIVE TEXT]\n' + (native_body or '[EMPTY]') + '\n'
                if need_ocr:
                    body += '\n[OCR TEXT — UNREVIEWED; ALTERNATIVE EXTRACTION, DO NOT CONCATENATE FOR RAG]\n' + (ocr_body or '[EMPTY]') + '\n'
                if tables:
                    body += '\n[TABLE ROWS — COLUMN LABELS PRESERVED; STRUCTURE REVIEW PENDING]\n'
                    body += '\n\n'.join(table_text(t) for t in tables) + '\n'
                handles['교범_전체_추출텍스트.txt'].write(body)
                if in_scope:
                    handles['실험범위_본문과표_검토본.txt'].write(body)
                if number in PROFILE['preview_pages']:
                    page.get_pixmap(dpi=110, colorspace=base.pymupdf.csRGB, alpha=False).save(output / 'previews' / f'page-{number:03d}.png')
                if number % 25 == 0:
                    print(json.dumps({'processed': number, 'new_ocr': len(new_ocr), 'reused_ocr': len(reused_ocr)}), flush=True)
    finally:
        for handle in handles.values():
            handle.close()
    base.write(output / 'ocr-snapshot/pages.jsonl', ''.join(base.jsonline(r) for r in all_ocr))
    base.dump(output / 'ocr-snapshot/manifest.json', {
        'source_sha256': config['input_sha256'], 'config_sha256': base.sha(config_path),
        'ocr_data_sha256': config['ocr']['data_sha256'], 'capture_pymupdf_version': base.pymupdf.VersionBind,
        'status': 'OCR_TRANSCRIPT_FIXED_NOT_REVIEWED', 'page_count': len(all_ocr), 'llm_used': False,
        'files': {'pages.jsonl': base.sha(output / 'ocr-snapshot/pages.jsonl')},
    })
    for name, records in [('page_coverage.jsonl', coverage), ('review_signals.jsonl', findings),
                          ('normalization_log.jsonl', changes), ('pmcs_table_rows.jsonl', all_tables)]:
        base.write(output / name, ''.join(base.jsonline(r) for r in records))
    base.write(output / 'pmcs_rows_as_text.jsonl', ''.join(base.jsonline({
        'row_id': r['row_id'], 'pdf_page': r['pdf_page'], 'text': table_text(r),
        'review_status': r['review_status'], 'ready_for_index': False,
    }) for r in all_tables))
    summary = {
        'profile': PROFILE, 'source_sha256': base.sha(source),
        'source_unchanged': base.sha(source) == config['input_sha256'],
        'total_pages': len(pages), 'scope_pages': sum(p['in_scope'] for p in pages),
        'outside_scope_pages': sum(not p['in_scope'] for p in pages),
        'raster_image_pages': sum(bool(p['image_count']) for p in pages),
        'ocr_pages': len(all_ocr), 'scope_ocr_pages': sum(p['in_scope'] and p['ocr_body_text'] is not None for p in pages),
        'newly_computed_ocr_pages': new_ocr, 'reused_ocr_pages': reused_ocr,
        'image_pages_without_ocr': [p['pdf_page'] for p in pages if p['image_count'] and p['ocr_body_text'] is None],
        'blank_pages': [p['pdf_page'] for p in pages if 'BLANK_PAGE' in p['review_flags']],
        'scope_pages_without_any_text': [p['pdf_page'] for p in pages if p['in_scope'] and not p['native_body_text'] and not p['ocr_body_text']],
        'invalid_native_mapping_pages': [p['pdf_page'] for p in pages if 'INVALID_NATIVE_TEXT_MAPPING' in p['review_flags']],
        'pmcs_rows': len(all_tables), 'review_signal_records': len(findings),
        'review_signal_counts': dict(Counter(reason for r in findings for reason in r['reasons'])),
        'review_signal_pages': len({r['pdf_page'] for r in findings}),
        'llm_used_for_parsing_or_correction': False, 'network_used_during_run': False,
        'evaluation_questions_read': False, 'automatic_content_corrections': 0,
        'corpus_frozen': False, 'chunking_performed': False,
        'fresh_ocr_determinism': 'NOT_ESTABLISHED',
    }
    if not summary['source_unchanged']:
        raise ValueError('Source PDF changed during the run')
    base.dump(output / 'summary.json', summary)
    write_comparison(output, pages)
    base.dump(output / 'manifest.json', {
        'program_sha256': base.sha(Path(__file__)), 'base_program_sha256': base.sha(Path(base.__file__)),
        'ocr_worker_sha256': base.sha(base.BASE / 'ocr_worker.py'), 'config_sha256': base.sha(config_path),
        'source_sha256': base.sha(source), 'input_ocr_snapshot_sha256': base.sha(snapshot / 'manifest.json'),
        'scanned_table_snapshot_sha256': table_meta['files']['tables.jsonl'],
        'python': platform.python_version(), 'platform': platform.platform(),
        'pymupdf': base.pymupdf.VersionBind, 'tesseract': '5.5.2',
        'files': {p.relative_to(output).as_posix(): base.sha(p) for p in sorted(output.rglob('*')) if p.is_file()},
    })
    print(json.dumps({'complete': True, 'pages': len(pages), 'ocr_pages': len(all_ocr),
                      'new_ocr': len(new_ocr), 'reused_ocr': len(reused_ocr)}, ensure_ascii=False), flush=True)


def extend_snapshot(config_path, snapshot, output):
    """Capture missing OCR only; the subsequent full runs verify every raster."""
    config = json.loads(config_path.read_text(encoding='utf-8'))
    source = (base.BASE / config['input']).resolve()
    if base.sha(source) != config['input_sha256']:
        raise ValueError('Source hash mismatch')
    cached = load_snapshot(snapshot, config, config_path)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Snapshot output must be new or empty')
    language = base.BASE / config['ocr']['data']
    if base.sha(language) != config['ocr']['data_sha256']:
        raise ValueError('Language data hash mismatch')
    added = []
    with tempfile.TemporaryDirectory(prefix='kidet-full-ocr-') as temp, base.pymupdf.open(source) as doc:
        if not str(temp).isascii():
            raise ValueError('OCR requires an ASCII temporary path')
        shutil.copyfile(language, Path(temp) / 'eng.traineddata')
        if len(doc) != config['expected_pages']:
            raise ValueError('Unexpected page count')
        for page in doc:
            native = base.line_records(page)
            clean, _ = base.clean_lines(native, page.rect.height)
            body = '\n\n'.join(b['text'] for b in base.blocks_from_lines(clean))
            number = page.number + 1
            if needs_ocr(page, native, body, cached) and number not in cached:
                lines, digest = base.full_ocr_lines(page, temp, config['ocr']['dpi'], config['ocr']['language'])
                cached[number] = {'pdf_page': number, 'method': 'tesseract_full_page', 'raster_sha256': digest, 'lines': lines}
                added.append(number)
    if base.sha(source) != config['input_sha256']:
        raise ValueError('Source changed during OCR')
    output.mkdir(parents=True, exist_ok=True)
    base.write(output / 'pages.jsonl', ''.join(base.jsonline(cached[n]) for n in sorted(cached)))
    base.dump(output / 'manifest.json', {
        'source_sha256': config['input_sha256'], 'config_sha256': base.sha(config_path),
        'ocr_data_sha256': config['ocr']['data_sha256'], 'capture_pymupdf_version': base.pymupdf.VersionBind,
        'status': 'OCR_TRANSCRIPT_FIXED_NOT_REVIEWED', 'page_count': len(cached), 'llm_used': False,
        'parent_snapshot_sha256': base.sha(snapshot / 'manifest.json'), 'added_pages': added,
        'extension_program_sha256': base.sha(Path(__file__)), 'ocr_worker_sha256': base.sha(base.BASE / 'ocr_worker.py'),
        'files': {'pages.jsonl': base.sha(output / 'pages.jsonl')},
    })
    print(json.dumps({'complete': True, 'added_pages': added, 'snapshot_pages': len(cached)}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=base.BASE / 'config.json')
    parser.add_argument('--snapshot', type=Path, default=base.BASE / 'assets/ocr-snapshot')
    parser.add_argument('--capture-missing-ocr', action='store_true')
    parser.add_argument('--extend-snapshot-only', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.extend_snapshot_only:
        extend_snapshot(args.config.resolve(), args.snapshot.resolve(), args.output.resolve())
    else:
        run(args.config.resolve(), args.snapshot.resolve(), args.output.resolve(), args.capture_missing_ocr)
