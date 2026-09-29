"""Immutable first-round inputs; no writing to generation, gold, or corpus."""
import platform
from collections import Counter
from importlib.metadata import version
from .common import BASE, EXPERIMENT, ROOT, EvaluationError, read, sha, fingerprint, valid_id


def source_packet(run_id):
    directory=EXPERIMENT/'runs'/valid_id(run_id)
    packet=directory/'evaluation-inputs'
    manifest=read(packet/'manifest.json')
    tracked={}
    def check(path, expected=None):
        actual=sha(path)
        if expected is not None and actual!=expected:
            raise EvaluationError('SOURCE_HASH_MISMATCH')
        tracked[path.relative_to(ROOT).as_posix()]=actual
    check(packet/'manifest.json')
    for name,expected in manifest['files'].items():
        if name!='answers.jsonl':raise EvaluationError('UNEXPECTED_PACKET_FILE')
        check(packet/name,expected)
    check(EXPERIMENT/'evaluation-policy.json',manifest['evaluation_policy_sha256'])
    gold=EXPERIMENT/'gold-v1'
    check(gold/'manifest.json',manifest['gold_manifest_sha256'])
    for name,expected in read(gold/'manifest.json')['files'].items():
        path=(gold/name).resolve()
        if not path.is_relative_to(gold.resolve()):raise EvaluationError('INVALID_GOLD_PATH')
        check(path,expected)
    import json
    rows=[json.loads(s) for s in (packet/'answers.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
    if manifest['source_round']!=1 or len(rows)!=120 or manifest['answers']!=120:
        raise EvaluationError('EXPECTED_FIRST_ROUND_120_ANSWERS')
    counts=Counter((r['question_id'],r['condition']) for r in rows)
    if len(counts)!=120 or set(counts.values())!={1} or len({r['question_id'] for r in rows})!=60:
        raise EvaluationError('INVALID_QUESTION_PAIRS')
    for r in rows:
        if r['condition'] not in ('LLM_ONLY','RAG') or r['type'] not in ('single-evidence','multi-evidence','unanswerable'):
            raise EvaluationError('INVALID_CONDITION_OR_TYPE')
        if (r['question_id'],'LLM_ONLY') not in counts or (r['question_id'],'RAG') not in counts:
            raise EvaluationError('UNPAIRED_QUESTION')
        expected=f"r1-{r['question_id']}-{'rag' if r['condition']=='RAG' else 'llm_only'}"
        if r['attempt_key']!=expected:raise EvaluationError('INVALID_ATTEMPT_KEY')
        check(directory/'attempts'/(expected+'.json'),r['attempt_file_sha256'])
        if len(r['retrieved_contexts'])!=len(r['retrieved_chunk_ids']) or len(set(r['retrieved_chunk_ids']))!=len(r['retrieved_chunk_ids']):
            raise EvaluationError('CONTEXT_IDS_MISMATCH')
        if r['condition']=='LLM_ONLY' and r['retrieved_contexts']:
            raise EvaluationError('CONTEXT_LEAK_IN_LLM_ONLY')
        if r['type']!='unanswerable' and (not r['oracle_evidence'] or not r['required_elements']):
            raise EvaluationError('ANSWERABLE_GOLD_MISSING')
    if Counter(r['type'] for r in rows)!=Counter({'single-evidence':40,'multi-evidence':60,'unanswerable':20}):
        raise EvaluationError('QUESTION_TYPE_COUNTS_CHANGED')
    return rows,read(EXPERIMENT/'evaluation-policy.json'),tracked


def code_identity():
    paths=list(BASE.glob('*.py'))+[BASE/'requirements.lock.txt',ROOT/'retrieval/config.json',ROOT/'retrieval/model.py']
    files={p.relative_to(ROOT).as_posix():sha(p) for p in paths}
    return {'files':files,'sha256':fingerprint(files)}


def environment():
    return {'python':platform.python_version(),'platform':platform.platform(),
            'packages':{p:version(p) for p in ('ragas','openai','pydantic','numpy','instructor','langchain-community','httpx')}}
