"""Freeze visually reviewed decisions and replayable, source-bound patches.

This program replays recorded decisions; it performs no LLM/OCR inference.
"""
from __future__ import annotations
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import pymupdf
import correct_extraction as io
from audit_whole_manual import line_positions, overlap
from review557_decisions import DECISIONS

REVIEW = io.BASE / 'review-557'
PARENT = io.BASE / 'corrections/batch-003/correction-log.json'


def locate_edit(row, spec, pages, by_id):
    layer = spec['layer']; rid = f"P{row['pdf_page']:04d}:{layer}"
    record = by_id[rid]
    if 'before_text' in spec:
        before = spec['before_text']
        assert record['text'].count(before) == 1, ('explicit anchor ambiguous', row['id'])
        start = record['text'].index(before)
    elif layer == 'native':
        before = row['native']; start = row['offset']
    else:
        before = row['ocr']
        matches = [(off, line) for off, line in line_positions(pages[row['pdf_page']-1], layer)
                   if line['text'] == before]
        matches = [(off,line) for off,line in matches
                   if overlap(row['bbox'],line['bbox'])[0] >= .7 and overlap(row['bbox'],line['bbox'])[1] >= .55]
        assert len(matches) == 1, ('OCR coordinate match not unique', row['id'],len(matches))
        start = matches[0][0]
    assert record['text'][start:start+len(before)] == before, ('source mismatch',row['id'])
    after = spec.get('text')
    if after == '@native':
        after = row['native']
    if 'leading_bullet' in spec:
        assert before[0] in spec['leading_bullet'], ('unexpected list marker',row['id'],before)
        after = '• '+before[1:].lstrip(' ')
    elif after is None:
        after = before
        for old,new in spec['replacements']:
            after = after.replace(old,new)
    assert before != after, ('no changed characters',row['id'],before,spec)
    # Record the smallest contiguous changed span, retaining exact anchors above.
    left = 0
    while left < min(len(before),len(after)) and before[left] == after[left]:
        left += 1
    right = 0
    while right < min(len(before)-left,len(after)-left) and before[-1-right] == after[-1-right]:
        right += 1
    end = len(before)-right; aend = len(after)-right
    # Core replay requires a nonempty before anchor even for a pure insertion.
    if left == end:
        if left > 0:
            left -= 1
        else:
            end += 1; aend += 1
    return dict(record_id=rid, pdf_page=row['pdf_page'], start=start+left,end=start+end,
                before=before[left:end], after=after[left:aend], bbox=row['bbox'],
                render_clip=spec.get('render_clip',row['render_clip']))


def plan():
    rows = io.load_records(REVIEW/'candidates.jsonl')
    assert len(rows)==557 and set(DECISIONS)==set(range(1,558))
    assert not any(d['category']=='DETAIL_REVIEW' for d in DECISIONS.values())
    parent=json.loads(PARENT.read_text(encoding='utf-8'))
    records=io.source_records(io.check_inputs(parent)); by_id={r['id']:r for r in records}
    pages=io.load_records(io.ROOT/parent['inputs']['pages']['path'])
    corrections=[]; decisions=[]; errors=[]; seen={}
    for serial,row in enumerate(rows,1):
        d=copy.deepcopy(DECISIONS[serial]); ids=[]
        for spec in d.pop('edits'):
            try:
                patch=locate_edit(row,spec,pages,by_id)
                key=(patch['record_id'],patch['start'],patch['end'],patch['after'])
                if key in seen:
                    ids.append(seen[key]); continue
                for previous in parent['corrections']+corrections:
                    if previous['record_id']==patch['record_id'] and max(previous['start'],patch['start']) < min(previous['end'],patch['end']):
                        raise ValueError(('overlapping patch',row['id'],previous['id'],patch))
                cid=f'FIX-{111+len(corrections):04d}'
                patch.update(id=cid, reason=d['reason'], source_check='CODEX_PDF_VISUAL_CHECK',
                             human_review='NOT_PERFORMED',candidate_id=row['id'],serial=serial)
                corrections.append(patch); seen[key]=cid; ids.append(cid)
            except Exception as exc:
                errors.append({'serial':serial,'candidate_id':row['id'],'error':str(exc)})
        decisions.append({**row,**d,'serial':serial,'status':'SOURCE_REVIEWED',
                          'correction_ids':ids,'source_check':'CODEX_PDF_VISUAL_CHECK',
                          'human_review':'NOT_PERFORMED','in_scope':pages[row['pdf_page']-1]['in_scope']})
    result={'candidate_count':557,'reviewed_count':len(decisions),
            'categories':dict(Counter(d['category'] for d in decisions)),
            'proposed_patches':len(corrections),'errors':errors}
    (REVIEW/'preflight.json').write_bytes(io.json_bytes(result))
    if errors:
        print(json.dumps(result,ensure_ascii=False));return None
    return parent,records,corrections,decisions,result


def build(freeze=False):
    planned=plan()
    if planned is None:
        raise SystemExit(1)
    ledger,records,corrections,decisions,result=planned
    if not freeze:
        print(json.dumps(result,ensure_ascii=False));return
    out=io.BASE/'corrections/batch-004'
    if out.exists():
        raise ValueError('Frozen batch exists; do not overwrite')
    out.mkdir(parents=True)
    for patch in ledger['corrections']:
        dest=out/patch['evidence_crop'];dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes((PARENT.parent/patch['evidence_crop']).read_bytes())
    with pymupdf.open(io.ROOT/ledger['inputs']['pdf']['path']) as pdf:
        for patch in corrections:
            rel=f"evidence/{patch['id']}.png"
            pdf[patch['pdf_page']-1].get_pixmap(dpi=180,alpha=False,clip=pymupdf.Rect(patch['render_clip'])).save(out/rel)
            patch.update(evidence_crop=rel,evidence_sha256=io.sha(out/rel))
    ledger['corrections']+=corrections
    ledger['batch']='batch-004-557-source-review'
    ledger['parent']={'path':PARENT.relative_to(io.ROOT).as_posix(),'sha256':io.sha(PARENT),'preserved_corrections':110}
    ledger['selection']={'frozen_candidate_list':(REVIEW/'candidates.jsonl').relative_to(io.ROOT).as_posix(),
                         'sha256':io.sha(REVIEW/'candidates.jsonl'),'reviewed':557,
                         'evaluated_questions_read':False,'categories':result['categories']}
    ledger['remaining_review']=['These 557 alignments have source-based dispositions. This is not a character-level certification of all 890 pages.',
                                'Unadopted cross-region OCR remains as audit evidence, not as a prose source.',
                                'PDF 118 Metal particles are is incomplete in the source and is not completed by inference.']
    io.validate_ledger(records,ledger)
    (out/'correction-log.json').write_bytes(io.json_bytes(ledger))
    (REVIEW/'decisions.jsonl').write_bytes(io.records_bytes(decisions))
    (REVIEW/'freeze.json').write_bytes(io.json_bytes({**result,'ledger_sha256':io.sha(out/'correction-log.json'),
        'decision_file_sha256':io.sha(REVIEW/'decisions.jsonl'),'decision_program_sha256':io.sha(io.BASE/'review557_decisions.py'),
        'builder_sha256':io.sha(__file__),'cumulative_corrections':len(ledger['corrections'])}))
    print(json.dumps({**result,'cumulative_corrections':len(ledger['corrections'])},ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--freeze',action='store_true')
    build(ap.parse_args().freeze)
