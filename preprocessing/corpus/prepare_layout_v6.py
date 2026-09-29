"""Freeze exact OCR word coordinates; never substitute OCR rerun text.

Layout labels here are candidates. Acceptance is recorded separately after
source checks. Existing tables and individually reviewed boxes take priority.
"""
from collections import defaultdict, Counter
from pathlib import Path
import shutil
from .common import SourceStore, BASE, ROOT, PACKAGE, read_json, write_json, write_jsonl, union_box


def initialize():
    rules=PACKAGE/'rules/v6'
    if rules.exists():
        raise ValueError('Use a new rules version')
    shutil.copytree(PACKAGE/'rules/v5-final', rules)
    config=read_json(PACKAGE/'config.json')
    config.update(corpus_version='hmmwv-v6',rules_path='rules/v6')
    write_json(PACKAGE/'config.json',config)


def prepare():
    s=SourceStore(check=False)
    rules=PACKAGE/s.config['rules_path']
    rows=[]; reports=[]; inputs=[]
    for path in sorted((BASE/'ocr-structure-review-20260924/full-audit-e').glob('page-*.json')):
        a=read_json(path); pn=a['summary']['pdf_page']; rid=f'P{pn:04d}:ocr'
        rectangles={r['id']:r for r in a['rectangles']}
        right_edges=[r['bbox'][0] for r in a['rectangles'] if 315<r['bbox'][0]<420 and
                     r['bbox'][2]-r['bbox'][0]>100 and 1500<r['area']<150000]
        reference_edge=min(right_edges) if right_edges else 335
        inputs.append(path.relative_to(ROOT).as_posix())
        raw=s.before[rid]['text']; fixed=s.records[rid]['text']
        mapped=[]; skipped=[]
        for word in a['words']:
            rs,re=word['raw_start'],word['raw_end']
            if raw[rs:re]!=word['text']:
                raise ValueError(f'Frozen word mismatch {pn}: {rs}')
            run=next((r for r in s.runs[rid] if r[2]<=rs and re<=r[3] and r[4] is None),None)
            if run is None:
                skipped.append([rs,re]);continue
            cs=run[0]+rs-run[2]; ce=cs+re-rs
            if fixed[cs:ce]!=word['text']:raise ValueError('Correction mapping')
            box=word['bbox']; cx=(box[0]+box[2])/2
            family=a['summary']['family_candidate']
            rect=rectangles.get(word['box_id'])
            broad=rect and (rect['bbox'][2]-rect['bbox'][0]>245 or rect['area']>50000)
            if box[1]<125 and family=='DIAGNOSTIC_PANEL':
                group='header-'+('left' if cx<175 else 'flow' if cx<365 else 'right')
            elif box[1]<120:
                group='header-left' if cx<320 else 'header-right'
            elif word['box_id'] and not (broad and family=='DIAGNOSTIC_PANEL'):
                group=word['box_id']
            elif family=='DIAGNOSTIC_PANEL':
                group='unboxed-'+('left' if cx<170 else 'centre' if cx<365 else 'right')
            elif family=='REFERENCE_PAGE':
                group='unboxed-'+('left' if cx<reference_edge else 'right')
            else:group='unboxed-body'
            mapped.append({'start':cs,'end':ce,'raw_start':rs,'raw_end':re,'bbox':box,'group':group})
        # Join only adjacent words from the same ORIGINAL line and region.
        # A mixed line is cut at an observed word boundary, never by character
        # counts or guessed spaces. Every literal character remains traceable.
        groups=[]
        for w in sorted(mapped,key=lambda x:x['start']):
            gap=fixed[groups[-1][-1]['end']:w['start']] if groups else ''
            if groups and groups[-1][-1]['group']==w['group'] and gap.isspace() and '\n' not in gap:
                groups[-1].append(w)
            else:groups.append([w])
        for i,words in enumerate(groups):
            start,end=words[0]['start'],words[-1]['end']
            rows.append({'id':f'XY{pn:04d}-{i+1:04d}','record_id':rid,'pdf_page':pn,
                'start':start,'end':end,'text':fixed[start:end],
                'bbox':union_box([w['bbox'] for w in words]),'group':words[0]['group'],
                'family':a['summary']['family_candidate'],'words':words,
                'evidence':path.relative_to(ROOT).as_posix(),
                'coordinate_basis':'FROZEN_OCR_WORDS_EXACT_RAW_MATCH',
                'semantic_review':False})
        reports.append({'pdf_page':pn,'family':a['summary']['family_candidate'],
                        'coordinate_spans':len(groups),'mapped_words':len(mapped),
                        'words_in_corrected_regions':len(skipped),
                        'changed_rerun_lines_not_adopted':len(a['changed_lines'])})
    write_jsonl(rules/'coordinate-spans.jsonl',rows)
    write_json(rules/'coordinate-preparation.json',{'pages':len(reports),'spans':len(rows),
               'page_results':reports,'family_counts':dict(Counter(p['family'] for p in reports)),
               'ocr_text_replaced':False,'word_geometry_is_not_semantic_approval':True})
    config=read_json(PACKAGE/'config.json')
    config['additional_inputs']=sorted(set(config['additional_inputs']+inputs))
    write_json(PACKAGE/'config.json',config)
    print({'pages':len(reports),'spans':len(rows)})


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--initialize',action='store_true');args=p.parse_args()
    if args.initialize:initialize()
    prepare()
