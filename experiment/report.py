"""Deterministic retrieval/time/resource reporting. No generated quality scores."""
import argparse, statistics
from collections import Counter
import numpy as np
from .io import BASE,read_json,save,sha,utc,write_text
from .gold import retrieval_score

def distribution(values):
    if not values:return {'n':0,'median':None,'p95':None}
    return {'n':len(values),'median':float(np.median(values)),
      'p95':float(np.percentile(values,95,method='linear'))}

def summarize(directory):
    manifest=read_json(directory/'manifest.json');gold={q['id']:q for q in read_json(BASE/'gold-v1/questions.json')}
    rows=[read_json(p) for p in sorted((directory/'attempts').glob('*.json'))]
    by_key={(x['question_id'],x['round'],x['condition']):x for x in rows}
    first=[x for x in rows if x['round']==1];first_rag=[x for x in first if x['condition']=='RAG']
    scores=[]
    if manifest['mode']=='formal':
        for row in first_rag:
            q=gold[row['question_id']]
            scores.append({'question_id':q['id'],'type':q['type'],
              **retrieval_score(q,[i['id'] for i in (row['retrieval'] or {}).get('items',[])])})
    groups={}
    for kind in ('single-evidence','multi-evidence','all-answerable'):
        subset=[x for x in scores if x['status']=='OK' and (kind=='all-answerable' or x['type']==kind)]
        groups[kind]={'n':len(subset),'evidence_recall_at_5':statistics.mean(x['evidence_recall_at_5'] for x in subset) if subset else None,
          'complete_evidence_at_5':statistics.mean(x['complete_evidence_at_5'] for x in subset) if subset else None,
          'complete_count':sum(x['complete_evidence_at_5'] for x in subset)}
    required_rounds=manifest['rounds'];included=[];excluded={}
    questions=read_json(directory/'questions.json')
    for q in questions:
        attempts=[by_key.get((q['id'],rd,c)) for rd in range(1,required_rounds+1) for c in ('LLM_ONLY','RAG')]
        reasons=[]
        if any(a is None for a in attempts):reasons.append('NOT_ATTEMPTED')
        if any(a and a['status']!='OK' for a in attempts):reasons.append('GENERATION_FAILURE')
        if any(a and a['timing_anomalies'] for a in attempts):reasons.append('TIMING_ANOMALY')
        if reasons:excluded[q['id']]=reasons
        else:included.append(q['id'])
    timing={};resources={}
    for condition in ('LLM_ONLY','RAG'):
        representatives={qid:statistics.median(by_key[(qid,rd,condition)]['timing_ms']['total']
             for rd in range(1,required_rounds+1)) for qid in included}
        timing[condition]={'total_ms':distribution(list(representatives.values())),
          'per_question_median_ms':representatives}
        for component in ('retrieval','generation'):
            values=[statistics.median(by_key[(qid,rd,condition)]['timing_ms'][component]
                    for rd in range(1,required_rounds+1)) for qid in included] if component!='retrieval' or condition=='RAG' else []
            timing[condition][component+'_ms']=distribution(values)
        valid=[r['resources'] for r in rows if r['condition']==condition and r['resources']['valid']]
        resources[condition]={'valid_attempts':len(valid),
          'peak_rss_bytes':max((r['peak_rss_bytes'] for r in valid),default=None),
          'peak_vram_bytes':max((r['peak_vram_bytes'] for r in valid),default=None),
          'idle_vram_bytes':statistics.median(r['idle_vram_bytes'] for r in valid) if valid else None,
          'maximum_sample_gap_ms':max((r['max_actual_interval_ms'] for r in valid),default=None)}
    result={'run_id':manifest['id'],'mode':manifest['mode'],'created_at':utc(),
      'run_state':read_json(directory/'status.json')['state'],'attempts':len(rows),'planned':manifest['planned_requests'],
      'status_counts':dict(Counter(x['status'] for x in rows)),'first_round_answers':len(first),
      'quality_evaluation':'NOT_RUN','researcher_direct_review':'PENDING',
      'retrieval_status':'PROVISIONAL_CODEX_REVIEWED_GOLD' if scores else 'NOT_FORMAL_EVALUATION',
      'retrieval':groups,'retrieval_per_question':scores,'timing':timing,'resources':resources,
      'timing_scope':f'Per-question {required_rounds}-round median, then median/p95 (linear interpolation). Warm requests only.',
      'timing_included_question_ids':included,'timing_excluded':excluded,
      'output_truncations':{c:sum(x['output_truncated'] for x in rows if x['condition']==c) for c in ('LLM_ONLY','RAG')},
      'first_round_unprovided_citation_answers':sum(bool(x['unprovided_citations']) for x in first),
      'hashes':{'run_manifest':sha(directory/'manifest.json'),'gold_manifest':sha(BASE/'gold-v1/manifest.json'),
        'report_code':sha(BASE/'report.py'),'gold_scoring_code':sha(BASE/'gold.py')},
      'attempt_hashes':{p.name:sha(p) for p in sorted((directory/'attempts').glob('*.json'))}}
    save(directory/'summary.json',result)
    lines=[f'# {manifest["id"]} 실행 결과','',f'실행: {len(rows)}/{manifest["planned_requests"]}. 상태: {result["status_counts"]}.',
      '', '생성 품질 자동평가와 연구자 직접 검토는 미완료다. 아래 검색 점수는 Codex가 대조한 사전 근거표에 따른 잠정 집계다.',
      '', '| 유형 | 문항 | Evidence Recall@5 | Complete Evidence Retrieval@5 |','| --- | ---: | ---: | ---: |']
    for k,v in groups.items():
        if v['n']:lines.append(f'| {k} | {v["n"]} | {v["evidence_recall_at_5"]:.4f} | {v["complete_count"]}/{v["n"]} ({v["complete_evidence_at_5"]:.4f}) |')
    lines+=['',f'시간 비교 대상 {len(included)}문항. 질의별 {required_rounds}회 중앙값의 median/p95.',
      '', '| 조건 | median (초) | p95 (초) | Peak RSS (GiB) | Peak 장치 VRAM (GiB) |', '| --- | ---: | ---: | ---: | ---: |']
    for c in ('LLM_ONLY','RAG'):
        t=timing[c]['total_ms'];r=resources[c]
        if t['n']:lines.append(f'| {c} | {t["median"]/1000:.3f} | {t["p95"]/1000:.3f} | {(r["peak_rss_bytes"] or 0)/2**30:.3f} | {(r["peak_vram_bytes"] or 0)/2**30:.3f} |')
    lines+=['','RSS는 필요한 프로세스의 working set 합계이며 공유 메모리 중복 가능성이 있다. VRAM은 장치 전체 값이다. 두 값 모두 100ms 간격의 관측 최대값이다.',
      '',f'출력 길이 제한 도달: {result["output_truncations"]}. 답변 내용 점수는 아직 산출하지 않았다.']
    write_text(directory/'결과.md','\n'.join(lines)+'\n')
    return result

