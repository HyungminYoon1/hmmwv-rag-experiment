"""Inspect the fixed manual without OCR, LLMs, or document modification."""
from pathlib import Path
import hashlib
import json
import re
import sys
import pymupdf

BASE = Path(__file__).resolve().parent
SOURCE = BASE.parent / '제출 논문 초안/논문참고자료/TM_9-2320-280-20-1_1996_Change2_2004_TFS_archive.pdf'
EXPECTED = '4606773be7d6914f23fa9f9d51dcdb1f4b054dea99db9cd4109fb5d412a21c7d'

def write(path, text):
    path.write_bytes(text.replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8'))

def main():
    out = BASE / 'audit'
    out.mkdir(exist_ok=True)
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if digest != EXPECTED:
        raise ValueError('Input manual hash does not match the research protocol.')
    rows = []
    raw = []
    with pymupdf.open(SOURCE) as doc:
        for page in doc:
            data = page.get_text('dict', flags=pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES)
            lines = []
            for block in data['blocks']:
                for line in block.get('lines', []):
                    spans = line['spans']
                    lines.append({'bbox': list(line['bbox']), 'text': ''.join(s['text'] for s in spans),
                                  'block': block['number'], 'fonts': sorted(set(s['font'] for s in spans)),
                                  'size': max((s['size'] for s in spans), default=0),
                                  'direction': list(line['dir'])})
            images = page.get_image_info()
            area = page.rect.width * page.rect.height
            image_areas = [(pymupdf.Rect(i['bbox']) & page.rect).get_area() / area for i in images]
            text = '\n'.join(x['text'] for x in lines)
            footer = [x['text'] for x in lines if x['bbox'][1] >= page.rect.height - 65]
            row = {'pdf_page': page.number + 1, 'width': page.rect.width, 'height': page.rect.height,
                   'chars': len(text.strip()), 'words': len(page.get_text('words')),
                   'replacement_chars': text.count('\ufffd'), 'image_count': len(images),
                   'max_image_area_ratio': round(max(image_areas, default=0), 5),
                   'fonts': sorted({f for x in lines for f in x['fonts']}),
                   'footer': footer, 'head': [x['text'] for x in lines[:5]]}
            rows.append(row)
            raw.append({'pdf_page': page.number + 1, 'width': page.rect.width, 'height': page.rect.height,
                        'lines': lines, 'words': [list(w) for w in page.get_text('words')],
                        'image_bboxes': [list(x['bbox']) for x in images]})
        meta = {'input_sha256': digest, 'page_count': len(doc), 'pymupdf': pymupdf.VersionBind,
                'pdf_metadata': doc.metadata, 'ocr_used': False, 'llm_used': False,
                'pages_without_text': [r['pdf_page'] for r in rows if r['chars'] == 0],
                'pages_below_200_chars': [r['pdf_page'] for r in rows if r['chars'] < 200],
                'pages_full_page_image': [r['pdf_page'] for r in rows if r['max_image_area_ratio'] >= .85],
                'replacement_char_count': sum(r['replacement_chars'] for r in rows)}
    write(out / 'pages.jsonl', ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in rows))
    write(out / 'raw_pages.jsonl', ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in raw))
    write(out / 'inspection.json', json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    print(json.dumps(meta, ensure_ascii=False))

if __name__ == '__main__':
    main()
