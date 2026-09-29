"""python -m experiment.evaluation.runner --help (separate evaluation environment)."""
import argparse
import asyncio
import json
import os
import sys
import time
from contextlib import contextmanager
from .common import BASE, EXPERIMENT, ROOT, EvaluationError, read, save, sha, fingerprint, valid_id, utc, safe_error
from .providers import validate_profile, ollama_metadata, Transport
from .inputs import source_packet, code_identity, environment
from .fixtures import synthetic_rows
from .report import summarize, completed


def profile_named(name):
    return validate_profile(read(BASE/'profiles'/(valid_id(name)+'.json')))


def doctor(profile):
    result={'provider':profile['provider'],'model':profile['model'],'smoke_only':profile.get('smoke_only',False),
            'environment':environment(),'credential_present':None}
    if profile['provider']=='openai':
        result['credential_present']=bool(os.environ.get(profile['api_key_env']))
        result['ready']=result['credential_present']
        result['model_access_verified']=False
    else:
        try:
            result['local_model']=ollama_metadata(profile)
            result['ready']=True
        except Exception as e:
            result.update(ready=False,error=safe_error(e))
    return result


def prepare(run_id,profile_name,source_run='formal-v1',mode='benchmark'):
    profile=profile_named(profile_name)
    if mode=='benchmark' and profile.get('smoke_only'):
        raise EvaluationError('SMOKE_MODEL_CANNOT_SCORE_BENCHMARK')
    directory=BASE/'runs'/valid_id(run_id)
    if directory.exists():raise EvaluationError('RUN_ALREADY_EXISTS')
    if mode=='benchmark':
        rows,policy,sources=source_packet(source_run)
    else:
        rows=synthetic_rows();policy=read(EXPERIMENT/'evaluation-policy.json')
        sources={'experiment/evaluation-policy.json':sha(EXPERIMENT/'evaluation-policy.json')}
    local=ollama_metadata(profile) if profile['provider']=='ollama' else None
    packet={'rows':rows,'policy':policy}
    identity={'profile':profile,'inputs_hash':fingerprint(packet),'source_hashes':sources,
              'code':code_identity(),'environment':environment(),'local_model':local,
              'maximum_attempts_per_stage':3,'concurrency':1}
    manifest={'id':run_id,'mode':mode,'source_run':source_run if mode=='benchmark' else None,
              'created_at':utc(),'profile':profile,'identity':identity,'identity_hash':fingerprint(identity),
              'evaluator_configured_after_generation':True,'researcher_source_review':'PENDING',
              'human_evaluator_validation':'PENDING'}
    directory.mkdir(parents=True)
    for name in identity['code']['files']:
        snapshot=directory/'code-snapshot'/name
        snapshot.parent.mkdir(parents=True,exist_ok=True)
        snapshot.write_bytes((ROOT/name).read_bytes())
    save(directory/'inputs.json',packet)
    save(directory/'manifest.json',manifest)
    summarize(directory)
    return {'id':run_id,'mode':mode,'answers':len(rows),'provider':profile['provider'],'model':profile['model'],
            'status':'PREPARED_NO_GENERATION_OR_JUDGE_CALLS','base_stage_calls':sum(1 if r['type']=='unanswerable' else 8 if r['condition']=='RAG' else 7 for r in rows)}


def verify(directory):
    m=read(directory/'manifest.json');identity=m['identity']
    if fingerprint(identity)!=m['identity_hash'] or m['profile']!=identity['profile']:
        raise EvaluationError('MANIFEST_IDENTITY_MISMATCH')
    packet=read(directory/'inputs.json')
    if fingerprint(packet)!=identity['inputs_hash']:raise EvaluationError('FROZEN_INPUTS_CHANGED')
    if code_identity()!=identity['code']:raise EvaluationError('EVALUATOR_CODE_CHANGED_CREATE_NEW_RUN')
    for name,expected in identity['code']['files'].items():
        if sha(directory/'code-snapshot'/name)!=expected:raise EvaluationError('CODE_SNAPSHOT_CHANGED')
    if environment()!=identity['environment']:raise EvaluationError('EVALUATOR_ENVIRONMENT_CHANGED')
    for name,expected in identity['source_hashes'].items():
        path=(ROOT/name).resolve()
        if not path.is_relative_to(ROOT.resolve()) or sha(path)!=expected:raise EvaluationError('ORIGINAL_INPUT_CHANGED')
    if m['profile']['provider']=='ollama' and ollama_metadata(m['profile'])!=identity['local_model']:
        raise EvaluationError('LOCAL_MODEL_CHANGED')
    if m['mode']=='benchmark' and m['profile'].get('smoke_only'):raise EvaluationError('SMOKE_MODEL_CANNOT_SCORE_BENCHMARK')
    return m,packet


