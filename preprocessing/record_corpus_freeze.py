"""Write the final experiment-input receipt and Korean preprocessing record."""
from collections import Counter
from corpus.common import *


def md(path,text):
    path.write_text(text.replace('\r\n','\n').replace('\n','\r\n'),encoding='utf-8',newline='')


def main():
    work=PACKAGE/'reports/rules-v6-freeze';run=BASE/'output/corpus-v6-final'
    a=read_json(run/'audit.json');s=read_json(run/'build_summary.json');m=read_json(run/'manifest.json')
    c=read_json(work/'comparison/comparison.json');source=read_json(PACKAGE/'reports/corrected-v19-audit.json')
    tests=read_json(work/'tests-results.json');runtime=read_json(work/'runtime.json')
    assert a['corpus_ready_for_index'] and a['mechanical_status']=='PASS' and not a['errors']
    assert c['deterministic_replica'] and c['all_source_changes_match_ledger']
    assert c['previous_inputs_preserved']==c['previous_input_count']
    assert source['status']==tests['status']==runtime['status']=='PASS'
    rules=PACKAGE/'rules/v6-final';history=read_jsonl(run/'review_history.jsonl')
    frozen={'schema':1,'state':'FROZEN_FOR_TEXT_RESEARCH','date':'2026-09-25',
      'corpus_version':s['corpus_version'],'corpus':run.relative_to(ROOT).as_posix(),
      'replica':'preprocessing/output/corpus-v6-final-replica','manifest_sha256':sha(run/'manifest.json'),
      'input_lock_sha256':sha(PACKAGE/'inputs.lock.json'),'source_pdf_sha256':sha(ROOT/read_json(run/'config.json')['source_pdf']),
      'corrected_source':'preprocessing/output/corrected-v19-a','correction_ledger':'preprocessing/corrections/batch-019/correction-log.json',
      'rules':'preprocessing/corpus/rules/v6-final','summary':s,'audit':a,
      'review_history_categories':dict(Counter(r['code'] for r in history)),
      'source_correction_audit':source,'tests':tests,'runtime':runtime,
      'comparison':'preprocessing/corpus/reports/rules-v6-freeze/comparison/comparison.json',
      'before_backup':'preprocessing/backups/corpus-freeze-before-20260924-233201/manifest.json',
      'scope_policy':'preprocessing/corpus/그림과_텍스트_처리원칙.md',
      'replay_invokes_llm':False,'correction_authoring_used_codex':True,
      'semantic_all_characters_certified':False,'human_source_review':'NOT_PERFORMED',
      'change_policy':'Create a new version; retain this frozen input and associate evaluation results with its manifest.'}
    write_json(work/'freeze.json',frozen)
    categories='\n'.join(f'| `{k}` | {v:,} |' for k,v in frozen['review_history_categories'].items())
    text=f'''# 데이터 전처리 실시사항

2026-09-25. 작업 전 데이터를 백업한 뒤 추가 추출 오류와 문장·조건 연결을 보완했다. 그림의 처리 범위를 정하고 정상 검토 항목의 종료 이력을 남겼으며, 전체 실험 범위를 다시 생성해 **`corpus-v6-final`을 텍스트 RAG 실험 입력본으로 고정했다.**

## 1. 최종 입력과 결과

| 구분 | 적용본 |
| --- | --- |
| 원본 PDF | `제출 논문 초안/논문참고자료/TM_9-2320-280-20-1_1996_Change2_2004_TFS_archive.pdf` |
| 파싱 원시 자료 | `preprocessing/output/full-manual-v2-a`, `preprocessing/output/corrected-v19-a/units-before.jsonl` |
| 보정 후 텍스트 | `preprocessing/output/corrected-v19-a/units-corrected.jsonl` |
| 유효 보정 목록 | `preprocessing/corrections/batch-019/correction-log.json` |
| 구조·선택 규칙 | `preprocessing/corpus/rules/v6-final` |
| 검색 corpus와 청크 | `preprocessing/output/corpus-v6-final` |
| 독립 반복 생성본 | `preprocessing/output/corpus-v6-final-replica` |
| 고정 기록 | [freeze.json](rules-v6-freeze/freeze.json) |

원본 파일은 총 890쪽이다. 기존에 정한 연구 범위인 제1·2장, **PDF 31–863쪽의 833쪽 전체**를 처리했다. 평가질의의 근거 부분만 선별하지 않았다. 이 문서의 쪽수는 PDF 파일 기준이다.

| 항목 | 이전 v5 | 고정본 v6 |
| --- | ---: | ---: |
| 청킹 전 구조단위 | 3,816 | {s['units']:,} |
| 청크 | 3,852 | {s['chunks']:,} |
| 청크 최대 토큰 | 500 | {a['max_chunk_tokens']} |
| 청킹 실패 | 0 | {len(s['chunk_failures'])} |
| 활성 검토 항목 | 6,260 | {a['review_count']} |
| 선택 보류 구간 | 2,931 | {a['pending_selection_spans']} |
| 대체 표현의 미결 대상 | 211 | {a['pending_representation_destinations']} |

500토큰은 모든 청크의 고정 길이가 아니라 **제목·조건을 포함한 최대 길이**다. 같은 구조단위가 길 때 그 본문 안에서 100토큰 중첩을 적용한다. 독립 표 행·질문·시험 방법·조건을 길이만으로 합치지 않아 청크 수가 늘었다. 청크 수에 500을 곱한 값은 교범의 총 토큰 수가 아니다.

## 2. 백업과 원본 보존

작업 전 [백업 명세](../../backups/corpus-freeze-before-20260924-233201/manifest.json)에 7,533개 파일을 보존했다. 원본 파일 합계는 1,141,080,514 bytes이며 ZIP과 모든 압축 항목의 해시를 확인했다. 작업 후 백업 위치와 검증 결과는 [완료 기록](rules-v6-freeze/completion.json)에 남긴다.

- 작업 전 ZIP SHA-256: `c8c0eba77c8bcc2fc9a0d5930f476f80f9c8e5224920a34b9cf7408d35b4ce34`.
- 원본 PDF SHA-256: `{frozen['source_pdf_sha256']}`.
- 기존 corpus의 잠금 입력 {c['previous_input_count']:,}개가 모두 보존됐음을 전후 비교로 확인했다.
- 원시 파싱, 이전 보정본, 기존 v5 corpus는 덮어쓰지 않았다. 중간 검토본도 이력으로 남겼다.

## 3. 실제 수정 내용

| 대상 | 실시 내용 |
| --- | --- |
| OCR 혼합과 문자 선택 | 671쪽의 고정 단어 좌표를 원시 문자와 정확히 대응시켰다. 저신뢰 박스와 native/OCR 차이 후보를 PDF와 대조하고, 확인한 내용만 보정 목록에 반영했다. 재OCR 출력은 자동 채택하지 않았다. |
| native 본문·조건 | 16,630줄의 인쇄 흔적을 검사했다. 303쪽의 화면에 보이지 않는 8줄은 제외하고, 좌표가 어긋난 3줄은 실제 위치를 기록했다. 질문 141개의 조건 경계를 재검사하여 45개의 범위를 좁혔다. |
| OCR 진단 질문 | 같은 질문의 왼쪽 조건과 우측 시험 방법·이유를 구별했다. 마지막 질문 아래의 종료 문구를 조건에 붙이지 않는다. 대응이 분명하지 않은 박스의 문구는 독립 텍스트로 보존한다. |
| 혼합이 심한 페이지 | 147·185·201·219·224·291·390·463·479·674·696·718·742·822쪽을 박스별로 재전사했다. 누락된 질문·원인 항목·시험 지시를 원문에서 복원했다. |
| 조건 박스 하단 | POSSIBLE PROBLEMS에서 끝나는 14사례를 대조했다. 실제로 비어 있는 10사례는 유지하고, 항목이 빠지거나 혼합된 4쪽은 복원했다. |
| 표·안내문 | 모델·속도·시험 색인·GO-chain 등의 표를 행·열과 조건으로 재구성했다. 52쪽 속도표와 54쪽 명판은 수치를 해당 열에 연결했고, 126·128쪽 안내문의 좌우 설명이 섞이지 않게 분리했다. |
| 시험 카드·경고 | 831–848쪽 중 대상 17쪽의 102개 카드 구간을 구성했다. 시험 절차에는 같은 카드의 Pre-Test·NOTES를 연결했다. 341쪽의 PCB 교체 경고와 361쪽의 멀티미터 제목도 해당 본문에 연결했다. |
| 확인된 분기 | 총 92개 연결을 원문의 질문·분기 표식·조치와 함께 기록했다. 그 밖의 화살표 경로는 새 정비 설명으로 만들지 않았다. |

최종 유효 보정 기록은 **{source['recorded_corrections']:,}건**이다. 기존 408건은 그대로 보존했으며 이번 버전에서 추가된 유효 기록은 {c['added_corrections']:,}건이다. 한 기록이 단어 하나 또는 여러 박스의 재전사를 담을 수 있으므로 이 수치를 오타 개수로 해석하지 않는다. 더 정확한 영역 전사로 대체된 이번 작업의 중간 기록은 `superseded-corrections.json`에 보관했다.

작업 명칭은 **PDF 텍스트 추출 오류 보정**이다. 원문 대조와 보정안 작성에는 Codex를 사용했다. 원문을 요약하거나 새로운 정비 설명을 추가하는 방식은 사용하지 않았으며, 고정한 보정 목록을 재실행할 때는 LLM을 호출하지 않는다.

## 4. 그림과 원문 결함의 처리

[그림과 텍스트의 처리 원칙](../그림과_텍스트_처리원칙.md)에 기준을 정리했다. 그림이 있는 페이지를 통째로 제외하지 않는다. 그 안의 독립 설명문·경고·표·질문은 포함한다. 배선의 연결, 부품 위치, 화살표 경로, 계기 모양처럼 그림 해석이 필요한 관계는 PDF와 좌표로 남기며 LLM 설명을 추가하지 않는다.

그림 라벨이나 선을 잘못 읽은 조각은 일반 본문과 분리하고 제외 이유를 기록했다. 관계가 그림에만 남는 단위에는 그림 의존 상태를 표시했다. 50쪽 명판의 희미한 중량값은 추정하지 않았고 읽을 수 있는 슬링 지시를 보존했다.

원문 자체의 이상도 고치지 않았다. 예를 들어 118쪽의 끊긴 `Metal particles are`, 408쪽의 숫자가 빠진 `130 Ω ± Ω`, 612쪽의 `wound`, 361쪽의 `reed`를 유지했다. 224쪽 배기계통 질문의 조치에도 실제로 `INDUCTION SYSTEM`이 인쇄돼 있어 `EXHAUST`로 바꾸지 않았다. 이런 값·문구를 완전한 정답으로 전제하지 않도록 원문 결함 기록을 남겼다.

그림을 읽어야 답할 수 있는 질의와 교범에 답이 없는 질의는 다르다. 평가질의의 답변 가능성은 고정본과 원본 PDF를 기준으로 구분한다.

## 5. 검토 표시 정리

재생성하면서 구조단위가 더 세분화되어 새 검토 번호가 생겼다. 아래 {a['closed_review_count']:,}건을 텍스트 범위의 정상·처리방침 확정 항목으로 종료했다. 이는 기존 6,260건과 일대일 대응하는 수치도, 수정한 오류 개수도 아니다.

| 유형 | 종료 기록 수 |
| --- | ---: |
{categories}

종료 기록은 최종 폴더의 `review_history.jsonl`에 남아 있다. 각 기록에 원문 범위, 소유 구조단위, 판정 서명, 정책 ID와 검증 근거를 연결했다. 문자 선택 충돌·열 혼합·출처 미배정·토큰 초과는 이 종료 규칙으로 해제할 수 없다.

개별 연결을 만들지 않은 박스는 문구만 독립적으로 보존하고 그 관계를 PDF에 남긴다. 이것은 텍스트 연구의 처리 범위를 확정한 것이며, 확인하지 않은 관계를 올바른 연결이라고 승인한 것이 아니다.

## 6. 검증 결과

- **보정 전후:** {source['records_checked']:,}개 원시 레코드를 전부 비교했다. 변경된 {source['changed_records']:,}개 레코드의 실제 차이 {source['actual_diff_hunks']:,}개 묶음이 보정 목록과 일치했다. 기록 밖의 변경은 검출되지 않았다. [보정 감사](corrected-v19-audit.json)
- **재현성:** 보정본 735개 파일과 corpus {len(c['replica_files'])}개 파일을 각각 별도 생성하여 SHA-256이 전부 일치했다. [전후·반복 비교](rules-v6-freeze/comparison/comparison.json)
- **corpus 검사:** 문자 처리 기록·출처 대응·조건 계약·표·청크 재구성·500토큰 상한·검토 종료 이력을 검사했다. 기계 검사 {a['checks']:,}개를 통과했다. [최종 감사](../../output/corpus-v6-final/audit.json)
- **회귀 검사:** {tests['total_tests']}개 테스트를 통과했다. 문자 변조, 표의 행·열·수치 손실, 잘못된 조건 연결, 숨은 native 문자, 종료 문구의 조건 혼입 등을 확인했다. [테스트 결과](rules-v6-freeze/tests-results.json)
- **재생성 중 발견한 문제:** 시험 카드 정의가 갱신 과정에서 빠지는 문제를 복원하고 별도 카드 목록 검사를 추가했다. 6개의 제목·표제 대체 참조가 순환하던 문제도 최종 채택 대상을 명시해 해결했다. 실패한 중간본은 최종본으로 사용하지 않는다.
- **앱 확인:** 기존 localhost 서버에 읽기 전용 요청을 보내 최종본의 요약·청크·검토 목록·원본 이미지 응답을 확인했다. 서버 재시작 명령은 자동 승인 검토에서 차단됐으며 구체적인 사유는 제공되지 않았다. 새 생성 파이프라인은 CLI로 검증했다. [실행 확인](rules-v6-freeze/runtime.json)

자동 검사는 기록 밖의 변경과 구조 규칙 위반을 확인한다. 원본 PDF의 모든 글자와 모든 화살표를 사람이 전수 검수했다는 뜻은 아니다. 이번 고정은 문서에 명시한 텍스트 연구 범위와 검증 결과를 기준으로 한다. 고정 후 수정이 필요하면 새 버전을 만들고 해당 버전을 사용한 실험 결과를 구분한다.

| 자료 | 확인 상태 | 범위 |
| --- | --- | --- |
| 원본 PDF | PARTIAL | 파일 전체 해시, 전체 OCR 구조 자료, 보정·예외·표본 페이지의 PDF 대조. 모든 글자와 그림 관계의 전수 검수는 아님 |
| 원시 자료·보정 기록·보정본 | VERIFIED | 전체 레코드 전후 비교와 보정 목록의 일치, 반복 생성 일치 |
| 최종 corpus·규칙·검토 이력 | VERIFIED | 833쪽 전체 문자 처리·출처·토큰·규칙 검사와 두 번 생성한 파일 일치 |
| 논문·60개 평가질의 | NOT_INSPECTED | 이번 데이터 처리에서 읽거나 변경하지 않음 |

## 7. 다시 실행하기와 다음 단계

`preprocessing` 폴더에서 실행한다. 출력은 새로운 폴더로 지정한다.

```powershell
.\\.venv\\Scripts\\python.exe -X utf8 correct_extraction.py --ledger corrections/batch-019/correction-log.json --output output/corrected-replay
.\\.venv\\Scripts\\python.exe -X utf8 verify_corrections.py output/corrected-replay --ledger corrections/batch-019/correction-log.json --report audit/replay.json
.\\.venv\\Scripts\\python.exe -X utf8 -m corpus.build --output output/corpus-replay
.\\.venv\\Scripts\\python.exe -X utf8 -m corpus.verify output/corpus-replay --report corpus/reports/replay.json
```

현재 설정은 corrected-v19-a와 rules/v6-final을 읽는다. tokenizer와 입력 파일은 해시로 고정했다. 새 OCR·외부 생성형 AI API 호출 없이 같은 추출 스냅샷 이후의 결과를 재생성한다.

다음 단계는 이 corpus의 임베딩·검색 인덱스를 만들고 평가질의의 근거를 고정하는 것이다. 이후 동일한 LLM의 LLM Only/RAG 조건을 비교한다. 이번 작업에서 검색·LLM·RAGAS 성능 실험을 수행한 것은 아니다.
'''
    md(PACKAGE/'reports/데이터_전처리_실시사항_2026-09-25.md',text)
    old=PACKAGE/'reports/표재추출_문자보정_조건연결_실시기록_2026-09-24.md'
    content=old.read_text(encoding='utf-8');pointer='> 최신 상태: [2026-09-25 데이터 전처리 실시사항](데이터_전처리_실시사항_2026-09-25.md). 아래는 v5 당시 기록이며 최종 입력은 v6 고정본이다.\n\n'
    if not content.startswith('> 최신 상태:'):md(old,pointer+content)
    readme=f'''# HMMWV corpus 앱

**실험 입력 고정본:** `hmmwv-v6` / `corpus-v6-final`. PDF 31–863쪽의 833쪽에서 청크 **{s['chunks']:,}개**를 생성했다. 활성 검토 항목과 선택 보류는 0이며 두 번 생성한 파일이 모두 일치했다. [데이터 전처리 실시사항](reports/데이터_전처리_실시사항_2026-09-25.md)에 수정 내용과 검증 범위를 기록했다.

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
- `inputs.lock.json`: 입력·규칙·원문 대조 근거 {len(m['inputs']):,}개 파일의 SHA-256.
- [고정 기록](reports/rules-v6-freeze/freeze.json): 최종 manifest와 검증 결과.

원본 PDF는 총 890쪽이다. 기존 연구 범위 전체를 처리했으며 평가질의에 맞춰 교범을 선별하지 않았다. 500은 상한이므로 청크 수에 500을 곱해 원문 토큰 수로 해석하지 않는다.

## 그림과 검토 기록

독립 설명문·경고·표·진단 박스 문구는 사용한다. 그림의 위치·배선·화살표를 LLM 설명으로 추가하지 않는다. 확인된 92개 분기 연결 외의 그림 관계는 PDF에 남긴다. [처리 원칙](그림과_텍스트_처리원칙.md)을 적용한다.

정상 구조 검토 {a['closed_review_count']:,}건은 출처·정책·판정 서명과 함께 종료 이력으로 옮겼다. 선택 충돌·열 혼합·출처 미배정·토큰 초과는 자동 종료 대상이 아니다. `corpus_ready_for_index=true`는 이 텍스트 범위와 검사를 통과한 상태이며, 원본의 모든 문자와 그림 관계를 사람이 전수 검수했다는 뜻은 아니다.

## 생성과 독립 검증

다음 명령은 `preprocessing` 폴더에서 실행한다. 출력 폴더는 새 이름이어야 한다.

```powershell
.\\.venv\\Scripts\\python.exe -X utf8 -m corpus.build --output output/corpus-my-run
.\\.venv\\Scripts\\python.exe -X utf8 -m corpus.verify output/corpus-my-run --report corpus/reports/my-verification.json
.\\.venv\\Scripts\\python.exe -X utf8 -m unittest discover -s corpus/tests -v
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
'''
    md(PACKAGE/'README.md',readme)
    print({'state':frozen['state'],'chunks':s['chunks'],'closed_reviews':a['closed_review_count'],'report':'corpus/reports/데이터_전처리_실시사항_2026-09-25.md'})


if __name__=='__main__':main()
