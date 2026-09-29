import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace
import pytest
import httpx
from ragas.embeddings.base import BaseRagasEmbedding
from experiment.evaluation.common import EvaluationError, read, save, fingerprint
from experiment.evaluation.schemas import AnswerKind, CoverageOutput, SupportOutput
from experiment.evaluation.engine import Evaluator, coverage_valid, quotes_valid, cosine_reference
from experiment.evaluation.judge import Journal
from experiment.evaluation.providers import Transport, strict_schema, validate_profile
from experiment.evaluation.fixtures import synthetic_rows
from experiment.evaluation.runner import profile_named, prepare, pid_alive
from experiment.evaluation.inputs import source_packet
from experiment.evaluation.report import summarize


def run(value):return asyncio.run(value)


def test_reference_cosine_is_independent_of_numpy(monkeypatch):
    import numpy as np
    def forbidden(*args,**kwargs):raise AssertionError('Reference must not use NumPy dot or norm')
    monkeypatch.setattr(np,'dot',forbidden);monkeypatch.setattr(np.linalg,'norm',forbidden)
    assert cosine_reference([1.,0.],[0.,1.])==0.
    assert cosine_reference([3.,4.],[-3.,-4.])==pytest.approx(-1.)
    assert cosine_reference([3.,4.],[6.,8.])==pytest.approx(1.)
    with pytest.raises(EvaluationError):cosine_reference([0.,0.],[1.,0.])
    with pytest.raises(EvaluationError):cosine_reference([1.],[1.,0.])


class Vectors(BaseRagasEmbedding):
    def __init__(self,negative=False):
        super().__init__();self.last_vectors={};self.negative=negative
        self.last_query_vector=None;self.last_response_vectors=None
    def embed_text(self,text,**kwargs):
        value=[1.,0.] if text.startswith('At what') else [-1.,0.] if self.negative else [1.,0.]
        self.last_vectors[text]=value
        return value
    def embed_texts(self,texts,**kwargs):return [self.embed_text(t) for t in texts]
    async def aembed_text(self,text,**kwargs):
        self.last_query_vector=self.embed_text(text)
        return self.last_query_vector
    async def aembed_texts(self,texts,**kwargs):
        self.last_response_vectors=self.embed_texts(texts)
        return self.last_response_vectors


class FakeJournal:
    def __init__(self,row,flags=(0,0,0),fail=None,full=False):
        self.row=row;self.flags=iter(flags);self.calls=[];self.fail=fail;self.full=full
    async def ask(self,key,prompt,model,validator=None):
        self.calls.append((key,prompt))
        if self.fail and self.fail in key:raise EvaluationError('MOCK_EVALUATOR_FAILURE')
        if 'answer-kind' in key:
            payload={'kind':'full_abstention' if self.full else 'normal','contains_factual_claims':not self.full,'reason':'fixture'}
        elif 'relevancy' in key:payload={'question':'What is the storage temperature?','noncommittal':next(self.flags)}
        elif 'claims' in key:payload={'statements':[] if self.full else [self.row['response']]}
        elif 'coverage' in key:
            payload={'elements':[{'id':e['id'],'fulfilled':int(not self.full),'answer_quote':self.row['response'] if not self.full else '', 'reason':'fixture'} for e in self.row['required_elements']]}
        elif 'abstention' in key:
            payload={'explicitly_withholds_missing':True,'supplies_missing_as_fact':False,'unrelated_refusal':False,
                     'has_partial_answer':True,'partial_within_allowed':True,'partial_supported_by_oracle':True,
                     'partial_supported_by_retrieved':False,'answer_quote':self.row['response'],'source_ids':[],'reason':'fixture'}
        else:
            source='O:fixture-1' if 'oracle_support' in key else 'fixture-chunk'
            payload={'statements':[{'statement':self.row['response'],'reason':'fixture','verdict':1,
                        'evidence_ids':[source],'evidence_quotes':[self.row['oracle_evidence'][0]['text']]}]}
        out=model.model_validate(payload,strict=True)
        if validator:validator(out)
        return out


@pytest.fixture
def policy():
    from experiment.evaluation.common import EXPERIMENT
    return read(EXPERIMENT/'evaluation-policy.json')


