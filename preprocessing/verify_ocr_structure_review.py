"""Independently verify full OCR audit coverage and exact coordinate provenance."""
from pathlib import Path
from collections import Counter, defaultdict
import argparse
from corpus.common import BASE, ROOT, SourceStore, read_json, read_jsonl, write_json, sha


def verify(folder):
    folder=Path(folder).resolve();store=SourceStore();checks=0;errors=[]
    def check(condition,code,detail):
        nonlocal checks
        checks+=1
        if not condition:errors.append({'code':code,'detail':detail})
    expected={r['pdf_page'] for r in store.records.values() if r['layer']=='ocr' and r['in_scope']}
    census=read_jsonl(folder/'page-census.jsonl');actual=[r['pdf_page'] for r in census]
    check(len(actual)==len(set(actual)),'DUPLICATE_PAGE','page-census')
    check(set(actual)==expected,'SCOPE_COVERAGE',sorted(expected-set(actual)))
    expected_refs=[]
    for review in read_jsonl(BASE/'output/corpus-v4-rules-c/review_queue.jsonl'):
        for ref in review['source_refs']:
            if ref['layer']=='ocr' and ref['pdf_page'] in expected and ref['pdf_page']==review['pdf_page']:
                expected_refs.append((review['id'],ref['record_id'],ref['start'],ref['end']))
    actual_refs=[]
    for row in census:
        pn=row['pdf_page'];data=read_json(folder/f'page-{pn:04d}.json')
        raw=store.before[f'P{pn:04d}:ocr']['text']
        check(row==data['summary'],'PAGE_SUMMARY',pn)
        capture_path=ROOT/row['capture_file'];capture=read_json(capture_path)
        check(sha(capture_path)==row['capture_sha256'],'CAPTURE_HASH',pn)
        capture_lines=defaultdict(list)
        for line in capture['lines']:capture_lines[(line['text'].strip(),tuple(line['bbox']))].append(line)
        expected_words={}
        for a,b,bbox,_,_ in store.lines[f'P{pn:04d}:ocr']:
            matching=capture_lines.get((raw[a:b],tuple(bbox)),[])
            if len(matching)==1:
                leading=len(matching[0]['text'])-len(matching[0]['text'].lstrip())
                for w in matching[0]['words']:
                    ws=max(w['start']-leading,0);we=min(w['end']-leading,b-a)
                    if ws < we:
                        expected_words[(a+ws,a+we)]={**w,'expected_text':matching[0]['text'][ws+leading:we+leading]}
        check({(w['raw_start'],w['raw_end']) for w in data['words']}==set(expected_words),'ALL_EXACT_WORDS_PRESENT',pn)
        box_ids={r['id'] for r in data['rectangles']}
        boxes={r['id']:r for r in data['rectangles']}
        for w in data['words']:
            check(raw[w['raw_start']:w['raw_end']]==w['text'],'WORD_SOURCE_TEXT',pn)
            check(w['box_id'] is None or w['box_id'] in box_ids,'WORD_BOX_TARGET',pn)
            original=expected_words.get((w['raw_start'],w['raw_end']))
            check(original is not None and w['bbox']==original['bbox'] and w['confidence']==original['confidence'],'WORD_OCR_COORDINATES',pn)
            check(original is not None and w['text']==original['expected_text'] and len(original['text'])-len(w['text'])==w['line_edge_whitespace_removed'],'WORD_CAPTURE_TEXT',pn)
            if w['box_id'] in boxes:
                a=w['bbox'];b=boxes[w['box_id']]['bbox']
                check(b[0]-1.5<=a[0] and b[1]-1.5<=a[1] and a[2]<=b[2]+1.5 and a[3]<=b[3]+1.5,'WORD_INSIDE_RECORDED_BOX',pn)
        for box in data['rectangles']:
            b=box['bbox'];width,height=capture['page_rect'][2:]
            check(0<=b[0]<b[2]<=width and 0<=b[1]<b[3]<=height,'BOX_PAGE_BOUNDS',pn)
            check(box['words']==[w for w in data['words'] if w['box_id']==box['id']],'BOX_WORD_MEMBERSHIP',pn)
        covered={i for w in data['words'] for i in range(w['raw_start'],w['raw_end'])}
        missing=sum(not c.isspace() and i not in covered for i,c in enumerate(raw))
        check(missing==row['unmapped_nonspace_raw_characters'],'UNMAPPED_CHARACTERS',pn)
        check(row['corpus_modified'] is False,'READ_ONLY_AUDIT',pn)
        for r in data['reviews']:
            ref=r['source'];actual_refs.append((r['review_id'],ref['record_id'],ref['start'],ref['end']))
            current=store.records[ref['record_id']]['text'][ref['start']:ref['end']]
            check(ref['text']==current,'REVIEW_SOURCE_TEXT',r['review_id'])
            if r['class']=='CORRECTION_REGION_REQUIRES_REVIEWED_COORDINATES':
                check(any(s['correction_id'] for s in ref['raw_spans']),'CORRECTION_CLASS',r['review_id']);continue
            relevant=[w for w in data['words'] if any(s['start']<=w['raw_start'] and w['raw_end']<=s['end'] for s in ref['raw_spans'])]
            needed={i for s in ref['raw_spans'] for i in range(s['start'],s['end']) if not raw[i].isspace()}
            present={i for w in relevant for i in range(w['raw_start'],w['raw_end'])}
            check(r['mapping_complete']==(needed==present),'EXACT_MAPPING_FLAG',r['review_id'])
            check(r['box_ids']==sorted({w['box_id'] for w in relevant if w['box_id']}),'RECTANGLE_MEMBERSHIP',r['review_id'])
    check(Counter(actual_refs)==Counter(expected_refs),'ALL_OCR_REVIEW_REFS_ACCOUNTED',len(expected_refs))
    summary=read_json(folder/'summary.json')
    check(summary['audited_pages']==len(expected),'SUMMARY_COUNT',len(expected))
    check(summary['reviews_cleared']==0,'NO_AUTOMATIC_REVIEW_CLEARING',summary['reviews_cleared'])
    report={'status':'PASS' if not errors else 'FAIL','checks':checks,'errors':errors,
            'scope_ocr_pages':len(expected),'review_refs':len(expected_refs),
            'semantic_correctness_certified':False,'review_diagnosis_only':True,
            'verifier_sha256':sha(Path(__file__))}
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path);p.add_argument('--report',required=True,type=Path)
    args=p.parse_args();result=verify(args.folder);write_json(args.report,result)
    print(result)
    raise SystemExit(result['status']!='PASS')
