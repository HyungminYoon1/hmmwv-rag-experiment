"""Close reviewed layout prompts; never close source choice or budget failures."""
import json
from .common import PACKAGE,read_json,text_sha

NORMAL_CODES={'STRUCTURE_BOUNDARY','OCR_REGION_STRUCTURE','BOX_CONTEXT_REVIEW','FLOW_ANNOTATION_REVIEW'}


def signature(review):
    fields={k:review.get(k) for k in ('code','pdf_page','unit_key','source_refs','detail')}
    return text_sha(json.dumps(fields,ensure_ascii=False,sort_keys=True))


def resolve(store,units):
    path=PACKAGE/store.config['rules_path']/'review-policy.json'
    if not path.is_file():return list(store.reviews),[]
    policy=read_json(path)
    if policy.get('status')!='APPROVED_FOR_TEXT_SCOPE':return list(store.reviews),[]
    by={u['key']:u for u in units};active=[];history=[]
    for r in store.reviews:
        u=by.get(r['unit_key']);refs=r['source_refs']
        valid=(r['code'] in NORMAL_CODES and u is not None and refs and
               all(x['bbox'] and x['text']==store.exact(x)['text'] for x in refs))
        if not valid:active.append(r);continue
        relation='PDF_ONLY_UNLESS_EXPLICIT_REVIEWED_LINK'
        history.append({**r,'status':'CLOSED','original_status':r['status'],
          'resolution':{'policy_id':policy['id'],'review_signature':signature(r),'reviewer':'CODEX',
            'basis':'SOURCE_BLOCKS_AND_LITERAL_REGIONS_REVIEWED_WITH_GEOMETRY_CHECKS_AND_PDF_SAMPLES',
            'scope':'TEXT_CORPUS','graphic_relations':relation,'human_source_review':'NOT_PERFORMED',
            'semantic_all_characters_certified':False}})
    active_ids={r['id'] for r in active};closed_ids={r['id'] for r in history}
    for u in units:
        u['resolved_review_ids']=[x for x in u['review_ids'] if x in closed_ids]
        u['review_ids']=[x for x in u['review_ids'] if x in active_ids]
        if u['metadata'].get('graphic_dependency') or u['kind']=='flow_annotation':
            u['metadata'].setdefault('graphic_relations','PDF_ONLY_UNLESS_EXPLICIT_REVIEWED_LINK')
        if u.get('resolved_review_ids'):
            u['metadata']['text_scope_review']='LAYOUT_PROFILE_APPLIED'
            if u['metadata'].get('boundary')=='source_block_candidate':
                u['metadata']['boundary']='source_block_accepted_for_text_scope'
    return active,history


def verify_history(store,units,active,history,check):
    by={u['key']:u for u in units};all_ids={r['id'] for r in active};closed={}
    path=PACKAGE/store.config['rules_path']/'review-policy.json'
    policy=read_json(path) if path.exists() else {}
    check(not history or policy.get('status')=='APPROVED_FOR_TEXT_SCOPE','REVIEW_POLICY_NOT_APPROVED')
    if history:
        check(policy.get('pdf_samples_reviewed') and policy.get('source_correction_audit')=='PASS',
              'REVIEW_POLICY_MISSING_EVIDENCE')
        for e in policy.get('evidence',[]):
            check(store.lock['files'].get(e['file'])==e['sha256'],'REVIEW_EVIDENCE_NOT_LOCKED',e['file'])
    for r in history:
        check(r['id'] not in all_ids and r['id'] not in closed,'REVIEW_HISTORY_ID',r['id']);closed[r['id']]=r
        check(r['code'] in NORMAL_CODES,'UNSAFE_REVIEW_CLOSURE',r['id'])
        check(r['status']=='CLOSED' and r['original_status']=='NEEDS_REVIEW','REVIEW_HISTORY_STATE',r['id'])
        decision=r['resolution'];check(decision['review_signature']==signature(r),'REVIEW_SIGNATURE',r['id'])
        check(decision['policy_id']==policy.get('id'),'REVIEW_POLICY_ID',r['id'])
        u=by.get(r['unit_key']);check(u is not None,'REVIEW_OWNER_MISSING',r['id'])
        check(bool(r['source_refs']),'REVIEW_SOURCE_MISSING',r['id'])
        if u:
            sources=[p['source'] for p in u['body_parts']+u['prefix_parts'] if p['kind']=='source']
            for ref in r['source_refs']:
                check(store.exact(ref)==ref and bool(ref['bbox']),'REVIEW_SOURCE_CHANGED',r['id'])
                check(any(x['record_id']==ref['record_id'] and x['start']<=ref['start'] and ref['end']<=x['end'] for x in sources),
                      'REVIEW_SOURCE_NOT_IN_UNIT',r['id'])
    for u in units:
        check(set(u.get('resolved_review_ids',[]))<=set(closed),'UNKNOWN_CLOSED_REVIEW',u['key'])
        for rid in u.get('resolved_review_ids',[]):
            if rid in closed:check(closed[rid]['unit_key']==u['key'],'CLOSED_REVIEW_WRONG_UNIT',u['key'])
