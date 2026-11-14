import os
import subprocess
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent
EXE = Path('/workspace/executable')


def invoke(*args, input_bytes=None, env=None):
    child_env = os.environ.copy()
    child_env.pop('XH_CONFIG_DIR', None)
    if env:
        child_env.update({str(k): str(v) for k, v in env.items()})
    return subprocess.run([str(EXE), *map(str, args)], input=input_bytes,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=child_env)


@pytest.fixture
def server():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _reply(self, code=200, body=b'ok', headers=()):
            self.send_response(code)
            for key, value in headers:
                self.send_header(key, value)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)

        def do_GET(self):
            if self.path == '/redirect':
                self._reply(302, b'', [('Location', '/text')])
            elif self.path == '/error':
                self._reply(404, b'missing')
            elif self.path == '/json':
                self._reply(200, b'{"a":1}', [('Content-Type', 'application/json')])
            elif self.path == '/headers':
                self._reply(200, b'body', [('hello', 'Rodos')])
            else:
                self._reply(200, b'hello\n', [('Content-Type', 'text/plain')])

        def do_POST(self):
            size = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(size)
            self._reply(200, body, [('Content-Type', 'application/octet-stream')])

        def do_HEAD(self):
            self._reply(200, b'', [('Content-Type', 'text/plain')])

    httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{httpd.server_port}'
    finally:
        httpd.shutdown()
        thread.join()
        httpd.server_close()


def test_version_long_and_short():
    r = invoke('--version')
    assert (r.returncode, r.stdout, r.stderr) == (0, b'xh 0.25.3\n-native-tls +rustls\n', b'')
    r = invoke('-V')
    assert (r.returncode, r.stdout, r.stderr) == (0, b'xh 0.25.3\n', b'')


def test_concise_and_detailed_help():
    r = invoke('--help')
    assert r.returncode == 0 and not r.stderr
    assert r.stdout.startswith(b'xh is a friendly and fast tool for sending HTTP requests\n')
    assert b'Arguments:' in r.stdout and b'Options:' in r.stdout
    assert b'Run "xh help" for more complete documentation.' in r.stdout
    r = invoke('help')
    assert r.returncode == 0 and b'key:=value' in r.stdout and b'header;' in r.stdout
    assert b'exit status' not in r.stdout.lower() and b'examples' not in r.stdout.lower()


def test_help_order_and_no_git_subcommands():
    assert invoke('--help', '--bad-option').returncode == 0
    r = invoke('--bad-option', '--help')
    assert r.returncode == 2 and not r.stdout and r.stderr.startswith(b'error: unexpected argument')
    r = invoke('list')
    assert r.returncode == 2 and b'Usage:' in r.stderr


@pytest.mark.parametrize('args, expected', [
    (('--offline', '--ignore-stdin', 'GET', 'https://example.com'), b'GET / HTTP/1.1\n'),
    (('--offline', '--ignore-stdin', 'https://example.com'), b'GET / HTTP/1.1\n'),
    (('--offline', '--ignore-stdin', 'https://example.com', 'n=alice', 'age:=30'), b'POST / HTTP/1.1\n'),
    (('--offline', '--ignore-stdin', ':8000/path'), b'GET /path HTTP/1.1\n'),
])
def test_offline_url_and_method_inference(args, expected):
    r = invoke(*args)
    assert r.returncode == 0 and not r.stderr and r.stdout.startswith(expected)


def test_offline_headers_json_and_framing():
    r = invoke('--offline', '--ignore-stdin', 'https://example.com', 'name=alice', 'age:=30')
    assert r.returncode == 0
    assert b'Accept: application/json, */*;q=0.5\n' in r.stdout
    assert r.stdout.endswith(b'{"name":"alice","age":30}\n\n')


def test_json_nested_paths_and_sparse_array():
    r = invoke('--offline', '--ignore-stdin', '--print=B', 'https://example.com',
               'user[name]=Ada', 'items[0]=a', 'items[2]=c')
    assert r.returncode == 0 and r.stdout.endswith(b'{"user":{"name":"Ada"},"items":["a",null,"c"]}\n\n')


def test_json_path_error_has_context_and_caret():
    r = invoke('--offline', '--ignore-stdin', 'https://example.com', 'foo[x]extra')
    assert r.returncode == 1 and not r.stdout
    assert r.stderr == b"executable: error: expected '['\n\n  foo[x]extra\n        ^\n"


