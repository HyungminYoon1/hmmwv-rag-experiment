"""Loopback-only corpus builder and PDF source review application."""
from __future__ import annotations
from datetime import datetime
from functools import lru_cache
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import sys
import threading
from urllib.parse import parse_qs,urlsplit
import webbrowser

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from corpus.common import PACKAGE,BASE,ROOT,read_json,read_jsonl,write_json

OUTPUT_ROOT=BASE/'output'
STATIC=PACKAGE/'web'


def output_path(name):
    if not re.fullmatch(r'corpus-[A-Za-z0-9_-]{1,80}',name):
        raise ValueError('Invalid run name')
    path=(OUTPUT_ROOT/name).resolve()
    if path.parent!=OUTPUT_ROOT.resolve() or not (path/'manifest.json').is_file():
        raise ValueError('Unknown run')
    return path


@lru_cache(maxsize=3)
def load_run(name):
    path=output_path(name)
    chunks=read_jsonl(path/'chunks.jsonl')
    maps={m['chunk_id']:m for m in read_jsonl(path/'source_map.jsonl')}
    return {'path':path,'chunks':chunks,'by_id':{c['id']:c for c in chunks},'maps':maps,
            'reviews':read_jsonl(path/'review_queue.jsonl'),'pages':read_jsonl(path/'page_coverage.jsonl'),
            'audit':read_json(path/'audit.json'),'summary':read_json(path/'build_summary.json'),
            'manifest':read_json(path/'manifest.json'),'config':read_json(path/'config.json')}


