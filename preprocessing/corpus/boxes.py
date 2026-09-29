"""Apply locked source-region and context contracts before generic selection."""
from .common import source_parts

DETAILS={
 'BOX_CONTEXT_REVIEW':'질문·조건·시험 박스를 native 좌표로 분리했습니다. 이 페이지의 개별 원문·맞은편 참고 설명 대조가 남습니다.',
 'CONDITION_ASSOCIATION_UNRESOLVED':'질문·시험 박스는 보존했지만 왼쪽 조건의 적용 대상을 확정하지 못해 별도 단위로 유지했습니다.',
 'FLOW_ANNOTATION_REVIEW':'흐름도 보조 문자를 보존했습니다. 화살표 경로의 의미는 본문으로 바꾸지 않았습니다.'}


def reviewed_boxes(store,units):
    for row in store.table('box-units.jsonl'):
        body=[store.exact(r) for r in row['body_refs']]
        context=[store.exact(r) for r in row['context_refs']]
        reviews=[store.review(code,body[0]['pdf_page'],DETAILS[code],body[:1],row['key']) for code in row['review_codes']]
        units.add(row['key'],row['kind'],source_parts(body,join=row.get('body_separator','\n')),source_parts(context,'condition',join=row.get('context_separator','\n')),reviews,
                  {**row['metadata'],'layout_review':row['review'],'evidence':row['evidence']})
    for row in store.table('box-dispositions.jsonl'):
        store.decide(store.exact(row['source']),row['status'],row['reason'],[row['rule']])