def test_ragas_components_and_shared_claims(policy):
    row=synthetic_rows()[0];journal=FakeJournal(row)
    result=run(Evaluator(journal,Vectors(),policy).evaluate(row))
    assert not result['errors']
    assert result['metrics']['ar_raw']['value']==pytest.approx(1)
    assert result['metrics']['faithfulness']['value']==1
    assert result['metrics']['oracle_support']['value']==1
    claims=[p for k,p in journal.calls if '/claims-' in k]
    assert len(claims)==1 and 'O:fixture-1' not in claims[0] and 'fixture-chunk' not in claims[0]
    assert len(result['stages']['claims'])==1


@pytest.mark.parametrize('flags,expected',[((1,1,1),0),((1,0,1),-1),((0,0,0),-1)])
def test_ar_requires_all_noncommittal_and_preserves_negative_cosine(policy,flags,expected):
    row=synthetic_rows()[0]
    result=run(Evaluator(FakeJournal(row,flags),Vectors(negative=True),policy).evaluate(row))
    assert result['metrics']['ar_raw']['value']==pytest.approx(expected)
    assert len(result['stages']['answer_relevancy']['questions'])==3


def test_evaluator_failure_is_missing_and_not_zero(policy):
    row=synthetic_rows()[0]
    result=run(Evaluator(FakeJournal(row,fail='oracle_support'),Vectors(),policy).evaluate(row))
    assert result['metrics']['oracle_support']=={'value':None,'status':'N/A_EVAL_ERROR'}
    assert result['metrics']['required_coverage']['value']==1


def test_ar_same_text_in_query_and_generated_batch_does_not_overwrite_vector(policy):
    class BatchVectors(Vectors):
        async def aembed_texts(self,texts,**kwargs):
            self.last_response_vectors=[[0.9,0.1] for _ in texts]
            self.last_vectors.update(zip(texts,self.last_response_vectors))
            return self.last_response_vectors
    row=synthetic_rows()[0];row['user_input']='What is the storage temperature?'
    result=run(Evaluator(FakeJournal(row),BatchVectors(),policy).evaluate(row))
    assert 'answer_relevancy' not in result['errors']
    assert result['metrics']['ar_raw']['value']==pytest.approx(0.9/(0.82**0.5))


def test_generation_failure_zero_and_no_judge_calls(policy):
    row=synthetic_rows()[0];row['generation_status']='TIMEOUT';journal=FakeJournal(row)
    result=run(Evaluator(journal,Vectors(),policy).evaluate(row))
    assert result['metrics']['ar_report']['value']==0 and result['metrics']['ar_raw']['value'] is None
    assert result['metrics']['faithfulness']['status']=='N/A_NO_RESPONSE'
    assert not journal.calls


def test_no_facts_abstention_not_perfect_faithfulness(policy):
    row=synthetic_rows()[0];row['response']='I cannot answer.'
    result=run(Evaluator(FakeJournal(row,full=True),Vectors(),policy).evaluate(row))
    assert not result['errors']
    assert result['metrics']['oracle_support']['value']==0
    assert result['metrics']['required_coverage']['value']==0
    assert result['metrics']['faithfulness']['status']=='N/A_NO_CLAIM'
    assert result['metrics']['full_abstention']['value']==1


@pytest.mark.parametrize('condition,metric,expected',[('RAG','correct_abstention',0),('LLM_ONLY','corpus_unanswerable_abstention',1)])
def test_unanswerable_partial_support_scopes(policy,condition,metric,expected):
    row=synthetic_rows()[2];row['condition']=condition
    result=run(Evaluator(FakeJournal(row),Vectors(),policy).evaluate(row))
    assert result['metrics'][metric]['value']==expected
    assert result['metrics']['oracle_support']['status']=='N/A_OUT_OF_SCOPE'


@pytest.mark.parametrize('ids,quote',[(['wrong'],'12 C'),(['temperature','temperature'],'12 C'),(['temperature'],'invented')])
def test_coverage_rejects_missing_duplicate_ids_or_fabricated_quote(ids,quote):
    result=CoverageOutput(elements=[{'id':i,'fulfilled':1,'answer_quote':quote,'reason':'x'} for i in ids])
    with pytest.raises(EvaluationError):coverage_valid(result,[{'id':'temperature'}],'12 C')


