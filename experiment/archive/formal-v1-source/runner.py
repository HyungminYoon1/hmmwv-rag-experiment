"""Manifest-pinned paired experiment; first outcomes and all failed attempts are retained."""
import argparse, json, os, re, socket, time, urllib.error
from collections import Counter
import numpy as np
from .io import BASE,ROOT,read_json,save,sha,utc
from .generation import Generator,api,context_text,evaluation_copy,EMPTY_CONTEXT
from .retriever import Retriever
from .resources import Monitor,monitored_pids

CORE=('runner.py','generation.py','worker.py','retriever.py','resources.py','io.py',
      'config.json','prompt.txt','development.json','evaluation-policy.json')

def schedule(ids,rounds=3,seed=42):
    order=list(np.random.Generator(np.random.PCG64(seed)).permutation(sorted(ids)))
    rows=[]
    for rd in range(1,rounds+1):
        sequence=order[::-1] if rd==2 else order
        for position,qid in enumerate(sequence):
            conditions=['LLM_ONLY','RAG'] if (position+rd-1)%2==0 else ['RAG','LLM_ONLY']
            for condition in conditions:
                rows.append({'sequence':len(rows)+1,'round':rd,'question_id':str(qid),'condition':condition,
                  'key':f'r{rd}-{qid}-{condition.lower()}'})
    return rows

def identity():
    from retrieval.common import environment
    config=read_json(BASE/'config.json')
    paths=[BASE/p for p in CORE]+[BASE/'gold-v1/manifest.json',BASE/'models/model.lock.json',
      ROOT/config['tokenizer'],ROOT/config['tokenizer_config'],ROOT/'retrieval/config.json',
      ROOT/'retrieval/service.py',ROOT/'retrieval/indexes/bge-m3-v1/manifest.json',
      ROOT/'preprocessing/output/corpus-v6-final/manifest.json']
    tags=api('/api/tags')['models'];model=next(x for x in tags if x['name']==config['model'])
    return {'files':{p.relative_to(ROOT).as_posix():sha(p) for p in paths},
      'environment':environment(),'ollama_version':api('/api/version'),'model_digest':model['digest'],
      'model_details':model['details']}

def verify_gold():
    gold=BASE/'gold-v1';manifest=read_json(gold/'manifest.json')
    for name,digest in manifest['files'].items():
        if sha(gold/name)!=digest:raise ValueError('Gold file changed: '+name)

def prepare(run_id,mode):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,60}',run_id):raise ValueError('Invalid run ID')
    directory=BASE/'runs'/run_id
    if directory.exists():raise FileExistsError('Run ID already exists; existing results are preserved')
    verify_gold()
    if mode=='formal':
        pilot=read_json(BASE/'reports/pilot-readiness.json')
        if pilot['status']!='PASS' or pilot['identity']!=identity():raise ValueError('A matching successful pilot is required')
    config=read_json(BASE/'config.json')
    source=BASE/('gold-v1/questions.json' if mode=='formal' else 'development.json')
    # Only the public question strings enter this runner dataset. Labels remain in separate gold files.
    questions=[{'id':q['id'],'question':q['question']} for q in read_json(source)]
    rounds=config['rounds'] if mode=='formal' else 1
    plan=schedule([x['id'] for x in questions],rounds,config['seed'])
    directory.mkdir(parents=True);save(directory/'questions.json',questions);save(directory/'schedule.json',plan)
    manifest={'id':run_id,'created_at':utc(),'mode':mode,'identity':identity(),
      'question_file_sha256':sha(source),'questions_sha256':sha(directory/'questions.json'),
      'schedule_sha256':sha(directory/'schedule.json'),'planned_requests':len(plan),'rounds':rounds,
      'quality_round':1,'researcher_direct_review':'PENDING','quality_evaluation':'NOT_RUN',
      'warmup_ids':['D01','D02','D04','D06','D09'],'warmup_per_condition_per_round':5}
    save(directory/'manifest.json',manifest)
    save(directory/'status.json',{'state':'PREPARED','completed':0,'planned':len(plan),'at':utc()})
    print('PREPARED',run_id,len(plan),flush=True)

