"""Freeze source-bound table/flow repairs without changing any v4 artifact."""
from collections import defaultdict
from copy import deepcopy
import json
import shutil
from .common import (SourceStore, ROOT, BASE, PACKAGE, read_json, read_jsonl,
                     write_json, write_jsonl, sha)

RULES = PACKAGE/'rules/v5'
NEW = BASE/'corrections/batch-008'


def initialize(source='corrected-v8-a'):
    if RULES.exists():
        raise ValueError('The version already exists')
    audit = read_json(BASE/f'audit/{source}.json')
    if audit['status'] != 'PASS':
        raise ValueError('Source correction audit must pass first')
    shutil.copytree(PACKAGE/'rules/v4', RULES)
    regions = read_json(NEW/'source-regions.json')
    changed = {r['record_id'] for r in regions}
    removed = []
    # These three partial OCR/native matches were superseded by full PDF
    # region review. No old offset is silently shifted into new text.
    for path in sorted(RULES.glob('*.jsonl')):
        rows = read_jsonl(path); kept = []
        for row in rows:
            touched = [rid for rid in changed if rid in json.dumps(row)]
            if touched:
                if path.name != 'review557-adoption-rules.jsonl':
                    raise ValueError('Unreviewed legacy reference migration: '+path.name)
                removed.append({'file': path.name, 'row': row, 'record_ids': touched,
                                'reason': 'Replaced by v5 reviewed regions and literal alternative matching'})
            else:
                kept.append(row)
        if len(kept) != len(rows):
            write_jsonl(path, kept)
    assert len(removed) == 3
    write_jsonl(RULES/'source-regions.jsonl', read_jsonl(RULES/'source-regions.jsonl')+regions)
    write_json(RULES/'v8-reference-migration.json', {
        'from': 'corrected-v7-a', 'to': source, 'removed_legacy_rules': removed,
        'changed_records': sorted(changed), 'unchanged_references_reused_without_offset_changes': True})
    config = read_json(PACKAGE/'config.json')
    config.update(corpus_version='hmmwv-v5', rules_path=RULES.relative_to(PACKAGE).as_posix(),
                  corrected_source='preprocessing/output/'+source,
                  correction_ledger=(NEW/'correction-log.json').relative_to(ROOT).as_posix())
    config['additional_inputs'] += [p.relative_to(ROOT).as_posix() for p in
                                   [NEW/'source-regions.json', NEW/'table-cell-map.json']]
    write_json(PACKAGE/'config.json', config)


