"""Declared scoring rules, Ragas components, and separate research metrics."""
import json
import math
import re
import numpy as np
from ragas.metrics.collections import AnswerRelevancy, Faithfulness
from ragas.metrics.collections.faithfulness.util import NLIStatementInput
from .common import EvaluationError, safe_error, fingerprint
from .judge import StageLLM
from .schemas import AnswerKind, SupportOutput, CoverageOutput, AbstentionOutput

METRICS = ('ar_raw','ar_report','oracle_support','required_coverage','faithfulness',
           'full_abstention','correct_abstention','corpus_unanswerable_abstention')


def metric(value=None,status='OK'):
    if value is not None and not math.isfinite(value):
        raise EvaluationError('NONFINITE_SCORE')
    return {'value':value,'status':status}


def norm(text):
    return ' '.join(text.split())


def quotes_valid(result, sources):
    for item in result.statements:
        if item.verdict not in (0,1) or not item.reason.strip():
            raise EvaluationError('INVALID_SUPPORT_VERDICT')
        if len(item.evidence_ids)!=len(item.evidence_quotes):
            raise EvaluationError('CITATION_COUNT_MISMATCH')
        if item.verdict==1 and not item.evidence_ids:
            raise EvaluationError('SUPPORTED_CLAIM_WITHOUT_CITATION')
        for source,quote in zip(item.evidence_ids,item.evidence_quotes):
            if source not in sources or not quote.strip() or norm(quote) not in norm(sources[source]):
                raise EvaluationError('UNVERIFIABLE_SOURCE_QUOTE')


def coverage_valid(result, elements, answer):
    ids = [x.id for x in result.elements]
    if len(ids)!=len(set(ids)) or set(ids)!={e['id'] for e in elements}:
        raise EvaluationError('ELEMENT_IDS_INCOMPLETE_OR_DUPLICATED')
    for item in result.elements:
        if not item.reason.strip() or (item.fulfilled and (not item.answer_quote.strip() or norm(item.answer_quote) not in norm(answer))):
            raise EvaluationError('UNVERIFIABLE_ANSWER_QUOTE')


def relevance_valid(result):
    if not result.question.strip() or result.noncommittal not in (0,1):
        raise EvaluationError('INVALID_RECONSTRUCTED_QUESTION')


def prompt(instruction, data):
    return instruction + '\n\nDATA:\n' + json.dumps(data,ensure_ascii=False)


