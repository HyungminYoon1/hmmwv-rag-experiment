"""Add approved v2 sidecars/evidence to the lock without replacing old hashes."""
from .common import ROOT,PACKAGE,read_json,read_jsonl,write_json,sha


def lock_rules():
    path=PACKAGE/'inputs.lock.json';lock=read_json(path)
    config=read_json(PACKAGE/'config.json')
    active_prefix='preprocessing/corpus/'+config.get('rules_path','rules/v2')+'/'
    # Refuse silently accepting any change to existing authoritative inputs.
    for name,expected in lock['files'].items():
        if not name.startswith(active_prefix) and sha(ROOT/name)!=expected:raise ValueError('Existing input changed: '+name)
    rules=PACKAGE/config.get('rules_path','rules/v2')
    assets=list(rules.glob('*.json'))+list(rules.glob('*.jsonl'))
    # Evidence in scope/closure sidecars is as authoritative as box evidence.
    checked_evidence={}
    def evidence_files(value):
        if isinstance(value,list):
            for item in value:yield from evidence_files(item)
        elif isinstance(value,dict):
            if isinstance(value.get('file'),str) and 'sha256' in value:
                candidate=ROOT/value['file']
                if value['file'] not in checked_evidence:
                    if not candidate.is_file():raise ValueError('Missing rule evidence: '+value['file'])
                    checked_evidence[value['file']]=sha(candidate)
                    yield candidate
                if checked_evidence[value['file']]!=value['sha256']:raise ValueError('Rule evidence changed: '+value['file'])
            for item in value.values():yield from evidence_files(item)
    for asset in list(assets):
        data=read_jsonl(asset) if asset.suffix=='.jsonl' else read_json(asset)
        assets.extend(evidence_files(data))
    for rule in read_jsonl(rules/'selection-overrides.jsonl'):
        asset=rule.get('image',rule.get('evidence',{}).get('file'))
        if asset:assets.append(ROOT/asset)
    for rule in read_jsonl(rules/'new-review-items.jsonl'):assets.append(ROOT/rule['evidence']['file'])
    for e in read_json(rules/'layout-profile-review.json')['evidence']:assets.append(ROOT/e['file'])
    if 'corrected_source' in config:
        assets += [ROOT/config['corrected_source']/n for n in ('units-corrected.jsonl','units-before.jsonl','manifest.json')]
        ledger=ROOT/config['correction_ledger'];assets.append(ledger)
        assets += [ledger.parent/p['evidence_crop'] for p in read_json(ledger)['corrections']]
    assets += list((PACKAGE/'reports/rules-v3-work').glob('*.png'))
    assets += list((PACKAGE/'reports/rules-v4-work').glob('*.png'))
    if (rules/'box-units.jsonl').exists():
        assets += [ROOT/r['evidence']['file'] for r in read_jsonl(rules/'box-units.jsonl')]
    if (rules/'source-regions.jsonl').exists():
        assets += [ROOT/r['evidence']['file'] for r in read_jsonl(rules/'source-regions.jsonl')]
    for relative in config.get('additional_inputs',[]):assets.append(ROOT/relative)
    assets += list((PACKAGE/'reports/rules-v2-work/pdf-pages').glob('*.png'))
    assets += list((ROOT/'research/evidence/corpus-detail-rules-proposal-2026-09-24').glob('*.png'))
    for asset in assets:
        asset=asset.resolve()
        if not asset.is_relative_to(ROOT):raise ValueError('Outside project')
        lock['files'][asset.relative_to(ROOT).as_posix()]=sha(asset)
    lock['schema']=2
    write_json(path,lock)
    print(len(lock['files']),'locked inputs and review artifacts')


if __name__=='__main__':lock_rules()
