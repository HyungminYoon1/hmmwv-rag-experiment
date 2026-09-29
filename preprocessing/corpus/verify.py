"""Re-read artifacts and verify text, source coverage, windows and provenance."""
from __future__ import annotations
from collections import defaultdict,Counter
from functools import lru_cache
from pathlib import Path
import sys
from tokenizers import Tokenizer

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from corpus.common import SourceStore,ROOT,PACKAGE,read_json,read_jsonl,sha,text_sha,write_json


def verify(output,store=None):
    output=Path(output).resolve()
    errors=[];checks=0
    def check(condition,code,detail=''):
        nonlocal checks
        checks+=1
        if not condition and len(errors)<200:
            errors.append({'code':code,'detail':str(detail)[:500]})
    store=store or SourceStore()
    manifest=read_json(output/'manifest.json')
    for name,expected in manifest['inputs'].items():
        path=(ROOT/name).resolve()
        check(path.is_relative_to(ROOT) and path.is_file() and sha(path)==expected,'INPUT_HASH',name)
    check(manifest['inputs']==store.lock['files'],'INPUT_MANIFEST')
    for name,expected in manifest['files'].items():
        path=(output/name).resolve()
        check(path.is_relative_to(output) and path.is_file() and sha(path)==expected,'OUTPUT_HASH',name)
    for name,expected in manifest['code'].items():
        path=(PACKAGE/name).resolve()
        check(path.is_relative_to(PACKAGE) and path.is_file() and sha(path)==expected,'CODE_HASH',name)
    config=read_json(output/'config.json')
    check(config==store.config,'CONFIG_MISMATCH')
    tokenizer=Tokenizer.from_file(str(ROOT/config['tokenizer_path']))
    tokenizer.no_truncation();tokenizer.no_padding()
    @lru_cache(maxsize=32768)
    def tokens(text):
        return len(tokenizer.encode(text,add_special_tokens=False).ids)
    units=read_jsonl(output/'corpus_units.jsonl')
    chunks=read_jsonl(output/'chunks.jsonl')
    maps=read_jsonl(output/'source_map.jsonl')
    selections=read_jsonl(output/'selection_ledger.jsonl')
    pages=read_jsonl(output/'page_coverage.jsonl')
    reviews=read_jsonl(output/'review_queue.jsonl')
    history=read_jsonl(output/'review_history.jsonl') if (output/'review_history.jsonl').exists() else []
    unit_by_id={u['id']:u for u in units}
    by_key={u['key']:u for u in units}
    map_by_id={m['chunk_id']:m for m in maps}
    check(len(unit_by_id)==len(units) and len(by_key)==len(units),'DUPLICATE_UNITS')
    check(len(map_by_id)==len(maps)==len(chunks),'SOURCE_MAP_COUNT')
    allowed_labels={}
    for f in ['pmcs-structure.jsonl','review557-tables.jsonl','restored-image-tables.jsonl']:
        for t in store.table(f):
            allowed_labels[f,t.get('id',t.get('row_id'))]=list(t.get('headers',t.get('fields',{})))
    manual_rows={r['key']:r for r in store.table('manual-table-units.jsonl')}
    from corpus.verify_tables import verify_table_contracts
    verify_table_contracts(list(manual_rows.values()),check)
    for key,row in manual_rows.items():
        allowed_labels['manual-table-units.jsonl',key]=[f['name'] for f in row['fields']]
    # Independently reconstruct every correction, including untouched spans.
    for rid,record in store.records.items():
        original=store.before[rid]['text'];cursor=0;pieces=[]
        for p in sorted(store.patches[rid],key=lambda p:p['start']):
            check(original[p['start']:p['end']]==p['before'],'PATCH_BEFORE',p['id'])
            pieces.extend([original[cursor:p['start']],p['after']]);cursor=p['end']
        pieces.append(original[cursor:])
        check(''.join(pieces)==record['text'],'CORRECTED_RECORD',rid)
    source_coverage=defaultdict(list)
    unit_coverage=defaultdict(list)
    def inspect_part(part,location):
        kind=part.get('kind')
        if kind=='source':
            s=part['source'];rid=s['record_id'];a,b=s['start'],s['end']
            check(rid in store.records,'SOURCE_RECORD',location)
            if rid not in store.records: return
            rec=store.records[rid]
            check(0<=a<=b<=len(rec['text']),'SOURCE_RANGE',location)
            check(rec['text'][a:b]==part['text']==s['text'],'SOURCE_TEXT',location)
            check(s['pdf_page']==rec['pdf_page'] and s['printed_page']==rec['printed_page'],'SOURCE_PAGE',location)
            expected=[]
            raw_cursor=fixed_cursor=0
            for p in sorted(store.patches[rid],key=lambda p:p['start']):
                length=p['start']-raw_cursor
                lo,hi=max(a,fixed_cursor),min(b,fixed_cursor+length)
                if lo<hi: expected.append({'start':raw_cursor+lo-fixed_cursor,'end':raw_cursor+hi-fixed_cursor,'correction_id':None})
                fixed_cursor+=length
                if max(a,fixed_cursor)<min(b,fixed_cursor+len(p['after'])):
                    expected.append({'start':p['start'],'end':p['end'],'correction_id':p['id']})
                fixed_cursor+=len(p['after']);raw_cursor=p['end']
            lo,hi=max(a,fixed_cursor),min(b,fixed_cursor+len(store.before[rid]['text'])-raw_cursor)
            if lo<hi: expected.append({'start':raw_cursor+lo-fixed_cursor,'end':raw_cursor+hi-fixed_cursor,'correction_id':None})
            check(s['raw_spans']==expected,'RAW_POSITION_MAP',location)
            # Coordinates refer to stored source lines/cells, not guessed glyphs.
            box_set={tuple(line[2]) for line in store.lines[rid] if line[2] and any(
                max(line[0],x['start'])<min(line[1],x['end']) for x in expected)}
            matched_patch_ids={x['correction_id'] for x in expected}
            box_set.update(tuple(p['bbox']) for p in store.patches[rid]
                           if p['id'] in matched_patch_ids and p.get('kind')=='MISSING_PRINTED_CELL')
            regions=[r for r in store.source_regions[rid] if max(a,r['start'])<min(b,r['end'])]
            covered_chars={i for r in regions for i in range(max(a,r['start']),min(b,r['end']))}
            regional=bool(regions) and all(i in covered_chars or rec['text'][i].isspace() for i in range(a,b))
            if regional:
                box_set={tuple(r['bbox']) for r in regions}
                check(s['coordinate_precision']=='reviewed_pdf_region','REVIEWED_COORDINATE_KIND',location)
            else:
                coordinates=[r for r in store.coordinate_spans[rid] if max(a,r['start'])<min(b,r['end'])]
                covered={i for r in coordinates for i in range(max(a,r['start']),min(b,r['end']))}
                precise=bool(coordinates) and all(i in covered or rec['text'][i].isspace() for i in range(a,b))
                if precise:
                    box_set={tuple(w['bbox']) for r in coordinates for w in r['words']
                             if max(a,w['start'])<min(b,w['end'])}
                    check(s['coordinate_precision']=='frozen_word_coordinates','WORD_COORDINATE_KIND',location)
            expected_boxes=sorted(box_set,key=lambda b:(b[1],b[0],b[3],b[2]))
            check(s['bboxes']==[list(b) for b in expected_boxes],'SOURCE_COORDINATES',location)
        elif kind=='separator':
            check(all(c in '\n\t :;|[]=' for c in part['text']),'UNDECLARED_FORMATTING',location)
        elif kind=='label':
            d=part['definition'];key=d['file'],d['id']
            check(d['field'] in allowed_labels.get(key,[]),'UNKNOWN_STRUCTURE_LABEL',location)
            a=part.get('label_start',0);b=part.get('label_end',len(d['field']))
            check(part['text']==d['field'][a:b],'LABEL_TEXT',location)
        else:
            check(False,'UNKNOWN_PART',location)
    for u in units:
        for kind in ('prefix','body'):
            parts=u[kind+'_parts']
            check(''.join(p['text'] for p in parts)==u[kind+'_text'],'UNIT_SERIALIZATION',u['id'])
            for p in parts:
                inspect_part(p,u['id'])
                if p['kind']=='source':
                    s=p['source'];unit_coverage[u['key'],s['record_id']].append((s['start'],s['end']))
        if u['kind']=='pmcs_item':
            for p in u['body_parts']:
                if p['kind']=='label':
                    definition=p['definition']
                    expected_rid=definition['id']+':'+definition['field']
                    following=u['body_parts'][u['body_parts'].index(p)+2]
                    check(following.get('source',{}).get('record_id')==expected_rid,'PMCS_COLUMN_MAPPING',u['id'])
        if u['kind']=='manual_table_row':
            expected=manual_rows.get(u['key'])
            check(expected is not None,'UNKNOWN_MANUAL_TABLE_ROW',u['id'])
            if expected:
                body='\n'.join(f['name']+': '+f['text'] for f in expected['fields'])
                check(u['body_text']==body,'MANUAL_TABLE_FIELD_MAPPING',u['id'])
                refs=[p['source'] for p in u['prefix_parts'] if p['kind']=='source']
                check(refs==[store.exact(r) for r in expected['context_refs']],'MANUAL_TABLE_CONTEXT',u['id'])
                check(all(u['metadata'].get(k)==v for k,v in expected['metadata'].items()),
                      'MANUAL_TABLE_METADATA',u['id'])
        if u['kind']=='table_row':
            tid=u['metadata']['table_id'];row_number=u['metadata']['row']
            table=next((t for f in ('review557-tables.jsonl','restored-image-tables.jsonl') for t in store.table(f) if t['id']==tid),None)
            check(table is not None,'UNKNOWN_TABLE',u['id'])
            if table:
                row=table['rows'][row_number-1]
                expected='\n'.join(h+': '+(row[h]['text'] if isinstance(row[h],dict) else row[h]) for h in table['headers'])
                check(u['body_text']==expected,'TABLE_COLUMN_MAPPING',u['id'])
    by_unit=defaultdict(list)
    for i,c in enumerate(chunks):
        check(c['id']==f'C{i+1:06d}','CHUNK_ID',c['id'])
        check(c['unit_id'] in unit_by_id,'CHUNK_UNIT',c['id'])
        if c['unit_id'] not in unit_by_id: continue
        u=unit_by_id[c['unit_id']];by_unit[u['id']].append(c)
        if config.get('schema',1)>=2:
            check(c.get('structure_metadata')==u['metadata'],'CHUNK_STRUCTURE_METADATA',c['id'])
        check(c['text']==u['prefix_text']+u['body_text'][c['body_start']:c['body_end']],'WINDOW_TEXT',c['id'])
        check(c['prefix_chars']==len(u['prefix_text']),'PREFIX_LENGTH',c['id'])
        check(tokens(c['text'])==c['token_count']<=config['max_tokens'],'TOKEN_LIMIT',c['id'])
        check(text_sha(c['text'])==c['text_sha256'],'TEXT_HASH',c['id'])
        mapping=map_by_id.get(c['id'],{}).get('parts',[])
        pos=0
        for p in mapping:
            check(p['start']==pos and p['end']>pos,'MAPPING_PARTITION',c['id'])
            check(c['text'][p['start']:p['end']]==p['text'],'MAPPING_TEXT',c['id'])
            inspect_part(p,c['id']);pos=p['end']
            if p['kind']=='source':
                s=p['source'];source_coverage[c['unit_key'],s['record_id']].append((s['start'],s['end']))
        check(pos==len(c['text']),'MAPPING_END',c['id'])
    for uid,u in unit_by_id.items():
        group=by_unit[uid]
        check(bool(group),'UNIT_WITHOUT_CHUNKS',uid)
        if not group: continue
        check(group[0]['body_start']==0 and group[0]['overlap_tokens']==0,'FIRST_WINDOW',uid)
        check(group[-1]['body_end']==len(u['body_text']),'LAST_WINDOW',uid)
        for prev,cur in zip(group,group[1:]):
            a,b=cur['body_start'],prev['body_end']
            check(prev['body_start']<a<b<cur['body_end'],'WINDOW_PROGRESS',cur['id'])
            actual=tokens(u['body_text'][a:b])
            check(actual==cur['overlap_tokens']>=config['body_overlap_tokens'],'OVERLAP_TOKENS',cur['id'])
            check(b-a==cur['overlap_chars'],'OVERLAP_CHARS',cur['id'])
            check(all(tokens(u['body_text'][j:b])<config['body_overlap_tokens'] for j in range(a+1,b)),
                  'SHORTEST_CHARACTER_OVERLAP',cur['id'])
    from corpus.verify_boxes import verify_box_contracts
    verify_box_contracts(store,units,check)
    def covered(spans,a,b):
        cursor=a
        for x,y in sorted(spans):
            if y<=cursor: continue
            if x>cursor: return False
            cursor=max(cursor,y)
            if cursor>=b: return True
        return cursor>=b
    selection_by_record=defaultdict(list)
    by_page=defaultdict(Counter)
    for row in selections:
        selection_by_record[row['record_id']].append(row)
        by_page[row['pdf_page']][row['status']]+=len(row['text'])
        check((row['status']=='EXCLUDED_BY_SCOPE')==not_in_scope(store.records[row['record_id']]),'SELECTION_SCOPE',row['id'])
        if row['status']=='INCLUDED':
            check(bool(row['owners']),'INCLUDED_WITHOUT_OWNER',row['id'])
            for owner in row['owners']:
                key=owner['unit_key'],row['record_id']
                check(covered(unit_coverage[key],row['start'],row['end']),'UNIT_SOURCE_LOSS',row['id'])
                check(covered(source_coverage[key],row['start'],row['end']),'CHUNK_SOURCE_LOSS',row['id'])
        check(row['status'] in ['INCLUDED','DUPLICATE_ALTERNATIVE','EXCLUDED_BY_SCOPE','EXCLUDED_NON_TEXT',
                               'LAYOUT_ONLY','NEEDS_REVIEW'],'SELECTION_STATE',row['id'])
    for rid,rec in store.records.items():
        pos=0
        for row in selection_by_record[rid]:
            check(row['start']==pos and row['end']>pos,'LEDGER_PARTITION',row['id'])
            check(rec['text'][row['start']:row['end']]==row['text'],'LEDGER_TEXT',row['id'])
            pos=row['end']
        check(pos==len(rec['text']),'LEDGER_MISSING_TEXT',rid)
    low,high=config['scope_pdf_pages']
    check([p['pdf_page'] for p in pages]==list(range(low,high+1)),'PAGE_COVERAGE')
    for page in pages:
        check(page['character_dispositions']==dict(by_page[page['pdf_page']]),'PAGE_CHARACTER_COUNTS',page['pdf_page'])
    for rule in store.table('review557-adoption-rules.jsonl'):
        if not rule['in_scope']:continue
        refinements=[r for r in manual_rows.values() if r['metadata'].get('refines_old_rule')==rule['candidate_id']]
        if refinements:
            check(rule['candidate_id']=='ALIGN-00370' and len(refinements)==5 and
                  all(r['review']=='CODEX_PDF_LAYOUT_REVIEW' for r in refinements),'INVALID_RULE_REFINEMENT',rule['candidate_id'])
            # Only the explicitly reviewed table spans may replace the earlier
            # broad region exclusion. Native procedure text must remain.
            nr=rule['native_span']
            check(any(s['status']=='INCLUDED' and s['start']<=nr['start'] and s['end']>=nr['end']
                      for s in selection_by_record[nr['record_id']]),'REFINEMENT_NATIVE_LOSS',rule['candidate_id'])
            continue
        refs=[rule['native_span'],rule['ocr_span']] if rule['category']=='FLOWCHART_BRANCH' else [
            rule['native_span'] if rule['preferred_layer_for_aligned_span']=='ocr' else rule['ocr_span']]
        for ref in refs:
            check(not any(s['status']=='INCLUDED' and max(s['start'],ref['start'])<min(s['end'],ref['end'])
                          for s in selection_by_record[ref['record_id']]),'REVIEWED_ALTERNATIVE_INDEXED',rule['candidate_id'])
    contexts=store.table('pmcs-context-links.jsonl')
    for context in contexts:
        for item in context['applies_to_items']:
            u=by_key.get('pmcs:'+item)
            check(u is not None,'MISSING_PMCS_ITEM',item)
            if u:
                check(any(p['kind']=='source' and p['source']['record_id']==context['source_record']
                          and p['source']['start']<=context['start'] and p['source']['end']>=context['end']
                          for p in u['prefix_parts']),'PMCS_CONTEXT_LOSS',item)
    raw_pages=read_jsonl(ROOT/'preprocessing/output/full-manual-v2-a/raw_native_pages.jsonl')
    images=read_jsonl(output/'image_regions.jsonl')
    expected_images=[(p['pdf_page'],i,b) for p in raw_pages if low<=p['pdf_page']<=high for i,b in enumerate(p['image_bboxes'])]
    check([(p['pdf_page'],p['image_index'],p['bbox']) for p in images]==expected_images,'IMAGE_REGION_INVENTORY')
    review_ids={r['id'] for r in reviews}
    check(len(review_ids)==len(reviews),'REVIEW_IDS')
    for u in units:
        check(set(u['review_ids'])<=review_ids,'UNKNOWN_REVIEW',u['id'])
    from corpus.review_resolution import verify_history
    verify_history(store,units,reviews,history,check)
    from corpus.verify_selection import verify_proofs
    pending_proofs=verify_proofs(output,store,selections,check)
    pending=len(reviews)+sum(s['status']=='NEEDS_REVIEW' for s in selections)+pending_proofs
    ready=not errors and not pending
    return {'schema':1,'mechanical_status':'FAIL' if errors else 'PASS',
            'corpus_status':'INVALID' if errors else ('REVIEW_REQUIRED' if pending else 'READY'),
            'corpus_ready_for_index':ready,'checks':checks,'errors':errors,
            'review_count':len(reviews),'pending_selection_spans':sum(s['status']=='NEEDS_REVIEW' for s in selections),
            'closed_review_count':len(history),
            'pending_representation_destinations':pending_proofs,
            'scope_pages':len(pages),'units':len(units),'chunks':len(chunks),
            'max_chunk_tokens':max((c['token_count'] for c in chunks),default=0),
            'semantic_correctness_certified':False,'human_source_review':'NOT_PERFORMED'}


def not_in_scope(record):
    return not record['in_scope']


def main():
    import argparse,json
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path);p.add_argument('--report',type=Path)
    args=p.parse_args();result=verify(args.output)
    if args.report:
        if args.report.resolve().is_relative_to(args.output.resolve()):
            raise ValueError('Independent verification report must be outside the output directory')
        write_json(args.report,result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['mechanical_status']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
