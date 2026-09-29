"""Join PDF box candidates to current character dispositions and unit owners."""
from pathlib import Path
from collections import Counter, defaultdict
from bisect import bisect_right
import hashlib
from corpus.common import BASE, SourceStore, read_json, read_jsonl, write_json, write_jsonl

ROOT_OUT=BASE/'ocr-structure-review-20260924'
AUDIT=ROOT_OUT/'full-audit-e'


def main():
    store=SourceStore()
    census=read_jsonl(AUDIT/'page-census.jsonl')
    units=read_jsonl(BASE/'output/corpus-v4-rules-c/corpus_units.jsonl')
    ledger=read_jsonl(BASE/'output/corpus-v4-rules-c/selection_ledger.jsonl')
    by_record=defaultdict(list)
    for row in ledger:
        if row['layer']=='ocr':by_record[row['record_id']].append(row)
    for rows in by_record.values():rows.sort(key=lambda r:r['start'])
    starts={rid:[r['start'] for r in rows] for rid,rows in by_record.items()}
    by_page_units=defaultdict(list)
    for u in units:
        for pn in u['pdf_pages']:by_page_units[pn].append(u)
    box_results=[];unit_links=defaultdict(set)
    for row in census:
        pn=row['pdf_page'];rid=f'P{pn:04d}:ocr'
        data=read_json(AUDIT/f'page-{pn:04d}.json')
        for box in data['rectangles']:
            if len(box['words'])<4:continue
            statuses=Counter();owners=set();word_items=[]
            for word in box['words']:
                a,b=word['raw_start'],word['raw_end'];mapped=[]
                runs=[run for run in store.runs[rid] if max(a,run[2])<min(b,run[3])]
                if len(runs)!=1 or runs[0][4]:
                    state=['CORRECTED_SOURCE_REQUIRES_REGION_MAP'];word_owners=[]
                else:
                    cs,ce,rs,re,_=runs[0];left,right=cs+a-rs,cs+b-rs
                    i=max(0,bisect_right(starts[rid],left)-1)
                    while i<len(by_record[rid]) and by_record[rid][i]['start']<right:
                        item=by_record[rid][i]
                        if max(left,item['start'])<min(right,item['end']):mapped.append(item)
                        i+=1
                    state=sorted({r['status'] for r in mapped})
                    word_owners=sorted({o['unit_key'] for r in mapped for o in r['owners'] if o['role']=='body'})
                    assert mapped and min(r['start'] for r in mapped)<=left and max(r['end'] for r in mapped)>=right
                statuses.update(state);owners.update(word_owners)
                word_items.append({'text':word['text'],'raw_start':a,'raw_end':b,'states':state,'body_owners':word_owners})
            flags=[]
            if statuses['INCLUDED'] and statuses['NEEDS_REVIEW']:flags.append('PARTIALLY_SELECTED_BOX')
            if len(owners)>1:flags.append('MULTIPLE_BODY_UNITS_FOR_BOX')
            if statuses['NEEDS_REVIEW'] and not statuses['INCLUDED']:flags.append('BOX_WITH_PENDING_CONTENT')
            key=f'P{pn:04d}:{box["id"]}'
            result={'key':key,'pdf_page':pn,'family':row['family_candidate'],'bbox':box['bbox'],
                    'words':word_items,'word_state_counts':dict(statuses),'body_owners':sorted(owners),
                    'flags':flags,'interpretation':'GEOMETRIC_DIAGNOSIS_NOT_AUTOMATIC_ERROR_VERDICT'}
            box_results.append(result)
            for owner in owners:unit_links[owner].add(key)
        ocr_units=[u for u in by_page_units[pn] if any(p['kind']=='source' and p['source']['layer']=='ocr' and p['source']['pdf_page']==pn for p in u['body_parts'])]
        row['ocr_body_units']=len(ocr_units)
        row['ocr_body_units_without_prefix']=sum(not u['prefix_text'].strip() for u in ocr_units)
        row['box_content_candidates']=sum(x['pdf_page']==pn for x in box_results)
        row['box_content_flags']=dict(Counter(f for x in box_results if x['pdf_page']==pn for f in x['flags']))
    linked_units=[]
    for u in units:
        if u['key'] not in unit_links:continue
        linked_units.append({'unit_key':u['key'],'kind':u['kind'],'pdf_pages':u['pdf_pages'],
          'box_keys':sorted(unit_links[u['key']]),'prefix_present':bool(u['prefix_text'].strip()),
          'generic_prose_spans_multiple_boxes':u['kind']=='prose' and len(unit_links[u['key']])>1})
    sampled={};pilot={138,219,534,612,810,822}
    for family in sorted({r['family_candidate'] for r in census}):
        pages=sorted(r['pdf_page'] for r in census if r['family_candidate']==family and r['pdf_page'] not in pilot)
        sample=pages[:1]+pages[-1:] if len(pages)>1 else pages[:]
        ordered=sorted(set(pages)-set(sample),key=lambda pn:(hashlib.sha256(f'HMMWV-corpus-rules-v2|{family}|{pn:04d}'.encode()).hexdigest(),pn))
        sampled[family]=sample+ordered[:max(0,5-len(sample))]
    summary={'scope_ocr_pages':len(census),'family_counts':dict(Counter(r['family_candidate'] for r in census)),
       'detected_content_box_candidates':len(box_results),'box_flag_counts':dict(Counter(f for b in box_results for f in b['flags'])),
       'ocr_body_units':sum(r['ocr_body_units'] for r in census),
       'ocr_body_units_without_prefix':sum(r['ocr_body_units_without_prefix'] for r in census),
       'generic_prose_units_spanning_multiple_boxes':sum(u['generic_prose_spans_multiple_boxes'] for u in linked_units),
       'warning':'These counts identify review locations; neither missing prefix nor a multi-box unit alone proves semantic error.',
       'data_modified':False,'corpus_ready_for_index':False}
    write_jsonl(ROOT_OUT/'page-results.jsonl',census)
    write_jsonl(ROOT_OUT/'box-content-audit.jsonl',box_results)
    write_jsonl(ROOT_OUT/'unit-box-links.jsonl',linked_units)
    write_json(ROOT_OUT/'structural-findings-summary.json',summary)
    write_json(ROOT_OUT/'independent-visual-sample.json',{'excluded_pilot_pages':sorted(pilot),'selection_rule':'First and last, then SHA256 ascending as specified in approved detailed rules','family_samples':sampled,'sample_is_not_statistical_zero_error_proof':True})
    print(summary)
    print('Visual samples:',sampled)


if __name__=='__main__':main()
