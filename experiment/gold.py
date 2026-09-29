"""Build source-reviewed gold without running the evaluated search method."""
from itertools import product
import re
from .io import BASE, ROOT, read_json, read_jsonl, save, sha, text_sha, write_text
from .annotations import GROUPS, QUESTION_GROUPS, ELEMENTS, NOTES, UNANSWERABLE_REFS
from retrieval.common import load_config
from retrieval.source import Corpus

def combinations(values):
    return [[f'C{x:06}' for x in (v if isinstance(v, tuple) else (v,))] for v in values]

def minimum_chunks(evidence):
    if not evidence: return None
    return min(len(set().union(*(set(c) for c in choice)))
               for choice in product(*(e['sufficient_chunk_sets'] for e in evidence)))

def retrieval_score(question, ids):
    if question['type'] == 'unanswerable': return {'status':'N/A_OUT_OF_SCOPE'}
    found = set(ids)
    flags = {e['id']: any(set(combo) <= found for combo in e['sufficient_chunk_sets'])
             for e in question['evidence']}
    return {'status':'OK', 'covered':flags, 'evidence_recall_at_5':sum(flags.values())/len(flags),
            'complete_evidence_at_5':int(all(flags.values()))}

def build():
    corpus = Corpus(load_config())
    source = next((ROOT/'retrieval/benchmarks/holdout-v1').glob('*채점기준.json'))
    original = read_json(source)['questions']
    target = BASE/'gold-v1'
    if (target/'manifest.json').exists():
        raise ValueError('Gold version already exists; create a new version for changes')
    groups = {}
    for key, values in GROUPS.items():
        combos = combinations(values)
        ids = sorted(set(x for c in combos for x in c))
        primary = combos[0]
        groups[key] = {
            'id':key, 'sufficient_chunk_sets':combos,
            'primary_chunks':primary,
            'oracle_text':'\n\n'.join(corpus.by_id[x]['text'] for x in primary),
            'sources':[{k:corpus.by_id[x][k] for k in ('id','unit_id','pdf_pages','printed_pages','text_sha256')} for x in ids],
            'source_group_ids': sorted({corpus.by_id[x]['unit_id'] for x in primary}),
            'codex_pdf_review':'VERIFIED_REQUIRED_FACTS',
            'researcher_direct_review':'PENDING',
        }
    rows=[]
    for q in original:
        groups_q=[groups[key] for key in QUESTION_GROUPS[q['id']]]
        elements=ELEMENTS.get(q['id'],q['required_answer_elements'])
        row={k:q[k] for k in ('id','type','question','answerable_in_scope','topic','missing_information','allowed_partial_answer')}
        row.update({'evidence':groups_q,'required_elements':[{'id':f'{q["id"]}-A{i:02}', 'text':v} for i,v in enumerate(elements,1)],
                    'draft_required_elements':q['required_answer_elements'],
                    'original_locations':q['evidence_groups'],
                    'review_note':NOTES.get(q['id'],''),
                    'researcher_direct_review':'PENDING', 'codex_pdf_review':'VERIFIED_REQUIRED_FACTS',
                    'min_sufficient_chunks':minimum_chunks(groups_q) if q['answerable_in_scope'] else None})
        if q['id'] in UNANSWERABLE_REFS:
            ref=UNANSWERABLE_REFS[q['id']]
            hits=[{'id':c['id'],'pages':c['pdf_pages'],'text':c['text']} for c in corpus.chunks
                  if re.search(r'(?<!\d)'+re.escape(ref)+r'(?![\d.])',c['text'],re.I)]
            save(target/'scope-checks'/f'{q["id"]}.json', {'paragraph':ref,'corpus_wide_reference_matches':hits,
                'reason':'Full referenced maintenance procedure belongs to chapters 3-9 in volume 2. Volume 1 contains references/diagnosis/partial steps, not the complete requested procedure.',
                'checked_source_scope':[31,863],'volume_statement_pdf_page':20,
                'scope_page_is_generation_context':False,'match_search_is_not_by_itself_proof_of_absence':True})
            row['scope_validation']={'pdf_page':20,'paragraph':ref,'scope_check':f'scope-checks/{q["id"]}.json',
                'role':'SCOPE_METADATA_ONLY_NOT_RETRIEVABLE_EVIDENCE'}
        rows.append(row)
    assert len(rows)==60 and len({r['id'] for r in rows})==60
    assert all(r['question']==q['question'] and r['type']==q['type'] for r,q in zip(rows,original))
    assert all(len(r['evidence']) == (1 if r['type']=='single-evidence' else 2) for r in rows if r['type']!='unanswerable')
    assert all(r['min_sufficient_chunks']<=5 for r in rows if r['min_sufficient_chunks'] is not None)
    for row in rows:
        for e in row['evidence']:
            for c in e['sources']:
                assert corpus.by_id[c['id']]['text_sha256']==c['text_sha256']
                assert corpus.mappings[c['id']]['parts']
    save(target/'questions.json',rows)
    save(target/'groups.json',groups)
    save(target/'review-attestation.json',{'status':'PENDING_RESEARCHER_DIRECT_REVIEW','reviewed_question_ids':[],
        'reviewer':None,'reviewed_at':None,'gold_questions_sha256':sha(target/'questions.json')})
    pages=sorted(int(p.stem.split('-')[1]) for p in (BASE/'evidence-review').glob('pdf-*.png'))
    save(target/'validation.json',{'status':'PASS_PROGRAMMATIC_AND_CODEX_SOURCE_REVIEW',
        'questions':60,'types':{'single-evidence':20,'multi-evidence':30,'unanswerable':10},
        'question_texts_unchanged':True,'question_types_unchanged':True,'reviewed_pdf_pages':pages,
        'researcher_direct_review':'PENDING','min_chunks_max':max(r['min_sufficient_chunks'] or 0 for r in rows),
        'group_count':len(groups),'chunk_ids_valid':True,'corpus_unchanged':True,
        'semantic_equivalence_not_proved_by_program':True})
    text=['# 60문항 정답 근거·청크 대응표\n',
          '질문 문구와 20/30/10 유형을 유지했다. 원본 PDF의 필요한 사실은 Codex가 대조했다. 연구자 직접 확인은 아직 미완료다.\n',
          '각 괄호 안의 +는 모두 필요, 괄호 사이 /는 대안이다. PDF 20쪽은 범위 확인 자료이며 검색 문맥으로 사용하지 않는다.\n']
    for r in rows:
        text.extend([f'## {r["id"]} · {r["type"]}',r['question'],'',
            f'최소 충분 청크 수: {r["min_sufficient_chunks"] if r["min_sufficient_chunks"] is not None else "해당 없음"}',
            '필수 답변 요소:'])
        text.extend(f'- {e["id"]}: {e["text"]}' for e in r['required_elements'])
        if r['missing_information']:text.extend(['결여 정보: '+r['missing_information'],'허용 부분 답변: '+r['allowed_partial_answer']])
        for e in r['evidence']:
            text.extend(['',e['id']+': '+' / '.join('('+' + '.join(c)+')' for c in e['sufficient_chunk_sets']),
                'PDF: '+', '.join(map(str, sorted({p for s in e['sources'] for p in s['pdf_pages']}))),
                '```text',e['oracle_text'],'```'])
        if r['review_note']:text.append('검토 메모: '+r['review_note'])
        text.append('')
    write_text(target/'대응표.md','\n\n'.join(text))
    save(target/'manifest.json',{'status':'CODEX_VERIFIED_AWAITING_RESEARCHER_REVIEW','source_sha256':sha(source),
        'corpus_manifest_sha256':corpus.manifest_sha256,'original_pdf_sha256':sha(corpus.pdf_path),
        'files':{str(p.relative_to(target)).replace('\\','/'):sha(p) for p in target.rglob('*') if p.is_file() and p.name!='review-attestation.json'},
        'generation_input_policy':'Only question and actual retrieved chunks. No gold/type/answerability labels.'})
    print('GOLD_BUILD_PASS',len(rows),'questions',len(pages),'PDF pages reviewed')

if __name__=='__main__':build()