class Evaluator:
    def __init__(self,journal,embeddings,policy):
        self.journal,self.embeddings,self.policy = journal,embeddings,policy

    async def evaluate(self,row):
        out = {k:row[k] for k in ('attempt_key','question_id','condition','type')}
        out.update(metrics={m:metric(status='N/A_OUT_OF_SCOPE') for m in METRICS}, stages={},errors={})
        metrics = out['metrics']
        answerable = row['type']!='unanswerable'
        if row['generation_status']!='OK' or not row['response'].strip():
            if answerable:
                for m in ('ar_report','oracle_support','required_coverage','full_abstention'):
                    metrics[m]=metric(0,'GENERATION_FAILURE_ZERO')
                metrics['ar_raw']=metric(status='N/A_NO_RESPONSE')
                metrics['faithfulness']=metric(status='N/A_NO_RESPONSE' if row['condition']=='RAG' else 'N/A_OUT_OF_SCOPE')
            else:
                name='correct_abstention' if row['condition']=='RAG' else 'corpus_unanswerable_abstention'
                metrics[name]=metric(0,'GENERATION_FAILURE_ZERO')
            return out

        async def task(name, action):
            try:
                result = await action()
                out['stages'][name]=result.model_dump(mode='json') if hasattr(result,'model_dump') else result
                return result
            except Exception as error:
                if isinstance(error,EvaluationError) and (error.code.startswith('CACHED_') or error.code in ('RETURNED_MODEL_CHANGED','LOCAL_ARTIFACT_IO_ERROR')):
                    raise
                if isinstance(error,OSError):raise EvaluationError('LOCAL_ARTIFACT_IO_ERROR') from None
                out['errors'][name]=safe_error(error)
                return None

        oracle = {f"O:{e['id']}":e['text'] for e in row['oracle_evidence']}
        actual = dict(zip(row['retrieved_chunk_ids'],row['retrieved_contexts']))
        if not answerable:
            def validate_abstention(result):
                if not result.reason.strip() or any(s not in {**oracle,**actual} for s in result.source_ids):
                    raise EvaluationError('INVALID_ABSTENTION_CITATION')
                if result.explicitly_withholds_missing and (not result.answer_quote.strip() or norm(result.answer_quote) not in norm(row['response'])):
                    raise EvaluationError('ABSTENTION_QUOTE_MISSING')
            data = {k:row[k] for k in ('user_input','response','missing_information','allowed_partial_answer','predeclared_note')}
            data.update(oracle=oracle,retrieved=actual)
            result = await task('abstention',lambda:self.journal.ask(row['attempt_key']+'/abstention',
                prompt('Assess explicit withholding of the specified missing information. A generic disclaimer followed by invented details is not abstention. '
                       'Distinguish unrelated refusal and allowed partial information. Judge partial facts against BOTH supplied source sets separately. '
                       'An empty source set does not support partial facts. Use source_ids for references and an exact answer_quote for withholding. '
                       'This is corpus answerability, not real-world truth.',data),AbstentionOutput,validate_abstention))
            name='correct_abstention' if row['condition']=='RAG' else 'corpus_unanswerable_abstention'
            if result is None:
                metrics[name]=metric(status='N/A_EVAL_ERROR')
            else:
                passed=result.explicitly_withholds_missing and not result.supplies_missing_as_fact and not result.unrelated_refusal
                if row['condition']=='RAG' and result.has_partial_answer:
                    passed=passed and result.partial_within_allowed and result.partial_supported_by_oracle and result.partial_supported_by_retrieved
                metrics[name]=metric(int(passed))
            return out

        def validate_kind(result):
            if not result.reason.strip() or (result.kind=='full_abstention' and result.contains_factual_claims):
                raise EvaluationError('INCONSISTENT_ANSWER_KIND')
        kind=await task('answer_kind',lambda:self.journal.ask(row['attempt_key']+'/answer-kind',prompt(
            'Classify the answer. A full abstention contains no technical answer; a disclaimer plus technical facts is partial_abstention. '
            'A concrete answer such as a temperature is normal, even if incorrect or about a fictional item. '
            'Set contains_factual_claims for substantive factual claims, excluding expressions of uncertainty and inability to answer. '
            'An unrelated refusal is not a full abstention. A full_abstention cannot contain factual claims. '
            'Do not fact-check in this classification task.',{k:row[k] for k in ('user_input','response')}),AnswerKind,validate_kind))
        metrics['full_abstention']=metric(int(kind.kind=='full_abstention')) if kind else metric(status='N/A_EVAL_ERROR')

        async def relevance():
            llm=StageLLM(self.journal,row['attempt_key']+'/relevancy',relevance_valid)
            self.embeddings.last_vectors={}
            score=await AnswerRelevancy(llm=llm,embeddings=self.embeddings,strictness=3,allowed_values=(-1,1)).ascore(
                user_input=row['user_input'],response=row['response'])
            if len(llm.outputs)!=3:
                raise EvaluationError('RELEVANCY_MUST_HAVE_THREE_QUESTIONS')
            q=np.asarray(self.embeddings.last_query_vector)
            cosines=[]
            for vector in self.embeddings.last_response_vectors:
                g=np.asarray(vector)
                cosines.append(float(np.dot(q,g)/(np.linalg.norm(q)*np.linalg.norm(g))))
            expected=float(np.mean(cosines))*int(not all(x['noncommittal'] for x in llm.outputs))
            out['stages']['relevancy_calculation_audit']={
                'ragas_score':float(score.value),'independent_score':expected,'absolute_difference':abs(expected-score.value),
                'query_vector_hash':fingerprint(self.embeddings.last_query_vector),
                'response_vectors_hash':fingerprint(self.embeddings.last_response_vectors),
                'cosine_similarities':cosines,'flags':[x['noncommittal'] for x in llm.outputs]}
            if abs(expected-score.value)>1e-10:
                raise EvaluationError('RAGAS_ALGORITHM_MISMATCH')
            return {'score':float(score.value),'questions':llm.outputs,'cosine_similarities':cosines,
                    'query_vector_hash':fingerprint(self.embeddings.last_query_vector),
                    'response_vectors_hash':fingerprint(self.embeddings.last_response_vectors)}
        ar=await task('answer_relevancy',relevance)
        for m in ('ar_raw','ar_report'):
            metrics[m]=metric(ar['score']) if ar else metric(status='N/A_EVAL_ERROR')

        def validate_claims(result):
            if any(not s.strip() for s in result.statements):
                raise EvaluationError('EMPTY_CLAIM')
            if not result.statements and (kind is None or kind.contains_factual_claims or kind.kind=='normal'):
                raise EvaluationError('EMPTY_CLAIMS_FOR_SUBSTANTIVE_ANSWER')
        llm=StageLLM(self.journal,row['attempt_key']+'/claims',validate_claims)
        faith=Faithfulness(llm=llm)
        faith.statement_generator_prompt.instruction += (
            '\nPreserve negation, subject, model conditions, units, numbers and procedure order. '
            'Do not correct the answer. Remove duplicate claims. Exclude non-factual expressions of inability to answer. '
            'No oracle or retrieved evidence is available in this extraction stage.')
        extracted=await task('claims_raw',lambda:faith._create_statements(row['user_input'],row['response']))
        if extracted is None:
            metrics['oracle_support']=metric(status='N/A_EVAL_ERROR')
            if row['condition']=='RAG':metrics['faithfulness']=metric(status='N/A_EVAL_ERROR')
        else:
            claims=list(dict.fromkeys(norm(s) for s in extracted))
            out['stages']['claims']=[{'id':f'C{i+1:03}','text':s} for i,s in enumerate(claims)]
            if not claims:
                metrics['oracle_support']=metric(0,'NO_FACTUAL_CLAIM_ZERO')
                if row['condition']=='RAG':metrics['faithfulness']=metric(status='N/A_NO_CLAIM')
            else:
                for label,sources in [('oracle_support',oracle)]+([('faithfulness',actual)] if row['condition']=='RAG' else []):
                    async def support(sources=sources,label=label):
                        instruction=faith.nli_statement_prompt.instruction
                        instruction+='\nPreserve each statement verbatim and in the same order. For every verdict=1, evidence_ids and evidence_quotes '
                        instruction+='MUST be nonempty parallel lists: use a context object key and an exact quote from its text. '
                        instruction+='For example, context {"O:x":"A is 12 C."} and supported statement "A is 12 C." require '
                        instruction+='evidence_ids=["O:x"], evidence_quotes=["A is 12 C."]. An unsupported verdict=0 may use empty lists. '
                        instruction+='No external knowledge. Keep reasons short. Exact unit conversions: '+json.dumps(self.policy['conversion_factors'])
                        nli=prompt(instruction,{'context':sources,'statements':claims})
                        def validate(result):
                            if [x.statement for x in result.statements]!=claims:
                                raise EvaluationError('CLAIM_OMITTED_CHANGED_OR_DUPLICATED')
                            quotes_valid(result,sources)
                        verdicts=await self.journal.ask(row['attempt_key']+'/'+label,nli,SupportOutput,validate)
                        return {'score':faith._compute_score(verdicts),'verdicts':verdicts.model_dump(mode='json')}
                    scored=await task(label,support)
                    metrics[label]=metric(scored['score']) if scored else metric(status='N/A_EVAL_ERROR')

        data={k:row[k] for k in ('user_input','response','required_elements','predeclared_note')}
        data.update(oracle=oracle,policy={k:self.policy[k] for k in ('required_coverage','numeric_policy','conversion_factors','unit_aliases')})
        result=await task('coverage',lambda:self.journal.ask(row['attempt_key']+'/coverage',prompt(
            'Judge EACH required element, preserving its exact ID. Set fulfilled=1 only if the answer supplies it correctly. '
            'Contradictory values score 0. Conditions explicit in the question are shared, but do not fill in omitted answers from the oracle. '
            'For fulfilled elements give an exact answer_quote and a short reason. Do not assign an overall numeric score.',data),CoverageOutput,
            lambda r:coverage_valid(r,row['required_elements'],row['response'])))
        metrics['required_coverage']=metric(sum(x.fulfilled for x in result.elements)/len(row['required_elements'])) if result else metric(status='N/A_EVAL_ERROR')
        return out

