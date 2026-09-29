"""Versioned, source-bound corrections. Never overwrite gold-v1 or generation."""
import copy
import json
import re
from pathlib import Path
from .evaluation.common import ROOT, EXPERIMENT, read, save, sha, utc, write_text
from .gold import minimum_chunks, retrieval_score

REV = EXPERIMENT / 'revisions/20260929-v2'
GOLD = EXPERIMENT / 'gold-v2'
OLD_REVIEW = EXPERIMENT / 'astra-review/20260929-v1'
PDF = ROOT / '제출 논문 초안/논문참고자료/TM_9-2320-280-20-1_1996_Change2_2004_TFS_archive.pdf'

POLICY_ADDITIONS = {
    'version': 'post-review-v2-20260929',
    'revision_timing': 'AFTER_GENERATION_AND_INITIAL_EVALUATION',
    'claims': 'Extract substantive technical factual claims only, once from question and answer. Carry shared operating conditions explicitly stated in the question or answer into every applicable claim. Preserve negation, units, subject, constraints and procedure order. Deduplicate semantically equivalent claims. Never add a technical answer from the question or fix the answer. Reuse the SAME claims for oracle and actual-context support.',
    'excluded_claims': 'Record input-presence statements, self-described knowledge provenance, citation/chunk-ID availability and non-factual inability separately; do not include them in technical fact denominators. A claim about the manual as a whole lacking a TECHNICAL fact is substantive; an inability to find it in the supplied excerpts is input-scope metadata. Technical speculation still counts as a claim; retain its uncertainty.',
    'required_coverage': 'Score each declared element 0/1. All independent clauses joined by AND are necessary; a named list of several symptoms requires every listed symptom. OR in the medical/technical symptom wording means list the alternatives, not that any single listed symptom suffices, unless the rubric explicitly says acceptable alternatives. Equivalent units and source-printed conversions are accepted. A concrete correct proposition expressed cautiously (likely, probably, I cannot confirm but...) may fulfill a CONTENT element; a pure refusal or vague category does not. Do not require optional explanatory details. Contradictions within the answer invalidate that element. Conditions explicit in the question are shared.',
    'source_location': 'Assess factual support, not retrieval of an identical section title. Do not append a location only named in the question as a new factual claim. Equivalent evidence for the same object and operating condition is allowed. Preserve an explicit chart-specific value when the rubric states other sections have different values. Do not transfer a threshold to a different model or subsystem.',
    'support_reasoning': 'Several supplied evidence passages may jointly support a claim through explicit inclusion rules or stated comparisons. No outside technical knowledge. Keep uncertainty and question-wide conditions; do not judge a conditional statement as unconditional. Unsupported by a bounded oracle is not proven false.',
    'unanswerable': 'Withhold the frozen missing COMPLETE procedure. A disclaimer followed by invented missing steps is a failure. Any related substantive technical assertion is a partial answer, including inspections, model applicability, thresholds and safety warnings. Do not skip partial-source checks because the assertion is not a usable step of the requested full procedure. Judge partial facts against the frozen oracle and actual retrieved context separately. Preserve all model/operation constraints; another component procedure is not the requested procedure.',
    'manual_review': 'Original selected 40 answers retained. Astra supplemental AI review completed; researcher and expert review are not performed. Post-review corrections are not a new independent blind validation.',
    'automatic_quality_status': 'PREPARED_FOR_REVISED_EVALUATION',
    'ragas_version': '0.4.3',
    'judge_model': 'gpt-6-sol',
}

SUPPLEMENTS = {
    'M15': ['C001112', 'C001114', 'C001115'],
    'U01': ['C003280', 'C003282'],
    'U05': ['C001020', 'C002990', 'C003672', 'C003675', 'C003676', 'C003677'],
    'U07': ['C003620'],
    'U08': ['C000597', 'C000907'],
    'U09': ['C001421', 'C002414'],
    'U10': ['C000004', 'C000902', 'C005743'],
}

