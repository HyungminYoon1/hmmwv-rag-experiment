"""Behavioral and corruption tests using the actual pinned tokenizer/source."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer

from corpus.common import BASE,PACKAGE,SourceStore,read_json,read_jsonl,write_json,write_jsonl,sha,text_sha
from corpus.chunk import Chunker,ChunkingError
from corpus.structure import Units,reviewed_tables
from corpus.app import Application,make_handler,output_path


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine=Chunker(BASE/'assets/qwen-tokenizer/tokenizer.json')

    def test_exact_body_reconstruction_and_unicode(self):
        body=('압력 10–15 PSI · 엔진 6.5L · ±25 °C 🛠️\nDo not remove the cap.\n'*160)
        prefix='WARNING\nCondition: engine stopped.\n\n'
        windows=self.engine.split(body,prefix)
        self.assertGreater(len(windows),2)
        reconstructed='';previous_end=0
        for w in windows:
            self.assertEqual(w['text'],prefix+body[w['body_start']:w['body_end']])
            self.assertLessEqual(self.engine.count(w['text']),500)
            reconstructed+=body[max(previous_end,w['body_start']):w['body_end']]
            if previous_end:
                self.assertGreaterEqual(w['overlap_tokens'],100)
                self.assertTrue(all(self.engine.count(body[a:previous_end])<100
                                    for a in range(w['body_start']+1,previous_end)))
            previous_end=w['body_end']
        self.assertEqual(reconstructed,body)
        self.assertEqual(windows,self.engine.split(body,prefix))

    def test_small_independent_units_have_no_overlap(self):
        for text in ('First independent item.','Second independent item.'):
            result=self.engine.split(text,'Heading\n')
            self.assertEqual(len(result),1)
            self.assertEqual(result[0]['overlap_tokens'],0)
            self.assertEqual(result[0]['body_end'],len(text))
        self.assertEqual(self.engine.split(' \n\t'),[])

    def test_required_context_is_never_silently_dropped(self):
        with self.assertRaises(ChunkingError):
            self.engine.split('Value: 15 PSI.','condition '*800)
        # A prefix can fit by itself yet leave too little body for a new window.
        tiny=Chunker(BASE/'assets/qwen-tokenizer/tokenizer.json',max_tokens=30,overlap=25)
        with self.assertRaises(ChunkingError):
            tiny.split('body '*150,'required condition '*8)


class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store=SourceStore()

    def test_corrected_table_offsets_point_back_to_logged_replacement(self):
        table=next(t for t in self.store.table('restored-image-tables.jsonl') if t['pdf_page']==856)
        ref=self.store.ref(table['source_record'],table['start'],table['end'])
        self.assertEqual(ref['text'],table['source_text'])
        self.assertIn('FIX-0110',[x['correction_id'] for x in ref['raw_spans']])
        self.assertTrue(ref['bboxes'])

    def test_pmcs_cells_rows_conditions_and_incomplete_source_survive(self):
        units=Units(self.store);reviewed_tables(self.store,units)
        pmcs=[u for u in units.items if u['kind']=='pmcs_item']
        self.assertEqual(len(pmcs),36)
        self.assertTrue(any('Metal particles are' in u['body_text'] for u in pmcs))
        self.assertTrue(any('Change fluid every 12,000 miles' in u['body_text'] for u in pmcs))
        used={p['source']['record_id'] for u in units.items for p in u['body_parts']+u['prefix_parts'] if p['kind']=='source'}
        for row in self.store.table('pmcs-structure.jsonl'):
            for key,value in row['fields'].items():
                if value.strip():self.assertIn(row['row_id']+':'+key,used)

    def test_table_pairs_are_not_column_wise_concatenation(self):
        units=Units(self.store);reviewed_tables(self.store,units)
        rows=[u for u in units.items if u['metadata'].get('table_id')=='P0272:oil-pressure']
        self.assertEqual(len(rows),5)
        stopped=next(u for u in rows if 'STOP' in u['body_text'])
        self.assertIn('ENGINE RPM: STOP',stopped['body_text'])
        self.assertIn('APPROXIMATE OIL PRESSURE: 0 PSI',stopped['body_text'])
        self.assertNotIn('2000',stopped['body_text'])


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=Application()
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(cls.app))
        cls.worker=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.worker.start()
        cls.url='http://127.0.0.1:'+str(cls.server.server_address[1])

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.worker.join(timeout=3)

    def test_health_and_page_image(self):
        with urlopen(self.url+'/api/health') as response:
            self.assertEqual(json.load(response)['application'],'kidet-corpus')
        with urlopen(self.url+'/api/page.png?page=272') as response:
            self.assertEqual(response.headers['Content-Type'],'image/png')
            self.assertEqual(response.read(8),b'\x89PNG\r\n\x1a\n')

    def test_foreign_host_and_missing_job_token_are_rejected(self):
        for request in [Request(self.url+'/api/state',headers={'Host':'attacker.invalid'}),
                        Request(self.url+'/api/build',data=b'{}',method='POST')]:
            with self.assertRaises(HTTPError) as result:urlopen(request)
            self.assertEqual(result.exception.code,403)

    def test_no_arbitrary_path_serving(self):
        with self.assertRaises(ValueError):output_path('../config.json')
        with self.assertRaises(HTTPError) as result:urlopen(self.url+'/api/page.png?page=0')
        self.assertEqual(result.exception.code,400)
        with self.assertRaises(HTTPError) as result:urlopen(self.url+'/../config.json')
        self.assertEqual(result.exception.code,404)


class CorruptionTests(unittest.TestCase):
    def test_verifier_detects_changed_text_even_if_hash_is_updated(self):
        current=read_json(PACKAGE/'config.json')
        sources=sorted((p.parent for p in (BASE/'output').glob('corpus-*/config.json')
                        if read_json(p)==current and (p.parent/'manifest.json').exists()),
                       key=lambda p:p.stat().st_mtime,reverse=True)
        if not sources:self.skipTest('Build the current input version before the corruption test')
        source=sources[0]
        from corpus.verify import verify
        self.assertEqual(verify(source)['mechanical_status'],'PASS','Corruption test requires a valid current-version fixture')
        with tempfile.TemporaryDirectory(prefix='corpus-test-') as tmp:
            copy=Path(tmp)/'result';shutil.copytree(source,copy)
            chunks=read_jsonl(copy/'chunks.jsonl')
            chunks[0]['text']='X'+chunks[0]['text'][1:]
            chunks[0]['text_sha256']=text_sha(chunks[0]['text'])
            write_jsonl(copy/'chunks.jsonl',chunks)
            manifest=read_json(copy/'manifest.json');manifest['files']['chunks.jsonl']=sha(copy/'chunks.jsonl')
            write_json(copy/'manifest.json',manifest)
            result=verify(copy)
            self.assertEqual(result['mechanical_status'],'FAIL')
            self.assertIn('WINDOW_TEXT',{e['code'] for e in result['errors']})
            self.assertIn('MAPPING_TEXT',{e['code'] for e in result['errors']})
            self.assertFalse(result['corpus_ready_for_index'])


if __name__=='__main__':unittest.main()
