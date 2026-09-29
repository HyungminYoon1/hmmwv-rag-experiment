"""Build candidate corpus, chunks, provenance and independent audit."""
from __future__ import annotations
from collections import Counter,defaultdict
from pathlib import Path
import platform
import sys

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))

from corpus.common import (SourceStore,ROOT,BASE,PACKAGE,read_jsonl,read_json,
                          write_json,write_jsonl,sha,parts_text)
from corpus.structure import Units,reviewed_tables,manual_tables
from corpus.regions import prose_units
from corpus.select_spans import select,ledger
from corpus.chunk import Chunker,ChunkingError
from corpus.serialize import chunk_record


def code_hashes():
    return {p.relative_to(PACKAGE).as_posix():sha(p) for p in sorted(PACKAGE.rglob('*'))
            if p.is_file() and p.suffix in ('.py','.json','.jsonl','.html','.js','.css')
            and not any(x in ('__pycache__','tests','reports') for x in p.relative_to(PACKAGE).parts)
            and p.name!='inputs.lock.json'}


def build(output,progress=None):
    last_report=None
    def report(stage,percent):
        nonlocal last_report
        if progress and last_report!=(stage,percent): progress({'stage':stage,'percent':percent})
        last_report=(stage,percent)
    output=Path(output).resolve()
    if output.exists():
        raise ValueError('Output directory already exists; use a new name')
    if not output.is_relative_to(ROOT) or output==ROOT:
        raise ValueError('Output must be a new directory within the project')
    report('입력 파일·해시 확인',3)
    store=SourceStore()
    units=Units(store)
    report('검토된 표와 항목 구성',15)
    reviewed_tables(store,units)
    manual_tables(store,units)
    if (PACKAGE/store.config.get('rules_path','rules/v2')/'box-units.jsonl').exists():
        from corpus.boxes import reviewed_boxes
        reviewed_boxes(store,units)
    for finding in store.table('new-review-items.jsonl'):
        store.review(finding['code'],finding['pdf_page'],finding['detail'],
                     [store.exact(r) for r in finding.get('source_refs',[])])
    report('native/OCR 구간 선택',25)
    selected=select(store)
    report('본문 구조와 출처 연결',43)
    prose_units(store,units,selected)
    selection,coverage=ledger(store)
    issues_by_page=defaultdict(list)
    for issue in store.table('source-issues.jsonl'):
        issues_by_page[issue['pdf_page']].append(issue)
    from corpus.review_resolution import resolve
    active_reviews,review_history=resolve(store,units.items)
    store.reviews=active_reviews
    units.items.sort(key=lambda u:u['order'])
    chunker=Chunker(ROOT/store.config['tokenizer_path'],store.config['max_tokens'],store.config['body_overlap_tokens'])
    chunks=[];maps=[];failures=[]
    report('Qwen tokenizer로 청킹',55)
    for i,unit in enumerate(units.items):
        unit['id']=f'U{i+1:06d}'
        unit['review_ids']=sorted(set(unit['review_ids']))
        unit['source_issues']=[iss for pn in unit['pdf_pages'] for iss in issues_by_page[pn]]
        try:
            windows=chunker.split(unit['body_text'],unit['prefix_text'])
        except ChunkingError as exc:
            rid=store.review('TOKEN_BUDGET',unit['pdf_pages'][0],str(exc),owner=unit['key'])
            unit['review_ids'].append(rid)
            failures.append({'unit_id':unit['id'],'reason':str(exc)})
            windows=[]
        for window in windows:
            rec,mapping=chunk_record(store,unit,window,len(chunks)+1)
            chunks.append(rec);maps.append(mapping)
        if i%100==0:
            report('Qwen tokenizer로 청킹',55+int(25*(i+1)/max(1,len(units.items))))
    report('선택 기록·산출물 저장',82)
    output.mkdir(parents=True)
    files={'corpus_units.jsonl':units.items,'chunks.jsonl':chunks,'source_map.jsonl':maps,
           'selection_ledger.jsonl':selection,'page_coverage.jsonl':coverage,'review_queue.jsonl':store.reviews,
           'review_history.jsonl':review_history,
           'selection_proofs.jsonl':store.selection_proofs}
    # Image region inventory is audit metadata, never an inferred caption.
    regions=[]
    for p in read_jsonl(BASE/'output/full-manual-v2-a/raw_native_pages.jsonl'):
        if not store.pages[p['pdf_page']]['in_scope']: continue
        for i,box in enumerate(p['image_bboxes']):
            regions.append({'pdf_page':p['pdf_page'],'image_index':i,'bbox':box,
                            'status':'IMAGE_RETAINED_FOR_SOURCE_REVIEW',
                            'semantic_description_generated':False})
    files['image_regions.jsonl']=regions
    for name,records in files.items(): write_jsonl(output/name,records)
    summary={'schema':2,'corpus_version':store.config['corpus_version'],
             'scope_pages':len(coverage),'units':len(units.items),'chunks':len(chunks),
             'selected_characters':sum(len(x['text']) for x in selection if x['status']=='INCLUDED'),
             'review_count':len(store.reviews),'review_pages':len({r['pdf_page'] for r in store.reviews}),
             'closed_review_count':len(review_history),
             'review_categories':dict(Counter(r['code'] for r in store.reviews)),
             'chunk_failures':failures,'max_chunk_tokens':max((c['token_count'] for c in chunks),default=0),
             'replay_invokes_llm':False,'evaluation_questions_read':False,
             'human_source_review':'NOT_PERFORMED','corpus_ready_for_index':False,
             'artifact_state':'CANDIDATE_CORPUS'}
    write_json(output/'build_summary.json',summary)
    write_json(output/'config.json',store.config)
    manifest={'schema':1,'inputs':store.lock['files'],'code':code_hashes(),
              'environment':{'python':platform.python_version(),'platform':sys.platform,
                             'tokenizers':__import__('tokenizers').__version__},
              'files':{name:sha(output/name) for name in [*files,'build_summary.json','config.json']}}
    write_json(output/'manifest.json',manifest)
    report('독립 검증',90)
    from corpus.verify import verify
    audit=verify(output,store=store)
    write_json(output/'audit.json',audit)
    summary['corpus_ready_for_index']=audit['corpus_ready_for_index']
    summary['artifact_state']='VALIDATED_TEXT_CORPUS' if audit['corpus_ready_for_index'] else 'CANDIDATE_CORPUS'
    write_json(output/'build_summary.json',summary)
    manifest['files']['build_summary.json']=sha(output/'build_summary.json')
    manifest['files']['audit.json']=sha(output/'audit.json')
    write_json(output/'manifest.json',manifest)
    report('완료: 검토 대상 확인' if store.reviews else '완료',100)
    return {'output':str(output),'summary':summary,'audit':audit}


def main():
    import argparse,json
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=build(args.output,lambda e:print(json.dumps(e,ensure_ascii=False),flush=True))
    print(json.dumps({k:result[k] for k in ('output','summary')},ensure_ascii=False,indent=2))
    # Review-required is a valid draft build, but never a successful freeze.
    return 0 if result['audit']['mechanical_status']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
