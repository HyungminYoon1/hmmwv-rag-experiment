"""Adopt source-checked columns and explicit speed/index table rows."""
import re
from .common import *
from .final_text_repairs_v6 import REGIONS


def main():
    from .migrate_reviewed_boxes_v6 import main as migrate
    migrate(16)
    rules=PACKAGE/'rules/v6';batch=BASE/'corrections/batch-016';regions=read_json(batch/'regions.json')
    limits={f'P{pn:04d}:ocr':max(r['end'] for r in regions if r['pdf_page']==pn) for pn in REGIONS}
    def affected(v):
        if isinstance(v,list):return any(affected(x) for x in v)
        if isinstance(v,dict):
            rid=v.get('record_id',v.get('source_record'))
            return (rid in limits and v.get('start',limits[rid])<limits[rid]) or any(affected(x) for x in v.values())
        return False
    for name in ['box-units.jsonl','box-dispositions.jsonl','source-regions.jsonl','selection-overrides.jsonl','review557-adoption-rules.jsonl','manual-dispositions.jsonl']:
        write_jsonl(rules/name,[r for r in read_jsonl(rules/name) if not affected(r)])
    for r in regions:
        img=batch/f'evidence/V16-P{r["pdf_page"]:04d}.png'
        r.update(review='CODEX_PDF_LAYOUT_REVIEW',evidence={'file':img.relative_to(ROOT).as_posix(),'sha256':sha(img)})
    write_jsonl(rules/'source-regions.jsonl',read_jsonl(rules/'source-regions.jsonl')+regions)
    s=SourceStore(check=False);boxes=s.table('box-units.jsonl');disp=s.table('box-dispositions.jsonl')
    tables=s.table('manual-table-units.jsonl');overrides=s.table('selection-overrides.jsonl')
    by={(r['pdf_page'],r['name']):r for r in regions}
    for r in regions:
        pn=r['pdf_page'];ref=s.exact(r)
        if r['name'].startswith('diagram'):
            disp.append({'source':ref,'status':'EXCLUDED_NON_TEXT','reason':'PRINTED_GUIDE_DIAGRAM_TEMPLATE_PDF_ONLY','rule':'V16-SCOPE'});continue
        if pn==52 and r['name'].startswith('speed'):continue
        if r['name']=='heading':continue
        context=[s.exact(by[pn,'heading'])]
        boxes.append({'key':f'V16:P{pn:04d}:{r["name"]}','kind':'reviewed_text_box','body_refs':[ref],
          'context_refs':context,'review_codes':[],'review':'CODEX_PDF_LAYOUT_REVIEW','evidence':r['evidence'],
          'metadata':{'boundary':'individually_reviewed_pdf_box','graphic_relations_inferred':False,'graphic_dependency':pn in (126,128)}})
    def literal(rid,value,start=0):
        a=s.records[rid]['text'].index(value,start);return s.ref(rid,a,a+len(value))
    for suffix in ['R','D','2','1']:
        r=by[52,'speed-'+suffix];ref=s.exact(r);values=ref['text'].splitlines();pos=ref['start'];fields=[]
        for name,value in zip(['TRANSMISSION RANGE SELECTION','L Low Lock','H High','H/L High Lock'],values):
            fields.append({'name':name,'refs':[s.ref(ref['record_id'],pos,pos+len(value))],'text':value});pos+=len(value)+1
        tables.append({'key':'V16:P0052:speed:'+suffix,'fields':fields,
          'context_refs':[s.exact(by[52,k]) for k in ['heading','speed-title','speed-header']],
          'review':'CODEX_PDF_LAYOUT_REVIEW','metadata':{'table_id':'P0052:vehicle-speed','cell_occupancy_checked_against_pdf':True,
          'blank_cells_invented':False,'evidence':r['evidence']}})
    for pn,entries in [(132,[('BATTERY CIRCUIT','2-251'),('GLOWPLUGS CIRCUIT','2-303'),('STARTER CIRCUIT','2-261'),('FUEL SYSTEM','2-95'),('INTAKE AIR/EXHAUST','2-137'),('COMPRESSION/MECHANICAL','2-143')]),
                       (137,[('FUEL SYSTEM','2-95'),('INTAKE AIR/EXHAUST','2-137'),('COMPRESSION/MECHANICAL','2-143')])]:
        rid=f'P{pn:04d}:ocr';text=s.records[rid]['text'];start=text.index('PARAGRAPH PAGE');context=[s.ref(rid,start,start+len('PARAGRAPH PAGE'))]
        image=PACKAGE/f'reports/rules-v6-work/figure-scope/p{pn}.png';ev={'file':image.relative_to(ROOT).as_posix(),'sha256':sha(image)}
        for i,(name,page) in enumerate(entries):
            a=text.index(name,start);b=text.index(page,a)
            fields=[{'name':label,'refs':[r],'text':r['text']} for label,r in [('PARAGRAPH',s.ref(rid,a,a+len(name))),('PAGE',s.ref(rid,b,b+len(page)))]]
            tables.append({'key':f'V16:P{pn:04d}:index:{i}','fields':fields,'context_refs':context,
              'review':'CODEX_PDF_LAYOUT_REVIEW','metadata':{'table_id':f'P{pn:04d}:paragraph-index','cell_occupancy_checked_against_pdf':True,'blank_cells_invented':False,'evidence':ev}})
            for pos in range(a+len(name),b):
                if text[pos]=='|':disp.append({'source':s.ref(rid,pos,pos+1),'status':'LAYOUT_ONLY','reason':'TABLE_RULE_STROKE','rule':'V16-INDEX'})
    # Native headings are represented by the visually checked equivalent.
    for pn in REGIONS:
        rid=f'P{pn:04d}:native';ocr=f'P{pn:04d}:ocr';text=s.records[ocr]['text'];ev=by[pn,'heading']['evidence']
        for ref in s.fragments(rid):
            if not ref['text'].strip():continue
            m=re.search(r'\s+'.join(re.escape(w) for w in ref['text'].split()),text,re.I)
            if not m:raise ValueError(('Native heading not represented',pn,ref['text']))
            overrides.append({'id':f'V16-N{pn}-{ref["start"]}','source':ref,'action':'REPRESENT','targets':[s.ref(ocr,*m.span())],
              'reason':'PDF_CHECKED_HEADING_IN_TRANSCRIBED_REGION','review':'CODEX_PDF_VISUAL_REVIEW','evidence':ev})
    write_jsonl(rules/'box-units.jsonl',boxes);write_jsonl(rules/'box-dispositions.jsonl',disp)
    write_jsonl(rules/'manual-table-units.jsonl',tables);write_jsonl(rules/'selection-overrides.jsonl',overrides)
    config=read_json(PACKAGE/'config.json');config['additional_inputs'].append('preprocessing/corrections/batch-016/regions.json');write_json(PACKAGE/'config.json',config)
    print({'table_rows_added':13,'transcribed_pages':3})


if __name__=='__main__':main()
