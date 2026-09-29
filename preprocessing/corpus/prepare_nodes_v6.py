"""Build bounded same-node OCR contracts; do not infer any YES/NO edge."""
from collections import defaultdict
import re
from .common import *
from .structure import Units,reviewed_tables,manual_tables
from .boxes import reviewed_boxes
from .select_spans import select
from .regions import prose_units


def main():
    s=SourceStore(check=False);rules=PACKAGE/'rules/v6'
    # Revision 2 changes only panel geometry. Preserve the original contracts
    # and review decisions before reconstructing their literal components.
    old=rules/'node-profile-review.json'
    revision=4
    history=rules/f'node-profile-review-v{revision-1}.json'
    if old.exists():
        if history.exists():raise ValueError('Revision already prepared')
        write_json(history,read_json(old))
        saved=read_jsonl(rules/'profile-superseded-boxes.jsonl')
        write_jsonl(rules/f'profile-superseded-boxes-v{revision-1}.jsonl',saved)
        from .exception_pages_v6 import PAGES
        from .late_exception_pages_v6 import PAGES as LATE
        from .end_panel_pages_v6 import PAGES as ENDS
        exceptions=set(PAGES)|set(LATE)|set(ENDS)
        rows=s.table('box-units.jsonl')
        rows=[r for r in rows if r['metadata'].get('profile')!='V6_OCR_DIAGNOSTIC_TEXT']
        keys={r['key'] for r in rows}
        rows += [r for r in saved if r['key'] not in keys and
                 not any(x['pdf_page'] in exceptions for x in r['body_refs'])]
        write_jsonl(rules/'box-units.jsonl',rows)
        s=SourceStore(check=False)
    u=Units(s);reviewed_tables(s,u);manual_tables(s,u);reviewed_boxes(s,u)
    selected=select(s);prose_units(s,u,selected)
    work=PACKAGE/'reports/rules-v6-work';write_jsonl(work/'pre-node-units.jsonl',u.items);write_jsonl(work/'pre-node-reviews.jsonl',s.reviews)
    bypage=defaultdict(list)
    for unit in u.items:
        if len(unit['pdf_pages'])==1:bypage[unit['pdf_pages'][0]].append(unit)
    rows=s.table('box-units.jsonl');original={r['key']:r for r in rows};added=[];consumed=set();results=[]
    def refs(unit):return [p['source'] for p in unit['body_parts'] if p['kind']=='source']
    def bbox(unit):return union_box([r['bbox'] for r in refs(unit) if r['bbox']])
    def literal(unit):return re.sub(r'\s+',' ',unit['body_text']).strip()
    for pn,allunits in sorted(bypage.items()):
        auditpath=BASE/f'ocr-structure-review-20260924/full-audit-e/page-{pn:04d}.json'
        if not auditpath.exists():continue
        audit=read_json(auditpath)
        if audit['summary']['family_candidate']!='DIAGNOSTIC_PANEL' or pn==125:continue
        # Join touching outlines in the left column. A last-node condition may
        # end well above a terminal oval; the next heading is not its boundary.
        rects=[r['bbox'] for r in audit['rectangles'] if r['bbox'][0]>=20 and
               r['bbox'][2]<=185 and 50<r['bbox'][2]-r['bbox'][0]<160]
        components=[]
        for b in sorted(rects,key=lambda b:b[1]):
            hits=[g for g in components if any(abs(b[0]-a[0])<6 and abs(b[2]-a[2])<6 and
                   max(b[1],a[1])-min(b[3],a[3])<5 for a in g)]
            merged=[b]+[a for g in hits for a in g]
            components=[g for g in components if g not in hits]+[merged]
        bounds=[union_box(g) for g in components]
        pool=[x for x in allunits if x['kind'] in ('prose','reviewed_text_box')]
        questions=[x for x in pool if '?' in literal(x) and (b:=bbox(x)) and 145<=b[0]<=215 and b[2]<=370 and b[2]-b[0]>85 and b[1]>125]
        questions.sort(key=lambda x:bbox(x)[1])
        known=[x for x in pool if re.search(r'KNOWN\s+INFO',literal(x)) and bbox(x)[2]<177]
        known.sort(key=lambda x:bbox(x)[1])
        for qi,q in enumerate(questions):
            qb=bbox(q);candidates=[x for x in known if -18<=qb[1]-bbox(x)[1]<=48]
            if len(candidates)!=1:
                results.append({'pdf_page':pn,'question':q['key'],'status':'NOT_LINKED','reason':'NO_UNIQUE_BOUNDED_LEFT_HEADER','candidates':len(candidates)});continue
            anchor=candidates[0];y=bbox(anchor)[1];next_y=min([bbox(x)[1] for x in known if bbox(x)[1]>y+25]+[755])
            ab=bbox(anchor);cx=(ab[0]+ab[2])/2;cy=(ab[1]+ab[3])/2
            physical=[b for b in bounds if b[0]-3<=cx<=b[2]+3 and b[1]-3<=cy<=b[3]+3]
            if len(physical)!=1:
                results.append({'pdf_page':pn,'question':q['key'],'status':'LITERAL_PANELS_PDF_RELATIONS_ONLY','reason':'NO_UNIQUE_LEFT_RECTANGLE'});continue
            left_box=physical[0]
            left=[x for x in pool if (b:=bbox(x)) and b[0]>=left_box[0]-3 and b[2]<=left_box[2]+3 and
                  b[1]>=left_box[1]-3 and b[3]<=left_box[3]+3
                  and not re.search(r'\b(?:GO TO|FROM|Page|YES|NO FAULTS)\b',literal(x))]
            # The right panel begins beside the question/step, not below the
            # centre's last line. Only the printed TEST OPTIONS / REASON region
            # belonging to this vertical block can be inherited.
            right=[x for x in pool if (b:=bbox(x)) and b[0]>=320 and
                   b[2]<=575 and b[1]>=y-15 and b[3]<next_y-4]
            right.sort(key=lambda x:(bbox(x)[1],bbox(x)[0]))
            if not any('TEST OPTIONS' in literal(x) or 'REASON FOR QUESTION' in literal(x) for x in right):
                results.append({'pdf_page':pn,'question':q['key'],'status':'NOT_LINKED','reason':'NO_BOUNDED_TEST_PANEL'});continue
            left.sort(key=lambda x:(bbox(x)[1],bbox(x)[0]))
            members=[q,*left,*right]
            if any(x['key'] in consumed for x in members):
                results.append({'pdf_page':pn,'question':q['key'],'status':'NOT_LINKED','reason':'AMBIGUOUS_SHARED_PANEL'});continue
            topic=[]
            rid=f'P{pn:04d}:ocr'
            for r in selected:
                b=r['bbox']
                if r['pdf_page']==pn and b and b[3]<130 and b[0]<180 and b[2]<205 and len(r['text'].strip())>2:
                    topic.append(r)
            topic.sort(key=lambda r:(r['bbox'][1],r['bbox'][0]))
            key=f'V6:P{pn:04d}:node:{qi+1}'
            body=[r for x in [q,*right] for r in refs(x)];context=topic+[r for x in left for r in refs(x)]
            evidence=next((x['evidence'] for x in [original[m['key']] for m in members if m['key'] in original]),None)
            if not evidence:evidence={'file':auditpath.relative_to(ROOT).as_posix(),'sha256':sha(auditpath)}
            added.append({'key':key,'kind':'diagnostic_box','body_refs':body,'context_refs':context,
              'body_separator':' ','context_separator':'\n','review_codes':[],
              'review':'SAMPLED_PDF_PROFILE_WITH_BOUNDED_GEOMETRY',
              'evidence':evidence,'metadata':{'boundary':'bounded_same_node_panels',
                'condition_link_basis':'UNIQUE_LEFT_HEADER_AND_BOUNDED_SAME_NODE_TEST_PANEL',
                'question_bbox':qb,'condition_band':[y,next_y],
                'condition_box':left_box,
                'profile':'V6_OCR_DIAGNOSTIC_TEXT','source_component_keys':[x['key'] for x in members],
                'graphic_relations_inferred':False,'graphic_dependency':True,
                'branch_interpretation':'PDF_ONLY_UNLESS_SEPARATE_VERIFIED_EDGE'}})
            consumed.update(x['key'] for x in members)
            results.append({'pdf_page':pn,'question':q['key'],'status':'LINKED','contract':key,
                            'left_components':[x['key'] for x in left],'right_components':[x['key'] for x in right]})
    replaced=[r for r in rows if r['key'] in consumed]
    write_jsonl(rules/'box-units.jsonl',[r for r in rows if r['key'] not in consumed]+added)
    write_jsonl(rules/'profile-superseded-boxes.jsonl',replaced)
    write_json(rules/'node-profile-review.json',{'nodes':len(added),'superseded_component_boxes':len(replaced),
      'results':results,'development_samples':[183,549,720,728],
      'regression_profile_samples':[125,828,728,720,549],
      'revision':revision,
      'excluded_special_page':125,'review_method':'Source PDF comparison and bounded application checks; not all characters re-read.',
      'human_source_review':'NOT_PERFORMED'})
    print({'nodes':len(added),'unlinked':[r for r in results if r['status']=='NOT_LINKED']})


if __name__=='__main__':main()
