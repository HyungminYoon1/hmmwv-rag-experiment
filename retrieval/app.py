"""Local HTTP adapter. Search policy and file access live in the service layer."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from urllib.parse import urlsplit, parse_qs

from .common import PACKAGE
from .service import SearchService, BusyError


def handler_for(service):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def send(self, status, value, content_type='application/json; charset=utf-8'):
            body = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def local_request(self):
            port = self.server.server_address[1]
            return self.headers.get('Host') in (f'127.0.0.1:{port}', f'localhost:{port}')

        def do_GET(self):
            if not self.local_request():
                return self.send(403, {'error': 'Local requests only'})
            parsed = urlsplit(self.path)
            params = parse_qs(parsed.query)
            route = parsed.path
            try:
                if route in ('/', '/history', '/index'):
                    return self.send(200, (PACKAGE / 'web/index.html').read_bytes(), 'text/html; charset=utf-8')
                if route in ('/app.js', '/style.css', '/favicon.svg'):
                    content_type = {'/app.js': 'text/javascript', '/style.css': 'text/css',
                                    '/favicon.svg': 'image/svg+xml'}[route]
                    return self.send(200, (PACKAGE / 'web' / route[1:]).read_bytes(), content_type + '; charset=utf-8')
                if route == '/api/health':
                    return self.send(200, {'application': 'kidet-retrieval', 'ready': service.encoder is not None})
                if route == '/api/status':
                    return self.send(200, service.status())
                if route == '/api/history':
                    return self.send(200, {'items': service.history()})
                if route == '/api/info':
                    return self.send(200, service.information())
                if route == '/api/record':
                    return self.send(200, service.record(params['id'][0]))
                if route == '/api/chunk':
                    return self.send(200, service.corpus.source(params['id'][0]))
                if route == '/api/page.png':
                    data = service.corpus.page_png(params['id'][0], int(params['page'][0]))
                    return self.send(200, data, 'image/png')
                return self.send(404, {'error': 'Not found'})
            except (ValueError, KeyError, IndexError, OSError) as exc:
                return self.send(400, {'error': str(exc)})

        def do_POST(self):
            port = self.server.server_address[1]
            allowed = (f'http://127.0.0.1:{port}', f'http://localhost:{port}')
            if (not self.local_request() or self.headers.get('X-Retrieval-Request') != '1'
                or self.headers.get('Origin') not in (None, *allowed)
                or self.headers.get('Sec-Fetch-Site') == 'cross-site'):
                return self.send(403, {'error': 'Request rejected'})
            if self.path != '/api/search':
                return self.send(404, {'error': 'Not found'})
            try:
                if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                    raise ValueError('JSON request required')
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 65536:
                    raise ValueError('Invalid request size')
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict) or set(data) != {'question'}:
                    raise ValueError('Only a question may be submitted')
                return self.send(200, service.search(data['question']))
            except BusyError as exc:
                return self.send(409, {'error': str(exc)})
            except (ValueError, KeyError, OSError) as exc:
                return self.send(400, {'error': str(exc)})
            except Exception:
                # Do not dump arbitrary exception inputs, paths or credentials to clients.
                return self.send(500, {'error': '검색 중 오류가 발생했습니다. 실행 환경을 확인해주세요.'})
    return Handler


def serve(port=8766):
    service = SearchService()
    server = ThreadingHTTPServer(('127.0.0.1', port), handler_for(service))
    server.daemon_threads = True
    def prepare():
        try:
            service.load_model()
        except Exception as exc:
            service.load_error = type(exc).__name__ + ': model initialization failed'
    threading.Thread(target=prepare, daemon=True).start()
    print(f'HMMWV search: http://127.0.0.1:{port}/', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    serve(args.port)