NOTES = {
    'S02': 'A01 requires both runs poorly and does not remain running. A02 requires all three listed starting symptoms. A clear subordinate example of runs poorly may support that symptom but does not replace the other symptoms.',
    'S14': 'Same 6.2 L idle-speed value in other manual sections is equivalent evidence. Do not require an Engine Lubrication heading when judging the value itself.',
    'M05': 'A04 requires solvent prohibition, not the damage explanation. The damage explanation is optional here; M23 explicitly asks why and still requires it.',
    'M06': 'A01 requires oil entering the combustion chambers; piston-ring and valve-seal routes are optional explanatory details for this question. They remain required in S16-A02. Cautious but concrete correct technical content can fulfill an element.',
    'M11': 'The 40 lb-ft statement applies to the 60/100/200 amp alternator PMCS entry. Do not apply it to 400 amp alternators.',
    'M15': 'Non-arctic service is shared by the whole answer. PMCS specifies Dexron II for the transfer case, whereas Change 2 lubrication table permits II or III. II is permitted in the transfer case but not in the 4L80-E. Do not mark III permission false or infer that II is uniquely allowed. Transfer level remains within 1/2 inch on level ground.',
    'M18': 'A03 requires solvent prohibition. The reason (diaphragm damage) is optional because this question does not ask why. Annual includes semiannual; semiannual CDR inspection therefore also applies at annual inspection.',
    'M29': 'The full-power failure relation alone is required from intake/exhaust. C002086 supports this relation but not all three symptoms required in S06.',
}

PARTIAL = {
    'U01': '§4-8 replacement reference, PMCS mounting torque 40 lb-ft (54 N m), negative-cable caution, and explicitly sourced starter pinion/gear/armature or flywheel inspections. Identify inspections as partial diagnostic information, never as the complete replacement procedure.',
    'U05': '§4-79 reference, battery PMCS inspection facts and warnings in the frozen source bank. A warning to disconnect the negative cable before PCB/harness work may be reported WITH that original condition. Do not generalize a regulator, PCB or fusible-link procedure into the complete battery replacement sequence.',
    'U07': '§4-29 reference, controller identification, connector inspection and source-qualified warnings. Do not turn connector inspection into the complete controller replacement procedure.',
    'U08': '§3-75 reference, thermostat operating facts and explicitly qualified hot-engine or surge-cap warnings. These do not supply the full access/removal/reassembly procedure.',
    'U09': 'Water-manometer vacuum check, §3-9a/3-9 reference, oil-saturation inspection, solvent prohibition and wiping with a rag. Other generic pressure/vacuum values must not be used as the absent complete test setup and acceptance limits.',
    'U10': '§3-83 reference, M1123 model identity, worn-belt inspections and pulley/tension references with their stated model exclusions. Do not apply the standard adjustable-belt tension to the M1123 serpentine belt or claim a complete routing/removal sequence.',
}


