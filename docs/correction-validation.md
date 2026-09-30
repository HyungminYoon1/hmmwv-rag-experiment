# 정정 배포 검증 — v2026.09.30

이 문서는 2026-09-29에 검토한 근거 기준을 2026-09-30에 배포하기 위한 점검 기록이다. 최초 배포와 이번 정정을 구분한다. 태그에 담긴 문서는 게시 전 검사 시점의 기록이며, 게시 후 검증은 [Release 설명](https://github.com/HyungminYoon1/hmmwv-rag-experiment/releases/tag/v2026.09.30)과 [main의 이 문서](https://github.com/HyungminYoon1/hmmwv-rag-experiment/blob/main/docs/correction-validation.md)에 추가한다. 공개한 태그는 옮기지 않는다.

## 과학적 기록과 집계

| 확인 대상 | 상태 | 실시 내용 |
|---|---|---|
| 질문 60개 | VERIFIED | gold-v2와 문구·유형 불변 비교. 원문 대조 및 개정 이유는 gold-v3/review와 decisions.json에 기록 |
| 평가 답변 120개 | VERIFIED | 원본 Sol 결과와 대조. S16의 두 답변에서 불필요한 요소만 제외. 다른 판정 값은 보존 |
| 집계 재현 | VERIFIED | 새 API 호출 없이 재계산. 별도 Decimal·집합 계산으로 검색 집계·평균·분모·조건 간 차이 확인 |
| 검색 결과 | VERIFIED | Recall@5 78.0%, 전체 필수 근거 확보 31/50. 원 생성 로그의 검색 결과로도 동일 값 계산 |
| 근거 캡처 78개 | VERIFIED | 고정 PDF에서 기록된 해상도로 다시 렌더링하여 픽셀 대조 |
| 전체 교범·청크의 의미 | PARTIAL | 관련 원문과 청크 대조. 잔여 구조 오류를 공개했으며, 890쪽 전체를 완전히 의미 검수한 것으로 간주하지 않음 |
| 독립 연구자·정비 전문가 검토 | NOT_PERFORMED | Astra의 AI 원문 대조와 구분 |

`experiment.correction verify`는 출처 해시·허용된 수정 범위·계산 일관성을 검사한다. 정답 기준의 의미를 독립적으로 판정하는 도구는 아니다. 근거 기준의 작성 오류와 Sol API 호출을 구분한 설명은 [정정 내역](corrections-20260929.md)을 참고한다.

## 프로그램과 공개 자료

게시 전 최종 점검 결과를 아래에 기록한다. Git 원본 기록과 기존 ZIP 세 개는 보존하고, 정정 결과·검사 코드·캡처 ZIP을 추가한다.

- 자동 검사: 30개 테스트 통과. 새 기준의 의미별 회귀 사례, 기존 판정 보존, 기준 선택, 추가 무결성 목록의 변조·충돌·누락 차단을 확인했다.
- 전체 공개 자료: 19,161개 파일의 크기·SHA-256 검사 통과. 원 Git 파일 4,598개 중 변경한 14개는 공개 문서·보조 도구·배포 목록이며, 원 생성·API 응답·기존 정답 기준·고정 corpus·인덱스는 그대로다.
- 기존 평가 보존 검사: 원 인용 392개, 주장 판정 762개, 요소 판정 248개, 집계 64개·짝비교 12개와 원 캡처 202개 검사 통과. 이번 추가 원문 캡처 78개는 별도 검사했다.
- 정정 재계산: 새 로컬 출력 디렉토리에서 120개 판정을 재집계해 동일 값 확인. 원 결과를 덮어쓰거나 모델을 호출하지 않았다.
- 브라우저: 실행 현황·근거 검토·답변 비교·답변 평가 화면 확인. 현재 gold-v3 기본 선택, Recall 78.0%·31/50, S16의 단일 요소와 대체 조합, 과거 평가 24.8%·77.2% 표시를 확인했다. 조회 중 콘솔 오류 없음.
- 공개 범위: Git 후보 4,745개와 HWPX 내부 XML·추가 ZIP을 검사했다. Gitleaks 후보 21건은 기존 파일의 SHA-256 값 19건과 실행 ID 2건으로 확인했으며 미결 후보는 없다. PC 계정 경로와 HWPX의 로컬 계정 메타데이터는 발견되지 않았다. 자료 경로 문자열은 보존했고, 공개 Markdown의 비공개 문서 참조는 없다. 안내·정정 문서 15개의 상대 링크가 모두 존재한다.
- 기존 자료 ZIP 세 개의 크기·SHA-256 유지. 추가 캡처 ZIP은 78개 파일, 15,212,420바이트다.
- 원격 게시·새 clone 복원: 완료. 아래 게시 후 검증에 결과를 기록했다.

## 다시 확인하는 명령

```powershell
py -3.11 -X utf8 scripts/verify_artifacts.py --scope all
py -3.11 -X utf8 -m experiment.correction verify
.\.venv-view\Scripts\python.exe -X utf8 -m experiment.correction verify --source-images
py -3.11 -X utf8 -m experiment.correction recalculate --output validation/local/gold-v3-recheck
py -3.11 -X utf8 scripts/score_retrieval.py --source-run formal-v1 --gold-version gold-v3
.\experiment\evaluation\.venv\Scripts\python.exe -X utf8 -m unittest discover -s scripts/tests -v
```


## 게시 후 검증 — 2026-09-30

- GitHub 공개 상태: public. Release `v2026.09.30`을 최신 버전으로 게시했다.
- 고정 커밋: `b7282a1f825f09f4816f576d08a0cee6fd629619`. 태그는 게시 후 옮기지 않았다. 게시 후 기록은 별도 커밋으로 main에 추가했다.
- 비인증 접근: Git 자격 증명 도우미를 끈 새 clone과 인증 헤더 없는 Release API 요청이 성공했다.
- 첨부 다운로드: 네 ZIP을 로컬 ZIP 복사나 인증 토큰 없이 HTTPS로 새로 내려받았다. 합계 540,180,164바이트이며 각 크기·SHA-256이 manifest와 일치했다.
- 복원: 새 사본에 14,418개 파일을 복원했다. Git 파일과 합쳐 19,161개 검증 대상의 크기·해시 검사가 통과했다.
- 재현: 새 사본의 60문항·120개 답변 검증과 정정 재집계가 통과했다. 전체 analysis.json이 배포본과 같고, 생성 로그를 직접 읽는 검색 집계도 Recall 78.0%·31/50을 재현했다.
- 원문: 새로 받은 78개 캡처를 원본 PDF 렌더링과 다시 대조했다. 원 평가의 202개 캡처·인용·판정 검사도 통과했다. PDF 렌더링에는 이 Windows PC에 이미 설치된 `.venv-view`의 PyMuPDF를 사용했다. 새 장비에서 환경을 다시 설치한 검사는 아니다.
- 보존: 검증 후 새 clone의 추적 파일은 변경되지 않았다. 과거 Release의 태그와 세 첨부의 ID·크기·해시는 그대로이며, 설명 앞에 정정 안내만 추가했다.

전체 과정에서 새 생성·임베딩·평가 API 호출은 없었다. 프로그램·자료 복원과 계산 재현을 확인한 결과이며, 위에 구분한 독립 전문가 검토 상태를 변경하지 않는다.
