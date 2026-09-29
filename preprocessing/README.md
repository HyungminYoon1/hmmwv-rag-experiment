# HMMWV 교범 전처리

**현재 상태 — 추가 보정 및 재청킹:** [2026-09-24 실시 기록](corpus/reports/표재추출_문자보정_조건연결_실시기록_2026-09-24.md). 문자 입력은 `output/corrected-v9-a`, 검토용 corpus는 `output/corpus-v5-rules-c`다. 전체 OCR 감사에서 확인한 일곱 사례와 관련 10쪽을 보완하고 표 23행·74셀 및 흐름 연결 26개를 반영했다. 실험 범위 833쪽을 다시 청킹하여 3,852개를 생성했다. 전체 구조 검토는 남아 있으며 아직 실험용 확정본은 아니다. 아래 v4 및 1,126개 청크 기록은 이전 단계의 이력이다.

**v4 보정 단계:** 프로젝트 자료 3,739개 파일을 백업·검증했다. v4는 당시 보정 단계의 기준본이며 검색 corpus 구성·청킹·모델 실험은 이후 진행했다. 현재 자료와 실행 순서는 [배포본 README](../README.md)에서 확인한다.

**최신 추가 검토:** [557건 추가 검토와 보정 결과](557건_추가검토와_보정결과.md). v3와 근거 자료 253개 파일을 백업한 뒤, 남아 있던 native/OCR 차이 후보 557건을 원본 PDF와 모두 대조했다. 202개 후보에 269건의 추가 수정을 반영했으며 누적 수정 기록은 379건이다. 최신 문자 보정본은 `output/corrected-v4-a`, 표·레이어 처리 규칙은 `review-557/verified-v4-a`다. 기록 없는 변경은 없었고 재실행 보정 파일 388개와 구조 파일 19개가 각각 일치했다. PDF 118쪽의 불완전한 `Metal particles are`는 그대로 보존했다. 최종 검색 corpus의 선택·청킹은 다음 단계다.

**이전 검토:** [v3 전체 교범 추가 검토와 수정 전후 비교](전체교범_추가검토와_전후비교.md). 전체 890쪽 자동 검사, PMCS 표 검토와 누적 110건 보정의 기록이다. 그 문서에서 미검수로 남긴 557건은 위 후속 검토에서 모두 처리했다.

**최초 보정 기록:** [batch-001 결과와 재실행 방법](PDF_텍스트_추출_오류_보정.md). 이전 51건과 `output/corrected-v1-a`도 보존했다. 아래의 ‘LLM 미사용’ 설명은 최초 추출 프로그램의 실행에 관한 것이며, 이후 보정 후보 작성과 원문 대조에는 Codex를 사용했다.

**최신 전체 파싱 결과:** [전체 교범 파싱·보정 검토](전체교범_파싱_검토결과.md), [전체 파싱 실행 방법](전체교범_파싱_실행방법.md). PDF 890쪽과 OCR 702쪽을 처리한 최종 자료는 `output/full-manual-v2-a`에 있다. 아래 설명과 `output/run-a`는 최초 501쪽 OCR 처리의 기록이다.

지정된 교범의 텍스트층과 표를 추출하고, 텍스트층이 부족한 페이지에는 Tesseract OCR을 적용한다. 실행 중 LLM, 외부 생성형 AI API, 번역 모델을 사용하지 않는다. 원본 PDF를 수정하지 않는다.

**재현성의 범위:** 원본 PDF에서 OCR을 매번 새로 계산하면 일부 인식 결과가 달랐다. 따라서 `replay.py`는 함께 제공한 **고정 OCR 추출본**과 원본 PDF를 입력으로 사용한다. 원래 텍스트 추출·형식 정리·표 열 분리·출처 검사는 다시 실행하며, OCR 결과만 고정 자료를 읽는다. 이것을 ‘PDF부터 새로 OCR해도 모두 동일하다’는 결과로 해석하면 안 된다.

