"""Record PDF layout observations separately from reproducible measurements."""
from collections import Counter
from pathlib import Path
from corpus.common import BASE, ROOT, SourceStore, read_json, read_jsonl, write_json, write_jsonl, sha

DEST=BASE/'ocr-structure-review-20260924'
NOTES={
33:'차량 그림 두 개와 각각의 모델 캡션. 그림 이름과 일반 본문을 구별한다.',
60:'회전한 16개 모델 헤더와 공통 열 구조. 셀/행은 기존 수동 표 정의를 우선한다.',
95:'PMCS 도입 본문과 NOTE. 테두리 없는 본문이며 질문 박스가 아니다.',
100:'PMCS 항목 7의 WARNING/CAUTION 및 절차. 같은 표 안 경고의 적용 항목을 유지한다.',
105:'PMCS 항목 11/12와 그림이 있으며 모든 논리 행에 가로선이 있는 것은 아니다.',
113:'PMCS 항목 19의 계속 부분과 항목 20 및 NOTE를 구별한다.',
118:'한 큰 열 테두리에 항목 31/32가 들어간다. 사각형 하나를 의미 단위 하나로 취급하면 안 된다.',
125:'교범 사용법 예시 그림이다. 실제 고장 진단 단계로 분류하지 않는다.',
130:'용어 설명과 전기회로 설명의 두 절. 본문 제목으로 경계를 잡는다.',
134:'왼쪽 참고 설명과 오른쪽 RPM 시험 카드. 카드 제목/단계와 참고 대상이 필요하다.',
138:'첫 시작 안내에는 왼쪽 조건 박스가 없다. 순번으로 조건을 붙이지 않는다.',
219:'세 질문과 경고 표시, 맞은편 설명 참조가 있다. 경고를 페이지 전체에 일괄 적용하지 않는다.',
344:'한 개의 교체 조치 박스와 선행 참조. 일반 세 열 질문 양식과 다르다.',
347:'세 질문과 조건 박스가 있는 흐름도. 질문 3의 23.5–25.5 VOLTS 수치를 보호한다.',
393:'오른쪽 시험 카드 네 개, 왼쪽 조치 설명 및 핀 그림. 각각의 카드 경계를 보존한다.',
408:'PIN-TO-PIN / RESISTANCE 표 네 행과 NOTE의 solid-state controller 예외가 있다. 현재 단위에서는 표 수치가 깨지고 NOTE 문장도 분리되어 있다.',
474:'FULL/HALF/EMPTY와 35/16/0 OHMS 표, 회로도, 두 시험 카드가 있다. 현재 OCR 단위에는 도면 문자와 카드 문장이 혼합되어 있다.',
502:'SUMMARY OF CONNECTIONS는 TERMINAL/CONNECTION/WIRE NUMBER 8행 표다. F행 325B가 현재 3258로 추출되어 있다. CAUTION은 continuity measurement에 적용된다.',
534:'자유 배치 분기 흐름도. 세 열 질문 양식에 맞지 않는다.',
542:'HIGH/LOW RESISTANCE가 서로 다른 질문/조치를 가진다.',
543:'HIGH/LOW RESISTANCE가 분리된 흐름도이며 선과 YES/NO 표식을 따라야 한다.',
544:'HIGH/LOW RESISTANCE가 별개인데 현재 단위는 조치/분기 표식 일부를 함께 묶는다.',
547:'RESISTANCE TOO LOW와 TOO HIGH의 질문/수리 조치가 별개다. 현재 같은 단위에 다른 분기의 조치가 결합되어 있다.',
565:'참고 설명 한 문단만 있다. 닫힌 박스가 없다는 이유로 추출 실패라고 할 수 없다.',
575:'B6/B7/B8의 YES/NO 조합 여덟 행과 조치 열 및 NOTE. 현재 native/OCR 텍스트에 대부분의 조건 조합이 아예 없어서 문자 보존 검사로는 누락을 잡을 수 없다.',
576:'질문 C3의 CAUTION 표식은 맞은편 577쪽 설명을 가리킨다. 다른 질문에 일괄 연결하지 않는다.',
612:'AMBULANCE(All Dome Lamps)와 문 닫힘 상태가 제목 조건이다. 질문 19의 앞부분이 현재 단위에서 빠지고 TB TERMINAL 2?가 TB TERMINAL 27로 남는다.',
670:'M997 ONLY 모델 조건과 질문 10/11. NO를 항상 같은 종류의 수리 조치로 해석하면 안 된다.',
689:'시험 카드 옆 회로도가 있다. 재OCR의 문자 불일치는 도면 주변 혼합 줄에서 발생했다. 그림 선을 자연어 정비 관계로 해석하지 않는다.',
735:'참고 설명과 회로도. 도면 라벨을 일반 본문과 구별한다.',
779:'시험 카드와 복잡한 배선도. 잡음 OCR 줄은 그림 주변에 있으며 임의 재작성하지 않는다.',
787:'회로도 페이지. 독립된 정상 절차 본문으로 취급할 수 없는 그림 라벨이다.',
789:'배선 연결 그림과 라벨. 그림 관계는 이번 텍스트 구조 검토로 복원하지 않았다.',
810:'세 번째 NO가 대각선으로 나가며 최종 YES 조치와 구별된다. 인쇄면수 3-710은 원문 그대로 보존한다.',
812:'첫 조건의 M997 ONLY와 후속 질문의 알려진 상태를 구별한다.',
822:'NOTE 참조와 불완전하게 검출되는 오른쪽 테두리. 닫힌 사각형 검출만으로 모든 설명을 찾지 못한다.',
828:'B1/B2/B3 각각의 맞은편 참고 설명은 829쪽의 별도 문단이다.',
829:'세 참고 문단의 가로 폭이 고정 열 경계를 넘는다. 현재 중간 문장이 다른 단위에 모여 문장이 끊어진다.',
830:'테두리 없는 시험명/번호/쪽 목록 표. 닫힌 사각형 0개라도 표다.',
848:'테두리 없는 6영역 시험 설명. Description/Pre-Test/Applications/Control Functions/Test Procedure/Error Messages로 나눠야 한다.',
854:'표시창 예시 E001/C004와 표 형태의 상태 설명은 서로 다른 구조다.',
856:'케이블 설명과 27행 부품표. 기존 표 복원 규칙을 기하 사각형으로 대체하지 않는다.',
860:'GO-chain 절차, 경고, 표시창, YES/NO 분기가 섞인 양식. 일반 질문 박스와 구별한다.',
863:'GO-chain의 마지막 절차 쪽. 자동 분류의 일반 본문/그림 후보만으로는 충분하지 않다.'}