def test_form_and_query_encoding():
    r = invoke('--offline', '--ignore-stdin', '--form', '--print=HB', 'https://example.com/p?old=1',
               'q==a b&c', 'x=a b')
    assert r.returncode == 0
    assert b'POST /p?old=1&q=a+b%26c HTTP/1.1\n' in r.stdout
    assert r.stdout.endswith(b'x=a+b\n\n')


def test_curl_canonical_and_stdin_not_consumed():
    r = invoke('--curl', '--follow', 'http://example.com', input_bytes=b'ignored')
    assert (r.returncode, r.stdout, r.stderr) == (0, b'curl -L http://example.com/\n', b'')
    r = invoke('--curl', '--raw', 'hello world', 'http://example.com')
    assert r.returncode == 0 and b"-d 'hello world'" in r.stdout


def test_generated_completions_have_native_structure():
    cases = [('complete-bash', b'_executable', b'COMPREPLY'),
             ('complete-zsh', b'#compdef executable', b'--no-version'),
             ('complete-fish', b'complete -c executable', b'@'),
             ('complete-powershell', b'Register-ArgumentCompleter', b'--version'),
             ('complete-nushell', b'export extern executable', b'--version'),
             ('complete-elvish', b'arg-completer', b'--version')]
    for kind, marker, other in cases:
        r = invoke('--generate', kind)
        assert r.returncode == 0 and not r.stderr
        assert marker in r.stdout and other in r.stdout and len(r.stdout) > 1000


def test_generate_is_standalone_and_case_sensitive():
    r = invoke('--generate', 'complete-bash', 'http://example.com')
    assert r.returncode == 2 and not r.stdout and b"cannot be used with" in r.stderr
    r = invoke('--generate', 'COMPLETE-BASH')
    assert r.returncode == 2 and b'possible values:' in r.stderr


def test_live_request_returns_body_and_print_selection(server):
    r = invoke(server + '/text')
    assert r.returncode == 0 and r.stdout == b'hello\n' and not r.stderr
    r = invoke('--print=h', server + '/headers')
    assert r.returncode == 0 and r.stdout.startswith(b'HTTP/1.0 200 OK\n')
    assert b'Hello: Rodos\n' in r.stdout and r.stdout.endswith(b'\n\n')


def test_live_request_body_json_and_head(server):
    r = invoke('--print=b', 'POST', server + '/echo', 'name=alice')
    assert r.returncode == 0 and r.stdout == b'{"name":"alice"}'
    r = invoke('--print=b', 'HEAD', server + '/text')
    assert r.returncode == 0 and r.stdout == b''


def test_status_exit_codes_and_override(server):
    r = invoke(server + '/error')
    assert r.returncode == 4 and r.stdout == b'missing'
    r = invoke('--no-check-status', server + '/error')
    assert r.returncode == 0 and r.stdout == b'missing'


def test_follow_redirect_and_json_pretty(server):
    r = invoke('--follow', server + '/redirect')
    assert r.returncode == 0 and r.stdout == b'hello\n'
    r = invoke('--pretty=format', '--print=b', server + '/json')
    assert r.returncode == 0 and b'    "a": 1' in r.stdout


def test_session_initializes_and_read_only_preserves(tmp_path):
    session = tmp_path / 'state.json'
    r = invoke('--offline', '--ignore-stdin', '--session', session, 'http://example.com')
    assert r.returncode == 0 and session.exists()
    original = session.read_bytes()
    r = invoke('--offline', '--ignore-stdin', '--session-read-only', session, 'http://example.com')
    assert r.returncode == 0 and session.read_bytes() == original


def test_config_defaults_can_be_overridden(tmp_path):
    (tmp_path / 'config.json').write_text('{"default_options":["--json"]}')
    r = invoke('--offline', '--ignore-stdin', 'http://example.com', env={'XH_CONFIG_DIR': tmp_path})
    assert r.returncode == 0 and b'Accept: application/json, */*;q=0.5' in r.stdout
    r = invoke('--offline', '--ignore-stdin', '--no-json', 'http://example.com',
               env={'XH_CONFIG_DIR': tmp_path})
    assert r.returncode == 0 and b'Accept: */*\n' in r.stdout
