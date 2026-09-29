"""Project reviewed tables and group text without generating new prose."""
from __future__ import annotations
from collections import defaultdict
import re
from .common import source_part, source_parts, separator, label, parts_text, union_box


class Units:
    def __init__(self, store):
        self.store=store
        self.items=[]

    def add(self, key, kind, body_parts, prefix_parts=None, review_ids=None, metadata=None):
        if not parts_text(body_parts).strip():
            return None
        prefix_parts=list(prefix_parts or [])
        if prefix_parts:
            prefix_parts.append(separator('\n\n'))
        refs=[p['source'] for p in body_parts+prefix_parts if p['kind']=='source']
        pages=sorted({r['pdf_page'] for r in refs})
        if not pages:
            raise ValueError('Unit must have actual source text')
        body_refs=[p['source'] for p in body_parts if p['kind']=='source']
        first=min(body_refs,key=lambda r:(r['pdf_page'],(r['bbox'] or [0,0,0,0])[1],r['start']))
        box=first['bbox'] or [0,0,0,0]
        column=(-1 if box[1]<115 else (0 if (box[0]+box[2])/2<320 else 1)) if first['pdf_page'] in range(526,532) else 0
        unit={'key':key,'kind':kind,'body_parts':body_parts,'prefix_parts':prefix_parts,
              'body_text':parts_text(body_parts),'prefix_text':parts_text(prefix_parts),
              'pdf_pages':pages,'order':[first['pdf_page'],column,box[1],box[0],key],
              'review_ids':list(review_ids or []),'metadata':metadata or {}}
        self.items.append(unit)
        for role,parts in [('body',body_parts),('context',prefix_parts)]:
            for p in parts:
                if p['kind']=='source':
                    self.store.claim(p['source'],key,role)
        return unit


def page_titles(store,pn):
    rid=f'P{pn:04d}:native'
    if rid not in store.records or not store.records[rid]['text'].strip():
        rid=f'P{pn:04d}:ocr'
    if rid not in store.records:
        return []
    candidates=[r for r in store.fragments(rid) if r['text'].strip() and r['bbox'] and r['bbox'][1]<120]
    result=[]
    anchors=[r for r in candidates if re.match(r'^(?:CHAPTER\s|Section\s|SECTION\s|\d+-\d+(?:\.\d+)*\.\s|Table \d|TABLE \d)',r['text'].strip())]
    reference=next((r for r in candidates if r['text'].strip() in ('REFERENCE INFORMATION','DIAGNOSTIC FLOWCHART')),None)
    for r in candidates:
        is_anchor=any(r['start']==a['start'] for a in anchors)
        continuation=any(set(r['source_blocks'])&set(a['source_blocks']) for a in anchors)
        same_header=reference and r['text'].strip().isupper() and abs(r['bbox'][1]-reference['bbox'][1])<24
        if is_anchor or continuation or same_header:
            result.append(r)
    return result


def field_parts(store, fields, definition, prefix=False, include_empty=False):
    parts=[]
    for field,refs in fields:
        if not include_empty and (not refs or not any(r['text'].strip() for r in refs)):
            continue
        if parts:
            parts.append(separator())
        parts.extend([label(field,{**definition,'field':field}),separator(': ')])
        parts.extend(source_parts(refs,'condition' if prefix else 'body'))
    return parts


