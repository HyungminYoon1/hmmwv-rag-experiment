"""Install the explicit PDF alignment decisions before the v14 ref migration."""
from .common import *


def main():
    rules=PACKAGE/'rules/v6';s=SourceStore(check=False)
    path=rules/'alignment-review.jsonl'
    if path.exists():raise ValueError('Already applied')
    decisions=read_json(PACKAGE/'reports/rules-v6-work/alignment/decisions.json')
    overrides=read_jsonl(rules/'selection-overrides.jsonl')
    # 613 is now a stated figure exclusion, not an unresolved text selection.
    superseded=[r for r in overrides if r['source']['pdf_page']==613 and r['action']=='NEEDS_REVIEW']
    overrides=[r for r in overrides if r not in superseded]
    boxes=read_jsonl(rules/'box-dispositions.jsonl')
    for b in boxes:
        if b['source']['pdf_page']==613 and b['status']=='NEEDS_REVIEW':
            b.update(status='EXCLUDED_NON_TEXT',reason='FIGURE_TOPOLOGY_OUTSIDE_TEXT_RESEARCH_SCOPE')
    write_jsonl(rules/'box-dispositions.jsonl',boxes)
    units=read_jsonl(PACKAGE/'reports/rules-v6-work/v13-units.jsonl')
    for d in decisions:
        action=d['action'];src=d['source_refs'][0];targets=d['source_refs'][1:]
        if d['number'] in (11,13):
            needle='MIL-B-46176' if d['number']==11 else 'Inspect tires'
            targets=[p['source'] for u in units for p in u['body_parts'] if p['kind']=='source' and
                     p['source']['layer']=='table' and p['source']['pdf_page']==src['pdf_page'] and needle in p['text']]
            assert targets
        if d['number'] in (103,104):targets=[t for t in targets if t['text']!='G']
        if d['number'] in (100,101,102):
            for n in targets:
                overrides.append({'id':f'V6-A{d["number"]:03d}-BULLET','source':n,'action':'LAYOUT_ONLY',
                 'reason':'PRINTED_BULLET_NOT_LETTER_G','review':'CODEX_PDF_VISUAL_REVIEW',
                 'image':d['image'],'image_sha256':d['image_sha256']})
        if action=='GRAPHIC':rule_action='EXCLUDED_NON_TEXT';reason='FIGURE_OR_FLOW_MARKER_RETAINED_IN_SOURCE_NOT_PROSE'
        elif action=='REPRESENT':rule_action='REPRESENT';reason='PDF_CONFIRMED_ALTERNATIVE_TEXT'
        else:rule_action='PREFERRED';reason='PDF_CONFIRMED_TEXT_NATIVE_LAYER_IS_PARTIAL_REFERENCE'
        row={'id':f'V6-A{d["number"]:03d}','source':src,'action':rule_action,'reason':reason,
             'review':'CODEX_PDF_VISUAL_REVIEW','image':d['image'],'image_sha256':d['image_sha256']}
        if action=='REPRESENT':row['targets']=targets
        overrides.append(row)
    write_jsonl(rules/'selection-overrides.jsonl',overrides)
    write_jsonl(path,decisions)
    write_json(rules/'alignment-superseded.json',superseded)
    print(len(decisions),'decisions installed')


if __name__=='__main__':main()
