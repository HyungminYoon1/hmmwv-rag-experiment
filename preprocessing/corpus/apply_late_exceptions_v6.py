"""Adopt final source-checked exceptions without changing the frozen baseline."""
import re,shutil
from .common import *
from .late_exception_pages_v6 import PAGES


def main():
    rules=PACKAGE/'rules/v6';snapshot=PACKAGE/'reports/rules-v6-work/rules-before-v18'
    if snapshot.exists():raise ValueError('Already applied')
    shutil.copytree(rules,snapshot);old=SourceStore(check=False);batch=BASE/'corrections/batch-018'
    new={r['id']:r for r in read_jsonl(BASE/'output/corrected-v18-a/units-corrected.jsonl')}
    patches=[p for p in read_json(batch/'correction-log.json')['corrections'] if p['record_id']=='P0619:ocr']
    patches.sort(key=lambda p:p['start']);ids={f'P{pn:04d}:ocr' for pn in PAGES}
    def mentions(v):
        if isinstance(v,list):return any(mentions(x) for x in v)
        if isinstance(v,dict):return v.get('record_id',v.get('source_record')) in ids or any(mentions(x) for x in v.values())
        return False
    def bound(pos,right=False):
        shift=0
        for p in patches:
            if pos<=p['start']:return pos+shift
            if pos>=p['end']:shift+=len(p['after'])-p['end']+p['start']
            else:return p['start']+shift+(len(p['after']) if right else 0)
        return pos+shift
    def migrate(v):
        if isinstance(v,list):return [migrate(x) for x in v]
        if not isinstance(v,dict):return v
        rid=v.get('record_id',v.get('source_record'))
        if rid=='P0619:ocr' and 'start' in v and 'end' in v:
            v={**v,'start':bound(v['start']),'end':bound(v['end'],True)}
            for key in ['text','source_text']:
                if key in v:v[key]=new[rid]['text'][v['start']:v['end']]
            return v
        return {k:migrate(x) for k,x in v.items()}
    active=['box-units.jsonl','box-dispositions.jsonl','source-regions.jsonl','selection-overrides.jsonl',
            'review557-adoption-rules.jsonl','manual-dispositions.jsonl','manual-table-units.jsonl']
    for name in active:write_jsonl(rules/name,[migrate(r) for r in read_jsonl(rules/name) if not mentions(r)])
    write_jsonl(rules/'coordinate-spans.jsonl',[])
    config=read_json(PACKAGE/'config.json');config.update(corrected_source='preprocessing/output/corrected-v18-a',correction_ledger='preprocessing/corrections/batch-018/correction-log.json')
    config['additional_inputs'] += [f'preprocessing/corrections/batch-018/{n}.json' for n in ['regions','nodes','superseded-corrections']]
    write_json(PACKAGE/'config.json',config)
    regions=read_json(batch/'regions.json')
    for r in regions:
        image=batch/f'evidence/V18-P{r["pdf_page"]:04d}.png'
        r.update(review='CODEX_PDF_LAYOUT_REVIEW',evidence={'file':image.relative_to(ROOT).as_posix(),'sha256':sha(image)})
    write_jsonl(rules/'source-regions.jsonl',read_jsonl(rules/'source-regions.jsonl')+regions)
    s=SourceStore(check=False);rows=s.table('box-units.jsonl');disp=s.table('box-dispositions.jsonl');edges=s.table('flow-links.jsonl')
    by={(r['pdf_page'],r['name']):r for r in regions}
    for node in read_json(batch/'nodes.json'):
        pn=node['pdf_page'];key=f'V18:P{pn:04d}:{node["step"]}';ev=by[pn,'title']['evidence']
        context=[s.exact(r) for r in node['context']];body=[s.exact(r) for r in node['body']]
        meta={'boundary':'individually_reviewed_question_panels','step':node['step'],'condition_link_basis':'PDF_VISUAL_SAME_NODE_BOXES','graphic_dependency':True,'graphic_relations_inferred':False}
        rows.append({'key':key,'kind':'diagnostic_box','body_refs':body,'context_refs':context,'review_codes':[],
                     'review':'CODEX_PDF_LAYOUT_REVIEW','evidence':ev,'metadata':meta})
        if 'action' in node:
            action=key+':NO';branch=s.exact(node['no'])
            rows.append({'key':action,'kind':'diagnostic_action','body_refs':[s.exact(node['action'])],
              'context_refs':context+[body[0],branch],'review_codes':[],'review':'CODEX_PDF_LAYOUT_REVIEW','evidence':ev,
              'metadata':{**meta,'branch':'NO','parent_question':key}})
            edges.append({'source':key,'target':action,'branch':'NO','branch_source':branch,'page':pn,'evidence':ev})
    for r in regions:
        if r['role']=='navigation':disp.append({'source':s.exact(r),'status':'EXCLUDED_NON_TEXT','reason':'VERIFIED_DIAGRAM_NAVIGATION_PDF_ONLY','rule':'V18-NAVIGATION'})
    overrides=s.table('selection-overrides.jsonl')
    for pn in PAGES:
        rid=f'P{pn:04d}:native';ocr=f'P{pn:04d}:ocr';text=s.records[ocr]['text'];ev=by[pn,'title']['evidence']
        for ref in s.fragments(rid):
            if not ref['text'].strip():continue
            m=re.search(r'\s+'.join(re.escape(w) for w in ref['text'].split()),text,re.I)
            if not m:raise ValueError(('Unrepresented native text',pn,ref['text']))
            overrides.append({'id':f'V18-N{pn}-{ref["start"]}','source':ref,'action':'REPRESENT','targets':[s.ref(ocr,*m.span())],
              'reason':'PDF_CHECKED_NATIVE_REFERENCE_IN_TRANSCRIBED_NODE','review':'CODEX_PDF_VISUAL_REVIEW','evidence':ev})
    # p619: preserve both printed test panels and the repair callout; keep the
    # surrounding electrical drawing in the PDF, not in the retrieval prose.
    prior=read_jsonl(BASE/'output/corpus-v6-final-check-a/corpus_units.jsonl');lookup={u['key']:u for u in prior}
    image=PACKAGE/'reports/rules-v6-work/final-alignment/p619.png';ev={'file':image.relative_to(ROOT).as_posix(),'sha256':sha(image)}
    for number,keys in enumerate([['region:619:1:3'],['region:619:1:5','region:619:1:6']]):
        refs=[s.ref(r['record_id'],r['start'],r['end']) for key in keys for p in lookup[key]['body_parts'] if p['kind']=='source' for r in [migrate(p['source'])]]
        rows.append({'key':f'V18:P0619:test:{number}','kind':'reviewed_text_box','body_refs':refs,'context_refs':[],
          'review_codes':[],'review':'CODEX_PDF_LAYOUT_REVIEW','evidence':ev,'metadata':{'boundary':'individually_reviewed_pdf_box','graphic_relations_inferred':False}})
    rid='P0619:ocr';text=s.records[rid]['text'];repair=[]
    for value,start in [('Repair lead, refer to (para. 4-85).',0),('Repair lead connector, refer to',0),('(para. 4-85).',text.index('Repair lead connector'))]:
        a=text.index(value,start);repair.append(s.ref(rid,a,a+len(value)))
    rows.append({'key':'V18:P0619:repair','kind':'reviewed_text_box','body_refs':repair,'context_refs':[],
      'review_codes':[],'review':'CODEX_PDF_LAYOUT_REVIEW','evidence':ev,'metadata':{'boundary':'individually_reviewed_pdf_box','graphic_dependency':True,'graphic_relations_inferred':False}})
    # Exact repaired callout coordinates prevent diagram labels joining it.
    extra=[]
    for i,r in enumerate(repair):extra.append({**{k:r[k] for k in ['record_id','pdf_page','start','end','text']},
      'name':f'V18-619-repair-{i}','bbox':[140,595+i*10,270,608+i*10],'review':'CODEX_PDF_LAYOUT_REVIEW','evidence':ev})
    write_jsonl(rules/'source-regions.jsonl',s.table('source-regions.jsonl')+extra)
    write_jsonl(rules/'box-units.jsonl',rows)
    from .structure import Units,reviewed_tables,manual_tables
    from .boxes import reviewed_boxes
    s=SourceStore(check=False);u=Units(s);reviewed_tables(s,u);manual_tables(s,u);reviewed_boxes(s,u)
    proofs=s.table('figure-exclusions.jsonl')
    for layer in ['native','ocr']:
        rid=f'P0619:{layer}'
        for ref in s.fragments(rid):
            if not ref['text'].strip() or s.claimed(ref) or not ref['bbox'] or ref['bbox'][1]<135:continue
            disp.append({'source':ref,'status':'EXCLUDED_NON_TEXT','reason':'P619_DIAGRAM_OUTSIDE_PRINTED_TEST_AND_REPAIR_PANELS','rule':'V18-619-FIGURE'})
            proofs.append({'source':ref,'evidence':ev,'semantic_caption_generated':False})
    # p624 is complementary header text, not an alternative to its native ref.
    old_candidates=read_json(PACKAGE/'reports/rules-v6-work/final-alignment/candidates.json')
    ref=s.exact(next(r for r in old_candidates if r['pdf_page']==624)['source_refs'][0]);image=PACKAGE/'reports/rules-v6-work/final-alignment/3.png'
    overrides.append({'id':'V18-P624-COMPLEMENT','source':ref,'action':'PREFERRED','reason':'PDF_CONFIRMED_HEADER_TEXT_COMPLEMENTS_NATIVE_FIGURE_REFERENCE',
      'review':'CODEX_PDF_VISUAL_REVIEW','evidence':{'file':image.relative_to(ROOT).as_posix(),'sha256':sha(image)}})
    # p341: a single source bracket attaches the warning to PCB replacement.
    evp=PACKAGE/'reports/rules-v6-work/final-samples/p0341.png';ev={'file':evp.relative_to(ROOT).as_posix(),'sha256':sha(evp)}
    def unitrefs(key):return [s.exact(p['source']) for p in lookup[key]['body_parts'] if p['kind']=='source']
    rows.append({'key':'V18:P0341:pcb-replacement','kind':'reviewed_text_box','body_refs':unitrefs('region:341:1:3'),
      'context_refs':unitrefs('region:341:1:1')+unitrefs('region:341:1:2'),'review_codes':[],'review':'CODEX_PDF_LAYOUT_REVIEW','evidence':ev,
      'metadata':{'boundary':'individually_reviewed_bracket','condition_link_basis':'PDF_SAME_REPLACEMENT_CALLOUT','graphic_relations_inferred':False}})
    write_jsonl(rules/'box-units.jsonl',rows);write_jsonl(rules/'box-dispositions.jsonl',disp)
    write_jsonl(rules/'figure-exclusions.jsonl',proofs);write_jsonl(rules/'selection-overrides.jsonl',overrides)
    write_jsonl(rules/'flow-links.jsonl',edges);facts=read_json(rules/'flow-assertions.json');facts['edges']=[[e['source'],e['branch'],e['target']] for e in edges];write_json(rules/'flow-assertions.json',facts)
    write_json(rules/'final-artifact-exceptions.json',{'retranscribed_pages':list(PAGES),'repair_and_figure_scope_page':619,'warning_link_page':341,
      'header_complement_page':624,'baseline_v5_corrections_preserved':True})
    print({'retranscribed_pages':len(PAGES),'new_nodes':11,'explicit_flow_links':len(edges)})


if __name__=='__main__':main()
