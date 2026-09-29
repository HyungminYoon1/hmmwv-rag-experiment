# 검색 기능 결정 기록

2026-09-28. 사용자가 검색 기능 구축을 승인했다. 기존 60개 평가질의는 연구 감독자의 지침 또는 심각한 문항 결함이 없는 한 최종 결과에 사용할 예정이다.

## R01. 고정 전처리와 검색 프로그램 분리

- 맥락: corpus-v6-final은 입력·규칙·코드 해시까지 보존한 전처리 결과다.
- 선택지: 기존 corpus 앱 수정 / 새 검색 모듈과 실행 환경.
- 결정: `retrieval/`에 별도 Python 환경과 8766 포트의 검색 화면을 만든다. 전처리 파일과 8765 서버는 유지한다.
- 이유: 전처리의 재현 기록을 유지하며 다음 실험 단계를 독립적으로 구현한다.
- 관련 파일: `architecture.md`, `app.py`, `run_search.ps1`.
- 후속 검토: LLM 비교 실행기는 이 검색 서비스를 사용한다. 화면 통합이 필요하면 전처리 고정 버전과 분리된 새 앱 버전으로 작업한다.

## R02. 기존 dense 검색 설계 유지

- 맥락: 검색 설정은 BGE-M3 CPU float32, 배치 8, L2 정규화, FAISS IndexFlatIP, Top-5다. [검색 구조](architecture.md)와 `config.json`에 같은 설정을 기록한다.
- 선택지: 기존 설계 / BM25 혼합·재순위화·질의 재작성 추가.
- 결정: 기존 설계를 따른다. CPU thread 8, interop thread 1, seed 42, eager attention, CLS pooling, 1,024차원을 명시한다. 모델 revision은 `5617a9f61b028005a4858fdac845db406aefb181`이다.
- 이유: 최종 평가질의의 검색 성능을 보면서 방법을 추가하지 않는다. 임베딩에 들어가는 텍스트는 고정 청크 본문 전체다.
- 관련 파일: `config.json`, `model.py`, `index.py`, `build.py`.
- 후속 검토: 모든 문서의 BGE tokenizer 길이를 검사한다. 질문·문서의 자동 잘림, 영벡터, 비유한값은 실패로 처리한다. 검색 점수는 정답 확률이 아니다.

## R03. 최종 평가용 60문항 보존

- 맥락: 사용자가 현재 문항을 잠정 확정했다. JSON·CSV의 질문/ID/유형이 일치하고 20/30/10 구성과 중복 없음이 확인됐다.
- 선택지: 개발에 함께 사용 / 별도 보존과 개발용 실행 차단.
- 결정: HWPX·CSV·채점기준 JSON·근거 문서를 바이트 그대로 복사하고 원본 해시를 기록한다. 질문 문구는 수정하지 않는다. 최종 근거·청크 대응표 상태는 PENDING으로 남긴다.
- 이유: 질문의 확정과 정답 근거 검증은 별도 단계다. 확정 의사가 있는 문항으로 검색 설정을 조정하지 않는다.
- 관련 파일: `benchmark.py`, `benchmarks/holdout-v1/`, `service.py`.
- 후속 검토: 동일 질문의 개발 실행을 대소문자·구두점·공백 정규화로 막는다. 의미상 바꿔 쓴 질문까지 판별하는 장치는 아니다. 연구 감독자의 지침·심각한 결함이 있으면 근거와 변경 이력을 남기고 새 버전을 만든다.

## R04. 추적 가능한 로컬 기록

- 맥락: 검색 결과가 어떤 corpus·모델·인덱스에서 나왔는지 재확인할 수 있어야 한다.
- 선택지: 화면에만 표시 / 로컬 실행별 JSON 저장 / 외부 DB 저장.
- 결정: 로컬 JSON에 질문·순위·점수·본문·출처·시간·버전을 저장한다. 개발 기록은 자동 삭제하지 않는다. 브라우저에는 검색, 기록, 자료 화면을 나눠 제공한다.
- 이유: 데이터 규모가 작고 외부 서비스가 필요하지 않다. 중복 개발 실행을 정식 평가 결과에 섞지 않는다.
- 관련 파일: `service.py`, `web/`, `runs/development/`.
- 후속 검토: 정식 실험은 별도 디렉터리·실행 계획·근거 매핑을 사용한다. 현재 시간 기록은 워밍업과 반복 횟수를 통제한 정식 실험 결과가 아니다.

## R05. 다운로드와 추론 분리

- 맥락: 공개 모델 확보에는 인터넷이 필요하지만 검색은 로컬에서 실행해야 한다.
- 선택지: 요청마다 원격 모델 조회 / 초기 다운로드 후 로컬 경로로 로딩.
- 결정: BAAI 공식 저장소의 특정 revision만 받고 파일 해시를 고정한다. 모델은 `local_files_only=True`, `trust_remote_code=False`, `weights_only=True`로 읽는다. 로컬 모델 구동 시 HF/Transformers 오프라인 설정을 적용한다.
- 이유: 검색 중 외부 AI API와 모델 최신판 변경에 의존하지 않는다. 공개 가중치 파일은 pickle 전체 객체 실행을 허용하는 방식으로 열지 않는다.
- 관련 파일: `download_model.py`, `model.py`, `models/*.lock.json`.
- 후속 검토: 독립 재실행에서 Python socket 연결을 막은 상태로 임베딩을 확인한다. 시스템 전체 방화벽 검증과 구별한다.

## R06. 실패한 초기 인덱스 보존

