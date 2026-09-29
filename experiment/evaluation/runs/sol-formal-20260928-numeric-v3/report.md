# 답변 평가 sol-formal-20260928-numeric-v3

- 상태: COMPLETED (120/120)
- 평가 모델: gpt-6-sol
- 구분: PROVISIONAL_AUTOMATIC_SCORES
- 연구자 원문 검토 및 수동평가 대조: PENDING
- 평가기 오류는 결측이며, 생성 실패 0점과 구분한다. 자동평가가 완료되어도 최종 품질 검증 완료를 뜻하지 않는다.

| 조건 | 대상 | 지표 | 평균 | 유효 답변 수 | 처리 답변 수 |
|---|---|---|---:|---:|---:|
| LLM_ONLY | all | ar_raw | 0.7267 | 50 | 60 |
| LLM_ONLY | all | ar_report | 0.7267 | 50 | 60 |
| LLM_ONLY | all | oracle_support | 0.1021 | 50 | 60 |
| LLM_ONLY | all | required_coverage | 0.2363 | 50 | 60 |
| LLM_ONLY | all | faithfulness | — | 0 | 60 |
| LLM_ONLY | all | full_abstention | 0.0800 | 50 | 60 |
| LLM_ONLY | all | correct_abstention | — | 0 | 60 |
| LLM_ONLY | all | corpus_unanswerable_abstention | 0.4000 | 10 | 60 |
| RAG | all | ar_raw | 0.8411 | 50 | 60 |
| RAG | all | ar_report | 0.8411 | 50 | 60 |
| RAG | all | oracle_support | 0.7619 | 50 | 60 |
| RAG | all | required_coverage | 0.7320 | 50 | 60 |
| RAG | all | faithfulness | 0.8293 | 50 | 60 |
| RAG | all | full_abstention | 0.0400 | 50 | 60 |
| RAG | all | correct_abstention | 0.5000 | 10 | 60 |
| RAG | all | corpus_unanswerable_abstention | — | 0 | 60 |

짝비교는 두 조건 모두 유효한 동일 문항에 한정한다. Faithfulness와 두 답변불가 지표는 적용 범위가 달라 직접 짝비교하지 않는다.
상세 판정과 근거 인용은 results/, 원본 평가 응답과 재시도 이력은 calls/에 보관한다.
