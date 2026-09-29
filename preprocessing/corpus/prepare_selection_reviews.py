"""Replay individually inspected contact-sheet decisions; no fuzzy decisions."""
from .common import PACKAGE,ROOT,read_json,read_jsonl,write_jsonl,sha


def main():
    folder=PACKAGE/'rules/v2'
    rows=read_jsonl(folder/'selection-overrides.jsonl')
    known={r['id'] for r in rows}
    inspected={
        'short_labels':{72,81,90,91,165,191,219,248,343,344,345,346,347,354,356,374,419},
        'manual_tables':{20,21,22,23,24,25,316,317,318,319,320,321,322,323,324,325,326,327,328,329},
        'pmcs':set(range(93,160))-{100,106,132,133},
    }
    for category,numbers in inspected.items():
        evidence=PACKAGE/'reports/rules-v2-work/selection-crops'/category
        for entry in read_json(evidence/'manifest.json'):
            if int(entry['id'][1:]) not in numbers:continue
            source=entry['source'];targets=entry['targets']
            pairs=[(source,targets)]
            if entry['id']=='R000343':pairs=[(target,[source]) for target in targets]
            for i,(src,dst) in enumerate(pairs):
                key='PDF-V2-'+entry['id']+(f'-{i+1}' if len(pairs)>1 else '')
                if key in known:continue
                png=evidence/entry['sheet']
                rows.append({'id':key,'source':src,'targets':dst,'action':'REPRESENT',
                             'preferred_refs':dst,'reason':'PDF_CONFIRMED_ALTERNATIVE_LAYER',
                             'review':'CODEX_PDF_VISUAL_REVIEW','rule_ids':['S03','S07','S09'],
                             'evidence':{'file':png.relative_to(ROOT).as_posix(),'sha256':sha(png),
                                         'clip':entry['clip']},'text_modified':False})
    write_jsonl(folder/'selection-overrides.jsonl',rows)
    print(len(rows),'reviewed source decisions')


if __name__=='__main__':main()
