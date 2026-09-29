# HMMWV 정비교범 기반 로컬 RAG 비교 실험

공개 HMMWV 정비교범을 대상으로, 같은 경량 언어모델에 교범 검색 결과를 제공했을 때 답변의 근거 활용과 응답 특성이 어떻게 달라지는지 비교한 연구입니다. 전처리·검색·답변 생성·평가 프로그램과 실제 실험 기록을 함께 제공합니다.

## 1. 실험 개요

| 항목 | 설정 |
| --- | --- |
| 교범 | TM 9-2320-280-20-1, Volume 1, 1996년 발행 / Change 2: 2004-07-15 |
| 문서 범위 | PDF 전체 890쪽 중 제1·2장에 해당하는 31~863쪽, 833쪽 |
| 검색 corpus | corpus-v6-final, 8,344개 청크, 청크당 최대 500토큰(Qwen 토크나이저 기준) |
| 검색 | BGE-M3, CPU float32, FAISS IndexFlatIP, Top-5 |
| 답변 생성 | Qwen3-4B-Instruct-2507, Q4_K_M GGUF, 로컬 Ollama |
| 비교 조건 | LLM Only / RAG, 같은 모델·공통 프롬프트 사용 |
| 평가질의 | 단일 근거 20개, 다중 근거 30개, 답변불가 10개 |
| 실행 기록 | 60문항 × 두 조건 × 세 회차 = 360개 요청; 내용 품질은 첫 회차 120개 답변 분석 |
| 자동평가 | GPT-6 Sol. 질문 관련성 계산에 RAGAS 사용; 추가 연구 지표와 수정 프롬프트 포함 |

정비 답변 생성은 로컬에서 수행했습니다. 답변 자동평가는 별도 단계에서 외부 API를 사용했습니다. [설계와 지표](docs/experiment-design.md), [교범·모델 출처](docs/data-sources.md)를 참고하세요.

## 2. 디렉토리와 실행 기록

| 위치 | 내용 |
| --- | --- |
| preprocessing/ | PDF 추출·OCR 재생·기록된 보정 적용 프로그램 |
| preprocessing/corpus/ | 구조 처리·청킹·검증과 corpus 확인 화면 |
| retrieval/ | BGE-M3 임베딩·인덱스·검색 앱 |
| experiment/ | LLM Only/RAG 실행기, 자원·응답시간 측정과 결과 화면 |
| experiment/runs/formal-v1/ | 실제 360개 요청과 첫 회차 평가 입력 |
| experiment/evaluation/runs/ | 실제 답변 평가·수정 기록 6개와 기능 점검 기록 7개 |
| experiment/gold-v1/, gold-v2/ | 최초 정답 근거와 원문 검토 후 개정한 근거 |
| experiment/revisions/20260929-v2/ | 평가 개정 이유, 전후 점수와 검증 자료 |
| artifacts/ | 원본 파일 목록, 공개용 변경 기록, 자료 묶음의 SHA-256·복원 경로 |
| scripts/ | 이 배포본의 설치·복원·조회·검증 보조 도구 |
| docs/ | 다른 연구자를 위한 설치·재연·출처 안내 |