이 프로그램의 산출물은 **원문 검토가 가능한 중간 전처리 자료**다. 그림의 연결 관계, 조건 분기, 페이지를 넘는 의미 단위까지 확정한 최종 RAG corpus는 아니다. 청킹·임베딩·검색·RAGAS 평가는 이 프로그램에 포함하지 않는다.

## 만들어진 결과 확인

- `검증결과.md`: 실제 검사 결과와 한계.
- `output/run-a/검토용_원문대조.html`: 원본 이미지와 추출 결과를 함께 보는 자료. 브라우저에서 열면 된다.
- `audit/verification.json`: 자동 검증과 두 번 실행한 결과의 파일별 SHA-256 비교.
- `output/run-a/summary.json`: 처리 페이지 수, OCR 수, 검토 표시 등의 집계.

## 현재 PC에서 다시 실행

이미 이 폴더에 실행 환경과 OCR 언어 파일을 준비했다. 다음 명령은 PowerShell에서 실행한다. 출력 폴더는 비어 있거나 새 이름이어야 한다.

```powershell
Set-Location -LiteralPath '<PROJECT_ROOT>\preprocessing'
.\.venv\Scripts\python.exe -X utf8 .\replay.py --output .\output\run-c
.\.venv\Scripts\python.exe -X utf8 .\verify.py .\output\run-c --report .\audit\verify-run-c.json
```

동일 환경에서 첫 결과와 비교하려면 다음을 실행한다.

```powershell
.\.venv\Scripts\python.exe -X utf8 .\verify.py .\output\run-a .\output\run-c --report .\audit\compare-a-c.json
```

비교 보고서는 비교하는 두 출력 폴더 **밖**에 저장한다. 비교 대상으로 지정한 출력 폴더 안에 보고서를 추가하면 폴더 내용이 달라진다.

### 원본부터 OCR을 새로 계산할 때

```powershell
.\.venv\Scripts\python.exe -X utf8 .\preprocess.py --output .\output\new-ocr-capture
```

이 경로는 재실행할 수 있지만 OCR 문자까지 같은 결과가 나온다고 보증하지 않는다. 새 추출본을 고정 자료로 채택할 때는 원문을 대조한 뒤 **새 폴더**에 보관한다.

```powershell
.\.venv\Scripts\python.exe -X utf8 .\freeze_ocr.py --from-run .\output\new-ocr-capture --output .\assets\ocr-snapshot-next
.\.venv\Scripts\python.exe -X utf8 .\replay.py --snapshot .\assets\ocr-snapshot-next --output .\output\run-next
```

현재 `assets/ocr-snapshot`은 원시 OCR 결과를 고정해 둔 것으로, 내용 검수가 끝났거나 최종 RAG corpus가 확정됐다는 뜻은 아니다. 원본 PDF·설정·OCR 데이터·렌더러 버전·추출본의 해시가 맞지 않거나 다시 렌더링한 이미지가 달라지면 재사용을 중단한다.

## 새 환경 준비

