# 답변 평가 local-smoke-20260928-v1

- 상태: COMPLETED_WITH_EVAL_ERRORS (3/3)
- 평가 모델: kidet-qwen3-4b-instruct-2507:q4-k-m-v1
- 구분: SYNTHETIC_FUNCTIONAL_TEST
- 연구자 원문 검토 및 수동평가 대조: PENDING
- 평가기 오류는 결측이며, 생성 실패 0점과 구분한다. 자동평가가 완료되어도 최종 품질 검증 완료를 뜻하지 않는다.

| 조건 | 대상 | 지표 | 평균 | 유효 답변 수 | 처리 답변 수 |
|---|---|---|---:|---:|---:|
| RAG | all | ar_raw | — | 0 | 3 |
| RAG | all | ar_report | — | 0 | 3 |
| RAG | all | oracle_support | 0.0000 | 1 | 3 |
| RAG | all | required_coverage | 0.5000 | 2 | 3 |
| RAG | all | faithfulness | 0.0000 | 1 | 3 |
| RAG | all | full_abstention | 1.0000 | 2 | 3 |
| RAG | all | correct_abstention | 1.0000 | 1 | 3 |
| RAG | all | corpus_unanswerable_abstention | — | 0 | 3 |

짝비교는 두 조건 모두 유효한 동일 문항에 한정한다. Faithfulness와 두 답변불가 지표는 적용 범위가 달라 직접 짝비교하지 않는다.
상세 판정과 근거 인용은 results/, 원본 평가 응답과 재시도 이력은 calls/에 보관한다.
