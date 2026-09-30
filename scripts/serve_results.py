"""Serve the preserved dashboard on a chosen loopback port without an LLM."""
import argparse
import json
from http.server import ThreadingHTTPServer
import sys
from urllib.parse import urlparse, parse_qs
from artifact_io import ROOT

sys.path.insert(0, str(ROOT))
from experiment.app import Handler
import results_data


def make_server(port):
    class ViewHandler(Handler):
        def do_GET(self):
            actual = self.server.server_address[1]
            if self.headers.get('Host') not in (f'127.0.0.1:{actual}', f'localhost:{actual}'):
                self.send_error(403)
                return
            url = urlparse(self.path)
            args = parse_qs(url.query)
            try:
                kind = 'application/json; charset=utf-8'
                if url.path in ('/', '/gold', '/results', '/evaluation'):
                    name = 'evaluation.html' if url.path == '/evaluation' else 'index.html'
                    data = (ROOT / 'scripts/web' / name).read_bytes()
                    kind = 'text/html; charset=utf-8'
                elif url.path == '/api/evaluation':
                    data = json.dumps(results_data.evaluation_overview(), ensure_ascii=False).encode('utf-8')
                elif url.path == '/api/evaluation-run':
                    data = json.dumps(results_data.evaluation_run(args.get('id', [''])[0]), ensure_ascii=False).encode('utf-8')
                elif url.path == '/api/overview':
                    data = json.dumps(results_data.overview(), ensure_ascii=False).encode('utf-8')
                elif url.path == '/api/gold':
                    data = json.dumps(results_data.gold_rows(args.get('version', [None])[0]), ensure_ascii=False).encode('utf-8')
                else:
                    self.headers.replace_header('Host', '127.0.0.1:8767')
                    super().do_GET()
                    return
            except (ValueError, FileNotFoundError, KeyError):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)
    return ThreadingHTTPServer(('127.0.0.1', port), ViewHandler)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', type=int, default=8767)
    args = p.parse_args()
    if not 1 <= args.port <= 65535:
        p.error('Port must be between 1 and 65535')
    with make_server(args.port) as server:
        print(f'Results: http://127.0.0.1:{args.port}/evaluation', flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
