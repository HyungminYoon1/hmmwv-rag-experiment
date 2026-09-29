"""Replay explicit PDF-reviewed layout definitions into literal source sidecars.

This prepares rules, not corpus text corrections. All cell content remains a
slice of the immutable v4 records. The generated sidecar is separately locked.
"""
from __future__ import annotations
from pathlib import Path
import re
from .common import SourceStore,PACKAGE,write_jsonl,write_json,sha,read_json

OUT=PACKAGE/read_json(PACKAGE/'config.json').get('rules_path','rules/v2')


class Tables:
    def __init__(self):
        self.store=SourceStore();self.units=[];self.dispositions=[]

    def lines(self,pn,layer='native'):
        rid=f'P{pn:04d}:{layer}'
        return [r for r in self.store.fragments(rid) if r['text'].strip()]

    def rect(self,pn,x0,y0,x1,y1,layer='native'):
        return sorted([r for r in self.lines(pn,layer) if r['bbox'] and
                       x0<=r['bbox'][0]<x1 and y0<=r['bbox'][1]<y1],
                      key=lambda r:(round(r['bbox'][1],1),r['bbox'][0],r['start']))

    def add(self,key,fields,context=(),metadata=None):
        seen=set();context=[r for r in context if not ((r['record_id'],r['start'],r['end']) in seen or seen.add((r['record_id'],r['start'],r['end'])))]
        self.units.append({'key':key,'fields':[{'name':name,'refs':refs,'text':'\n'.join(r['text'] for r in refs)} for name,refs in fields],
                           'context_refs':context,'metadata':metadata or {},
                           'review':'CODEX_PDF_LAYOUT_REVIEW','rules':['T01','T02','T03','T04','T05','T07','T08']})

    def grid(self,pn,key,ys,yend,xs,names,context=(),extra=None):
        extra=extra or {}
        for i,y in enumerate(ys):
            end=ys[i+1]-3 if i+1<len(ys) else yend
            fields=[(name,self.rect(pn,xs[j],y-3,xs[j+1],end)) for j,name in enumerate(names)]
            self.add(f'{key}:row:{i+1}',fields,[*context,*extra.get(i,[])],{'table_id':key,'row':i+1,'expected_rows':len(ys)})

    def exact(self,pn,text,layer='native',occurrence=0):
        rid=f'P{pn:04d}:{layer}';full=self.store.records[rid]['text'];starts=[m.start() for m in re.finditer(re.escape(text),full)]
        if len(starts)<=occurrence:raise ValueError((rid,text,occurrence))
        return self.store.ref(rid,starts[occurrence],starts[occurrence]+len(text))

    def mark(self,ref,reason,status='LAYOUT_ONLY'):
        self.dispositions.append({'source':ref,'status':status,'reason':reason,'rule':'T01','review':'CODEX_PDF_LAYOUT_REVIEW'})

    def matrix(self):
        # Sixteen grid columns. M1123 is a wrapped second line in the final
        # M1097 group, not a seventeenth column. Grid boundaries were inspected.
        models=['M966, M966A1, M1121','M996, M996A1','M997, M997A1, M997A2','M998, M998A1',
                'M1025, M1025A1, M1025A2','M1026, M1026A1','M1035, M1035A1, M1035A2',
                'M1036','M1037','M1038, M1038A1','M1042','M1043, M1043A1, M1043A2',
                'M1044, M1044A1','M1045, M1045A1, M1045A2','M1046, M1046A1',
                'M1097, M1097A1, M1097A2,','M1123']
        headers=[[self.exact(60,m,'ocr')] for m in models[:-1]]
        headers[-1].append(self.exact(60,models[-1],'ocr'))
        xs=[226.25,244.25,262.25,281.25,300.75,319.75,339.25,355.75,374.75,395.25,412.75,433.25,452.25,471.25,490.25,509.25,539.5]
        ys=[290.1,319.4,348.6,368.1,416.9,436.1,455.6,484.9,514.1,543.6,582.9,621.6,641.1,660.4,679.9,699.1,719]
        names=self.rect(60,100,285,228,750)
        marks=[r for r in self.rect(60,228,285,545,750) if r['text']=='x']
        for i,y in enumerate(ys):
            end=ys[i+1]-3 if i+1<len(ys) else 750
            rowname=[r for r in names if y-3<=r['bbox'][1]<end and r['text'] not in ('Ambulance:','Communications:')]
            context=self.rect(60,0,70,600,140)
            if 4<=i<=9:context+=[self.exact(60,'Ambulance:')]
            if i in (11,12):context+=[self.exact(60,'Communications:')]
            rowmarks=[r for r in marks if abs(r['bbox'][1]-y)<3]
            assigned={}
            for r in rowmarks:
                x=(r['bbox'][0]+r['bbox'][2])/2
                matches=[j for j in range(16) if xs[j]<=x<xs[j+1]]
                assert len(matches)==1
                j=matches[0]
                assert j not in assigned
                assigned[j]=r
            # Empty cells remain empty; only positive printed marks enter text.
            for j,header in enumerate(headers):
                fields=[('Equipment/Function',rowname),('Model',header),('Mark',[assigned[j]] if j in assigned else [])]
                self.add(f'P0060:matrix:r{i+1}:c{j+1}',fields,context,
                         {'table_id':'P0060:model-matrix','row':i+1,'column':j+1,'expected_columns':16,
                          'cell_state':'PRINTED_X' if j in assigned else 'BLANK_NOT_NEGATION'})

    def abbreviations(self):
        ctx=self.rect(61,0,185,600,222)
        for side,(x0,x1) in enumerate([(50,300),(320,550)]):
            lines=self.rect(61,x0,222,x1,379)
            keys=[r for r in lines if re.search(r'(?:\.[ \t]*){2,}',r['text'])]
            for i,key in enumerate(keys):
                m=re.search(r'(?:\.[ \t]*){2,}',key['text'])
                left=self.store.ref(key['record_id'],key['start'],key['start']+m.start())
                right=[]
                if m.end()<len(key['text']):right.append(self.store.ref(key['record_id'],key['start']+m.end(),key['end']))
                right.extend(r for r in lines if r!=key and abs(r['bbox'][3]-key['bbox'][3])<2)
                assert right,(side,key['text'])
                self.mark(self.store.ref(key['record_id'],key['start']+m.start(),key['start']+m.end()),'DOTTED_TABLE_LEADER')
                self.add(f'P0061:abbreviations:{side}:{i+1}',[('MEASUREMENT',[left]),('ABBREVIATION',right)],ctx,
                         {'table_id':'P0061:abbreviations','side':side,'row':i+1})

    def lubrication(self):
        names=['USAGE','FLUID/LUBRICANT','CAPACITIES','EXPECTED TEMPERATURE']
        title120=self.rect(120,0,370,600,414)
        oil_notes=self.rect(120,0,700,600,730)
        chassis_notes=self.rect(120,0,730,600,753)
        def row(key,refs,ctx,meta=None):self.add(key,list(zip(names,refs)),ctx,meta)
        usage=self.rect(120,50,415,155,478);cap=self.rect(120,270,415,423,478)
        for i,y in enumerate([416.5,428.5,440.5]):
            row(f'P0120:oil:{i+1}',[usage,self.rect(120,155,y-1,270,y+1),cap,self.rect(120,423,y-1,600,y+1)],title120+oil_notes,
                {'table_id':'P0120:lubrication','group':'engine-oil','row':i+1,'shared_capacity':True})
        usage=self.rect(120,50,480,155,580);cap=self.rect(120,270,480,423,580)
        general=self.rect(120,155,480,270,503)
        for i,(a,b,y) in enumerate([(506,529,505.5),(530,553,529.5),(554,580,553.5)]):
            row(f'P0120:coolant:{i+1}',[usage,general+self.rect(120,155,a,270,b),cap,self.rect(120,423,y-1,600,y+1)],title120,
                {'table_id':'P0120:lubrication','group':'coolant','row':i+1,'shared_capacity':True})
        fluid=self.rect(120,155,580,270,635);temp=self.rect(120,423,580,600,690)
        for i,(a,b) in enumerate([(580,632),(640,690)]):
            usage=self.rect(120,50,a,155,b)
            if i:usage=[self.exact(120,'Brake System')]+usage
            row(f'P0120:brake:{i+1}',[usage,fluid,self.rect(120,270,a,423,b),temp],title120,
                {'table_id':'P0120:lubrication','group':'brake','row':i+1,'shared_fluid_temperature':True})
        title121=self.rect(121,0,70,600,112)
        usage=self.exact(121,'Transmission')
        temp=self.rect(121,422,113,600,141)
        for i,(a,b) in enumerate([(111,136),(136,164)]):
            uses=[usage]+self.rect(121,60,a,139,b)
            # Superscript trademark raises the bbox; preserve printed order.
            fluid=self.rect(121,140,a,267,b)
            if i:fluid=sorted(fluid,key=lambda r:r['start'])
            row(f'P0121:transmission:{i+1}',[uses,fluid,self.rect(121,268,a,420,b),temp],title121,
                {'table_id':'P0120:lubrication','group':'transmission','row':i+1,'shared_temperature':True})
        row('P0121:transmission:arctic',[[usage],self.rect(121,140,165,267,180),[],self.rect(121,422,165,600,180)],title121,
            {'table_id':'P0120:lubrication','group':'transmission','capacity':'BLANK_NOT_INFERRED'})
        fluid=self.rect(121,140,181,267,211);temp=self.rect(121,422,181,600,211)
        for i,(a,b) in enumerate([(183,195),(195,211)]):
            uses=self.rect(121,50,a,139,b)
            if i:uses=[self.exact(121,'Transfer')]+uses
            else:uses+=[self.exact(121,'Case')]
            row(f'P0121:transfer:{i+1}',[uses,fluid,self.rect(121,268,a,420,b),temp],title121,
                {'table_id':'P0120:lubrication','group':'transfer-case','row':i+1,'shared_fluid_temperature':True})
        for i,(a,b) in enumerate([(211,239),(240,268),(269,297),(298,361),(362,397)]):
            refs=[self.rect(121,x0,a,x1,b) for x0,x1 in [(50,140),(140,267),(268,422),(422,600)]]
            row(f'P0121:lubrication:{i+1}',refs,title121+(chassis_notes if i>=3 else []),{'table_id':'P0120:lubrication','group':'other','row':i+1})

    def standard_specs(self,pn):
        lines=self.lines(pn)
        top=350 if pn==61 else 95 if pn==62 else 95 if pn==63 else 80
        if pn==61:top=385
        candidates=sorted([r for r in lines if r['bbox'][1]>=top],key=lambda r:(round(r['bbox'][1],1),r['bbox'][0]))
        anchors=[r for r in candidates if r['bbox'][0]<90 and re.match(r'^\d{1,2}(?:\.\d+)?\.(?:\s|[A-Z]|$)',r['text'])]
        title=[r for r in self.rect(pn,0,55,600,95) if r['text'].startswith('Table 1-2.')]
        if pn==61:title=self.rect(pn,0,129,600,144)
        standards=[self.exact(61,'STANDARD'),self.exact(61,'METRIC')]
        note=self.rect(61,0,695,600,723)
        for gi,start in enumerate(anchors):
            end=anchors[gi+1]['bbox'][1]-1 if gi+1<len(anchors) else 750 if pn!=61 else 695
            rows=[r for r in candidates if start['bbox'][1]-1<=r['bbox'][1]<end]
            heads=[r for r in rows if abs(r['bbox'][1]-start['bbox'][1])<2]
            data=[r for r in rows if r not in heads]
            # Dotted leaders determine field/value boundaries even when one PDF
            # line contains both. Coordinates select the metric column.
            yvalues=sorted({round(r['bbox'][3],1) for r in data if re.search(r'(?:\.[ \t]*){2,}',r['text'])})
            rowsets=[]
            for y in yvalues:
                group=[r for r in data if abs(r['bbox'][3]-y)<2]
                rowsets.append((y,group))
            parent=[];buffer=[];model=[];used=set()
            for ri,(y,group) in enumerate(rowsets):
                prev=rowsets[ri-1][0]+2 if ri else start['bbox'][1]+2
                between=[r for r in data if prev<r['bbox'][3]<y-2 and (r['start'],r['end']) not in used]
                # Property continuation lines immediately after the preceding
                # row belong there, not to the next property (handled below).
                for r in between:
                    if r['text'].rstrip().endswith(':') or r['text'].strip() in ('Engine','Oil Pressure','Gear Ratios','Fuel Filter'):
                        parent=[r];buffer=[]
                    elif r['bbox'][0]<180:buffer.append(r)
                prop=[];standard=[];metric=[]
                for r in group:
                    used.add((r['start'],r['end']))
                    m=re.search(r'(?:\.[ \t]*){2,}',r['text'])
                    if m:
                        if m.start():prop.append(self.store.ref(r['record_id'],r['start'],r['start']+m.start()))
                        self.mark(self.store.ref(r['record_id'],r['start']+m.start(),r['start']+m.end()),'DOTTED_TABLE_LEADER')
                        if m.end()<len(r['text']):standard.append(self.store.ref(r['record_id'],r['start']+m.end(),r['end']))
                    elif r['bbox'][0]>=445:metric.append(r)
                    else:standard.append(r)
                nexty=rowsets[ri+1][0]-2 if ri+1<len(rowsets) else end
                tails=[r for r in data if y+2<r['bbox'][3]<nexty and r['bbox'][0]>=180 and (r['start'],r['end']) not in used]
                for r in tails:
                    (metric if r['bbox'][0]>=445 else standard).append(r);used.add((r['start'],r['end']))
                propname=''.join(r['text'] for r in prop).strip()
                if pn==61 and parent and not propname.startswith(('Crankcase','Drain','W/Dry')):parent=[]
                if pn==63 and parent and 'Gear Ratios' in parent[0]['text'] and propname not in ('First','Second','Third','Fourth','Reverse'):parent=[]
                if propname.startswith('Model') and any(x in ' '.join(r['text'] for r in heads) for x in ('ENGINE','TRANSMISSION','TRANSFER CASE','WINCH')):model=standard[:]
                ctx=title+heads+standards+parent+([] if ri==0 else model)+(note if pn==61 and gi==1 else [])
                self.add(f'P{pn:04d}:spec:{gi+1}:{ri+1}',[('ITEM',buffer+prop),('STANDARD',standard),('METRIC',metric)],ctx,
                         {'table_id':'P0061:tabulated-data','section':gi+1,'row':ri+1})
                buffer=[]

    def run(self):
        # Parts lists: source row anchors, fixed printed column boundaries.
        names=['ITEM NO.','PART NUMBER','NSN','NOMENCLATURE','QTY']
        for pn,low,high,key,xs,count in [
            (119,145,337,'P0119:semiannual',[54,96,218,350,506,556],11),
            (119,425,632,'P0119:annual',[54,96,218,350,506,556],12),
            (120,123,367,'P0120:biennial',[54,96,184,301,507,557],16)]:
            ys=[r['bbox'][1] for r in self.rect(pn,54,low,96,high) if re.fullmatch(r'\d+\.',r['text'])]
            assert len(ys)==count,(key,ys)
            ctx=self.rect(pn,0,350 if key.endswith(':annual') else 65,600,low)
            self.grid(pn,key,ys,high,xs,names,ctx)
        # Pump replacement conditions are actual surrounding source paragraphs.
        self.grid(196,'P0196:pump',[626.8,652.8,678.8,704.8],731,[123,241,347,437,563],
                  ['Model Pump P/N (NSN)','Serial Number Break','Original P/N','New P/N (NSN)'],
                  self.rect(196,0,480,600,625))
        self.grid(277,'P0277:alternator',[452.3,484,515.7],553,[141,278,432],
                  ['Dual Voltage Alternator','Single Voltage System'],
                  self.rect(277,0,85,600,100)+self.rect(277,0,256,600,310)+self.rect(277,0,408,600,451))
        # State readouts: two independent tables on the same page.
        for lo,hi,key,n in [(107,236,'P0855:prompting',5),(325,668,'P0855:error',14)]:
            anchors=self.rect(855,0,lo,110,hi);assert len(anchors)==n
            context=self.rect(855,0,70 if lo==107 else 290,600,lo)
            self.grid(855,key,[r['bbox'][1] for r in anchors],hi,[0,110,600],['VTM Readout','Interpretation'],context)
        # Pin table states: both use Ignition ON; engine state differs.
        names=['CKT NOM.','CKT #','PIN','TO PIN','EXP READ'];xs=[54,145,205,260,326,425]
        for ys,end,key,head in [([314.2,344.8,375.2,405.8,436],455,'P0532:engine-off',(249,305)),
                                ([560.2,601.2,631.2,661.2],681,'P0532:engine-on',(489,555))]:
            ctx=self.rect(532,0,75,600,106)+self.rect(532,0,118,425,242)+self.rect(532,0,head[0],425,head[1])
            extra={2:self.rect(532,0,456,425,475)} if key.endswith('off') else {}
            self.grid(532,key,ys,end,xs,names,ctx,extra)
        # Preserve the diagram arrows as metadata; table measurements stay text.
        for r in self.rect(532,425,305,600,690):
            if r['text'].strip()=='No':self.mark(r,'J1_FLOW_BRANCH_LABEL','EXCLUDED_NON_TEXT')
        # The following page is a distinct resistance table, with Ignition OFF.
        # Two-line circuit numbers stay in the same cell; case is significant.
        self.grid(533,'P0533:ignition-off',
                  [280.5,310.25,339.75,369.5,399.25,440,480.75,510.5,540.25,570,610.75],
                  640,[54,145,205,260,300,430],names,
                  self.rect(533,0,75,600,106)+self.rect(533,0,118,430,151)+self.rect(533,0,210,430,272))
        for r in self.rect(533,430,270,600,640):
            if r['text'].strip()=='No':self.mark(r,'J1_FLOW_BRANCH_LABEL','EXCLUDED_NON_TEXT')
        # Seven explicitly printed ignition state groups, not a continuous list.
        self.grid(329,'P0329:ignition',[151.9,182.3,328.8,434,478,520.2,637.7],714,[267,327,565],
                  ['IGNITION SWITCH POSITION','DIAGNOSTIC CHECKS'],
                  self.rect(329,0,80,600,139)+self.rect(329,0,140,266,273))
        # Image text above the alternator drawing: preserve sign and terminal.
        for i,line in enumerate(['#6 to V - BATTERY','#7 to P + BATTERY','#8 to Y - FIELD COIL','#10 to W + FIELD COIL','#11 to Z SENSOR (AC)']):
            ref=self.exact(300,line,'ocr');match=re.fullmatch(r'(#[0-9]+) to ([A-Z]) (.*)',line)
            fields=[]
            for j,label in [(1,'WIRE NO.'),(2,'TERM. LTR.'),(3,'FUNCTION')]:
                a,b=match.span(j);fields.append((label,[self.store.ref(ref['record_id'],ref['start']+a,ref['start']+b)]))
            self.add(f'P0300:wire:row:{i+1}',fields,self.rect(300,0,65,600,110)+[self.exact(300,'WIRE TERM. FUNCTION\nNO. LTR.','ocr')],
                     {'table_id':'P0300:wire','row':i+1,'expected_rows':5,'refines_old_rule':'ALIGN-00370'})
            a,b=match.span(2);self.mark(self.store.ref(ref['record_id'],ref['start']+match.end(1),ref['start']+a),'PRINTED_TABLE_RELATION_SEPARATOR')
        for pn in [61,62,63,64]:self.standard_specs(pn)
        self.matrix();self.abbreviations();self.lubrication()
        self.additional_tables()
        OUT.mkdir(parents=True,exist_ok=True)
        write_jsonl(OUT/'manual-table-units.jsonl',self.units)
        write_jsonl(OUT/'manual-dispositions.jsonl',self.dispositions)
        write_json(OUT/'table-preparation.json',{'units':len(self.units),'dispositions':len(self.dispositions),
                   'pdf_visual_review_pages':[60,61,62,63,64,98,119,120,121,123,124,196,277,300,329,532,533,573,855],
                   'remaining_layout_definitions':[],'source_records_modified':False,
                   'layout_findings':['PDF 60 has 16 grid columns; M1123 is the second line of the final M1097 group.']})
        print(len(self.units),'table units prepared')

    def additional_tables(self):
        # The paragraph/foldout columns belong to 22 physical rows, including
        # two wrapped labels. Blank foldout cells remain blank.
        ys=[370.522,381.082,391.642,402.202,412.762,423.322,433.882,455.002,
            465.562,476.122,497.242,507.802,518.362,528.922,539.482,550.042,
            560.602,571.162,581.722,592.282,602.842,613.402]
        self.grid(123,'P0123:foldouts',ys,633,[75,251,347,445],
                  ['SYSTEM LEVEL TESTS','PARAGRAPH','FOLDOUT NUMBER'],
                  self.rect(123,0,70,600,245))
        tops=[('ENGINE STARTING','2-41'),('ENGINE RUNNING','2-47'),('COOLING','2-57'),
              ('LUBRICATION','2-65'),('ELECTRICAL','2-71')]
        systems=[('FUEL','2-95'),('AIR INTAKE/EXHAUST','2-137'),('COMPRESSION/MECHANICAL','2-143'),
            ('ENGINE COOLING','2-155'),('ENGINE LUBRICATION','2-187'),('ALTERNATOR','2-194'),
            ('PROTECTIVE CONTROL BOX/\n2-227\nDISTRIBUTION BOX','2-227'),
            ('BATTERY CIRCUIT','2-251'),('STARTER CIRCUIT','2-261'),('GLOWPLUGS (PCB)','2-303'),
            ('GLOWPLUGS (DISTRIBUTION BOX)','2-318.1'),('INSTRUMENTS','2-319'),('LIGHTS','2-389'),
            ('TRANSMISSION (3L80)','2-399'),('TRANSMISSION (4L80-E)','2-11'),('BRAKES','2-445'),
            ('STEERING','2-459'),('DRIVETRAIN','2-79'),('AMBULANCE ELECTRICAL','2-497'),
            ('AMBULANCE MECHANICAL','2-693'),('WINCH','2-715'),('DCA TROUBLESHOOTING','2-723')]
        for group,rows,header in [('top',tops,'TOP LEVEL TESTS'),('system',systems,'SYSTEM LEVEL TESTS')]:
            for i,(name,value) in enumerate(rows,1):
                refs=[self.exact(124,name)] if not name.startswith('PROTECTIVE CONTROL') else [
                    self.exact(124,'PROTECTIVE CONTROL BOX/'),self.exact(124,'DISTRIBUTION BOX')]
                self.add(f'P0124:{group}:row:{i}',[(header,refs),('PAGE',[self.exact(124,value)])],
                    [self.exact(124,'2-14. HOW TO USE THIS TROUBLESHOOTING GUIDE (Cont’d)'),self.exact(124,header,occurrence=1)],
                    {'table_id':f'P0124:{group}','row':i,'expected_rows':len(rows),
                     'source_anomalies':['PRINTED_PAGE_REFERENCE_PRESERVED'] if value in ('2-11','2-79') else []})
        ctx=self.rect(573,0,65,600,90)+self.rect(573,80,277,280,330)+self.rect(573,0,685,600,739)
        for i,(model,rpm) in enumerate([('6.2L engine','650±25 RPM'),('6.5L engine','700±25 RPM'),('6.5L detuned','700±25 RPM')],1):
            refs=[self.exact(573,model)]
            if i==3:
                refs.append(self.exact(573,'engine\n700±25 RPM'))
                r=refs.pop();refs.append(self.store.ref(r['record_id'],r['start'],r['start']+6))
            value=self.exact(573,rpm,occurrence=1 if i==3 else 0)
            self.add(f'P0573:idle:row:{i}',[('Engine',refs),('Idle speed',[value])],ctx,
                     {'table_id':'P0573:idle','row':i,'expected_rows':3,'procedure_step':'18'})


if __name__=='__main__':Tables().run()
