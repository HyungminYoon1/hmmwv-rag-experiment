"""Prepare first-round scoring inputs and human source guides; no evaluator calls."""
import argparse,json
from collections import Counter
import numpy as np
from .io import BASE,read_json,save,sha,write_text,utc

def build(run_id):
    directory=BASE/'runs'/run_id
    if read_json(directory/'status.json')['state']!='COMPLETED':raise ValueError('Collection is not complete')
    if read_json(directory/'audit.json')['status']!='PASS':raise ValueError('Input audit must pass')
    target=directory/'evaluation-inputs'
    if target.exists():raise FileExistsError('Existing evaluation packet is preserved')
    gold={q['id']:q for q in read_json(BASE/'gold-v1/questions.json')};rows=[]
    for p in sorted((directory/'attempts').glob('r1-*.json')):
        r=read_json(p);q=gold[r['question_id']]
        rows.append({'attempt_key':r['key'],'question_id':q['id'],'condition':r['condition'],'type':q['type'],
          'user_input':r['question'],'response':r['evaluation_answer'],'raw_response':r['response']['response'],
          'retrieved_contexts':[c['text'] for c in (r['retrieval'] or {}).get('items',[])],
          'retrieved_chunk_ids':[c['id'] for c in (r['retrieval'] or {}).get('items',[])],
          'oracle_evidence':[{'id':e['id'],'text':e['oracle_text'],'sources':e['sources']} for e in q['evidence']],
          'required_elements':q['required_elements'],'missing_information':q['missing_information'],
          'allowed_partial_answer':q['allowed_partial_answer'],'predeclared_note':q['review_note'],
          'generation_status':r['status'],'attempt_file_sha256':sha(p),'evaluation_status':'NOT_RUN'})
    assert len(rows)==120 and len({r['attempt_key'] for r in rows})==120
    target.mkdir();write_text(target/'answers.jsonl','\n'.join(json.dumps(r,ensure_ascii=False) for r in rows)+'\n')
    save(target/'manifest.json',{'at':utc(),'status':'READY_FOR_EVALUATOR_CONFIGURATION','answers':120,
      'source_round':1,'files':{'answers.jsonl':sha(target/'answers.jsonl')},
      'gold_manifest_sha256':sha(BASE/'gold-v1/manifest.json'),'evaluation_policy_sha256':sha(BASE/'evaluation-policy.json'),
      'ragas_status':'NOT_INSTALLED','judge_api_status':'NOT_CONFIGURED','automatic_scores':'NOT_RUN',
      'researcher_direct_review':'PENDING','oracle_is_not_a_generated_reference_answer':True})
    selected=read_json(directory/'manual-review/selection.json')['question_ids']
    save(directory/'manual-review/evidence-guide.json',[{'question_id':qid,'question':gold[qid]['question'],
      'required_elements':gold[qid]['required_elements'],'evidence':gold[qid]['evidence'],
      'missing_information':gold[qid]['missing_information'],'allowed_partial_answer':gold[qid]['allowed_partial_answer'],
      'note':gold[qid]['review_note']} for qid in selected])
    write_text(directory/'manual-review/검토방법.md',
      '# 수동 검증 40개\n\n'
      '먼저 blinded-answers.json의 답변을 읽고 evidence-guide.json 및 원본 PDF를 대조한다. '
      '조건명과 자동점수를 보지 않은 상태에서 주장별 지원, 필수 요소 충족 또는 답변불가 부분의 유보 여부를 기록한다. '
      '검토자의 이름·확인 날짜와 원문 위치·판정 사유를 함께 남긴다.\n\n'
      '이 단계가 끝난 뒤 key.json에서 조건을 확인한다. 답변가능 문항의 RAG 답변 10개에 대해서는 '
      '원본 attempt 파일의 retrieval.items에 실제로 제공된 문맥을 사용하여 주장 지원 여부를 추가 확인한다. '
      '이는 Oracle 근거 지원 판정과 구별한다. 답변의 인용 양식으로 조건을 추측할 수 있다는 한계도 기록한다.\n\n'
      '현재 40개는 검토 대상으로 추출된 상태이며 검토가 완료된 것이 아니다. 수동 점수를 자동점수 평균에 섞지 않는다.\n')
    attempts=[read_json(p) for p in (directory/'attempts').glob('*.json')]
    descriptive={}
    for cond in ('LLM_ONLY','RAG'):
        first=[r for r in attempts if r['condition']==cond and r['round']==1]
        descriptive[cond]={'n':len(first),'input_tokens_mean':float(np.mean([r['input_tokens_counted'] for r in first])),
           'output_tokens_mean':float(np.mean([r['response']['eval_count'] for r in first])),
           'output_tokens_median':float(np.median([r['response']['eval_count'] for r in first])),
           'unprovided_citation_answers':sum(bool(r['unprovided_citations']) for r in first)}
    variations=read_json(directory/'audit.json')['answer_variation_across_rounds']
    save(directory/'descriptive.json',{'first_round_tokens':descriptive,
      'different_text_across_rounds':dict(Counter(v['condition'] for v in variations)),
      'interpretation':'A text difference is not necessarily a factual difference. Output lengths are not controlled to be identical, so latency differences alone do not prove faster computation.'})
    print('EVALUATION_INPUTS_READY',len(rows),'MANUAL_REVIEW_PENDING',40)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--id',required=True);args=parser.parse_args()
    import re
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,60}',args.id):raise ValueError('Invalid run ID')
    build(args.id)
