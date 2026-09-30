"""Aggregation over cached answers and declared evidence; no model calls."""
import math

def retrieval(gold, rows, excluded=()):
    details=[]
    for q in gold:
        if q['type']=='unanswerable' or q['id'] in excluded: continue
        ids=rows['r1-'+q['id']+'-rag']['retrieved_chunk_ids']
        hit={g['id']:any(set(combo)<=set(ids) for combo in g['sufficient_chunk_sets']) for g in q['evidence']}
        details.append({'id':q['id'],'type':q['type'],'retrieved_ids':ids,'groups':hit,'recall':sum(hit.values())/len(hit),'complete':all(hit.values())})
    summary={}
    for kind in ['all','single-evidence','multi-evidence']:
        subset=[d for d in details if kind=='all' or d['type']==kind]
        summary[kind]={'n':len(subset),'mean_recall':math.fsum(d['recall'] for d in subset)/len(subset),
                       'complete':sum(d['complete'] for d in subset),'none':sum(d['recall']==0 for d in subset),
                       'partial':sum(0<d['recall']<1 for d in subset)}
    return {'summary':summary,'details':details}

def quality(results, search, excluded=()):
    output={'aggregate':[],'pairs':[],'retrieval_groups':[]}
    for kind in ['all','single-evidence','multi-evidence']:
        for condition in ['LLM_ONLY','RAG']:
            subset=[r for r in results if r['type']!='unanswerable' and r['question_id'] not in excluded and r['condition']==condition and (kind=='all' or r['type']==kind)]
            for metric in ['ar_report','oracle_support','required_coverage','faithfulness']:
                vals=[r['metrics'][metric]['value'] for r in subset if r['metrics'][metric]['value'] is not None]
                output['aggregate'].append({'type':kind,'condition':condition,'metric':metric,'n':len(vals),'mean':math.fsum(vals)/len(vals) if vals else None})
            output['aggregate'].append({'type':kind,'condition':condition,'metric':'all_required','n':len(subset),'count':sum(r['metrics']['required_coverage']['value']==1 for r in subset)})
        by={c:{r['question_id']:r for r in results if r['type']!='unanswerable' and r['question_id'] not in excluded and r['condition']==c and (kind=='all' or r['type']==kind)} for c in ['LLM_ONLY','RAG']}
        for metric in ['ar_report','oracle_support','required_coverage']:
            diffs=[by['RAG'][i]['metrics'][metric]['value']-by['LLM_ONLY'][i]['metrics'][metric]['value'] for i in sorted(by['RAG'])]
            output['pairs'].append({'type':kind,'metric':metric,'n':len(diffs),'mean_difference':math.fsum(diffs)/len(diffs),'higher':sum(d>1e-12 for d in diffs),'equal':sum(abs(d)<=1e-12 for d in diffs),'lower':sum(d< -1e-12 for d in diffs)})
    rag={r['question_id']:r for r in results if r['type']!='unanswerable' and r['condition']=='RAG' and r['question_id'] not in excluded}
    for complete in [True,False]:
        ids=[d['id'] for d in search['details'] if d['complete']==complete and d['id'] not in excluded]
        output['retrieval_groups'].append({'complete':complete,'n':len(ids),'ids':ids,
            'support':math.fsum(rag[i]['metrics']['oracle_support']['value'] for i in ids)/len(ids),
            'coverage':math.fsum(rag[i]['metrics']['required_coverage']['value'] for i in ids)/len(ids),
            'all_required':sum(rag[i]['metrics']['required_coverage']['value']==1 for i in ids)})
    output['supported_but_incomplete']=[i for i,r in rag.items() if r['metrics']['oracle_support']['value']==1 and r['metrics']['required_coverage']['value']<1]
    return output