def execute_one(row,question,gen,retriever,server_pid):
    before=gen.resident();pids,tree=monitored_pids(server_pid,retriever.pid,row['condition']=='RAG')
    monitor=Monitor(pids,gen.config['sample_interval_ms']/1000);monitor.start()
    time.sleep(gen.config['idle_seconds'])
    record={**row,'question':question,'started_at':utc(),'resident_before':before,'model_pids_before':tree,
      'retrieval':None,'payload':None,'response':None,'status':'NOT_RUN','timing_anomalies':[]}
    monitor.phase='request';start=time.perf_counter();split=start
    fatal=False
    try:
        if row['condition']=='RAG':
            record['retrieval']=retriever.search(question)
            context=context_text(record['retrieval']['items'])
            split=time.perf_counter()
        else:context=EMPTY_CONTEXT
        payload,count=gen.prepare(question,context);record['payload']=payload;record['input_tokens_counted']=count
        response=gen.generate(payload);record['response']=response
        record['status']='OK' if response.get('done') and response.get('response','').strip() else 'GEN_EMPTY'
    except (TimeoutError,socket.timeout) as exc:
        record['status']='GEN_TIMEOUT';record['error']=type(exc).__name__+': '+str(exc);fatal=True
    except urllib.error.URLError as exc:
        record['status']='GEN_TIMEOUT' if isinstance(exc.reason,(TimeoutError,socket.timeout)) else 'GEN_ERROR'
        record['error']=type(exc).__name__+': '+str(exc);fatal=True
    except Exception as exc:
        record['status']='GEN_ERROR';record['error']=type(exc).__name__+': '+str(exc);fatal=True
    end=time.perf_counter();record['ended_at']=utc();monitor.phase='after'
    record['resources']=monitor.stop()
    record['timing_ms']={'total':(end-start)*1000,
       'retrieval':(split-start)*1000 if row['condition']=='RAG' else None,
       'generation':(end-split)*1000,'component_gap':0.0}
    try:
        record['resident_after']=gen.resident()
        _,after_tree=monitored_pids(server_pid,retriever.pid,row['condition']=='RAG')
        record['model_pids_after']=after_tree
        if set(tree)!=set(after_tree):record['timing_anomalies'].append('MODEL_PROCESS_CHANGED')
    except Exception as exc:
        record['timing_anomalies'].append('RESIDENCY_CHECK_FAILED');record['residency_error']=str(exc);fatal=True
    response=record['response'] or {};answer=response.get('response','')
    clean,citations=evaluation_copy(answer);record['evaluation_answer']=clean;record['citation_ids']=citations
    supplied={x['id'] for x in (record['retrieval'] or {}).get('items',[])}
    record['unprovided_citations']=sorted({x[1:-1] for x in citations}-supplied)
    record['output_truncated']=response.get('done_reason')=='length'
    actual=response.get('prompt_eval_count')
    if actual is not None and record.get('input_tokens_counted')!=actual:
        record['timing_anomalies'].append('TOKEN_COUNT_MISMATCH');fatal=True
    record['prompt_eval_cached_count']=response.get('prompt_eval_cached_count')
    record['prompt_eval_cache_reporting']='AVAILABLE' if 'prompt_eval_cached_count' in response else 'UNAVAILABLE'
    record['fatal_requires_diagnosis']=fatal
    return record

