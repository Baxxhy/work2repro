import http.server
import socketserver
import threading
import time
from pathlib import Path

import pytest


EXE = Path('/workspace/executable')


class Site:
    def __init__(self, routes):
        self.routes = routes
        self.requests = []
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                owner.requests.append((self.path, dict(self.headers)))
                spec = owner.routes.get(self.path, (404, 'text/plain', b'not found', {}))
                if callable(spec):
                    spec = spec(self)
                status, ctype, body, *extra = spec
                self.send_response(status)
                self.send_header('Content-Type', ctype)
                for k, v in (extra[0] if extra else {}).items():
                    self.send_header(k, v)
                self.end_headers()
                if isinstance(body, str):
                    body = body.encode()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *args):
                pass

        self.server = socketserver.ThreadingTCPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_address[1]}'

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


@pytest.fixture
def site_factory():
    sites = []
    def make(routes):
        s = Site(routes)
        sites.append(s)
        return s
    yield make
    for s in sites:
        s.close()


def run(*args):
    import subprocess
    return subprocess.run([str(EXE), *map(str, args)], capture_output=True, timeout=12)


def html(body):
    return (200, 'text/html; charset=utf-8', body)
