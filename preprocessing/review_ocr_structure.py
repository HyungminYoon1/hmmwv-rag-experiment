"""Audit every in-scope OCR record against PDF geometry without changing inputs.

Detected rectangles are evidence candidates, not approved diagnostic relations.
The program records all unmapped characters and does not clear corpus reviews.
"""
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys

from corpus.common import BASE, ROOT, SourceStore, read_json, read_jsonl, sha, write_json, write_jsonl

sys.path.insert(0, str(BASE/'assets/ocr-layout-tools'))
import cv2
import numpy as np
import pymupdf

DEST = BASE/'ocr-structure-review-20260924'
CAPTURES = [BASE/'corpus/reports/rules-v4-work/ocr-words-all', DEST/'ocr-words-remaining']


def inside(a, b, tolerance=1.5):
    return (b[0]-tolerance <= a[0] and b[1]-tolerance <= a[1]
            and a[2] <= b[2]+tolerance and a[3] <= b[3]+tolerance)


def rectangles(page):
    dpi = 144
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, alpha=False)
    gray = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    ink = cv2.threshold(gray, 195, 255, cv2.THRESH_BINARY_INV)[1]
    # Close small scan gaps perpendicular to a line before measuring length.
    h = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((3, 1), np.uint8))
    h = cv2.morphologyEx(h, cv2.MORPH_OPEN, np.ones((1, 70), np.uint8))
    v = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((1, 3), np.uint8))
    v = cv2.morphologyEx(v, cv2.MORPH_OPEN, np.ones((25, 1), np.uint8))
    borders = cv2.morphologyEx(h | v, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    contours = cv2.findContours(borders, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[0]
    found = []
    for c in contours:
        x, y, w, height = cv2.boundingRect(c)
        ratio = cv2.contourArea(c)/(w*height)
        if not (w >= 55 and height >= 16 and w < pix.width*.95 and height < pix.height*.92 and ratio >= .84):
            continue
        box = [round(x/2, 2), round(y/2, 2), round((x+w)/2, 2), round((y+height)/2, 2)]
        if not any(max(abs(a-b) for a,b in zip(box,r['bbox'])) < 4 for r in found):
            found.append({'bbox': box, 'rectangularity': round(ratio, 4), 'area': w*height/4})
    found.sort(key=lambda r: (r['bbox'][1], r['bbox'][0], r['area']))
    for i, r in enumerate(found):
        r['id'] = f'B{i+1:03d}'
    return found


def word_mapping(store, pn, capture):
    rid = f'P{pn:04d}:ocr'
    lookup = defaultdict(list)
    for line in capture['lines']:
        # SourceStore's original record has only outer line whitespace stripped.
        # Shift offsets by that explicit normalization; preserve every word.
        lookup[(tuple(line['bbox']), line['text'].strip())].append(line)
    mapped, changed = [], []
    for a,b,box,_,_ in store.lines[rid]:
        text = store.before[rid]['text'][a:b]
        matches = lookup.get((tuple(box), text), [])
        if len(matches) != 1:
            changed.append({'raw_start':a,'raw_end':b,'text':text,'bbox':box,
                            'reason':'FROZEN_LINE_AND_CAPTURE_TEXT_OR_BBOX_MISMATCH'})
            continue
        leading = len(matches[0]['text'])-len(matches[0]['text'].lstrip())
        for w in matches[0]['words']:
            left=max(w['start'],leading)
            right=min(w['end'],leading+len(text))
            if left >= right:continue
            word_text=matches[0]['text'][left:right]
            start, end = a+left-leading, a+right-leading
            assert a <= start < end <= b
            assert store.before[rid]['text'][start:end] == word_text
            mapped.append({'raw_start':start,'raw_end':end,'text':word_text,
                           'bbox':w['bbox'],'confidence':w['confidence'],
                           'line_edge_whitespace_removed':len(w['text'])-len(word_text)})
    covered = set(i for w in mapped for i in range(w['raw_start'],w['raw_end']))
    missing = sum(not ch.isspace() and i not in covered for i,ch in enumerate(store.before[rid]['text']))
    return mapped, changed, missing


def classify(ref, words, raw_text):
    if any(s['correction_id'] for s in ref['raw_spans']):
        return {'class':'CORRECTION_REGION_REQUIRES_REVIEWED_COORDINATES','box_ids':[]}
    ranges = [(s['start'],s['end']) for s in ref['raw_spans']]
    relevant = [w for w in words if any(a <= w['raw_start'] and w['raw_end'] <= b for a,b in ranges)]
    covered = {i for w in relevant for i in range(w['raw_start'],w['raw_end'])}
    expected = {i for a,b in ranges for i in range(a,b) if not raw_text[i].isspace()}
    complete = covered == expected
    ids = sorted({w['box_id'] for w in relevant if w['box_id']})
    unboxed = [w for w in relevant if not w['box_id']]
    if not complete:
        status = 'INCOMPLETE_EXACT_WORD_MAPPING'
    elif not ids:
        status = 'NO_CLOSED_RECTANGLE_MATCH'
    elif unboxed:
        status = 'BOX_AND_UNBOXED_TEXT'
    elif len(ids) > 1:
        status = 'MULTIPLE_RECTANGLES'
    else:
        status = 'SINGLE_RECTANGLE'
    return {'class':status,'box_ids':ids,'word_count':len(relevant),
            'unboxed_words':[w['text'] for w in unboxed],'mapping_complete':complete}


def main(output, pages=None, render=False):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Use a new audit folder')
    output.mkdir(parents=True)
    store = SourceStore()
    all_pages = sorted(r['pdf_page'] for r in store.records.values() if r['layer']=='ocr' and r['in_scope'])
    targets = all_pages if pages is None else pages
    capture_paths = {}
    for folder in CAPTURES:
        for p in folder.glob('page-*.json'):
            pn = int(p.stem.rsplit('-',1)[1])
            if pn in capture_paths:raise ValueError('Duplicate coordinate capture')
            capture_paths[pn] = p
    missing_captures = sorted(set(targets)-set(capture_paths))
    if missing_captures:raise ValueError('Missing word-coordinate pages: '+str(missing_captures))
    ledger = read_jsonl(BASE/'output/corpus-v4-rules-c/selection_ledger.jsonl')
    reviews = read_jsonl(BASE/'output/corpus-v4-rules-c/review_queue.jsonl')
    per_page = defaultdict(Counter)
    review_counts = defaultdict(Counter)
    for r in ledger:
        if r['layer']=='ocr':per_page[r['pdf_page']][r['status']] += len(r['text'])
    for r in reviews:review_counts[r['pdf_page']][r['code']] += 1
    pdf = pymupdf.open(ROOT/store.config['source_pdf'])
    census, all_reviews, changed_lines = [], [], []
    for ni,pn in enumerate(targets):
        capture = read_json(capture_paths[pn]);assert capture['raster_matches_frozen']
        boxes = rectangles(pdf[pn-1])
        words, changed, unmapped = word_mapping(store,pn,capture)
        for w in words:
            hits = [r for r in boxes if inside(w['bbox'],r['bbox'])]
            hit = min(hits,key=lambda r:r['area']) if hits else None
            w['box_id'] = hit['id'] if hit else None
        for b in boxes:
            b['words'] = [w for w in words if w['box_id']==b['id']]
            b['text'] = ' '.join(w['text'] for w in sorted(b['words'],key=lambda w:w['raw_start']))
            b['reading_order'] = 'ORIGINAL_OFFSETS_FILTERED_TO_RECTANGLE_NOT_SEMANTICALLY_APPROVED'
        header = ' '.join(l['text'] for l in capture['lines'] if l['bbox'][1] < 125).upper()
        native = store.records.get(f'P{pn:04d}:native',{}).get('text','')
        full = capture['raw_text'].upper()
        if 'KNOWN INFO' in full or 'TEST OPTIONS' in full:kind='DIAGNOSTIC_PANEL'
        elif 'DIAGNOSTIC FLOWCHART' in header:kind='FREE_FLOWCHART'
        elif 'REFERENCE INFORMATION' in header or 'REFERENCE INFORMATION' in native[:250]:kind='REFERENCE_PAGE'
        elif 95 <= pn <= 121:kind='PMCS_OR_MAINTENANCE'
        elif pn in (60,272,276,300,531,532,533,830,854,855,856):kind='TABLE_OR_TABLE_WITH_FIGURE'
        else:kind='TEXT_FIGURE_OR_LABELS'
        page_reviews=[]
        for r in reviews:
            if r['pdf_page'] != pn:continue
            for ref in r['source_refs']:
                if ref['layer']!='ocr' or ref['pdf_page']!=pn:continue
                item={'review_id':r['id'],'review_code':r['code'],'pdf_page':pn,
                      'source':ref,**classify(ref,words,store.before[ref['record_id']]['text'])}
                page_reviews.append(item)
        stats=Counter(r['class'] for r in page_reviews)
        item={'pdf_page':pn,'family_candidate':kind,'selection_characters':dict(per_page[pn]),
              'existing_review_counts':dict(review_counts[pn]),'geometry_review_counts':dict(stats),
              'closed_rectangles':len(boxes),'mapped_words':len(words),'unmapped_nonspace_raw_characters':unmapped,
              'changed_rerun_line_count':len(changed),'capture_file':capture_paths[pn].relative_to(ROOT).as_posix(),
              'capture_sha256':sha(capture_paths[pn]),'native_characters':len(native),
              'ocr_characters':len(store.records[f'P{pn:04d}:ocr']['text']),
              'known_info_count':full.count('KNOWN INFO'),'test_options_count':full.count('TEST OPTIONS'),
              'visual_review':'NOT_YET_RECORDED','corpus_modified':False}
        write_json(output/f'page-{pn:04d}.json',{'summary':item,'rectangles':boxes,'words':words,'reviews':page_reviews,'changed_lines':changed})
        if render:
            annotated=pymupdf.open();annotated.insert_pdf(pdf,from_page=pn-1,to_page=pn-1);p=annotated[0]
            for b in boxes:
                p.draw_rect(pymupdf.Rect(b['bbox']),color=(0.85,0.15,0.15),width=.55)
                p.insert_text((b['bbox'][0]+1,b['bbox'][1]+6),b['id'],fontsize=5,color=(0.85,0.05,0.05))
            p.get_pixmap(dpi=110,alpha=False).save(output/f'page-{pn:04d}-geometry.png');annotated.close()
        census.append(item);all_reviews+=page_reviews
        changed_lines += [{'pdf_page':pn,**c} for c in changed]
        if ni%25==0 or ni+1==len(targets):print(json.dumps({'audited':ni+1,'total':len(targets),'page':pn}),flush=True)
    write_jsonl(output/'page-census.jsonl',census)
    write_jsonl(output/'review-classification.jsonl',all_reviews)
    write_jsonl(output/'rerun-line-differences.jsonl',changed_lines)
    write_json(output/'summary.json',{'scope_ocr_pages':len(all_pages),'audited_pages':len(targets),
       'scope_pdf_pages':[31,863],'families':dict(Counter(r['family_candidate'] for r in census)),
       'review_classification':dict(Counter(r['class'] for r in all_reviews)),
       'pages_with_rerun_line_differences':[r['pdf_page'] for r in census if r['changed_rerun_line_count']],
       'rectangle_geometry_is_not_semantic_approval':True,'corpus_modified':False,'reviews_cleared':0,
       'source_pdf_sha256':sha(ROOT/store.config['source_pdf']),'script_sha256':sha(Path(__file__)),
       'dependencies':{'opencv':cv2.__version__,'numpy':np.__version__,'pymupdf':pymupdf.__version__}})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--pages',help='Comma-separated subset for profile development')
    parser.add_argument('--render',action='store_true')
    args=parser.parse_args()
    main(args.output,[int(x) for x in args.pages.split(',')] if args.pages else None,args.render)
