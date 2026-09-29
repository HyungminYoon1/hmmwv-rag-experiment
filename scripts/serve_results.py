"""Serve the preserved dashboard on a chosen loopback port without an LLM."""
import argparse
from http.server import ThreadingHTTPServer
import sys
from artifact_io import ROOT

sys.path.insert(0, str(ROOT))
from experiment.app import Handler


def make_server(port):
    class ViewHandler(Handler):
        def do_GET(self):
            actual = self.server.server_address[1]
            if self.headers.get('Host') not in (f'127.0.0.1:{actual}', f'localhost:{actual}'):
                self.send_error(403)
                return
            # The original adapter validates port 8767. Only this validated local
            # transport header changes; its data services and files stay intact.
            self.headers.replace_header('Host', '127.0.0.1:8767')
            super().do_GET()
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
