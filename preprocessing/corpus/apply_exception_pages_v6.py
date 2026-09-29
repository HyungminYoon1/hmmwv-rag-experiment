"""Replace only the six reviewed exception-page contracts, preserving history."""
import re
import shutil
from .common import *
from .exception_pages_v6 import PAGES


def main():
    rules=PACKAGE/'rules/v6';backup=PACKAGE/'reports/rules-v6-work/rules-before-v15'
    if backup.exists():raise ValueError('Already applied')
    shutil.copytree(rules,backup)
    rids={f'P{pn:04d}:ocr' for pn in PAGES}
    def mentions(v):
        if isinstance(v,list):return any(mentions(x) for x in v)
        if isinstance(v,dict):return v.get('record_id',v.get('source_record')) in rids or any(mentions(x) for x in v.values())
        return False
    for name in ['box-units.jsonl','box-dispositions.jsonl','source-regions.jsonl','coordinate-spans.jsonl','selection-overrides.jsonl','review557-adoption-rules.jsonl','manual-dispositions.jsonl']:
        p=rules/name
        if p.exists():write_jsonl(p,[r for r in read_jsonl(p) if not mentions(r)])
    config=read_json(PACKAGE/'config.json');config.update(corrected_source='preprocessing/output/corrected-v15-a',correction_ledger='preprocessing/corrections/batch-015/correction-log.json')
    config['additional_inputs']+=['preprocessing/corrections/batch-015/regions.json','preprocessing/corrections/batch-015/nodes.json','preprocessing/corrections/batch-015/superseded-corrections.json']
    write_json(PACKAGE/'config.json',config)
    batch=BASE/'corrections/batch-015';regions=read_json(batch/'regions.json');existing=read_jsonl(rules/'source-regions.jsonl')
    for r in regions:
        image=batch/f'evidence/V15-P{r["pdf_page"]:04d}.png'
        r.update(review='CODEX_PDF_LAYOUT_REVIEW',evidence={'file':image.relative_to(ROOT).as_posix(),'sha256':sha(image)})
    write_jsonl(rules/'source-regions.jsonl',existing+regions)
    s=SourceStore(check=False);boxes=s.table('box-units.jsonl');dispositions=s.table('box-dispositions.jsonl');edges=s.table('flow-links.jsonl')
    nodes=read_json(batch/'nodes.json');lookup={(r['pdf_page'],r['name']):r for r in regions}
    def exact(r):return s.ref(r['record_id'],r['start'],r['end'])
    for n in nodes:
        pn=n['pdf_page'];key=f'V15:P{pn:04d}:{n["step"]}';evidence=lookup[pn,'title']['evidence']
        context=[exact(r) for r in n['context']];body=[exact(n[k]) for k in ('question','options','reason')]
        meta={'boundary':'individually_reviewed_question_panels','step':n['step'],'condition_link_basis':'PDF_VISUAL_SAME_NODE_BOXES','graphic_relations_inferred':False,'graphic_dependency':True}
        boxes.append({'key':key,'kind':'diagnostic_box','body_refs':body,'context_refs':context,'review_codes':[],
                      'review':'CODEX_PDF_LAYOUT_REVIEW','metadata':meta,'evidence':evidence})
        action=key+':NO'
        boxes.append({'key':action,'kind':'diagnostic_action','body_refs':[exact(n['action'])],
          'context_refs':context+[exact(n['question']),exact(n['no'])],'review_codes':[],
          'review':'CODEX_PDF_LAYOUT_REVIEW','metadata':{**meta,'branch':'NO','parent_question':key},'evidence':evidence})
        edges.append({'source':key,'target':action,'branch':'NO','branch_source':exact(n['no']),'page':pn,'evidence':evidence})
        dispositions.append({'source':exact(n['yes']),'status':'EXCLUDED_NON_TEXT','reason':'YES_CONTINUATION_RETAINED_AS_PDF_FLOW_METADATA','rule':'V15-FLOW'})
    for r in regions:
        if r['role']=='navigation':dispositions.append({'source':exact(r),'status':'EXCLUDED_NON_TEXT','reason':'PDF_FLOW_NAVIGATION_METADATA','rule':'V15-FLOW'})
    # Preserve native page references through explicit, PDF-confirmed matches.
    overrides=s.table('selection-overrides.jsonl')
    for pn in PAGES:
        rid=f'P{pn:04d}:native';ocr=f'P{pn:04d}:ocr';text=s.records[ocr]['text'];ev=lookup[pn,'title']['evidence']
        for ref in s.fragments(rid):
            if not ref['text'].strip():continue
            pattern=r'\s+'.join(re.escape(w) for w in ref['text'].split());m=re.search(pattern,text,re.I)
            if not m:raise ValueError(('Unrepresented native text',pn,ref['text']))
            overrides.append({'id':f'V15-N{pn}-{ref["start"]}','source':ref,'action':'REPRESENT','targets':[s.ref(ocr,*m.span())],
                'reason':'PDF_CHECKED_NATIVE_FRAGMENT_IN_FULL_REGION_TRANSCRIPTION','review':'CODEX_PDF_VISUAL_REVIEW','evidence':ev})
    write_jsonl(rules/'box-units.jsonl',boxes);write_jsonl(rules/'box-dispositions.jsonl',dispositions)
    write_jsonl(rules/'selection-overrides.jsonl',overrides);write_jsonl(rules/'flow-links.jsonl',edges)
    facts=read_json(rules/'flow-assertions.json');facts['edges']=[[e['source'],e['branch'],e['target']] for e in edges];write_json(rules/'flow-assertions.json',facts)
    print({'exception_pages':len(PAGES),'new_nodes':len(nodes),'new_NO_links':len(nodes)})


if __name__=='__main__':main()
