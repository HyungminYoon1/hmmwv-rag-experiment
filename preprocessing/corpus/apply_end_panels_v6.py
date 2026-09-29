"""Adopt source-checked panel ends and the p361 multimeter heading."""
import re,shutil
from .common import *
from .end_panel_pages_v6 import PAGES


def main():
    rules=PACKAGE/'rules/v6';snapshot=PACKAGE/'reports/rules-v6-work/rules-before-v19'
    if snapshot.exists():raise ValueError('Already applied')
    shutil.copytree(rules,snapshot);batch=BASE/'corrections/batch-019'
    ids={f'P{pn:04d}:ocr' for pn in PAGES}
    def mentions(v):
        if isinstance(v,list):return any(mentions(x) for x in v)
        if isinstance(v,dict):return v.get('record_id',v.get('source_record')) in ids or any(mentions(x) for x in v.values())
        return False
    for name in ['box-units.jsonl','box-dispositions.jsonl','source-regions.jsonl','selection-overrides.jsonl',
                 'review557-adoption-rules.jsonl','manual-dispositions.jsonl','manual-table-units.jsonl']:
        write_jsonl(rules/name,[r for r in read_jsonl(rules/name) if not mentions(r)])
    write_jsonl(rules/'coordinate-spans.jsonl',[])
    config=read_json(PACKAGE/'config.json');config.update(corrected_source='preprocessing/output/corrected-v19-a',correction_ledger='preprocessing/corrections/batch-019/correction-log.json')
    config['additional_inputs'] += [f'preprocessing/corrections/batch-019/{n}.json' for n in ['regions','nodes','superseded-corrections']]
    write_json(PACKAGE/'config.json',config)
    regions=read_json(batch/'regions.json')
    for r in regions:
        image=batch/f'evidence/V19-P{r["pdf_page"]:04d}.png'
        r.update(review='CODEX_PDF_LAYOUT_REVIEW',evidence={'file':image.relative_to(ROOT).as_posix(),'sha256':sha(image)})
    write_jsonl(rules/'source-regions.jsonl',read_jsonl(rules/'source-regions.jsonl')+regions)
    s=SourceStore(check=False);rows=s.table('box-units.jsonl');disp=s.table('box-dispositions.jsonl')
    edges=[r for r in s.table('flow-links.jsonl') if r['page'] not in PAGES]
    by={(r['pdf_page'],r['name']):r for r in regions}
    for node in read_json(batch/'nodes.json'):
        pn=node['pdf_page'];key=f'V19:P{pn:04d}:{node["step"]}';ev=by[pn,'title']['evidence']
        context=[s.exact(r) for r in node['context']];body=[s.exact(r) for r in node['body']]
        meta={'boundary':'individually_reviewed_question_panels','step':node['step'],'condition_link_basis':'PDF_VISUAL_SAME_NODE_BOXES','graphic_dependency':True,'graphic_relations_inferred':False}
        rows.append({'key':key,'kind':'diagnostic_box','body_refs':body,'context_refs':context,'review_codes':[],
                     'review':'CODEX_PDF_LAYOUT_REVIEW','evidence':ev,'metadata':meta})
        action=key+':NO';branch=s.exact(node['no'])
        rows.append({'key':action,'kind':'diagnostic_action','body_refs':[s.exact(node['action'])],
          'context_refs':context+[body[0],branch],'review_codes':[],'review':'CODEX_PDF_LAYOUT_REVIEW','evidence':ev,
          'metadata':{**meta,'branch':'NO','parent_question':key}})
        edges.append({'source':key,'target':action,'branch':'NO','branch_source':branch,'page':pn,'evidence':ev})
    for r in regions:
        if r['role']=='navigation':disp.append({'source':s.exact(r),'status':'EXCLUDED_NON_TEXT','reason':'VERIFIED_DIAGRAM_NAVIGATION_PDF_ONLY','rule':'V19-NAVIGATION'})
        elif r['role']=='flow_annotation':
            rows.append({'key':f'V19:P{r["pdf_page"]:04d}:terminal','kind':'flow_annotation','body_refs':[s.exact(r)],
              'context_refs':[],'review_codes':[],'review':'CODEX_PDF_LAYOUT_REVIEW','evidence':r['evidence'],
              'metadata':{'boundary':'literal_terminal_callout','graphic_dependency':True,'graphic_relations_inferred':False,
                          'branch_interpretation':'PDF_ONLY_NO_PRINTED_BRANCH_LABEL'}})
    overrides=s.table('selection-overrides.jsonl')
    for pn in PAGES:
        rid=f'P{pn:04d}:native';ocr=f'P{pn:04d}:ocr';text=s.records[ocr]['text'];ev=by[pn,'title']['evidence']
        for ref in s.fragments(rid):
            if not ref['text'].strip():continue
            m=re.search(r'\s+'.join(re.escape(w) for w in ref['text'].split()),text,re.I)
            if not m:raise ValueError(('Unrepresented native text',pn,ref['text']))
            overrides.append({'id':f'V19-N{pn}-{ref["start"]}','source':ref,'action':'REPRESENT','targets':[s.ref(ocr,*m.span())],
              'reason':'PDF_CHECKED_NATIVE_REFERENCE_IN_TRANSCRIBED_NODE','review':'CODEX_PDF_VISUAL_REVIEW','evidence':ev})
    prior={u['key']:u for u in read_jsonl(BASE/'output/corpus-v6-final-check-a/corpus_units.jsonl')}
    def refs(key,field):return [s.exact(p['source']) for p in prior[key][field] if p['kind']=='source']
    im=PACKAGE/'reports/rules-v6-work/final-samples/p0361.png';ev={'file':im.relative_to(ROOT).as_posix(),'sha256':sha(im)}
    rows.append({'key':'V19:P0361:multimeter','kind':'reviewed_text_box','body_refs':refs('region:361:1:5','body_parts'),
      'context_refs':refs('region:361:1:4','prefix_parts')+refs('region:361:1:4','body_parts'),
      'review_codes':[],'review':'CODEX_PDF_LAYOUT_REVIEW','evidence':ev,
      'metadata':{'boundary':'individually_reviewed_test_box','condition_link_basis':'SAME_PRINTED_MULTIMETER_BOX'}})
    cleaned=[]
    for r in rows:
        if r['key'].startswith('V6:'):
            box=r['metadata']['condition_box'];kept=[]
            for ref in r['context_refs']:
                if ref['text'].strip()=='KNOWN INFO' and ref['bbox'][3]<box[1]-3:
                    cleaned.append({'unit_key':r['key'],'source':ref,'reason':'FIRST_NODE_HEADER_IS_NOT_PAGE_TITLE'});continue
                kept.append(ref)
            r['context_refs']=kept
    write_jsonl(rules/'box-units.jsonl',rows);write_jsonl(rules/'box-dispositions.jsonl',disp)
    write_jsonl(rules/'selection-overrides.jsonl',overrides);write_jsonl(rules/'flow-links.jsonl',edges)
    facts=read_json(rules/'flow-assertions.json');facts['edges']=[[e['source'],e['branch'],e['target']] for e in edges];write_json(rules/'flow-assertions.json',facts)
    issues=s.table('source-issues.jsonl')
    for pn,code,detail in [(224,'INDUCTION_WORDING','3번 배기계통 질문의 NO 조치도 INDUCTION SYSTEM COMPONENTS로 인쇄되어 있다. EXHAUST로 추정 교정하지 않았다.'),
                           (718,'PREVIOISLY','원문 PREVIOISLY 철자를 유지했다.'),
                           (361,'REED','원문 Be sure to reed the correct scale. 문구를 유지했다.')]:
        ev=by[pn,'title']['evidence'] if pn!=361 else {'file':im.relative_to(ROOT).as_posix(),'sha256':sha(im)}
        issues.append({'id':f'P{pn:04d}_PRINTED_{code}','pdf_page':pn,'detail':detail,'status':'SOURCE_WORDING_PRESERVED','evidence':ev})
    write_jsonl(rules/'source-issues.jsonl',issues)
    cases=read_json(PACKAGE/'reports/rules-v6-work/left-panel-ends/candidates.json')
    for r in cases:r['resolution']='RETRANSCRIBED_NONEMPTY_PANEL' if r['pdf_page'] in PAGES else 'PDF_CONFIRMED_EMPTY_POSSIBLE_PROBLEMS'
    write_json(rules/'condition-panel-end-review.json',{'cases':cases,'removed_duplicate_page_headers':cleaned,
      'source_review':'CODEX_PDF_VISUAL_REVIEW','human_source_review':'NOT_PERFORMED'})
    print({'new_nodes':len(PAGES),'explicit_flow_links':len(edges),'removed_duplicate_headers':len(cleaned)})


if __name__=='__main__':main()
