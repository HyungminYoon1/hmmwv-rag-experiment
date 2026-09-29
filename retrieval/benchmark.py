"""Keep the user's 60 final-evaluation questions outside development search."""
from __future__ import annotations

from collections import Counter
import csv
import re
import shutil
import unicodedata
from .common import ROOT, load_config, local_path, read_json, sha, text_sha, write_json, write_jsonl, check_files


def normalized_question(text):
    return ' '.join(re.findall(r'\w+', unicodedata.normalize('NFKC', text).casefold()))


class Holdout:
    def __init__(self, path):
        self.path = path
        self.manifest = read_json(path / 'manifest.json')
        check_files(path, self.manifest['files'])
        self.hashes = read_json(path / 'question-hashes.json')

    def matching_id(self, question):
        return self.hashes.get(text_sha(normalized_question(question)))

    def require_development(self, question):
        if self.matching_id(question):
            raise ValueError('이 질문은 최종 평가용 60문항에 포함돼 있습니다. 개발용 검색에서는 실행하지 않습니다.')


def freeze():
    config = load_config()
    out = local_path(config['holdout'])
    if out.exists():
        Holdout(out)
        print('Existing question snapshot verified; unchanged.')
        return
    base = ROOT / '제출 논문 초안'
    source_names = ['부록A_평가질의_v0.2_2026-09-21_채점기준.json',
                    '부록A_평가질의_v0.2_2026-09-21_질의.csv',
                    '부록A_평가질의 목록_윤형민_v0.2.hwpx',
                    '부록A_평가질의_v0.2_2026-09-21_근거와_채점기준.md']
    data = read_json(base / source_names[0])
    questions = data['questions']
    with (base / source_names[1]).open(encoding='utf-8-sig', newline='') as stream:
        csv_rows = list(csv.DictReader(stream))
    public_rows = [{k: q[k] for k in ('id', 'type', 'question')} for q in questions]
    if public_rows != csv_rows:
        raise ValueError('The CSV and grading JSON contain different question sets')
    hashes = {text_sha(normalized_question(q['question'])): q['id'] for q in questions}
    counts = dict(Counter(q['type'] for q in questions))
    if len(questions) != 60 or len(hashes) != 60 or len({q['id'] for q in questions}) != 60:
        raise ValueError('The benchmark must contain 60 unique questions and IDs')
    if counts != {'single-evidence': 20, 'multi-evidence': 30, 'unanswerable': 10}:
        raise ValueError('Unexpected question-type counts')
    out.mkdir(parents=True)
    for name in source_names:
        shutil.copy2(base / name, out / name)
    write_jsonl(out / 'questions.jsonl', public_rows)
    write_json(out / 'question-hashes.json', hashes)
    write_json(out / 'manifest.json', {
        'schema': 1, 'date': '2026-09-28', 'question_count': 60, 'types': counts,
        'question_set_status': 'PROVISIONALLY_FIXED_BY_USER_FOR_FINAL_EVALUATION',
        'change_policy': 'Only supervisor guidance or a serious question defect; preserve and version any change.',
        'ground_truth_status': 'PENDING_SOURCE_AND_CHUNK_VALIDATION',
        'retrieval_evaluation': 'NOT_RUN',
        'development_use': False,
        'guard_scope': 'Exact match after Unicode, case, punctuation and whitespace normalization; no semantic paraphrase detection.',
        'original_files': {str((base / n).relative_to(ROOT)).replace('\\', '/'): sha(base / n) for n in source_names},
        'files': {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}})
    Holdout(out)
    print('60 evaluation questions preserved; JSON/CSV identity and uniqueness passed.')


if __name__ == '__main__':
    freeze()