FINDINGS=[
 ('F01',612,['region:612:1:1','region:612:1:15','region:612:1:26'],
  '질문·적용 조건 분리와 식별자 오독',
  '질문 19: IS THERE BATTERY VOLTAGE IN CONTROL BOX AT: TB TERMINAL 1? TB TERMINAL 2?',
  '질문 앞부분이 빠진 단위에 TB TERMINAL 1?/TB TERMINAL 27 및 수리 조치가 남아 있다. 페이지 적용 조건도 별도 단위다.',
  '실제 질문 박스 단위 복원, 제목 적용 조건 연결, 2?를 27로 읽은 문자 오류의 별도 보정'),
 ('F02',547,['region:547:1:2','region:547:1:10'],
  '상반된 저항 조건의 조치 결합',
  'RESISTANCE TOO LOW / RESISTANCE TOO HIGH는 상하 별도 흐름도다.',
  '다른 분기의 wire 923A/359A 수리 조치들이 같은 일반 본문에 모이고 선행 질문이 떨어졌다.',
  '자유 배치 흐름도용 노드/분기 정의와 조건별 구조 단위 작성'),
 ('F03',829,['region:829:1:1','region:829:1:2'],
  '고정 열 경계가 참고 문장을 절단',
  '첫 참고 문단의 came from and rerun the original DCA test...는 앞 문장에 이어진다.',
  '첫 문단과 두 번째 문단의 오른쪽 끝이 별도 단위에 함께 모였다. 세 질문의 참고 설명도 첫 단위에 합쳐졌다.',
  'PDF의 참고 문단 범위와 828쪽 B1/B2/B3 관계를 별도 정의'),
 ('F04',575,['region:575:1:1','region:575:1:2'],
  '정비 판단표의 조건 조합 추출 누락',
  'B6/B7/B8별 YES/NO 8개 조합, 조치 열, 두 번째/세 번째 조합에 관한 NOTE가 있다.',
  '조건 조합 대부분이 보정 전후 텍스트에 없다. 결과 조치만 본문으로 들어가며 검색 문맥에서 판단 근거를 잃는다.',
  '원본 PDF의 표 8행을 재추출/전사하고 조건 3열+조치+NOTE로 구조화'),
 ('F05',408,['region:408:1:1','region:408:1:2','region:408:1:3'],
  '저항 표 수치 오독과 적용 예외 문장 분리',
  'PIN-TO-PIN / RESISTANCE 표와 solid-state controller에는 pin-to-pin 저항 검사를 사용할 수 없다는 NOTE.',
  '예: 0.40 Ω TO 0.75 Ω가 0.40 2 TO 0.75 Q로, 27 Ω ± 3 Ω가 272432로 남는다. NOTE의 끝 case.가 다른 단위로 분리됐다.',
  '표 셀 재추출/문자 보정, NOTE를 완전한 문단으로 복원하고 적용 범위 고정'),
 ('F06',474,['region:474:1:1','region:474:1:2','region:474:1:3'],
  '회로도 라벨과 시험 절차 혼합',
  '왼쪽 회로도, 오른쪽 STE/ICE-R/멀티미터 카드, 아래 GAUGE READING/OHMS 표는 별도 영역.',
  'The connector...와 2. Start Test...가 한 줄로 결합되고 FUEL/GAUGE/58H 등의 그림 라벨이 시험 단계와 합쳐졌다.',
  '줄 분할의 x좌표 후보가 아닌 실제 카드 경계와 단어 좌표로 분리; 그림 라벨 별도 보존'),
 ('F07',502,['region:502:1:1'],
  '연결 표 배선번호 오독',
  'SUMMARY OF CONNECTIONS의 F행 WIRE NUMBER는 325B다.',
  '현재 본문에는 3258로 남아 있다. 표를 일반 본문으로만 묶고 그림의 단자 라벨도 같이 들어가 있다.',
  '325B 문자 보정과 8행 표 구조 정의; 도면 라벨/주의문 범위 분리')]


