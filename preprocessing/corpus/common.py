"""File contracts and exact corrected-to-extracted source references."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
BASE = PACKAGE.parent
ROOT = BASE.parent
STRUCTURE = BASE / 'review-557/verified-v4-a'


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def read_jsonl(path):
    with Path(path).open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_text(path, text):
    Path(path).write_bytes(text.replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8'))


def write_json(path, value):
    write_text(path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def write_jsonl(path, values):
    write_text(path, ''.join(json.dumps(v, ensure_ascii=False, sort_keys=True) + '\n' for v in values))


def overlap(a, b):
    if not a or not b:
        return (0., 0.)
    dx = max(0., min(a[2], b[2]) - max(a[0], b[0]))
    dy = max(0., min(a[3], b[3]) - max(a[1], b[1]))
    return dx / max(1., min(a[2]-a[0], b[2]-b[0])), dy / max(1., min(a[3]-a[1], b[3]-b[1]))


def union_box(boxes):
    if not boxes:
        return None
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def intersects(a, b, c, d):
    return max(a, c) < min(b, d)


class SourceStore:
    def __init__(self, check=True):
        self.config = read_json(PACKAGE / 'config.json')
        self.lock = read_json(PACKAGE / 'inputs.lock.json')
        if check:
            for relative, expected in self.lock['files'].items():
                path = (ROOT / relative).resolve()
                if not path.is_relative_to(ROOT) or not path.is_file() or sha(path) != expected:
                    raise ValueError('Input hash mismatch: ' + relative)
        source = self.config.get('corrected_source', 'preprocessing/output/corrected-v4-a')
        corrections = self.config.get('correction_ledger', 'preprocessing/corrections/batch-004/correction-log.json')
        self.records = {r['id']: r for r in read_jsonl(ROOT/source/'units-corrected.jsonl')}
        self.before = {r['id']: r for r in read_jsonl(ROOT/source/'units-before.jsonl')}
        region_path = PACKAGE/self.config.get('rules_path','rules/v2')/'source-regions.jsonl'
        self.source_regions = defaultdict(list)
        if region_path.exists():
            for region in read_jsonl(region_path):
                rec = self.records[region['record_id']]
                box=region['bbox']
                if not (0<=region['start']<region['end']<=len(rec['text']) and
                        rec['pdf_page']==region['pdf_page'] and len(box)==4 and
                        all(isinstance(v,(int,float)) for v in box) and box[0]<box[2] and box[1]<box[3]):
                    raise ValueError('Invalid reviewed region geometry or range')
                if rec['text'][region['start']:region['end']] != region['text']:
                    raise ValueError('Reviewed region text mismatch')
                self.source_regions[region['record_id']].append(region)
        self.pages = {p['pdf_page']: p for p in read_jsonl(BASE/'output/full-manual-v2-a/pages.jsonl')}
        self.coordinate_spans = defaultdict(list)
        coordinates = PACKAGE/self.config.get('rules_path','rules/v2')/'coordinate-spans.jsonl'
        if coordinates.exists():
            for span in read_jsonl(coordinates):
                if self.records[span['record_id']]['text'][span['start']:span['end']] != span['text']:
                    raise ValueError('Frozen coordinate text mismatch')
                self.coordinate_spans[span['record_id']].append(span)
        self.patches = defaultdict(list)
        for p in read_json(ROOT/corrections)['corrections']:
            self.patches[p['record_id']].append(p)
        self.runs = {}
        self.lines = defaultdict(list)
        for rid, record in self.records.items():
            raw = self.before[rid]['text']
            runs, a, c = [], 0, 0
            for p in sorted(self.patches[rid], key=lambda p: p['start']):
                if raw[p['start']:p['end']] != p['before']:
                    raise ValueError('Correction source mismatch: '+p['id'])
                if p['start'] > a:
                    size = p['start'] - a
                    runs.append((c, c+size, a, p['start'], None))
                    c += size
                runs.append((c, c+len(p['after']), p['start'], p['end'], p['id']))
                c += len(p['after']); a = p['end']
            if a < len(raw):
                runs.append((c, c+len(raw)-a, a, len(raw), None))
            self.runs[rid] = runs
            if record['layer'] == 'table':
                self.lines[rid] = [(0, len(raw), record.get('bbox'), 'cell', [])]
            else:
                offset = 0
                for bi, block in enumerate(self.pages[record['pdf_page']][record['layer']+'_blocks']):
                    for line in block['lines']:
                        end = offset+len(line['text'])
                        if raw[offset:end] != line['text']:
                            raise ValueError('Source line offsets differ: '+rid)
                        self.lines[rid].append((offset, end, line['bbox'], bi, line.get('fonts', [])))
                        offset = end+1
                    offset += 1
        self.claims = defaultdict(list)
        self.decisions = defaultdict(list)
        self.reviews = []
        self._review_seq = 0
        self.representations = defaultdict(list)
        self.selection_proofs = []
        self.resolutions = []

    def table(self, name):
        versioned = PACKAGE / self.config.get('rules_path', 'rules/v2') / name
        if versioned.is_file():
            return read_jsonl(versioned)
        if name in ('manual-table-units.jsonl','manual-dispositions.jsonl','selection-overrides.jsonl','page-layouts.jsonl','new-review-items.jsonl'):
            path=PACKAGE/'rules/v2'/name
            return read_jsonl(path) if path.is_file() else []
        return read_jsonl(STRUCTURE/name)

    def ref(self, rid, start=0, end=None):
        rec = self.records[rid]
        end = len(rec['text']) if end is None else end
        if not (type(start) is int and type(end) is int and 0 <= start <= end <= len(rec['text'])):
            raise ValueError('Invalid source span: '+rid)
        raw_spans = []
        for cs, ce, rs, re, correction_id in self.runs[rid]:
            if not intersects(start, end, cs, ce):
                continue
            if correction_id:
                left, right = rs, re
            else:
                left = rs+max(start-cs, 0); right = rs+min(end-cs, ce-cs)
            raw_spans.append({'start':left, 'end':right, 'correction_id':correction_id})
        matches = [line for line in self.lines[rid] if any(intersects(line[0], line[1], r['start'], r['end']) for r in raw_spans)]
        boxes = list({tuple(line[2]) for line in matches if line[2]})
        # A restored cell had no raw text at the value's printed position.
        # Include its reviewed PDF region, rather than highlighting only the
        # neighbouring label used as the insertion anchor in the raw record.
        patch_ids={r['correction_id'] for r in raw_spans if r['correction_id']}
        boxes += [tuple(p['bbox']) for p in self.patches[rid]
                  if p['id'] in patch_ids and p.get('kind')=='MISSING_PRINTED_CELL']
        boxes=list(set(boxes))
        reviewed = [r for r in self.source_regions[rid]
                    if intersects(start,end,r['start'],r['end'])]
        # Only replace coarse correction coordinates when every non-space
        # character is covered by the explicitly reviewed source regions.
        regional = bool(reviewed) and all(c.isspace() or any(r['start']<=i<r['end'] for r in reviewed)
                                         for i,c in enumerate(rec['text'][start:end],start))
        if regional: boxes=list({tuple(r['bbox']) for r in reviewed})
        coordinates=[r for r in self.coordinate_spans[rid] if intersects(start,end,r['start'],r['end'])]
        precise=not regional and bool(coordinates) and all(c.isspace() or any(r['start']<=i<r['end'] for r in coordinates)
                    for i,c in enumerate(rec['text'][start:end],start))
        if precise:
            # A requested subspan can contain only some words of a line.
            boxes=list({tuple(w['bbox']) for r in coordinates for w in r['words']
                        if intersects(start,end,w['start'],w['end'])})
        boxes.sort(key=lambda b: (b[1], b[0], b[3], b[2]))
        block_ids = list(dict.fromkeys(line[3] for line in matches))
        return {'record_id':rid, 'start':start, 'end':end, 'text':rec['text'][start:end],
                'pdf_page':rec['pdf_page'], 'printed_page':rec['printed_page'], 'layer':rec['layer'],
                'bbox':union_box(boxes), 'bboxes':[list(b) for b in boxes], 'raw_spans':raw_spans,
                'coordinate_precision':('reviewed_pdf_region' if regional else 'frozen_word_coordinates' if precise else
                                        'correction_region' if any(s['correction_id'] for s in raw_spans) else 'line_or_cell'),
                'source_blocks':block_ids, 'fonts':sorted({f for line in matches for f in line[4]})}

    def exact(self, ref):
        result = self.ref(ref['record_id'], ref['start'], ref['end'])
        if result['text'] != ref['text']:
            raise ValueError('Sidecar text mismatch: '+ref['record_id'])
        return result

    def claim(self, ref, owner, role='body'):
        self.claims[ref['record_id']].append((ref['start'], ref['end'], owner, role))

    def decide(self, ref, status, reason, rule_ids=None):
        self.decisions[ref['record_id']].append((ref['start'], ref['end'], status, reason, rule_ids or []))

    def represent(self, ref, targets, reason, rule_ids=None, kind='WHITESPACE_EQUIVALENT'):
        from .equivalence import proof
        item=proof(ref,targets,kind,rule_ids)
        item['id']=f'P{len(self.selection_proofs)+1:07d}'
        item['reason']=reason
        self.selection_proofs.append(item)
        self.representations[ref['record_id']].append((ref['start'],ref['end'],item['id']))
        return item['id']

    def represented(self, ref):
        return [pid for a,b,pid in self.representations[ref['record_id']]
                if a<=ref['start'] and ref['end']<=b]

    def review(self, code, page, detail, refs=None, owner=None):
        self._review_seq += 1
        entry = {'id':f'R{self._review_seq:06d}', 'code':code, 'pdf_page':page,
                 'detail':detail, 'source_refs':refs or [], 'unit_key':owner, 'status':'NEEDS_REVIEW'}
        self.reviews.append(entry)
        return entry['id']

    def fragments(self, rid, extra=()):
        text = self.records[rid]['text']
        bounds = {0, len(text), *extra}
        pos = 0
        for line in text.splitlines(True):
            stripped_end = pos+len(line.rstrip('\r\n'))
            bounds.update([pos, stripped_end, pos+len(line)]); pos += len(line)
        for a,b,*_ in self.claims[rid] + self.decisions[rid] + self.representations[rid]:
            bounds.update([a,b])
        for span in self.coordinate_spans[rid]:
            bounds.update([span['start'],span['end']])
        ordered = sorted(x for x in bounds if 0 <= x <= len(text))
        for a,b in zip(ordered, ordered[1:]):
            yield self.ref(rid, a, b)

    def claimed(self, ref):
        return any(a <= ref['start'] and ref['end'] <= b for a,b,*_ in self.claims[ref['record_id']])

    def decision(self, ref):
        values = [(s,r,ids) for a,b,s,r,ids in self.decisions[ref['record_id']]
                  if a <= ref['start'] and ref['end'] <= b]
        if not values:
            return None
        # Choosing an extraction layer is independent of how its literal text
        # is represented (for example a native branch label kept as metadata).
        final=[v for v in values if v[0]!='PREFERRED']
        if final:values=final
        # Conflicting explicit rules may not silently win by iteration order.
        states = {v[0] for v in values}
        if len(states) > 1:
            return ('NEEDS_REVIEW','CONFLICTING_SELECTION_RULES',sorted({x for v in values for x in v[2]}))
        return (values[0][0],'; '.join(sorted({v[1] for v in values})),sorted({x for v in values for x in v[2]}))


def source_part(ref, role='body'):
    return {'kind':'source','text':ref['text'],'source':ref,'role':role}


def separator(text='\n'):
    if any(c not in '\n\t :;|[]=' for c in text):
        raise ValueError('Unsupported formatting separator')
    return {'kind':'separator','text':text}


def label(text, definition):
    return {'kind':'label','text':text,'definition':definition}


def parts_text(parts):
    return ''.join(p['text'] for p in parts)


def source_parts(refs, role='body', join='\n'):
    result=[]
    for ref in refs:
        if result:
            result.append(separator(join))
        result.append(source_part(ref, role))
    return result
