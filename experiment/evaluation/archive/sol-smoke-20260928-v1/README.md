# 기능 점검 중 남은 임시 저장 사본

`interrupted-save.json`은 sol-smoke-20260928-v1의 synthetic-correct / answer-kind 단계에서 남은 임시 저장 파일을 내용 변경 없이 보존한 것입니다. 같은 위치의 정식 `attempt-1.json`과 바이트가 달라 삭제하지 않았습니다.

원래 파일명과 이동 전후 SHA-256은 `artifacts/publication-changes.json`의 `archive_interrupted_save` 항목에 있습니다. 이 파일은 정식 60문항 실험이나 현재 결과표의 집계 입력이 아닙니다. 파일명과 위치를 정리한 것이며 새로운 API 호출이나 평가 결과를 만든 것은 아닙니다.
