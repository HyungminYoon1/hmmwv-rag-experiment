# 답변 평가 gold-v3-formal-20260929

- 상태: COMPLETED (120/120)
- 평가 모델: gpt-6-sol
- 구분: PROVISIONAL_AUTOMATIC_SCORES
- 연구자 원문 검토 및 수동평가 대조: PENDING
- 평가기 오류는 결측이며, 생성 실패 0점과 구분한다. 자동평가가 완료되어도 최종 품질 검증 완료를 뜻하지 않는다.

| 조건 | 대상 | 지표 | 평균 | 유효 답변 수 | 처리 답변 수 |
|---|---|---|---:|---:|---:|
| LLM_ONLY | all | ar_raw | 0.7267 | 50 | 60 |
| LLM_ONLY | all | ar_report | 0.7267 | 50 | 60 |
| LLM_ONLY | all | oracle_support | 0.1841 | 50 | 60 |
| LLM_ONLY | all | required_coverage | 0.2580 | 50 | 60 |
| LLM_ONLY | all | faithfulness | — | 0 | 60 |
| LLM_ONLY | all | full_abstention | 0.0800 | 50 | 60 |
| LLM_ONLY | all | correct_abstention | — | 0 | 60 |
| LLM_ONLY | all | corpus_unanswerable_abstention | 0.4000 | 10 | 60 |
| RAG | all | ar_raw | 0.8411 | 50 | 60 |
| RAG | all | ar_report | 0.8411 | 50 | 60 |
| RAG | all | oracle_support | 0.7766 | 50 | 60 |
| RAG | all | required_coverage | 0.7820 | 50 | 60 |
| RAG | all | faithfulness | 0.8519 | 48 | 60 |
| RAG | all | full_abstention | 0.0400 | 50 | 60 |
| RAG | all | correct_abstention | 0.5000 | 10 | 60 |
| RAG | all | corpus_unanswerable_abstention | — | 0 | 60 |

짝비교는 두 조건 모두 유효한 동일 문항에 한정한다. Faithfulness와 두 답변불가 지표는 적용 범위가 달라 직접 짝비교하지 않는다.
상세 판정과 근거 인용은 results/, 원본 평가 응답과 재시도 이력은 위 부모 평가 기록에 보관한다.

## 원문 대조에 따른 정정

이 기록은 gold-v3와 기존 Sol 판정을 사용한 재집계다. 새 API 호출은 0회다. S16에서 질문에 없는 유입 경로 요소만 제외했고, 나머지 판정은 보존했다. 검색 근거 Recall@5는 78.0%, 전체 근거 확보는 31/50이다. 좁은 동등 근거 기준에서는 74.0%·29/50이다.

판정 원본과 API 호출 이력은 `../sol-revision-formal-20260929-v3/`에 있고, 이 기록의 results/는 파생 결과다. 상세 검색·민감도 결과는 analysis.json을 따른다.
