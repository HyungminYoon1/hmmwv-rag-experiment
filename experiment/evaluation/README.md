# 답변 평가 실행기

첫 회차 답변 120개를 OpenAI Responses API 또는 로컬 Ollama로 평가한다. 기존 질문·정답 근거·검색 문맥·생성 답변은 수정하지 않는다. 환경은 evaluation/.venv로 분리했고, 임베딩은 기존 검색 환경의 고정 BGE-M3를 별도 프로세스로 호출한다.

## 현재 결과와 평가 기록

현재 확인할 결과는 [sol-revision-formal-20260929-v3](runs/sol-revision-formal-20260929-v3/report.md)이다. 채점 기준 개정 전 비교 자료는 [sol-formal-20260928-numeric-v3](runs/sol-formal-20260928-numeric-v3/report.md)이며, 현재 결과를 가리키는 파일은 [active-evaluation.json](../revisions/20260929-v2/active-evaluation.json)이다.

화면의 13개는 같은 첫 회차 120개 답변의 평가·수정 기록 6개와 가상 사례를 사용한 기능 점검 기록 7개다. v2·v3는 평가 기록의 개정 번호이며, 답변 생성 회차나 모델 버전이 아니다. ‘연결 시험’은 평가기 기능 점검을 뜻한다. **각 기록의 목적·수정 이유·상태는 [평가 기록 안내](RUN_HISTORY.md)에 정리했다.**

## 지표

| 지표 | 대상 | 방식 |
|---|---|---|
| 질문 관련성 | 답변 가능한 50문항 × 두 조건 | RAGAS 0.4.3 AnswerRelevancy. 역생성 질문 3개와 원 질문의 코사인 유사도 평균. noncommittal이 모두 1일 때만 0. 음수 유지 |
| 정답 근거 지지율 | 위와 같음 | 사실 주장 중 고정 정답 근거가 지지하는 비율 |
| 필수 요소 충족률 | 위와 같음 | 사전에 정한 필수 요소별 0/1 판정의 평균 |
| 검색 문맥 충실도 | 답변 가능한 RAG 50개 | 같은 주장 목록을 실제 Top-5에 대조 |
| 완전 답변유보율 | 답변 가능한 두 조건 | 실질적인 답변 없이 유보한 비율 |
| 답변불가 질의 유보 | 답변불가 10문항 × 두 조건 | RAG는 허용된 부분 답변의 정답·검색 근거도 확인. LLM Only는 별도의 교범 답변불가 유보율 |

주장 목록은 질문과 답변만으로 한 번 추출하고 두 근거 집합에 공통 적용한다. Faithfulness는 RAGAS의 주장 추출·NLI 지시문·비율 계산을 사용하되 출처 ID와 원문 인용을 요구하는 프롬프트를 적용했다. 원래 few-shot 예제를 그대로 사용한 기본 지표와 구분해 기록한다. 정답 근거 지지율·필수 요소 충족률·유보 판정은 연구용 추가 지표다.

인용이 실제 자료에 존재하는지, 주장·요소가 누락되거나 중복되었는지 프로그램이 검사한다. 인용 존재 검사는 **해당 인용이 주장을 뒷받침하는지에 대한 의미 검토**를 대신하지 않는다. 수치·단위·조건 판정은 기존 evaluation-policy.json을 따른다.

## 실행 방법

작업 폴더 `<PROJECT_ROOT>`에서 실행한다. 사용자가 GPT-6 Sol을 선택했다. 아래는 이번 평가 실행의 명령이다. 이미 만든 실행 ID에 prepare를 다시 실행하지 않는다.

```powershell
# 설정 확인: 실제 평가 호출 없음, 키는 존재 여부만 표시
$env:OPENAI_API_KEY = [Environment]::GetEnvironmentVariable('OPENAI_API_KEY','User')
.\experiment\evaluation\.venv\Scripts\python.exe -X utf8 -m experiment.evaluation.runner doctor --profile openai-sol

# 입력·설정 고정: 실제 평가 호출 없음
.\experiment\evaluation\.venv\Scripts\python.exe -X utf8 -m experiment.evaluation.runner prepare --id sol-formal-20260928-v1 --profile openai-sol

# 이 명령부터 실제 평가 모델 호출
.\experiment\evaluation\.venv\Scripts\python.exe -X utf8 -m experiment.evaluation.runner run --id sol-formal-20260928-v1

# 저장된 결과 재집계
.\experiment\evaluation\.venv\Scripts\python.exe -X utf8 -m experiment.evaluation.runner report --id sol-formal-20260928-v1
```

중단 후 같은 run 명령으로 재개한다. `--limit 2`는 미완료 답변 2개만 추가 처리한다. 동시에 한 요청씩 호출한다. 이미 평가 오류로 완료한 답변도 점수가 나올 때까지 반복 채점하지 않는다. 입력·코드·환경·설정을 고치면 새 실행 폴더를 사용한다.

