"""Map frozen OCR words to original offsets and group physical review candidates.

No text/condition is adopted or review cleared by this script. An exact OCR
rerun match proves offset correspondence, not correctness against the PDF.
"""
from collections import Counter,defaultdict
from .common import SourceStore,BASE,PACKAGE,read_json,read_jsonl,write_json,write_jsonl,sha


def main():
    s=SourceStore();folder=PACKAGE/'reports/rules-v4-work/ocr-words-all'
    manifest=read_json(folder/'manifest.json')
    for name,digest in manifest['files'].items():assert sha(folder/name)==digest
    old={p['pdf_page']:p for p in read_jsonl(BASE/'assets/ocr-full-manual-v2/pages.jsonl')}
    captures={p['pdf_page']:read_json(folder/f"page-{p['pdf_page']:04d}.json") for p in manifest['pages']}
    lookup={pn:defaultdict(list) for pn in captures}
    deltas=[]
    for pn,c in captures.items():
        assert c['raster_matches_frozen']
        for line in c['lines']:lookup[pn][(tuple(line['bbox']),line['text'])].append(line)
        before=old[pn]['lines'];after=c['lines']
        deltas.append({'pdf_page':pn,'same_line_count':len(before)==len(after),
                       'text_changed':[(a['text'],b['text']) for a,b in zip(before,after) if a['text']!=b['text']],
                       'all_legacy_fields_match':c['legacy_lines_exactly_match']})
    queue=read_jsonl(BASE/'output/corpus-v3-rules-c/review_queue.jsonl')
    candidates=[]
    for q in queue:
        if q['code']!='CROSS_REGION_TEXT':continue
        for source in q['source_refs']:
            rid=source['record_id'];pn=source['pdf_page']
            item={'old_review_id':q['id'],'pdf_page':pn,'source':source,'adopted':False,
                  'semantic_review':'NOT_COMPLETED','word_spans':[],'segments':[]}
            if source['layer']!='ocr':
                item['status']='NATIVE_BOX_BOUNDARY_REVIEW';candidates.append(item);continue
            if pn in (217,262,289):
                item['status']='REPLACED_BY_PDF_REVIEWED_BATCH007';candidates.append(item);continue
            spans=source['raw_spans']
            if any(x['correction_id'] for x in spans):
                item['status']='EXISTING_CORRECTION_NEEDS_REGION_COORDINATES';candidates.append(item);continue
            covered=set();words=[];issue=None
            for a,b,bbox,block,fonts in s.lines[rid]:
                relevant=[x for x in spans if max(a,x['start'])<min(b,x['end'])]
                if not relevant:continue
                raw=s.before[rid]['text'][a:b]
                matches=lookup[pn].get((tuple(bbox),raw),[])
                if len(matches)!=1:issue='RERUN_LINE_NOT_IDENTICAL';break
                for w in matches[0]['words']:
                    start,end=a+w['start'],a+w['end']
                    if not any(x['start']<=start and end<=x['end'] for x in relevant):continue
                    assert s.before[rid]['text'][start:end]==w['text']
                    words.append({'raw_start':start,'raw_end':end,'text':w['text'],'bbox':w['bbox']})
                    covered.update(range(start,end))
            if issue is None:
                for x in spans:
                    if any(i not in covered and not s.before[rid]['text'][i].isspace() for i in range(x['start'],x['end'])):
                        issue='PARTIAL_WORD_OR_UNMAPPED_CHARACTER';break
            if issue:item['status']=issue
            else:
                item['status']='EXACT_WORD_COORDINATES_REQUIRES_LAYOUT_REVIEW'
                item['word_spans']=words
                # These are physical segments, not semantic columns or nodes.
                groups=[]
                for w in words:
                    if not groups:groups.append([w]);continue
                    p=groups[-1][-1]
                    if w['bbox'][0]-p['bbox'][2]>24 or w['bbox'][0]<p['bbox'][0]-5:
                        groups.append([w])
                    else:groups[-1].append(w)
                for group in groups:
                    a,b=group[0]['raw_start'],group[-1]['raw_end']
                    item['segments'].append({'raw_start':a,'raw_end':b,'text':s.before[rid]['text'][a:b],
                        'bbox':[min(w['bbox'][0] for w in group),min(w['bbox'][1] for w in group),
                                max(w['bbox'][2] for w in group),max(w['bbox'][3] for w in group)],
                        'semantic_role':'UNASSIGNED'})
            candidates.append(item)
    target=PACKAGE/'reports/rules-v4-work/coordinate-review'
    if target.exists():raise ValueError('Use a new report version')
    target.mkdir()
    write_jsonl(target/'candidates.jsonl',candidates)
    write_jsonl(target/'ocr-rerun-differences.jsonl',deltas)
    counts=dict(Counter(c['status'] for c in candidates))
    write_json(target/'summary.json',{'pages_captured':len(captures),'candidates':len(candidates),'statuses':counts,
        'pages_with_changed_text':[d['pdf_page'] for d in deltas if d['text_changed']],
        'raw_coordinates_only':True,'reviews_cleared_by_this_program':0,'corpus_text_modified':False,
        'coordinate_file_sha256':sha(target/'candidates.jsonl'),'capture_manifest_sha256':sha(folder/'manifest.json')})
    print(counts)


if __name__=='__main__':main()