def main():
    sample=read_json(DEST/'independent-visual-sample.json')
    pilot=set(sample['excluded_pilot_pages'])
    sampled={p for pages in sample['family_samples'].values() for p in pages}
    exception={670,689,779,848,860}
    assert set(NOTES)==pilot|sampled|exception|{408,474,502,575}
    pages=[]
    for pn,note in sorted(NOTES.items()):
        # Pilot observations used its rendering; all subsequent detail views used A.
        folder='profile-pilot' if pn in pilot else 'full-audit-a'
        img=DEST/folder/f'page-{pn:04d}-geometry.png'
        assert img.is_file(),img
        pages.append({'pdf_page':pn,'reviewer':'Codex','scope':'LAYOUT_AND_SELECTED_TEXT_NOT_FULL_PROOFREADING',
          'selection':'pilot' if pn in pilot else 'independent_sample' if pn in sampled else 'rerun_exception' if pn in exception else 'overview_followup',
          'image':img.relative_to(ROOT).as_posix(),'image_sha256':sha(img),'finding':note})
    write_json(DEST/'visual-review.json',{'reviewer':'Codex','detail_pages':len(pages),'all_characters_verified':False,'pages':pages})
    units={u['key']:u for u in read_jsonl(BASE/'output/corpus-v4-rules-c/corpus_units.jsonl')}
    s=SourceStore();findings=[]
    for ident,pn,keys,title,source,observed,action in FINDINGS:
        selected=[units[k] for k in keys]
        findings.append({'id':ident,'pdf_page':pn,'title':title,'status':'CONFIRMED_SOURCE_AND_CORPUS_DISCREPANCY',
          'source_observation':source,'observed_current_corpus':observed,'next_action':action,
          'units':[{'key':u['key'],'kind':u['kind'],'prefix_text':u['prefix_text'],'body_text':u['body_text'],
                    'body_parts':u['body_parts']} for u in selected],
          'corrected_ocr_text':s.records[f'P{pn:04d}:ocr']['text'],'changed_this_task':False})
    write_json(DEST/'confirmed-findings.json',{'scope':'Confirmed cases, not an exhaustive count of all errors','findings':findings})
    overview=read_json(DEST/'layout-overview/manifest.json')
    mapping={pn:sh for sh in overview['sheets'] for pn in sh['pages']}
    detailed={r['pdf_page']:r for r in pages}
    rows=read_jsonl(DEST/'page-results.jsonl')
    for r in rows:
        pn=r['pdf_page'];r['visual_review']='DETAILED_LAYOUT_AND_SELECTED_TEXT' if pn in detailed else 'CONTACT_SHEET_LAYOUT_OVERVIEW_ONLY'
        r['overview_sheet']='layout-overview/'+mapping[pn]['file']
        r['overview_image_sha256']=mapping[pn]['sha256']
        r['detail_review_record']='visual-review.json' if pn in detailed else None
        r['confirmed_finding_ids']=[f['id'] for f in findings if f['pdf_page']==pn]
    write_jsonl(DEST/'page-review-results.jsonl',rows)
    lines=['# OCR 페이지별 구조 검토','',
      '실험 범위 PDF 31–863쪽 중 OCR 레코드가 있는 671쪽이다. 모든 쪽은 프로그램 검사와 32 dpi 축소 배치 확인을 거쳤다. 상세 44쪽은 확대 이미지에서 구조와 지정 문구를 대조했으며 모든 글자·분기를 검수했다는 뜻은 아니다.',
      '', '자동 유형은 후보 분류다. 검토 표식·보류 문자 0은 PDF 누락 0이라는 뜻이 아니다(575쪽 사례). 쪽번호는 PDF 순번이다.', '',
      '| PDF 쪽 | 자동 유형 후보 | 화면 확인 | OCR 보류 문자 | 기존 검토 표식 | 확인된 사례 | 근거 |',
      '| ---: | --- | --- | ---: | ---: | --- | --- |']
    for r in rows:
        pn=r['pdf_page'];kind='확대' if pn in detailed else '축소 배치'
        lines.append(f"| {pn} | {r['family_candidate']} | {kind} | {r['selection_characters'].get('NEEDS_REVIEW',0):,} | {sum(r['existing_review_counts'].values())} | {', '.join(r['confirmed_finding_ids'])} | [배치]({r['overview_sheet']}) · [확대 이미지](full-audit-e/page-{pn:04d}-geometry.png) · [좌표](full-audit-e/page-{pn:04d}.json) |")
    (DEST/'페이지별_검토결과.md').write_bytes(('\r\n'.join(lines)+'\r\n').encode('utf-8'))
    print({'overview_pages':len(mapping),'detail_pages':len(pages),'confirmed_case_groups':len(findings),'page_results':len(rows)})


if __name__=='__main__':main()