OpenAI 키는 Windows 사용자 환경 변수 `OPENAI_API_KEY`에 저장하고 새 터미널에서 실행한다. 키를 채팅·이 저장소·명령 이력에 넣지 않는다. doctor는 프로세스에 키가 보이는지 확인하며 계정의 모델 접근 권한까지 검증하지 않는다. 키 설정이나 prepare만으로 유료 호출을 시작하지 않는다.

프로필은 `openai-astra`, `openai-sol`, `local-gemma4-12b`, `installed-4b-smoke`가 있다. 로컬 모델을 자동으로 내려받지 않는다. Gemma 선택 시 실험용 Ollama 서버(11435)의 저장소에 설치해야 한다. 기본 11434에 설치한 것과 구분한다. 설치된 생성용 Qwen 4B는 본 평가를 차단하고 다음 가상 사례 점검에만 허용한다.

```powershell
.\experiment\evaluation\.venv\Scripts\python.exe -X utf8 -m experiment.evaluation.runner smoke --id local-smoke-new --profile installed-4b-smoke
```

## 기록과 처리 규칙

- manifest.json / inputs.json: 사후 평가 모델·설정과 입력·코드·환경 해시. 새 실행에는 code-snapshot/으로 실행 코드 사본도 보관한다.
- calls/: 전체 프롬프트·출력 형식·원본 응답·실패 이력. 최초 포함 최대 3회, 첫 유효 결과 채택. 중단된 시도도 횟수에 포함된다. 파일 교체 오류는 저장만 재시도하며 계속 실패하면 중단한다. 저장된 완전한 응답은 모델명과 출력 형식을 검증한 뒤 복구하므로 새 유료 호출이 필요하지 않다.
- results/: 주장·근거 인용·요소별 판정과 점수. 평가시간은 생성 응답시간과 별개다. 관련성 점수는 RAGAS 계산과 Python math.fsum 기반 독립 계산을 1e-10 이내로 대조한다.
- embeddings/: 고정 BGE 벡터·입력·해시. 원 질문과 역생성 질문의 벡터는 호출별로 구분한다.
- summary.json / report.md: 유효 답변 수·결측 사유·공통 유효 문항의 짝비교.

생성 실패는 규칙에 따라 0점, 평가기 실패는 결측이다. 사실 주장이 없는 답변의 Faithfulness는 해당 없음이다. 최종 60문항의 점수를 보고 모델·프롬프트를 유리하게 고르지 않는다. 수정 필요 시 기존 기록과 수정 사유를 보존한다.

정상적인 답변 하나의 기본 호출 수는 LLM Only 7회, RAG 8회이며 답변불가 응답은 1회다. 120답변의 기본 호출은 총 770회다. 빈 주장·생성 실패로 줄거나 재시도로 늘 수 있다. 토큰 사용량은 남기지만 확정 청구 금액으로 표시하지 않는다.

API에서 반환한 모델명도 기록하고 변경을 차단한다. 같은 alias의 내부 갱신까지 확인할 수는 없으므로 평가 날짜·alias를 함께 기록한다. 로컬 모델은 digest를 고정한다. 문맥이 보수적인 입력 한도를 넘으면 몰래 자르지 않고 평가 오류로 기록한다.

API 선택 시 질문·답변·필요한 근거 텍스트가 외부로 전송된다. OpenAI store=false는 제공자의 모든 로그 보관이 없다는 뜻이 아니다. 로컬은 loopback만 허용하고 cloud 모델 태그를 차단한다. RAGAS 사용량 추적·LangSmith 전송을 끄며 키를 제거한 원본 기록을 PC에 보관한다. 자동 삭제는 하지 않는다. 화면은 읽기 전용이다.

연구자의 정답 근거 확인과 미리 선정한 40개 수동평가의 대조는 별도 단계다. 자동평가 완료만으로 이를 완료로 표시하지 않는다. 자동 점수와 수동 점수를 섞어 하나의 평균으로 만들지 않는다.

## 설치 재현

```powershell
py -3.11 -m venv experiment/evaluation/.venv
.\experiment\evaluation\.venv\Scripts\python.exe -m pip install -r experiment/evaluation/requirements.lock.txt
.\experiment\evaluation\.venv\Scripts\python.exe -m pip check
.\experiment\evaluation\.venv\Scripts\python.exe -X utf8 -m pytest experiment/evaluation/tests -q
```

