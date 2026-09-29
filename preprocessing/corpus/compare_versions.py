"""Compare corpus versions through audited correction deltas and exact intervals."""
from collections import Counter,defaultdict
from pathlib import Path
from bisect import bisect_right
from .common import BASE,ROOT,read_json,read_jsonl,write_json,write_jsonl,sha
from .compare_runs import verify_hashes
from verify_corrections import audit_changes


def corrected_source(run):
    config=read_json(run/'config.json')
    folder=ROOT/config.get('corrected_source','preprocessing/output/corrected-v4-a')
    ledger=ROOT/config.get('correction_ledger','preprocessing/corrections/batch-004/correction-log.json')
    return read_jsonl(folder/'units-corrected.jsonl'),read_json(ledger)


def compare(before,after,output,replica):
    before,after,output,replica=map(lambda p:Path(p).resolve(),(before,after,output,replica))
    if output.exists() or not output.is_relative_to(ROOT):raise ValueError('Use a new project report directory')
    am,bm,rm=[verify_hashes(p) for p in (before,after,replica)]
    old,al=corrected_source(before);new,bl=corrected_source(after)
    old_ids={p['id']:p for p in al['corrections']};new_ids={p['id']:p for p in bl['corrections']}
    if any(new_ids.get(k)!=p for k,p in old_ids.items()):raise ValueError('Parent corrections were changed')
    by_record=defaultdict(list)
    for p in al['corrections']:by_record[p['record_id']].append(p)
    delta=[]
    for p in bl['corrections']:
        if p['id'] in old_ids:continue
        shift=sum(len(q['after'])-(q['end']-q['start']) for q in by_record[p['record_id']] if q['end']<=p['start'])
        if any(max(q['start'],p['start'])<min(q['end'],p['end']) for q in by_record[p['record_id']]):
            raise ValueError('Overlapping version corrections need an explicit replacement contract')
        delta.append({**p,'start':p['start']+shift,'end':p['end']+shift})
    errors,diffs=audit_changes(old,new,delta)
    if errors:raise ValueError(errors)
    old_text={r['id']:r['text'] for r in old};new_text={r['id']:r['text'] for r in new}
    groups=[]
    for run in (before,after):
        grouped=defaultdict(list)
        for row in read_jsonl(run/'selection_ledger.jsonl'):grouped[row['record_id']].append(row)
        for rid,rows in grouped.items():
            cursor=0
            for r in rows:
                if r['start']!=cursor or r['end']-r['start']!=len(r['text']):raise ValueError('Broken source partition')
                cursor=r['end']
            expected=old_text[rid] if run==before else new_text[rid]
            if ''.join(r['text'] for r in rows)!=expected:raise ValueError('Ledger/source mismatch')
        groups.append(grouped)
    corrections=defaultdict(list)
    for p in delta:corrections[p['record_id']].append(p)
    transitions=Counter();changes=[];same_chars=0
    for rid,left in groups[0].items():
        right=groups[1][rid];runs=[];a=b=0
        for p in sorted(corrections[rid],key=lambda p:p['start']):
            if a<p['start']:runs.append((a,p['start'],b))
            b+=p['start']-a+len(p['after']);a=p['end']
        if a<len(old_text[rid]):runs.append((a,len(old_text[rid]),b))
        le=[r['end'] for r in left];re=[r['end'] for r in right]
        for start,end,dest in runs:
            if old_text[rid][start:end]!=new_text[rid][dest:dest+end-start]:raise ValueError('Unrecorded text delta')
            same_chars+=end-start;cursor=start;i=bisect_right(le,cursor);j=bisect_right(re,dest)
            while cursor<end:
                new_cursor=dest+cursor-start
                next_end=min(end,left[i]['end'],start+right[j]['end']-dest)
                prev,cur=left[i],right[j]
                if prev['status']!=cur['status']:
                    transitions[prev['status']+' -> '+cur['status']]+=next_end-cursor
                    changes.append({'record_id':rid,'pdf_page':cur['pdf_page'],'before_start':cursor,
                         'before_end':next_end,'after_start':new_cursor,'after_end':new_cursor+next_end-cursor,
                         'text':old_text[rid][cursor:next_end],'before':prev['status'],'after':cur['status']})
                cursor=next_end
                if cursor==left[i]['end']:i+=1
                if dest+cursor-start==right[j]['end']:j+=1
    files=[{'file':n,'equal':sha(after/n)==sha(replica/n),'sha256':sha(after/n)} for n in [*bm['files'],'manifest.json']]
    if bm['inputs']!=rm['inputs'] or bm['code']!=rm['code']:raise ValueError('Replica input/code differs')
    preserved=[name for name,digest in am['inputs'].items() if bm['inputs'].get(name)==digest and sha(ROOT/name)==digest]
    result={'before':before.relative_to(ROOT).as_posix(),'after':after.relative_to(ROOT).as_posix(),
            'all_source_changes_match_ledger':True,'added_corrections':len(delta),
            'changed_source_records':len({p['record_id'] for p in delta}),
            'actual_delta_diff_hunks':len(diffs),'complete_source_partitions':True,
            'unchanged_source_characters_compared':same_chars,'changed_status_intervals':len(changes),
            'status_transition_characters_in_unchanged_spans':dict(transitions),
            'previous_inputs_preserved':len(preserved),'previous_input_count':len(am['inputs']),
            'replica_files':files,'deterministic_replica':all(x['equal'] for x in files),
            'before_summary':read_json(before/'build_summary.json'),'after_summary':read_json(after/'build_summary.json'),
            'after_audit':read_json(after/'audit.json')}
    output.mkdir(parents=True)
    write_json(output/'comparison.json',result);write_jsonl(output/'source-correction-delta.jsonl',delta)
    write_jsonl(output/'actual-text-diffs.jsonl',diffs);write_jsonl(output/'changed_dispositions.jsonl',changes)
    write_jsonl(output/'newly_pending.jsonl',[x for x in changes if x['after']=='NEEDS_REVIEW'])
    write_jsonl(output/'previously_pending_resolved.jsonl',[x for x in changes if x['before']=='NEEDS_REVIEW' and x['after']!='NEEDS_REVIEW'])
    return result


if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('before',type=Path);p.add_argument('after',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--replica',type=Path,required=True)
    args=p.parse_args();r=compare(args.before,args.after,args.output,args.replica)
    print(json.dumps({k:r[k] for k in ['added_corrections','changed_source_records','all_source_changes_match_ledger',
        'previous_inputs_preserved','deterministic_replica','changed_status_intervals']},ensure_ascii=False))
