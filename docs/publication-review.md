# 공개 전 보강 내역

작업일: 2026-09-29. 공개 준비본 버전: `20260929-publication-v3`.

## 공개 문서 정리

Git 대상 Markdown 74개와 자료 ZIP의 Markdown 29개를 검색하고 해당 문맥을 확인했습니다. 실험 문서 37개에서 연결할 수 없는 문서 참조와 작성 메모를 정리했습니다. 필요한 정의·설정·판정 근거는 문서 자체와 저장소 내부 링크로 설명합니다.

보고서 생성기와 화면 파일 8개에도 같은 문구 정리를 적용했습니다. 관련 활성 해시 목록 3개를 갱신하고 review-evidence ZIP을 다시 만들었습니다. 나머지 ZIP 2개와 원 연구 자료는 유지했습니다. 이번 변경을 포함한 공개 파생 파일·이동 기록은 총 50건입니다.

수정 전 공개 파일과 ZIP 3개는 저장소 밖에 백업했습니다. 현재 검증 결과는 [배포본 검증 기록](package-validation.md), 결정 근거는 [P15](packaging-decisions.md#p15-공개-문서의-독립성과-재생성-일치)에 있습니다.

## 앞선 보강 내역 (v2)

| 항목 | 적용 내용 |
| --- | --- |
| PC 경로 | 문서·JSON·검토 보존본 11개에서 로컬 사용자 경로를 치환. Markdown 링크는 프로젝트 상대경로로 수정 |
| HWPX 메타데이터 | 평가질의 부록 사본 2개의 creator·lastsaveby를 비움. 본문·서식·미리보기 등 다른 ZIP 항목의 바이트는 유지 |
| 검증 목록 | holdout manifest, 활성 baseline, 백업 파일 목록 3개의 관련 해시만 공개 사본에 맞게 갱신 |
| 과거 서버 로그 참조 | 처음부터 배포 대상에 없던 검색 서버 로그 6개를 활성 baseline 검사에서 제외하고 원래 해시·제외 이유를 기록 |
| 임시 파일 | 기존 정식 저장 파일과 달랐던 사본 1개를 별도 archive에 그대로 보존 |
| 빈 로그 | 내용이 없는 worker.log 8개만 Git 공개 대상에서 제외 |
| 라이선스 | Qwen 토크나이저와 tessdata_fast의 공식 LICENSE·SOURCE.md를 Git과 각 자료 ZIP에 동봉 |
| Git 제외 규칙 | 개인키, 인증파일, HAR, 임시 파일의 예방용 제외 규칙 추가. 연구 JSON·일반 로그는 유지 |

## 원본과 공개 사본

연구 원본은 변경하지 않았습니다. 작업 전 Git 후보 파일과 ZIP 3개는 저장소 바깥의 로컬 작업 폴더에 백업했습니다.

- [original-files.json](../artifacts/original-files.json): 원래 Git 대상 연구 파일의 해시. 변경하지 않았습니다.
- [source-bundles.json](../artifacts/source-bundles.json): 보강 전 ZIP·원 자료 파일의 목록과 해시.
- [publication-changes.json](../artifacts/publication-changes.json): v2의 변경·이동 17건에 이번 문서 정리를 합한 50건, 빈 로그 제외 8건, ZIP의 라이선스·출처 추가 4건.
- [manifest.json](../artifacts/manifest.json): 현재 공개 ZIP의 파일 목록·크기·해시.

실험 당시 source hash를 기록한 과거 보고서는 그 의미를 유지합니다. 실제 공개 사본의 바이트를 검사하는 목록과 원본 출처 기록을 구별했습니다. 저장된 답변·인용문·점수의 계산 로직이나 판정은 수정하지 않았습니다.

## 검증

공개용 파일 검사는 다음 명령으로 실행합니다.

```powershell
py -3.11 -X utf8 scripts/verify_artifacts.py --scope all
.\experiment\evaluation\.venv\Scripts\python.exe -X utf8 -m unittest discover -s scripts/tests -v
.\.venv-view\Scripts\python.exe -X utf8 scripts/verify_saved_results.py
```

공개 사본으로 달라진 파일도 현재 해시와 일치해야 합니다. 변경 목록과 원래 출처가 맞지 않거나, 선언하지 않은 자료 변경·제외가 있으면 검증은 실패합니다. 최종 확인 결과는 [배포본 검증 기록](package-validation.md)에 기록합니다.

비밀정보 검사에는 로컬 Gitleaks v8.30.1과 별도 패턴·문서 메타데이터 검사를 사용했습니다. 비밀값은 출력하지 않았고, 검사 자료를 외부 서비스에 보내지 않았습니다. 검사한 파일 집합에서 실제 인증정보가 발견되지 않았다는 결과이며, 새 파일을 추가할 때도 포함 목록과 내용을 확인해야 합니다.

Git 후보 4,598개와 ZIP 3개를 검사했고, 미결 인증정보 후보·로컬 사용자 경로는 없었습니다. 새 디렉토리의 자료 복원, 18,900개 공개 자료 해시 검사, 저장된 120개 답변과 202개 PDF 캡처 대조, 배포 도구 테스트 19개가 모두 통과했습니다.

코드 자체의 공개 라이선스 선택과 원격 GitHub 업로드는 이번 보강 범위에 포함하지 않았습니다.
