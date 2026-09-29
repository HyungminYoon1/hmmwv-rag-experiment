"""Region-limited source selection with a complete character disposition ledger."""
from __future__ import annotations
from collections import defaultdict,Counter
import re
from .common import overlap, intersects, union_box
from .equivalence import norm, witness


def reviewed_rules(store):
    refined={r['metadata']['refines_old_rule'] for r in store.table('manual-table-units.jsonl')
             if r['metadata'].get('refines_old_rule')}
    for rule in store.table('review557-adoption-rules.jsonl'):
        if not rule['in_scope']:
            continue
        if rule['candidate_id'] in refined:
            # Its image table and native prose are now represented separately;
            # literal matching below handles only the actual duplicate text.
            continue
        native=store.exact(rule['native_span']);ocr=store.exact(rule['ocr_span'])
        category=rule['category'];rid=[rule['candidate_id']]
        if category=='FLOWCHART_BRANCH':
            for ref in [native,ocr]:
                store.decide(ref,'EXCLUDED_NON_TEXT','REVIEWED_DIAGRAM_BRANCH_METADATA',rid)
        elif rule['preferred_layer_for_aligned_span']=='ocr':
            store.represent(native,[ocr],'REFERENCE_IS_PRESENT_IN_REVIEWED_OCR',rid,'REVIEWED_ALTERNATIVE')
            # Included by the generic reader only if it is not already in a table.
            store.decide(ocr,'PREFERRED','REVIEWED_OCR_REGION',rid)
        else:
            store.represent(ocr,[native],rule['handling'],rid,'REVIEWED_ALTERNATIVE')
            store.decide(native,'PREFERRED',rule['handling'],rid)


def select(store):
    reviewed_rules(store)
    for rule in store.table('selection-overrides.jsonl'):
        source=store.exact(rule['source'])
        if rule['action']=='REPRESENT':
            store.represent(source,[store.exact(r) for r in rule['targets']],rule['reason'],[rule['id']],'PDF_REVIEWED_ALTERNATIVE')
        else:
            store.decide(source,rule['action'],rule['reason'],[rule['id']])
        for ref in rule.get('preferred_refs',[]):
            store.decide(store.exact(ref),'PREFERRED',rule['reason'],[rule['id']])
    selected=[]
    # Source choice and representation are separate axes. Actual text witnesses
    # replace the old bbox-only table suppression and 0.8 similarity rule.
    registry={r['pdf_page']:r for r in store.table('table-layout-review.jsonl') if r['in_scope']}
    completed={'pmcs','oil_pressure','dtc85_ratio_table_in_image','test_index','status_readouts',
               'transducer_components_in_image','two_column_prose','diagram_not_data_table','flowchart_with_table_caption'}
    completed_pages=set(getattr(store,'structured_pages',[]))
    for pn,reg in registry.items():
        if reg['kind'] not in completed and pn not in completed_pages:
            store.review('TABLE_STRUCTURE',pn,
                         '표의 행·열·상위 조건을 추가로 구조화해야 합니다. '+reg['handling'])
    for pn,page in sorted(store.pages.items()):
        if not page['in_scope']:continue
        claimed=[]
        for rid,claims in list(store.claims.items()):
            if store.records[rid]['pdf_page']!=pn:continue
            claimed.extend(store.ref(rid,a,b) for a,b,*_ in claims)
        claimed=list({(r['record_id'],r['start'],r['end']):r for r in claimed}.values())
        remaining={}
        for layer in ('native','ocr'):
            rid=f'P{pn:04d}:{layer}'
            if rid not in store.records:continue
            remaining[layer]=[]
            for ref in list(store.fragments(rid)):
                if not ref['text'].strip() or store.claimed(ref) or store.represented(ref):continue
                decision=store.decision(ref)
                if decision and decision[0] not in ('PREFERRED','NEEDS_REVIEW'):continue
                if decision and decision[0]=='NEEDS_REVIEW':
                    store.review('SELECTION_CONFLICT',pn,decision[1],[ref]);continue
                near=[n for n in claimed if n['record_id']!=rid and
                      overlap(ref['bbox'],n['bbox'])[0]>.45 and overlap(ref['bbox'],n['bbox'])[1]>.5]
                found=None
                for target in near:
                    found=witness(store,ref,[target])
                    if found:break
                if not found and near:
                    for key in (lambda n:(n['bbox'][1],n['bbox'][0],n['start']),
                                lambda n:(n['bbox'][0],n['bbox'][1],n['start'])):
                        found=witness(store,ref,sorted(near,key=key))
                        if found:break
                if found:
                    store.represent(ref,found,'REPRESENTED_BY_STRUCTURED_SOURCE',['S02','S03']);continue
                remaining[layer].append(ref)
        natives=remaining.get('native',[])
        all_native=[r for r in store.fragments(f'P{pn:04d}:native') if r['text'].strip()] if f'P{pn:04d}:native' in store.records else []
        for ref in remaining.get('ocr',[]):
            decision=store.decision(ref)
            if decision and decision[0]=='PREFERRED':selected.append(ref);continue
            near=[n for n in all_native if overlap(ref['bbox'],n['bbox'])[0]>.45 and overlap(ref['bbox'],n['bbox'])[1]>.5]
            if not near:selected.append(ref);continue
            found=None
            for target in near:
                found=witness(store,ref,[target])
                if found:break
            if not found:
                for key in (lambda n:(n['bbox'][1],n['bbox'][0],n['start']),
                            lambda n:(n['bbox'][0],n['bbox'][1],n['start'])):
                    found=witness(store,ref,sorted(near,key=key))
                    if found:break
            if found:
                store.represent(ref,found,'EXACT_ALTERNATIVE_TEXT',['S03','S06']);continue
            reverse=[witness(store,n,[ref]) if len(norm(n['text']))>=4 and not store.claimed(n)
                     and not store.represented(n) else None for n in near]
            # A printed reference embedded in image text is only part of a line.
            # Keep that whole OCR line, with exact witnesses for native refs.
            if all(reverse):
                selected.append(ref)
                for n,targets in zip(near,reverse):
                    store.represent(n,targets,'NATIVE_FRAGMENT_IN_IMAGE_TEXT',['S04','S06'])
                continue
            store.decide(ref,'NEEDS_REVIEW','UNALIGNED_OVERLAPPING_OCR',[])
            store.review('LAYER_ALIGNMENT',pn,'추출층의 전체 문자 대응 또는 추가 원문 대조가 필요합니다.',[ref]+near)
        selected.extend(r for r in natives if not store.represented(r))
    return selected