def reviewed_tables(store,units):
    pmcs=store.table('pmcs-structure.jsonl')
    contexts=store.table('pmcs-context-links.jsonl')
    groups=defaultdict(list)
    for row in pmcs:
        if row['item']:
            groups[row['item']].append(row)
    for item,rows in groups.items():
        key='pmcs:'+item
        prefix=source_parts(page_titles(store,rows[0]['pdf_page']),'heading')
        # Item, interval and applicable component stay with each window.
        for field in ['ITEM NO.','INTERVAL','ITEM TO BE INSPECTED']:
            first=next((r for r in rows if r['fields'][field].strip()),None)
            if first:
                if prefix: prefix.append(separator())
                prefix += field_parts(store,[(field,[store.ref(first['row_id']+':'+field)])],
                                      {'file':'pmcs-structure.jsonl','id':first['row_id']},True)
        context_refs=[]
        for c in contexts:
            if item in c['applies_to_items']:
                context_refs.append(store.ref(c['source_record'],c['start'],c['end']))
        if context_refs:
            if prefix: prefix.append(separator())
            prefix += source_parts(context_refs,'condition')
        body=[]
        for row in rows:
            if body: body.append(separator('\n\n'))
            body += field_parts(store,[(field,[store.ref(row['row_id']+':'+field)]) for field in row['fields']],
                                {'file':'pmcs-structure.jsonl','id':row['row_id']})
        units.add(key,'pmcs_item',body,prefix,metadata={'item':item,'row_ids':[r['row_id'] for r in rows],
                  'source_issues':sorted({x for r in rows for x in r['source_issues']})})
    # Context cells are primary source text too, even when repeated in item prefixes.
    for row in pmcs:
        if row['role']=='context':
            fields=[(field,[store.ref(row['row_id']+':'+field)]) for field in row['fields']]
            units.add('pmcs-context:'+row['row_id'],'pmcs_context',
                      field_parts(store,fields,{'file':'pmcs-structure.jsonl','id':row['row_id']}),
                      source_parts(page_titles(store,row['pdf_page']),'heading'))

    for table in store.table('review557-tables.jsonl'):
        prefix=source_parts(page_titles(store,table['pdf_page']),'heading')
        for i,row in enumerate(table['rows']):
            fields=[(field,[store.exact(r) for r in row[field]['source_spans']]) for field in table['headers']]
            units.add(table['id']+f':row:{i+1}','table_row',
                      field_parts(store,fields,{'file':'review557-tables.jsonl','id':table['id']}),
                      prefix,metadata={'table_id':table['id'],'row':i+1})

    for table in store.table('restored-image-tables.jsonl'):
        rid=table['source_record'];text=store.records[rid]['text']
        prefix=source_parts(page_titles(store,table['pdf_page']),'heading')
        review_ids=[]
        if table.get('parent_condition'):
            # The reviewed sidecar describes the condition; locate its literal
            # source instead of silently synthesizing a contextual sentence.
            expected=table['parent_condition']
            candidates=[]
            native=f'P{table["pdf_page"]:04d}:native'
            full=store.records[native]['text']
            normalized=re.sub(r'\s+',' ',full)
            if expected.casefold() in normalized.casefold():
                words=expected.split()
                pattern=r'\s+'.join(re.escape(w) for w in words)
                match=re.search(pattern,full,re.I)
                if match:
                    candidates=[store.ref(native,*match.span())]
            if candidates:
                if prefix: prefix.append(separator())
                prefix += source_parts(candidates,'condition')
            else:
                review_ids.append(store.review('TABLE_PARENT_CONDITION',table['pdf_page'],
                                  '표의 상위 조건 원문 위치를 확인해야 합니다.',owner=table['id']))
        position=table['start']
        lines=[]
        for line in table['source_text'].splitlines(True):
            lines.append((position,line.rstrip('\r\n')));position+=len(line)
        header_count=1 if table['id']=='P0856:components' else 2
        header_refs=[store.ref(rid,offset,offset+len(line)) for offset,line in lines[:header_count]]
        if prefix: prefix.append(separator())
        prefix += source_parts(header_refs,'table_header')
        data=lines[header_count:]
        if len(data)!=len(table['rows']):
            raise ValueError('Restored table row count mismatch')
        for i,((offset,line),row) in enumerate(zip(data,table['rows'])):
            fields=[];cursor=0
            for header in table['headers']:
                value=row[header]
                pos=line.find(value,cursor)
                if pos<0:
                    raise ValueError('Restored table value is not literal')
                fields.append((header,[store.ref(rid,offset+pos,offset+pos+len(value))]))
                cursor=pos+len(value)
            units.add(table['id']+f':row:{i+1}','table_row',
                      field_parts(store,fields,{'file':'restored-image-tables.jsonl','id':table['id']}),
                      prefix,review_ids,{'table_id':table['id'],'row':i+1})
        # Original header strings and delimiters are separately accounted for.
        whole=store.ref(rid,table['start'],table['end'])
        store.decide(whole,'LAYOUT_ONLY','RESTORED_TABLE_HEADER_OR_DELIMITER',[table['id']])


def manual_tables(store,units):
    for row in store.table('manual-table-units.jsonl'):
        fields=[(f['name'],[store.exact(r) for r in f['refs']]) for f in row['fields']]
        for f,(_,refs) in zip(row['fields'],fields):
            if '\n'.join(r['text'] for r in refs)!=f['text']:
                raise ValueError('Manual table contract mismatch: '+row['key'])
        prefix=source_parts([store.exact(r) for r in row['context_refs']],'condition')
        units.add(row['key'],'manual_table_row',
                  field_parts(store,fields,{'file':'manual-table-units.jsonl','id':row['key']},include_empty=True),
                  prefix,metadata={**row['metadata'],'layout_review':row['review']})
    for item in store.table('manual-dispositions.jsonl'):
        store.decide(store.exact(item['source']),item['status'],item['reason'],[item['rule']])
    store.structured_pages={60,61,62,63,64,119,120,121,123,124,196,277,300,329,532,533,573,855}
    store.structured_pages.update(r['context_refs'][0]['pdf_page']
        for r in store.table('manual-table-units.jsonl')
        if r['metadata'].get('cell_occupancy_checked_against_pdf'))


# Kept as a public import for callers of the original module.
from .regions import prose_units
