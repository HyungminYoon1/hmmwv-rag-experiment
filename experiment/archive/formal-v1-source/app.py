"""Local read-only HTTP adapter. Calculations belong to runner/report services."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs
import json
from .io import BASE
from . import webdata

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get('Host') not in ('127.0.0.1:8767','localhost:8767'):
            self.send_error(403);return
        try:
            url=urlparse(self.path);args=parse_qs(url.query);kind='application/json; charset=utf-8'
            if url.path in ('/','/gold','/results'):
                data=(BASE/'web/index.html').read_bytes();kind='text/html; charset=utf-8'
            elif url.path=='/api/overview':data=json.dumps(webdata.overview(),ensure_ascii=False).encode('utf-8')
            elif url.path=='/api/gold':data=json.dumps(webdata.gold_rows(),ensure_ascii=False).encode('utf-8')
            elif url.path=='/api/run':data=json.dumps(webdata.run_data(args.get('id',[''])[0]),ensure_ascii=False).encode('utf-8')
            elif url.path=='/source':data=webdata.source_image(args.get('page',[''])[0]);kind='image/png'
            else:self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self'; frame-ancestors 'none'")
            self.end_headers();self.wfile.write(data)
        except (ValueError,FileNotFoundError,KeyError):self.send_error(404)
    def log_message(self,fmt,*args):pass

if __name__=='__main__':
    print('Experiment dashboard: http://127.0.0.1:8767/',flush=True)
    ThreadingHTTPServer(('127.0.0.1',8767),Handler).serve_forever()
