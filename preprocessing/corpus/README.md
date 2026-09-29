# HMMWV corpus 앱

**실험 입력 고정본:** `hmmwv-v6` / `corpus-v6-final`. PDF 31–863쪽의 833쪽에서 청크 **8,344개**를 생성했다. 활성 검토 항목과 선택 보류는 0이며 두 번 생성한 파일이 모두 일치했다. [데이터 전처리 실시사항](reports/데이터_전처리_실시사항_2026-09-25.md)에 수정 내용과 검증 범위를 기록했다.

보정된 교범으로 검색 corpus와 청크를 만들고 원본 PDF·출처·검토 기록을 확인하는 로컬 앱이다. 검색 모델·LLM·RAGAS 실험은 다음 단계다.

## 실행

프로젝트 최상위의 `corpus 앱 실행.cmd`를 실행한다. 주소는 <http://127.0.0.1:8765/chunks?run=corpus-v6-final>이다. 실행 중 인터넷 연결이나 GPU는 필요하지 않다.

| 화면 | 내용 |
| --- | --- |
| `/chunks` | 청크 검색, 원문 대조, 문자 출처 |
| `/pages` | 원본 PDF 이미지와 포함·제외 기록 |
| `/reviews` | 활성 검토 항목. 종료 이력은 생성본의 `review_history.jsonl`에 보존 |
| `/runs` | 생성·검증과 실행 이력 |

상단 결과 선택에서 `corpus-v6-final`을 선택한다. `corpus-v6-final-replica`는 반복 검증용이며 내용이 같다. v5 및 gate-check·final-check 등의 이름은 이전 결과 또는 중간 검토본이다. 앱을 다시 실행하면 마지막으로 생성한 결과가 기본 선택될 수 있다.

## 현재 입력

- 문자: `preprocessing/output/corrected-v19-a/units-corrected.jsonl`.
- 보정 목록: `preprocessing/corrections/batch-019/correction-log.json`, 유효 1,504건. 원시 추출은 보존한다.
- 규칙: `preprocessing/corpus/rules/v6-final`. 질문·조건·표·시험 카드의 출처와 처리 범위를 저장한다.
- 설정: `config.json`. 범위 833쪽, 제목·조건을 포함한 **최대 500토큰**, 같은 단위 본문 안의 중첩 100토큰.
- `inputs.lock.json`: 입력·규칙·원문 대조 근거 6,576개 파일의 SHA-256.
- [고정 기록](reports/rules-v6-freeze/freeze.json): 최종 manifest와 검증 결과.

원본 PDF는 총 890쪽이다. 기존 연구 범위 전체를 처리했으며 평가질의에 맞춰 교범을 선별하지 않았다. 500은 상한이므로 청크 수에 500을 곱해 원문 토큰 수로 해석하지 않는다.

## 그림과 검토 기록

독립 설명문·경고·표·진단 박스 문구는 사용한다. 그림의 위치·배선·화살표를 LLM 설명으로 추가하지 않는다. 확인된 92개 분기 연결 외의 그림 관계는 PDF에 남긴다. [처리 원칙](그림과_텍스트_처리원칙.md)을 적용한다.

정상 구조 검토 9,953건은 출처·정책·판정 서명과 함께 종료 이력으로 옮겼다. 선택 충돌·열 혼합·출처 미배정·토큰 초과는 자동 종료 대상이 아니다. `corpus_ready_for_index=true`는 이 텍스트 범위와 검사를 통과한 상태이며, 원본의 모든 문자와 그림 관계를 사람이 전수 검수했다는 뜻은 아니다.

## 생성과 독립 검증

다음 명령은 `preprocessing` 폴더에서 실행한다. 출력 폴더는 새 이름이어야 한다.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m corpus.build --output output/corpus-my-run
.\.venv\Scripts\python.exe -X utf8 -m corpus.verify output/corpus-my-run --report corpus/reports/my-verification.json
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s corpus/tests -v
```

현재 실행 중인 서버에서는 최종본의 읽기 동작을 확인했다. 서버 재시작 명령이 차단되어 생성·검증 코드의 갱신은 CLI에서 확인했다. 새 결과를 재생성할 때는 위 CLI 명령을 사용하거나 서버를 다시 실행한 뒤 앱을 이용한다.

고정 이후 변경은 새 버전으로 만든다. 최종 출력·입력·규칙을 직접 덮어쓰지 않는다. 새 OCR이나 LLM을 실행하지 않고 고정한 추출 스냅샷과 보정 목록으로 재생성한다. 보정안 작성과 PDF 대조에 Codex를 사용한 사실은 실시 기록에 남겼다.

## 주요 출력

| 파일 | 내용 |
| --- | --- |
| `corpus_units.jsonl` | 청킹 전 본문·제목·조건과 구조단위 |
| `chunks.jsonl` | 검색 문자열·토큰 수·본문 범위·중첩 |
| `source_map.jsonl` | 청크 → 보정문 → 원시 구간·보정 ID → PDF 좌표 |
| `selection_ledger.jsonl` | 전체 문자 구간의 포함·중복·제외·보류 사유 |
| `selection_proofs.jsonl` | 중복 구간을 대신 표현하는 출처 |
| `page_coverage.jsonl`, `image_regions.jsonl` | 833쪽 처리 기록과 원본 그림 위치 |
| `review_queue.jsonl`, `review_history.jsonl` | 활성 검토와 종료 이력 |
| `manifest.json`, `audit.json`, `build_summary.json` | 입력·코드·출력 해시와 검사 결과 |

`build.py`는 실행 순서, `select_spans.py`는 채택 구간, `structure.py`·`boxes.py`·`regions.py`는 구조, `chunk.py`는 토큰 창을 담당한다. `verify.py`와 별도 검증 모듈은 출처·문자·표·조건·종료 이력을 검사한다. `app.py`는 localhost 화면과 작업 실행을 담당한다.

주요 의존성은 `tokenizers==0.23.2`, `PyMuPDF==1.28.2`다. Qwen tokenizer revision은 `cdbee75f17c01a7cc42f958dc650907174af0554`이며 모델 가중치는 필요하지 않다. 구현 근거는 프로젝트의 `research/2026-09-24_corpus_생성과_청킹_구현계획.md`, 결정 기록은 [DECISIONS.md](DECISIONS.md)에 있다.
