"""Compare immutable runs by source character coordinates, not changing IDs."""
from collections import Counter,defaultdict
from pathlib import Path
from .common import ROOT,BASE,read_json,read_jsonl,write_json,write_jsonl,sha


def verify_hashes(folder):
    manifest=read_json(folder/'manifest.json')
    for name,expected in manifest['files'].items():
        path=(folder/name).resolve()
        if not path.is_relative_to(folder) or not path.is_file() or sha(path)!=expected:
            raise ValueError('Artifact differs from its own manifest: '+name)
    return manifest


def compare(before,after,output,replica=None):
    before=Path(before).resolve();after=Path(after).resolve();output=Path(output).resolve()
    if output.exists() or not output.is_relative_to(ROOT):raise ValueError('Use a new report directory in the project')
    old_manifest=verify_hashes(before);new_manifest=verify_hashes(after)
    a=read_jsonl(before/'selection_ledger.jsonl');b=read_jsonl(after/'selection_ledger.jsonl')
    by_a=defaultdict(list);by_b=defaultdict(list)
    for r in a:by_a[r['record_id']].append(r)
    for r in b:by_b[r['record_id']].append(r)
    if set(by_a)!=set(by_b):raise ValueError('Source record inventory changed')
    changes=[];transitions=Counter();complete=True
    for rid in by_a:
        left=by_a[rid];right=by_b[rid]
        for rows in [left,right]:
            cursor=0
            for r in rows:
                if r['start']!=cursor or r['end']-r['start']!=len(r['text']):raise ValueError('Broken source partition')
                cursor=r['end']
        if ''.join(r['text'] for r in left)!=''.join(r['text'] for r in right):raise ValueError('Original record text changed: '+rid)
        boundaries=sorted({v for r in left+right for v in (r['start'],r['end'])})
        i=j=0
        for start,end in zip(boundaries,boundaries[1:]):
            while left[i]['end']<=start:i+=1
            while right[j]['end']<=start:j+=1
            prev,cur=left[i],right[j]
            if prev['status']==cur['status']:continue
            transitions[prev['status']+' -> '+cur['status']]+=end-start
            changes.append({'record_id':rid,'pdf_page':cur['pdf_page'],'start':start,'end':end,
                            'text':cur['text'][start-cur['start']:end-cur['start']],
                            'before':prev['status'],'after':cur['status'],
                            'before_reason':prev['reason'],'after_reason':cur['reason'],
                            'rule_ids':cur.get('rule_ids',[]),'representation_proof_ids':cur.get('representation_proof_ids',[])})
    check_same=[]
    if replica:
        replica=Path(replica).resolve();replica_manifest=verify_hashes(replica)
        if new_manifest['inputs']!=replica_manifest['inputs'] or new_manifest['code']!=replica_manifest['code']:
            raise ValueError('Replica uses different inputs or code')
        for name in [*new_manifest['files'],'manifest.json']:
            check_same.append({'file':name,'equal':sha(after/name)==sha(replica/name),'sha256':sha(after/name)})
    unchanged_inputs={name:expected for name,expected in old_manifest['inputs'].items()
                      if new_manifest['inputs'].get(name)==expected and sha(ROOT/name)==expected}
    before_chunks=read_jsonl(before/'chunks.jsonl');after_chunks=read_jsonl(after/'chunks.jsonl')
    exact=Counter(c['text_sha256'] for c in before_chunks)&Counter(c['text_sha256'] for c in after_chunks)
    audit=read_json(after/'audit.json')
    result={'before':before.relative_to(ROOT).as_posix(),'after':after.relative_to(ROOT).as_posix(),
            'before_summary':read_json(before/'build_summary.json'),'after_summary':read_json(after/'build_summary.json'),
            'unchanged_original_inputs':len(unchanged_inputs),'original_input_count':len(old_manifest['inputs']),
            'same_source_record_text':True,'complete_source_partitions':True,
            'changed_status_intervals':len(changes),'status_transition_characters':dict(transitions),
            'identical_chunk_texts':sum(exact.values()),'chunk_ids_are_not_comparison_keys':True,
            'replica_files':check_same,'deterministic_replica':all(r['equal'] for r in check_same) if check_same else None,
            'new_audit_mechanical_status':audit['mechanical_status'],
            'corpus_ready_for_index':audit['corpus_ready_for_index'],
            'unresolved_is_not_missing_audit_data':True}
    output.mkdir(parents=True)
    write_json(output/'comparison.json',result)
    write_jsonl(output/'changed_dispositions.jsonl',changes)
    write_jsonl(output/'newly_pending.jsonl',[r for r in changes if r['after']=='NEEDS_REVIEW'])
    write_jsonl(output/'previously_pending_resolved.jsonl',[r for r in changes if r['before']=='NEEDS_REVIEW' and r['after']!='NEEDS_REVIEW'])
    return result


def main():
    import argparse,json
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('before',type=Path);p.add_argument('after',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--replica',type=Path)
    a=p.parse_args();r=compare(a.before,a.after,a.output,a.replica)
    print(json.dumps({k:r[k] for k in ['same_source_record_text','unchanged_original_inputs','changed_status_intervals','identical_chunk_texts','deterministic_replica','corpus_ready_for_index']},indent=2))


if __name__=='__main__':main()
