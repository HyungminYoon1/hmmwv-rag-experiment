"""Record v6's individually checked condition links and source migration."""
import json
from collections import defaultdict
from .common import ROOT,BASE,PACKAGE,SourceStore,read_json,read_jsonl,write_json,write_jsonl


def main():
    rules=PACKAGE/'rules/v6';baseline=PACKAGE/'rules/v5-final';batch=BASE/'corrections/batch-010'
    removed=[];changed={f'P{n:04d}:ocr' for n in (546,860,861,862,863)}
    for name in ['review557-adoption-rules.jsonl','selection-overrides.jsonl']:
        rows=read_jsonl(baseline/name);keep=[]
        for row in rows:
            if any(rid in json.dumps(row) for rid in changed):removed.append({'file':name,'row':row})
            else:keep.append(row)
        write_jsonl(rules/name,keep)
    write_json(rules/'v10-reference-migration.json',{'from':'corrected-v9-a','to':'corrected-v10-a','replaced_rules':removed,
               'basis':'New individually checked literal regions replace earlier partial source alignments.'})
    config=read_json(PACKAGE/'config.json');config.update(corrected_source='preprocessing/output/corrected-v10-a',correction_ledger='preprocessing/corrections/batch-010/correction-log.json')
    config['additional_inputs']=sorted(set(config['additional_inputs']+['preprocessing/corrections/batch-010/source-regions.json']))
    write_json(PACKAGE/'config.json',config)
    # Old coordinate snapshots for these records have old corrected offsets.
    write_jsonl(rules/'coordinate-spans.jsonl',[r for r in read_jsonl(rules/'coordinate-spans.jsonl') if r['record_id'] not in changed])
    new=read_json(batch/'source-regions.json')
    write_jsonl(rules/'source-regions.jsonl',read_jsonl(baseline/'source-regions.jsonl')+new)
    s=SourceStore(check=False);regions=defaultdict(dict);evidence={}
    for r in new:regions[r['pdf_page']][r['name']]=s.ref(r['record_id'],r['start'],r['end']);evidence[r['pdf_page']]=r['evidence']
    rows=read_jsonl(baseline/'box-units.jsonl');disps=read_jsonl(baseline/'box-dispositions.jsonl');edges=read_jsonl(baseline/'flow-links.jsonl')
    added=[]
    def rr(p,*names):return [regions[p][n] for n in names]
    def add(p,n,body,context=(),**meta):
        title=rr(p,'header') if 'header' in regions[p] else [s.ref(f'P{p:04d}:native')]
        r={'key':f'P{p:04d}:v6:{n}','kind':'diagnostic_box','body_refs':rr(p,*body),
           'context_refs':title+rr(p,*context),'metadata':{'boundary':'recorded_pdf_region','graphic_dependency':True,
           'graphic_relations_inferred':False,'condition_link_basis':'PDF_REVIEWED_EXPLICIT_BOX_RELATION',**meta},
           'review':'CODEX_PDF_LAYOUT_REVIEW','review_codes':[],'evidence':evidence[p]}
        rows.append(r);added.append(r);return r['key']
    def edge(p,src,branch,target,ctx=()):
        b=regions[p][branch] if branch else None
        edges.append({'page':p,'source':f'P{p:04d}:v6:{src}','branch':b['text'] if b else None,
            'target':f'P{p:04d}:v6:{target}','branch_source':b,'path_context':list(ctx),
            'basis':'PDF_REVIEWED_VISIBLE_EDGE','evidence':evidence[p]})
    for l in 'ABC':
        add(546,l+'-question',[l+'-question'],[l+'-title',l+'-wire'])
        for name,branch in [('repair','no'),('ds','yes')]:
            add(546,l+'-'+name,[l+'-'+name],[l+'-title',l+'-wire',l+'-question',l+'-'+branch],branch=branch.upper())
            edge(546,l+'-question',l+'-'+branch,l+'-'+name)
    add(860,'question1',['step1','question1'],['title','note','mode','go1','caution'])
    for name,branch in [('continue3','yes'),('next','no')]:
        add(860,name,[name],['note','caution','step1','question1',branch],branch=branch.upper())
        edge(860,'question1',branch,name)
    add(861,'light-question',['light-question'],['mode','go1'])
    add(861,'partial-display',['partial-display'],['light-question','light-yes'],branch='YES')
    add(861,'question2',['step2','question2'],['light-question','light-no'],branch='NO')
    edge(861,'light-question','light-yes','partial-display');edge(861,'light-question','light-no','question2')
    add(861,'continue3',['continue3'],['step2','question2','q2-yes'],branch='YES');edge(861,'question2','q2-yes','continue3')
    add(861,'battery-question',['no-power','battery-test','battery-question'],['step2','question2','q2-no'],branch='NO');edge(861,'question2','q2-no','battery-question')
    for name,branch,body in [('cable-action','battery-no',['cable-action']),('charge','battery-yes',['charge','return'])]:
        add(861,name,body,['battery-test','battery-question',branch],branch=regions[861][branch]['text']);edge(861,'battery-question',branch,name)
    add(862,'question3',['step3','question3'],['go1','mode'])
    add(862,'retry-question',['retry','retry-question'],['step3','question3','q3-no'],branch='NO');edge(862,'question3','q3-no','retry-question')
    add(862,'replace',['replace'],['retry','retry-question','retry-no'],branch='NO');edge(862,'retry-question','retry-no','replace')
    add(862,'display-check',['display-check','note','next'],['step3'],requires_graphic_display_sequence=True)
    edge(862,'question3','q3-yes','display-check');edge(862,'retry-question','retry-yes','display-check')
    add(863,'question-pass',['question-pass'],['go1','mode'])
    add(863,'repeat3-question',['repeat3','repeat3-question'],['question-pass','pass-no','confidence-note'],branch='NO');edge(863,'question-pass','pass-no','repeat3-question')
    add(863,'replace3',['replace3'],['repeat3','repeat3-question','repeat3-no'],branch='NO');edge(863,'repeat3-question','repeat3-no','replace3')
    add(863,'question-vin',['step4','question-vin'],['vin-note'])
    edge(863,'question-pass','pass-yes','question-vin');edge(863,'repeat3-question','repeat3-yes','question-vin')
    add(863,'repeat4-question',['repeat4','repeat4-question'],['step4','question-vin','vin-no','vin-note'],branch='NO');edge(863,'question-vin','vin-no','repeat4-question')
    add(863,'replace4',['replace4'],['repeat4','repeat4-question','repeat4-no'],branch='NO');edge(863,'repeat4-question','repeat4-no','replace4')
    add(863,'continue',['continue'],['step4','question-vin'])
    edge(863,'question-vin','vin-yes','continue');edge(863,'repeat4-question','repeat4-yes','continue')
    # This is an explicit printed two-column table, not a graphical display.
    tables=read_jsonl(baseline/'manual-table-units.jsonl')
    tables.append({'key':'P0862:confidence:row:1','fields':[
        {'name':'TEST NO.','text':'66','refs':rr(862,'table66')},
        {'name':'TEST','text':'CONFIDENCE\nTEST','refs':rr(862,'table-confidence')}],
        'context_refs':[s.ref('P0862:native')]+rr(862,'table-header'),
        'metadata':{'table_id':'P0862:confidence','row':1,'expected_rows':1,'cell_occupancy_checked_against_pdf':True},
        'review':'CODEX_PDF_LAYOUT_REVIEW','evidence':evidence[862]})
    # Preserve all remaining transcribed captions and labels; labels are explicitly
    # identified for the text-only scope decision rather than silently dropped.
    claimed={(r['record_id'],r['start'],r['end']) for x in added for r in x['body_refs']+x['context_refs']}
    claimed.update((r['record_id'],r['start'],r['end']) for r in rr(862,'table-header','table66','table-confidence'))
    branches={(e['branch_source']['record_id'],e['branch_source']['start'],e['branch_source']['end']) for e in edges if e.get('branch_source')}
    for pn,rs in regions.items():
        for name,r in rs.items():
            if (r['record_id'],r['start'],r['end']) in claimed:continue
            if (r['record_id'],r['start'],r['end']) in branches:
                disps.append({'source':r,'status':'EXCLUDED_NON_TEXT','reason':'BRANCH_PRESERVED_IN_REVIEWED_FLOW_LINK','rule':'V6_LITERAL_BRANCH','evidence':evidence[pn]})
            else:
                key=add(pn,name,[name],[],text_role='figure_annotation' if name in ('labels','display-labels') else 'caption')
    write_jsonl(rules/'box-units.jsonl',rows);write_jsonl(rules/'box-dispositions.jsonl',disps)
    write_jsonl(rules/'manual-table-units.jsonl',tables);write_jsonl(rules/'flow-links.jsonl',edges)
    assertions=read_json(rules/'flow-assertions.json');assertions['edges']=[[e['source'],e['branch'],e['target']] for e in edges];write_json(rules/'flow-assertions.json',assertions)
    print({'new_units':len(added),'flow_edges':len(edges),'removed_old_rules':len(removed)})

if __name__=='__main__':main()
