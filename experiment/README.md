# HMMWV 비교 실험

고정한 60문항에 대해 같은 Qwen3-4B-Instruct-2507 Q4_K_M의 LLM Only와 RAG를 비교한다. 기존 corpus와 검색 인덱스는 읽기 전용으로 사용한다.

## 확인 화면

- http://127.0.0.1:8767/ : 실행 현황
- http://127.0.0.1:8767/gold : 필수 답변 요소, 충분 청크 조합, 원본 PDF 이미지
- http://127.0.0.1:8767/results : 첫 회차의 두 조건 답변 원문
- http://127.0.0.1:8767/evaluation : 답변 평가 결과. [13개 평가 기록의 의미와 현재 사용할 결과](evaluation/RUN_HISTORY.md)
- 기존 교범 검색은 http://127.0.0.1:8766/ 에서 계속 사용할 수 있다.

화면은 조회용이다. 실험 실행이나 연구자 검토 완료 처리는 화면을 열었다는 이유로 이루어지지 않는다.

## 파일

| 위치 | 내용 |
| --- | --- |
| gold-v1/questions.json | 변경하지 않은 60문항과 정답 근거·채점 요소 |
| gold-v1/대응표.md | 사람이 읽는 근거 대응표 |
| gold-v1/review-attestation.json | 연구자 직접 검토 기록. 현재 미완료 |
| evidence-review/ | 원본 PDF에서 렌더링한 대조 자료. PDF를 새로 만든 것이 아님 |
| config.json / prompt.txt | 고정 생성 설정과 두 조건의 공통 프롬프트 |
| models/model.lock.json | 다운로드한 GGUF의 출처·revision·바이트 해시 |
| runs/formal-v1/manifest.json | 본 실험의 실행 정체성과 파일 해시 |
| runs/formal-v1/attempts/ | 360개 요청의 입력·출력·검색·시간·자원 기록 |
| runs/formal-v1/warmups/ | 집계에서 제외하는 조건별 5회 워밍업 기록 |
| runs/formal-v1/summary.json / 결과.md | 검색·시간·자원 집계. 자동 품질 점수와 구분 |
| runs/formal-v1/audit.json | 질문·청크·입력·토큰 길이·실행 범위 검사 |
| runs/formal-v1/manual-review/ | 40개 답변의 수동 검증 자료. key.json은 조건을 가리는 검토 후 확인 |
| archive/ | 수정 전 개발 설정과 본 실험 소스 사본 |

## 실행 방법

작업 폴더는 이 문서의 상위 폴더인 `kidet-2026-paper`이다. PowerShell에서 다음 명령을 사용한다. 이미 실행 중인 프로세스나 완료된 실행 ID는 중복 실행하지 않는다.

```powershell
# 실험 전용 Ollama 서버
pwsh -File .\experiment\start_ollama.ps1

# 조회 화면
.\retrieval\.venv\Scripts\python.exe -X utf8 -m experiment.app

# 완료 결과 재검증과 집계: 모델 답변을 새로 생성하지 않는다.
.\retrieval\.venv\Scripts\python.exe -X utf8 -m experiment.audit --id formal-v1
.\retrieval\.venv\Scripts\python.exe -X utf8 -m experiment.report --id formal-v1
```

새 실행은 `runner prepare --id 새이름 --mode formal` 뒤 `runner run --id 새이름`으로 만든다. 동일한 설정의 개발 시험 통과 기록이 필요하다. 코드·질문·모델·설정이 바뀌면 기존 실행에 이어 붙이지 않는다. 중단 시 이미 시도한 요청을 덮어쓰지 않으며, 실행 중 남은 요청이나 중단 사유를 확인하고 재개해야 한다. `active.json`이나 `running.lock`을 원인 확인 없이 지워 우회하지 않는다.

## 평가 범위

검색 점수는 근거 단위의 충분 청크 조합을 기준으로 계산한다. `(A + B) / C`는 A와 B를 함께 찾거나, C 하나를 찾으면 해당 근거가 충족된다는 뜻이다. 중첩된 대안 청크를 중복 정답으로 세지 않는다.

전체 360개 요청 중 내용 품질과 검색의 주 분석은 첫 회차를 사용한다. 시간은 두 조건 모두 세 회차 정상인 공통 문항에서 질의별 중앙값을 낸 뒤 median/p95를 계산한다. 출력 길이 제한 도달, 존재하지 않는 인용, 답변 변화도 보존한다. 짧은 유보 답변이 빨랐다는 이유만으로 성능이 우수하다고 해석하지 않는다.

RSS는 조건에 필요한 실행기·Ollama·생성 프로세스와 RAG 검색 프로세스의 working set 합계다. VRAM은 GPU 장치 전체 사용량이다. 100ms 간격의 관측값이며 시스템 전체의 순수 RAM이나 순간 최대값은 아니다. 검색 모델·인덱스는 상주하고, 쿼리 임베딩은 매 RAG 요청 새로 계산한다. 런타임 prefix/KV 캐시를 끄지 않는다.

