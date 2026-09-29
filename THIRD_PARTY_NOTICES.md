# 외부 자료와 소프트웨어

이 파일은 배포본에 사용한 외부 자료의 출처 안내입니다. 각 권리자의 원문 조건을 대체하지 않습니다.

| 자료 | 사용·배포 방식 | 확인할 위치 |
| --- | --- | --- |
| 미군 HMMWV 교범 TM 9-2320-280-20-1 | 기관 공개 PDF의 보존본을 runtime-data에 포함. 표지·공개 배포 표시·출처 유지 | [판본과 수집 기록](자료/미군교범/출처_및_판본_확인.md), [출처 정리](docs/data-sources.md) |
| BAAI/bge-m3 | 가중치는 포함하지 않음. 고정 revision으로 다운로드 | [모델 카드](https://huggingface.co/BAAI/bge-m3), retrieval/models의 잠금 파일 |
| Qwen3-4B-Instruct-2507 | 생성용 원 모델 계열. 고정 토크나이저를 runtime-data에 포함 | [공식 라이선스 사본](licenses/qwen-tokenizer/LICENSE), [판본·출처](licenses/qwen-tokenizer/SOURCE.md) |
| tessdata_fast 4.1.0 | 영어 OCR 학습자료를 preprocessing-replay에 포함 | [공식 라이선스 사본](licenses/tessdata-fast/LICENSE), [판본·출처](licenses/tessdata-fast/SOURCE.md) |
| bartowski의 Qwen GGUF | Q4_K_M 양자화 파일을 별도 다운로드 | [GGUF 배포](https://huggingface.co/bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF), experiment/models의 잠금 파일 |
| Ollama | 별도 설치, 모델 제공·생성 실행 | [Ollama 저장소](https://github.com/ollama/ollama) |
| PyMuPDF, Tesseract 등 전처리 도구 | Python 의존성은 잠금 파일로 설치. 보존 OCR 결과와 실행 기록 제공 | preprocessing/requirements.lock.txt 및 preprocessing의 설명서 |
| PyTorch, Transformers, Sentence Transformers, FAISS | 별도 설치, 임베딩·검색 수행 | retrieval/requirements.lock.txt |
| RAGAS와 평가 의존성 | 별도 설치, 질문 관련성 등 자동평가 수행 | experiment/evaluation/requirements.lock.txt |

평가 모델 API의 서비스 조건과 프로젝트 코드의 공개 라이선스는 별개입니다. API 키·계정 자격 증명은 배포하지 않습니다. 모델을 설치·재배포하거나 이 코드에 라이선스를 적용할 때는 해당 고정 판본의 원문 조건을 확인하세요.

Qwen 토크나이저와 tessdata_fast 자료에는 각 ZIP 안에도 LICENSE와 SOURCE.md를 동봉했습니다. 공식 라이선스 원문과 배포 데이터의 바이트를 보존했습니다. 확인한 고정 판본의 파일 목록에는 별도의 NOTICE가 없었습니다. 이 외부 자료의 Apache-2.0 라이선스를 프로젝트 자체 코드에 적용한 것은 아닙니다.