- 맥락: PyTorch 2.14.0+cpu 환경에서 56개 청크 처리 후 다음 배치의 벡터 유효성 검사가 실패했다. 같은 배치를 새 프로세스로 계산했을 때는 유한 벡터가 나와 문구만의 문제로 단정할 수 없다.
- 선택지: 오류 벡터를 치환·무시 / 성공할 때까지 반복 / 실행 라이브러리를 조정하고 재검증.
- 결정: 초기 부분 산출물을 `indexes/bge-m3-v1-failed-torch214`에 보존했다. CPU float32 설계는 유지하고 PyTorch 2.8.0+cpu 환경에서 검증한다. 최초 실패 자료는 최종 검색에서 사용하지 않는다.
- 이유: NaN이나 영벡터를 0으로 채우면 검색 결과가 왜곡된다. 정확한 하위 원인은 아직 특정하지 않았다.
- 관련 파일: `reports/embedding-failure-probe.json`, 실패 폴더의 `build-state.json`, `requirements.lock.txt`.
- 후속 검토: 전체 벡터 유효성, 독립 인덱스 재구성 및 별도 프로세스의 표본 재계산 결과를 완료 기록에 남긴다.

## R07. 계산 재현성과 프로세스 CPU 배치

- 맥락: PyTorch 2.8.0+cpu로만 변경해도 같은 입력의 계산 차이가 남았다. Sentence Transformers 5.1.1 / Transformers 4.55.4 조합, 공식 ONNX 그래프와 ONNX Runtime 1.30.0에서도 CPU 배치를 제한하지 않은 진단은 반복 동일성을 통과하지 못했다. 기본 연산·난수·파일 해시·입력 토큰 점검만으로 하위 원인을 특정하지 못했다. 당시 최근 2시간 WHEA 이벤트 조회는 0건이었으며, 이를 하드웨어 정상 인증으로 해석하지 않는다.
- 선택지: 반복 차이를 무시 / GPU로 실험 방법 변경 / 같은 CPU 설계에서 프로세스 배치를 고정하고 재검증.
- 결정: 마지막 방법. CPU 0 한 개에 배치한 진단은 단일·배치 입력이 동일했고, Windows CPU Set 정보에서 성능 등급이 높은 서로 다른 코어 8개를 선택한 진단도 세 번의 배치 쌍에서 최대 차이 0이었다. 논리 CPU 0·2·4·6·8·10·12·14, CPU thread 8, PyTorch 2.8.0+cpu / Sentence Transformers 5.1.1 / Transformers 4.55.4를 사용한다. ONNX는 원인 구분용 진단에만 사용한다.
- 이유: 모델·정밀도·검색 방식을 유지하면서 이 PC에서 반복 계산이 일치한 실행 구성을 명시한다. 프로세스 종료 시 해당 배치도 끝나며 BIOS·Windows 전역 전원 설정·다른 앱을 변경하지 않는다. 정확한 CPU·런타임 하위 원인은 미확정이다.
- 관련 파일: `cpu_affinity.py`, `config.json`, `model.py`, `reports/affinity-probe.json`, `reports/performance-cores-probe.json`, `reports/torch-diagnostics/`, `reports/onnx-preflight.json`.
- 후속 검토: 표본만으로 완료하지 않고 전체 8,344개 문서 벡터를 별도 프로세스에서 재계산한다. 전체 바이트 일치 기록이 있어야 앱을 시작한다. 정식 실험에도 CPU 배치와 패키지를 기록한다.

## R08. 문서 임베딩 배치 순서

- 맥락: 고정 청크의 BGE 길이는 3~531 token으로 차이가 크다. 입력 순서대로 8개씩 묶으면 짧은 청크를 긴 청크 길이로 패딩하는 계산이 늘어난다.
- 선택지: 원문 순서 배치 / 토큰 길이 순 배치 후 원래 행 순서 복원.
- 결정: BGE token 길이 내림차순, 동점 청크 ID 오름차순으로 8개씩 계산한 뒤 ID 순서의 벡터 행에 저장한다. `batch-order.json`과 배치 영수증에 행 번호를 기록한다.
- 이유: 평가질의나 검색 순위와 무관한 계산 효율 조정이다. 문서 내용·청크 구분·검색 방법·문서 배치 크기 8은 유지한다.
- 관련 파일: `build.py`, `verify.py`, `config.json`.
- 후속 검토: 독립 벡터 재계산에서도 같은 배치 구성을 사용한다. 구현 후 값을 보고 특정 질문의 순위를 개선하는 방식으로 배치를 조정하지 않는다.

## 공개 구현 근거

- [BAAI BGE-M3 공식 모델 카드](https://huggingface.co/BAAI/bge-m3): dense embedding에 Sentence Transformers 사용 가능. 배포 모듈의 CLS pooling·정규화 구성을 확인했다.
- [FAISS 공식 거리·유사도 설명](https://github.com/facebookresearch/faiss/wiki/MetricType-and-distances): 문서와 질의 벡터를 정규화한 뒤 내적 검색을 적용한다.
- [Sentence Transformers 공식 모델 API](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html): revision, 로컬 파일 제한, 모델 로딩 인자 및 encode 인터페이스를 확인했다. 실제 설치 버전과 API 구현을 별도로 점검한다.
- [Microsoft CPU Set 구조 설명](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-system_cpu_set_information): 코어·논리 프로세서·성능 등급 필드와 프로세스 배치 정보를 확인했다. 등급이 높은 코어를 고른 판단 근거이며, 이번 수치 차이의 원인을 설명하는 문헌은 아니다.

위 자료는 구현 근거다. 이 교범에 대한 검색 성능이나 현재 실험의 결과를 입증하는 자료로 사용하지 않는다.