def test_supported_claim_requires_real_source_quote():
    result=SupportOutput(statements=[{'statement':'A','reason':'x','verdict':1,'evidence_ids':['O1'],'evidence_quotes':['invented']}])
    with pytest.raises(EvaluationError):quotes_valid(result,{'O1':'real text'})


class FakeTransport:
    def __init__(self,valid=False,complete=True):self.calls=0;self.valid=valid;self.complete=complete
    async def send(self,prompt,model):
        self.calls+=1
        data={'kind':'normal','contains_factual_claims':True,'reason':'test'} if self.valid else {'bad':'schema'}
        return {'text':json.dumps(data),'complete':self.complete,'usage':{},'returned_model':'test-model'}


def test_first_valid_response_reused_and_prompt_change_blocked(tmp_path):
    transport=FakeTransport(valid=True);journal=Journal(tmp_path,transport,'identity')
    run(journal.ask('one','prompt',AnswerKind));run(journal.ask('one','prompt',AnswerKind))
    assert transport.calls==1
    with pytest.raises(EvaluationError,match='CACHED_REQUEST_MISMATCH'):
        run(journal.ask('one','changed',AnswerKind))


@pytest.mark.parametrize('valid,complete',[(False,True),(True,False)])
def test_retry_limit_persists_across_resume(tmp_path,monkeypatch,valid,complete):
    async def no_wait(*args):pass
    monkeypatch.setattr('experiment.evaluation.judge.asyncio.sleep',no_wait)
    transport=FakeTransport(valid,complete)
    for _ in range(2):
        with pytest.raises(EvaluationError,match='STAGE_ATTEMPTS_EXHAUSTED'):
            run(Journal(tmp_path,transport,'identity').ask('one','prompt',AnswerKind))
    assert transport.calls==3
    assert len(list(tmp_path.rglob('attempt-*.json')))==3