class Builder:
    def __init__(self):
        self.s = SourceStore(check=False)
        self.rows = read_jsonl(RULES/'box-units.jsonl')
        self.tables = read_jsonl(RULES/'manual-table-units.jsonl')
        self.dispositions = read_jsonl(RULES/'box-dispositions.jsonl')
        self.regions = defaultdict(dict); self.evidence = {}; self.edges = []
        for r in read_json(NEW/'source-regions.json'):
            self.regions[r['pdf_page']][r['name']] = self.s.ref(r['record_id'], r['start'], r['end'])
            self.evidence[r['pdf_page']] = r['evidence']

    def refs(self, pn, *names):
        return [self.regions[pn][n] for n in names]

    def add(self, pn, name, body, context, kind='reviewed_region', codes=(), **metadata):
        key = f'P{pn:04d}:'+name
        refs = body+context
        self.rows.append({'key': key, 'kind': kind, 'body_refs': body, 'context_refs': context,
                          'metadata': {'boundary': 'recorded_pdf_region', 'graphic_relations_inferred': False,
                                       'cross_page_join': len({r['pdf_page'] for r in refs}) > 1, **metadata},
                          'review': 'CODEX_PDF_LAYOUT_REVIEW', 'review_codes': list(codes),
                          'evidence': self.evidence[pn]})
        return key

    def header(self, pn):
        return self.refs(pn, 'header')

    def edge(self, pn, node, branch, target, path_context=()):
        self.edges.append({'page': pn, 'source': f'P{pn:04d}:question:{node}', 'branch': branch,
                           'target': target, 'branch_source': self.refs(pn, node+'-'+branch.lower())[0],
                           'path_context': list(path_context), 'basis': 'PDF_REVIEWED_VISIBLE_EDGE',
                           'evidence': self.evidence[pn]})

    def reference_pages(self):
        for pn, names in {408: ['warning','steice91','multimeter','replace'],
                          474: ['connector-location','steice91','multimeter'], 502: ['caution']}.items():
            for name in names:
                context = self.header(pn)+(self.refs(408, 'exception') if (pn,name)==(408,'replace') else [])
                self.add(pn, name, self.refs(pn,name), context)
        for pn, pairs in {408: [('engine-labels','engine-caption'),('harness-labels','harness-caption'),
                               ('controller-labels','controller-caption')],
                          474: [('figure-labels',None)], 502: [('figure-labels','figure-caption')]}.items():
            for name, caption in pairs:
                context = self.header(pn)+(self.refs(pn,caption) if caption else [])
                self.add(pn, name, self.refs(pn,name), context, kind='figure_labels',
                         graphic_dependency=True, wiring_topology_transcribed=False,
                         codes=['FLOW_ANNOTATION_REVIEW'])
        for name in ['steice89','multimeter']:
            self.add(613,name,self.refs(613,name),self.header(612),
                     applies_to_questions=['P0612:question:17','P0612:question:19'])
        rid='P0613:ocr'; text=self.s.records[rid]['text']
        start=text.index('SPARE FUSE')
        self.dispositions.append({'source':self.s.ref(rid,start,len(text)), 'status':'NEEDS_REVIEW',
                                  'reason':'CONTROL_BOX_DIAGRAM_OCR_REQUIRES_LABEL_AND_TOPOLOGY_REVIEW',
                                  'rule':'V5_GRAPHIC_PENDING', 'evidence':self.evidence[613]})

    def table_units(self):
        for spec in read_json(NEW/'table-cell-map.json'):
            pn=spec['page']; name=spec['name']; count=len(spec['rows'])
            context=self.header(pn)+self.refs(pn,name+'-header')
            if pn==408:
                context += self.refs(pn,'exception','controller-caption')
            elif pn==474:
                ref=self.refs(pn,'figure-labels')[0]
                context += [self.s.ref(ref['record_id'],ref['start'],ref['start']+len('FUEL GAUGE'))]
            elif pn==502:
                context += self.refs(pn,'caution')
            elif pn==575:
                context += self.refs(pn,'table-note')+self.refs(574,'B9-id','B9-known','B9-question')
            for i, fields in enumerate(spec['rows'],1):
                self.tables.append({'key':f'P{pn:04d}:{name}:row:{i}',
                    'fields':[{'name':label,'text':self.regions[pn][ref]['text'],
                               'refs':self.refs(pn,ref)} for label,ref in fields],
                    'context_refs':context, 'metadata':{'table_id':f'P{pn:04d}:{name}', 'row':i,
                    'expected_rows':count, 'cross_page_join':pn==575, 'cell_occupancy_checked_against_pdf':True,
                    'source_issues':['P0408_MISSING_TOLERANCE_NUMBER'] if pn==408 and i==1 else []},
                    'review':'CODEX_PDF_LAYOUT_REVIEW', 'evidence':self.evidence[pn]})

    def ordinary_flow(self,pn,steps):
        self.add(pn,'incoming-reference',self.refs(pn,'start'),self.header(pn),'flow_annotation',
                 graphic_dependency=True, reference_role='incoming')
        for i,step in enumerate(steps):
            context=self.header(pn)+self.refs(pn,step+'-id',step+'-known',step+'-possible')
            body=self.refs(pn,step+'-question',step+'-options',step+'-reason')
            metadata={}
            if pn==574 and step=='B7':
                body+=self.refs(575,'hydro-method')
            if pn==574 and step=='B9':
                metadata['reference_table']='P0575:answers'
            if pn==612 and step in ('17','19'):
                metadata['reference_units']=['P0613:steice89','P0613:multimeter']
            if pn==828 and step=='B2':
                ref=self.refs(829,'B2-reference')[0]
                context+=[self.s.ref(ref['record_id'],ref['start'],ref['start']+ref['text'].index('\n'))]
            if pn==828 and step=='B3':
                body+=self.refs(829,'B3-interpretation')
            self.add(pn,'question:'+step,body,context,'diagnostic_box',step=step,
                     graphic_dependency=True, condition_link_basis='PDF_REVIEWED_EXPLICIT_BOX_RELATION',
                     condition_roles=['KNOWN INFO','POSSIBLE PROBLEMS'], **metadata)
            if step+'-exit' in self.regions[pn]:
                body=self.refs(pn,step+'-exit')
                if pn==828 and step=='B3':body+=self.refs(829,'B3-note')
                key=self.add(pn,'branch:'+step+':NO',body,
                    context+self.refs(pn,step+'-question',step+'-no'),'flow_annotation',step=step,
                    graphic_dependency=True, branch_label='NO',parent_question=f'P{pn:04d}:question:{step}',
                    branch_relation='PDF_REVIEWED_VISIBLE_EDGE',not_an_unconditional_action=True)
                self.edge(pn,step,'NO',key)
                if pn==574:
                    # Both paths continue; the NO ellipse is a reminder, not a repair exit.
                    self.edges.append({'page':pn,'source':key,'branch':None,
                        'target':f'P{pn:04d}:question:{steps[i+1]}',
                        'basis':'PDF_REVIEWED_VISIBLE_EDGE','evidence':self.evidence[pn]})
            if step+'-continue' in self.regions[pn]:
                key=self.add(pn,'branch:'+step+':YES',self.refs(pn,step+'-continue'),
                    context+self.refs(pn,step+'-question',step+'-yes'),'flow_annotation',step=step,
                    graphic_dependency=True, branch_label='YES',parent_question=f'P{pn:04d}:question:{step}',
                    branch_relation='PDF_REVIEWED_VISIBLE_EDGE',not_an_unconditional_action=True)
                self.edge(pn,step,'YES',key)
            elif step+'-yes' in self.regions[pn]:
                self.edge(pn,step,'YES',f'P{pn:04d}:question:{steps[i+1]}')
                self.dispositions.append({'source':self.refs(pn,step+'-yes')[0],
                    'status':'EXCLUDED_NON_TEXT','reason':'BRANCH_PRESERVED_IN_REVIEWED_FLOW_LINK',
                    'rule':'V5_LITERAL_BRANCH','evidence':self.evidence[pn]})
        if pn==828:
            for step in ['B1','B2']:
                self.add(829,step+'-reference',self.refs(829,step+'-reference'),
                         self.header(829)+self.header(828)+self.refs(828,step+'-id',step+'-known',step+'-question'),
                         linked_question='P0828:question:'+step, link_basis='PDF_OPPOSITE_PAGE_ALIGNED_REFERENCE')

    def transmission_flow(self):
        pn=547; header=self.header(pn)+self.refs(pn,'title')
        self.add(pn,'description',self.refs(pn,'description'),header)
        self.add(pn,'wire-label',self.refs(pn,'wire-label'),header,'figure_labels',graphic_dependency=True)
        for prefix,title in [('L','low-title'),('H','high-title')]:
            for index in [1,2]:
                step=prefix+str(index); path_context=[]
                if index==2:path_context=self.refs(pn,prefix+'1-question',prefix+'1-yes')
                context=header+self.refs(pn,title)+path_context
                self.add(pn,'question:'+step,self.refs(pn,step+'-question'),context,'diagnostic_box',
                         step=step,graphic_dependency=True,condition_link_basis='PDF_REVIEWED_EXPLICIT_PATH',
                         local_identifier_printed=False)
                for branch,suffix in [('NO','exit'),('YES','continue')]:
                    if step+'-'+suffix not in self.regions[pn]:continue
                    key=self.add(pn,'branch:'+step+':'+branch,self.refs(pn,step+'-'+suffix),
                        context+self.refs(pn,step+'-question',step+'-'+branch.lower()),'flow_annotation',
                        step=step,graphic_dependency=True,branch_label=branch,
                        parent_question=f'P0547:question:{step}',branch_relation='PDF_REVIEWED_VISIBLE_EDGE',
                        not_an_unconditional_action=True)
                    self.edge(pn,step,branch,key,path_context)
                if index==1:
                    self.edge(pn,step,'YES',f'P0547:question:{prefix}2')

    def run(self):
        self.reference_pages(); self.table_units(); self.transmission_flow()
        self.ordinary_flow(574,['B7','B8','B9'])
        self.ordinary_flow(612,['17','18','19'])
        self.ordinary_flow(828,['B1','B2','B3'])
        write_jsonl(RULES/'box-units.jsonl',self.rows)
        write_jsonl(RULES/'manual-table-units.jsonl',self.tables)
        write_jsonl(RULES/'box-dispositions.jsonl',self.dispositions)
        write_jsonl(RULES/'flow-links.jsonl',self.edges)
        issues=read_jsonl(RULES/'source-issues.jsonl')
        issues.append({'id':'P0408_MISSING_TOLERANCE_NUMBER','pdf_page':408,
            'status':'SOURCE_VALUE_INCOMPLETE_PRESERVED',
            'description':'PIN 1–5 셀의 PDF에는 130 Ω ± Ω로 인쇄되어 있고 ± 뒤 숫자가 없다. 숫자를 추정하지 않고 문자 그대로 보존했다.',
            'evidence':self.evidence[408]})
        if 'wound' in self.regions[612]['17-reason']['text']:
            issues.append({'id':'P0612_PRINTED_WOUND','pdf_page':612,'status':'SOURCE_TYPO_PRESERVED',
                'description':'원문에 No voltage wound indicate a로 인쇄되어 있어 would로 문법 교정하지 않았다.',
                'evidence':self.evidence[612]})
        write_jsonl(RULES/'source-issues.jsonl',issues)
        write_json(RULES/'finding-resolutions-v5.json', {
            'audit':'OCR_전체구조_검토결과_2026-09-24.md', 'confirmed_case_pages':[408,474,502,547,575,612,829],
            'related_page_review':[574,613,828], 'table_rows_recovered_or_separated':23,
            'source_issues_preserved':['P0408_MISSING_TOLERANCE_NUMBER'],
            'partial_page_613':'Two test cards reviewed; diagram raw OCR retained pending separate review',
            'global_corpus_ready':False,'evaluation_questions_read':False,
            'human_source_review':'NOT_PERFORMED'})
        print('v5 contracts prepared:',len(self.rows),'boxes;',len(self.tables),'table rows;',len(self.edges),'flow links')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rules',default='rules/v5')
    parser.add_argument('--batch',default='batch-008')
    parser.add_argument('--source',default='corrected-v8-a')
    args=parser.parse_args()
    RULES=PACKAGE/args.rules;NEW=BASE/'corrections'/args.batch
    initialize(args.source); Builder().run()
