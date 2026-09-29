# 실험 프로그램 구조

2026-09-28 사용자 승인에 따라 구현한다. 기존 retrieval과 고정 corpus는 수정하지 않는다.

- annotations.py / gold.py: PDF 대조 결정과 정답 근거·청크 대응표. 검색 모델을 호출하지 않는다.
- generation.py: 질문과 실제 검색 문맥으로 공통 프롬프트를 만들고 로컬 Ollama를 호출한다. 정답 자료를 읽지 않는다.
- worker.py: 기존 검증된 SearchService의 모델·인덱스를 사용하는 별도 정식 검색 프로세스. 개발 질문 차단은 원래 앱에 유지한다.
- runner.py: 순서·회차·워밍업·실패·중단·실행 기록을 관리한다. 생성 입력에는 질문 문자열만 전달한다.
- resources.py: 조건별 PID의 RSS와 장치 VRAM을 표본 측정한다.
- report.py: 완료된 실행의 검색 점수와 시간·자원 통계를 산출한다. 내용 품질 평가와 구별한다.
- app.py / web/: 근거 검토, 실행 상태, 결과를 나눠 표시한다. HTTP 계층에 실험 계산을 넣지 않는다.

실험 자료는 experiment/에 둔다. 기존 retrieval/.venv를 변경하지 않고 검색/로컬 호출에 사용한다. 사후 RAGAS는 별도 환경에서 연결한다. Ollama는 127.0.0.1:11435, 실험 화면은 127.0.0.1:8767에서 실행한다. 8765와 8766은 보존한다.

생성모델과 검색모델은 상주하되 별도 PID로 둔다. LLM Only의 RAM 합계에는 검색 PID를 포함하지 않고, RAG에는 포함한다. 같은 PID는 중복 계산하지 않는다. 요청 처리 중 다른 모델 계산을 병행하지 않는다.

원본, 근거 결정, 전체 입력·출력과 실패 기록은 PC에 보관하며 자동 삭제하지 않는다. 질문이나 교범의 내용을 외부 생성 API로 보내지 않는다. 모델 초기 다운로드는 별도 단계다. 평가 API 사용 여부·모델은 평가 단계에서 확정한다.

## 사후 답변 평가 (2026-09-28)

evaluation/runner.py가 입력 검증·고정·재개를, engine.py가 기존 평가 규칙을 담당한다. providers.py는 외부 OpenAI Responses 또는 loopback Ollama 호출만 담당한다. judge.py는 재시도와 원본 응답 보존을, embeddings.py는 고정 BGE-M3의 별도 프로세스 호출을 담당한다. report.py는 지표·결측·짝비교를 집계하고 view.py는 읽기 전용 화면 데이터를 제공한다. HTTP 계층에는 평가 계산이나 유료 실행을 넣지 않는다.

환경은 evaluation/.venv, 산출물은 evaluation/runs/로 분리한다. API 또는 로컬 평가모델을 선택하고 CLI run으로 실행한다. 기존 corpus·질문·근거·생성 실행을 덮어쓰지 않는다. 기능 점검에는 최종 60문항과 무관한 가상 사례를 사용한다. 세부 규칙은 evaluation/README.md 및 DECISIONS.md의 E09~E11을 따른다.

## 검토 후 평가 개정 경로 (2026-09-29)

`revision_gold.py`는 원 gold-v1을 읽어 질문별 근거와 정책을 gold-v2에 만든다. `evaluation/revision_engine.py`는 수정한 주장·지지·요소·유보 판정을 담당하고, `revision_runner.py`는 원 실행·이전 점수·개정 입력을 고정해 새 실행을 관리한다. 같은 providers/judge 계층을 사용하며 기존 engine/runner와 corpus·생성 경로는 보존한다. 재사용하는 질문 관련성·답변 종류 단계는 출처 해시로 구별한다. HTTP 계층은 조회만 담당한다. 사후 보완과 검증 스크립트·문서는 revisions/20260929-v2에 둔다.