def test_openai_payload_uses_structured_output_and_no_store(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','sk-test-not-a-real-credential')
    captured={}
    async def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(model_dump=lambda **k:{'model':'gpt-6-sol','usage':{'input_tokens':1,'output_tokens':1}},
                               output_text='{}',status='completed')
    transport=Transport(profile_named('openai-sol'))
    transport.client=SimpleNamespace(responses=SimpleNamespace(create=create))
    result=run(transport.send('data',AnswerKind))
    assert result['model_consistent']
    assert captured['store'] is False
    assert captured['reasoning']=={'effort':'medium'}
    assert captured['text']['format']['strict'] is True
    assert 'temperature' not in captured and 'api_key' not in captured


def test_missing_credential_never_calls_remote(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    with pytest.raises(EvaluationError,match='API_KEY_NOT_CONFIGURED'):
        run(Transport(profile_named('openai-sol')).send('data',AnswerKind))


def test_redaction_on_disk(tmp_path,monkeypatch):
    key='test-private-value-for-unit-test';monkeypatch.setenv('OPENAI_API_KEY',key)
    save(tmp_path/'test.json',{'message':key,'authorization':'Bearer dummy'})
    assert key not in (tmp_path/'test.json').read_text(encoding='utf-8')
    assert read(tmp_path/'test.json')['authorization']=='[REDACTED]'


@pytest.mark.parametrize('change',[{'base_url':'http://example.com:11434'},{'model':'gemma4:cloud'}])
def test_local_profile_cannot_route_to_remote(change):
    p=profile_named('local-gemma4-12b');p.update(change)
    with pytest.raises(EvaluationError):validate_profile(p)


def test_context_guard_never_silently_truncates():
    p=profile_named('installed-4b-smoke');p['num_ctx']=1024
    with pytest.raises(EvaluationError,match='CONSERVATIVE_CONTEXT_LIMIT_EXCEEDED'):
        run(Transport(p).send('text',AnswerKind))


def test_existing_generator_cannot_be_selected_for_formal_benchmark():
    with pytest.raises(EvaluationError,match='SMOKE_MODEL_CANNOT_SCORE_BENCHMARK'):
        prepare('forbidden-test','installed-4b-smoke')


def test_all_actual_packet_hashes_and_first_round_pairs():
    rows,policy,files=source_packet('formal-v1')
    assert len(rows)==120 and len(files)>120
    assert policy['quality_round']==1


def test_pairwise_summary_uses_common_valid_only(tmp_path):
    manifest={'id':'test','mode':'benchmark','created_at':'test','profile':{'model':'fixture','provider':'mock'},
              'source_run':'fixture','identity_hash':'identity'}
    save(tmp_path/'manifest.json',manifest)
    expected=[]
    for q,c,value in [('Q1','LLM_ONLY',0.2),('Q1','RAG',0.7),('Q2','RAG',1.0),('Q2','LLM_ONLY',None)]:
        key=q+'-'+c;expected.append({'attempt_key':key})
        row={'attempt_key':key,'question_id':q,'type':'single-evidence','condition':c,'errors':{},
             'metrics':{m:{'value':value,'status':'OK' if value is not None else 'N/A_EVAL_ERROR'} for m in (
             'ar_raw','ar_report','oracle_support','required_coverage','faithfulness','full_abstention','correct_abstention','corpus_unanswerable_abstention')}}
        save(tmp_path/'results'/(key+'.json'),{'identity_hash':'identity','result_hash':fingerprint(row),'result':row})
    save(tmp_path/'inputs.json',{'rows':expected})
    summary=summarize(tmp_path)
    paired=next(x for x in summary['paired'] if x['metric']=='ar_report' and x['type']=='all')
    assert paired['paired_n']==1 and paired['mean_rag_minus_llm_only']==pytest.approx(0.5)
    assert summary['final_quality_claims_ready'] is False


def test_process_lock_detection():
    import os
    assert pid_alive(os.getpid())


def test_atomic_save_retries_temporary_windows_lock_without_new_judge_call(tmp_path,monkeypatch):
    from pathlib import Path
    original=Path.replace;failures=[]
    def sometimes_locked(source,target):
        if Path(target).name=='attempt-1.json' and len(failures)<2:
            failures.append(1);raise PermissionError('simulated file sharing lock')
        return original(source,target)
    monkeypatch.setattr(Path,'replace',sometimes_locked)
    monkeypatch.setattr('experiment.evaluation.common.time.sleep',lambda _:None)
    transport=FakeTransport(valid=True)
    result=run(Journal(tmp_path,transport,'identity').ask('one','prompt',AnswerKind))
    assert result.kind=='normal' and len(failures)==2 and transport.calls==1


def test_permanent_io_failure_preserves_previous_artifact(tmp_path,monkeypatch):
    from pathlib import Path
    save(tmp_path/'value.json',{'old':True})
    def locked(*args):raise PermissionError('simulated permanent lock')
    monkeypatch.setattr(Path,'replace',locked)
    monkeypatch.setattr('experiment.evaluation.common.time.sleep',lambda _:None)
    with pytest.raises(EvaluationError,match='LOCAL_ARTIFACT_IO_ERROR'):save(tmp_path/'value.json',{'new':True})
    assert read(tmp_path/'value.json')=={'old':True}
    assert len(list(tmp_path.glob('*.tmp')))==1


def test_saved_response_recovered_without_another_paid_call(tmp_path):
    from experiment.evaluation.judge import save_attempt
    transport=FakeTransport(valid=True);journal=Journal(tmp_path,transport,'identity')
    run(journal.ask('one','prompt',AnswerKind))
    path=tmp_path/'one/attempt-1.json';record=read(path)
    record['status']='STARTED';record.pop('parsed');save_attempt(path,record)
    result=run(journal.ask('one','prompt',AnswerKind))
    assert result.kind=='normal' and transport.calls==1
    assert read(path)['recovered_saved_response'] is True


def test_recovery_rejects_changed_provider_model(tmp_path):
    from experiment.evaluation.judge import save_attempt
    transport=FakeTransport(valid=True);journal=Journal(tmp_path,transport,'identity')
    run(journal.ask('one','prompt',AnswerKind))
    path=tmp_path/'one/attempt-1.json';record=read(path)
    record['status']='STARTED';record.pop('parsed')
    record['provider']['model_consistent']=False;save_attempt(path,record)
    with pytest.raises(EvaluationError,match='RETURNED_MODEL_CHANGED'):
        run(journal.ask('one','prompt',AnswerKind))
    assert transport.calls==1