RAGAS·Oracle 지원도·요소 충족도·유보 판정과 연구자 직접 검토는 별도 단계다. API 설정 전에는 자동 품질 점수를 만들지 않는다. Codex의 PDF 대조를 연구자의 직접 확인이나 정비 전문가 검증이라고 표현하지 않는다. 사후 평가모델과 세부 평가 프롬프트의 확정 시점은 생성 수집 전 설정과 구분해 기록한다.

## 평가 API 설정

RAGAS는 OpenAI 전용이 아니며 로컬 Ollama나 다른 제공자도 연결할 수 있다. 자동평가 모델은 답변 생성용 Qwen과 구별하여 선택하고 수동 검증 자료와 비교한다.

OpenAI를 선택하면 Windows의 **계정의 환경 변수 편집 → 사용자 변수 → 새로 만들기**에 `OPENAI_API_KEY`를 저장한다. 키 값은 채팅·문서·이 저장소에 넣지 않는다. 별도 답변 평가 실행기에서 OpenAI API와 로컬 Ollama를 지원한다. 사용자가 GPT-6 Sol을 선택했고, API 가상 사례 점검과 첫 회차 120답변의 자동평가를 완료했다. 원본 기록은 evaluation/runs/sol-formal-20260928-v1, 9월 28일 수치 보정 집계는 evaluation/runs/sol-formal-20260928-numeric-v3에 저장했다. 현재 개정 결과는 sol-revision-formal-20260929-v3이며, [평가 기록 안내](evaluation/RUN_HISTORY.md)에서 수정 전후 기록을 구분해 확인할 수 있다. 연구자 원문 확인과 40답변 수동 대조는 아직 남아 있다. 키를 저장하는 것만으로 평가가 시작되지 않으며, Codex 화면에서 Astra를 사용하는 것이 API 인증을 대신하지 않는다. 사용 방법과 지표 정의는 [평가 실행기 안내](evaluation/README.md), 기록은 [답변 평가 화면](http://127.0.0.1:8767/evaluation)에서 확인한다.

- [OpenAI 키 설정 안내](https://developers.openai.com/api/docs/quickstart)
- [GPT-6 Sol API 모델](https://developers.openai.com/api/docs/models/gpt-6-sol)
- [RAGAS의 로컬 모델 연결](https://docs.ragas.io/en/stable/getstarted/evals/)

## 출처와 검토 범위

실험 규칙 문서, retrieval의 architecture·README·설정·검색 관련 코드, 고정 60문항은 이번 작업에서 확인했다. corpus 전체는 프로그램으로 해시·레코드·청크 대응을 검사했다. PDF는 67쪽의 필수 사실과 대체 근거를 눈으로 대조했으며, 890쪽 전체를 이번에 다시 눈으로 검토한 것은 아니다. 파일 무결성과 문장의 의미 정확성은 구별한다.

세부 선택과 수정 사유는 DECISIONS.md, 실행 결과는 해당 실행 폴더를 따른다.

## 2026-09-29 평가 오류 수정

최초 자동평가 후 Astra의 원문 대조에서 확인한 근거 누락과 평가 기준을 보완했다. `gold-v2/`가 수정한 근거 대응표이며, 생성 당시 고정 자료인 `gold-v1/`은 그대로 보존한다. 질문·유형·corpus·검색 결과·생성 답변·시간 측정은 바꾸지 않았다.

새 평가 ID는 `sol-revision-formal-20260929-v2`이다. 검토 후 개정한 기준임을 기록하고 동일한 GPT-6 Sol 설정으로 두 조건에 적용한다. 질문 관련성과 완전 답변유보 분류는 원 입력·기준이 같아 기존 값을 재사용한다. 근거 지지·요소 충족·답변불가 유보는 새로 평가한다. 최초 40답변의 Astra 검토를 인간 수동평가와 섞지 않는다.

최종 인용 복원 결과는 별도 파생 실행 `sol-revision-formal-20260929-v3`로 보관한다. 이 단계는 추가 모델 호출 없이 원문의 빠진 중간 인용 구간만 복원하며, 판정 내용과 최초 v2 기록은 보존한다. 현재 결과는 `revisions/20260929-v2/active-evaluation.json` 및 검증 기록을 따른다.

- 결과와 처리 현황: [수정 결과 화면](http://127.0.0.1:8771/index.html)
- [결정 기록](revisions/20260929-v2/DECISIONS.md)
- [결과 업데이트 문서](revisions/20260929-v2/결과_업데이트.md)
- [정답 근거 v2](gold-v2/대응표.md)
