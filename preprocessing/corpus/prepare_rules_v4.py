"""Apply reviewed v4 relations and retranscribed boxes; preserve v3 unchanged."""
from collections import defaultdict
from .common import SourceStore,ROOT,PACKAGE,read_json,read_jsonl,write_json,write_jsonl,sha
from .structure import page_titles

RULES=PACKAGE/'rules/v4'
EVIDENCE=PACKAGE/'reports/rules-v4-work'
LEFT={287:[[56,216,167,378],[56,390,167,551],[57,562,167,724]],
      330:[[62,116,173,308],[64,318,175,509],[64,515,175,702]],
      332:[[63,116,174,292],[64,311,175,496],[65,510,175,696]],
      334:[[62,116,174,292],[64,328,175,504],[66,524,178,690]]}
STEPS={287:['B1','B2','B3'],330:['10','11','12'],332:['13','14','15'],334:['16','17','18']}


class Builder:
    def __init__(self):
        self.s=SourceStore();self.rows=read_jsonl(PACKAGE/'rules/v3/box-units.jsonl')
        self.dispositions=read_jsonl(PACKAGE/'rules/v3/box-dispositions.jsonl')
        self.log=[]

    def evidence(self,pn):
        p=EVIDENCE/f'page-{pn:04d}.png'
        return {'file':p.relative_to(ROOT).as_posix(),'sha256':sha(p)}

    def lines(self,pn):
        return [r for r in self.s.fragments(f'P{pn:04d}:native') if r['text'].strip()]

    def rect(self,pn,box):
        x0,y0,x1,y1=box
        return sorted([r for r in self.lines(pn) if r['bbox'] and x0-1<=r['bbox'][0]
                       and r['bbox'][2]<=x1+1 and y0<=(r['bbox'][1]+r['bbox'][3])/2<y1],
                      key=lambda r:(r['bbox'][1],r['bbox'][0],r['start']))

    def add(self,key,body,ctx=(),kind='reviewed_region',metadata=None,codes=()):
        if not body:raise ValueError('Empty reviewed body: '+key)
        pn=body[0]['pdf_page'];seen=set();context=[]
        for r in ctx:
            k=(r['record_id'],r['start'],r['end'])
            if k not in seen:context.append(r);seen.add(k)
        row={'key':key,'kind':kind,'body_refs':body,'context_refs':context,
             'metadata':{'boundary':'recorded_pdf_region','graphic_relations_inferred':False,
                         'cross_page_join':len({r['pdf_page'] for r in body+context})>1,
                         **(metadata or {})},'review':'CODEX_PDF_LAYOUT_REVIEW',
             'review_codes':list(codes),'evidence':self.evidence(pn)}
        self.rows.append(row);return row

    def native(self):
        originals={r['key']:r for r in self.rows}
        self.rows=[r for r in self.rows if not any(r['key'].startswith(f'P{pn:04d}:') for pn in LEFT)]
        all_refs={pn:self.lines(pn) for pn in LEFT}
        note=self.rect(331,[120,142,259,273])
        warnings={330:self.rect(331,[128,580,260,665]),332:self.rect(333,[130,370,290,440]),
                  334:self.rect(335,[133,197,300,269])}
        for pn,steps in STEPS.items():
            title=page_titles(self.s,pn)
            contexts=[self.rect(pn,b) for b in LEFT[pn]]
            qs=[]
            for i,step in enumerate(steps):
                old=originals[f'P{pn:04d}:question:{step}']
                ident=[r for r in old['context_refs'] if r['text']==step]
                assert len(ident)==1
                conditions=[] if pn==287 and i==0 else contexts[i-1 if pn==287 else i]
                qrefs=self.rect(pn,old['metadata']['pdf_box'])
                qrefs=[r for r in qrefs if r['text']!=step]
                ctx=title+ident+conditions+(note if pn!=287 else [])
                row=self.add(old['key'],old['body_refs'],ctx,'diagnostic_box',{
                    **old['metadata'],'condition_link_basis':'PDF_REVIEWED_EXPLICIT_BOX_RELATION',
                    'cross_page_join':pn!=287,
                    'local_condition_present':bool(conditions),'reference_page_reviewed':True,
                    'condition_roles':['KNOWN INFO','POSSIBLE PROBLEMS'],
                    'left_region':None if not conditions else LEFT[pn][i-1 if pn==287 else i],
                    'reference_units':['P0288:model-note'] if step=='B1' else [],
                    'analyzer_precondition_source':331 if pn!=287 else None})
                qs.append((row,qrefs,ident,conditions))
                self.log.append({'pdf_page':pn,'step':step,'left_box':row['metadata']['left_region'],
                                 'resolution':'EXPLICIT_RELATION' if conditions else 'NO_LOCAL_CONDITION_BOX',
                                 'evidence':self.evidence(pn)})
            no=sorted([r for r in all_refs[pn] if r['text']=='NO'],key=lambda r:r['bbox'][1])
            yes=sorted([r for r in all_refs[pn] if r['text']=='YES'],key=lambda r:r['bbox'][1])
            assert len(no)==len(steps)==len(yes)
            old_annotations=[r for k,r in originals.items() if k.startswith(f'P{pn:04d}:annotation:')]
            # Full ellipse boundaries were inspected on the rendered PDF.
            groups={287:[[2,3],[4,5],[6]],330:[[2],[3,4],[5,6,7]],
                    332:[[2],[3,4,5],[6,7]],334:[[2,3,4],[5],[6,7]]}[pn]
            for i,numbers in enumerate(groups):
                body=[r for n in numbers for r in originals[f'P{pn:04d}:annotation:{n}']['body_refs']]
                row,qrefs,ident,conditions=qs[i]
                warning=warnings[pn] if (pn,i) in [(330,2),(332,1),(334,0)] else []
                self.add(f'P{pn:04d}:branch:{steps[i]}:NO',body,title+ident+conditions+qrefs+[no[i]]+warning,
                         'flow_annotation',{'step':steps[i],'graphic_dependency':True,'branch_label':'NO',
                         'parent_question':row['key'],'branch_relation':'PDF_REVIEWED_VISIBLE_EDGE',
                         'warning_applies_to':'PCB/distribution box harness disconnection and replacement' if warning else None,
                         'not_an_unconditional_action':True})
            start=originals[f'P{pn:04d}:annotation:1']['body_refs']
            self.add(f'P{pn:04d}:incoming-reference',start,title,'flow_annotation',
                     {'graphic_dependency':True,'reference_role':'incoming'})
            if pn==287:
                body=originals['P0287:annotation:7']['body_refs']
                self.add('P0287:continue:B4',body,title+contexts[2]+[yes[2]],'flow_annotation',
                         {'graphic_dependency':True,'reference_role':'continuation','target_unit':'P0289:question:B4',
                          'condition_role':'continuation_state','not_B3_entry_condition':True})
            else:
                # Former x<180/to-next-heading selection captured part of these
                # continuation ellipses in the last KNOWN INFO. Bound it exactly.
                body=self.rect(pn,[151,700,243,740])
                body=[r for r in body if r['text'] not in ('YES','NO')]
                self.add(f'P{pn:04d}:continuation',body,title+[yes[2]],'flow_annotation',
                         {'graphic_dependency':True,'reference_role':'continuation'})
            used={(r['record_id'],r['start'],r['end']) for row in self.rows for r in row['body_refs']+row['context_refs']}
            left=[r for r in all_refs[pn] if (r['record_id'],r['start'],r['end']) not in used
                  and r['text'] not in ('YES','NO','!','!!')]
            if left:
                self.add(f'P{pn:04d}:remaining-reference',left,title,'flow_annotation',
                         {'graphic_dependency':True},['FLOW_ANNOTATION_REVIEW'])
        # Used branch labels are now literal context, not excluded twice.
        used={(r['record_id'],r['start'],r['end']) for row in self.rows for r in row['body_refs']+row['context_refs']}
        self.dispositions=[d for d in self.dispositions if
                           (d['source']['record_id'],d['source']['start'],d['source']['end']) not in used]

    def reference_pages(self):
        titles={pn:page_titles(self.s,pn) for pn in (288,331,333,335)}
        self.add('P0288:model-note',self.rect(288,[131,122,332,270]),titles[288],
                 metadata={'linked_question':'P0287:question:B1','link_basis':'EXPLICIT_OPPOSITE_PAGE_NOTE'})
        self.add('P0288:wire-note',self.rect(288,[131,273,331,343]),titles[288])
        self.add('P0288:steice89',self.rect(288,[358,143,541,242]),titles[288])
        specs={331:([128,580,261,665],[128,666,261,712],[129,395,261,432]),
               333:([130,370,290,440],[130,443,291,487],[130,568,291,603]),
               335:([133,197,301,269],[133,273,301,308],None)}
        for pn,(warning,action,repair) in specs.items():
            self.add(f'P{pn:04d}:replacement',self.rect(pn,action),titles[pn]+self.rect(pn,warning),
                     metadata={'warning_scope':'PCB/distribution box harness disconnection and replacement'})
            if repair:self.add(f'P{pn:04d}:lead-repair',self.rect(pn,repair),titles[pn],metadata={'replacement_warning_inherited':False})
        for name,box in [('glowplug',[133,450,311,468]),('battery',[133,603,310,620])]:
            self.add('P0335:'+name,self.rect(335,box),titles[335],metadata={'replacement_warning_inherited':False})
        self.add('P0331:analyzer-note',self.rect(331,[120,142,259,273]),titles[331])
        # Same seven operating-state groups as printed here; do not import values
        # from the similar table on 329 or correct the source's anomalies.
        rows=read_jsonl(PACKAGE/'rules/v3/manual-table-units.jsonl')
        bands=[(141,173),(173,320),(320,425),(425,468),(468,513),(513,629),(629,679)]
        common=titles[331]+self.rect(331,[325,101,558,137])+self.rect(331,[120,142,259,273])
        for i,(lo,hi) in enumerate(bands,1):
            fields=[]
            for name,rect in [('IGNITION SWITCH POSITION',[265,lo,324,hi]),('DIAGNOSTIC CHECKS',[329,lo,558,hi])]:
                refs=self.rect(331,rect)
                fields.append({'name':name,'text':'\n'.join(r['text'] for r in refs),'refs':refs})
            rows.append({'key':f'P0331:ignition:row:{i}','fields':fields,'context_refs':common,
                         'metadata':{'table_id':'P0331:ignition','row':i,'expected_rows':7},
                         'review':'CODEX_PDF_LAYOUT_REVIEW','evidence':self.evidence(331)})
        write_jsonl(RULES/'manual-table-units.jsonl',rows)

    def retranscribed(self):
        regions=read_jsonl(RULES/'source-regions.jsonl')
        by_page=defaultdict(dict)
        for r in regions:by_page[r['pdf_page']][r['name']]=self.s.ref(r['record_id'],r['start'],r['end'])
        for pn,refs in by_page.items():
            steps={217:['M1','M2','M3'],262:['C5','C6','C7'],289:['B4','B5']}[pn]
            for step in steps:
                body=[refs[step+'-'+name] for name in ('question','options','reason') if step+'-'+name in refs]
                context=[refs['header'],refs[step+'-id']]+[refs[step+'-'+name] for name in ('known','possible') if step+'-'+name in refs]
                self.add(f'P{pn:04d}:question:{step}',body,context,'diagnostic_box',
                         {'step':step,'graphic_dependency':True,'condition_link_basis':'PDF_REVIEWED_EXPLICIT_BOX_RELATION',
                          'condition_roles':['KNOWN INFO','POSSIBLE PROBLEMS'],'reference_page_reviewed':False})
                for suffix,branch in [('exit','NO'),('continue','YES')]:
                    if step+'-'+suffix not in refs:continue
                    self.add(f'P{pn:04d}:branch:{step}:{branch}',[refs[step+'-'+suffix]],
                             context+[refs[step+'-question'],refs[step+'-'+branch.lower()]],'flow_annotation',
                             {'step':step,'graphic_dependency':True,'branch_label':branch,
                              'parent_question':f'P{pn:04d}:question:{step}','branch_relation':'PDF_REVIEWED_VISIBLE_EDGE',
                              'not_an_unconditional_action':True})
            self.add(f'P{pn:04d}:incoming-reference',[refs['start']],[refs['header']],'flow_annotation',
                     {'graphic_dependency':True,'reference_role':'incoming'})
            used={(r['record_id'],r['start'],r['end']) for row in self.rows for r in row['body_refs']+row['context_refs']}
            for name,ref in refs.items():
                if (ref['record_id'],ref['start'],ref['end']) in used:continue
                assert name.endswith('-yes'),name
                self.dispositions.append({'source':ref,'status':'EXCLUDED_NON_TEXT','reason':'LITERAL_FLOW_BRANCH_MARKER',
                                          'rule':'G02','evidence':self.evidence(pn)})

    def run(self):
        self.native();self.reference_pages();self.retranscribed()
        write_jsonl(RULES/'box-units.jsonl',self.rows)
        write_jsonl(RULES/'box-dispositions.jsonl',self.dispositions)
        write_json(RULES/'condition-resolutions.json',{'schema':1,'relations':self.log,
            'resolved_previous_condition_review_items':9,'graphic_dependency_preserved':True,
            'original_inputs_preserved':True,'evaluation_questions_read':False})
        print('v4 boxes',len(self.rows),'dispositions',len(self.dispositions))


if __name__=='__main__':Builder().run()
