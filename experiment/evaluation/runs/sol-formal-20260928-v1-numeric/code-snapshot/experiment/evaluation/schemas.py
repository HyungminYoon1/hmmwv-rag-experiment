"""Structured judgments. Numeric scores are computed by code, not by the judge."""
from typing import Literal
from pydantic import BaseModel, ConfigDict
from ragas.metrics.collections.faithfulness.util import NLIStatementOutput, StatementFaithfulnessAnswer


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class AnswerKind(StrictModel):
    kind: Literal['normal', 'partial_abstention', 'full_abstention', 'irrelevant_refusal']
    contains_factual_claims: bool
    reason: str


class LocatedStatement(StatementFaithfulnessAnswer):
    model_config = ConfigDict(extra='forbid')
    evidence_ids: list[str]
    evidence_quotes: list[str]


class SupportOutput(NLIStatementOutput):
    model_config = ConfigDict(extra='forbid')
    statements: list[LocatedStatement]


class ElementJudgment(StrictModel):
    id: str
    fulfilled: Literal[0, 1]
    answer_quote: str
    reason: str


class CoverageOutput(StrictModel):
    elements: list[ElementJudgment]


class AbstentionOutput(StrictModel):
    explicitly_withholds_missing: bool
    supplies_missing_as_fact: bool
    unrelated_refusal: bool
    has_partial_answer: bool
    partial_within_allowed: bool
    partial_supported_by_oracle: bool
    partial_supported_by_retrieved: bool
    answer_quote: str
    source_ids: list[str]
    reason: str

