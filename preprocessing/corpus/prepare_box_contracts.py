"""Freeze literal source regions and explicit context links, without rewriting text.

Native flowchart geometry is a bounded profile. A box is not associated with a
question when containment/anchor checks fail. Arrow paths are never paraphrased.
"""
from collections import defaultdict
import re
import pymupdf
from .common import SourceStore,ROOT,BASE,PACKAGE,read_json,write_json,write_jsonl,sha
from .structure import page_titles

OUT=PACKAGE/'rules/v3'
EVIDENCE=PACKAGE/'reports/rules-v3-work'


class Contracts:
    def __init__(self):
        self.s=SourceStore();self.units=[];self.dispositions=[];self.findings=[];self.profile=[]
        self.used=defaultdict(set)
        self.pdf=pymupdf.open(ROOT/self.s.config['source_pdf'])

    def lines(self,pn,layer='native'):
        rid=f'P{pn:04d}:{layer}'
        return [r for r in self.s.fragments(rid) if r['text'].strip()] if rid in self.s.records else []

    def rect(self,pn,x0,y0,x1,y1,layer='native'):
        return sorted([r for r in self.lines(pn,layer) if r['bbox'] and
                       x0<=r['bbox'][0]<x1 and y0<=r['bbox'][1]<y1],
                      key=lambda r:(round(r['bbox'][1],1),r['bbox'][0],r['start']))

    def exact(self,pn,text,layer='native',occurrence=0):
        rid=f'P{pn:04d}:{layer}';full=self.s.records[rid]['text']
        starts=[m.start() for m in re.finditer(re.escape(text),full)]
        a=starts[occurrence];return self.s.ref(rid,a,a+len(text))

    def evidence(self,pn):
        path=EVIDENCE/f'page-{pn:04d}.png'
        if not path.exists():self.pdf[pn-1].get_pixmap(dpi=110,alpha=False).save(path)
        return {'file':path.relative_to(ROOT).as_posix(),'sha256':sha(path)}

    def add(self,key,body,context=(),kind='reviewed_region',metadata=None,review_codes=()):
        if not body:return
        # Keep every exact source reference. Repeating a condition is explicit.
        seen=set();ctx=[]
        for r in context:
            t=(r['record_id'],r['start'],r['end'])
            if t not in seen:ctx.append(r);seen.add(t)
        pn=body[0]['pdf_page']
        for r in [*body,*ctx]:self.used[r['record_id']].add((r['start'],r['end']))
        self.units.append({'key':key,'kind':kind,'body_refs':body,'context_refs':ctx,
            'metadata':{'boundary':'recorded_pdf_region','cross_page_join':False,
                        'graphic_relations_inferred':False,**(metadata or {})},
            'review_codes':list(review_codes),'evidence':self.evidence(pn),
            'review':'CODEX_PDF_LAYOUT_REVIEW' if pn in (123,124,133,165,197,287,328,336,389,517,573,583,849)
                     else 'NATIVE_GEOMETRY_PROFILE_WITH_REMAINING_CONTEXT_REVIEW'})

    def mark(self,ref,reason):
        self.dispositions.append({'source':ref,'status':'EXCLUDED_NON_TEXT','reason':reason,'rule':'G02',
                                  'evidence':self.evidence(ref['pdf_page'])})
        self.used[ref['record_id']].add((ref['start'],ref['end']))

    def unmatched(self,pn):
        return [r for r in self.lines(pn) if (r['start'],r['end']) not in self.used[r['record_id']]]

    def source133(self):
        boxes=read_json(BASE/'corrections/batch-005/page-133-regions.json')
        refs={};pos=0;rid='P0133:ocr'
        for name,box,text in boxes:
            ref=self.s.ref(rid,pos,pos+len(text));assert ref['text']==text
            refs[name]=ref;pos+=len(text)+2
        for n in ('1','2','3'):
            self.add('P0133:question:'+n,[refs[n+'-question'],refs[n+'-options'],refs[n+'-reason']],
                     [refs['header'],refs[n+'-id'],refs[n+'-known'],refs[n+'-possible']],
                     'diagnostic_box',{'step':n,'condition_box':n+'-known','graphic_dependency':True,
                        'pdf_box':next(b for name,b,t in boxes if name==n+'-question'),
                        'pdf_regions':[{'role':name.split('-',1)[1],'bbox':b,
                                        'record_id':rid,'start':refs[name]['start'],'end':refs[name]['end']}
                                       for name,b,t in boxes if name in [n+'-id',n+'-known',n+'-possible',n+'-question',n+'-options',n+'-reason']],
                        'condition_link_basis':'PDF_VISUAL_SAME_NODE_BOXES'})
        for name in ('1-no','1-yes'):self.mark(refs[name],'LITERAL_FLOW_BRANCH_MARKER')
        for name in ('start','1-exit','3-exit'):
            self.add('P0133:'+name,[refs[name]],[refs['header']],kind='flow_annotation',
                     metadata={'graphic_dependency':True,'branch_relation':'PDF_ONLY'})

    def native_flows(self):
        # No OCR spans in this profile. The scanned/mixed layouts use separate
        # reviewed contracts or remain in the review queue.
        pages=[]
        for pn,p in self.s.pages.items():
            if not p['in_scope'] or f'P{pn:04d}:ocr' in self.s.records:continue
            text=self.s.records.get(f'P{pn:04d}:native',{}).get('text','')
            if 'KNOWN INFO' in text and 'TEST OPTIONS' in text:pages.append(pn)
        for pn in pages:
            refs=self.lines(pn);titles=page_titles(self.s,pn)
            titles += [r for r in refs if r['bbox'][1]<105 and r['bbox'][0]<110 and
                       r['text'].isupper() and len(r['text'])>8 and r not in titles]
            shapes=self.pdf[pn-1].get_drawings()
            questions=[]
            for shape in shapes:
                b=list(shape['rect'])
                if not ((shape['width'] or 0)>=2.5 and 165<=b[0]<230 and 100<b[2]-b[0]<245 and b[3]-b[1]>25):continue
                # Some paths include an incoming vertical connector. The white
                # rectangle drawn beneath the border supplies the actual box.
                fills=[list(x['rect']) for x in shapes if x['type']=='f' and
                       abs(x['rect'].x0-b[0])<3 and abs(x['rect'].x1-b[2])<3 and
                       abs(x['rect'].y1-b[3])<3 and b[1]<=x['rect'].y0<b[3]-20]
                if len(fills)==1:b=fills[0]
                if not any(sum(abs(x-y) for x,y in zip(b,q))<6 for q in questions):questions.append(b)
            questions.sort(key=lambda b:b[1])
            known=[r for r in refs if r['text'].strip()=='KNOWN INFO' and r['bbox'][0]<180]
            tests=[r for r in refs if r['text'].strip()=='TEST OPTIONS' and r['bbox'][0]>330]
            known.sort(key=lambda r:r['bbox'][1]);tests.sort(key=lambda r:r['bbox'][1])
            matched=set();attached=set();valid=0
            for i,b in enumerate(questions):
                identifiers=[r for r in refs if re.fullmatch(r'(?:[A-Z](?:\.\d+)?-?)?\d+(?:\.\d+)?',r['text'].strip()) and
                             b[0]-4<=r['bbox'][0]<b[0]+42 and -26<=r['bbox'][1]-b[1]<2]
                if len(identifiers)!=1:continue
                ident=identifiers[0];step=ident['text'].strip()
                body=[r for r in refs if b[0]-3<=r['bbox'][0] and r['bbox'][2]<=b[2]+4 and
                      b[1]-2<=(r['bbox'][1]+r['bbox'][3])/2<=b[3]+2 and r!=ident]
                if not body:continue
                body.sort(key=lambda r:(round(r['bbox'][1],1),r['bbox'][0],r['start']))
                candidates=[j for j,k in enumerate(known) if -45<=k['bbox'][1]-b[1]<=8]
                if pn==328 and step=='7':candidates=[0]  # Visually checked tall first left box.
                krefs=[]
                if len(candidates)==1 and candidates[0] not in attached:
                    j=candidates[0];lo=known[j]['bbox'][1]-1;hi=known[j+1]['bbox'][1]-1 if j+1<len(known) else 760
                    krefs=[r for r in refs if r['bbox'][0]<180 and lo<=r['bbox'][1]<hi]
                    attached.add(j)
                t=[j for j,r in enumerate(tests) if -45<=r['bbox'][1]-b[1]<=8]
                right=[]
                if len(t)==1:
                    j=t[0];lo=tests[j]['bbox'][1]-1;hi=tests[j+1]['bbox'][1]-1 if j+1<len(tests) else 760
                    right=[r for r in refs if r['bbox'][0]>=335 and lo<=r['bbox'][1]<hi and r not in body]
                    matched.add(j)
                # Explicit PDF review found vertically offset left boxes on 287.
                # The question and touching right box are clear; no left-box
                # association is invented merely from ordering or proximity.
                codes=[] if pn in (165,197,328,336,583) else ['BOX_CONTEXT_REVIEW']
                if pn==287:codes=['CONDITION_ASSOCIATION_UNRESOLVED']
                self.add(f'P{pn:04d}:question:{step}',body+sorted(right,key=lambda r:(r['bbox'][1],r['bbox'][0])),
                    titles+[ident]+sorted(krefs,key=lambda r:(r['bbox'][1],r['bbox'][0])),
                    'diagnostic_box',{'step':step,'pdf_box':b,'condition_link_basis':'BOUNDED_NATIVE_BOX_PROFILE' if krefs else 'NO_UNVERIFIED_CONDITION_LINK',
                        'graphic_dependency':True,'reference_page_reviewed':False},codes)
                valid+=1
            for j,k in enumerate(known):
                if j in attached:continue
                lo=k['bbox'][1]-1;hi=known[j+1]['bbox'][1]-1 if j+1<len(known) else 760
                body=[r for r in refs if r['bbox'][0]<180 and lo<=r['bbox'][1]<hi]
                self.add(f'P{pn:04d}:unlinked-condition:{j+1}',body,titles,'condition_box',
                    {'condition_link_basis':'PRESERVED_INDEPENDENTLY','graphic_dependency':True},['CONDITION_ASSOCIATION_UNRESOLVED'])
            remaining=self.unmatched(pn)
            groups=defaultdict(list)
            for r in remaining:
                if r['text'].strip() in ('YES','NO','Yes','No','!!','!'):
                    self.mark(r,'LITERAL_FLOW_BRANCH_OR_WARNING_SYMBOL');continue
                if r in titles:continue
                groups[tuple(r['source_blocks'])].append(r)
            for i,body in enumerate(groups.values()):
                self.add(f'P{pn:04d}:annotation:{i+1}',body,titles,'flow_annotation',
                    {'graphic_dependency':True,'branch_relation':'PDF_ONLY'},['FLOW_ANNOTATION_REVIEW'])
            self.profile.append({'pdf_page':pn,'question_rectangles':len(questions),'assigned_questions':valid,
                                 'known_boxes':len(known),'attached_known_boxes':len(attached),
                                 'test_boxes':len(tests),'attached_test_boxes':len(matched),
                                 'full_page_semantics_reviewed':False})

    def reference517(self):
        title=self.rect(517,0,90,600,120)
        # Full-width procedure text must not be forced into a two-column layout.
        ranges=[('fluid',120,301),('road',345,500),('fan',585,645)]
        for name,lo,hi in ranges:
            refs=self.rect(517,140,lo,590,hi)
            ctx=title+([self.exact(517,'Road Test Procedure','ocr')] if name=='road' else [])
            self.add('P0517:'+name,refs,ctx,metadata={'procedure':name,'graphic_dependency':False})

    def reference389(self):
        titles=page_titles(self.s,389)
        warning=self.rect(389,0,170,335,275)
        procedure=self.rect(389,0,278,335,315)
        self.add('P0389:pcb-replacement',procedure,titles+warning,
                 metadata={'warning_scope':'PCB/distribution box disconnection and replacement'})
        for name,lo,hi in [('steice91',150,276),('multimeter',310,460)]:
            body=self.rect(389,340,lo,550,hi)
            self.add('P0389:'+name,body,titles,metadata={'independent_test_box':True,'left_warning_inherited':False})

    def reference849(self):
        title=self.rect(849,0,160,600,185)
        description=self.rect(849,80,225,320,340)
        pre=self.rect(849,330,225,590,340)
        for name,rect in [('description',(80,225,320,340)),('pretest',(330,225,590,340)),
                          ('applications',(80,355,320,420)),('controls',(330,355,590,420)),
                          ('procedure',(80,480,320,640)),('errors',(330,480,590,640))]:
            body=self.rect(849,*rect)
            ctx=title+(description+pre if name=='procedure' else [])
            self.add('P0849:'+name,body,ctx,metadata={'test_number':'91','panel':name,
                       'preconditions_repeated':name=='procedure'})

    def procedure573(self):
        title=page_titles(self.s,573)
        refs=self.lines(573)
        warning=self.rect(573,0,473,590,506)
        note=self.rect(573,0,685,590,739)
        temperatures=self.rect(573,80,277,280,308)
        anchors=[r for r in refs if re.match(r'^(?:[89]|1\d|2\d)\.',r['text']) and r['bbox'][0]<100]
        anchors.sort(key=lambda r:r['bbox'][1])
        assert len(anchors)==22
        for i,a in enumerate(anchors):
            step=int(a['text'].split('.')[0]);lo=a['bbox'][1]-.5
            hi=anchors[i+1]['bbox'][1]-.5 if i+1<len(anchors) else 682
            body=[r for r in refs if lo<=r['bbox'][1]<hi and r not in warning and
                  not (180<r['bbox'][1]<408 and r['bbox'][0]>=280) and
                  not (330<r['bbox'][1]<376)]
            # Step 18 values are represented by the separate engine/RPM table.
            ctx=title+note+warning+(temperatures if step>=18 else [])
            self.add(f'P0573:step:{step}',body,ctx,kind='procedure_step',metadata={
                'step':str(step),'procedure':'power steering analyzer test',
                'warning_scope':'same analyzer test; never neighbouring drawing labels',
                'condition_scope':'cooling-system note applies to this test',
                'continues_from_previous_page':True,'prior_setup_not_reconstructed':True})
        labels=[r for r in refs if 180<r['bbox'][1]<408 and r['bbox'][0]>=280]
        for i,r in enumerate(labels):self.add(f'P0573:figure-label:{i+1}',[r],title,'figure_label',{'graphic_dependency':True})

    def intro124(self):
        title=page_titles(self.s,124)
        # Split the one native line containing two columns at a checked literal
        # offset. No geometric character position is fabricated.
        left=self.exact(124,'THERE ARE 21 SYSTEM LEVEL TESTS.')
        right=self.exact(124,'THESE ARE USED BY THE TOP')
        for name,body,ctx in [
            ('top',self.rect(124,270,112,520,140),self.rect(124,0,112,260,140)),
            ('system',[right]+self.rect(124,270,162,520,200),[left]),
            ('pages',self.rect(124,270,210,520,290),self.rect(124,0,210,260,290))]:
            self.add('P0124:explanation:'+name,body,title+ctx)

    def run(self):
        self.source133();self.native_flows();self.reference517();self.reference389()
        self.reference849();self.procedure573();self.intro124()
        write_jsonl(OUT/'box-units.jsonl',self.units)
        write_jsonl(OUT/'box-dispositions.jsonl',self.dispositions)
        write_json(OUT/'native-box-profile.json',{'pages':self.profile,'individual_visual_check_pages':[165,197,287,328,336,583],
            'other_pages':'Mechanical geometry checks; source context review remains pending.',
            'rejected_association_page':287,'unmatched_left_boxes_are_not_guessed':True})
        print('Box units:',len(self.units),'dispositions:',len(self.dispositions),'native pages:',len(self.profile))


if __name__=='__main__':Contracts().run()
