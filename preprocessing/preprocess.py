"""Offline PDF extraction and audit, with deterministic conventional OCR.

This is an intermediate extraction dataset, not a frozen RAG corpus. OCR text
and diagram reading order are never silently accepted as reviewed evidence.
No LLM, generative API, model inference, embedding or translation is used.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import html
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile

# OpenMP must see the setting before the native OCR library is loaded.
os.environ['OMP_THREAD_LIMIT'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
import pymupdf

BASE = Path(__file__).resolve().parent
COLUMNS = ['ITEM NO.', 'INTERVAL', 'ITEM TO BE INSPECTED',
           'PROCEDURES', 'NOT FULLY MISSION CAPABLE IF']


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8'))


def dump(path: Path, data) -> None:
    write(path, json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def jsonline(data) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True) + '\n'


def line_records(page, textpage=None):
    flags = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES
    data = page.get_text('dict', flags=flags, textpage=textpage)
    lines = []
    for block in data['blocks']:
        for number, line in enumerate(block.get('lines', [])):
            lines.append({
                'bbox': [round(v, 4) for v in line['bbox']],
                'text': ''.join(s['text'] for s in line['spans']),
                'block': block['number'], 'line': number,
                'fonts': sorted({s['font'] for s in line['spans']}),
                'direction': list(line['dir']),
            })
    return lines


def margin_label(text):
    value = re.sub(r'[\s\x00-\x1f\x7f]+', '', text)
    value = re.sub(r'Change[12]', '', value)
    match = re.fullmatch(r'([123]-\d+(?:\.\d+)?)(?:[/-]?\(?[123]-\d+(?:\.\d+)?[Bb]lank\)?)?', value)
    return match.group(1) if match else None


def page_label(lines, height):
    candidates = []
    for line in lines:
        if line['bbox'][1] >= height * .85:
            # Tracking in some fonts becomes spaces, e.g. '2 - 2 6'.
            value = margin_label(line['text'])
            if value:
                candidates.append((line['bbox'][1], value))
    return max(candidates)[1] if candidates else None


def clean_lines(lines, height):
    kept, changes = [], []
    for line in lines:
        before = line['text']
        after = before.strip()
        y0, y1 = line['bbox'][1], line['bbox'][3]
        # Only recognized margin text is removed. Body text near the margin stays.
        margin = y1 < height * .09 or y0 > height * .85
        header = re.fullmatch(r'TM\s+9\s*-\s*2320\s*-\s*280\s*-\s*20\s*-\s*1', after)
        compact_margin = re.sub(r'\s+', '', after)
        footer = margin_label(after) or re.fullmatch(r'Change[12]', compact_margin)
        if margin and (header or (footer and after)):
            changes.append({'bbox': line['bbox'], 'rule': 'recognized_margin', 'before': before, 'after': ''})
            continue
        if before != after:
            changes.append({'bbox': line['bbox'], 'rule': 'outer_whitespace', 'before': before, 'after': after})
        if after:
            kept.append({**line, 'text': after})
    return kept, changes


def blocks_from_lines(lines):
    groups = {}
    for line in lines:
        groups.setdefault(line['block'], []).append(line)
    result = []
    for block, group in groups.items():
        box = [min(l['bbox'][0] for l in group), min(l['bbox'][1] for l in group),
               max(l['bbox'][2] for l in group), max(l['bbox'][3] for l in group)]
        result.append({'source_block': block, 'bbox': box,
                       'text': '\n'.join(l['text'] for l in group),
                       'lines': group})
    return sorted(result, key=lambda x: (x['bbox'][1], x['bbox'][0], x['source_block']))


def native_grid(page):
    """PMCS has five columns; derive boundaries from the actual vertical rules."""
    candidates = []
    for drawing in page.get_drawings():
        rect = drawing['rect']
        if rect.height > 25 and rect.width < 4 and 40 < rect.x0 < 590:
            candidates.append(((rect.x0 + rect.x1) / 2, rect.y0, rect.y1))
        elif rect.height > 450 and rect.width > 450 and 40 < rect.x0 < 95 and 60 < rect.y0 < 135:
            candidates += [(rect.x0, rect.y0, rect.y1), (rect.x1, rect.y0, rect.y1)]
    clustered = []
    for x, y0, y1 in sorted(candidates):
        if clustered and abs(x - clustered[-1][0]) < 4:
            old = clustered[-1]
            clustered[-1] = ((old[0] + x) / 2, min(y0, old[1]), max(y1, old[2]))
        else:
            clustered.append((x, y0, y1))
    left = [c for c in clustered if 40 < c[0] < 95 and c[2] - c[1] > 450]
    right = [c for c in clustered if 520 < c[0] < 590 and c[2] - c[1] > 450]
    if not left or not right:
        raise ValueError(f'PMCS outer border needs review: page {page.number + 1}: {clustered}')
    x0, x1 = min(c[0] for c in left), max(c[0] for c in right)
    bounds = []
    # These fixed column proportions are specific to this manual's Table 2-1.
    # Illustrations interrupt vertical rules on some pages, so use each visible
    # nearby rule where available, and retain the known proportion otherwise.
    for fraction in [0, .098, .215, .348, .737, 1]:
        target = x0 + (x1 - x0) * fraction
        near = [c[0] for c in clustered if abs(c[0] - target) < 4]
        bounds.append(round(min(near, key=lambda x: abs(x-target)) if near else target, 3))
    return bounds, max(c[2] for c in left + right)


def words_as_lines(words):
    # Keep column selection upstream; never flatten the two right-hand columns.
    rows = []
    for word in sorted(words, key=lambda w: (w[1], w[0])):
        if rows and abs(word[1] - rows[-1][0]) < 3:
            rows[-1][1].append(word)
        else:
            rows.append((word[1], [word]))
    return '\n'.join(' '.join(w[4] for w in sorted(group, key=lambda w: w[0])) for _, group in rows)


def crop_ocr(page, rect, tessdata, dpi, masks=()):
    """OCR pixels only, excluding explicitly registered illustration rectangles."""
    pix = page.get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72), clip=rect,
                          colorspace=pymupdf.csRGB, alpha=False)
    # clear_with does not change the original PDF; it whites out the crop's pixels.
    for mask in masks:
        intersect = pymupdf.Rect(mask) & rect
        if not intersect.is_empty:
            pixels = pymupdf.IRect(
                int(intersect.x0 * dpi / 72),
                int(intersect.y0 * dpi / 72),
                int(intersect.x1 * dpi / 72),
                int(intersect.y1 * dpi / 72))
            pix.clear_with(255, pixels)
    padded = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, pix.width + 40, pix.height + 40), False)
    padded.clear_with(255)
    pix.set_origin(20, 20)
    padded.copy(pix, pix.irect)
    padded.set_dpi(dpi, dpi)
    return isolated_ocr(padded, tessdata, dpi)['text']


def isolated_ocr(pix, tessdata, dpi, width=None):
    # In-process repeated OCR showed differences on identical raster inputs.
    # Feed a lossless PNG to a fresh worker, with no adaptive state shared.
    path = Path(tessdata) / 'ocr-input.png'
    pix.save(path)
    cmd = [sys.executable, '-X', 'utf8', str(BASE / 'ocr_worker.py'), str(path), tessdata, '--dpi', str(dpi)]
    if width is not None:
        cmd += ['--width', str(width)]
    else:
        cmd += ['--psm', '6']
    result = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8',
                            timeout=120, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.stderr.strip():
        # Do not suppress the OCR engine's warnings. The external run log retains them.
        print(result.stderr, file=sys.stderr, end='')
    return json.loads(result.stdout)


def full_ocr_lines(page, tessdata, dpi, language):
    """Record the actual raster supplied to OCR; use a fresh in-memory OCR PDF."""
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
    raster_hash = hashlib.sha256(pix.samples).hexdigest()
    if page.rotation:
        raise ValueError('This fixed-manual profile expects unrotated pages.')
    if language != 'eng':
        raise ValueError('This fixed-manual profile uses the pinned English OCR data.')
    return isolated_ocr(pix, tessdata, dpi, page.rect.width)['lines'], raster_hash


def pmcs_rows(page, config, tessdata):
    n = page.number + 1
    scan = config['pmcs_scanned_pages'].get(str(n))
    if scan:
        bounds = scan['columns']
        definitions = scan['rows']
        method = 'tesseract_column_crop'
        words = None
    else:
        bounds, bottom = native_grid(page)
        words = page.get_text('words')
        starts = sorted([w for w in words if bounds[0] < (w[0] + w[2]) / 2 < bounds[1]
                         and re.fullmatch(r'\d+(?:\.\d+)?', w[4])
                         and 130 < w[1] < bottom], key=lambda w: w[1])
        if not starts:
            raise ValueError(f'No PMCS item number on native page {n}')
        definitions = [{'item': w[4], 'top': w[1] - 4,
                        'bottom': starts[i + 1][1] - 4 if i + 1 < len(starts) else bottom}
                       for i, w in enumerate(starts)]
        # A page may begin with notes belonging to the continued item before its number.
        # Keep these separately. Do not guess their item association.
        if definitions[0]['top'] > 150:
            definitions.insert(0, {'item': None, 'top': 141,
                                   'bottom': definitions[0]['top']})
        method = 'native_column_coordinates'
    result = []
    for index, row in enumerate(definitions):
        fields, field_boxes = {}, {}
        for col in range(5):
            inset = 3 if scan else 1
            rect = pymupdf.Rect(bounds[col] + inset, row['top'], bounds[col + 1] - inset, row['bottom'])
            field_boxes[COLUMNS[col]] = list(rect)
            if scan:
                fields[COLUMNS[col]] = crop_ocr(page, rect, tessdata, config['ocr']['dpi'],
                                                scan['excluded_graphic_regions'])
            else:
                selected = [w for w in words if rect.x0 <= (w[0] + w[2]) / 2 < rect.x1
                            and rect.y0 <= (w[1] + w[3]) / 2 < rect.y1]
                fields[COLUMNS[col]] = words_as_lines(selected)
        result.append({'row_id': f'P{n:04d}-T2_1-R{index+1:02d}',
                       'pdf_page': n, 'table': 'Table 2-1. Unit Level Preventive Maintenance Checks and Services HMMWV',
                       'item': row['item'], 'method': method, 'fields': fields,
                       'field_bboxes': field_boxes,
                       'review_status': 'OCR_UNREVIEWED' if scan else 'STRUCTURE_REVIEW_REQUIRED',
                       'excluded_graphic_regions': scan['excluded_graphic_regions'] if scan else []})
    return result


def compact(text):
    return re.sub(r'[^a-z0-9]', '', text.casefold())


def evidence_audit(config, pages, out):
    source = (BASE / config['evaluation_candidates']).resolve()
    candidates = json.loads(source.read_text(encoding='utf-8-sig'))
    records = []
    for q in candidates['questions']:
        for index, ev in enumerate(q['evidence_groups']):
            n = ev['pdf_page_1_based']
            p = pages[n]
            anchor = ev['anchor']
            target = compact(anchor)
            native_hit = bool(target) and target in compact(p['native_body_text'])
            table_hit = bool(target) and target in compact('\n'.join(
                value for row in p['tables'] for value in row['fields'].values()))
            ocr_hit = bool(target) and target in compact(p.get('ocr_body_text') or '')
            # An anchor hit is not proof of sufficient evidence, semantic correctness,
            # answerability, or final chunk mapping.
            status = ('OUTSIDE_INDEX_SCOPE' if not p['in_scope'] else
                      'NATIVE_ANCHOR_FOUND' if native_hit else
                      'TABLE_ANCHOR_FOUND' if table_hit else
                      'OCR_ANCHOR_FOUND_REVIEW_REQUIRED' if ocr_hit else
                      'ANCHOR_NOT_FOUND_REVIEW_REQUIRED')
            records.append({'question_id': q['id'], 'evidence_group': index + 1,
                            'pdf_page': n, 'printed_page': p['printed_page'],
                            'anchor': anchor, 'status': status,
                            'native_hit': native_hit, 'table_hit': table_hit, 'ocr_hit': ocr_hit,
                            'semantic_coverage': 'NOT_VERIFIED', 'chunk_mapping': 'PENDING'})
    write(out / 'candidate_anchor_audit.jsonl', ''.join(jsonline(r) for r in records))
    return {'input_sha256': sha(source), 'questions': len(candidates['questions']),
            'evidence_groups': len(records), 'status_counts': dict(Counter(r['status'] for r in records)),
            'all_semantic_coverage': 'NOT_VERIFIED'}


def html_report(out, records, summary):
    panels = []
    for n in summary['preview_pages']:
        p = records[n]
        table_html = ''
        for row in p['tables']:
            table_html += '<h4>' + html.escape(row['row_id']) + '</h4><table><tbody>'
            for key, value in row['fields'].items():
                table_html += f'<tr><th>{html.escape(key)}</th><td><pre>{html.escape(value)}</pre></td></tr>'
            table_html += '</tbody></table>'
        panels.append(f'''<section id="p{n}"><h2>PDF {n} / 인쇄면 {html.escape(p['printed_page'] or '확인 필요')}</h2>
<p>{html.escape(', '.join(p['review_flags']) or '자동 검사 경고 없음 — 내용 정확성 보증은 아님')}</p>
<div class="pair"><img loading="lazy" src="previews/page-{n:03d}.png" alt="교범 원문 {n}쪽">
<div><details open><summary>원래 텍스트층에서 추출한 본문</summary><pre>{html.escape(p['native_body_text'])}</pre></details>
<details><summary>페이지 OCR 결과 — 검수 전</summary><pre>{html.escape(p.get('ocr_body_text') or '이 페이지는 OCR 대상 아님')}</pre></details>
<details {'open' if p['tables'] else ''}><summary>열을 구분한 PMCS 점검표 — 검수 전</summary>{table_html}</details></div></div></section>''')
    nav = ' · '.join(f'<a href="#p{n}">{n}</a>' for n in summary['preview_pages'])
    write(out / '검토용_원문대조.html', f'''<!doctype html><html lang="ko"><meta charset="utf-8">
<title>험비 교범 전처리 원문 대조</title><style>
body{{font:16px/1.55 system-ui,sans-serif;margin:24px;color:#182333;background:#f5f7fa}}
header,section{{background:white;padding:24px;border-radius:8px;margin:18px 0}}
.pair{{display:grid;grid-template-columns:minmax(320px,1fr) minmax(320px,1fr);gap:24px;align-items:start}}
img{{width:100%;border:1px solid #ccc}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.5 ui-monospace,monospace}}
table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid #bbb;padding:8px;vertical-align:top;text-align:left}}th{{width:28%}}
summary{{cursor:pointer;font-weight:bold}}details{{margin-bottom:20px}}
@media(max-width:900px){{.pair{{grid-template-columns:1fr}}}}</style>
<header><h1>험비 교범 전처리 원문 대조</h1>
<p>LLM 없이 PyMuPDF와 Tesseract OCR로 생성한 중간 자료입니다. 원문은 변경하지 않았습니다.
OCR은 글자를 읽을 뿐 회로 연결·화살표·절차 분기를 판정하지 않습니다. 최종 검색 corpus와 정답 근거 대응표는 아직 확정하지 않았습니다.</p>
<p>확인용 표본 {len(summary['preview_pages'])}쪽. 교범 전체를 시각 검수한 자료는 아닙니다.</p><nav>{nav}</nav></header>
{''.join(panels)}</html>''')


def run(config_path, out):
    config = json.loads(config_path.read_text(encoding='utf-8'))
    source = (BASE / config['input']).resolve()
    if sha(source) != config['input_sha256']:
        raise ValueError('Original PDF hash mismatch')
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output directory must be empty; use a new output name to preserve previous results.')
    ocr_data = BASE / config['ocr']['data']
    if sha(ocr_data) != config['ocr']['data_sha256']:
        raise ValueError('OCR language asset hash mismatch')
    out.mkdir(parents=True, exist_ok=True)
    (out / 'previews').mkdir(exist_ok=True)
    pages, review, modifications, all_tables = {}, [], [], []
    raw_native = (out / 'raw_native_pages.jsonl').open('w', encoding='utf-8', newline='\r\n')
    raw_ocr = (out / 'raw_ocr_pages.jsonl').open('w', encoding='utf-8', newline='\r\n')
    normalized = (out / 'pages.jsonl').open('w', encoding='utf-8', newline='\r\n')
    try:
        # Tesseract's fopen on this Windows build cannot use Korean paths.
        # Use an ASCII temp copy of the *same hash-verified* language file.
        with tempfile.TemporaryDirectory(prefix='kidet-ocr-') as tmp, pymupdf.open(source) as doc:
            if not str(tmp).isascii():
                raise ValueError('Tesseract requires an ASCII TEMP path on this Windows build.')
            shutil.copyfile(ocr_data, Path(tmp) / 'eng.traineddata')
            if len(doc) != config['expected_pages']:
                raise ValueError('PDF page count mismatch')
            for page in doc:
                n = page.number + 1
                native_lines = line_records(page)
                images = page.get_image_info()
                raw_native.write(jsonline({'pdf_page': n, 'width': page.rect.width, 'height': page.rect.height,
                                           'lines': native_lines, 'words': [list(w) for w in page.get_text('words')],
                                           'image_bboxes': [[round(v, 4) for v in im['bbox']] for im in images]}))
                clean, changes = clean_lines(native_lines, page.rect.height)
                blocks = blocks_from_lines(clean)
                body = '\n\n'.join(b['text'] for b in blocks)
                in_scope = config['scope_pdf_pages'][0] <= n <= config['scope_pdf_pages'][1]
                flags = []
                if in_scope and images:
                    flags.append('IMAGE_CONTENT_NOT_SEMANTICALLY_RECONSTRUCTED')
                if in_scope and len(body) < config['ocr']['native_body_chars_below'] and images:
                    flags.append('LOW_NATIVE_TEXT_WITH_IMAGES')
                if not body and not images:
                    flags.append('BLANK_PAGE')
                ocr_used = (in_scope and config['ocr']['enabled'] and
                            ((len(body) < config['ocr']['native_body_chars_below'] and images)
                             or n in config['ocr']['extra_audit_pages']))
                ocr_body, ocr_blocks = None, []
                if ocr_used:
                    ocr_lines, raster_hash = full_ocr_lines(page, tmp, config['ocr']['dpi'], config['ocr']['language'])
                    raw_ocr.write(jsonline({'pdf_page': n, 'method': 'tesseract_full_page',
                                           'raster_sha256': raster_hash, 'lines': ocr_lines}))
                    cleaned_ocr, ocr_changes = clean_lines(ocr_lines, page.rect.height)
                    ocr_blocks = blocks_from_lines(cleaned_ocr)
                    ocr_body = '\n\n'.join(b['text'] for b in ocr_blocks)
                    changes += [{**c, 'layer': 'ocr'} for c in ocr_changes]
                    flags.append('OCR_UNREVIEWED')
                tables = []
                if n in config['pmcs_native_pages'] or str(n) in config['pmcs_scanned_pages']:
                    tables = pmcs_rows(page, config, tmp)
                    flags.append('TABLE_STRUCTURE_REVIEW_REQUIRED')
                if ((61 <= n <= 66 or n in [119, 120]) or
                    (not tables and any(re.search(r'(?:^Table\s+\d|\bTABLE\s*$|\bCHART\s*$)', l['text'], re.I) for l in clean))):
                    flags.append('OTHER_TABLE_LAYOUT_REVIEW_REQUIRED')
                printed = page_label(native_lines, page.rect.height)
                printed_source = 'native' if printed else None
                if not printed and ocr_used:
                    printed = page_label(ocr_lines, page.rect.height)
                    printed_source = 'ocr_unreviewed' if printed else None
                if in_scope and not printed and n != 570:
                    flags.append('PRINTED_PAGE_LABEL_REVIEW_REQUIRED')
                if in_scope and printed and not printed.startswith('1-' if n < 92 else '2-'):
                    flags.append('UNEXPECTED_PRINTED_CHAPTER_NUMBER')
                p = {'pdf_page': n, 'printed_page': printed, 'in_scope': in_scope,
                     'printed_page_source': printed_source,
                     'native_body_text': body, 'native_blocks': blocks,
                     'ocr_body_text': ocr_body, 'ocr_blocks': ocr_blocks, 'tables': tables,
                     'image_count': len(images), 'review_flags': flags,
                     'extraction_status': 'INTERMEDIATE_NOT_FROZEN',
                     'included_in_final_corpus': None}
                pages[n] = p
                normalized.write(jsonline(p))
                all_tables.extend(tables)
                modifications.extend({'pdf_page': n, 'layer': c.get('layer', 'native'), **c} for c in changes)
                if in_scope and flags:
                    review.append({'pdf_page': n, 'printed_page': printed, 'flags': flags,
                                   'native_chars': len(body), 'ocr_chars': len(ocr_body or ''),
                                   'decision': 'PENDING_SOURCE_REVIEW'})
                if n in config['preview_pages']:
                    page.get_pixmap(matrix=pymupdf.Matrix(1.25, 1.25)).save(out / 'previews' / f'page-{n:03d}.png')
                if n % 25 == 0:
                    print(f'Processed {n}/{len(doc)}', flush=True)
    finally:
        raw_native.close()
        raw_ocr.close()
        normalized.close()
    write(out / 'pmcs_table_rows.jsonl', ''.join(jsonline(r) for r in all_tables))
    write(out / 'normalization_log.jsonl', ''.join(jsonline(r) for r in modifications))
    write(out / 'review_queue.jsonl', ''.join(jsonline(r) for r in review))
    exclusions = [{'pdf_page': n, 'reason': 'OUTSIDE_CHAPTER_1_2'} for n, p in pages.items() if not p['in_scope']]
    write(out / 'outside_scope_pages.jsonl', ''.join(jsonline(r) for r in exclusions))
    scope = [p for p in pages.values() if p['in_scope']]
    summary = {
        'source_sha256': config['input_sha256'], 'source_unchanged': sha(source) == config['input_sha256'],
        'total_pages': len(pages), 'scope_pages': len(scope),
        'native_nonempty_pages': sum(bool(p['native_body_text']) for p in scope),
        'ocr_pages': sum(p['ocr_body_text'] is not None for p in scope),
        'pages_with_images': sum(p['image_count'] > 0 for p in scope),
        'blank_pages': [p['pdf_page'] for p in scope if 'BLANK_PAGE' in p['review_flags']],
        'pmcs_rows': len(all_tables), 'pmcs_ocr_rows': sum(r['method'].startswith('tesseract') for r in all_tables),
        'review_flags': dict(Counter(f for p in scope for f in p['review_flags'])),
        'preview_pages': config['preview_pages'], 'normalization_operations': len(modifications),
        'llm_used': False, 'network_used_during_run': False,
        'final_corpus_frozen': False, 'chunking_performed': False,
        'candidate_audit': evidence_audit(config, pages, out),
    }
    if not summary['source_unchanged']:
        raise ValueError('Input changed during execution')
    dump(out / 'summary.json', summary)
    html_report(out, pages, summary)
    packages = sorted((d.metadata['Name'].lower(), d.version) for d in importlib.metadata.distributions())
    manifest = {'python': platform.python_version(), 'platform': platform.platform(),
                'machine': platform.machine(), 'packages': packages,
                'pymupdf_version': pymupdf.VersionBind, 'mupdf_version': pymupdf.VersionFitz,
                'config_sha256': sha(config_path), 'program_sha256': sha(Path(__file__)),
                'ocr_worker_sha256': sha(BASE / 'ocr_worker.py'),
                'input_sha256': sha(source), 'ocr_data_sha256': sha(ocr_data),
                'ocr_threads': 1, 'ocr_process_policy': 'FRESH_PROCESS_PER_IMAGE',
                'ocr_engine': 'Tesseract 5.5.2 via tesserocr; LSTM_ONLY; learning disabled; DOTPRODUCT=generic',
                'schema_version': config['schema_version'],
                'files': {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob('*')) if p.is_file()}}
    dump(out / 'manifest.json', manifest)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=BASE / 'config.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.config.resolve(), args.output.resolve())
