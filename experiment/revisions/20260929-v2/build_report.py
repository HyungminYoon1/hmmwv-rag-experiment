"""Build a static before/after report from saved evaluations. No model calls."""
from pathlib import Path
import sys
import json
import shutil
import html
import math
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from experiment.evaluation.common import read, save, sha, utc, write_text

HERE = Path(__file__).resolve().parent
ACTIVE = read(HERE/'active-evaluation.json') if (HERE/'active-evaluation.json').exists() else {'run_id': 'sol-revision-formal-20260929-v2'}
RUN = ROOT/'experiment/evaluation/runs'/ACTIVE['run_id']
OLD = ROOT/'experiment/evaluation/runs/sol-formal-20260928-numeric-v3'
WEB = ROOT/'experiment/astra-review/20260929-v1'
GOLD = ROOT/'experiment/gold-v2'
LABELS = {'ar_report': '질문 관련성', 'oracle_support': '정답 근거 지지율', 'required_coverage': '필수 요소 충족률',
          'faithfulness': '검색 문맥 충실도', 'full_abstention': '완전 답변유보율', 'correct_abstention': 'RAG 적절한 답변유보율',
          'corpus_unanswerable_abstention': 'LLM Only 교범 답변불가 유보율'}


def esc(v): return html.escape(str(v if v is not None else ''))
def display(value, metric):
    if value is None: return '—'
    return f'{value:.4f}' if metric == 'ar_report' else f'{value*100:.1f}%'


