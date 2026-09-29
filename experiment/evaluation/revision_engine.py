"""Post-review v2 scoring with unchanged relevance and a frozen, auditable rubric."""
import copy
import json
from typing import Literal
from .common import EvaluationError
from .engine import METRICS, metric, norm, prompt, quotes_valid, coverage_valid
from .schemas import StrictModel, SupportOutput, CoverageOutput


class ExtractedFact(StrictModel):
    statement: str
    answer_quote: str


class RevisedClaims(StrictModel):
    shared_conditions: list[str]
    statements: list[ExtractedFact]
    excluded_metadata: list[str]


class RevisedAbstention(StrictModel):
    explicitly_withholds_missing: bool
    supplies_missing_as_fact: bool
    unrelated_refusal: bool
    answer_quote: str
    partial_claims: list[str]
    partial_within_allowed: bool
    oracle_verdicts: SupportOutput
    retrieved_verdicts: SupportOutput
    reason: str


def validate_claims(result, answer):
    seen = set()
    for item in result.statements:
        text = norm(item.statement)
        if not text or text in seen:
            raise EvaluationError('EMPTY_OR_DUPLICATE_CLAIM')
        seen.add(text)
        if not item.answer_quote.strip() or norm(item.answer_quote) not in norm(answer):
            raise EvaluationError('CLAIM_WITHOUT_REAL_ANSWER_QUOTE')


def validate_partial(result, answer, oracle, actual):
    if not result.reason.strip():
        raise EvaluationError('EMPTY_ABSTENTION_REASON')
    if result.explicitly_withholds_missing and (not result.answer_quote.strip() or norm(result.answer_quote) not in norm(answer)):
        raise EvaluationError('ABSTENTION_WITHOUT_REAL_QUOTE')
    if len(result.partial_claims) != len(set(result.partial_claims)) or any(not x.strip() for x in result.partial_claims):
        raise EvaluationError('DUPLICATE_OR_EMPTY_PARTIAL_CLAIM')
    for verdicts, sources in [(result.oracle_verdicts, oracle), (result.retrieved_verdicts, actual)]:
        if [v.statement for v in verdicts.statements] != result.partial_claims:
            raise EvaluationError('PARTIAL_CLAIMS_CHANGED_OR_OMITTED')
        quotes_valid(verdicts, sources)


def abstention_scores(result, condition):
    withheld = result.explicitly_withholds_missing and not result.supplies_missing_as_fact and not result.unrelated_refusal
    oracle_ok = all(v.verdict == 1 for v in result.oracle_verdicts.statements)
    actual_ok = all(v.verdict == 1 for v in result.retrieved_verdicts.statements)
    passed = withheld
    if condition == 'RAG' and result.partial_claims:
        passed = passed and result.partial_within_allowed and oracle_ok and actual_ok
    return {'value': int(passed), 'withholding_only': int(withheld), 'partial_claim_count': len(result.partial_claims),
            'partial_supported_by_oracle': oracle_ok if result.partial_claims else None,
            'partial_supported_by_retrieved': actual_ok if result.partial_claims else None}


