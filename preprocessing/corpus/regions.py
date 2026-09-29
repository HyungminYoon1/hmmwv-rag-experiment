"""Layout-aware candidates. Ambiguous geometry never becomes an approved order.

The splitter only rearranges literal source slices. A layout candidate remains
review-required until a PDF-reviewed contract supplies boundaries and context.
"""
from collections import defaultdict
import re
from .common import source_parts

SECTION = re.compile(r'^(\d{1,2}-\d{1,3}(?:\.\d+)*[A-Za-z]?)\.\s+(.+)')


def is_section(ref):
    value=ref['text'].strip();match=SECTION.match(value)
    if not match:return None
    # A printed page reference such as "2-312 PCB" has no terminating dot.
    if value.isupper() or any('Bold' in f or 'Heavy' in f for f in ref['fonts']):
        return match[1]
    return None


def page_kind(refs,pn):
    header=' '.join(r['text'] for r in refs if r['bbox'] and r['bbox'][1]<110)
    if pn in range(526,532):return 'reviewed_two_column'
    if 'DIAGNOSTIC FLOWCHART' in header:return 'diagnostic_flowchart'
    if 'REFERENCE INFORMATION' in header:return 'reference_information'
    if any(is_section(r) for r in refs):return 'numbered_section'
    return 'other'


def bucket(ref,kind):
    box=ref['bbox']
    if not box:return 'unknown'
    x0,y0,x1,y1=box
    if kind=='diagnostic_flowchart':
        # A line that intersects multiple content columns is kept separate and
        # flagged. No character-to-column locations are guessed from its text.
        if x0<165 and x1<=168:return 'left'
        if 165<=x0<355 and x1<=360:return 'centre'
        if x0>=350:return 'right'
        return 'cross_column'
    if kind in ('reference_information','reviewed_two_column'):
        if x0<320 and x1<=335:return 'left'
        if x0>=320:return 'right'
        return 'wide'
    return 'body'


def group_regions(refs,kind):
    """Within a column, retain PDF/OCR blocks; do not interleave neighbouring ones."""
    groups=defaultdict(list)
    anchors=sorted({round(r['bbox'][1],1) for r in refs if r['bbox'] and
                    r['text'].strip() in ('KNOWN INFO','TEST OPTIONS')})
    bands=[]
    for y in anchors:
        if not bands or y-bands[-1]>15:bands.append(y)
    for ref in refs:
        col=bucket(ref,kind)
        # Mixed OCR lines cannot be repaired by concatenating other lines.
        # Preserve them individually as evidence for the next extraction review.
        if col in ('cross_column','unknown'):
            key=(col,ref['record_id'],('span',ref['start']))
        elif kind=='diagnostic_flowchart':
            band=sum(y<=box_y+6 for y in bands) if (box_y:=ref['bbox'][1]) else 0
            key=(col,'node_band',band)
        elif kind in ('reference_information','reviewed_two_column'):
            key=(col,'page_column',0)
        else:key=(col,'section',0)
        groups[key].append(ref)
    result=[]
    rank={'left':0,'centre':1,'right':2,'wide':3,'body':0,'unknown':4,'cross_column':5}
    for key,items in groups.items():
        # Original offset is primary within a block; a reviewed OCR correction
        # can span multiple physical lines and must not be reordered internally.
        items.sort(key=lambda r:((r['bbox'] or [0,0,0,0])[1],(r['bbox'] or [0,0,0,0])[0],r['start']))
        result.append((key,items))
    result.sort(key=lambda pair:(min((r['bbox'] or [0,0,0,0])[1] for r in pair[1]),
                                 rank[pair[0][0]],pair[1][0]['start']))
    return result


def prose_units(store,units,selected):
    from .structure import page_titles
    by_page=defaultdict(list)
    for ref in selected:by_page[ref['pdf_page']].append(ref)
    for pn,refs in sorted(by_page.items()):
        kind=page_kind(refs,pn)
        titles=page_titles(store,pn)
        # Expand the genuine header only, never a page reference inside a box.
        title_keys={(r['record_id'],r['start'],r['end']) for r in titles}
        headings=sorted([(r,is_section(r)) for r in refs if is_section(r)],
                        key=lambda pair:((pair[0]['bbox'] or [0,0,0,0])[1],pair[0]['start']))
        body=[r for r in refs if (r['record_id'],r['start'],r['end']) not in title_keys
              and not is_section(r)]
        segments=defaultdict(list)
        for ref in body:
            y=(ref['bbox'] or [0,0,0,0])[1]
            active=[(h,s) for h,s in headings if (h['bbox'] or [0,0,0,0])[1]<=y]
            section=active[-1][1] if active else None
            segments[section].append(ref)
        all_heading_refs=titles+[h for h,_ in headings]
        if not body:
            if all_heading_refs:
                units.add(f'heading:{pn}','heading',source_parts(all_heading_refs),metadata={'boundary':'source_heading'})
            continue
        for segment_number,(section,items) in enumerate(segments.items()):
            section_headings=[h for h,s in headings if s==section]
            prefixes=titles+section_headings
            seen=set();prefixes=[r for r in prefixes if not ((r['record_id'],r['start'],r['end']) in seen or seen.add((r['record_id'],r['start'],r['end'])))]
            family=None
            if store.coordinate_spans:
                from .layout import groups as spatial_groups
                family,groups=spatial_groups(store,pn,items,kind)
            else:groups=group_regions(items,kind)
            for i,(group,part) in enumerate(groups):
                key=f'region:{pn}:{segment_number+1}:{i+1}'
                reviews=[store.review('STRUCTURE_BOUNDARY',pn,
                    '이 문자 블록의 경계를 확인합니다. 별도 계약이 없는 다른 박스의 조건이나 그림 관계는 상속하지 않습니다.',part[:1],key)]
                if group[0] in ('cross_column','unknown'):
                    store.review('CROSS_REGION_TEXT',pn,
                        '한 추출 줄이 여러 열 또는 영역과 겹칩니다. 문자별 좌표나 원문 대조 없이 나누거나 다른 본문에 연결하지 않았습니다.',part,key)
                    for ref in part:store.decide(ref,'NEEDS_REVIEW','CROSS_REGION_TEXT',['B01','G02'])
                    continue
                elif any(r['layer']=='ocr' for r in part):
                    reviews.append(store.review('OCR_REGION_STRUCTURE',pn,
                        '이 OCR 블록의 문자 품질과 진단 박스·그림 설명 경계를 확인해야 합니다.',part[:1],key))
                units.add(key,'prose',source_parts(part),source_parts(prefixes,'heading'),reviews,
                          {'section':section,'boundary':'source_block_candidate','page_layout':kind,
                           'column':group[0],'cross_page_join':False,
                           'graphic_relations_inferred':False,
                           'layout_family':family,
                           'graphic_dependency':family in ('DIAGNOSTIC_PANEL','FREE_FLOWCHART'),
                           'condition_link_basis':'NO_UNREVIEWED_CROSS_BOX_INHERITANCE'})
        # Headers not used by any body are still retained as literal source.
        for i,ref in enumerate(all_heading_refs):
            if not store.claimed(ref):
                units.add(f'heading:{pn}:{i}','heading',source_parts([ref]),metadata={'boundary':'source_heading'})
