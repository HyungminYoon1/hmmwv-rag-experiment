"""Apply the individually checked zero-ink findings, including shifted text."""
from .common import *


def main():
    s=SourceStore(check=False);rules=PACKAGE/s.config['rules_path']
    findings=read_json(rules/'native-visibility.json')['invisible_candidates']
    boxes=read_jsonl(rules/'box-units.jsonl');disps=read_jsonl(rules/'box-dispositions.jsonl');regions=read_jsonl(rules/'source-regions.jsonl')
    log=[]
    for f in findings:
        rid=f['record_id'];pn=f['pdf_page'];a=f['raw_start'];b=f['raw_end']
        run=next(r for r in s.runs[rid] if r[4] is None and r[2]<=a and b<=r[3])
        start=run[0]+a-run[2];end=start+b-a;r=s.ref(rid,start,end)
        path=PACKAGE/'reports/rules-v3-work/page-0303.png' if pn==303 else BASE/f'ocr-structure-review-20260924/full-audit-e/page-{pn:04d}-geometry.png'
        evidence={'file':path.relative_to(ROOT).as_posix(),'sha256':sha(path)}
        if pn==303:
            assert len([x for x in findings if x['pdf_page']==303])==8
            for row in boxes:
                row['context_refs']=[t for t in row['context_refs'] if not(t['record_id']==rid and start<=t['start'] and t['end']<=end)]
                assert not any(t['record_id']==rid and start<=t['start'] and t['end']<=end for t in row['body_refs'])
                if row['key']=='P0303:question:E3':
                    row['metadata'].update(condition_link_basis='NO_LOCAL_CONDITION_ON_RENDERED_PDF',condition_box=None)
            disps.append({'source':r,'status':'EXCLUDED_NON_TEXT','reason':'NATIVE_TEXT_COVERED_BY_WHITE_GRAPHICS_NOT_VISIBLE_IN_PDF',
                          'rule':'V6_VISIBLE_SOURCE_AUTHORITY','evidence':evidence})
            log.append({**f,'decision':'EXCLUDE_HIDDEN_NATIVE_TEXT','review':'CODEX_PDF_VISUAL_REVIEW','evidence':evidence})
        else:
            box={280:[444,689,536,699],716:[250,108,299,121],854:[82,530,99,539]}[pn]
            regions.append({'name':f'visible-native-{pn}-{start}','record_id':rid,'pdf_page':pn,'start':start,'end':end,
                            'text':r['text'],'bbox':box,'review':'CODEX_PDF_LAYOUT_REVIEW','evidence':evidence,
                            'coordinate_note':'Text is visible at this location; original native bbox missed its printed pixels.'})
            log.append({**f,'decision':'RETAIN_TEXT_REMAP_TO_VISIBLE_REGION','visible_bbox':box,'evidence':evidence})
    write_jsonl(rules/'box-units.jsonl',boxes);write_jsonl(rules/'box-dispositions.jsonl',disps);write_jsonl(rules/'source-regions.jsonl',regions)
    write_json(rules/'visibility-decisions.json',{'findings':log,'hidden_lines_excluded':8,'shifted_lines_retained':3,
               'zero_ink_is_not_automatic_deletion':True})
    print({'excluded_hidden_lines':8,'retained_remapped_lines':3})

if __name__=='__main__':main()
