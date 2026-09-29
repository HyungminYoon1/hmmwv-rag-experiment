"""Record new findings without rewriting the immutable corrected-v4 source."""
from .common import SourceStore,PACKAGE,ROOT,write_jsonl,write_json,read_json,sha
import pymupdf


def main():
    store=SourceStore();out=PACKAGE/'rules/v2';evidence=PACKAGE/'reports/rules-v2-work/source-findings'
    evidence.mkdir(parents=True,exist_ok=True)
    pdf=pymupdf.open(ROOT/store.config['source_pdf'])
    definitions=[
        (133,'EXTRACTION_ERROR_CONFIRMED','OCR에 서로 다른 진단 박스의 문자와 깨진 문자열이 섞여 있습니다. 예: NOES THE ENGINE cA, STENCE FEST 10. v4 문자 보정 배치의 추가 원문 대조가 필요합니다.','ocr'),
        (517,'SYMBOL_EXTRACTION_REVIEW','변속 레버 위치의 원형 D 기호가 native/OCR 문장에서 온전히 표현되지 않습니다. 자동 철자 치환으로 해결하지 않고 다음 보정 배치에서 원문 기호와 기록 방식을 확인해야 합니다.','native'),
        (287,'LAYOUT_PROFILE_REJECTED','유형 표본 검사에서 왼쪽 KNOWN INFO 박스와 중앙 질문 박스의 수직 위치가 일치하지 않습니다. y좌표 또는 일반 다단 규칙만으로 조건을 질문에 배정하는 규칙을 승인하지 않았습니다.','native'),
        (123,'ADDITIONAL_TABLE_STRUCTURE','SYSTEM LEVEL TESTS / PARAGRAPH / FOLDOUT NUMBER 표가 기존 14쪽 목록에 없었습니다. 줄바꿈된 항목과 빈 FOLDOUT 셀의 행 대응을 추가로 구조화해야 합니다.','native'),
        (124,'ADDITIONAL_TABLE_STRUCTURE','TOP LEVEL TESTS 및 SYSTEM LEVEL TESTS / PAGE 목록을 열별 본문으로 연결하지 않도록 추가 표 정의가 필요합니다.','native'),
        (573,'ADDITIONAL_TABLE_STRUCTURE','18번 절차의 엔진별 공회전 속도 3행이 오른쪽 그림 문자와 함께 추출되어 있습니다. 표의 행·수치와 주변 절차 적용 범위를 분리해야 합니다.','native'),
    ]
    rows=[]
    for pn,code,detail,layer in definitions:
        png=evidence/f'page-{pn:04d}.png'
        pdf[pn-1].get_pixmap(dpi=130,alpha=False).save(png)
        rows.append({'pdf_page':pn,'code':code,'detail':detail,
                     'source_refs':[store.ref(f'P{pn:04d}:{layer}')],
                     'evidence':{'file':png.relative_to(ROOT).as_posix(),'sha256':sha(png)},
                     'status':'NEEDS_REVIEW','source_text_modified':False})
    write_jsonl(out/'new-review-items.jsonl',rows)
    write_json(out/'layout-profile-review.json',{
        'profile':'native_three_column_flowchart','status':'REJECTED_AFTER_SAMPLE',
        'selection_seed':'HMMWV-corpus-rules-v2','rule_development_pages':[197],
        'sample_pages':[165,583,336,287,328],
        'failure_page':287,'failure':'Left conditions and centre questions do not share vertical starts.',
        'action':'Keep structure review for this family. Do not mark a source block as a verified diagnostic node.',
        'evidence':[{'file':(PACKAGE/f'reports/rules-v2-work/native-flow-sample-{i}.png').relative_to(ROOT).as_posix(),
                     'sha256':sha(PACKAGE/f'reports/rules-v2-work/native-flow-sample-{i}.png')} for i in (1,2)]})
    print(len(rows),'new findings; original records unchanged')


if __name__=='__main__':main()