def ledger(store):
    rows=[];page_counts=defaultdict(Counter)
    for rid,rec in store.records.items():
        for ref in store.fragments(rid):
            owners=[{'unit_key':key,'role':role} for a,b,key,role in store.claims[rid]
                    if a<=ref['start'] and ref['end']<=b]
            if not rec['in_scope']:
                state,reason,rule_ids='EXCLUDED_BY_SCOPE','OUTSIDE_CHAPTERS_1_2',[]
            elif not ref['text'].strip():
                state,reason,rule_ids='LAYOUT_ONLY','WHITESPACE',[]
            elif owners:
                state,reason,rule_ids='INCLUDED','SOURCE_MAPPED_TO_UNITS',[]
            elif store.represented(ref):
                state,reason,rule_ids='DUPLICATE_ALTERNATIVE','EXPLICIT_SOURCE_REPRESENTATION',store.represented(ref)
            else:
                decision=store.decision(ref)
                if decision and decision[0]!='PREFERRED':
                    state,reason,rule_ids=decision
                else:
                    state,reason,rule_ids='NEEDS_REVIEW','UNASSIGNED_SOURCE_TEXT',[]
                    store.review('UNASSIGNED_TEXT',rec['pdf_page'],'채택 또는 제외 근거를 지정해야 합니다.',[ref])
            row={'id':f'S{len(rows)+1:07d}','record_id':rid,'start':ref['start'],'end':ref['end'],
                 'text':ref['text'],'pdf_page':rec['pdf_page'],'layer':rec['layer'],'bbox':ref['bbox'],
                 'status':state,'reason':reason,'rule_ids':rule_ids,'owners':owners,
                 'representation_proof_ids':store.represented(ref)}
            rows.append(row);page_counts[rec['pdf_page']][state]+=len(ref['text'])
    coverage=[]
    for pn,page in sorted(store.pages.items()):
        if not page['in_scope']: continue
        coverage.append({'pdf_page':pn,'printed_page':page['printed_page'],'character_dispositions':dict(page_counts[pn]),
                         'blank_page':'BLANK_PAGE' in page['review_flags'],'image_count':page['image_count'],
                         'vector_drawing_count':page['vector_drawing_count'],
                         'graphic_relations':'NOT_CONVERTED_TO_PROSE',
                         'source_flags':page['review_flags']})
    return rows,coverage
