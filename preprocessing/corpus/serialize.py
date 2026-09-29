"""Map every emitted character to source text or declared formatting."""
from __future__ import annotations
from .common import parts_text, text_sha


def sliced_parts(store,parts,start,end,offset=0):
    result=[];position=0
    for part in parts:
        following=position+len(part['text'])
        a,b=max(start,position),min(end,following)
        if a<b:
            left,right=a-position,b-position
            item={'kind':part['kind'],'start':offset+a-start,'end':offset+b-start,
                  'text':part['text'][left:right]}
            if part['kind']=='source':
                source=part['source']
                item['source']=store.ref(source['record_id'],source['start']+left,source['start']+right)
                item['role']=part.get('role','body')
            elif part['kind']=='label':
                item['definition']=part['definition'];item['label_start']=left;item['label_end']=right
            result.append(item)
        position=following
    return result


def chunk_record(store,unit,window,number):
    chunk_id=f'C{number:06d}'
    prefix_len=len(unit['prefix_text'])
    mapping=sliced_parts(store,unit['prefix_parts'],0,prefix_len)
    mapping+=sliced_parts(store,unit['body_parts'],window['body_start'],window['body_end'],prefix_len)
    pages=sorted({m['source']['pdf_page'] for m in mapping if m['kind']=='source'})
    rec={'id':chunk_id,'unit_id':unit['id'],'unit_key':unit['key'],'kind':unit['kind'],
         **window,'prefix_chars':prefix_len,'text_sha256':text_sha(window['text']),
         'pdf_pages':pages,'printed_pages':sorted({str(m['source']['printed_page']) for m in mapping
                                                if m['kind']=='source' and m['source']['printed_page']}),
         'review_ids':unit['review_ids'],'resolved_review_ids':unit.get('resolved_review_ids',[]),'source_issues':unit['source_issues'],
         'structure_metadata':unit['metadata'],
         'status':'REVIEW_REQUIRED' if unit['review_ids'] else 'STRUCTURE_PROJECTED'}
    return rec,{'chunk_id':chunk_id,'parts':mapping}
