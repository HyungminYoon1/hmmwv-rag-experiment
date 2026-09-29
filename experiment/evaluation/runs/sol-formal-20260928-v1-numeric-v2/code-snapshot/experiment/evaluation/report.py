"""Explicit denominators and paired comparisons; no conversion of evaluator failure to zero."""
from collections import Counter
from statistics import mean
from .common import read, save, write_text, utc, EvaluationError, fingerprint

METRICS=('ar_raw','ar_report','oracle_support','required_coverage','faithfulness',
         'full_abstention','correct_abstention','corpus_unanswerable_abstention')


def completed(directory,manifest):
    rows=[]
    for path in sorted((directory/'results').glob('*.json')):
        record=read(path)
        result=record['result']
        if record['identity_hash']!=manifest['identity_hash'] or record['result_hash']!=fingerprint(result):
            raise EvaluationError('RESULT_INTEGRITY_MISMATCH')
        rows.append(result)
    return rows


def summarize(directory):
    m=read(directory/'manifest.json')
    rows=completed(directory,m)
    expected=read(directory/'inputs.json')['rows']
    keys={r['attempt_key'] for r in expected}
    if len({r['attempt_key'] for r in rows})!=len(rows) or any(r['attempt_key'] not in keys for r in rows):
        raise EvaluationError('UNEXPECTED_RESULT')
    aggregate=[]
    for condition in ('LLM_ONLY','RAG'):
        for kind in ('all','single-evidence','multi-evidence','unanswerable'):
            subset=[r for r in rows if r['condition']==condition and (kind=='all' or r['type']==kind)]
            if not subset:continue
            for name in METRICS:
                values=[r['metrics'][name]['value'] for r in subset if r['metrics'][name]['value'] is not None]
                aggregate.append({'condition':condition,'type':kind,'metric':name,'mean':mean(values) if values else None,
                                  'valid_n':len(values),'processed_n':len(subset),
                                  'statuses':dict(Counter(r['metrics'][name]['status'] for r in subset))})
    paired=[]
    for name in ('ar_report','oracle_support','required_coverage','full_abstention'):
        for kind in ('all','single-evidence','multi-evidence'):
            groups={c:{r['question_id']:r['metrics'][name]['value'] for r in rows if r['condition']==c
                       and r['type']!='unanswerable' and (kind=='all' or r['type']==kind)
                       and r['metrics'][name]['value'] is not None} for c in ('LLM_ONLY','RAG')}
            ids=sorted(set(groups['LLM_ONLY']) & set(groups['RAG']))
            paired.append({'metric':name,'type':kind,'paired_n':len(ids),'question_ids':ids,
                           'mean_rag_minus_llm_only':mean(groups['RAG'][q]-groups['LLM_ONLY'][q] for q in ids) if ids else None})
    usage=Counter();attempts=0;calls=0
    for p in (directory/'calls').rglob('attempt-*.json'):
        item=read(p);attempts+=1
        if item.get('provider'):
            calls+=1
            for key in ('input_tokens','output_tokens'):
                value=(item['provider'].get('usage') or {}).get(key)
                if isinstance(value,int):usage[key]+=value
    errors=sum(bool(r['errors']) for r in rows)
    state='NOT_RUN' if not rows else 'PARTIAL' if len(rows)<len(expected) else 'COMPLETED_WITH_EVAL_ERRORS' if errors else 'COMPLETED'
    out={'id':m['id'],'mode':m['mode'],'created_at':m['created_at'],'updated_at':utc(),
         'status':state,'judge':m['profile']['model'],'provider':m['profile']['provider'],
         'processed':len(rows),'expected':len(expected),'answers_with_evaluator_errors':errors,
         'source_run':m['source_run'],'source_round':1 if m['mode']=='benchmark' else None,
         'researcher_source_review':'PENDING','human_evaluator_validation':'PENDING',
         'final_quality_claims_ready':False,'interpretation':'SYNTHETIC_FUNCTIONAL_TEST' if m['mode']=='smoke' else 'PROVISIONAL_AUTOMATIC_SCORES',
         'aggregate':aggregate,'paired':paired,'provider_response_count':calls,'attempt_slots_used':attempts,
         'usage':dict(usage),'usage_is_complete_invoice':False}
    save(directory/'summary.json',out)
    lines=[f"# 답변 평가 {m['id']}",'',f"- 상태: {state} ({len(rows)}/{len(expected)})",f"- 평가 모델: {m['profile']['model']}",
           f"- 구분: {out['interpretation']}",'- 연구자 원문 검토 및 수동평가 대조: PENDING',
           '- 평가기 오류는 결측이며, 생성 실패 0점과 구분한다. 자동평가가 완료되어도 최종 품질 검증 완료를 뜻하지 않는다.',
           '', '| 조건 | 대상 | 지표 | 평균 | 유효 답변 수 | 처리 답변 수 |','|---|---|---|---:|---:|---:|']
    for a in aggregate:
        if a['type']!='all':continue
        value='—' if a['mean'] is None else f"{a['mean']:.4f}"
        lines.append(f"| {a['condition']} | {a['type']} | {a['metric']} | {value} | {a['valid_n']} | {a['processed_n']} |")
    lines+=['','짝비교는 두 조건 모두 유효한 동일 문항에 한정한다. Faithfulness와 두 답변불가 지표는 적용 범위가 달라 직접 짝비교하지 않는다.',
            '상세 판정과 근거 인용은 results/, 원본 평가 응답과 재시도 이력은 calls/에 보관한다.']
    write_text(directory/'report.md','\n'.join(lines)+'\n')
    return out
