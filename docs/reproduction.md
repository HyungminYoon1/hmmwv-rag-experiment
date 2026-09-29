# 설치와 실험 재연

이 설명서의 명령은 저장소 최상위, 즉 `README.md`가 있는 폴더에서 PowerShell 7로 실행합니다. `Push-Location`을 명시한 전처리 명령만 예외입니다. 각 명령의 성공을 확인한 뒤 다음 명령을 실행하세요. 새 실행 ID의 예시는 처음 한 번 사용할 이름이며, 이미 같은 ID가 있으면 다른 이름을 정합니다.

## 1. 어떤 수준으로 재연할 것인가

| 목적 | 필요한 것 | 새 모델 호출 |
| --- | --- | --- |
| 저장된 답변·평가표 열기 | Python 3.11, 저장소 파일 | 없음 |
| 파일·수치·PDF 캡처 검증 | 위 자료 + 자료 ZIP 3개 + PyMuPDF | 없음 |
| 고정 추출본에서 보정·청킹 재생 | 전처리 환경 + preprocessing-replay 자료 | 없음 |
| 로컬 모델로 새 답변 생성 | 전체 환경 + BGE-M3 + Qwen + Ollama + 지원 장비 | 로컬 생성만 수행 |
| 새 답변의 자동평가 | 평가 환경 + 고정 BGE-M3 + GPT-6 Sol API 접근 | 외부 유료 API 사용 |

기존 측정값을 검산하는 것과 새 답변을 생성하는 것은 서로 다른 절차입니다. 자동평가 프롬프트와 모델 판정도 저장되어 있어, 기존 결과를 읽기 위해 API를 다시 호출할 필요는 없습니다.

## 2. 기준 환경과 설치 전 확인

원 실험은 다음 환경에서 실행했습니다. 이는 기록된 환경이며 각 항목을 최소 사양으로 측정한 결과는 아닙니다.

| 항목 | 원 실험 환경 |
| --- | --- |
| OS | Windows 11 Home, build 26200, x64 |
| Python | 3.11.9, 64-bit |
| CPU | Intel Core i9-14900HX, 24코어 / 32 논리 프로세서 |
| RAM | 약 64GB |
| GPU | NVIDIA GeForce RTX 4070 Laptop GPU, 8GB VRAM |
| GPU 드라이버 | 616.92 |
| Ollama | 0.34.1 |
| 임베딩 | torch 2.8.0+cpu, sentence-transformers 5.1.1, transformers 4.55.4 |

원본 기록은 [hardware.json](../experiment/reports/hardware.json)과 [생성 manifest](../experiment/runs/formal-v1/manifest.json)에 있습니다. 모델 두 개의 다운로드 크기는 약 4.5GiB이며 Qwen을 Ollama에 등록하면 모델 저장 공간이 추가로 필요합니다. 환경·자료·새 실행을 위해 25~30GiB 정도의 여유 공간을 준비하는 편이 좋습니다.