RAGAS 0.4.3은 langchain-community 0.4.2와 조합 시 VertexAI import가 실패했다. 해당 모듈을 제공하는 0.3.31로 고정했으며 라이브러리 소스를 직접 수정하지 않았다. 전체 버전은 lock 파일에 기록했다. [상류 이슈](https://github.com/vibrantlabsai/ragas/issues/2745).

추천 모델과 근거: `research/2026-09-28_답변평가_실행기_구현과_평가모델_선정.md`. 실행기 검증 결과: verification.json. 화면: <http://127.0.0.1:8767/evaluation>.

## 2026-09-28 실행 결과

GPT-6 Sol로 120답변을 평가했다. 원래 실행은 `sol-formal-20260928-v1`, 당시 수치 보정 집계는 `sol-formal-20260928-numeric-v3`이다. 현재 개정 결과는 위의 ‘현재 결과와 평가 기록’을 따른다. 원래 API 응답 771회를 보존했으며, NumPy 내적의 간헐적 수치 불일치 7건 때문에 저장된 역질문·벡터를 이용해 100개 관련성 점수를 일괄 재계산했다. 모델 재호출은 없었고 math.fsum과 50자리 Decimal 계산이 1e-10 이내로 일치했다. 다른 판정은 바꾸지 않았다.

가상 사례·실패한 파생 실행과 이전 파생 실행은 이력으로 보존한다. 수치 재계산 결과는 원본 집계와 계산 코드의 사본을 보관하므로 원래 report를 다시 생성해도 출처 검증이 유지된다. 재계산은 verification/recalculate_relevancy.py, 검증은 verification/verify_sol_run.py를 모듈로 실행한다. 기존 ID를 덮어쓰지 않는다. 연구자 확인·수동평가 대조는 아직 PENDING이다. 자세한 수치와 API 사용량은 research/2026-09-28_GPT-6_Sol_답변평가_실시기록.md에 기록했다.

저장된 원본 평가에서 새 파생 실행을 만들고 검증하는 예시다. 추가 모델 호출은 없으며, 새 ID를 사용해야 한다.

```powershell
.\experiment\evaluation\.venv\Scripts\python.exe -X utf8 -m experiment.evaluation.verification.recalculate_relevancy --source sol-formal-20260928-v1 --id sol-formal-numeric-new
.\experiment\evaluation\.venv\Scripts\python.exe -X utf8 -m experiment.evaluation.verification.verify_sol_run --id sol-formal-numeric-new --require-complete
```

## 2026-09-29 검토 후 재평가 v2

`revision_engine.py`와 `revision_runner.py`는 원 실행을 보존하는 별도 사후 평가 경로다. 원래 `runner`와 `engine`은 기존 실행의 재현 기록으로 유지한다. 개정 정책은 `../gold-v2/evaluation-policy.json`이며, 새 실행 ID는 `sol-revision-formal-20260929-v2`이다.

- 조건이 유지된 기술 사실만 지지율의 분모에 넣고, 입력 존재·자기 출처·인용 ID 설명은 별도 기록한다.
- 질문과 답변으로 주장을 추출하고, oracle와 실제 검색 문맥은 분리해 동일한 주장 목록을 평가한다. 지지 판정에서 질문은 운용 조건 확인용이며 사실 근거가 아니다.
- 모든 등록 대체 근거와 검토한 부분 답변 근거를 oracle에 포함한다. 근거 조합은 문항별 요구 사실에 한정한다.
- 관련 기술 사실이 있는 답변불가 응답에는 주장별 부분 근거 검사를 생략하지 않는다.
- 원래 질문 관련성의 역질문·벡터·검산과 답변 종류 분류는 복사·해시 고정해 재사용한다. 변경된 단계의 정상 호출 예상은 370회이며 실패 재시도·빈 주장에 따라 달라진다.
- 주장 추출과 NLI 프롬프트를 수정한 연구용 평가다. 기존 RAGAS 기본 지표를 그대로 사용했다고 표현하지 않는다.

```powershell
# 중단 후 재개. 이미 완료된 답변을 다시 호출하지 않는다.
$env:OPENAI_API_KEY = [Environment]::GetEnvironmentVariable('OPENAI_API_KEY','User')
.\experiment\evaluation\.venv\Scripts\python.exe -X utf8 -m experiment.evaluation.revision_runner run --id sol-revision-formal-20260929-v2

# 원본·인용·산술·캡처 검사와 문서 재구성. API 호출 없음.
.\retrieval\.venv\Scripts\python.exe -X utf8 experiment\revisions\20260929-v2\verify_results.py
.\experiment\evaluation\.venv\Scripts\python.exe -X utf8 experiment\revisions\20260929-v2\build_report.py
```

가상 사례 3개와 코드 검사 38개가 통과했다. 완료 수·검증 상태·개정 전후 점수는 `../revisions/20260929-v2/결과_업데이트.md` 및 새 실행의 summary.json을 따른다.

원문 인용의 줄 사이에 있던 필드를 평가모델이 생략하여 연속 인용 검사가 실패한 경우에는, 같은 출처에서 같은 문구와 순서가 확인되는 구간만 별도 파생 실행 `sol-revision-formal-20260929-v3`에서 복원한다. 원 v2의 실패 기록과 판정은 유지한다. 복원 도구는 `../revisions/20260929-v2/derive_citations.py`이며 추가 API 호출 없이 저장된 응답을 사용한다. 완료된 최종 실행은 `../revisions/20260929-v2/active-evaluation.json`이 가리킨다. 인용 복원 기준과 독립 검산 결과를 함께 확인한다.

검증 도구는 PDF를 다시 렌더링하므로 PyMuPDF가 설치된 `retrieval/.venv`에서 실행한다. API 재평가·인용 복원은 기존 `evaluation/.venv`를 사용한다.
