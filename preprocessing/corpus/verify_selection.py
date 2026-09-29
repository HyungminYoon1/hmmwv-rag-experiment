"""Independent checks of alternative-source witnesses and their destinations."""
from collections import defaultdict
import re
from .common import read_jsonl,ROOT,sha


def verify_proofs(output,store,selections,check):
    path=output/'selection_proofs.jsonl'
    if not path.is_file():return 0
    proofs=read_jsonl(path);by_id={p['id']:p for p in proofs}
    check(len(by_id)==len(proofs),'REPRESENTATION_IDS')
    old_rules={r['candidate_id']:r for r in store.table('review557-adoption-rules.jsonl')}
    new_rules={r['id']:r for r in store.table('selection-overrides.jsonl')}
    checked_images=set()
    for rule in new_rules.values():
        evidence=rule.get('evidence',{})
        image=rule.get('image',evidence.get('file'))
        expected=rule.get('image_sha256',evidence.get('sha256'))
        check(bool(image and expected),'PDF_DECISION_WITHOUT_EVIDENCE',rule['id'])
        if image and image not in checked_images:
            path=(ROOT/image).resolve()
            check(path.is_relative_to(ROOT) and path.is_file() and sha(path)==expected,'PDF_EVIDENCE_HASH',image)
            check(store.lock['files'].get(image)==expected,'PDF_EVIDENCE_NOT_LOCKED',image)
            checked_images.add(image)
    norm=lambda t:re.sub(r'\s+',' ',t).strip()
    def identity(r):return (r['record_id'],r['start'],r['end'],r['text'])
    for p in proofs:
        source=p['source'];targets=p['targets']
        for ref in [source,*targets]:
            try:check(store.ref(ref['record_id'],ref['start'],ref['end'])==ref,'PROOF_SOURCE_REF',p['id'])
            except (KeyError,ValueError):check(False,'PROOF_SOURCE_REF',p['id'])
        check(bool(targets),'PROOF_EMPTY_TARGET',p['id'])
        check(all(source['pdf_page']==r['pdf_page'] for r in targets),'PROOF_CROSS_PAGE',p['id'])
        check(all(identity(source)!=identity(r) for r in targets),'PROOF_SELF_REFERENCE',p['id'])
        if p['kind']=='WHITESPACE_EQUIVALENT':
            check(norm(source['text'])==norm(' '.join(r['text'] for r in targets)),
                  'ALTERNATIVE_TEXT_MISMATCH',p['id'])
            protected=lambda c:c.isalnum() or c in '._/+-−±°%'
            for ref in targets:
                full=store.records[ref['record_id']]['text'];a,b=ref['start'],ref['end']
                safe=(not a or not(protected(full[a]) and protected(full[a-1]))) and (
                    b==len(full) or not(protected(full[b-1]) and protected(full[b])))
                check(safe,'ALTERNATIVE_PARTIAL_VALUE',p['id'])
        elif p['kind']=='REVIEWED_ALTERNATIVE':
            valid=False
            for rule_id in p['rule_ids']:
                rule=old_rules.get(rule_id)
                if not rule:continue
                source_name='native_span' if rule['preferred_layer_for_aligned_span']=='ocr' else 'ocr_span'
                target_name='ocr_span' if source_name=='native_span' else 'native_span'
                valid=(rule['category']!='FLOWCHART_BRANCH' and identity(source)==identity(rule[source_name])
                       and len(targets)==1 and identity(targets[0])==identity(rule[target_name]))
                if valid:break
            check(valid,'UNVERIFIED_ALTERNATIVE_DECISION',p['id'])
        elif p['kind']=='PDF_REVIEWED_ALTERNATIVE':
            valid=any(rid in new_rules and identity(new_rules[rid]['source'])==identity(source)
                      and [identity(r) for r in new_rules[rid].get('targets',[])]==[identity(r) for r in targets]
                      and new_rules[rid].get('review')=='CODEX_PDF_VISUAL_REVIEW' for rid in p['rule_ids'])
            check(valid,'UNVERIFIED_PDF_DECISION',p['id'])
        else:check(False,'UNKNOWN_PROOF_KIND',p['id'])
    by_record=defaultdict(list)
    for r in selections:by_record[r['record_id']].append(r)
    pending=set()
    def resolve(ref,trail):
        if len(trail)>40:return False
        cursor=ref['start']
        for row in by_record[ref['record_id']]:
            if row['end']<=cursor or row['start']>=ref['end']:continue
            if row['start']>cursor:return False
            if row['status']=='NEEDS_REVIEW':return False
            if row['status']=='DUPLICATE_ALTERNATIVE':
                ids=row.get('representation_proof_ids',[])
                if not ids:return False
                valid=False
                for pid in ids:
                    if pid in trail or pid not in by_id:continue
                    if all(resolve(target,trail|{pid}) for target in by_id[pid]['targets']):valid=True;break
                if not valid:return False
            cursor=min(ref['end'],row['end'])
        return cursor==ref['end']
    for row in selections:
        if row['status']!='DUPLICATE_ALTERNATIVE':continue
        ids=row.get('representation_proof_ids',[])
        check(bool(ids) and all(pid in by_id for pid in ids),'DUPLICATE_WITHOUT_PROOF',row['id'])
        for pid in ids:
            if pid not in by_id:continue
            p=by_id[pid];src=p['source']
            check(src['record_id']==row['record_id'] and src['start']<=row['start']<row['end']<=src['end'],
                  'PROOF_DOES_NOT_COVER_SOURCE',row['id'])
        if not resolve({'record_id':row['record_id'],'start':row['start'],'end':row['end']},set()):pending.add(row['id'])
    return len(pending)
