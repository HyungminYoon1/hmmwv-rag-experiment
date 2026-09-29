"""Freeze literal figure exclusions, corrected line bounds and plate table cells."""
from collections import defaultdict
import re
from .common import *


def main():
    s=SourceStore(check=False);rules=PACKAGE/'rules/v6'
    if (rules/'text-scope-review.json').exists():raise ValueError('Already applied')
    rows=s.table('box-units.jsonl')
    for r in rows:
        if r['kind']=='reviewed_text_box':r['body_separator']=' '
    # Per-line bounds for the new mixed-line repairs. The y coordinates are
    # inherited from the inspected line; x partitions follow the printed panel.
    regions=s.table('source-regions.jsonl')
    bynum={d['number']:d for d in s.table('alignment-review.jsonl')}
    partitions={35:[(42,155),(360,515)],36:[(42,157),(170,365),(365,515)],
      63:[(30,165),(210,330)],158:[(30,170),(230,340)],159:[(130,350),(365,440)],
      162:[(25,180),(205,350)],165:[(25,200),(205,350)],166:[(25,165),(200,350)],
      167:[(25,185),(205,355)],170:[(25,180),(205,350)],
      184:[(25,190),(220,340)],191:[(25,190),(220,340)],
      194:[(25,165),(215,340)],198:[(25,190),(215,340)],199:[(25,190),(215,340)]}
    for num,d in bynum.items():
        if d['action']!='CORRECT':continue
        ref=d['source_refs'][0];text=s.records[ref['record_id']]['text'][ref['start']:ref['end']]
        assert text==d['after'],(num,text,d['after'])
        offsets=[];pos=ref['start']
        for line in text.splitlines(True):offsets.append((pos,pos+len(line.rstrip('\n')),line.rstrip('\n')));pos+=len(line)
        for i,(a,b,value) in enumerate(offsets):
            box=list(ref['bbox'])
            if num in partitions:box[0],box[2]=partitions[num][i]
            if num==86:box=[150,157+i*10,350,177+i*10]
            if num==205:box=[132,227+i*10,342,250+i*10]
            regions.append({'record_id':ref['record_id'],'pdf_page':ref['pdf_page'],'start':a,'end':b,
                'text':value,'bbox':box,'name':f'V6-A{num:03d}-line{i}',
                'review':'CODEX_PDF_LAYOUT_REVIEW',
                'evidence':{'file':d['image'],'sha256':d['image_sha256']}})
    write_jsonl(rules/'source-regions.jsonl',regions)
    s=SourceStore(check=False)
    # Convert the data plate's matrices to rows with explicit field association.
    plate=next(r for r in rows if r['key']=='P0054-B003:reviewed')
    refs=[s.exact(r) for r in plate['body_refs']];flat=' '.join(r['text'] for r in refs)
    positions=[];pos=0
    for r in refs:positions.append((pos,pos+len(r['text']),r));pos+=len(r['text'])+1
    def literal(value,start=0):
        a=flat.index(value,start);b=a+len(value);result=[]
        for x,y,r in positions:
            if max(a,x)<min(b,y):result.append(s.ref(r['record_id'],r['start']+max(a,x)-x,r['start']+min(b,y)-x))
        return result
    tables=s.table('manual-table-units.jsonl');dispositions=s.table('manual-dispositions.jsonl')
    def add(key,fields,context):
        f=[{'name':name,'refs':rs,'text':'\n'.join(r['text'] for r in rs)} for name,rs in fields]
        tables.append({'key':'P0054:plate:'+key,'fields':f,'context_refs':context,
          'review':'CODEX_PDF_LAYOUT_REVIEW','metadata':{'table_id':'P0054:servicing-plate',
            'cell_occupancy_checked_against_pdf':True,'blank_cells_invented':False,
            'source_check':'CODEX_PDF_VISUAL_CHECK','evidence':plate['evidence']}})
    context=literal('SERVICING DATA')
    for key,value in [('FUEL','DIESEL NO. 1. NO. 2, DFA'),('FUEL TANK CAPACITY','25 GALS'),('COOLING SYSTEM CAPACITY','25 QTS'),('CRANKCASE CAPACITY','7 QTS + 1 QT FOR FILTER')]:
        add(key,[('ITEM',literal(key)),('VALUE',literal(value))],context)
    title=literal('TIRE INFLATION PRESSURE')+literal('FRONT P.S.I. REAR P.S.I.')
    for i,line in enumerate(['ALL MODELS EXCEPT M996, M997, M1037, AND M1042 20 22','M996, M997, M1037, M1042 22 30']):
        a=flat.index(line);model,front,rear=line.rsplit(' ',2)
        add('tire'+str(i),[('MODELS',literal(model,a)),('FRONT P.S.I.',literal(front,a+len(model))),('REAR P.S.I.',literal(rear,a+len(model)+len(front)+1))],title)
    base=flat.index('TEMPERATURE');temp=['ABOVE +15°F','+40° TO -15°F','+40° TO -65°F']
    values={'ENGINE OIL':['OE-30','OE-10','OEA'],'GEAR OIL':['GO 80/90','GO 80/90','GO 75'],'GREASE':['GAA','GAA','GAA']}
    for i,t in enumerate(temp):
        fields=[('TEMPERATURE',literal(t,base))]
        for name,vs in values.items():
            a=flat.index(name,base)+len(name)
            for v in vs[:i]:a=flat.index(v,a)+len(v)
            fields.append((name,literal(vs[i],a)))
        add('temperature'+str(i),fields,literal('TEMPERATURE',base))
    drain=literal('TO DRAIN COOLING SYSTEM OPEN DRAINCOCK LOCATED AT LOWER RADIATOR TUBE')
    rows=[r for r in rows if r is not plate]
    rows.append({**plate,'key':'P0054:drain-instruction','body_refs':drain,
                 'metadata':{'boundary':'individually_reviewed_pdf_box','graphic_relations_inferred':False}})
    for r in refs:dispositions.append({'source':r,'status':'LAYOUT_ONLY','reason':'PRINTED_PLATE_TABLE_HEADERS_AND_DELIMITERS','rule':'V6-PLATE54'})
    write_jsonl(rules/'manual-table-units.jsonl',tables)
    write_jsonl(rules/'manual-dispositions.jsonl',dispositions)
    write_jsonl(rules/'box-units.jsonl',rows)
    # Actual inspected figure regions. Diagram geometry remains in the PDF.
    # Box/table claims have priority, so independent instructions are preserved.
    bounds={125:[(130,217,530,478),(115,575,530,585)],155:[(310,300,530,480)],
      306:[(320,110,535,435)],613:[(195,440,540,660)],743:[(285,375,575,735)],
      476:[(150,180,350,410),(150,420,540,730)],222:[(140,115,550,730)]}
    from .structure import Units,reviewed_tables,manual_tables
    from .boxes import reviewed_boxes
    s=SourceStore(check=False);u=Units(s);reviewed_tables(s,u);manual_tables(s,u);reviewed_boxes(s,u)
    exclusions=s.table('box-dispositions.jsonl');proofs=[]
    for pn,boxes in bounds.items():
        image=PACKAGE/f'reports/rules-v6-work/profile-images/p{pn:04d}.png'
        if not image.exists():
            import pymupdf
            with pymupdf.open(ROOT/s.config['source_pdf']) as pdf:pdf[pn-1].get_pixmap(dpi=144).save(image)
        for layer in ('native','ocr'):
            rid=f'P{pn:04d}:{layer}'
            if rid not in s.records:continue
            for ref in s.fragments(rid):
                if not ref['text'].strip() or s.claimed(ref) or not ref['bbox']:continue
                b=ref['bbox'];cx=(b[0]+b[2])/2;cy=(b[1]+b[3])/2
                if not any(x0<=cx<=x1 and y0<=cy<=y1 and b[0]>=x0-3 and b[2]<=x1+3 for x0,y0,x1,y1 in boxes):continue
                # 125 includes real exterior callouts. Only the inset OCR and
                # brace marks are excluded; native exterior prose stays intact.
                if pn==125 and layer=='native':continue
                exclusions.append({'source':ref,'status':'EXCLUDED_NON_TEXT','reason':'PDF_CONFIRMED_FIGURE_REGION_TEXT_SCOPE_EXCLUSION','rule':'V6-FIGURE-'+str(pn)})
                proofs.append({'source':ref,'figure_boxes':boxes,'evidence':{'file':image.relative_to(ROOT).as_posix(),'sha256':sha(image)},'semantic_caption_generated':False})
    write_jsonl(rules/'box-dispositions.jsonl',exclusions)
    write_jsonl(rules/'figure-exclusions.jsonl',proofs)
    write_json(rules/'text-scope-review.json',{'plate_rows_added':9,'figure_spans_excluded':len(proofs),
      'scope':'All 833 pages; literal text and reviewed tables. Graphic topology, connector position and display-shape interpretation are not encoded.',
      'figure_policy':'corpus/그림과_텍스트_처리원칙.md','source_check':'CODEX_PDF_VISUAL_CHECK','human_source_review':'NOT_PERFORMED'})
    print({'plate_rows':9,'figure_exclusions':len(proofs),'corrected_line_regions':len(regions)})


if __name__=='__main__':main()
