# 자료와 모델 출처

## 교범 PDF

| 항목 | 값 |
| --- | --- |
| 문서 | TM 9-2320-280-20-1, Unit Maintenance, HMMWV, Volume 1 |
| 판본 | 1996년 본문, Change 2: 2004-07-15 |
| PDF 쪽수 | 890 |
| 파일 크기 | 15,401,616 bytes |
| SHA-256 | `4606773be7d6914f23fa9f9d51dcdb1f4b054dea99db9cd4109fb5d412a21c7d` |
| 파일명 | `TM_9-2320-280-20-1_1996_Change2_2004_TFS_archive.pdf` |
| 배포 묶음 | runtime-data |

이 파일은 Texas A&M Forest Service가 공개했던 PDF의 Internet Archive 보존본입니다. 원 수집 시점에는 기존 기관 주소가 404였으므로 보존본을 사용했습니다. ‘현재 최신 교범을 기관 서버에서 직접 내려받았다’고 표현하지 않습니다. 파일 마지막의 보존 사이트 안내도 삭제하지 않았으며 검색 범위에는 포함하지 않습니다.

- [기존 Texas A&M Forest Service 주소](https://tfsweb.tamu.edu/uploadedFiles/FRP/New_-_Local_Capacity_Building/TM-9-2320-280-20-1%20Maintenance%20Manual%20M998%20Series%20HMMWV%20Vol%201.pdf)
- [실제 수집에 사용한 2024-06-07 보존본](https://web.archive.org/web/20240607092013id_/https://tfsweb.tamu.edu/uploadedFiles/FRP/New_-_Local_Capacity_Building/TM-9-2320-280-20-1%20Maintenance%20Manual%20M998%20Series%20HMMWV%20Vol%201.pdf)
- [수집 당시의 판본·출처 확인 기록](../자료/미군교범/출처_및_판본_확인.md)

## 추출·보정·청킹 자료

PDF가 대조 기준입니다. 파서 출력이나 AI 보정본을 PDF와 독립된 원문으로 취급하지 않습니다. 고정 OCR 결과, 보정 전후 텍스트, 변경 기록과 구조 처리 규칙을 함께 보관했습니다.

전처리 ZIP은 최종 설정의 입력 잠금 파일과 연결된 이전 판본·검토 자료를 포함합니다. 파일명이 오래되었거나 `backup`이라는 이유만으로 제외하지 않았습니다. 최종 검증이 참조하는 백업도 재연 입력입니다. 사람이 읽는 근거 캡처와 추가 검토 자료는 review-evidence ZIP에 분리했습니다.

`artifacts/manifest.json`에는 모든 복원 파일의 상대 경로·크기·SHA-256이 있습니다. `artifacts/original-files.json`은 Git으로 전달할 코드와 기존 결과 기록의 복사 기준입니다. 해시 일치는 보관된 파일과 같다는 뜻이며, 텍스트의 의미상 정확성을 독립적으로 입증하지는 않습니다.

고정 질의의 원본 확인을 위해 `부록A_평가질의 목록_윤형민_v0.2.hwpx`를 기존 위치와 `retrieval/benchmarks/holdout-v1/`의 보존 위치에 포함했습니다. 검색 검증기는 공개 사본의 해시를 확인합니다. 원본과 공개 사본의 차이는 `artifacts/publication-changes.json`에 기록했습니다.

## 모델

| 용도 | 출처 | 고정 revision |
| --- | --- | --- |
| 검색 | [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) | `5617a9f61b028005a4858fdac845db406aefb181` |
| 생성 GGUF | [bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF](https://huggingface.co/bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF) | `ae44f08e1392f39c0e474af10c3ff8355c8b6688` |

생성 파일은 `Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf`, 2,497,280,736 bytes입니다. SHA-256은 `2fde00ce69dd4899c70d020845e2638353015bba0fdf161b3eb965f2bca4464e`입니다.

가중치는 Git과 자료 ZIP에 포함하지 않습니다. 고정 다운로드 도구가 배포자의 revision 경로에서 내려받고 잠금 파일의 해시와 비교합니다. Qwen GGUF는 원 모델 개발사 자체 배포 파일과 구별합니다. 토크나이저 등 재연에 쓰인 부속 파일의 출처·해시는 각각의 잠금 파일에 보존했습니다.

답변 자동평가 모델은 설정과 원 응답에 기록된 GPT-6 Sol입니다. 이 모델의 가중치는 배포하지 않습니다. API 제공 상태가 바뀌면 저장된 원 평가 결과는 확인할 수 있지만 동일 서비스로 새 평가를 실행하지 못할 수 있습니다.

## 외부 라이선스

교범·모델·토크나이저·Python 의존성의 조건은 각 자료에 따릅니다. 프로젝트 코드에 라이선스를 정하더라도 외부 자료에 일괄 적용하지 않습니다. [외부 자료 안내](../THIRD_PARTY_NOTICES.md)를 함께 확인하세요.