검증 환경은 Windows x64 / Python 3.11.9다. 잠금 파일에는 이 환경에 맞는 tesserocr 2.10.0 / Tesseract 5.5.2 Windows wheel의 URL과 SHA-256이 들어 있다. Python 3.11 환경에서 다음을 실행한다. 준비 단계에는 패키지와 언어 파일 다운로드를 위해 인터넷이 필요하다. 준비 이후 `preprocess.py`는 로컬 파일만 읽는다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -X utf8 -m pip install -r .\requirements.lock.txt
.\.venv\Scripts\python.exe -X utf8 .\prepare_assets.py
```

동일 작업을 묶은 `setup.ps1`도 제공한다. Python 버전·OS·라이브러리·OCR 데이터가 달라진 환경까지 바이트 단위 일치를 보증하지 않는다. 원본, 코드, 설정, 패키지 버전, OCR 데이터 해시는 각 실행의 `manifest.json`에 기록한다.

`assets/qwen-tokenizer/`는 후속 청킹을 위해 받은 토크나이저 파일이다. 이번 추출 프로그램은 이를 사용하지 않으며, 생성 모델 가중치는 다운로드하지 않았다. OCR 데이터만 사용하는 것이므로 GPU가 필요하지 않다.

## 처리 내용과 파일

| 파일 | 내용 |
| --- | --- |
| `raw_native_pages.jsonl` | 전체 890쪽의 원래 텍스트층, 단어·줄·블록 좌표, 이미지 위치 |
| `raw_ocr_pages.jsonl` | OCR 대상 페이지의 OCR 원문과 좌표 |
| `pages.jsonl` | 페이지별 본문, 원래 텍스트와 OCR의 별도 보관, 인쇄면수, 범위, 표, 검토 표시 |
| `pmcs_table_rows.jsonl` | PDF 96~118쪽 정비 점검표의 행·열별 추출. 원문 좌표 포함 |
| `normalization_log.jsonl` | 인식된 머리말·쪽번호 제거 및 줄 앞뒤 공백 제거 기록 |
| `review_queue.jsonl` | 이미지, OCR, 표, 인쇄면수의 추가 확인 목록 |
| `outside_scope_pages.jsonl` | 제1·2장 밖의 페이지 목록. 검색 범위에서 제외 |
| `candidate_anchor_audit.jsonl` | 60개 질의 초안의 근거 문구가 추출 결과에 있는지 확인한 결과 |
| `previews/` | 원본에서 렌더링한 확인용 PNG |
| `manifest.json` | 코드·환경·입력·출력 파일의 해시 |

`assets/ocr-snapshot/`에는 원시 OCR 페이지·스캔 표의 고정 추출본과 그 출처 해시를 보관한다. `audit/ocr-capture/`는 이 추출본을 만든 실행 결과다. `output/run-a`, `output/run-b`는 고정 추출본을 사용해 다시 생성한 비교 결과다.

### 본문 및 범위

원본은 `config.json`에 지정된 SHA-256과 일치해야 한다. PDF 순번 31~863쪽이 제1·2장이다. 원래 인쇄면수와 PDF 순번을 별도로 기록한다. 864쪽 이후 색인 등과 1~30쪽의 표지·안내·목차는 원시 추출에는 보관하지만 검색 범위 표시에서는 제외한다.

머리말 제거는 페이지 위·아래에서 확인되는 문서번호·Change 표기·쪽번호에만 적용한다. 숫자·단위·부정문은 고치지 않는다. 줄끝 하이픈을 일괄 삭제하거나 문장을 새로 쓰지 않는다. 추출 실패를 답변불가 근거로 바꾸지 않는다.

### OCR

머리말 등을 제외한 원래 본문이 350자 미만이고 이미지가 있는 범위 내 페이지에 300 dpi 영어 OCR을 적용한다. 지정된 비교용 페이지도 추가 처리한다. 이 기준은 **추가 OCR 검사 대상을 고르는 기준**이며, 350자 이상이면 텍스트층이 완전하다는 뜻이 아니다. 모든 이미지 포함 페이지에 확인 표시를 남긴다.

Tesseract 언어 파일을 해시 확인 후 ASCII 임시 경로로 복사해 사용한다. 이 Windows 빌드에서는 한글 경로를 직접 전달하면 언어 파일을 열지 못하는 문제가 있어 적용한 처리다. 임시 복사본은 실행 후 자동 제거한다. OCR 스레드 수는 1로 고정한다.

PDF 렌더링은 PyMuPDF, OCR은 별도 tesserocr 프로세스에서 실행한다. 엔진은 Tesseract 5.5.2의 LSTM 전용 모드이며, 이미지마다 새 프로세스를 사용하고 적응 학습을 끈다. CPU 내적 연산은 `DOTPRODUCT=generic`으로 고정한다. 전체 페이지는 PSM 3, 표의 개별 열은 PSM 6을 사용한다. 실제 OCR에 넣은 픽셀 해시와 단어별 인식 신뢰도를 보관한다. 인식 신뢰도는 정답의 정확도를 보증하는 점수가 아니다.

OCR은 단어와 글자를 추출한다. 회로도의 연결, 화살표 방향, 정상·비정상 분기와 같은 의미를 복원하지 않는다. OCR 결과는 검수 전 자료로 저장하며, 원래 텍스트층에 덮어쓰거나 자동으로 정답 근거로 채택하지 않는다.

### PMCS 점검표

정비 점검표는 다섯 열을 분리한다. 일반 페이지에서는 실제 수직선 좌표와 해당 표의 고정 열 비율로 경계를 찾고, 항목 번호의 세로 위치로 행을 나눈다. PDF 97·103·111쪽의 표는 이미지이므로 `config.json`의 원문 대조 좌표로 셀을 잘라 OCR한다. 이 좌표 규칙은 **이 해시의 교범에만 적용**한다.

등록된 그림 영역은 OCR용 임시 이미지에서만 가린다. 원본과 원본 확인 PNG는 변경하지 않는다. 실제 그림을 가리키는 문장은 남기므로 해당 질문이 그림 해석을 요구하는지 별도로 검토해야 한다.

같은 항목이 다음 쪽으로 이어지는 부분과 항목 위쪽의 경고는 아직 자동으로 합치지 않는다. `item: null`은 항목 연결을 확정하지 않은 상단 내용이다. 이러한 연결과 그 밖의 표 구조를 먼저 확인한 뒤 의미 단위와 청크를 확정한다. 원래 텍스트와 좌표가 남아 있어 이어 붙인 근거를 추적할 수 있다.

### 근거 문구 점검

`candidate_anchor_audit.jsonl`은 대소문자·공백·일부 문장부호를 무시한 문구 존재 검사다. 정답의 충분성·수치 정확성·단일/다중 근거 분류·최종 청크 대응을 검증한 결과가 아니다. 특히 답변불가 후보가 참조하는 PDF 20쪽은 권별 구성 확인 자료이며 검색 범위 밖인 것이 정상이다.

## 검수 후 진행 순서

1. 표의 행·열, 적용 조건, 경고와 다음 쪽으로 이어지는 항목을 원문과 맞춘다. OCR 오인식은 원문에 근거한 보정 목록으로 기록한다.
2. 그림 해석이 필요한 구간과 문자만으로 답할 수 있는 구간을 정한다. 60개 후보의 모든 필수 근거가 남아 있는지 확인한다.
3. 기존 실험 규칙의 의미 단위와 Qwen 토크나이저 500 token / 같은 단위 내 100 token 중첩을 적용한다. 최종 청크·근거 대응표를 고정한 후 검색 실험으로 넘어간다.

## 근거 문서

- [PyMuPDF 텍스트 추출 설명](https://pymupdf.readthedocs.io/en/latest/recipes-text.html)
- [PyMuPDF의 Tesseract OCR 설명](https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html)
- [Tesseract 영어 데이터](https://github.com/tesseract-ocr/tessdata_fast/tree/4.1.0)
- [tesserocr의 Windows 설치 안내](https://github.com/sirfz/tesserocr#windows)
- [고정한 Windows OCR 빌드](https://github.com/simonflueckiger/tesserocr-windows_build/releases/tag/tesserocr-v2.10.0-tesseract-5.5.2)

현재 결과를 확인하려면 일반 설명보다 `검증결과.md`와 실제 원문 대조 자료를 먼저 읽으면 된다.

## 검색용 corpus 앱 — 2026-09-24

프로젝트 최상위의 `corpus 앱 실행.cmd`로 로컬 앱을 열 수 있다. 청크 탐색, 원문 페이지, 검토 목록, 생성·검증을 별도 화면에서 제공한다. [실행 안내](corpus/README.md)와 [구현·검증 결과](corpus/reports/검증결과_2026-09-24.md)를 참고한다.

v4 자료를 입력으로 833쪽에서 후보 청크 1,126개를 생성했다. 독립 검사와 두 실행의 11개 산출물 해시 비교는 통과했으며, 구조·구간 선택의 미결 항목 2,189개가 남아 있어 아직 실험 입력본으로 확정하지 않았다. 새 앱의 검사 통과가 전체 원문 의미 검토 완료를 뜻하지 않는다.
