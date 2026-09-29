"""Exercise the running local app with separate development questions."""
from __future__ import annotations

from datetime import datetime, timezone
import io
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .common import PACKAGE, ROOT, load_config, read_jsonl, write_json


def main():
    base = 'http://127.0.0.1:8766'

    def get(route):
        with urlopen(base + route, timeout=30) as response:
            return json.load(response)

    def search(question):
        request = Request(base + '/api/search', json.dumps({'question': question}).encode(),
                          {'Content-Type': 'application/json', 'X-Retrieval-Request': '1'}, method='POST')
        with urlopen(request, timeout=120) as response:
            return json.load(response)

    status = get('/api/status')
    if not status['ready']:
        raise ValueError('Search app is not ready')
    questions = [
        'How are maintenance forms and records used for this vehicle?',
        'Which warnings concern exposure to battery electrolyte?',
        '이 교범은 어떤 차량 모델을 다루나요?',
    ]
    cases = []
    first_result = None
    for question in questions:
        first, second = search(question), search(question)
        signature = lambda result: [(row['id'], row['score'], row['text_sha256']) for row in result['items']]
        if len(first['items']) != 5 or signature(first) != signature(second):
            raise ValueError('Repeated development searches differ')
        if first['generated_answer'] is not None or first['purpose'] != 'DEVELOPMENT_ONLY':
            raise ValueError('Unexpected search result purpose')
        if get('/api/record?id=' + first['id']) != first:
            raise ValueError('Saved record differs from returned result')
        cases.append({'question': question, 'record_ids': [first['id'], second['id']],
                      'ranks_and_scores_identical': True, 'result_count': 5})
        if first_result is None:
            first_result = first

    chunk = first_result['items'][0]
    source = get('/api/chunk?id=' + chunk['id'])
    if source['chunk']['text_sha256'] != chunk['text_sha256']:
        raise ValueError('PDF source is associated with another chunk')
    route = '/api/page.png?id=' + chunk['id'] + '&page=' + str(chunk['pdf_pages'][0])
    with urlopen(base + route, timeout=30) as response:
        content_type, png = response.headers.get_content_type(), response.read()
    from PIL import Image
    with Image.open(io.BytesIO(png)) as preview:
        dimensions = preview.size
        preview.verify()
    if content_type != 'image/png' or min(dimensions) < 100:
        raise ValueError('PDF source image is invalid')
    (PACKAGE / 'reports/source-preview.png').write_bytes(png)

    # Check rejection only: this request must never reach embedding or search.
    questions_path = ROOT / load_config()['holdout'] / 'questions.jsonl'
    reserved = read_jsonl(questions_path)[0]
    history = get('/api/history')['items']
    if history != sorted(history, key=lambda row: (row['created_at'], row['id']), reverse=True):
        raise ValueError('Search history is not in reverse chronological order')
    before = [row['id'] for row in history]
    try:
        search(reserved['question'])
    except HTTPError as exc:
        message = json.load(exc)['error']
        if exc.code != 400 or '최종 평가용 60문항' not in message:
            raise ValueError('Unexpected final-question rejection') from exc
    else:
        raise ValueError('Final evaluation question reached development search')
    if before != [row['id'] for row in get('/api/history')['items']]:
        raise ValueError('Rejected evaluation request created a search record')
    report = {
        'status': 'PASS', 'checked_at': datetime.now(timezone.utc).isoformat(),
        'index_manifest_sha256': status['index_manifest_sha256'],
        'development_queries': len(questions), 'development_searches': 2 * len(questions),
        'cases': cases, 'record_round_trip': 'PASS', 'history_order': 'PASS', 'pdf_source_preview': 'PASS',
        'source_chunk_id': chunk['id'], 'source_pdf_page': chunk['pdf_pages'][0],
        'source_image_size': dimensions, 'reserved_question_rejected_before_search': True,
        'evaluation_queries_executed': 0, 'relevance_evaluation': 'NOT_RUN',
    }
    write_json(PACKAGE / 'reports/http-smoke.json', report)
    print({key: report[key] for key in ('status', 'development_searches', 'pdf_source_preview',
                                      'evaluation_queries_executed')})


if __name__ == '__main__':
    main()
