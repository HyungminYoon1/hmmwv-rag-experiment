"""Bound native conditions by connected printed rectangles, not next heading."""
from collections import defaultdict
import pymupdf
from .common import SourceStore,PACKAGE,ROOT,read_json,read_jsonl,write_json,write_jsonl,union_box


def components(page):
    boxes=[]
    for drawing in page.get_drawings():
        for item in drawing['items']:
            if item[0]=='re':
                b=list(item[1])
                if b[2]-b[0]>55 and b[3]-b[1]>5:boxes.append(b)
    groups=[]
    for b in boxes:
        hit=[g for g in groups if any(abs(b[0]-x[0])<6 and abs(b[2]-x[2])<6 and
               max(b[1],x[1])-min(b[3],x[3])<3 for x in g)]
        if hit:
            merged=[b]+[x for g in hit for x in g]
            groups=[g for g in groups if g not in hit]+[merged]
        else:groups.append([b])
    return [union_box(g) for g in groups]


def contains(box,ref):
    b=ref['bbox'];x=(b[0]+b[2])/2;y=(b[1]+b[3])/2
    return box[0]-2<=x<=box[2]+2 and box[1]-2<=y<=box[3]+2


def main():
    s=SourceStore(check=False);rules=PACKAGE/s.config['rules_path'];rows=read_jsonl(rules/'box-units.jsonl')
    original={r['key']:r for r in read_jsonl(PACKAGE/'rules/v5-final/box-units.jsonl')}
    eligible={'BOUNDED_NATIVE_BOX_PROFILE','PRINTED_RECTANGLE_BOUNDED_NATIVE_PROFILE'}
    pages=sorted({r['body_refs'][0]['pdf_page'] for r in rows if r['metadata'].get('condition_link_basis') in eligible})
    geometry={};changes=[];extra=[]
    with pymupdf.open(ROOT/s.config['source_pdf']) as pdf:
        for pn in pages:geometry[pn]=components(pdf[pn-1])
    for row in rows:
        if row['metadata'].get('condition_link_basis') not in eligible:continue
        pn=row['body_refs'][0]['pdf_page'];refs=original[row['key']]['context_refs']
        anchor=next((r for r in refs if r['text'].strip()=='KNOWN INFO'),None)
        matching=[b for b in geometry[pn] if anchor and b[0]<180 and b[2]<185 and contains(b,anchor)]
        if len(matching)!=1:
            changes.append({'key':row['key'],'status':'UNRESOLVED_RECTANGLE','matches':matching});continue
        box=matching[0]
        # Keep headings and the exact local step identifier. Only the left
        # condition body is bounded here; prior explicitly reviewed links stay.
        keep=[];removed=[]
        for r in refs:
            if r['bbox'][1]<120 or r['text']==row['metadata'].get('step') or contains(box,r):keep.append(r)
            else:removed.append(r)
        if removed:
            row['context_refs']=keep
            extra.append({'key':row['key']+':detached-flow-text','kind':'flow_annotation','body_refs':removed,
                          'context_refs':[r for r in keep if r['bbox'][1]<120],
                          'metadata':{'boundary':'source_region','graphic_dependency':True,
                          'branch_relation':'PDF_ONLY','graphic_relations_inferred':False},
                          'review':'SOURCE_RECTANGLE_BOUNDARY','review_codes':['FLOW_ANNOTATION_REVIEW'],'evidence':row['evidence']})
        row['metadata']['condition_link_basis']='PRINTED_RECTANGLE_BOUNDED_NATIVE_PROFILE'
        row['metadata']['condition_box']=box
        changes.append({'key':row['key'],'status':'GEOMETRY_BOUNDED','box':box,
                        'removed_from_condition':[{'text':r['text'],'record_id':r['record_id'],'start':r['start'],'end':r['end']} for r in removed]})
    extra_keys={r['key'] for r in extra}
    write_jsonl(rules/'box-units.jsonl',[r for r in rows if r['key'] not in extra_keys]+extra)
    write_json(rules/'native-boundary-refinement.json',{'source_pdf':s.config['source_pdf'],
        'geometry':geometry,'changes':changes,'corrected_units':sum(bool(c.get('removed_from_condition')) for c in changes),
        'pending_units':sum(c['status']!='GEOMETRY_BOUNDED' for c in changes),
        'next_heading_used_as_lower_boundary':False,'graphic_paths_inferred':False})
    print({'pages':len(pages),'units':len(changes),'changed':sum(bool(c.get('removed_from_condition')) for c in changes),
           'pending':sum(c['status']!='GEOMETRY_BOUNDED' for c in changes)})

if __name__=='__main__':main()
