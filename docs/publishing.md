# GitHub 게시와 배포

저장소는 [HyungminYoon1/hmmwv-rag-experiment](https://github.com/HyungminYoon1/hmmwv-rag-experiment)이며 공개 범위는 public입니다. 고정 자료 ZIP 4개는 [Release `v2026.09.30`](https://github.com/HyungminYoon1/hmmwv-rag-experiment/releases/tag/v2026.09.30)에서 제공합니다. 이번 배포의 점검 범위와 게시 후 다운로드·복원 결과는 [정정 배포 검증](correction-validation.md)에 기록합니다. [최초 배포 검증](package-validation.md)은 이전 버전의 기록입니다.

## 저장소와 첨부 자료

`hmmwv-rag-experiment` 디렉토리만 Git 저장소의 루트로 사용합니다. 상위 `github-export` 전체나 원 연구 폴더 전체를 올리지 않습니다.

```
github-export/
├─ hmmwv-rag-experiment/     # GitHub 저장소로 만들 폴더
├─ release-assets/          # 같은 저장소의 Release에 첨부할 ZIP 4개
└─ _build/                  # 로컬 조립·점검 자료; 업로드하지 않음
```

자료를 복원하면 `hmmwv-rag-experiment` 안에 큰 입력 파일도 생깁니다. `.gitignore`가 이 파일들과 가상환경·모델 가중치·캐시를 제외합니다. 보관 대상 원 결과는 제외하지 않습니다. `.gitattributes`는 원 코드·기록의 SHA-256을 유지하기 위해 줄바꿈 자동 변환을 막습니다.

ZIP은 Git 커밋에 넣지 않고 같은 프로젝트의 Release에 첨부합니다. GitHub는 일반 Git의 큰 파일 업로드에 제한을 두며 Release 첨부는 별도 경로입니다. [큰 파일 안내](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github), [Release 안내](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)를 참고하세요.

## 새 배포를 게시하는 순서

1. `LICENSE_STATUS.md`에서 코드의 재사용 허용 범위를 확인합니다. 라이선스를 추가하거나 바꾸는 결정은 별도로 기록하고, 외부 자료에는 해당 자료의 조건을 적용합니다.
2. `scripts/verify_artifacts.py --scope all`로 복원 자료와 공개 사본 변경 목록을 확인합니다. manifest에 지정된 현재 ZIP 4개를 사용합니다. 외부 자료의 라이선스와 출처는 함께 제공하는 LICENSE·SOURCE.md와 THIRD_PARTY_NOTICES.md를 따릅니다.
3. Git에 포함될 파일 목록과 원격 주소를 확인합니다. API 키, `.env`, PC별 로그·자격 증명은 포함하지 않습니다. 개인키·인증파일·HAR·임시 파일의 제외 규칙을 추가했지만, `.gitignore`가 이미 추적 중인 파일을 제거하거나 파일 내용까지 검사하지는 않습니다. `.env.example`에는 예시값만 둡니다. [공개 전 보강 내역](publication-review.md)을 참고하세요.
4. 소스와 문서를 커밋하고 선택한 GitHub 저장소에 push합니다.
5. 같은 커밋의 Release를 만든 뒤 `release-assets`의 ZIP 4개를 첨부합니다.
6. 실제 업로드 URL로 README의 다운로드 안내를 보완합니다. ZIP을 다시 내려받아 manifest의 크기·SHA-256과 대조합니다.
7. 새 clone에서 ZIP 복원과 `--scope all` 검사를 한 번 더 실행합니다.

커밋은 로컬 변경 이력을 기록하는 작업이고, push는 그 커밋을 원격 저장소로 보내는 작업입니다. Release 첨부는 별도의 파일 업로드입니다. 이 저장소의 기본 브랜치는 `main`, 원격 이름은 `origin`입니다. 새 배포를 만들기 전 `git remote -v`로 위 저장소 주소와 일치하는지 확인합니다.

실험을 새로 실행했다면 원본 검증 보고서와 새 결과를 구분하고 `RUN_HISTORY.md`에 실행 목적·원본·변경 항목을 추가합니다. 이전 결과가 잘못되었다는 이유로 삭제해서 변경 경위를 없애지 않습니다.
