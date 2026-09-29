"""Preserve a source typo found during enlarged post-transcription review."""
from copy import deepcopy
import json
import correct_extraction as io


def main():
    parent=io.BASE/'corrections/batch-008/correction-log.json'
    out=io.BASE/'corrections/batch-009'
    if out.exists():raise ValueError('Use a new batch')
    ledger=json.loads(parent.read_text(encoding='utf-8'))
    target=next(p for p in ledger['corrections'] if p['id']=='FIX-V8-0612')
    superseded=deepcopy(target)
    assert target['after'].count('No voltage would indicate a')==1
    target['after']=target['after'].replace('No voltage would indicate a','No voltage wound indicate a')
    target['id']='FIX-V9-0612'
    target['reason']+=' 확대 재검토에서 원문 자체의 wound 표기를 확인하여 would로 문법 교정하지 않고 보존했다.'
    out.mkdir();(out/'evidence').mkdir()
    for patch in ledger['corrections']:
        (out/patch['evidence_crop']).write_bytes((parent.parent/patch['evidence_crop']).read_bytes())
    ledger.update(batch='batch-009-preserve-printed-source-typo',
        parent={'path':parent.relative_to(io.ROOT).as_posix(),'sha256':io.sha(parent),
                'preserved_corrections':407,'superseded_corrections':[superseded],
                'replacement_ids':['FIX-V9-0612'],
                'reason':'Post-transcription PDF magnification found printed wound; v8 remains an intermediate record.'})
    io.validate_ledger(io.source_records(io.check_inputs(ledger)),ledger)
    (out/'correction-log.json').write_bytes(io.json_bytes(ledger))
    regions=json.loads((parent.parent/'source-regions.json').read_text(encoding='utf-8'))
    for r in regions:
        if r['pdf_page']==612 and r['name']=='17-reason':
            r['text']=r['text'].replace('No voltage would indicate a','No voltage wound indicate a')
        r['evidence']['file']=r['evidence']['file'].replace('/batch-008/','/batch-009/')
    (out/'source-regions.json').write_bytes(io.json_bytes(regions))
    (out/'table-cell-map.json').write_bytes((parent.parent/'table-cell-map.json').read_bytes())
    print('Preserved 407 patches; superseded the page-612 transcription without altering the PDF or v8 artifacts')


if __name__=='__main__':main()