def build():
    if GOLD.exists():
        raise FileExistsError('gold-v2 already exists; preserve it')
    old = read(EXPERIMENT / 'gold-v1/questions.json')
    old_groups = read(EXPERIMENT / 'gold-v1/groups.json')
    chunks_path = ROOT / 'preprocessing/output/corpus-v6-final/chunks.jsonl'
    chunks = {c['id']: c for c in map(json.loads, chunks_path.read_text(encoding='utf-8').splitlines())}
    questions = copy.deepcopy(old)
    changes = []
    audit = []
    normalize = lambda s: re.sub(r'\W+', '', s).lower()
    normalized = {cid: normalize(c['text']) for cid, c in chunks.items()}
    for gid, g in old_groups.items():
        bodies = [normalize(chunks[cid]['text'].split('\n\n')[-1]) for cid in g['primary_chunks']]
        registered = {cid for combo in g['sufficient_chunk_sets'] for cid in combo}
        candidates = [cid for cid, text in normalized.items() if cid not in registered
                      and all(len(b) > 30 and b in text for b in bodies)]
        audit.append({'group': gid, 'question_ids': [q['id'] for q in old if gid in [e['id'] for e in q['evidence']]],
                      'method': 'all primary bodies contained after punctuation/whitespace normalization',
                      'candidate_ids': candidates, 'semantic_exhaustiveness_claimed': False})

    def add_combo(q, group_id, combo, reason):
        group = next(g for g in q['evidence'] if g['id'] == group_id)
        if combo not in group['sufficient_chunk_sets']:
            group['sufficient_chunk_sets'].append(combo)
            group['id'] = group_id if group_id.startswith(q['id'] + ':') else q['id'] + ':' + group_id
            ids = sorted({cid for c in group['sufficient_chunk_sets'] for cid in c})
            group['sources'] = [{k: chunks[cid][k] for k in ('id', 'unit_id', 'pdf_pages', 'printed_pages', 'text_sha256')} for cid in ids]
            changes.append({'question_id': q['id'], 'kind': 'retrieval_alternative', 'chunks': combo, 'reason': reason})

    for q in questions:
        qid = q['id']
        if qid == 'S14':
            add_combo(q, 'idle62', ['C002513'], '6.2 L 625-675 RPM explicitly stated; PDF 281.')
            add_combo(q, 'S14:idle62', ['C005697'], '6.2 L 650 +/-25 RPM explicitly stated; PDF 573.')
        if qid == 'M29':
            add_combo(q, 'intake', ['C002086'], 'Full-power failure relation; PDF 237. Do not propagate to S06.')
        if qid == 'M15':
            add_combo(q, 'transmission', ['C001112'], '4L80-E non-arctic III only; PDF 121. Does not suffice for arctic M19.')
        if qid == 'M16':
            add_combo(q, 'driveline_refill', ['C001117', 'C001118'], 'Change 2 table: hub 1 pt GO and axle 2 qt GO; both rows required; PDF 121.')
        replacements = {
            'M05-A04': 'Do not clean the CDR valve with solvent. The diaphragm-damage explanation is optional for this question.',
            'M06-A01': 'Blue exhaust smoke indicates oil entering the combustion chambers. Specific entry routes are optional for this question.',
            'M18-A03': 'Do not clean the CDR valve with solvent. The diaphragm-damage explanation is optional for this question.',
            'M15-A02': 'Dexron II is permitted in the transfer case. PMCS names II; the Change 2 lubrication table permits II or III. Do not require II-only exclusivity.',
        }
        for element in q['required_elements']:
            if element['id'] in replacements:
                before = element['text']; element['text'] = replacements[element['id']]
                changes.append({'question_id': qid, 'kind': 'rubric', 'id': element['id'], 'before': before, 'after': element['text']})
        q['original_required_elements'] = copy.deepcopy(next(o for o in old if o['id'] == qid)['required_elements'])
        q['review_note'] = (q['review_note'] + ' ' + NOTES.get(qid, '')).strip()
        if qid in PARTIAL:
            changes.append({'question_id': qid, 'kind': 'allowed_partial', 'before': q['allowed_partial_answer'], 'after': PARTIAL[qid]})
            q['allowed_partial_answer'] = PARTIAL[qid]
        ids = {cid for g in q['evidence'] for combo in g['sufficient_chunk_sets'] for cid in combo}
        ids.update(SUPPLEMENTS.get(qid, []))
        if q['type'] == 'unanswerable':
            # Same pre-existing whole-corpus reference search for all ten questions.
            scope = read(EXPERIMENT / f'gold-v1/scope-checks/{qid}.json')
            ids.update(x['id'] for x in scope['corpus_wide_reference_matches'])
        q['oracle_evidence'] = [{'id': cid, 'text': chunks[cid]['text'],
                                'sources': [{k: chunks[cid][k] for k in ('id', 'unit_id', 'pdf_pages', 'printed_pages', 'text_sha256')}]}
                               for cid in sorted(ids)]
        q['min_sufficient_chunks'] = minimum_chunks(q['evidence']) if q['answerable_in_scope'] else None
        q['revision'] = 'post-review-v2-20260929'
    assert [(q['id'], q['question'], q['type']) for q in old] == [(q['id'], q['question'], q['type']) for q in questions]
    policy = read(EXPERIMENT / 'evaluation-policy.json'); policy.update(POLICY_ADDITIONS)
    save(GOLD / 'questions.json', questions)
    save(GOLD / 'changes.json', changes)
    save(GOLD / 'alternative-audit.json', {'group_scan': audit, 'questions_checked': 60, 'chunks_scanned': len(chunks),
                                         'scope': 'Prior 60-question source review plus same exact-body candidate scan for all 69 groups; not exhaustive semantic search.'})
    save(GOLD / 'evaluation-policy.json', policy)
    save(GOLD / 'review-attestation.json', {'status': 'AI_REVISED_RESEARCHER_REVIEW_PENDING', 'reviewer': 'Codex Astra',
                                          'human_reviewed_question_ids': [], 'at': utc()})
    lines = ['# 60문항 정답 근거·청크 대응표 v2', '', '질문·유형·생성 답변은 유지했다. 사후 AI 검토에서 확인한 오류와 평가 기준 보완을 적용했다.', '']
    for q in questions:
        lines += [f"## {q['id']} · {q['type']}", q['question'], '', '필수요소:']
        lines += [f"- {e['id']}: {e['text']}" for e in q['required_elements']]
        lines += ['근거 조합:'] + [f"- {g['id']}: " + ' / '.join(' + '.join(c) for c in g['sufficient_chunk_sets']) for g in q['evidence']]
        lines += ['평가 참고: ' + q['review_note']]
        if q['missing_information']:
            lines += ['결여 정보: ' + q['missing_information'], '허용 부분 답변: ' + q['allowed_partial_answer']]
        lines += ['oracle 청크: ' + ', '.join(e['id'] for e in q['oracle_evidence']), '']
    write_text(GOLD / '대응표.md', '\n'.join(lines))
    # Reuse full-page source images where available; render newly referenced pages separately.
    import fitz
    pdf = fitz.open(PDF); pages = sorted({p for q in questions for e in q['oracle_evidence'] for s in e['sources'] for p in s['pdf_pages']})
    captures = []
    for p in pages:
        image = OLD_REVIEW / f'pages/pdf-{p:04}.png'
        reused = image.exists()
        if not reused:
            image = REV / f'pages/pdf-{p:04}.png'; image.parent.mkdir(parents=True, exist_ok=True)
            pdf[p-1].get_pixmap(dpi=150, alpha=False).save(image)
        captures.append({'pdf_page': p, 'path': image.relative_to(ROOT).as_posix(), 'sha256': sha(image),
                         'reused_prior_capture': reused, 'role': 'source image; capture presence alone is not visual review'})
    pdf.close(); save(GOLD / 'source-captures.json', captures)
    old_scores = []; new_scores = []; details = []
    for q, before in zip(questions, old):
        if q['type'] == 'unanswerable': continue
        attempt = read(EXPERIMENT / f"runs/formal-v1/attempts/r1-{q['id']}-rag.json")
        ids = [c['id'] for c in attempt['retrieval']['items']]
        a = retrieval_score(before, ids); b = retrieval_score(q, ids)
        old_scores.append(a); new_scores.append(b); details.append({'question_id': q['id'], 'retrieved_ids': ids, 'before': a, 'after': b})
    summary = lambda scores: {'n': len(scores), 'mean_evidence_recall_at_5': sum(s['evidence_recall_at_5'] for s in scores)/len(scores),
                               'complete_evidence_count': sum(s['complete_evidence_at_5'] for s in scores)}
    save(REV / 'retrieval-comparison.json', {'old': summary(old_scores), 'new': summary(new_scores), 'details': details, 'retrieval_reexecuted': False})
    save(GOLD / 'manifest.json', {'version': 'gold-v2', 'created_at': utc(), 'source_gold_sha256': sha(EXPERIMENT/'gold-v1/questions.json'),
                                 'source_pdf_sha256': sha(PDF), 'source_corpus_sha256': sha(chunks_path),
                                 'source_review': 'experiment/astra-review/20260929-v1', 'changed_after_initial_results': True,
                                 'question_texts_unchanged': True, 'researcher_direct_review': 'PENDING',
                                 'files': {p.relative_to(GOLD).as_posix(): sha(p) for p in GOLD.rglob('*') if p.is_file()}})
    print(json.dumps({'gold': 'gold-v2', 'questions': len(questions), 'changes': len(changes), 'captures': len(captures),
                      'retrieval_before': summary(old_scores), 'retrieval_after': summary(new_scores)}, ensure_ascii=False))


if __name__ == '__main__':
    build()
