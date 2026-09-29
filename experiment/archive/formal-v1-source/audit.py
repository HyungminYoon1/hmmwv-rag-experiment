"""Independent file, paired-input, token and result coverage checks; no LLM calls."""
import argparse
from collections import Counter
from .io import BASE,ROOT,read_json,save,sha,utc
from .generation import Generator,EMPTY_CONTEXT,context_text

def baseline_check(target):
    baseline=read_json(BASE/'baseline.json');bad=[]
    for name,digest in baseline['files'].items():
        p=ROOT/name
        if not p.is_file() or sha(p)!=digest:bad.append(name)
    result={'status':'PASS' if not bad else 'FAIL','at':utc(),'checked_files':len(baseline['files']),
      'changed_or_missing':bad,'backup':baseline['backup']}
    save(target,result)
    if bad:raise RuntimeError('Baseline changed')
    return result

def audit_run(run_id):
    from retrieval.source import Corpus
    from retrieval.common import load_config
    corpus=Corpus(load_config());directory=BASE/'runs'/run_id;manifest=read_json(directory/'manifest.json')
    schedule=read_json(directory/'schedule.json');questions={q['id']:q['question'] for q in read_json(directory/'questions.json')}
    gen=Generator();errors=[];rows={p.stem:read_json(p) for p in (directory/'attempts').glob('*.json')}
    if set(rows)!={x['key'] for x in schedule}:errors.append('Missing or unexpected attempt records')
    token_max=0
    for step in schedule:
        r=rows.get(step['key'])
        if r is None:continue
        if any(r[k]!=v for k,v in step.items()):errors.append(step['key']+': schedule mismatch')
        if r['question']!=questions[step['question_id']]:errors.append(step['key']+': question changed')
        items=(r['retrieval'] or {}).get('items',[])
        if r['condition']=='RAG':
            if len(items)!=5 or [x['rank'] for x in items]!=[1,2,3,4,5]:errors.append(step['key']+': invalid Top-5')
            if len({x['id'] for x in items})!=5:errors.append(step['key']+': duplicate chunk')
            for x in items:
                original=corpus.by_id.get(x['id'])
                if original is None or any(x[k]!=v for k,v in original.items()):errors.append(step['key']+': chunk text/provenance changed')
        elif items:errors.append(step['key']+': reference leaked into LLM Only')
        payload,count=gen.prepare(r['question'],context_text(items) if r['condition']=='RAG' else EMPTY_CONTEXT)
        if r['payload']!=payload:errors.append(step['key']+': payload not reproducible')
        if r['input_tokens_counted']!=count or r['response']['prompt_eval_count']!=count:errors.append(step['key']+': token count')
        token_max=max(token_max,count)
        if len(r['resources']['pids'])!=len(set(r['resources']['pids'])):errors.append(step['key']+': PID counted twice')
    repeated_search=[];different_answers=[]
    for qid in questions:
        rag=[r for r in rows.values() if r['question_id']==qid and r['condition']=='RAG']
        signatures=[[(c['id'],c['score']) for c in (r['retrieval'] or {}).get('items',[])] for r in rag]
        if signatures and any(s!=signatures[0] for s in signatures):repeated_search.append(qid)
        for condition in ('LLM_ONLY','RAG'):
            answers={(r['response'] or {}).get('response') for r in rows.values() if r['question_id']==qid and r['condition']==condition}
            if len(answers)>1:different_answers.append({'question_id':qid,'condition':condition,'unique_answers':len(answers)})
    report={'status':'PASS' if not errors else 'FAIL','at':utc(),'run_id':run_id,'checked_attempts':len(rows),
      'errors':errors,'max_input_tokens':token_max,'output_token_budget':gen.config['options']['num_predict'],
      'context_limit':gen.config['options']['num_ctx'],'question_types_or_gold_in_payload':False if not errors else 'UNVERIFIED',
      'repeated_search_differences':repeated_search,'answer_variation_across_rounds':different_answers,
      'runtime_statuses':dict(Counter(r['status'] for r in rows.values())),
      'scope':'Recorded inputs, artifact integrity, exact chunk provenance, schedule and token lengths. Not semantic answer correctness.'}
    save(directory/'audit.json',report)
    baseline_check(directory/'baseline-after.json')
    if errors:raise RuntimeError('Run audit failed')
    print({k:report[k] for k in ('status','checked_attempts','max_input_tokens','repeated_search_differences','answer_variation_across_rounds')})

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--id');args=parser.parse_args()
    if args.id:
        import re
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,60}',args.id):raise ValueError('Invalid run ID')
        audit_run(args.id)
    else:print(baseline_check(BASE/'reports/baseline-before-formal.json'))