def run(run_id):
    directory=BASE/'runs'/run_id;manifest=read_json(directory/'manifest.json')
    if identity()!=manifest['identity']:raise ValueError('Run identity changed; do not resume under a different implementation')
    verify_gold()
    for name,key in [('questions.json','questions_sha256'),('schedule.json','schedule_sha256')]:
        if sha(directory/name)!=manifest[key]:raise ValueError('Run data changed')
    if (directory/'active.json').exists():raise RuntimeError('Interrupted attempt needs diagnosis; it will not be overwritten')
    previous=read_json(directory/'status.json')
    if previous['state']=='STOPPED':
        recovery=read_json(directory/'recovery.json')
        if recovery.get('stopped_at')!=previous['at'] or recovery.get('previous_request_ended') is not True:
            raise RuntimeError('Previous request completion must be verified before resuming')
    plan=read_json(directory/'schedule.json');questions={x['id']:x['question'] for x in read_json(directory/'questions.json')}
    completed={p.stem for p in (directory/'attempts').glob('*.json')} if (directory/'attempts').exists() else set()
    if len(completed)==len(plan):print('ALREADY_COMPLETE');return
    lock=directory/'running.lock'
    with lock.open('x',encoding='utf-8') as f:f.write(str(os.getpid()))
    retriever=None
    try:
        gen=Generator();server_pid=int((BASE/'reports/ollama-pid.txt').read_text(encoding='utf-8-sig').strip())
        retriever=Retriever()
        dev={x['id']:x['question'] for x in read_json(BASE/'development.json')}
        # The first load is excluded, before measured warmups and residency checks.
        payload,_=gen.prepare(dev['D01'],EMPTY_CONTEXT);gen.generate(payload);gen.resident()
        session=utc().replace(':','').replace('.','').replace('+','')
        warmed=set()
        for row in plan:
            if row['key'] in completed:continue
            if row['round'] not in warmed:
                save(directory/'status.json',{'state':'WARMING','round':row['round'],'completed':len(completed),'planned':len(plan),'at':utc()})
                for index,qid in enumerate(manifest['warmup_ids']):
                    for condition in ('LLM_ONLY','RAG'):
                        warm={'round':row['round'],'question_id':qid,'condition':condition,'purpose':'WARMUP'}
                        result=execute_one(warm,dev[qid],gen,retriever,server_pid)
                        save(directory/'warmups'/session/f'r{row["round"]}-{index}-{condition}.json',result)
                        if result['fatal_requires_diagnosis'] or result['status']!='OK':raise RuntimeError('Warmup failed; inspect retained record')
                warmed.add(row['round'])
            save(directory/'active.json',{**row,'started_at':utc(),'runner_pid':os.getpid()})
            save(directory/'status.json',{'state':'RUNNING',**row,'completed':len(completed),'planned':len(plan),'at':utc()})
            result=execute_one(row,questions[row['question_id']],gen,retriever,server_pid)
            output=directory/'attempts'/(row['key']+'.json')
            if output.exists():raise FileExistsError('Attempt already exists')
            save(output,result);(directory/'active.json').unlink();completed.add(row['key'])
            save(directory/'status.json',{'state':'RUNNING','completed':len(completed),'planned':len(plan),'last':row['key'],'at':utc()})
            print(f'{len(completed)}/{len(plan)} {row["key"]} {result["status"]} {result["timing_ms"]["total"]:.0f} ms',flush=True)
            if result['fatal_requires_diagnosis']:
                raise RuntimeError('Stopped after a failed or invalid attempt. Do not continue until the previous request has ended.')
        save(directory/'status.json',{'state':'COMPLETED','completed':len(completed),'planned':len(plan),'at':utc(),
          'quality_evaluation':'NOT_RUN','researcher_direct_review':'PENDING'})
    except BaseException as exc:
        save(directory/'status.json',{'state':'STOPPED','completed':len(completed),'planned':len(plan),'at':utc(),
             'error':type(exc).__name__+': '+str(exc)})
        raise
    finally:
        if retriever:retriever.close()
        lock.unlink(missing_ok=True)

def certify_pilot(run_id):
    directory=BASE/'runs'/run_id;manifest=read_json(directory/'manifest.json')
    rows=[read_json(p) for p in (directory/'attempts').glob('*.json')]
    checks={'pilot_mode':manifest['mode']=='pilot','twenty_attempts':len(rows)==20,
      'all_ok':all(x['status']=='OK' for x in rows),'no_timing_anomalies':all(not x['timing_anomalies'] for x in rows),
      'resources_valid':all(x['resources']['valid'] for x in rows),
      'token_counts_agree':all(x['input_tokens_counted']==x['response']['prompt_eval_count'] for x in rows),
      'same_identity':identity()==manifest['identity'],'completed':read_json(directory/'status.json')['state']=='COMPLETED'}
    save(BASE/'reports/pilot-readiness.json',{'status':'PASS' if all(checks.values()) else 'FAIL',
      'checks':checks,'identity':identity(),'run_id':run_id,'at':utc(),
      'scope':'Execution, token budgeting, paired inputs, and resource measurement. Not formal answer accuracy.'})
    print(checks)
    if not all(checks.values()):raise RuntimeError('Pilot not ready')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run','certify-pilot'])
    parser.add_argument('--id',required=True);parser.add_argument('--mode',choices=['pilot','formal'],default='pilot')
    args=parser.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,60}',args.id):raise ValueError('Invalid run ID')
    if args.action=='prepare':prepare(args.id,args.mode)
    elif args.action=='run':run(args.id)
    else:certify_pilot(args.id)

if __name__=='__main__':main()
