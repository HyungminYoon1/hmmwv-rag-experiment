"""Record the final repair scope, PDF cell occupancy, and source-bound delta."""
from collections import Counter
import pymupdf
from corpus.common import BASE, ROOT, PACKAGE, read_json, read_jsonl, write_json, write_jsonl, sha


def main():
    output=PACKAGE/'reports/rules-v5-work'
    for name,count in [('tests.txt',52),('correction-tests.txt',13)]:
        log=(output/name).read_text(encoding='utf-8')
        assert f'Ran {count} tests' in log and log.rstrip().endswith('OK') and 'skipped' not in log
    before=BASE/'output/corpus-v4-rules-c';after=BASE/'output/corpus-v5-rules-c'
    old=read_jsonl(before/'corpus_units.jsonl');new=read_jsonl(after/'corpus_units.jsonl')
    config=read_json(after/'config.json');rules=PACKAGE/config['rules_path']
    regions=read_json(BASE/'corrections/batch-009/source-regions.json')
    source={r['id']:r['text'] for r in read_jsonl(ROOT/config['corrected_source']/'units-corrected.jsonl')}
    checks=[]
    with pymupdf.open(ROOT/config['source_pdf']) as pdf:
        for r in regions:
            rect=pymupdf.Rect(r['bbox']);page=pdf[r['pdf_page']-1]
            assert page.rect.contains(rect) and source[r['record_id']][r['start']:r['end']]==r['text']
        for row in read_jsonl(rules/'manual-table-units.jsonl'):
            if not row['metadata'].get('cell_occupancy_checked_against_pdf'):continue
            for field in row['fields']:
                ref=field['refs'][0];b=ref['bbox']
                clip=pymupdf.Rect(b[0]+1.5,b[1]+1.5,b[2]-1.5,b[3]-1.5)
                pix=pdf[ref['pdf_page']-1].get_pixmap(clip=clip,dpi=144,colorspace=pymupdf.csGRAY,alpha=False)
                dark=sum(v<170 for v in pix.samples)
                assert dark>=10,(row['key'],field['name'],'No visible source marks')
                checks.append({'key':row['key'],'field':field['name'],'bbox':b,'dark_pixels':dark,
                               'literal':field['text'],'review':'PDF_LITERAL_CELL_CHECKED',
                               'occupancy_is_not_a_text_accuracy_test':True})
    assert len(checks)==74
    write_json(output/'table-cell-source-checks.json',{'status':'PASS','cells_checked':len(checks),
        'reviewed_regions_checked':len(regions),'cells':checks,
        'scope':'Only the four repaired tables; not all tables in the manual'})
    reviews=read_jsonl(after/'review_queue.jsonl');ledger=read_jsonl(after/'selection_ledger.jsonl')
    perpage=[]
    for pn in [408,474,502,547,574,575,612,613,828,829]:
        old_units=[r for r in old if pn in r['pdf_pages']]
        new_units=[r for r in new if pn in r['pdf_pages']]
        pending=[r for r in ledger if r['pdf_page']==pn and r['status']=='NEEDS_REVIEW']
        perpage.append({'pdf_page':pn,'old_units':old_units,'new_units':new_units,
            'remaining_review_categories':dict(Counter(r['code'] for r in reviews if r['pdf_page']==pn)),
            'remaining_selection_spans':len(pending),'remaining_selection_characters':sum(len(r['text']) for r in pending)})
    write_jsonl(output/'page-comparison.jsonl',perpage)
    comparison=read_json(PACKAGE/'reports/rules-v5-final-comparison/comparison.json')
    audit=read_json(after/'audit.json'); summary=read_json(after/'build_summary.json')
    record={
        'status':'REPAIR_AND_RECHUNK_COMPLETE_REVIEW_REMAINS',
        'active_source':config['corrected_source'],'active_rules':config['rules_path'],
        'active_corpus':after.relative_to(ROOT).as_posix(),
        'corpus_replica':'preprocessing/output/corpus-v5-rules-d',
        'correction_ledger':config['correction_ledger'],
        'corrected_pdf_pages':[408,474,502,547,574,575,612,613,828,829],
        'original_confirmed_case_groups':7,'related_pages':[574,613,828],
        'new_effective_corrections':10,'cumulative_corrections':408,
        'page_613_scope':'Only two test cards corrected. Diagram OCR retained as pending source, not indexed as normal prose.',
        'reviewed_source_regions':len(regions),'table_rows':23,'table_cells':74,'explicit_flow_links':26,
        'source_pdf_sha256':sha(ROOT/config['source_pdf']),
        'intermediate_outputs':['corrected-v8-a','corpus-v5-rules-a','corpus/rules/v5','corrections/batch-008'],
        'intermediate_reason':'Enlarged PDF check found printed wound. batch-009 preserves that spelling; batch-008 is retained as superseded evidence.',
        'source_issues_preserved':['P0408_MISSING_TOLERANCE_NUMBER','P0612_PRINTED_WOUND'],
        'mechanical_checks':audit['checks'],'mechanical_status':audit['mechanical_status'],
        'scope_pages':summary['scope_pages'],'chunks':summary['chunks'],'units':summary['units'],
        'max_chunk_tokens':summary['max_chunk_tokens'],'chunk_failures':summary['chunk_failures'],
        'remaining_reviews':audit['review_count'],'remaining_selection_spans':audit['pending_selection_spans'],
        'remaining_representation_destinations':audit['pending_representation_destinations'],
        'previous_inputs_preserved':comparison['previous_inputs_preserved'],
        'previous_input_count':comparison['previous_input_count'],
        'actual_delta_diff_hunks':comparison['actual_delta_diff_hunks'],
        'all_source_changes_match_ledger':comparison['all_source_changes_match_ledger'],
        'replica_files':len(comparison['replica_files']),
        'deterministic_replica':comparison['deterministic_replica'],
        'tests':{'corpus':52,'correction_audit':13,'skipped':0,'status':'PASS',
                 'logs':{n:sha(output/n) for n in ['tests.txt','correction-tests.txt']}},
        'full_manual_semantic_review_complete':False,'automatic_approval_extended_to_similar_pages':False,
        'corpus_ready_for_index':False,'evaluation_questions_read':False,'paper_modified':False,
        'replay_invokes_llm':False,'human_source_review':'NOT_PERFORMED',
        'next_scope':['Remaining general OCR mixed regions and flow contexts',
                      'Special free flowcharts 534-546, test panels 832/841/848, GO-chain 860-863',
                      'Independent samples and all affected pages before certifying any generalized rule']}
    write_json(output/'execution.json',record)
    print({k:record[k] for k in ['status','table_rows','table_cells','explicit_flow_links','chunks','mechanical_status']})


if __name__=='__main__':main()