자료 ZIP 3개는 [고정 Release `v2026.09.29`](https://github.com/HyungminYoon1/hmmwv-rag-experiment/releases/tag/v2026.09.29)에서 받습니다. `runtime-data-20260929.zip`, `preprocessing-replay-20260929.zip`, `review-evidence-20260929.zip`으로 나누어 제공합니다. 모델 가중치와 Python 가상환경은 포함하지 않습니다.

실험 계산 코드·교범·청크·질의 본문·생성 답변·평가 결과는 유지했습니다. 공개 사본에서는 PC 경로와 HWPX 작성자 메타데이터를 정리하고, 문서를 저장소 안의 설계·설정·결과만으로 읽을 수 있도록 편집했습니다. 관련 검증 목록도 갱신했습니다. 원 실험의 해시와 공개 사본의 해시는 [공개용 변경 기록](artifacts/publication-changes.json)으로 구분합니다. 하위 README와 당시 보고서는 작성 시점의 상태를 담고 있으므로, 현재 실행 절차는 이 README와 [재연 설명서](docs/reproduction.md)를 먼저 보세요.

## 3. 현재 결과

현재 자동평가 결과는 **sol-revision-formal-20260929-v3**입니다. 근거 Recall@5는 70%, 모든 필수 근거를 찾은 문항은 답변 가능한 50개 중 27개입니다.

| 자동평가 지표 | LLM Only | RAG |
| --- | ---: | ---: |
| 질문 관련성 | 0.7267 | 0.8411 |
| 정답 근거 지지율 | 18.4% | 77.7% |
| 필수 요소 충족률 | 24.8% | 77.2% |

위 세 지표는 각 조건의 답변 가능한 50문항을 대상으로 합니다. 질문 관련성은 정답률과 다릅니다. 원문 대조 후 근거·채점 기준을 수정했으며, 그 전후 변화는 생성모델 자체의 성능 향상을 뜻하지 않습니다. Astra의 추가 AI 검토와 연구자·정비 전문가의 직접 검증도 구분합니다.

- [결과 요약과 해석](docs/results.md)
- [13개 평가 기록의 목적과 버전 설명](experiment/evaluation/RUN_HISTORY.md)
- [개정 전후 점수와 검증 기록](experiment/revisions/20260929-v2/결과_업데이트.md)

## 4. 저장된 결과부터 확인하기

먼저 저장소를 내려받습니다.

```powershell
git clone --branch v2026.09.29 https://github.com/HyungminYoon1/hmmwv-rag-experiment.git
Set-Location hmmwv-rag-experiment
```

PowerShell에서 이 README가 있는 폴더를 작업 디렉토리로 사용합니다. Python 3.11이 필요합니다. 아래 절차는 모델 다운로드·새 답변 생성·평가 API 호출을 하지 않습니다.

```powershell
# 코드·실험 기록과 공개용 변경 목록에 따른 파일 해시 확인
py -3.11 -X utf8 scripts/verify_artifacts.py --scope core

# 결과 화면 실행: Python 표준 라이브러리 사용
py -3.11 -X utf8 scripts/serve_results.py --port 8767
```

브라우저에서 <http://127.0.0.1:8767/evaluation>을 엽니다. 이미 다른 앱이 해당 포트를 사용 중이면 `--port 8772`처럼 바꿀 수 있습니다. 서버는 `Ctrl+C`로 종료합니다.

원문 이미지와 전체 검증도 확인하려면 다음 명령으로 고정 Release의 ZIP 3개를 내려받아 복원합니다.

```powershell
py -3.11 -X utf8 scripts/restore_artifacts.py --base-url https://github.com/HyungminYoon1/hmmwv-rag-experiment/releases/download/v2026.09.29
py -3.11 -X utf8 scripts/verify_artifacts.py --scope all
pwsh -File scripts/setup.ps1 -Mode view
.\.venv-view\Scripts\python.exe -X utf8 scripts/verify_saved_results.py
```

복원 프로그램은 다른 내용의 파일을 덮어쓰지 않습니다. 검증 보고서는 기존 결과와 분리한 `validation/local/`에 생성됩니다.

## 5. 실험을 다시 실행하는 방법

모델 설치부터 새 실험·자동평가까지의 전체 명령을 **[재연 설명서](docs/reproduction.md)**에 정리했습니다.

1. 기준 환경과 장비 조건 확인: Windows x64, Python 3.11.9, Ollama 0.34.1, NVIDIA GPU.
2. 세 Python 환경 설치와 고정 corpus·인덱스·검토 자료 복원.
3. 잠금 파일에 기록된 BGE-M3와 Qwen GGUF 다운로드·해시 검사.
4. 실험 전용 Ollama 서버에 모델 등록.
5. 별도 개발 질문으로 실행 점검 후, 새 ID로 360개 요청 수집.
6. 새 답변에 대해 선택적으로 평가 API 실행. 저장된 기존 결과 확인에는 API 키가 필요하지 않습니다.

전처리와 청킹을 다시 만드는 명령, 임베딩 재생성 검사, API 키 입력, 중단 후 재개, 흔한 오류도 설명서에 포함했습니다. 다른 장비에서 시간·메모리 수치나 생성 답변이 완전히 같아진다고 가정하지 않으며, 새 결과는 제공된 원본 기록과 별도 ID로 보관합니다.

## 배포 정보

- [공개 저장소](https://github.com/HyungminYoon1/hmmwv-rag-experiment) · [고정 Release `v2026.09.29`](https://github.com/HyungminYoon1/hmmwv-rag-experiment/releases/tag/v2026.09.29).
- [배포 준비와 검증 기록](docs/package-validation.md), [패키징 결정 기록](docs/packaging-decisions.md).
- [공개 전 보강 내역](docs/publication-review.md): 경로·메타데이터 정리, 라이선스 동봉, 원본 보존 및 재검증.
- 코드의 공개 라이선스는 아직 선택하지 않았습니다. [라이선스 상태](LICENSE_STATUS.md)와 [외부 자료 출처](THIRD_PARTY_NOTICES.md)를 확인하세요.
