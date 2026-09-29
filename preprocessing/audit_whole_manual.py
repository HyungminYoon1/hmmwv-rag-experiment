"""Inventory every PDF page and extraction disagreement without changing text."""
from __future__ import annotations
import argparse
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import re
import sys
import pymupdf
import correct_extraction as io

PATTERN = re.compile(r'\b(?:lf|lt|lN|lS|lT|FlRST|systern|systam|currant|Teat|Pre-Test Procedureas)\b')


def normalize(s):
    return re.sub(r'\s+', ' ', s).strip().replace('’', "'").replace('“', '"').replace('”', '"')


def line_positions(page, layer):
    offset = 0
    for block in page[layer + '_blocks']:
        for line in block['lines']:
            yield offset, line
            offset += len(line['text']) + 1
        offset += 1


def overlap(a, b):
    dx = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    dy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return dx / max(1, min(a[2] - a[0], b[2] - b[0])), dy / max(1, min(a[3] - a[1], b[3] - b[1]))


def run(out):
    if out.exists():
        raise ValueError('Use a new inventory folder')
    out.mkdir(parents=True)
    (out / 'pages').mkdir()
    config = json.loads((io.BASE / 'config.json').read_text(encoding='utf-8'))
    pdf = (io.BASE / config['input']).resolve()
    assert io.sha(pdf) == config['input_sha256']
    source = io.BASE / 'output/full-manual-v2-a/pages.jsonl'
    parsed = io.load_records(source)
    existing = json.loads((io.BASE / 'corrections/batch-001/correction-log.json').read_text(encoding='utf-8'))
    signals = io.load_records(io.BASE / 'output/full-manual-v2-a/review_signals.jsonl')
    signal_counts = Counter(r['pdf_page'] for r in signals)
    inventory, candidates, alignments, table_candidates = [], [], [], []
    with pymupdf.open(pdf) as doc:
        for p in parsed:
            n = p['pdf_page']; page = doc[n - 1]
            assert n == page.number + 1
            text = p['native_body_text'] + '\n' + (p['ocr_body_text'] or '')
            captions = list(dict.fromkeys(line.strip() for line in text.splitlines()
                           if re.match(r'^\s*(?:Table|TABLE|Chart|CHART)\s+\d+[.-]\d+', line)))
            grids, grid_error = [], None
            try:
                finder = page.find_tables(strategy='lines_strict')
                for t in finder.tables:
                    if t.row_count >= 2 and t.col_count >= 2:
                        grids.append({'bbox': list(t.bbox), 'rows': t.row_count, 'columns': t.col_count,
                                      'cells': t.extract()})
            except Exception as exc:
                grid_error = type(exc).__name__ + ': ' + str(exc)
            if captions or grids or p['tables']:
                table_candidates.append({'pdf_page': n, 'captions': captions, 'grids': grids,
                                         'pmcs_rows': [t['row_id'] for t in p['tables']],
                                         'status': 'CANDIDATE_NOT_CONFIRMED_TABLE'})
            for layer in ('native', 'ocr'):
                for offset, line in line_positions(p, layer):
                    for m in PATTERN.finditer(line['text']):
                        candidates.append({'id': f'TEXT-{len(candidates)+1:05d}', 'pdf_page': n,
                                           'record_id': f'P{n:04d}:{layer}', 'start': offset + m.start(),
                                           'end': offset + m.end(), 'before': m.group(),
                                           'context': line['text'], 'bbox': line['bbox'],
                                           'status': 'NEEDS_PDF_VISUAL_CHECK'})
            ocr_lines = list(line_positions(p, 'ocr'))
            for offset, line in line_positions(p, 'native'):
                if len(line['text']) < 12:
                    continue
                matches = []
                for ooffset, other in ocr_lines:
                    x, y = overlap(line['bbox'], other['bbox'])
                    if x >= .7 and y >= .55:
                        a, b = normalize(line['text']), normalize(other['text'])
                        score = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
                        if .70 <= score < 1:
                            matches.append((score, other))
                if matches:
                    score, other = max(matches, key=lambda m: m[0])
                    alignments.append({'id': f'ALIGN-{len(alignments)+1:05d}', 'pdf_page': n,
                                       'record_id': f'P{n:04d}:native', 'offset': offset,
                                       'native': line['text'], 'ocr': other['text'], 'bbox': line['bbox'],
                                       'similarity': score, 'status': 'DISAGREEMENT_NOT_AUTOMATIC_CORRECTION'})
            inventory.append({'pdf_page': n, 'printed_page': p['printed_page'], 'in_scope': p['in_scope'],
                              'native_chars': len(p['native_body_text']), 'ocr_chars': len(p['ocr_body_text'] or ''),
                              'review_signals': signal_counts[n], 'caption_candidates': captions,
                              'grid_candidates': len(grids), 'grid_detection_error': grid_error,
                              'pmcs_rows': len(p['tables']), 'page_flags': p['review_flags'],
                              'review_status': 'AUTOMATIC_SCREEN_COMPLETE_NOT_FULL_TEXT_CERTIFICATION'})
            if captions or p['tables'] or n in list(range(60,66)) + list(range(830,860)) + [277,300,868,869,870,871,887,888]:
                page.get_pixmap(dpi=120, alpha=False).save(out / 'pages' / f'page-{n:03d}.png')
            if n % 50 == 0:
                print(json.dumps({'pages_screened': n, 'table_candidate_pages': len(table_candidates)}), flush=True)
    for name, records in [('page-audit.jsonl', inventory), ('text-candidates.jsonl', candidates),
                          ('native-ocr-disagreements.jsonl', alignments), ('table-candidates.jsonl', table_candidates)]:
        (out / name).write_bytes(io.records_bytes(records))
    summary = {'pages_screened': len(inventory), 'scope_pages': sum(r['in_scope'] for r in inventory),
               'text_candidates': len(candidates), 'native_ocr_disagreements': len(alignments),
               'table_candidate_pages': [r['pdf_page'] for r in table_candidates],
               'grid_detection_errors': [r['pdf_page'] for r in inventory if r['grid_detection_error']],
               'source_pdf_sha256': io.sha(pdf), 'source_pages_sha256': io.sha(source),
               'previous_ledger_sha256': io.sha(io.BASE / 'corrections/batch-001/correction-log.json'),
               'pymupdf': pymupdf.VersionBind, 'program_sha256': io.sha(__file__),
               'evaluation_questions_read': False, 'automatic_content_corrections': 0}
    (out / 'summary.json').write_bytes(io.json_bytes(summary))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
