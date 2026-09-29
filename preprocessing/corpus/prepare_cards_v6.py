"""Keep a test card's literal title, pre-test and notes with its procedure."""
import re
import pymupdf
from .common import *
from .structure import Units,reviewed_tables,manual_tables
from .boxes import reviewed_boxes
from .select_spans import select,ledger
from .regions import prose_units


def main():
    s=SourceStore(check=False);rules=PACKAGE/'rules/v6'
    if (rules/'test-card-review.json').exists():raise ValueError('Already prepared')
    u=Units(s);reviewed_tables(s,u);manual_tables(s,u);reviewed_boxes(s,u)
    prose_units(s,u,select(s));rows=s.table('box-units.jsonl');added=[]
    def refs(x):return [p['source'] for p in x['body_parts'] if p['kind']=='source']
    pages=[]
    with pymupdf.open(ROOT/s.config['source_pdf']) as pdf:
        for pn in range(831,851):
            if pn==849:continue # Existing individually reviewed test-card contract.
            raw=s.records.get(f'P{pn:04d}:native',{}).get('text','')
            if 'Description:' not in raw or 'Test Procedure:' not in raw:continue
            items=[x for x in u.items if x['pdf_pages']==[pn] and x['kind']=='prose']
            title=[x for x in items if re.search(r'TEST\s*#\s*\d+',x['body_text']) and len(x['body_text'])<150]
            proc=[x for x in items if x['body_text'].startswith('Test Procedure:')]
            if len(title)!=1 or len(proc)!=1:raise ValueError(('Card structure',pn,len(title),len(proc)))
            pre=[x for x in items if re.match(r'(?:Pre-Test|Pm-Test|Pm-lest) Procedure',x['body_text'])]
            notes=[x for x in items if x['body_text'].startswith('NOTES')]
            if not pre:raise ValueError(('Missing pre-test context',pn))
            image=PACKAGE/f'reports/rules-v6-work/figure-scope/card-{pn}.png';pdf[pn-1].get_pixmap(dpi=144).save(image)
            ev={'file':image.relative_to(ROOT).as_posix(),'sha256':sha(image)}
            for i,item in enumerate(items):
                if item in title:continue
                context=[r for t in title for r in refs(t)]
                if item in proc:context += [r for x in pre+notes for r in refs(x)]
                row={'key':f'V6:CARD:{pn}:{i}','kind':'test_card_section','body_refs':refs(item),'context_refs':context,
                  'review_codes':[],'review':'PDF_TEST_CARD_LAYOUT_PROFILE','evidence':ev,
                  'metadata':{'boundary':'literal_test_card_section','card_page':pn,'is_test_procedure':item in proc,
                    'condition_link_basis':'SAME_TEST_CARD_PRE_TEST_AND_NOTES' if item in proc else 'SAME_CARD_TITLE',
                    'graphic_relations_inferred':False}}
                rows.append(row);added.append(row['key'])
            pages.append(pn)
    write_jsonl(rules/'box-units.jsonl',rows)
    write_json(rules/'test-card-review.json',{'pages':pages,'units':added,'regression_samples':[832,841,848],
      'rule':'Same printed card only; Pre-Test and NOTES repeated with Test Procedure. No error message becomes a prerequisite.',
      'human_source_review':'NOT_PERFORMED'})
    print({'test_card_pages':pages,'sections':len(added)})


if __name__=='__main__':main()