먼저 [Python 3.11.9](https://www.python.org/downloads/release/python-3119/), [PowerShell](https://learn.microsoft.com/powershell/scripting/install/installing-powershell-on-windows), [Ollama 0.34.1](https://github.com/ollama/ollama/releases/tag/v0.34.1)을 설치합니다. 설치 후 새 터미널에서 확인합니다.

```powershell
py -3.11 --version
pwsh --version
ollama --version
```

자원 측정 코드는 Windows API와 `C:\Windows\System32\nvml.dll`을 사용합니다. 현재 정식 실행 경로는 Windows/NVIDIA 환경용입니다. 검색 프로세스는 논리 CPU `0,2,4,6,8,10,12,14`가 서로 다른 성능 코어인지 검사합니다. 다른 CPU 배치에서는 미리 지정한 조건이 맞는지 확인해야 하며, 검사 실패를 지우고 계속 실행하지 않습니다. Linux·macOS·AMD GPU용 자원 측정 이식은 이 배포본에 포함하지 않았습니다.

고정 인덱스 검증은 Python·패키지 버전뿐 아니라 OS의 `platform` 문자열과 CPU affinity도 비교합니다. 따라서 아래 정식 실행 절차는 기록된 환경과 호환되는 Windows 환경을 기준으로 합니다. 다른 OS 빌드나 CPU 배치에서는 별도 설정과 새 인덱스를 만드는 이식 작업이 필요할 수 있습니다. 결과 조회·파일 검증과 모든 PC에서의 새 실험 실행을 같은 지원 범위로 보지 않습니다.

## 3. 고정 자료 복원

[고정 Release `v2026.09.29`](https://github.com/HyungminYoon1/hmmwv-rag-experiment/releases/tag/v2026.09.29)에서 다음 파일을 받습니다.

- `runtime-data-20260929.zip`: 최종 corpus, 검색 인덱스, 교범 PDF, 생성 토크나이저.
- `preprocessing-replay-20260929.zip`: 고정 OCR·추출·보정·구조 처리 자료와 참조 기록.
- `review-evidence-20260929.zip`: 원문 캡처, AI 검토 근거, 평가 수정 검증에 필요한 백업.

다음 명령은 공개 Release에서 ZIP을 내려받고 검증한 뒤 복원합니다.

```powershell
py -3.11 -X utf8 scripts/verify_artifacts.py --scope core
py -3.11 -X utf8 scripts/restore_artifacts.py --base-url https://github.com/HyungminYoon1/hmmwv-rag-experiment/releases/download/v2026.09.29
py -3.11 -X utf8 scripts/verify_artifacts.py --scope all
```

ZIP을 이미 받았다면 `--base-url` 대신 `--asset-dir ../release-assets`처럼 저장한 디렉토리를 지정합니다. `--bundle runtime-data`처럼 한 묶음만 복원할 수도 있습니다.

복원은 ZIP 자체와 내부 파일의 크기·SHA-256을 검사합니다. 동일한 파일은 유지하고, 내용이 다른 기존 파일은 덮어쓰지 않습니다. 교범과 평가질의는 manifest에 지정된 경로에 복원합니다. 실행 프로그램이 해당 경로와 해시를 확인하므로 복원 뒤 임의로 이동하지 않습니다.

현재 자료 묶음은 `20260929-publication-v3`입니다. 공개용 경로·문서 메타데이터 정리, 문서 편집과 외부 자료 라이선스 동봉을 반영했습니다. `artifacts/original-files.json`과 `source-bundles.json`은 원래 연구 파일의 해시를 보존하며, `publication-changes.json`은 변경·이동·빈 로그 제외를 기록합니다. 검증 도구는 이 목록에 선언된 공개 사본의 해시를 검사하고, 선언되지 않은 차이는 실패로 처리합니다. 이전 로컬 준비본에 새 ZIP을 덮어 복원하면 충돌할 수 있으므로 새 디렉토리에 현재 저장소 파일과 ZIP을 함께 사용하세요.

## 4. 모델 없이 결과를 읽고 검증하기

답변·평가 화면은 Python 표준 라이브러리로 실행됩니다.

```powershell
py -3.11 -X utf8 scripts/serve_results.py --port 8767
```

<http://127.0.0.1:8767/evaluation>에서 현재 결과 `sol-revision-formal-20260929-v3`를 선택합니다. 원문 이미지 렌더링·수치 검증을 위해 PyMuPDF만 설치할 수도 있습니다. 서버를 `Ctrl+C`로 종료한 뒤 아래 명령을 실행합니다.

```powershell
pwsh -File scripts/setup.ps1 -Mode view
.\.venv-view\Scripts\python.exe -X utf8 scripts/verify_saved_results.py
.\.venv-view\Scripts\python.exe -X utf8 scripts/serve_results.py --port 8767
```

검증 보고서는 `validation/local/saved-results-verification.json`에 저장됩니다. 원래 검증 프로그램의 계산·대조 로직을 실행하되 보고서 저장 위치만 분리합니다. API·모델 다운로드·생성은 수행하지 않습니다.

공개용으로 바뀐 문서의 백업 목록은 공개 사본 해시를 가리키도록 갱신했습니다. 원래 목록은 `artifacts/source-bundles.json`에 해시를 남겼고, 변경 전후 관계는 `publication-changes.json`에 있습니다. 계산 결과와 인용문·캡처를 대조하는 로직은 그대로 실행합니다.

## 5. 전체 Python 환경 설치

로컬 생성이나 전처리 재생까지 실행하려면 세 환경을 만듭니다.

```powershell
pwsh -File scripts/setup.ps1 -Mode full
```

설치 위치는 `preprocessing/.venv`, `retrieval/.venv`, `experiment/evaluation/.venv`입니다. 각 디렉토리의 `requirements.lock.txt`를 사용하며 검색 환경의 CPU PyTorch는 공식 PyTorch 배포 저장소에서 먼저 설치합니다. 가상환경 활성화 대신 이후 명령처럼 사용할 Python 경로를 명시합니다. 이 단계에는 모델 다운로드나 평가 API 호출이 없습니다.

버전이 내려받아지지 않으면 최신 버전으로 임의 대체하지 않습니다. 원래 잠금 파일을 보존하고, 별도의 환경 변경 기록과 새 실행으로 다뤄야 합니다. 설치된 패키지가 서로 호환되는지는 setup 마지막의 `pip check`로 확인합니다.

## 6. 로컬 모델 다운로드와 등록

다음 명령은 이미 보관한 모델 잠금 파일을 읽고 정확한 revision의 파일을 다운로드합니다. 잠금 파일을 덮어쓰지 않습니다.

```powershell
py -3.11 -X utf8 scripts/download_models.py --model bge
py -3.11 -X utf8 scripts/download_models.py --model qwen
```

| 용도 | 고정 자료 |
| --- | --- |
| 검색 모델 | BAAI/bge-m3, revision `5617a9f61b028005a4858fdac845db406aefb181` |
| 생성 모델 | bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF, revision `ae44f08e1392f39c0e474af10c3ff8355c8b6688` |
| 생성 파일 | Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf |

Qwen 파일은 Qwen 원 모델을 양자화한 외부 배포자의 GGUF입니다. `ollama pull`로 이름이 비슷한 모델을 받는 대신 이 고정 파일을 사용합니다. 원 다운로드 모듈은 잠금 파일이 이미 있으면 가중치도 설치되어 있다고 가정하므로, 새 설치에서는 위 배포용 명령을 사용하세요.

실험 서버는 기본 Ollama 포트 11434와 구별한 **11435**를 사용합니다.

```powershell
pwsh -File scripts/start_ollama.ps1
$env:OLLAMA_HOST = '127.0.0.1:11435'
Push-Location experiment
try {
    ollama create kidet-qwen3-4b-instruct-2507:q4-k-m-v1 -f Modelfile
    if ($LASTEXITCODE -ne 0) { throw 'Ollama 모델 등록 실패' }
} finally {
    Pop-Location
}
py -3.11 -X utf8 scripts/preflight.py --ollama
```

서버는 숨겨진 프로세스로 실행되고 PID는 `experiment/reports/ollama-pid.txt`, 로그는 같은 폴더의 `ollama-stdout.log`·`ollama-stderr.log`에 남습니다. 모델 저장소는 `experiment/models/ollama/`입니다. 이미 11435를 사용 중인 프로세스가 있으면 새 시작 도구는 중단합니다. 같은 PC에서 원 연구 서버와 복제본의 정식 실험을 동시에 실행하지 않습니다.

## 7. 검색 자료 검사

복원한 인덱스의 파일·벡터·청크 대응부터 검사합니다. 검증 보고서는 새 위치를 지정합니다.

```powershell
.\retrieval\.venv\Scripts\python.exe -X utf8 -m retrieval.verify --report validation/local/index-verification.json
```

실제 모델로 문서 벡터를 다시 계산하고 싶다면 다음 중 하나를 실행합니다. 전체 8,344개 재계산은 시간이 걸립니다.

```powershell
# 표본 24개 문서 벡터 재계산
.\retrieval\.venv\Scripts\python.exe -X utf8 -m retrieval.verify --replay-model --report validation/local/index-model-replay.json

# 전체 문서 벡터 재계산
.\retrieval\.venv\Scripts\python.exe -X utf8 -m retrieval.verify --full-replay --report validation/local/index-full-replay.json
```

검색 화면만 열려면 `retrieval/.venv/Scripts/python.exe -X utf8 -m retrieval.app`을 실행하고 <http://127.0.0.1:8766/>에 접속합니다. 개발용 검색은 고정 60문항과 동일한 질문을 차단하므로 정식 질문은 다음 비교 실행기를 통해 처리합니다.

## 8. 새 답변 생성: 개발 점검 → 본 실행

아래 명령은 고정된 원본 ID `formal-v1`을 재사용하지 않습니다. 정답 근거는 생성 입력에 넣지 않으며 두 조건은 같은 질문과 모델을 사용합니다.

```powershell
# 별도 개발 질문 10개 × 두 조건으로 실행·토큰·시간 측정을 점검
.\retrieval\.venv\Scripts\python.exe -X utf8 -m experiment.runner prepare --id reproduction-pilot-v1 --mode pilot
.\retrieval\.venv\Scripts\python.exe -X utf8 -m experiment.runner run --id reproduction-pilot-v1
.\retrieval\.venv\Scripts\python.exe -X utf8 -m experiment.runner certify-pilot --id reproduction-pilot-v1

# 같은 환경의 점검이 PASS인 경우에만 60문항 × 두 조건 × 세 회차 실행
.\retrieval\.venv\Scripts\python.exe -X utf8 -m experiment.runner prepare --id reproduction-v1 --mode formal
.\retrieval\.venv\Scripts\python.exe -X utf8 -m experiment.runner run --id reproduction-v1

# 수집한 입력·출력 검사, 집계, 첫 회차 평가 입력 준비
.\retrieval\.venv\Scripts\python.exe -X utf8 -m experiment.audit --id reproduction-v1
.\retrieval\.venv\Scripts\python.exe -X utf8 -m experiment.report --id reproduction-v1
.\retrieval\.venv\Scripts\python.exe -X utf8 -m experiment.package_evaluation --id reproduction-v1
```

정상 종료 후 `experiment/runs/reproduction-v1/attempts/`에 360개 요청 기록이 생기며, 내용 평가에는 `evaluation-inputs/answers.jsonl`의 첫 회차 120개를 사용합니다. 시간은 세 회차 모두 정상인 공통 문항에서 질의별 중앙값 등을 계산합니다. 워밍업은 본 측정과 별도로 저장됩니다.

개발 점검은 `experiment/reports/pilot-readiness.json`을 현재 환경의 결과로 갱신합니다. 다른 장비의 새 실행을 시작한 뒤에는 원래 파일과 비교하는 `verify_artifacts.py --scope all`이 해당 변경을 탐지하는 것이 정상입니다. 원본 그대로의 검증용 사본과 새 실행용 사본을 분리하면 관리하기 쉽습니다.

## 9. 새 답변의 자동평가 — 선택 단계, 유료 API

로컬 답변 수집과 별개입니다. 저장된 연구 결과를 보는 데 이 단계는 필요하지 않습니다. 사용하려면 GPT-6 Sol에 접근할 수 있는 OpenAI API 키가 필요하며, 비용은 호출량과 계정 정책에 따라 발생합니다. 모델을 사용할 수 없으면 다른 모델로 자동 대체하지 않습니다.

PowerShell에서 키를 화면·명령 이력에 남기지 않고 현재 터미널 프로세스에만 넣는 예입니다.

```powershell
$judgeKeyInput = Read-Host 'OpenAI API 키' -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new('', $judgeKeyInput).Password
Remove-Variable judgeKeyInput
.\experiment\evaluation\.venv\Scripts\python.exe -X utf8 -m experiment.evaluation.runner doctor --profile openai-sol
```

원 실험과 같은 단계로 재연하려면 먼저 최초 평가 기준으로 새 답변을 채점하고, 저장된 역질문·벡터로 관련성 수치를 재계산한 다음 개정 기준을 적용합니다.

```powershell
# 여기의 prepare까지는 실제 평가 API를 호출하지 않음
.\experiment\evaluation\.venv\Scripts\python.exe -X utf8 -m experiment.evaluation.runner prepare --id reproduction-base-v1 --profile openai-sol --source-run reproduction-v1

# 이 run부터 실제 평가 API 호출
.\experiment\evaluation\.venv\Scripts\python.exe -X utf8 -m experiment.evaluation.runner run --id reproduction-base-v1

# 저장된 자료의 수치 재계산: API 추가 호출 없음
.\experiment\evaluation\.venv\Scripts\python.exe -X utf8 -m experiment.evaluation.verification.recalculate_relevancy --source reproduction-base-v1 --id reproduction-base-numeric-v1

# 새 실행의 답변에 현재 gold-v2 기준을 연결: API 호출 없음
.\experiment\evaluation\.venv\Scripts\python.exe -X utf8 scripts/prepare_revised_evaluation.py --source-evaluation reproduction-base-numeric-v1 --id reproduction-revised-v2

# 현재 개정 기준으로 재평가: 실제 API 호출
.\experiment\evaluation\.venv\Scripts\python.exe -X utf8 -m experiment.evaluation.revision_runner run --id reproduction-revised-v2
```

개정 준비 도구는 원래 `revision_runner`가 원 실험 ID를 고정해 읽는 부분을 새 실행에 연결하는 별도 도구입니다. 채점 엔진과 지표 계산은 기존 코드를 사용하며, 준비 도구의 해시와 입력·이전 판정을 새 manifest에 기록합니다.

원 실험 v3의 인용 복원은 당시 확인된 M18 사례를 처리한 이력입니다. 새 응답에 같은 보정이 필요하다고 가정하지 않습니다. 평가 오류가 생기면 해당 원본 응답·오류를 보존하고 원인에 맞게 별도 처리합니다. 점수가 좋아질 때까지 재호출하지 않습니다.

## 10. 전처리·청킹 재생 — 선택 단계

실험 실행에는 이미 고정한 corpus를 복원해 사용하면 됩니다. 다음 명령은 고정 OCR 추출본과 기록된 보정안을 이용해 앞 단계를 다시 생성합니다. 새 LLM이나 OCR 추정을 하지 않으며, 출력은 항상 새 디렉토리입니다.

```powershell
Push-Location preprocessing
try {
    # 고정 OCR로 PDF 전체 추출 다시 실행
    .\.venv\Scripts\python.exe -X utf8 parse_full_manual.py --snapshot assets/ocr-full-manual-v2 --output output/reproduction-parsed-v1
    .\.venv\Scripts\python.exe -X utf8 ../scripts/verify_parse_replay.py --replay output/reproduction-parsed-v1

    # 최종 보정 기록 재적용과 실제 차이 대조
    .\.venv\Scripts\python.exe -X utf8 correct_extraction.py --ledger corrections/batch-019/correction-log.json --output output/reproduction-corrected-v1
    .\.venv\Scripts\python.exe -X utf8 verify_corrections.py output/reproduction-corrected-v1 --ledger corrections/batch-019/correction-log.json --report ../validation/local/correction-replay.json

    # 고정한 보정·구조 입력에서 새 corpus 생성
    .\.venv\Scripts\python.exe -X utf8 -m corpus.build --output output/reproduction-corpus-v1
    .\.venv\Scripts\python.exe -X utf8 -m corpus.verify output/reproduction-corpus-v1 --report ../validation/local/corpus-replay.json
} finally {
    Pop-Location
}
```

보정·청킹 명령은 원본 잠금 파일이 가리키는 입력을 사용합니다. 바로 앞에서 만든 새 출력으로 참조 경로를 몰래 바꾸지 않습니다. 각 단계가 고정 입력에서 같은 결과를 만드는지 확인하는 절차이며, 새 OCR부터 시작하는 별도 파이프라인 실험과 구분합니다. 새로 OCR을 계산하면 인식 결과가 달라질 수 있습니다.

추출 재생의 원래 비교 프로그램은 30개 파일 중 manifest의 `ocr_worker_sha256`도 비교합니다. 과거 추출 이후 OCR worker 코드가 바뀌어 이 한 필드가 다르지만, 고정 OCR 재생에서는 그 worker로 새 OCR을 계산하지 않습니다. 위 배포용 검증 도구는 원 검증기의 27개 검사를 그대로 실행하고, 다른 29개 파일이 모두 같고 이 필드 하나만 다른 경우를 별도로 기록합니다. 원 보고서를 완전한 바이트 일치로 바꾸거나 차이를 숨기지 않습니다.

## 11. 중단과 오류 처리

| 상황 | 확인할 내용 |
| --- | --- |
| `RUN_ALREADY_EXISTS` | 완료·실패 기록을 덮어쓰지 말고 새 ID 사용. 진행 중인 실행을 재개할 때만 같은 `run` 명령 사용 |
| 원본 해시 불일치 | Git 줄바꿈 변환·파일 수정·불완전 복원 여부 확인. 원본 manifest를 현재 파일에 맞춰 고치지 않음 |
| CPU 배치 불일치 | 이 PC의 실제 성능 코어 구조와 기록한 설정 비교. 다른 장비 조건은 별도 설정·인덱스·실행 버전이 필요 |
| 토큰 수·문맥 길이 불일치 | GGUF·토크나이저·Ollama 버전과 Modelfile 확인 |
| 11435/8767 포트 사용 중 | 기존 프로세스의 목적 확인. 결과 조회는 다른 포트 사용 가능 |
| 생성 중 `active.json`/STOPPED | 이전 요청 종료 여부와 실패 기록 확인. 잠금 파일을 임의로 삭제해 우회하지 않음 |
| 평가 API 중단 | 동일한 `run --id`로 재개. 완료된 답변은 재사용하며 실패 이력을 보존 |
| 자동평가 오류 | 해당 없음과 0점을 구분. 기존 기록을 숨기거나 유리한 판정만 선택하지 않음 |

모델 alias의 제공 상태·내부 갱신과 GPU 연산은 새로운 시점의 결과에 영향을 줄 수 있습니다. 이 배포본은 원 실험의 입력·출력·모델 판본·설정과 검증 근거를 제공하며, 새 실행의 완전한 바이트 일치까지 보장하지는 않습니다.

## 참고 문서

- [Ollama Windows 설치](https://docs.ollama.com/windows)
- [Ollama GGUF 가져오기](https://docs.ollama.com/import)
- [Python 3.11.9 배포](https://www.python.org/downloads/release/python-3119/)
- [실제 배포본 검증 범위](package-validation.md)
