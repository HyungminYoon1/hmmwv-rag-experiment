import asyncio
from copy import deepcopy
import pytest
from experiment.evaluation.common import EXPERIMENT, EvaluationError, read
from experiment.evaluation.revision_engine import RevisedClaims, RevisedAbstention, RevisedEvaluator, validate_claims, validate_partial, abstention_scores
from experiment.evaluation.revision_runner import smoke_rows


def test_gold_v2_preserves_questions_and_does_not_overgrant_shared_group():
    old = {q['id']: q for q in read(EXPERIMENT/'gold-v1/questions.json')}
    new = {q['id']: q for q in read(EXPERIMENT/'gold-v2/questions.json')}
    assert len(new) == 60
    for qid, q in old.items():
        for name in ('question', 'type', 'missing_information', 'answerable_in_scope'):
            assert q[name] == new[qid][name]
    sets = lambda qid: [c for g in new[qid]['evidence'] for c in g['sufficient_chunk_sets']]
    assert ['C002086'] in sets('M29') and ['C002086'] not in sets('S06')
    assert ['C001112'] in sets('M15') and ['C001112'] not in sets('M19')
    assert ['C001117', 'C001118'] in sets('M16')


def test_optional_reason_fix_does_not_remove_explicit_why_requirement():
    gold = {q['id']: q for q in read(EXPERIMENT/'gold-v2/questions.json')}
    assert 'optional' in gold['M18']['required_elements'][2]['text']
    assert 'damages' in gold['M23']['required_elements'][1]['text']
    assert 'C003672' in [e['id'] for e in gold['U05']['oracle_evidence']]


def test_claim_quote_cannot_be_invented():
    value = RevisedClaims(shared_conditions=[], excluded_metadata=[], statements=[{'statement': 'A=12', 'answer_quote': 'A=12'}])
    with pytest.raises(EvaluationError): validate_claims(value, 'I cannot answer')


def partial(verdict=1):
    claim = {'statement': 'Inspect cracks.', 'reason': 'fixture', 'verdict': verdict,
             'evidence_ids': ['x'] if verdict else [], 'evidence_quotes': ['Inspect cracks.'] if verdict else []}
    return RevisedAbstention(explicitly_withholds_missing=True, supplies_missing_as_fact=False, unrelated_refusal=False,
                            answer_quote='Full procedure unavailable.', partial_claims=['Inspect cracks.'], partial_within_allowed=True,
                            oracle_verdicts={'statements': [claim]}, retrieved_verdicts={'statements': [claim]}, reason='fixture')


def test_partial_checks_cannot_be_skipped_by_claiming_no_usable_step():
    value = partial(0)
    assert abstention_scores(value, 'RAG')['value'] == 0
    assert abstention_scores(value, 'LLM_ONLY')['value'] == 1
    value.retrieved_verdicts.statements = []
    with pytest.raises(EvaluationError): validate_partial(value, value.answer_quote, {}, {})


def test_partial_actual_and_oracle_citations_cannot_cross_source_sets():
    value = partial()
    with pytest.raises(EvaluationError): validate_partial(value, value.answer_quote, {'x': 'Inspect cracks.'}, {})


class Journal:
    def __init__(self): self.calls = []
    async def ask(self, key, prompt, model, validator=None):
        self.calls.append((key, prompt))
        if '/claims-' in key:
            assert 'O:fixture' not in prompt and 'freezing storage uses fluid B' not in prompt
            data = {'shared_conditions': ['non-freezing storage'], 'excluded_metadata': ['No supplied excerpts.'],
                    'statements': [{'statement': 'In non-freezing storage use fluid A only.', 'answer_quote': 'use fluid A only.'}]}
        elif '/coverage-' in key:
            data = {'elements': [{'id': 'fluid', 'fulfilled': 1, 'answer_quote': 'use fluid A only.', 'reason': 'condition shared'}]}
        else:
            data = {'statements': [{'statement': 'In non-freezing storage use fluid A only.', 'verdict': 1,
                      'reason': 'same non-freezing condition', 'evidence_ids': ['O:fixture' if '/oracle_' in key else 'fixture'],
                      'evidence_quotes': ['non-freezing storage requires fluid A only']}]}
        result = model.model_validate(data)
        if validator: validator(result)
        return result


def test_cached_relevancy_preserved_and_same_claims_sent_to_both_support_tasks():
    row = smoke_rows()[0]; journal = Journal()
    old = {'metrics': {k: {'value': v, 'status': 'OK'} for k, v in [('ar_raw', -0.2), ('ar_report', -0.2), ('full_abstention', 0)]}, 'stages': {}}
    result = asyncio.run(RevisedEvaluator(journal, read(EXPERIMENT/'gold-v2/evaluation-policy.json')).evaluate(row, old))
    assert not result['errors']
    assert result['metrics']['ar_report']['value'] == -0.2
    assert result['metrics']['oracle_support']['value'] == result['metrics']['faithfulness']['value'] == 1
    assert len(journal.calls) == 4
    assert all('relevancy' not in key for key, _ in journal.calls)
