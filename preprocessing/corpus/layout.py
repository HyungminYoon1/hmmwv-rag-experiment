"""Literal spatial grouping, independent of OCR transcription and text selection."""
from collections import defaultdict
from .common import BASE, read_json, union_box


def groups(store,pn,refs,kind):
    path=BASE/f'ocr-structure-review-20260924/full-audit-e/page-{pn:04d}.json'
    audit=read_json(path) if path.exists() else None
    family=audit['summary']['family_candidate'] if audit else 'NATIVE_TEXT'
    buckets=defaultdict(list)
    test_card=all(t in store.records.get(f'P{pn:04d}:native',{}).get('text','')
                  for t in ('Description:','Test Procedure:'))
    for ref in refs:
        x0,y0,x1,y1=ref['bbox'] or [0,0,0,0]
        cx=(x0+x1)/2
        spans=[s for s in store.coordinate_spans[ref['record_id']]
               if s['start']<=ref['start'] and ref['end']<=s['end']]
        if pn==125 and ref['layer']=='native' and 150<y0<215:
            group='callout-'+('left' if cx<205 else 'middle' if cx<435 else 'right')
        elif pn==125 and ref['layer']=='native' and 475<y0<612:
            group='callout-bottom-'+('left' if cx<175 else 'middle' if cx<315 else 'right')
        elif spans:
            group=spans[0]['group']
        elif ref['coordinate_precision']=='reviewed_pdf_region':
            group='reviewed-'+str(tuple(ref['bbox']))
        elif ref['layer']=='native' and test_card:
            group='card-left' if cx<340 else 'card-right'
        elif ref['layer']=='native' and audit:
            hits=[r for r in audit['rectangles'] if r['bbox'][0]-3<=cx<=r['bbox'][2]+3 and
                  r['bbox'][1]-2<=(y0+y1)/2<=r['bbox'][3]+2 and
                  x0>=r['bbox'][0]-3 and x1<=r['bbox'][2]+3]
            group=min(hits,key=lambda r:r['area'])['id'] if hits else 'native-block-'+str(ref['source_blocks'])
        elif ref['layer']=='native':
            group='native-block-'+str(ref['source_blocks'])
        else:
            group='unboxed-'+('left' if cx<335 else 'right') if kind=='reference_information' else 'unboxed-body'
        buckets[group].append(ref)
    output=[]
    for name,items in buckets.items():
        items.sort(key=lambda r:(round(r['bbox'][1]/3) if r['bbox'] else 0,
                                 (r['bbox'] or [0,0,0,0])[0],r['start']))
        if name.startswith(('unboxed','native-unboxed','card-')):
            segments=[]
            for ref in items:
                if segments:
                    last=segments[-1][-1]
                    gap=ref['bbox'][1]-last['bbox'][3]
                    new_heading=test_card and (ref['text'].strip().endswith(':') or ref['text'].strip()=='NOTES')
                else:gap=100;new_heading=True
                if gap>15 or new_heading:segments.append([])
                segments[-1].append(ref)
            output.extend(((name,i),rs) for i,rs in enumerate(segments))
        else:output.append(((name,0),items))
    # Join a short printed panel heading to the immediately touching panel.
    # This does not link a flowchart branch or inherit a neighbouring warning.
    # The exact bounds and header predicates are checked in profile tests.
    merged=set()
    for i,(group,part) in enumerate(output):
        value=' '.join(r['text'].strip() for r in part)
        if not(value.isupper() and len(value)<=85 and
               ('TEST' in value or value in ('KNOWN INFO','POSSIBLE PROBLEMS','CONTINUITY (RESISTANCE)','BATTERY VOLTAGE','MULTIMETER'))):continue
        box=union_box([r['bbox'] for r in part]);candidates=[]
        for j,(other,body) in enumerate(output):
            if j==i or j in merged:continue
            b=union_box([r['bbox'] for r in body]);gap=b[1]-box[3]
            if 0<=gap<18 and abs((box[0]+box[2])-(b[0]+b[2]))/2<55 and b[2]-b[0]>50:
                candidates.append((gap,j))
        if candidates:
            _,j=min(candidates);output[j]=(output[j][0],part+output[j][1]);merged.add(i)
    output=[item for i,item in enumerate(output) if i not in merged]
    output.sort(key=lambda pair:(min(r['bbox'][1] for r in pair[1]),pair[0]))
    return family,output