class Application:
    def __init__(self):
        self.nonce=secrets.token_urlsafe(32)
        self.lock=threading.Lock()
        self.job={'running':False,'stage':'대기','percent':0}
        self.server=None

    def runs(self):
        result=[]
        for path in OUTPUT_ROOT.glob('corpus-*'):
            if not (path/'audit.json').is_file() or not (path/'manifest.json').is_file(): continue
            try:
                output_path(path.name)
                a=read_json(path/'audit.json')
                result.append({'name':path.name,'modified':path.stat().st_mtime,
                               'status':a['corpus_status'],'chunks':a['chunks']})
            except (ValueError,OSError,KeyError): continue
        return sorted(result,key=lambda r:r['modified'],reverse=True)

    def update(self,values):
        with self.lock: self.job.update(values)

    def start(self,kind,run=None):
        if kind not in ('build','verify'): raise ValueError('Unknown job')
        if kind=='verify': output_path(run or '')
        with self.lock:
            if self.job['running']: return False
            self.job={'running':True,'kind':kind,'stage':'시작','percent':0,'error':None}
        def work():
            try:
                if kind=='build':
                    from corpus.build import build
                    name='corpus-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')
                    result=build(OUTPUT_ROOT/name,self.update)
                    self.update({'run':name,'result':result['audit']})
                else:
                    from corpus.verify import verify
                    self.update({'stage':'입력·출력 독립 검증','percent':10})
                    result=verify(output_path(run))
                    report=PACKAGE/'reports'
                    report.mkdir(exist_ok=True)
                    write_json(report/('verify-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.json'),result)
                    self.update({'run':run,'result':result,'stage':'검증 완료','percent':100})
            except Exception as exc:
                self.update({'error':type(exc).__name__+': '+str(exc),'stage':'실행 오류'})
            finally:
                self.update({'running':False})
        threading.Thread(target=work,daemon=True).start()
        return True


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass

        def send(self,status,data,content_type='application/json; charset=utf-8'):
            if not isinstance(data,bytes): data=json.dumps(data,ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers();self.wfile.write(data)

        def valid_host(self):
            host=self.headers.get('Host','')
            port=self.server.server_address[1]
            return host in (f'127.0.0.1:{port}',f'localhost:{port}')

        def do_GET(self):
            if not self.valid_host(): return self.send(403,{'error':'Localhost only'})
            parsed=urlsplit(self.path);params=parse_qs(parsed.query)
            def value(k,default=''): return params.get(k,[default])[0]
            try:
                route=parsed.path
                static={p:'index.html' for p in ('/','/chunks','/reviews','/pages','/runs')}
                static.update({'/app.js':'app.js','/style.css':'style.css'})
                if route in static:
                    name=static[route];typ={'html':'text/html','js':'text/javascript','css':'text/css'}[name.split('.')[-1]]
                    return self.send(200,(STATIC/name).read_bytes(),typ+'; charset=utf-8')
                if route=='/api/state':
                    with app.lock: job=dict(app.job)
                    return self.send(200,{'runs':app.runs(),'job':job,'nonce':app.nonce})
                if route=='/api/health':
                    return self.send(200,{'application':'kidet-corpus','version':'1.0.0'})
                if route=='/api/summary':
                    from corpus.build import code_hashes
                    run=load_run(value('run'))
                    return self.send(200,{'audit':run['audit'],'summary':run['summary'],
                                         'config':run['config'],'environment':run['manifest']['environment'],
                                         'input_count':len(run['manifest']['inputs']),
                                         'code_matches':run['manifest']['code']==code_hashes()})
                if route=='/api/chunks':
                    run=load_run(value('run'));q=value('q').casefold();page=value('page');kind=value('kind')
                    rows=[c for c in run['chunks'] if (not q or q in c['text'].casefold() or q in c['id'].casefold())
                          and (not page or int(page) in c['pdf_pages']) and (not kind or c['kind']==kind)]
                    offset=max(0,int(value('offset','0')));limit=min(100,max(1,int(value('limit','50'))))
                    return self.send(200,{'total':len(rows),'items':[{
                        k:c[k] for k in ('id','kind','pdf_pages','token_count','review_ids')}
                        | {'preview':c['text'][:180]} for c in rows[offset:offset+limit]]})
                if route=='/api/chunk':
                    run=load_run(value('run'));cid=value('id')
                    c=run['by_id'][cid]
                    return self.send(200,{'chunk':c,'mapping':run['maps'][cid],
                                         'reviews':[r for r in run['reviews'] if r['id'] in c['review_ids']]})
                if route=='/api/reviews':
                    run=load_run(value('run'));q=value('q').casefold();page=value('page');code=value('code')
                    rows=[r for r in run['reviews'] if (not q or q in (r['id']+' '+r['detail']+' '+r['code']).casefold())
                          and (not page or r['pdf_page']==int(page)) and (not code or r['code']==code)]
                    offset=max(0,int(value('offset','0')))
                    return self.send(200,{'total':len(rows),'items':rows[offset:offset+50]})
                if route=='/api/pages':
                    run=load_run(value('run'));page=value('page')
                    rows=[p for p in run['pages'] if not page or p['pdf_page']==int(page)]
                    offset=max(0,int(value('offset','0')))
                    return self.send(200,{'total':len(rows),'items':rows[offset:offset+50]})
                if route=='/api/source':
                    run=load_run(value('run'));part=run['maps'][value('id')]['parts'][int(value('part'))]
                    source=part['source'];rid=source['record_id']
                    # Only named, pinned source records are returned. No arbitrary file reads.
                    records={r['id']:r for r in read_jsonl(BASE/'output/corrected-v4-a/units-before.jsonl')}
                    raw=records[rid]['text']
                    return self.send(200,{'source':source,'before_spans':[raw[s['start']:s['end']] for s in source['raw_spans']]})
                if route=='/api/page.png':
                    import pymupdf
                    pn=int(value('page'));boxes=[]
                    if not 1<=pn<=890: raise ValueError('Invalid PDF page')
                    if value('id'):
                        run=load_run(value('run'));mapping=run['maps'][value('id')]['parts']
                        if value('part'):
                            mapping=[mapping[int(value('part'))]]
                        boxes=[b for p in mapping if p['kind']=='source' and p['source']['pdf_page']==pn for b in p['source']['bboxes']]
                    pdf=ROOT/read_json(PACKAGE/'config.json')['source_pdf']
                    with pymupdf.open(pdf) as doc:
                        page=doc[pn-1]
                        for box in boxes:
                            page.draw_rect(pymupdf.Rect(box),color=(.85,.2,.08),width=.8,overlay=True)
                        data=page.get_pixmap(dpi=130,alpha=False).tobytes('png')
                    return self.send(200,data,'image/png')
                return self.send(404,{'error':'Not found'})
            except (ValueError,KeyError,IndexError,OSError) as exc:
                return self.send(400,{'error':str(exc)})

        def do_POST(self):
            if not self.valid_host() or not secrets.compare_digest(self.headers.get('X-Corpus-Token',''),app.nonce):
                return self.send(403,{'error':'Request rejected'})
            origin=self.headers.get('Origin')
            if origin and origin not in (f'http://127.0.0.1:{self.server.server_address[1]}',f'http://localhost:{self.server.server_address[1]}'):
                return self.send(403,{'error':'Origin rejected'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<=size<=2048: raise ValueError('Invalid request size')
                data=json.loads(self.rfile.read(size) or b'{}')
                if self.path=='/api/shutdown':
                    with app.lock: running=app.job['running']
                    if running: return self.send(409,{'error':'생성·검증 작업이 끝난 뒤 종료해주세요.'})
                    self.send(200,{'stopping':True})
                    threading.Thread(target=self.server.shutdown,daemon=True).start()
                    return
                if self.path not in ('/api/build','/api/verify'): return self.send(404,{'error':'Not found'})
                started=app.start(self.path.rsplit('/',1)[1],data.get('run'))
                return self.send(202 if started else 409,{'started':started})
            except (ValueError,OSError) as exc:
                return self.send(400,{'error':str(exc)})
    return Handler


def serve(port=8765,open_browser=False):
    app=Application()
    server=ThreadingHTTPServer(('127.0.0.1',port),make_handler(app));app.server=server
    url=f'http://127.0.0.1:{server.server_address[1]}/'
    print('Corpus app: '+url,flush=True)
    if open_browser: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=8765)
    p.add_argument('--open',action='store_true');a=p.parse_args();serve(a.port,a.open)
