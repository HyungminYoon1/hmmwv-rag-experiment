"""Apply reviewed figure bounds while protecting tables and literal prose."""
import re
import pymupdf
from .common import *
from .structure import Units,reviewed_tables,manual_tables
from .boxes import reviewed_boxes
from .select_spans import select
from .regions import prose_units

# Visual review: figure-scope/sheet-00..09. Bounds describe the illustration,
# not the page. Instructions and plate/table text are handled separately.
FIGURES={
132:[(155,255,477,545)],146:[(80,211,552,713)],153:[(60,340,575,625)],158:[(35,448,550,748)],
173:[(40,265,560,710)],174:[(40,292,560,710)],175:[(35,205,560,445)],
176:[(40,118,560,732)],177:[(30,95,565,732)],178:[(30,140,560,731)],179:[(30,150,565,738)],
180:[(30,100,565,740)],181:[(30,100,565,740)],182:[(90,254,550,635)],223:[(210,330,410,711)],
498:[(35,190,560,624)],499:[(35,180,567,592)],500:[(35,175,560,590)],501:[(35,165,560,586)],
605:[(145,113,570,475)],683:[(100,145,520,713)],
786:[(80,150,540,647)],787:[(35,140,545,662)],788:[(60,145,542,684)],789:[(70,140,565,677)],
790:[(35,115,568,713)],791:[(45,115,565,682)],792:[(40,125,565,708)],
851:[(40,201,560,695)],852:[(40,167,560,704)],853:[(170,166,352,299),(170,384,352,480),(170,582,352,686)],
857:[(38,348,550,718)],859:[(190,413,418,662)]}


def main():
    s=SourceStore(check=False);rules=PACKAGE/'rules/v6'
    if (rules/'final-text-scope-review.json').exists():raise ValueError('Already applied')
    units=Units(s);reviewed_tables(s,units);manual_tables(s,units);reviewed_boxes(s,units)
    disp=s.table('box-dispositions.jsonl');proofs=s.table('figure-exclusions.jsonl')
    image_root=PACKAGE/'reports/rules-v6-work/figure-scope'
    with pymupdf.open(ROOT/s.config['source_pdf']) as pdf:
        for pn,bounds in FIGURES.items():
            image=image_root/f'full-{pn}.png';pdf[pn-1].get_pixmap(dpi=144).save(image)
            ev={'file':image.relative_to(ROOT).as_posix(),'sha256':sha(image)}
            for layer in ('native','ocr'):
                rid=f'P{pn:04d}:{layer}'
                if rid not in s.records:continue
                for ref in s.fragments(rid):
                    if not ref['text'].strip() or s.claimed(ref) or not ref['bbox']:continue
                    b=ref['bbox'];cx=(b[0]+b[2])/2;cy=(b[1]+b[3])/2
                    if not any(x0<=cx<=x1 and y0<=cy<=y1 and b[0]>=x0-3 and b[2]<=x1+3 for x0,y0,x1,y1 in bounds):continue
                    # Preserve independent warnings and captions near diagrams.
                    if re.search(r'WHEN CHECKING|DISCONNECT NEGATIVE|MAKING CONTINUITY|ALL CIRCUITS MUST RETURN|Figure\s+\d+\.',ref['text'],re.I):continue
                    disp.append({'source':ref,'status':'EXCLUDED_NON_TEXT','reason':'REVIEWED_DIAGRAM_LABEL_OR_GRAPHIC_FRAGMENT_PDF_ONLY','rule':f'V6-FIGURE-FINAL-{pn}'})
                    proofs.append({'source':ref,'figure_boxes':bounds,'evidence':ev,'semantic_caption_generated':False})
    # The original p50 plate itself has faded/absent numeric content. Keep the
    # readable instruction; never reconstruct missing weights or diagram values.
    rid='P0050:ocr';text=s.records[rid]['text'];a=text.index('ATTACH TIE-DOWNS');b=text.index('GUIDES',a)+6
    image=image_root/'p50.png';ev={'file':image.relative_to(ROOT).as_posix(),'sha256':sha(image)}
    rows=s.table('box-units.jsonl');rows.append({'key':'V6:P0050:sling-instruction','kind':'reviewed_text_box',
      'body_refs':[s.ref(rid,a,b)],'context_refs':[],'review_codes':[],'review':'CODEX_PDF_LAYOUT_REVIEW','evidence':ev,
      'metadata':{'boundary':'individually_reviewed_pdf_box','graphic_dependency':True,'graphic_relations_inferred':False,
                  'source_issues':['P0050_FADED_DATA_PLATE']}})
    for ref in s.fragments(rid,extra=[a,b]):
        if ref['bbox'] and ref['bbox'][1]>135 and ref['text'].strip() and not (a<=ref['start'] and ref['end']<=b):
            disp.append({'source':ref,'status':'EXCLUDED_NON_TEXT','reason':'FADED_OR_DIAGRAM_DEPENDENT_DATA_PLATE_RETAINED_IN_PDF','rule':'V6-P50-SOURCE-LIMIT'})
            proofs.append({'source':ref,'evidence':ev,'source_limitation':'Original plate is partly faded; weights are not reconstructed.'})
    issues=s.table('source-issues.jsonl');issues.append({'id':'P0050_FADED_DATA_PLATE','pdf_page':50,
      'detail':'원본 명판의 도식 및 중량 수치 일부가 희미하거나 비어 있어 값을 추정하지 않았다. 읽을 수 있는 슬링 지시문은 별도 보존한다.','evidence':ev})
    write_jsonl(rules/'source-issues.jsonl',issues);write_jsonl(rules/'box-units.jsonl',rows)
    write_jsonl(rules/'box-dispositions.jsonl',disp);write_jsonl(rules/'figure-exclusions.jsonl',proofs)
    # Exclude standalone diagram strokes/markers only. Numeric values in any
    # structured table/box and letters embedded in prose cannot match this rule.
    s=SourceStore(check=False);u=Units(s);reviewed_tables(s,u);manual_tables(s,u);reviewed_boxes(s,u)
    selected=select(s);prose_units(s,u,selected);markers=[]
    for unit in u.items:
        if unit['kind']!='prose':continue
        value=unit['body_text'].strip();family=unit['metadata'].get('layout_family')
        if family not in ('DIAGNOSTIC_PANEL','FREE_FLOWCHART','REFERENCE_PAGE','TEXT_FIGURE_OR_LABELS'):continue
        if not re.fullmatch(r'[\s\W\dIOolvyY]{1,45}',value):continue
        # A number-only value outside a diagram may be real data: preserve it.
        if re.fullmatch(r'[\d\s.,+-]+',value):continue
        for part in unit['body_parts']:
            if part['kind']!='source':continue
            ref=part['source'];markers.append({'source':ref,'status':'EXCLUDED_NON_TEXT','reason':'STANDALONE_NON_PROSE_DIAGRAM_MARKER','rule':'V6-MARKER'})
    write_jsonl(rules/'box-dispositions.jsonl',disp+markers)
    write_jsonl(rules/'standalone-marker-decisions.jsonl',markers)
    write_json(rules/'final-text-scope-review.json',{'figure_pages':list(FIGURES),'figure_proofs':len(proofs),
      'standalone_marker_spans':len(markers),'source_limitations':[50],'protected':'Claimed tables, boxes, independent warnings and captions',
      'source_review':'CODEX_PDF_VISUAL_CHECK','human_source_review':'NOT_PERFORMED'})
    print({'figure_proofs':len(proofs),'markers':len(markers)})


if __name__=='__main__':main()
