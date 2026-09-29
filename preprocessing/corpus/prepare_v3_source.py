"""Version the reviewed source and migrate only unchanged legacy references."""
import difflib
from .common import BASE,PACKAGE,ROOT,STRUCTURE,read_json,read_jsonl,write_json,write_jsonl,sha


def main():
    out=PACKAGE/'rules/v3'
    if out.exists():raise ValueError('v3 already initialized')
    old={r['id']:r['text'] for r in read_jsonl(BASE/'output/corrected-v4-a/units-corrected.jsonl')}
    new={r['id']:r['text'] for r in read_jsonl(BASE/'output/corrected-v5-a/units-corrected.jsonl')}
    maps={rid:difflib.SequenceMatcher(None,text,new[rid],autojunk=False).get_matching_blocks()
          for rid,text in old.items() if text!=new[rid]}
    log=[]
    def migrate(obj,path):
        if isinstance(obj,list):return [migrate(v,path) for v in obj]
        if not isinstance(obj,dict):return obj
        result={k:migrate(v,path) for k,v in obj.items()}
        rid=obj.get('record_id');a=obj.get('start');b=obj.get('end')
        if rid in maps and isinstance(a,int) and isinstance(b,int):
            if old[rid][a:b]!=obj['text']:raise ValueError('Legacy source mismatch')
            matches=[j+(a-i) for i,j,n in maps[rid] if i<=a and b<=i+n]
            if len(matches)!=1:raise ValueError('Changed legacy decision needs new review: '+path+':'+rid)
            result.update(start=matches[0],end=matches[0]+b-a)
            log.append({'file':path,'record_id':rid,'before':[a,b],'after':[result['start'],result['end']],
                        'text_unchanged':True})
        return result
    out.mkdir()
    files={p.name:p for p in STRUCTURE.glob('*.jsonl')}
    files.update({p.name:p for p in (PACKAGE/'rules/v2').glob('*.jsonl')})
    for name,path in files.items():
        if name=='new-review-items.jsonl':
            # Replaced by page-specific completion/remaining decisions in v3.
            write_jsonl(out/name,[]);continue
        write_jsonl(out/name,migrate(read_jsonl(path),name))
    for path in (PACKAGE/'rules/v2').glob('*.json'):
        write_json(out/path.name,read_json(path))
    write_json(out/'source-migration.json',{'from':'corrected-v4-a','to':'corrected-v5-a',
         'changed_records':list(maps),'reference_migrations':log,
         'legacy_decision_text_changed':False,'removed_pending_findings':'Replaced individually by v3 finding-resolution contracts.'})
    config=read_json(PACKAGE/'config.json')
    config.update(corpus_version='hmmwv-v3',corrected_source='preprocessing/output/corrected-v5-a',
                  correction_ledger='preprocessing/corrections/batch-005/correction-log.json',rules_path='rules/v3')
    write_json(PACKAGE/'config.json',config)
    print('v3 source initialized:',list(maps),'legacy references migrated:',len(log))


if __name__=='__main__':main()
