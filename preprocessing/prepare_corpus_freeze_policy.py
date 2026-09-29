"""Record scope decisions after source corrections and the open-queue audit."""
from collections import Counter
from corpus.common import *
from corpus.review_resolution import NORMAL_CODES


def main():
    rules=PACKAGE/'rules/v6';target=rules/'review-policy.json'
    if target.exists():raise ValueError('Already approved; use a new policy version')
    gate=BASE/'output/corpus-v6-gate-check-b';a=read_json(gate/'audit.json')
    assert a['mechanical_status']=='PASS' and not a['errors']
    assert a['pending_selection_spans']==a['pending_representation_destinations']==0
    reviews=read_jsonl(gate/'review_queue.jsonl')
    assert all(r['code'] in NORMAL_CODES and r['unit_key'] and r['source_refs'] for r in reviews)
    sourceaudit=PACKAGE/'reports/corrected-v19-audit.json';assert read_json(sourceaudit)['status']=='PASS'
    replica=PACKAGE/'reports/rules-v6-work/corrected-v19-replica.json';assert read_json(replica)['status']=='PASS'
    # Old relation-review labels record a previous stage. Accept bounded native
    # boxes for the text scope, without claiming a cross-page/arrow interpretation.
    rows=read_jsonl(rules/'box-units.jsonl');native=[]
    for r in rows:
        meta=r['metadata']
        if r.get('review')=='NATIVE_GEOMETRY_PROFILE_WITH_REMAINING_CONTEXT_REVIEW':
            native.append(r['key']);meta['previous_layout_review']=r['review']
            r['review']='BOUNDED_NATIVE_PROFILE_ACCEPTED_FOR_TEXT_SCOPE'
            meta['cross_page_reference_policy']='DO_NOT_INHERIT_UNLESS_EXPLICIT_REVIEWED_CONTRACT'
    write_jsonl(rules/'box-units.jsonl',rows)
    raw=read_json(rules/'node-profile-review.json');unlinked=[]
    retranscribed={147,185,201,219,224,291,390,463,479,674,696,718,742,822}
    for r in raw['results']:
        if r['status']=='LINKED':continue
        unlinked.append({**r,'resolution':('REPLACED_BY_PDF_TRANSCRIBED_CONTRACTS' if r['pdf_page'] in retranscribed else 'LITERAL_PANELS_RETAINED_WITHOUT_INFERRED_RELATION'),
                         'graphic_relations':'PDF_ONLY_UNLESS_EXPLICIT_REVIEWED_LINK'})
    resolution={'scope':'TEXT_ONLY_CHAPTERS_1_AND_2','pages':[31,863],
      'policy':'Keep visible prose, tables and literal panels. Do not infer a relation between unlinked boxes.',
      'native_contracts_accepted':native,'unlinked_profile_questions':unlinked,
      'gate_audit':{'file':(gate/'audit.json').relative_to(ROOT).as_posix(),'sha256':sha(gate/'audit.json')},
      'review_categories':dict(Counter(r['code'] for r in reviews)),
      'source_choice_pending':0,'relation_scope_decided':True,'human_source_review':'NOT_PERFORMED'}
    write_json(rules/'scope-resolution-record.json',resolution)
    files=[sourceaudit,replica,gate/'audit.json',rules/'scope-resolution-record.json',
      rules/'native-boundary-refinement.json',rules/'visibility-decisions.json',rules/'coordinate-preparation.json',
      rules/'test-card-review.json',rules/'condition-panel-end-review.json',rules/'final-text-scope-review.json',
      PACKAGE/'그림과_텍스트_처리원칙.md']
    files += sorted((PACKAGE/'reports/rules-v6-work/final-samples').glob('*.png'))
    files += sorted((PACKAGE/'reports/rules-v6-work/left-panel-ends').glob('*.png'))
    policy={'id':'HMMWV-V6-TEXT-SCOPE-20260925','status':'APPROVED_FOR_TEXT_SCOPE',
      'source_correction_audit':'PASS','pdf_samples_reviewed':True,'normal_codes':sorted(NORMAL_CODES),
      'reviewer':'CODEX','human_source_review':'NOT_PERFORMED','semantic_all_characters_certified':False,
      'closure_basis':{
        'STRUCTURE_BOUNDARY':'Preserve source blocks, columns, headings and independent panels; bounded profile checked on source PDFs.',
        'OCR_REGION_STRUCTURE':'Frozen word coordinates, logged PDF corrections, source-selection audit and source layout samples.',
        'BOX_CONTEXT_REVIEW':'Same printed condition rectangle and same-node panel only; no inferred cross-page context.',
        'FLOW_ANNOTATION_REVIEW':'Literal annotation retained; unverified arrow relations remain PDF-only.'},
      'never_close_as_layout':['LAYER_ALIGNMENT','SELECTION_CONFLICT','CROSS_REGION_TEXT','UNASSIGNED_TEXT','TOKEN_BUDGET'],
      'evidence':[{'file':p.relative_to(ROOT).as_posix(),'sha256':sha(p)} for p in files]}
    write_json(target,policy)
    config=read_json(PACKAGE/'config.json')
    config['additional_inputs']=sorted(set(config['additional_inputs']+[p.relative_to(ROOT).as_posix() for p in files]))
    write_json(PACKAGE/'config.json',config)
    print({'normal_reviews':len(reviews),'native_text_scope_contracts':len(native),'evidence_files':len(files)})


if __name__=='__main__':main()
