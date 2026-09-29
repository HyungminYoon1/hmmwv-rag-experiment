# HMMWV 교범 검색

고정된 `corpus-v6-final`의 8,344개 청크를 BGE-M3로 검색한다. 문서·질의 임베딩은 CPU float32로 계산하고, L2 정규화한 1,024차원 벡터를 FAISS IndexFlatIP에서 정확 검색한다. 상위 5개를 반환하며 동점은 청크 ID 순서로 정렬한다. 이 PC에서는 검색 프로세스를 성능 코어 8개(논리 CPU 0·2·4·6·8·10·12·14)에 배치한다. 시스템 전체의 CPU 설정을 바꾸지 않는다.

## 실행

프로젝트 최상위의 **`교범 검색 실행.cmd`**를 연다. 주소는 <http://127.0.0.1:8766/>이다. 처음 모델을 읽는 동안에는 준비 상태가 표시된다.

| 화면 | 용도 |
| --- | --- |
| 교범 검색 | 질문에 해당하는 청크 5개와 유사도, PDF 출처 확인 |
| 검색 기록 | 이전 개발 검색 결과 열기, 결과 JSON 저장 |
| 검색 자료 | corpus·모델·인덱스 설정과 평가질의 보존 상태 |

검색 결과의 ‘원문 보기’를 누르면 해당 청크의 근거 영역이 표시된 PDF 이미지가 나온다. 여러 쪽의 근거를 포함한 청크는 쪽을 바꿔 확인할 수 있다. 이 앱은 검색 결과를 제공하며 LLM 답변 생성은 아직 연결하지 않았다.

기존 `corpus 앱 실행.cmd`와 8765 포트는 전처리 자료를 확인하는 데 계속 사용할 수 있다. 전처리 고정 코드와 corpus를 수정하지 않기 위해 검색 프로그램·환경을 분리했다.

## 평가질의

현재 60개 문항을 `benchmarks/holdout-v1`에 보존했다. HWPX·CSV·채점기준 JSON·근거 문서는 원본과 같은 바이트의 사본이다. 단일 근거 20개, 다중 근거 30개, 답변불가 10개이며 문항 문구를 수정하지 않았다.

검색 기능 개발에는 별도의 질문을 사용한다. 보존된 문항과 대소문자·구두점·공백을 정규화한 질문이 같으면 개발용 검색에서 실행하지 않는다. 원문 근거·최종 청크 대응표는 후속 검증 대상이며, 현재 검색 화면에서 평가 점수를 계산하지 않는다.

## 재현 실행

프로젝트 최상위에서 실행한다. 모델 다운로드 외의 단계는 확보된 파일만 사용한다. 아래 명령은 현재 고정 인덱스를 보존하면서 별도 복제 인덱스를 만들어 대조하는 예다.

인덱스가 없는 작업 폴더에서 처음 구축할 때에는 `python -m retrieval.build`와 `python -m retrieval.verify --full-replay`를 사용한다. 이때도 아래와 같은 `retrieval/.venv`의 Python으로 실행한다. 기존 완료 인덱스에 같은 명령을 다시 실행하면 덮어쓰지 않고 중단한다.

```powershell
powershell.exe -NoProfile -File retrieval/setup.ps1
.\retrieval\.venv\Scripts\python.exe -X utf8 -m retrieval.download_model
.\retrieval\.venv\Scripts\python.exe -X utf8 -m retrieval.build --output retrieval/indexes/bge-m3-replay
.\retrieval\.venv\Scripts\python.exe -X utf8 -m retrieval.verify --index retrieval/indexes/bge-m3-replay --full-replay --report retrieval/reports/replay-verification.json
.\retrieval\.venv\Scripts\python.exe -X utf8 -m unittest discover -s retrieval/tests -v
```

중단된 **미완료** 인덱스는 같은 `--output`에 `--resume`을 붙여 재개한다. 입력·모델·설정·패키지·코드가 같아야 하며, 완료된 인덱스는 덮어쓰지 않는다. 앱은 `config.json`의 `index` 경로를 사용한다. 인덱스 생성 이후 검색 설정이나 파이프라인 코드를 바꾸면 기존 인덱스 사용을 거부한다.

개발용 CLI 검색은 아래 형식이다. 질문을 입력하면 결과와 실행 기록이 `runs/development/`에 저장된다.

```powershell
.\retrieval\.venv\Scripts\python.exe -X utf8 -m retrieval.search "Your development question"
```

서버를 실행한 상태에서 `python -m retrieval.smoke`를 실행하면 별도 개발 질문 3개를 각각 두 번 검색하고, 결과 기록·PDF 출처·평가질의 차단을 확인한다. 실제 명령은 위 예와 같은 `retrieval/.venv`의 Python을 사용한다. 차단 확인 요청은 임베딩 전에 거부되며 평가 결과를 생성하지 않는다.

`indexes/`에는 모델별 벡터, FAISS 파일, 청크 대응표, BGE tokenizer 길이와 해시를 보관한다. `manifest.json`이 없는 중간 폴더는 검색용으로 사용하지 않는다. 자료 범위 밖의 질문에도 최근접 청크는 반환되며, 낮은 유사도가 곧 답변불가 판정은 아니다.

검증 프로그램은 전체 행·벡터 정규화·파일 해시·corpus 연결·독립 FAISS 재구성·NumPy 내적을 검사한다. `--replay-model`은 모든 입력 길이를 다시 계산하고 24개 문서 벡터를 별도 프로세스로 재계산한다. `--full-replay`는 8,344개 전체를 재계산하여 바이트 동일성을 확인한다. 현재 앱은 해당 인덱스의 전체 재계산 PASS 기록(`reports/index-verification.json`)이 있어야 시작한다. 이 검사는 검색 관련성 평가나 60문항의 정답 검증을 대신하지 않는다.

배치는 BGE 토큰 길이 내림차순·청크 ID 순서로 구성하여 패딩을 줄인다. 계산 후 벡터를 원래 청크 ID 순서로 복원하고 배치별 원래 행 번호를 보관한다. 다른 PC에서 사용할 때에는 실제 CPU 배치와 환경을 다시 검증하고 새 설정·인덱스·검증 기록을 만들어야 한다.

설계와 정책은 [architecture.md](architecture.md), [DECISIONS.md](DECISIONS.md)에 기록한다. 실제 검증·실행 결과는 `reports/`에서 확인한다.
