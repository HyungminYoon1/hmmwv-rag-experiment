"""Migrate exact refs through additive corrections and register reviewed boxes."""
from collections import defaultdict
import copy
from .common import *


def main(version=12):
    rules=PACKAGE/'rules/v6';batch=BASE/f'corrections/batch-{version:03d}'
    snapshot=PACKAGE/f'reports/rules-v6-work/rules-before-v{version}'
    if snapshot.exists():raise ValueError('Migration already started')
    snapshot.mkdir()
    for p in rules.iterdir():
        if p.is_file():(snapshot/p.name).write_bytes(p.read_bytes())
    old=SourceStore(check=False);ledger=read_json(batch/'correction-log.json')
    new={r['id']:r for r in read_jsonl(BASE/f'output/corrected-v{version}-a/units-corrected.jsonl')}
    old_ids={p['id'] for ps in old.patches.values() for p in ps};deltas=defaultdict(list)
    for p in ledger['corrections']:
        if p['id'] not in old_ids:
            shift=sum(len(q['after'])-q['end']+q['start'] for q in old.patches[p['record_id']] if q['end']<=p['start'])
            deltas[p['record_id']].append({**p,'start':p['start']+shift,'end':p['end']+shift})
    for ps in deltas.values():ps.sort(key=lambda p:p['start'])
    changed=[]
    def boundary(rid,pos,right=False):
        offset=0
        for p in deltas[rid]:
            if pos<=p['start']:return pos+offset
            if pos>=p['end']:offset+=len(p['after'])-p['end']+p['start']
            else:return p['start']+offset+(len(p['after']) if right else 0)
        return pos+offset
    def migrate(value):
        if isinstance(value,list):return [v for x in value if (v:=migrate(x)) is not None]
        if not isinstance(value,dict):return value
        rid=value.get('record_id',value.get('source_record'))
        if rid in deltas and all(k in value for k in ('start','end')):
            a,b=boundary(rid,value['start']),boundary(rid,value['end'],True)
            if a==b:return None
            out=copy.deepcopy(value);out.update(start=a,end=b)
            if 'text' in out:out['text']=new[rid]['text'][a:b]
            if 'source_text' in out:out['source_text']=new[rid]['text'][a:b]
            changed.append({'record_id':rid,'before':[value['start'],value['end']],'after':[a,b]})
            return out
        return {k:migrate(v) for k,v in value.items()}
    for p in rules.glob('*.jsonl'):
        if p.name in ('coordinate-spans.jsonl','alignment-triage.jsonl'):continue
        rows=migrate(read_jsonl(p));clean=[]
        for r in rows:
            if any(k in r and not r[k] for k in ('source','native_span','ocr_span','body_refs')):continue
            if r.get('action')=='REPRESENT' and not r.get('targets'):continue
            clean.append(r)
        write_jsonl(p,clean)
    write_jsonl(rules/'coordinate-spans.jsonl',[])
    config=read_json(PACKAGE/'config.json');config.update(corrected_source=f'preprocessing/output/corrected-v{version}-a',correction_ledger=f'preprocessing/corrections/batch-{version:03d}/correction-log.json')
    config['additional_inputs']=sorted(set(config['additional_inputs']+[f'preprocessing/corrections/batch-{version:03d}/reviewed-boxes.json',
       'preprocessing/corpus/reports/rules-v6-work/box-ocr-candidates/review-decisions.json']))
    write_json(PACKAGE/'config.json',config)
    store=SourceStore(check=False);regions=read_jsonl(rules/'source-regions.jsonl');contracts=[]
    for box in read_json(batch/'reviewed-boxes.json'):
        rid=box['record_id'];refs=[]
        for w in box['word_spans']:
            if not w['text']:continue
            hits=[(cs,ce,rs,re,pid) for cs,ce,rs,re,pid in store.runs[rid] if max(w['raw_start'],rs)<min(w['raw_end'],re)]
            assert len(hits)==1,(box['id'],w,hits)
            cs,ce,rs,re,pid=hits[0]
            a,b=(cs,ce) if pid else (cs+w['raw_start']-rs,cs+w['raw_end']-rs)
            ref=store.ref(rid,a,b);assert ref['text']==w['text']
            refs.append(ref)
            regions.append({'name':box['id'],'record_id':rid,'pdf_page':box['pdf_page'],
               'start':a,'end':b,'text':w['text'],'bbox':box['bbox'],
               'review':'CODEX_PDF_LAYOUT_REVIEW','evidence':{'file':box['source_image'],'sha256':box['source_image_sha256']}})
        assert ' '.join(r['text'] for r in refs).split()==box['literal_text'].split()
        contracts.append({'key':box['id']+':reviewed','kind':'reviewed_text_box','body_refs':refs,'context_refs':[],
          'metadata':{'boundary':'individually_reviewed_pdf_box','literal_box':box['id'],
            'graphic_relations_inferred':False,'condition_link_basis':'LOCAL_BOX_ONLY_PENDING_PROFILE',
            'box':box['bbox'],'literal_transcription':box['literal_text'],'text_structure':box['decision'].get('structure')},
          'review':'CODEX_PDF_LAYOUT_REVIEW','review_codes':[],'evidence':{'file':box['source_image'],'sha256':box['source_image_sha256']}})
    write_jsonl(rules/'source-regions.jsonl',regions)
    store=SourceStore(check=False)
    def refresh(value):
        if isinstance(value,list):return [refresh(v) for v in value]
        if isinstance(value,dict):
            if all(k in value for k in ('record_id','start','end','text','raw_spans')):return store.ref(value['record_id'],value['start'],value['end'])
            return {k:refresh(v) for k,v in value.items()}
        return value
    for p in rules.glob('*.jsonl'):
        if p.name in ('coordinate-spans.jsonl','alignment-triage.jsonl'):continue
        rows=read_jsonl(p)
        if p.name=='box-units.jsonl':rows+=contracts
        write_jsonl(p,refresh(rows))
    write_json(rules/f'v{version}-reference-migration.json',{'changed_references':changed,'reviewed_boxes':len(contracts),
       'basis':'Only additive, recorded raw-source word corrections; neighbouring source words preserved.'})
    print({'migrated_refs':len(changed),'reviewed_boxes':len(contracts),'source_regions':len(regions)})


if __name__=='__main__':main()
