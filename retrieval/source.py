"""Read-only access to the frozen corpus and its PDF provenance."""
from __future__ import annotations

from functools import cached_property
from .common import ROOT, local_path, sha, read_json, read_jsonl, check_files, text_sha


class Corpus:
    def __init__(self, config, verify=True):
        self.path = local_path(config['corpus'])
        self.manifest_sha256 = sha(self.path / 'manifest.json')
        if self.manifest_sha256 != config['corpus_manifest_sha256']:
            raise ValueError('The corpus is not the configured frozen version')
        self.manifest = read_json(self.path / 'manifest.json')
        if verify:
            check_files(self.path, self.manifest['files'])
        self.audit = read_json(self.path / 'audit.json')
        if not self.audit['corpus_ready_for_index'] or self.audit['errors']:
            raise ValueError('Corpus has not passed its readiness checks')
        self.chunks = read_jsonl(self.path / 'chunks.jsonl')
        self.by_id = {row['id']: row for row in self.chunks}
        if len(self.by_id) != len(self.chunks) or len(self.chunks) != self.audit['chunks']:
            raise ValueError('Missing or duplicated chunk IDs')
        if [r['id'] for r in self.chunks] != sorted(self.by_id):
            raise ValueError('Chunk ordering is not canonical')
        for row in self.chunks:
            if not row['text'].strip() or text_sha(row['text']) != row['text_sha256']:
                raise ValueError(f'Invalid chunk text: {row["id"]}')
        self.config = read_json(self.path / 'config.json')
        self.pdf_path = ROOT / self.config['source_pdf']
        expected = self.manifest['inputs'][self.config['source_pdf']]
        if verify and sha(self.pdf_path) != expected:
            raise ValueError('Original PDF hash mismatch')

    @cached_property
    def mappings(self):
        return {m['chunk_id']: m for m in read_jsonl(self.path / 'source_map.jsonl')}

    def source(self, chunk_id):
        return {'chunk': self.by_id[chunk_id], 'mapping': self.mappings[chunk_id]}

    def page_png(self, chunk_id, page_number):
        import pymupdf
        chunk = self.by_id[chunk_id]
        if page_number not in chunk['pdf_pages']:
            raise ValueError('Page does not belong to this chunk')
        boxes = {tuple(box) for part in self.mappings[chunk_id]['parts']
                 if part['kind'] == 'source' and part['source']['pdf_page'] == page_number
                 for box in part['source']['bboxes']}
        with pymupdf.open(self.pdf_path) as document:
            page = document[page_number - 1]
            for box in sorted(boxes):
                page.draw_rect(pymupdf.Rect(box), color=(0.07, 0.48, 0.43), width=1, overlay=True)
            return page.get_pixmap(dpi=115, alpha=False).tobytes('png')
