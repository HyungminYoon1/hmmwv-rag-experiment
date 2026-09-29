"""Export the 557 review dispositions, exact source references and table rows.

Only source spans and source-layout relations are projected here. No language
model is invoked, and this sidecar is not a finished retrieval corpus.
"""
from __future__ import annotations
import argparse
from collections import Counter
import contextlib
import copy
import difflib
import html
import io as stdio
import json
from pathlib import Path
import pymupdf
import correct_extraction as io
from audit_whole_manual import line_positions, overlap
import build_reviewed_structures as previous
from verify_corrections import audit_changes

REVIEW=io.BASE/'review-557'


def build(out):
    ledgerpath=io.BASE/'corrections/batch-004/correction-log.json'
    ledger=json.loads(ledgerpath.read_text(encoding='utf-8'))
    pages=io.load_records(io.check_inputs(ledger))
    raw={r['id']:r for r in io.source_records(io.check_inputs(ledger))}
    corrected=io.load_records(io.BASE/'output/corrected-v4-a/units-corrected.jsonl')
    fixed={r['id']:r for r in corrected}
    decisions=io.load_records(REVIEW/'decisions.jsonl')
    assert len(decisions)==557 and all(r['status']=='SOURCE_REVIEWED' for r in decisions)
    by_candidate={r['id']:r for r in decisions}
    patches=ledger['corrections']

    def ref(pn,layer,start,end,bbox):
        rid=f'P{pn:04d}:{layer}'; original_start,original_end=start,end
        # An edit can join an incorrectly split native heading. In that case,
        # keep the complete corrected lines instead of slicing through it.
        relevant=[p for p in patches if p['record_id']==rid]
        for p in relevant:
            if max(start,p['start']) < min(end,p['end']):
                start=min(start,p['start']);end=max(end,p['end'])
        if (start,end)!=(original_start,original_end):
            text=raw[rid]['text'];start=text.rfind('\n',0,start)+1
            stop=text.find('\n',end);end=len(text) if stop<0 else stop
        left=start+sum(len(p['after'])-len(p['before']) for p in relevant if p['end']<=start)
        right=end+sum(len(p['after'])-len(p['before']) for p in relevant if p['end']<=end)
        assert 0<=left<=right<=len(fixed[rid]['text'])
        return {'record_id':rid,'start':left,'end':right,'text':fixed[rid]['text'][left:right],
                'raw_start':start,'raw_end':end,'bbox':bbox}

    def line_ref(pn,off,line,layer='native'):
        return ref(pn,layer,off,off+len(line['text']),line['bbox'])

    def source_lines(pn):
        return list(line_positions(pages[pn-1],'native'))

    def select(pn,predicate):
        return [line_ref(pn,off,line) for off,line in source_lines(pn) if predicate(line)]

    def cell(refs):
        assert refs
        return {'text':'\n'.join(r['text'] for r in refs),'source_spans':refs}

    # Reuse the already reviewed PMCS/image-table projection, with v4 strings.
    previous.SOURCE_ISSUES=copy.deepcopy(previous.SOURCE_ISSUES)
    previous.SOURCE_ISSUES=[x for x in previous.SOURCE_ISSUES if x[1]!='TRUNCATED_ITEM32']
    previous.SOURCE_ISSUES += [
        (118,'TRUNCATED_ITEM32','Metal particles are만 원문에서 불완전하다. 117~119쪽 화면 및 PDF 문자층을 확인했고, 이 서술어 뒤 내용은 없다. Change fluid every 12,000 miles는 그 자체로 성립하는 명령문이므로 끊긴 문장으로 단정한 이전 판정을 정정한다.','SOURCE_INCOMPLETE_NO_INFERRED_COMPLETION'),
        (54,'OVERPRINTED_PLATES','제목 PLA/TES의 A와 T가 같은 기준선에서 겹친다. PDF 문자 순서와 화면을 함께 확인해 공백과 잘못 나뉜 행만 복원했다.','SOURCE_TYPOGRAPHY_WITH_VERIFIED_TEXT'),
        (73,'OVERPRINTED_ALTERNATOR','제목 L/T가 겹친다. 내부 문자와 확대 화면을 함께 대조했다.','SOURCE_TYPOGRAPHY_WITH_VERIFIED_TEXT'),
        (74,'OVERPRINTED_ALTERNATOR','제목 L/T가 겹친다. 내부 문자와 확대 화면을 함께 대조했다.','SOURCE_TYPOGRAPHY_WITH_VERIFIED_TEXT'),
        (208,'TEAT_IN_PROSE','원문 To teat for air leaks의 teat는 그대로 보존했다.','SOURCE_TEXT_PRESERVED'),
        (526,'VOITS','4.9 voits는 원문 표기다. 목록 기호만 보정했다.','SOURCE_TEXT_PRESERVED'),
        (527,'109_MINUTES','109 minutes는 원문에도 그렇게 인쇄되어 있다. 1.09 등으로 추정 변경하지 않았다.','SOURCE_TEXT_PRESERVED'),
        (830,'TEST_NUMBER_39','DC VOLTAGE 0 TO 45 VOLTS의 TEST #는 원문 표의 39를 유지했다.','SOURCE_IDENTIFIER_PRESERVED'),
        (848,'DA_ENERGIZED','da-energized는 원문에 보이는 표현이므로 de-energized로 바꾸지 않았다.','SOURCE_TEXT_PRESERVED'),
    ]
    with contextlib.redirect_stdout(stdio.StringIO()):
        previous.build(out,revision=4)
    pmcs=io.load_records(out/'pmcs-structure.jsonl')

    # Four text tables: every field is made of exact corrected native spans.
    tables=[]
    for pn in (272,276):
        ls=source_lines(pn)
        header=next(l for _,l in ls if l['text']=='ENGINE RPM' and l['bbox'][0]<150)
        divider=220 if pn==272 else 150
        headers=['ENGINE RPM','APPROXIMATE OIL PRESSURE']
        names=['STOP','6.2L IDLE (650 ± 25)','6.5L IDLE (700 ± 25)','6.5L DETUNED','2000']
        rows=[]
        for label in names:
            off,line=next((o,l) for o,l in ls if l['text']==label)
            left=[line_ref(pn,off,line)]
            y=line['bbox'][1]
            if label=='6.5L DETUNED':
                o,l=next((o,l) for o,l in ls if l['text']=='IDLE (700 ± 25)')
                left.append(line_ref(pn,o,l));y=l['bbox'][1]
            right=select(pn,lambda l:l['bbox'][0]>divider and abs(l['bbox'][1]-y)<1)
            assert len(right)==1
            rows.append({'ENGINE RPM':cell(left),'APPROXIMATE OIL PRESSURE':cell(right)})
        tables.append({'id':f'P{pn:04d}:oil-pressure','pdf_page':pn,'headers':headers,'rows':rows,
                       'source_check':'CODEX_PDF_VISUAL_CHECK','human_review':'NOT_PERFORMED'})
    pn=830;ls=source_lines(pn);rows=[]
    name_lines=[(off,l) for off,l in ls if 243<l['bbox'][1]<446 and l['bbox'][0]<200]
    assert len(name_lines)==19
    for off,line in name_lines:
        y=line['bbox'][1]
        if line['text'].endswith('  91'):
            cut=line['text'].rindex('  91')
            title=[ref(pn,'native',off,off+cut,line['bbox'])]
            number=[ref(pn,'native',off+cut+2,off+len(line['text']),line['bbox'])]
        else:
            title=[line_ref(pn,off,line)]
            number=select(pn,lambda l:350<l['bbox'][0]<430 and abs(l['bbox'][1]-y)<1)
        page=select(pn,lambda l:l['bbox'][0]>470 and abs(l['bbox'][1]-y)<1)
        assert len(number)==len(page)==1
        rows.append({'TEST NAME':cell(title),'TEST #':cell(number),'PAGE #':cell(page)})
    tables.append({'id':'P0830:test-index','pdf_page':830,'headers':['TEST NAME','TEST #','PAGE #'],'rows':rows,
                   'source_check':'CODEX_PDF_VISUAL_CHECK','human_review':'NOT_PERFORMED'})
    pn=854;rows=[]
    for low,high in [(485,524),(524,574),(574,612),(612,652)]:
        values=select(pn,lambda l:low<=l['bbox'][1]<high and l['bbox'][0]<150)
        desc=select(pn,lambda l:low<=l['bbox'][1]<high and l['bbox'][0]>150)
        rows.append({'VTM Readout':cell(values),'Interpretation':cell(desc)})
    tables.append({'id':'P0854:status-readouts','pdf_page':854,'headers':['VTM Readout','Interpretation'],'rows':rows,
                   'source_check':'CODEX_PDF_VISUAL_CHECK','human_review':'NOT_PERFORMED'})

    rules=[]
    for d in decisions:
        pn=d['pdf_page'];category=d['category']
        native=ref(pn,'native',d['offset'],d['offset']+len(d['native']),d['bbox'])
        matches=[(off,l) for off,l in line_positions(pages[pn-1],'ocr') if l['text']==d['ocr']
                 and overlap(d['bbox'],l['bbox'])[0]>=.7 and overlap(d['bbox'],l['bbox'])[1]>=.55]
        assert len(matches)==1,(d['id'],matches)
        off,ocrline=matches[0];ocr=line_ref(pn,off,ocrline,'ocr')
        rule={'candidate_id':d['id'],'serial':d['serial'],'pdf_page':pn,'in_scope':d['in_scope'],
              'category':category,'native_span':native,'ocr_span':ocr,
              'ocr_allowed_as_single_prose_span':True,'preferred_layer_for_aligned_span':'native',
              'scope':'THIS_ALIGNED_REGION_ONLY_NOT_THE_ENTIRE_PAGE','deduplicate_alternative_layers':True,
              'source_crop':(REVIEW/d['source_crop']).relative_to(io.ROOT).as_posix(),
              'source_crop_sha256':d['crop_sha256'],'correction_ids':d['correction_ids'],
              'source_check':d['source_check'],'human_review':d['human_review']}
        if category=='IMAGE_TEXT_WITH_NATIVE_REFERENCE':
            rule['preferred_layer_for_aligned_span']='ocr'
            rule['handling']='USE_CHECKED_OCR_REGION_LINK_NATIVE_REFERENCE_DO_NOT_DROP_IMAGE_PROSE'
        elif category=='SEPARATE_NATIVE_LABEL':
            b=ocrline['bbox']
            refs=select(pn,lambda l:overlap(b,l['bbox'])[1]>=.45 and overlap(b,l['bbox'])[0]>=.3)
            refs.sort(key=lambda r:r['bbox'][0])
            rule['native_adjacent_spans']=refs
            rule['handling']='PRESERVE_LINKED_NATIVE_LABELS_AND_LINE_BOUNDARIES_NO_DUPLICATE_INSERTION'
        elif category=='TABLE_COLUMN_MERGE':
            rule['ocr_allowed_as_single_prose_span']=False
            links=[]
            for row in pmcs:
                if row['pdf_page']!=pn:continue
                for field,b in row['source_field_bboxes'].items():
                    if b and overlap(d['bbox'],b)[0]>.05 and overlap(d['bbox'],b)[1]>.1:
                        links.append({'row_id':row['row_id'],'field':field,'record_id':row['row_id']+':'+field})
            assert links,(d['id'],'no PMCS cell')
            rule['pmcs_cell_refs']=links;rule['handling']='USE_VERIFIED_PMCS_CELLS_KEEP_COLUMNS_SEPARATE'
        elif category=='TABLE_ROW_ALIGNMENT':
            rule['ocr_allowed_as_single_prose_span']=False
            rule['table_id']=next(t['id'] for t in tables if t['pdf_page']==pn)
            rule['handling']='USE_SOURCE_LINKED_TABLE_ROWS'
        elif category=='OCR_CROSS_REGION_MERGE':
            rule['ocr_allowed_as_single_prose_span']=False
            rule['handling']='KEEP_NATIVE_REGION_KEEP_IMAGE_SEPARATE_DO_NOT_CONCATENATE_MIXED_OCR'
        elif category=='FLOWCHART_BRANCH':
            rule['ocr_allowed_as_single_prose_span']=False
            rule['branch_label']='No';rule['target_text']=native['text']
            rule['handling']='KEEP_BRANCH_LABEL_AND_TARGET_AS_DIAGRAM_RELATION_NOT_PROSE'
        elif category=='FIGURE_CALLOUT':
            rule['callout']=d['callout'];rule['handling']='KEEP_CALLOUT_METADATA_SEPARATE_FROM_PROSE'
        else:
            rule['handling']='USE_CORRECTED_SOURCE_SPAN_NO_PAGE_WIDE_LAYER_REPLACEMENT'
        rules.append(rule)

    # A source fragment remains in audit text but cannot be sufficient answer
    # evidence. Complete cautions on this page are not excluded wholesale.
    incomplete=[]
    for rid,record in fixed.items():
        if record['pdf_page']!=118:continue
        phrase='Metal particles are'
        if phrase in record['text']:
            start=record['text'].index(phrase)
            incomplete.append({'record_id':rid,'start':start,'end':start+len(phrase),'text':phrase,
                               'status':'SOURCE_INCOMPLETE','allow_as_sufficient_answer_evidence':False,
                               'handling':'KEEP_LITERAL_TEXT_DO_NOT_COMPLETE_BY_INFERENCE'})
    assert len(incomplete)==3 # native, OCR, and the corresponding PMCS cell.
    issue={'id':'PDF118_ITEM32_SOURCE_REVIEW','pdf_page':118,'printed_page':'2-27',
           'source_pages_compared':[117,118,119],
           'confirmed_incomplete_text':'Metal particles are','affected_spans':incomplete,
           'source_text_preserved':'Change fluid every 12,000 miles',
           'previous_assessment_corrected':'The imperative Change fluid every 12,000 miles is not established to be truncated.',
           'added_completion':False,'external_edition_substituted':False,
           'human_review':'NOT_PERFORMED','source_check':'CODEX_PDF_VISUAL_CHECK'}
    with pymupdf.open(io.ROOT/ledger['inputs']['pdf']['path']) as pdf:
        traces=[]
        for pn in (54,73,74):
            chars=[]
            for block in pdf[pn-1].get_text('rawdict')['blocks']:
                for line in block.get('lines',[]):
                    for span in line['spans']:
                        chars += [c for c in span['chars'] if 75<c['origin'][1]<110]
            traces.append({'pdf_page':pn,'characters':chars})
        issue['right_column_native_text']=pdf[117].get_text('text',clip=pymupdf.Rect(426,490,556,725)).strip()
        assert issue['right_column_native_text']=='Metal particles are'
        issue['full_page_native_text']=pdf[117].get_text()
        issue['next_page_start']=pdf[118].get_text()[:350]

    # Compare v3 with v4 in v3 coordinates, independently of replacement code.
    parent=json.loads((io.BASE/'corrections/batch-003/correction-log.json').read_text(encoding='utf-8'))
    assert patches[:110]==parent['corrections']
    delta=copy.deepcopy(patches[110:])
    for p in delta:
        shift=sum(len(q['after'])-len(q['before']) for q in parent['corrections'] if q['record_id']==p['record_id'] and q['end']<=p['start'])
        p['start']+=shift;p['end']+=shift
    old=io.load_records(io.BASE/'output/corrected-v3-a/units-corrected.jsonl')
    errors,diffs=audit_changes(old,corrected,delta)
    assert not errors,errors
    comparison={'status':'PASS','from':'corrected-v3-a','to':'corrected-v4-a',
                'additional_corrections':len(delta),'changed_records':len({d['record_id'] for d in diffs}),
                'changed_pages':sorted({d['pdf_page'] for d in diffs}),'actual_diff_hunks':len(diffs),
                'unrecorded_changes':0,'errors':errors,'actual_diffs':diffs}
    oldalign=io.load_records(out/'alignment-triage.jsonl')
    for row in oldalign:
        if row['id'] in by_candidate:
            reviewed=by_candidate[row['id']]
            row.update(status='SOURCE_REVIEWED_'+reviewed['category'],category=reviewed['category'],
                       correction_ids=reviewed['correction_ids'],reason=reviewed['reason'],
                       review_source='preprocessing/review-557/decisions.jsonl')
    assert len(oldalign)==801 and not any(r['status']=='UNRESOLVED_LAYER_DISAGREEMENT_NOT_AUTO_REPLACED' for r in oldalign)
    files={'alignment-triage.jsonl':oldalign,'review557-adoption-rules.jsonl':rules,
           'review557-tables.jsonl':tables,'overprinted-title-character-traces.jsonl':traces}
    for name,rows in files.items():(out/name).write_bytes(io.records_bytes(rows))
    (out/'source118-review.json').write_bytes(io.json_bytes(issue))
    (out/'v3-to-v4-comparison.json').write_bytes(io.json_bytes(comparison))
    diff=''.join(difflib.unified_diff(io.text_export(old).decode('utf-8').splitlines(True),
                                    io.text_export(corrected).decode('utf-8').splitlines(True),
                                    fromfile='corrected-v3-a/Codex_보정본.txt',tofile='corrected-v4-a/Codex_보정본.txt',n=2))
    (out/'v3-to-v4.diff').write_bytes(io.encoded(diff))
    # Compact browsing aid; program audits remain separate from source review.
    articles=[]
    for d,r in zip(decisions,rules):
        crop='../../../'+r['source_crop']
        articles.append(f'<article><h2>{d["serial"]:03d} · {d["id"]} · PDF {d["pdf_page"]}</h2>'
                        f'<p><b>{d["category"]}</b> {html.escape(d["reason"])}</p>'
                        f'<img loading="lazy" src="{html.escape(crop)}" alt="원본 PDF 발췌">'
                        f'<pre>native: {html.escape(d["native"])}\nOCR: {html.escape(d["ocr"])}</pre>'
                        f'<p>수정 기록: {", ".join(d["correction_ids"]) or "문자 수정 없음; 구조·채택 규칙 기록"}</p></article>')
    (out/'557건_검토내역.html').write_bytes(io.encoded('<!doctype html><html lang="ko"><meta charset="utf-8">'
        '<title>557건 원문 대조 결과</title><style>body{font:16px/1.7 system-ui;max-width:1200px;margin:30px auto;padding:20px;background:#f4f6f8}article{background:white;padding:20px;margin:20px 0}img{max-width:100%;height:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>'
        '<h1>557건 원문 대조 결과</h1><p>Codex가 원본 PDF 발췌를 확인하고 기록한 판정입니다. 사람의 검토와 구분합니다. 원문 자체의 표현은 추정 교정하지 않았습니다. 문자 수정과 구조 판정을 함께 기록합니다.</p>'+''.join(articles)+'</html>'))
    audit=json.loads((out/'structure-audit.json').read_text(encoding='utf-8'))
    audit.update(alignment_dispositions=dict(Counter(r['status'] for r in oldalign)),
                 reviewed_557=len(decisions),reviewed_557_pages=len({d['pdf_page'] for d in decisions}),
                 unreviewed_within_557=0,review557_categories=dict(Counter(r['category'] for r in decisions)),
                 added_table_count=4,added_table_rows=sum(len(t['rows']) for t in tables),
                 source_incomplete_spans=len(incomplete),
                 added_text_corrections=len(delta),alignments_with_text_corrections=sum(bool(d['correction_ids']) for d in decisions),
                 decision_file_sha256=io.sha(REVIEW/'decisions.jsonl'),
                 base_program_sha256=io.sha(previous.__file__),program_sha256=io.sha(__file__))
    (out/'structure-audit.json').write_bytes(io.json_bytes(audit))
    (out/'manifest.json').write_bytes(io.json_bytes({'files':{p.name:io.sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!='manifest.json'}}))
    print(json.dumps({k:audit[k] for k in ['status','reviewed_557','unreviewed_within_557','added_text_corrections','alignments_with_text_corrections','added_table_rows']},ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    build(ap.parse_args().output.resolve())
