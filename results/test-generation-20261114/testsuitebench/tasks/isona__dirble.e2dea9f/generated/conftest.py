import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


EXE = Path('/workspace/executable')


class Site:
    def __init__(self):
        self.requests = []
        self.routes = {}
        self.lock = threading.Lock()

    def set(self, path, status=200, body=b'found', headers=()):
        self.routes[path] = (status, body, list(headers))


@pytest.fixture
def site():
    state = Site()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def do_GET(self): self.respond()
        def do_HEAD(self): self.respond()
        def do_POST(self): self.respond()

        def respond(self):
            length = int(self.headers.get('Content-Length', '0') or 0)
            request_body = self.rfile.read(length) if length else b''
            with state.lock:
                state.requests.append((self.command, self.path, dict(self.headers), request_body))
                entry = state.routes.get(self.path, (404, b'not found', []))
            status, body, headers = entry
            self.send_response(status)
            for name, value in headers:
                self.send_header(name, value)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Connection', 'close')
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state.base = f'http://127.0.0.1:{server.server_port}'
    yield state
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


@pytest.fixture
def run(tmp_path):
    def invoke(*args, cwd=None, env=None, timeout=15):
        base_env = os.environ.copy()
        base_env.update({'NO_PROXY': '*', 'no_proxy': '*', 'NO_COLOR': '1'})
        if env:
            base_env.update(env)
        return subprocess.run([str(EXE), *map(str, args)], cwd=cwd or tmp_path,
                              env=base_env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout)
    return invoke


@pytest.fixture
def wordlist(tmp_path):
    def create(contents, name='words.txt'):
        path = tmp_path / name
        path.write_text(contents, encoding='utf-8')
        return path
    return create