def pid_alive(pid):
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        handle=kernel.OpenProcess(0x1000,False,pid)
        if not handle:
            if ctypes.get_last_error()==87:return False
            raise EvaluationError('CANNOT_VERIFY_LOCK_PROCESS')
        try:
            code=wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)):raise EvaluationError('CANNOT_VERIFY_LOCK_PROCESS')
            return code.value==259
        finally:kernel.CloseHandle(handle)
    try:os.kill(pid,0);return True
    except ProcessLookupError:return False


@contextmanager
def run_lock(directory):
    path=directory/'run.lock'
    if path.exists():
        old=read(path)
        if pid_alive(old['pid']):raise EvaluationError('RUN_ALREADY_ACTIVE')
        path.rename(directory/f"stale-lock-{time.time_ns()}.json")
    try:
        with path.open('x',encoding='utf-8',newline='\r\n') as stream:
            stream.write(json.dumps({'pid':os.getpid(),'at':utc()})+'\n')
    except FileExistsError:raise EvaluationError('RUN_ALREADY_ACTIVE') from None
    try:yield
    finally:path.unlink(missing_ok=True)


async def execute(directory,limit=None):
    from .judge import Journal
    from .engine import Evaluator
    from .embeddings import LocalEmbeddings
    manifest,packet=verify(directory)
    if manifest['profile']['provider']=='openai' and not os.environ.get(manifest['profile']['api_key_env']):
        raise EvaluationError('API_KEY_NOT_CONFIGURED')
    transport=Transport(manifest['profile'])
    # Keep the first observed API model string across interrupted runs.
    observed={read(p)['provider']['returned_model'] for p in (directory/'calls').rglob('attempt-*.json')
              if read(p).get('provider',{}).get('returned_model')}
    if len(observed)>1:raise EvaluationError('MIXED_RETURNED_MODELS')
    transport.expected_returned_model=next(iter(observed),None)
    embeddings=LocalEmbeddings(directory/'embeddings')
    journal=Journal(directory/'calls',transport,manifest['identity_hash'])
    evaluator=Evaluator(journal,embeddings,packet['policy'])
    try:
        with run_lock(directory):
            done={r['attempt_key'] for r in completed(directory,manifest)}
            remaining=[r for r in packet['rows'] if r['attempt_key'] not in done]
            if limit is not None:remaining=remaining[:limit]
            for row in remaining:
                start=time.perf_counter()
                result=await evaluator.evaluate(row)
                result['evaluation_elapsed_seconds']=time.perf_counter()-start
                save(directory/'results'/(row['attempt_key']+'.json'),{
                    'identity_hash':manifest['identity_hash'],'input_hash':fingerprint(row),'at':utc(),
                    'result_hash':fingerprint(result),'result':result})
                summary=summarize(directory)
                print(json.dumps({k:summary[k] for k in ('id','processed','expected','answers_with_evaluator_errors')},ensure_ascii=False),flush=True)
    finally:
        await transport.close()
        embeddings.close()
    return summarize(directory)


def main():
    parser=argparse.ArgumentParser(description='Frozen-answer evaluator: OpenAI Responses or local Ollama.')
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('doctor');p.add_argument('--profile',required=True)
    p=sub.add_parser('prepare');p.add_argument('--id',required=True);p.add_argument('--profile',required=True);p.add_argument('--source-run',default='formal-v1')
    p=sub.add_parser('run');p.add_argument('--id',required=True);p.add_argument('--limit',type=int)
    p=sub.add_parser('report');p.add_argument('--id',required=True)
    p=sub.add_parser('smoke');p.add_argument('--id',required=True);p.add_argument('--profile',default='installed-4b-smoke')
    args=parser.parse_args()
    try:
        if args.command=='doctor':out=doctor(profile_named(args.profile))
        elif args.command=='prepare':out=prepare(args.id,args.profile,args.source_run)
        elif args.command=='report':
            directory=BASE/'runs'/valid_id(args.id);verify(directory);out=summarize(directory)
        elif args.command=='smoke':
            directory=BASE/'runs'/valid_id(args.id)
            if not directory.exists():prepare(args.id,args.profile,mode='smoke')
            elif read(directory/'manifest.json')['mode']!='smoke':raise EvaluationError('NOT_A_SMOKE_RUN')
            out=asyncio.run(execute(directory))
        else:
            if args.limit is not None and args.limit<1:raise EvaluationError('LIMIT_MUST_BE_POSITIVE')
            out=asyncio.run(execute(BASE/'runs'/valid_id(args.id),args.limit))
        print(json.dumps(out,ensure_ascii=False,indent=2))
    except KeyboardInterrupt:
        print(json.dumps({'status':'INTERRUPTED','resume':'Repeat the same run command.'}));sys.exit(130)
    except Exception as error:
        print(json.dumps({'status':'ERROR',**safe_error(error)}));sys.exit(1)


if __name__=='__main__':main()
