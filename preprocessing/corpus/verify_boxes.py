"""Verify serialized boxes against frozen contracts and separate PDF check facts."""
from .common import PACKAGE,ROOT,read_json,read_jsonl,sha


def verify_box_contracts(store,units,check):
    rules=PACKAGE/store.config.get('rules_path','rules/v2')
    if not (rules/'box-units.jsonl').exists():return
    by_key={u['key']:u for u in units};seen=set()
    for row in read_jsonl(rules/'box-units.jsonl'):
        u=by_key.get(row['key'])
        check(u is not None,'MISSING_BOX_UNIT',row['key'])
        evidence=row['evidence'];path=ROOT/evidence['file']
        if evidence['file'] not in seen:
            check(path.is_file() and sha(path)==evidence['sha256'],'BOX_EVIDENCE_HASH',row['key'])
            check(store.lock['files'].get(evidence['file'])==evidence['sha256'],'BOX_EVIDENCE_NOT_LOCKED',row['key'])
            seen.add(evidence['file'])
        if not u:continue
        body=row.get('body_separator','\n').join(r['text'] for r in row['body_refs'])
        context=row.get('context_separator','\n').join(r['text'] for r in row['context_refs'])
        check(u['body_text']==body,'BOX_BODY_CHANGED',row['key'])
        check(u['prefix_text']==context+('\n\n' if context else ''),'BOX_CONTEXT_CHANGED',row['key'])
        for name,field in [('body_refs','body_parts'),('context_refs','prefix_parts')]:
            refs=[p['source'] for p in u[field] if p['kind']=='source']
            check(refs==[store.exact(r) for r in row[name]],'BOX_SOURCE_ORDER',row['key'])
        check(all(u['metadata'].get(k)==v for k,v in row['metadata'].items()),'BOX_METADATA_CHANGED',row['key'])
        check(u['kind']==row['kind'],'BOX_KIND',row['key'])
        if row['metadata'].get('profile')=='V6_OCR_DIAGNOSTIC_TEXT':
            left=row['metadata']['condition_box']
            for ref in row['context_refs']:
                b=store.exact(ref)['bbox']
                inside=b and b[0]>=left[0]-3 and b[1]>=left[1]-3 and b[2]<=left[2]+3 and b[3]<=left[3]+3
                title=b and b[3]<130 and 'KNOWN INFO' not in ref['text'] and 'POSSIBLE PROBLEMS' not in ref['text']
                check(inside or title,'CONDITION_OUTSIDE_PRINTED_BOX',row['key'])
    facts=read_json(rules/'box-assertions.json')
    for fact in facts['units']:
        u=by_key.get(fact['key'])
        check(u is not None,'PDF_EXPECTED_BOX',fact['key'])
        if not u:continue
        for field,part in [('body','body_text'),('context','prefix_text')]:
            for term in fact.get('required_'+field,[]):check(term in u[part],'PDF_BOX_REQUIRED_TEXT',fact['key']+':'+term)
            for term in fact.get('forbidden_'+field,[]):check(term not in u[part],'PDF_BOX_WRONG_LINK',fact['key']+':'+term)
        for field,value in fact.get('expected_metadata',{}).items():
            check(u['metadata'].get(field)==value,'PDF_BOX_RELATION',fact['key']+':'+field)
    for pn in facts['complete_native_profile_pages']:
        group=[u for u in units if u['key'].startswith(f'P{pn:04d}:question:') and u['kind']=='diagnostic_box']
        check(len(group)==3,'PDF_BOX_STEP_COUNT',pn)
    card_path=rules/'test-card-review.json'
    if card_path.exists():
        expected=set(read_json(card_path)['units'])
        actual={u['key'] for u in units if u['key'].startswith('V6:CARD:')}
        check(expected==actual,'PDF_TEST_CARD_SECTION_SET','reviewed card inventory')
    steps=sorted(int(u['metadata']['step']) for u in units if u['key'].startswith('P0573:step:'))
    check(steps==list(range(8,30)),'PDF_PROCEDURE_STEP_ORDER',573)
    flow_path=rules/'flow-links.jsonl'
    if flow_path.exists():
        links=read_jsonl(flow_path)
        expected=read_json(rules/'flow-assertions.json')['edges']
        actual=[[r['source'],r['branch'],r['target']] for r in links]
        check(sorted(actual,key=str)==sorted(expected,key=str),'PDF_FLOW_EDGE_SET','reviewed edges')
        for edge in links:
            check(edge['source'] in by_key and edge['target'] in by_key,'FLOW_ENDPOINT_EXISTS',edge['source'])
            if edge['branch'] is not None:
                ref=store.exact(edge['branch_source'])
                check(ref['text']==edge['branch'],'FLOW_LITERAL_BRANCH',edge['source'])
                check(ref['pdf_page']==edge['page'],'FLOW_BRANCH_PAGE',edge['source'])
            evidence=edge['evidence']
            check(store.lock['files'].get(evidence['file'])==evidence['sha256'],
                  'FLOW_EVIDENCE_NOT_LOCKED',edge['source'])