def manual_packet(directory):
    if (directory/'manual-review/selection.json').exists():return
    gold=read_json(BASE/'gold-v1/questions.json');rng=np.random.Generator(np.random.PCG64(42))
    selected=[]
    for kind,n in [('single-evidence',4),('multi-evidence',6)]:
        selected.extend(str(x) for x in rng.choice(sorted(q['id'] for q in gold if q['type']==kind),n,replace=False))
    selected+=sorted(q['id'] for q in gold if q['type']=='unanswerable')
    keys=[f'r1-{qid}-{c.lower()}' for qid in selected for c in ('LLM_ONLY','RAG')]
    order=list(np.random.Generator(np.random.PCG64(42)).permutation(keys));packet=[];key=[]
    for i,name in enumerate(order,1):
        row=read_json(directory/'attempts'/(name+'.json'));blind=f'B{i:02}'
        packet.append({'blind_id':blind,'question':row['question'],'answer':row['evaluation_answer'],
          'review_status':'PENDING','claim_verdicts':None,'element_verdicts':None,'abstention_verdict':None,'notes':''})
        key.append({'blind_id':blind,'attempt_key':name,'question_id':row['question_id'],'condition':row['condition']})
    target=directory/'manual-review'
    save(target/'selection.json',{'seed':42,'method':'PCG64; sorted IDs; 4 single then 6 multi without replacement; all unanswerable',
      'question_ids':selected,'answers':40,'selection_independent_of_answer_content':True})
    save(target/'blinded-answers.json',packet);save(target/'key.json',key)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--id',required=True);args=parser.parse_args()
    import re
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,60}',args.id):raise ValueError('Invalid run ID')
    directory=BASE/'runs'/args.id;result=summarize(directory)
    if result['mode']=='formal' and result['run_state']=='COMPLETED':manual_packet(directory)
    print({k:result[k] for k in ('run_id','attempts','status_counts','retrieval','output_truncations')})

if __name__=='__main__':main()