class RevisedEvaluator:
    def __init__(self, journal, policy):
        self.journal, self.policy = journal, policy

    async def evaluate(self, row, previous):
        out = {k: row[k] for k in ('attempt_key', 'question_id', 'condition', 'type')}
        out.update(metrics={m: metric(status='N/A_OUT_OF_SCOPE') for m in METRICS}, stages={}, errors={})
        answer = row['response']
        if row['generation_status'] != 'OK' or not answer.strip():
            raise EvaluationError('REVISION_EXPECTS_PRESERVED_SUCCESSFUL_GENERATION')
        oracle = {f"O:{e['id']}": e['text'] for e in row['oracle_evidence']}
        actual = dict(zip(row['retrieved_chunk_ids'], row['retrieved_contexts']))
        policy = self.policy

        # Evaluation failures are saved as missing. Integrity/storage failures stop the run.
        async def stage(name, action):
            from .common import safe_error
            try:
                value = await action()
                out['stages'][name] = value.model_dump(mode='json') if hasattr(value, 'model_dump') else value
                return value
            except Exception as e:
                if isinstance(e, OSError) or (isinstance(e, EvaluationError) and (e.code.startswith('CACHED_') or e.code in ('LOCAL_ARTIFACT_IO_ERROR', 'RETURNED_MODEL_CHANGED'))):
                    raise
                out['errors'][name] = safe_error(e)
                return None

        if row['type'] == 'unanswerable':
            data = {k: row[k] for k in ('user_input', 'response', 'missing_information', 'allowed_partial_answer', 'predeclared_note')}
            data.update(oracle=oracle, retrieved=actual,
                        policy={k: policy[k] for k in ('unanswerable', 'claims', 'excluded_claims', 'source_location', 'support_reasoning')})
            instruction = (
                'Assess explicit withholding of the requested COMPLETE missing procedure. '
                'Extract every related substantive technical assertion into partial_claims, including diagnostic facts and model identity even if not a usable requested step. '
                'Do not put statements about the supplied excerpts being unavailable into technical partial_claims. '
                'Give an exact withholding answer_quote. A disclaimer does not undo invented missing steps. '
                'For each partial claim give separate oracle_verdicts and retrieved_verdicts IN THE SAME ORDER, preserving the claim verbatim. '
                'Every supported verdict needs a source object key and exact source quote in parallel evidence_ids/evidence_quotes lists. '
                'An empty source set supports nothing. Mark unrelated source procedures as inapplicable to the requested component. '
                'A warning repeated from another procedure is allowed only with its actual component/operation qualifier retained. '
                'Set partial_within_allowed only for the declared partial scope. Do not use outside knowledge; give brief reasons.')
            result = await stage('abstention', lambda: self.journal.ask(row['attempt_key'] + '/abstention-v2',
                                prompt(instruction, data), RevisedAbstention,
                                lambda r: validate_partial(r, answer, oracle, actual)))
            name = 'correct_abstention' if row['condition'] == 'RAG' else 'corpus_unanswerable_abstention'
            if result is None:
                out['metrics'][name] = metric(status='N/A_EVAL_ERROR')
            else:
                scores = abstention_scores(result, row['condition'])
                out['metrics'][name] = metric(scores['value'])
                out['stages']['abstention_components'] = scores
            return out

        # These stages do not use oracle/rubric and have not changed in this revision.
        for name in ('ar_raw', 'ar_report', 'full_abstention'):
            out['metrics'][name] = copy.deepcopy(previous['metrics'][name])
        for name in ('answer_kind', 'answer_relevancy', 'relevancy_calculation_audit', 'relevancy_numeric_recalculation'):
            if name in previous['stages']:
                out['stages'][name] = copy.deepcopy(previous['stages'][name])
        out['stages']['inherited_metrics'] = ['ar_raw', 'ar_report', 'full_abstention']
        data = {k: row[k] for k in ('user_input', 'response')}
        data['policy'] = {k: policy[k] for k in ('claims', 'excluded_claims', 'source_location')}
        instruction = (
            'Extract atomic technical factual claims from the answer. No oracle or retrieved evidence is available. '
            'For every claim give a short exact answer_quote supporting that the ANSWER made the claim. '
            'Explicitly identify shared operating conditions and carry applicable conditions into the text of EVERY affected statement. '
            'Example: for a question restricted to wet operation, an answer saying "Fluid X only" becomes "During wet operation, fluid X only". '
            'Do not turn uncertainty into certainty, do not repair incorrect facts, and do not supply missing technical answers from the question. '
            'A question section label is a locator, not automatically a factual assertion by the answer. '
            'Deduplicate repeated meanings. List input-presence, self-provenance, citation availability and pure inability statements in excluded_metadata. '
            'Keep substantive technical speculation and wrong model/applicability claims in statements. Empty statements are valid only if no technical claims remain.')
        claims = await stage('claim_extraction', lambda: self.journal.ask(row['attempt_key'] + '/claims-v2',
                            prompt(instruction, data), RevisedClaims, lambda r: validate_claims(r, answer)))
        if claims is None:
            out['metrics']['oracle_support'] = metric(status='N/A_EVAL_ERROR')
            if row['condition'] == 'RAG': out['metrics']['faithfulness'] = metric(status='N/A_EVAL_ERROR')
        else:
            texts = [f.statement for f in claims.statements]
            out['stages']['claims'] = [{'id': f'C{i+1:03}', 'text': f.statement, 'answer_quote': f.answer_quote} for i, f in enumerate(claims.statements)]
            if not texts:
                out['metrics']['oracle_support'] = metric(0, 'NO_FACTUAL_CLAIM_ZERO')
                if row['condition'] == 'RAG': out['metrics']['faithfulness'] = metric(status='N/A_NO_CLAIM')
            else:
                for label, sources in [('oracle_support', oracle)] + ([('faithfulness', actual)] if row['condition'] == 'RAG' else []):
                    def validate(result, sources=sources):
                        if [x.statement for x in result.statements] != texts:
                            raise EvaluationError('CLAIM_CHANGED_OMITTED_OR_DUPLICATED')
                        quotes_valid(result, sources)
                    context_data = {'question_for_conditions_only': row['user_input'], 'answer_for_scope_only': answer,
                                    'shared_conditions': claims.shared_conditions, 'statements': texts, 'context': sources,
                                    'policy': {k: policy[k] for k in ('source_location', 'support_reasoning', 'numeric_policy', 'conversion_factors')}}
                    instr = ('Judge each statement ONLY against the supplied context; do not use external knowledge. '
                             'Use the question and answer ONLY to retain shared operating conditions, never as evidence that a technical statement is true. '
                             'Preserve each statement verbatim and in order. A conditional statement must not be judged against a different operating case. '
                             'Source passages may jointly support an explicit inclusion/comparison. Do not require an identical section title for an equivalent fact. '
                             'For verdict=1 give nonempty parallel evidence_ids/evidence_quotes with a context key and exact quote. '
                             'For verdict=0 short reasons and empty citations are allowed. Do not infer omitted source facts.')
                    supported = await stage(label, lambda label=label, context_data=context_data, validate=validate:
                                            self.journal.ask(row['attempt_key'] + '/' + label + '-v2', prompt(instr, context_data), SupportOutput, validate))
                    if supported is None:
                        out['metrics'][label] = metric(status='N/A_EVAL_ERROR')
                    else:
                        value = sum(s.verdict for s in supported.statements) / len(texts)
                        out['metrics'][label] = metric(value)
                        out['stages'][label] = {'score': value, 'verdicts': supported.model_dump(mode='json')}

        coverage_data = {k: row[k] for k in ('user_input', 'response', 'required_elements', 'predeclared_note')}
        coverage_data.update(oracle=oracle, policy={k: policy[k] for k in ('required_coverage', 'numeric_policy', 'conversion_factors', 'source_location')})
        coverage = await stage('coverage', lambda: self.journal.ask(row['attempt_key'] + '/coverage-v2',
                               prompt('Judge every required element with its original ID. Give 0 or 1 and an exact answer_quote for every fulfilled element. '
                                      'Follow optional-detail, compound-element and cautious-concrete-answer rules exactly. '
                                      'Do not fill missing answer content from evidence. Contradictory values invalidate the affected element. '
                                      'Give brief reasons; code computes the average.', coverage_data), CoverageOutput,
                               lambda r: coverage_valid(r, row['required_elements'], answer)))
        out['metrics']['required_coverage'] = metric(sum(e.fulfilled for e in coverage.elements)/len(row['required_elements'])) if coverage else metric(status='N/A_EVAL_ERROR')
        return out