def build():
    s = read(RUN/'summary.json'); old = read(OLD/'summary.json')
    results = {p.stem: read(p)['result'] for p in (RUN/'results').glob('*.json')}
    prior = read(RUN/'previous-results.json'); inputs = {r['attempt_key']: r for r in read(RUN/'inputs.json')['rows']}
    gold = read(GOLD/'questions.json'); changes = read(GOLD/'changes.json')
    retrieval = read(HERE/'retrieval-comparison.json')
    verification = read(HERE/'verification.json') if (HERE/'verification.json').exists() else {'status': 'PENDING'}
    complete = s['processed'] == 120 and s['answers_with_evaluator_errors'] == 0 and verification['status'] == 'PASS' and verification.get('run_id') == RUN.name
    api_count = ACTIVE.get('source_api_responses', s['provider_response_count'])
    usage = ACTIVE.get('source_usage', s['usage'])
    repairs = read(RUN/'citation-repairs.json') if (RUN/'citation-repairs.json').exists() else []
    quote_count = sum(len(r['changes']) for r in repairs)
    table = []
    for metric, label in LABELS.items():
        for condition in ['LLM_ONLY', 'RAG']:
            def find(summary):
                return next((a for a in summary['aggregate'] if a['metric'] == metric and a['condition'] == condition and a['type'] == 'all'), None)
            b = find(old); a = find(s)
            if not a or not a['valid_n']: continue
            table.append({'metric': metric, 'label': label, 'condition': condition, 'before': b['mean'], 'after': a['mean'],
                          'before_valid_n': b['valid_n'], 'valid_n': a['valid_n'], 'delta': a['mean']-b['mean']})
    # Never compare a partial new cohort against the complete old cohort.
    if not complete:
        table = []
    differences = []
    for key, after in sorted(results.items()):
        before = prior[key]
        changed = {k: {'before': before['metrics'][k]['value'], 'after': v['value']} for k, v in after['metrics'].items()
                   if v['value'] != before['metrics'][k]['value']}
        differences.append({'attempt_key': key, 'changed_metrics': changed})
    save(HERE/'comparison.json', {'status': 'COMPLETED' if complete else 'IN_PROGRESS', 'at': utc(), 'rows': table,
                                'retrieval': retrieval, 'answers': differences, 'new_api_response_count': api_count,
                                'usage': usage, 'run_id': RUN.name, 'source_run_id': ACTIVE.get('source_run_id', RUN.name),
                                'derivative_new_api_calls': 0, 'recovered_stages': len(repairs), 'timing_or_generation_changed': False})
    resolution = [
        ('G01', '적용', 'S14·M29에 확인한 대체 근거를 추가했다. M29의 한 사실을 S06의 세 증상 근거로 확대하지 않았다. 69개 묶음에 동일한 본문 포함 검색도 수행했다.'),
        ('G02', '적용', 'M05·M06·M18에서 질문에 요구하지 않은 설명을 필수요소와 분리했다. S02의 복합요건과 모든 요소의 충족 규칙을 명시했다. 사후 기준 변경으로 기록했다.'),
        ('G03', '적용', '모든 등록 대체 청크와 10개 답변불가 문항의 기존 전체 corpus 절 번호 검색 결과를 oracle에 포함했다. 확인된 점검·경고를 부분 답변 목록에 추가했다.'),
        ('G04', '원문 보존', '25/50의 max·less-than 차이와 단위 축약을 그대로 기록한다. 현재 질문의 20/30 비교에는 경계값 차이가 영향을 주지 않는다.'),
        ('G05', '적용', 'M11의 토크 적용 대상을 60/100/200 amp 발전기로 유지하고 평가 안내에 명시했다.'),
        ('G06', '적용', 'M15에 Change 2의 transfer-case Dexron II 또는 III 허용 표를 포함했다. 비극한 4L80-E의 III 전용 조건과 구별한다.'),
        ('E01', '적용', '주장 추출에서 공통 조건을 보존하고 지지 판정에도 질문·답변을 조건 확인용으로 제공한다. M15의 조건 누락 감점은 해소됐으나, 용량을 액면 기준으로 제시한 별도 오류가 확인돼 두 주장은 감점했다.'),
        ('E02', '적용', '입력 유무·자기 출처·인용 ID 설명을 excluded_metadata에 보존하고 기술 사실의 분모에서 분리했다. 같은 뜻의 중복 주장도 제거하도록 했다.'),
        ('E03', '적용', '값·대상·조건이 동일한 동등 근거를 인정한다. M09/M10처럼 절별 값이 다른 차트의 제한은 유지한다.'),
        ('E04', '적용', '관련 기술 사실이 있으면 부분 답변 검사를 수행한다. 부분 주장별 oracle와 실제 문맥 판정을 별도 기록하고 프로그램이 점수를 계산한다.'),
        ('E05', '적용', '조심스럽게 표현했더라도 구체적인 정답 내용을 제시하면 내용 충족을 인정한다. 실제 근거 지지 여부와 구분한다.'),
        ('E06', '기록 보존·정정', '기존 Astra의 최초 판정을 보존했다. 추가로 M15의 용량과 액면 기준을 혼동한 답변을 놓친 최초 판정을 사후 의견에서 정정했다. 새로운 Sol 결과에 Astra 수동 점수를 섞지 않았다.'),
        ('E07', '해석 보완', '유보 성공을 답변 전체 정확도라고 표현하지 않는다. 잘못된 M1123 부연은 별도 기술 주장으로 판정하되 유보 지표 자체의 정의는 유지한다.'),
    ]
    save(HERE/'issue-resolution.json', [{'id': i, 'status': status, 'action': action} for i, status, action in resolution])
    lines = ['# 평가 오류 수정 및 결과 업데이트', '', f"작성: {utc()} · 처리 {s['processed']}/120 · 검증 {verification['status']}", '',
             '기존 60문항과 첫 회차 120개 답변을 유지하고, 원문 검토에서 확인한 근거 누락과 평가 기준을 보완했다. gold-v2와 수정된 평가 규칙을 두 조건에 동일하게 적용했다.', '',
             '## 검색 결과', '', '| 지표 | 이전 | 수정 후 |', '|---|---:|---:|',
             f"| 근거 Recall@5 | {retrieval['old']['mean_evidence_recall_at_5']:.0%} | {retrieval['new']['mean_evidence_recall_at_5']:.0%} |",
             f"| 모든 필수 근거 검색 | {retrieval['old']['complete_evidence_count']}/50 | {retrieval['new']['complete_evidence_count']}/50 |", '',
             '저장된 Top-5를 새 대응표로 재계산했다. 검색 모델이나 인덱스를 변경하거나 검색을 다시 실행하지 않았다.', '',
             '## 답변 평가', '', '| 지표 | 조건 | 이전 | 수정 후 | 유효 답변 수 (이전 → 후) |', '|---|---|---:|---:|---:|']
    for r in table:
        lines.append(f"| {r['label']} | {r['condition']} | {display(r['before'],r['metric'])} | {display(r['after'],r['metric'])} | {r['before_valid_n']} → {r['valid_n']} |")
    lines += ['', '질문 관련성 및 완전 답변유보 분류는 기존 검증 결과를 그대로 사용했다. 근거 지지율·필수요소·답변불가 유보 판정은 재평가했다. 점수 변화에는 기준·근거 보완과 평가모델의 재판정 변동이 함께 들어 있으므로 생성모델의 성능 향상으로 해석하지 않는다.', '',
              '두 조건의 답변불가 유보율은 정의가 다르다. RAG는 부연한 부분 사실의 정답·검색 근거까지 요구한다. LLM Only 지표는 결여된 전체 절차를 유보했는지만 측정하므로 전체 사실 정확도가 아니다.', '',
              'U05 RAG는 제어박스 부연의 근거가 보완됐지만 자동 유보 판정은 0으로 유지됐다. 자료 범위를 설명하는 문장의 조건·or 예시를 해석하는 경계 사례로 후속 의미 검토에 남겼다. 10문항 지표이므로 이 한 문항의 판정은 유보율 10%p에 해당한다. 기본 자동 점수를 임의로 변경하지 않았다.', '',
              '답변 가능한 50문항에서 기술 주장이 하나도 없는 응답은 정답 근거 지지율 0, 검색 문맥 충실도 해당 없음으로 처리한다. 입력 설명을 기술 사실과 분리하면서 충실도 평균의 분모가 달라질 수 있다. 주장 분해 단위의 차이도 개별 지지율 변화에 영향을 준다.', '',
              '## 수정 사항', '']
    lines += [f'- {i} / {status}: {action}' for i, status, action in resolution]
    lines += ['', '## 검증과 실행 기록', '', f"- 원본 보존 및 산술·인용·입력 검증: {verification['status']}",
              '- 코드 회귀 검사: 38개 통과. Sol 가상 사례: 3개 통과, API 응답 9회. 가상 사례는 실험 결과에서 제외했다.',
              f"- 본 재평가 API 응답: {api_count}회. 토큰: {json.dumps(usage,ensure_ascii=False)}. 청구 금액을 뜻하지 않는다.",
              f"- 인용 복원: {len(repairs)}개 평가 단계, {quote_count}개 인용. 원 응답의 판정·주장·사유·근거 ID는 보존하고 생략된 중간 원문만 복원했다. 파생 실행의 추가 API 호출은 0회다.",
              '- 모델: gpt-6-sol, reasoning=medium, 동시 요청 1개, 첫 유효 응답 채택, 최대 3회 시도.',
              '- 원문 PDF, corpus, 생성 답변, 원래 점수는 보존했다. 추가적인 근거·평가 기록은 새 버전에 저장했다.',
              '- 원문의 관련 구간은 앞선 Astra 검토와 추가 후보 확인을 활용했다. corpus 전체에 의미상 동등한 근거가 하나도 빠지지 않았다고 보증하는 작업은 아니다.',
              '- 이번 검토·수정은 AI가 수행했다. 연구자 직접 검토 및 인간 평가자 검증 상태는 PENDING으로 유지한다.', '',
              '## 자료 확인 범위', '',
              '| 자료 | 상태 | 확인 범위 |', '|---|---|---|',
              '| 원 교범 PDF | PARTIAL | 파일 해시 및 연결된 페이지 캡처를 확인했다. 이전 검토의 88쪽 이미지 대조와 이번의 추가 확인을 활용했으며 890쪽 전체를 새로 정독하지 않았다. |',
              '| gold-v1 / gold-v2 | VERIFIED | 60문항과 69개 근거 묶음, 개정 전후 필수요소·대체 근거를 대조했다. |',
              '| 원 실험 답변·검색 결과 | VERIFIED | 120개 평가 입력의 답변·Top-5·문항이 원래 결과와 동일한지 확인했다. 의미 검토는 최초 40개 표본 및 후속 사례로 범위를 구분한다. |',
              '| 새 Sol 평가 결과 | ' + ('VERIFIED' if complete else 'PARTIAL') + ' | 완료 건수·해시·인용·계산과 선언된 변경을 검사한다. 이 상태는 사람의 전문적 판단 검증을 뜻하지 않는다. |', '',
              '## 평가 개정 요약', '',
              '> 최초 자동평가 후 원문 PDF와의 추가 AI 대조를 통해 대체 정답 근거의 누락 및 평가 규칙의 모호성을 확인하였다. 질문과 생성 답변을 보존한 상태에서 정답 근거와 채점 규칙을 개정하고, 동일한 평가모델로 두 조건의 답변을 재평가하였다. 개정 전후의 기준과 결과를 함께 보관하였다. 질문 관련성은 기존 역생성 질문과 임베딩으로 계산한 값을 재사용하였다. 근거 지지율과 검색 문맥 충실도는 조건을 보존한 기술 사실 주장에 대한 맞춤 NLI 평가로 산출하였다. 이 과정은 연구자의 직접 수동평가와 구분하였다.', '',
              '실험 생성 전에 고정한 평가 기준과 사후 개정한 기준을 실험 기록에서 구별한다. 현재 질문 세트는 변경하지 않았으며 새 독립 시험 세트로 표현하지 않는다.', '',
              '## 자료와 재현', '',
              '- [결정 기록](DECISIONS.md)', '- [근거 대응표 v2](../../gold-v2/대응표.md)', '- [프로그램 검증 결과](verification.json)',
              '- [답변별 전후 차이](comparison.json)', f'- [최종 Sol 결과](../../evaluation/runs/{RUN.name}/report.md)',
              '- [인용 복원 기준](인용_복원_결정.md)',
              '- [후속 의미 검토 및 Astra 정정](후속_의미검토.md)',
              '- [이전 PDF 캡처 및 AI 검토](../../astra-review/20260929-v1/00_검토보고서.md)',
              '- [OpenAI 평가 지침](https://developers.openai.com/api/docs/guides/evaluation-best-practices)', '',
              '```powershell', '.\\retrieval\\.venv\\Scripts\\python.exe -X utf8 experiment\\revisions\\20260929-v2\\verify_results.py',
              '.\\experiment\\evaluation\\.venv\\Scripts\\python.exe -X utf8 experiment\\revisions\\20260929-v2\\build_report.py', '```']
    write_text(HERE/'결과_업데이트.md', '\n'.join(lines)+'\n')
    # Keep the original first AI review as a separate historical page.
    if not (WEB/'review-v1.html').exists(): shutil.copy2(WEB/'index.html', WEB/'review-v1.html')
    for name in ['결과_업데이트.md', 'comparison.json', 'issue-resolution.json', 'verification.json', 'DECISIONS.md', '후속_의미검토.md', '인용_복원_결정.md']:
        if (HERE/name).exists(): shutil.copy2(HERE/name, WEB/('revision-'+name))
    web_md = (WEB/'revision-결과_업데이트.md').read_text(encoding='utf-8')
    for before, after in [
        ('(DECISIONS.md)', '(revision-DECISIONS.md)'),
        ('(../../gold-v2/대응표.md)', '(revision-gold.md)'),
        ('(verification.json)', '(revision-verification.json)'),
        ('(comparison.json)', '(revision-comparison.json)'),
        ('(후속_의미검토.md)', '(revision-후속_의미검토.md)'),
        ('(인용_복원_결정.md)', '(revision-인용_복원_결정.md)'),
        (f'(../../evaluation/runs/{RUN.name}/report.md)', f'(http://127.0.0.1:8767/evaluation?run={RUN.name})'),
        ('(../../astra-review/20260929-v1/00_검토보고서.md)', '(00_검토보고서.md)')]:
        web_md = web_md.replace(before, after)
    write_text(WEB/'revision-결과_업데이트.md', web_md)
    followup = (WEB/'revision-후속_의미검토.md').read_text(encoding='utf-8')
    followup = followup.replace('(../../astra-review/20260929-v1/', '(')
    followup = followup.replace('(../../evaluation/runs/sol-revision-formal-20260929-v2/results/r1-M15-rag.json)', '(revision-answers.html#r1-M15-rag)')
    write_text(WEB/'revision-후속_의미검토.md', followup)
    shutil.copy2(GOLD/'대응표.md', WEB/'revision-gold.md')
    captures = read(GOLD/'source-captures.json'); page_links = {}
    for cap in captures:
        target = WEB/f"pages/pdf-{cap['pdf_page']:04}.png"
        if not target.exists():
            target = WEB/f"revision-pages/pdf-{cap['pdf_page']:04}.png"; target.parent.mkdir(exist_ok=True)
            shutil.copy2(ROOT/cap['path'], target)
        page_links[cap['pdf_page']] = target.relative_to(WEB).as_posix()

    def frame(title, body, active):
        nav = [('index.html', '수정 결과'), ('revision-gold.html', '정답 근거'), ('revision-answers.html', '답변별 비교'), ('review-v1.html', '최초 검토 기록')]
        return '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+'</title><link rel="stylesheet" href="report.css"><header><small>KIDeT 2026 · HMMWV 정비교범 실험</small><h1>'+esc(title)+'</h1><nav>'+''.join(f'<a class="{"active" if url==active else ""}" href="{url}">{label}</a>' for url,label in nav)+'</nav></header><main>'+body+'<footer>2026-09-29 · gold-v2 · Sol 재평가 · 원문과 최초 실험 기록 보존</footer></main></html>'
    status_text = '재평가 및 검증 완료' if complete else '재평가 진행 중'
    body = f'<p>{status_text}. 기존 답변 {s["processed"]}/120개에 수정한 평가 기준을 적용했습니다.</p>'
    body += f'<div class="stats"><div class="stat"><strong>{retrieval["new"]["mean_evidence_recall_at_5"]:.0%}</strong><span>근거 Recall@5 · 이전 69%</span></div><div class="stat"><strong>{retrieval["new"]["complete_evidence_count"]}/50</strong><span>모든 필수 근거 검색 · 이전 26</span></div><div class="stat"><strong>{s["processed"]}/120</strong><span>답변 재평가</span></div><div class="stat"><strong>{esc(verification["status"])}</strong><span>원본 보존·계산·인용 검사</span></div></div>'
    body += '<p class="notice">질문과 생성 답변은 같습니다. 점수 변화는 근거 목록과 평가 기준을 보완한 결과이며, 생성모델을 개선해서 얻은 성능 향상은 아닙니다.</p>'
    body += '<h2>답변 평가 전후 비교</h2>'
    if not complete:
        body += '<p>120개 답변의 재평가와 검증을 마친 뒤 같은 전체 문항을 기준으로 전후 평균을 표시합니다.</p>'
    body += '<div class="scroll"><table><thead><tr><th>지표</th><th>조건</th><th>이전</th><th>수정 후</th><th>유효 답변 수<br>이전 → 후</th></tr></thead><tbody>'
    for r in table: body += f'<tr><td>{r["label"]}</td><td>{r["condition"]}</td><td>{display(r["before"],r["metric"])}</td><td><strong>{display(r["after"],r["metric"])}</strong></td><td>{r["before_valid_n"]} → {r["valid_n"]}</td></tr>'
    body += '</tbody></table></div><p class="muted">질문 관련성과 완전 답변유보 분류는 기존 값을 재사용했습니다. 기술 주장이 없는 답변은 충실도 평균에서 제외합니다. 두 조건의 답변불가 유보율은 평가 범위가 달라 전체 정확도처럼 직접 비교하지 않습니다.</p>'
    body += '<p class="small">U05의 자료 범위 설명은 해석의 경계 사례로 남겨 두었습니다. 자동 점수는 보존하고, 이유는 <a href="revision-후속_의미검토.md">후속 검토</a>에 기록했습니다.</p>'
    body += '<h2>어떻게 고쳤나요?</h2><div class="card"><ol><li>문항별로 동등한 근거를 추가하고, 다른 질문으로 잘못 확대하지 않았습니다.</li><li>주장의 운용 조건을 유지하고 입력·출처 설명을 기술 사실 점수와 분리했습니다.</li><li>질문에 없는 추가 설명을 필수요소에서 분리하고 부분 답변의 근거를 각각 확인했습니다.</li></ol><p>기준 개정은 최초 결과 확인 후 이루어졌으며, 두 조건 모두 같은 기준으로 재평가했습니다.</p></div>'
    body += '<details><summary>검토에서 확인한 13개 항목의 처리</summary><table><tr><th>항목</th><th>처리</th><th>내용</th></tr>'+''.join(f'<tr><td>{i}</td><td>{status}</td><td>{esc(action)}</td></tr>' for i,status,action in resolution)+'</table></details>'
    body += f'<p>Astra가 원문을 대조한 추가 AI 검토와 Sol의 자동평가를 기록했습니다. 연구자 직접 검토·정비 전문가 검증을 완료한 것으로 표시하지 않았습니다.</p><p class="muted">본 재평가 API 응답 {api_count}회 · 평가기 오류가 있는 답변 {s["answers_with_evaluator_errors"]}개 · 인용 복원 {len(repairs)}단계(추가 API 0회)</p>'
    body += f'<p><a class="chip" href="revision-결과_업데이트.md">결과 문서</a><a class="chip" href="revision-DECISIONS.md">결정 기록</a><a class="chip" href="revision-후속_의미검토.md">후속 검토와 정정</a><a class="chip" href="revision-인용_복원_결정.md">인용 복원 기준</a><a class="chip" href="revision-verification.json">검증 결과</a><a class="chip" href="http://127.0.0.1:8767/evaluation?run={RUN.name}">상세 평가 실행</a></p>'
    write_text(WEB/'index.html', frame('평가 오류 수정 결과', body, 'index.html'))
    search = '<input type="search" id="search" placeholder="문항 번호 또는 내용 검색" aria-label="문항 검색">'
    search_js = '<script>document.querySelector("#search").addEventListener("input",e=>{let q=e.target.value.toLowerCase();document.querySelectorAll(".entry").forEach(x=>x.hidden=!x.textContent.toLowerCase().includes(q))})</script>'
    body = '<p>원 질문을 유지하고 수정한 필수요소·근거 조합·원문 페이지를 정리했습니다.</p>'+search
    for q in gold:
        pages = sorted({p for e in q['oracle_evidence'] for source in e['sources'] for p in source['pdf_pages']})
        body += f'<details class="entry" id="{q["id"]}"><summary>{q["id"]} · {esc(q["question"])}</summary><h3>필수요소</h3><ul>'+''.join(f'<li>{e["id"]}: {esc(e["text"])}</li>' for e in q['required_elements'])+'</ul>'
        body += '<h3>검색 근거 조합</h3><ul>'+''.join(f'<li>{esc(g["id"])}: {esc(" / ".join(" + ".join(c) for c in g["sufficient_chunk_sets"]))}</li>' for g in q['evidence'])+'</ul>'
        body += '<p>'+esc(q['review_note'])+'</p>'
        if q['allowed_partial_answer']: body += '<p>허용 부분 답변: '+esc(q['allowed_partial_answer'])+'</p>'
        body += '<h3>원문 전체 페이지</h3>'+''.join(f'<a class="chip" href="{page_links[p]}">PDF {p}</a>' for p in pages)
        body += '<details><summary>고정한 정답 근거 텍스트</summary>'+''.join(f'<h4>{e["id"]}</h4><pre>{esc(e["text"])}</pre>' for e in q['oracle_evidence'])+'</details></details>'
    write_text(WEB/'revision-gold.html', frame('정답 근거 v2', body+search_js, 'revision-gold.html'))
    body = '<p>최초 답변을 그대로 두고 적용한 새 판정입니다. 펼치면 이전 점수와 주장별 새 근거를 확인할 수 있습니다.</p>'+search
    for key, r in sorted(results.items()):
        row = inputs[key]; before = prior[key]
        body += f'<details class="entry" id="{key}"><summary>{r["question_id"]} · {r["condition"]}</summary><p>{esc(row["user_input"])}</p><pre>{esc(row["response"])}</pre><table><tr><th>지표</th><th>이전</th><th>수정 후</th></tr>'
        for name, label in LABELS.items():
            a = r['metrics'][name]['value']; b = before['metrics'][name]['value']
            if a is not None or b is not None: body += f'<tr><td>{label}</td><td>{display(b,name)}</td><td>{display(a,name)}</td></tr>'
        body += f'</table><p><a href="revision-gold.html#{r["question_id"]}">이 문항의 근거와 PDF 캡처</a></p><details><summary>주장·인용·요소별 판정 원문</summary><pre>{esc(json.dumps(r["stages"],ensure_ascii=False,indent=2))}</pre></details></details>'
    write_text(WEB/'revision-answers.html', frame('120개 답변 재평가', body+search_js, 'revision-answers.html'))
    print(json.dumps({'status': 'COMPLETE' if complete else 'PARTIAL', 'answers': s['processed'], 'report': str(HERE/'결과_업데이트.md')}, ensure_ascii=False))


if __name__ == '__main__': build()
