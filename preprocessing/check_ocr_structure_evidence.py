"""Check frozen OCR evidence, audit repeatability, and deliberate corruption."""
from collections import Counter
from pathlib import Path
from copy import deepcopy
from corpus.common import BASE, ROOT, SourceStore, read_json, read_jsonl, write_json, sha
import verify_ocr_structure_review as verifier

DEST=BASE/'ocr-structure-review-20260924'


def main():
    left=DEST/'full-audit-e';right=DEST/'full-audit-f'
    names=sorted(p.name for p in left.iterdir() if p.suffix in ('.json','.jsonl'))
    other=sorted(p.name for p in right.iterdir() if p.suffix in ('.json','.jsonl'))
    assert names==other and len(names)==675
    compared=[{'file':n,'sha256':sha(left/n),'replica_sha256':sha(right/n)} for n in names]
    assert all(r['sha256']==r['replica_sha256'] for r in compared)
    write_json(DEST/'repeatability.json',{'status':'PASS','files_compared':len(names),'files':compared,
       'scope':'Frozen coordinate snapshots and PDF geometry; not freshly rerun OCR identity'})
    result=verifier.verify(left);write_json(DEST/'independent-verification.json',result)
    assert result['status']=='PASS',result['errors'][:5]
    original_reader=verifier.read_json
    tests=[]
    for mutation,expected in [('coordinates','WORD_OCR_COORDINATES'),('missing_word','ALL_EXACT_WORDS_PRESENT'),('source_text','REVIEW_SOURCE_TEXT')]:
        def changed_reader(path):
            data=original_reader(path)
            if Path(path)==left/'page-0612.json':
                data=deepcopy(data)
                if mutation=='coordinates':data['words'][0]['bbox'][0]+=9
                elif mutation=='missing_word':data['words'].pop(0)
                elif mutation=='source_text':data['reviews'][0]['source']['text']+=' INSERTED'
            return data
        verifier.read_json=changed_reader
        try:bad=verifier.verify(left)
        finally:verifier.read_json=original_reader
        codes=Counter(e['code'] for e in bad['errors'])
        assert bad['status']=='FAIL' and codes[expected]>0,(mutation,codes)
        tests.append({'mutation':mutation,'status':'PASS','rejected':True,'detected_error_codes':dict(codes)})
    write_json(DEST/'negative-tests.json',{'status':'PASS','disk_files_mutated':False,'tests':tests})

    old={r['pdf_page']:r for r in read_jsonl(BASE/'assets/ocr-full-manual-v2/pages.jsonl')}
    changes=[];edge_normalization=[]
    for row in read_jsonl(left/'page-census.jsonl'):
        pn=row['pdf_page'];capture=read_json(ROOT/row['capture_file'])
        assert old[pn]['raster_sha256']==capture['raster_sha256']
        a=old[pn]['lines'];b=capture['lines']
        fields=[f for f in ('text','bbox','block','line','word_confidences') if [x.get(f) for x in a]!=[x.get(f) for x in b]]
        if fields:
            differences=[{'line_index':i,'before':x['text'],'rerun':y['text'],'bbox':x['bbox']} for i,(x,y) in enumerate(zip(a,b)) if x['text']!=y['text']]
            changes.append({'pdf_page':pn,'different_fields':fields,'line_counts':[len(a),len(b)],'text_differences':differences})
        page=read_json(left/f'page-{pn:04d}.json')
        trimmed=[w for w in page['words'] if w['line_edge_whitespace_removed']]
        if trimmed:edge_normalization.append({'pdf_page':pn,'words':trimmed})
    write_json(DEST/'ocr-rerun-comparison.json',{'pages_compared':671,'raster_hashes_equal':True,
       'pages_with_any_line_field_difference':len(changes),
       'pages_with_text_difference':[r['pdf_page'] for r in changes if 'text' in r['different_fields']],
       'changes':changes,'outer_whitespace_alignment':edge_normalization,
       'new_ocr_adopted':False})

    baseline=read_json(BASE/'backups/condition-ocr-after-20260924-144343/manifest.json')
    prefixes=('preprocessing/output/corrected-v7-a/','preprocessing/output/corpus-v4-rules-c/',
              'preprocessing/corrections/batch-007/','preprocessing/corpus/rules/v4/')
    cfg=SourceStore().config
    exact={cfg['source_pdf'],'preprocessing/corpus/config.json','preprocessing/corpus/inputs.lock.json'}
    checked=[]
    for name,item in baseline['files'].items():
        if name in exact or name.startswith(prefixes):
            actual=sha(ROOT/name);assert actual==item['sha256'],name
            checked.append({'file':name,'sha256':actual})
    assert set(exact).issubset({r['file'] for r in checked})
    write_json(DEST/'baseline-preservation.json',{'status':'PASS','baseline_backup_sha256':baseline['archive_sha256'],
       'files_verified':len(checked),'files':checked,'corpus_or_corrected_source_modified':False})
    print({'status':'PASS','repeatability_files':len(names),'independent_checks':result['checks'],
           'negative_tests':len(tests),'preserved_files':len(checked),'rerun_difference_pages':len(changes)})


if __name__=='__main__':main()
