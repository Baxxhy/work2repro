import os
import subprocess
import time
import threading
import http.server
import socketserver
from pathlib import Path

import pytest

EXE = Path('/workspace/executable')
ESC = b'\x1b'
HELP = (b'Usage: jplot [OPTIONS] FIELD_SPEC [FIELD_SPEC...]:\n\n'
        b'OPTIONS:\n'
        b'  -interval duration\n'
        b'    \tWhen url is provided, defines the interval between fetches. Note that counter fields are computed based on this interval. (default 1s)\n'
        b'  -rows int\n'
        b'    \tLimits the height of the graph output.\n'
        b'  -steps int\n'
        b'    \tNumber of values to plot. (default 100)\n'
        b'  -url string\n'
        b'    \tURL to fetch every second. Read JSON objects from stdin if not specified.\n\n'
        b'FIELD_SPEC: [<option>[,<option>...]:]path\n'
        b'  option:\n'
        b'    - counter: Computes the difference with the last value. The value must increase monotonically.\n'
        b'    - marker: When the value is none-zero, a vertical line is drawn.\n'
        b'  path:\n'
        b'    JSON field path (eg: field.sub-field).\n')


def run(args=(), *, data=b'', env=None, timeout=4):
    e = os.environ.copy()
    e.pop('TERM_PROGRAM', None)
    e.update({'TERM': 'xterm', 'NO_COLOR': '1'})
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *args], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=e, timeout=timeout)


def iterm():
    return {'TERM_PROGRAM': 'iTerm.app'}


def test_help_bytes_and_streams():
    p = run(['--help'])
    assert p.returncode == 0
    assert p.stdout == ESC + b'[c'
    assert p.stderr == HELP
    assert len(p.stdout + p.stderr) == 704


@pytest.mark.parametrize('flag', ['-h', '--help'], ids=['short-help', 'long-help'])
def test_help_aliases(flag):
    p = run([flag])
    assert (p.returncode, p.stdout, p.stderr) == (0, ESC + b'[c', HELP)


def test_help_precedes_unknown_flag():
    p = run(['--help', '--not-a-flag'])
    assert (p.returncode, p.stdout, p.stderr) == (0, ESC + b'[c', HELP)


def test_help_after_terminator_is_positional():
    p = run(['--', '--help'])
    assert p.returncode == 1
    assert p.stdout == ESC + b'[cjplot:  iTerm2, Kitty, or DRCS Sixel graphics required'
    assert p.stderr == b''


def test_graphics_gate_default():
    p = run(['value'], data=b'{"value":1}\n')
    assert p.returncode == 1
    assert p.stdout == ESC + b'[cjplot:  iTerm2, Kitty, or DRCS Sixel graphics required'
    assert p.stderr == b''


def test_graphics_gate_precedes_missing_arguments():
    p = run([])
    assert p.returncode == 1
    assert p.stdout == ESC + b'[cjplot:  iTerm2, Kitty, or DRCS Sixel graphics required'
    assert p.stderr == b''


@pytest.mark.parametrize('term_program', ['iterm.app', 'ITERM.APP', 'iTerm2', ' iTerm.app', 'iTerm.app ', 'WezTerm', 'vscode', 'RandomTerminal'], ids=['lowercase','uppercase','iterm2','leading-space','trailing-space','wezterm','vscode','random'])
def test_only_exact_iterm_is_graphics_capability(term_program):
    p = run(['value'], env={'TERM_PROGRAM': term_program})
    assert p.returncode == 1
    assert p.stdout == ESC + b'[cjplot:  iTerm2, Kitty, or DRCS Sixel graphics required'
    assert p.stderr == b''


def test_exact_iterm_rejects_screen():
    p = run(['value'], env={**iterm(), 'TERM': 'screen'})
    assert (p.returncode, p.stdout, p.stderr) == (1, b'jplot:  screen and tmux not supported\n', b'')


@pytest.mark.parametrize('term', ['screen-256color', 'tmux'], ids=['screen-color','tmux'])
def test_screen_check_is_exact(term):
    p = run(['value'], env={**iterm(), 'TERM': term})
    assert p.returncode == 1
    assert p.stdout.startswith(b'jplot:  Cannot get window size:')
    assert p.stderr == b''


def test_missing_fields_prints_help_after_graphics_gate():
    p = run([], env=iterm())
    assert p.returncode == 1
    assert p.stdout == b''
    assert p.stderr == HELP


@pytest.mark.parametrize('arg,expected', [
    ('--invalid-flag', b'flag provided but not defined: -invalid-flag\n'),
    ('-invalid-flag', b'flag provided but not defined: -invalid-flag\n'),
    ('--url', b'flag needs an argument: -url\n'),
    ('-steps', b'flag needs an argument: -steps\n'),
    ('--rows', b'flag needs an argument: -rows\n'),
    ('-interval', b'flag needs an argument: -interval\n'),
])
def test_flag_parser_errors(arg, expected):
    p = run([arg])
    assert p.returncode == 2
    assert p.stdout == ESC + b'[c'
    assert p.stderr == expected + HELP


@pytest.mark.parametrize('arg', ['--invalid-flag', '-steps'], ids=['unknown-after-iterm','missing-after-iterm'])
def test_flag_errors_under_iterm_have_no_probe(arg):
    p = run([arg], env=iterm())
    assert p.returncode == 2
    assert p.stdout == b''


@pytest.mark.parametrize('value', ['invalid', 'notaduration', '2x'], ids=['invalid','word','unknown-unit'])
def test_invalid_duration(value):
    p = run(['--interval', value])
    assert p.returncode == 2
    assert p.stdout == ESC + b'[c'
    assert p.stderr.startswith(f'invalid value "{value}" for flag -interval: parse error\n'.encode())
    assert p.stderr.endswith(HELP)


@pytest.mark.parametrize('flag,value', [
    ('steps','abc'), ('steps','notanumber'), ('steps','5.5'),
    ('rows','abc'), ('rows','5.5')], ids=['steps-word','steps-text','steps-decimal','rows-word','rows-decimal'])
def test_invalid_integer_flags(flag, value):
    p = run([f'--{flag}={value}'])
    assert p.returncode == 2
    assert p.stdout == ESC + b'[c'
    assert p.stderr.startswith(f'invalid value "{value}" for flag -{flag}: parse error\n'.encode())
    assert p.stderr.endswith(HELP)


def test_integer_overflow_reason():
    p = run(['--steps=10000000000000000000'])
    assert p.returncode == 2
    assert p.stderr.startswith(b'invalid value "10000000000000000000" for flag -steps: value out of range\n')


@pytest.mark.parametrize('duration', ['1ns','1us','100ms','500ms','1s','2m','1h','1h30m','24h','-1s','-5s','0s','0'], ids=['ns','us','100ms','500ms','second','minutes','hour','compound','day','negative-one','negative-five','zero-s','zero'])
def test_duration_forms_are_accepted_by_flag_parser(duration):
    # A later invalid field option proves parsing got beyond duration validation.
    p = run(['--interval', duration, ':x'], env=iterm())
    assert p.returncode == 1
    assert p.stdout == b'jplot:  Cannot parse spec:  invalid field option: \n'
    assert p.stderr == b''


@pytest.mark.parametrize('flag,value', [
    ('steps','0'), ('steps','-3'), ('steps','999999999'),
    ('rows','0'), ('rows','-2'), ('rows','999999999')], ids=['steps-zero','steps-negative','steps-large','rows-zero','rows-negative','rows-large'])
def test_signed_and_large_integers_parse(flag, value):
    p = run([f'--{flag}={value}', ':x'], env=iterm())
    assert p.returncode == 1
    assert p.stdout == b'jplot:  Cannot parse spec:  invalid field option: \n'


@pytest.mark.parametrize('spec,option', [
    (':field',''), ('bad:field','bad'), ('invalid1,invalid2:field','invalid1'),
    ('Counter:field','Counter'), ('counter,:field',''), (' counter:field',' counter'),
    ('counter ,marker:field','counter '), ('COUNTER:field','COUNTER')], ids=['empty-option','unknown','first-invalid','uppercase','empty-option-member','leading-space','padded','uppercase-all'])
def test_invalid_field_options(spec, option):
    p = run([spec], env=iterm())
    assert p.returncode == 1
    assert p.stdout == f'jplot:  Cannot parse spec:  invalid field option: {option}\n'.encode()
    assert p.stderr == b''


def test_option_validation_precedes_data_read():
    p = run(['unknown:field'], data=b'not json\n', env=iterm())
    assert p.returncode == 1
    assert p.stdout == b'jplot:  Cannot parse spec:  invalid field option: unknown\n'


def test_empty_url_falls_back_to_stdin():
    p = run(['--url=', 'x'], data=b'{"x":1}\n', env=iterm())
    assert p.returncode == 1
    assert p.stdout.startswith(b'jplot:  Cannot get window size:')


def test_stdin_tty_without_url_reports_source_error():
    # stdin is a pipe in this test, so valid empty input reaches the final render gate.
    p = run(['x'], data=b'', env=iterm())
    assert p.returncode == 1
    assert p.stdout.startswith(b'jplot:  Cannot get window size:')


@pytest.mark.parametrize('payload,expected', [
    (b'{', b'jplot:  Data source error:  input error: unexpected end of JSON input'),
    (b'{"x":', b'jplot:  Data source error:  input error: unexpected end of JSON input'),
    (b'{"x":1,}\n', b'jplot:  Data source error:  input error: invalid character \'\'\' looking for beginning of object key string'),
    (b'{"y":1}\n', b'jplot:  Data source error:  cannot get x: x does not exist.'),
    (b'{"x":"hi"}\n', b'jplot:  Data source error:  invalid type x: string'),
    (b'{"x":true}\n', b'jplot:  Data source error:  invalid type x: bool'),
    (b'{"outer":2}\n', b'jplot:  Data source error:  cannot get outer.value: value is not an object. map[]'),
    (b'12\n', b'jplot:  Data source error:  cannot get x: x is not an object. map[]'),
], ids=['incomplete-object','incomplete-value','trailing-comma','missing','string-leaf','bool-leaf','primitive-parent','primitive-root'])
def test_stdin_json_and_extraction_errors(payload, expected):
    p = run(['x' if b'outer' not in payload else 'outer.value'], data=payload, env=iterm())
    assert p.returncode == 1
    assert p.stdout == expected
    assert p.stderr == b''


def test_data_errors_precede_terminal_size():
    p = run(['x'], data=b'{"x":"bad"}\n', env=iterm())
    assert p.returncode == 1
    assert p.stdout == b'jplot:  Data source error:  invalid type x: string'


def test_all_graphs_are_extracted():
    p = run(['x', 'y'], data=b'{"x":1}\n', env=iterm())
    assert p.returncode == 1
    assert p.stdout == b'jplot:  Data source error:  cannot get y: y does not exist.'


def test_blank_line_is_not_skipped():
    p = run(['x'], data=b'\n{"x":1}\n', env=iterm())
    assert p.returncode == 1
    assert p.stdout.startswith(b'jplot:  Data source error:')


def test_scanner_limit_rejects_long_line():
    payload = b'{"x":1,"padding":"' + b'a' * 200000 + b'"}\n'
    p = run(['x'], data=payload, env=iterm(), timeout=8)
    assert p.returncode == 1
    assert p.stdout == b'jplot:  Data source error:  input error: bufio.Scanner: token too long'


def test_scanner_accepts_65535_bytes_before_lf():
    # Padding keeps the line valid JSON while reaching the scanner boundary.
    prefix = b'{"x":1,"p":"'
    suffix = b'"}'
    payload = prefix + b'a' * (65535 - len(prefix) - len(suffix)) + suffix + b'\n'
    p = run(['x'], data=payload, env=iterm())
    assert p.returncode == 1
    assert p.stdout.startswith(b'jplot:  Cannot get window size:')


def test_scanner_rejects_65536_bytes_before_lf():
    prefix = b'{"x":1,"p":"'
    suffix = b'"}'
    payload = prefix + b'a' * (65536 - len(prefix) - len(suffix)) + suffix + b'\n'
    p = run(['x'], data=payload, env=iterm())
    assert p.returncode == 1
    assert p.stdout == b'jplot:  Data source error:  input error: bufio.Scanner: token too long'


def test_multiple_records_and_final_record_without_newline():
    p = run(['x'], data=b'{"x":1}\n{"x":2}', env=iterm())
    assert p.returncode == 1
    assert p.stdout.startswith(b'jplot:  Cannot get window size:')


def test_nested_unicode_and_non_identifier_paths_are_preserved():
    p = run(['outer.雪 key.0'], data='{"outer":{"雪 key":{"0":-1.25e2}}}\n'.encode(), env=iterm())
    assert p.returncode == 1
    assert p.stdout.startswith(b'jplot:  Cannot get window size:')
    assert p.stderr == b''


def test_duplicate_paths_are_allowed():
    p = run(['x+x', 'x'], data=b'{"x":0}\n', env=iterm())
    assert p.returncode == 1
    assert p.stdout.startswith(b'jplot:  Cannot get window size:')


def test_empty_path_is_syntactically_accepted():
    p = run(['counter:'], data=b'{"":1}\n', env=iterm())
    assert p.returncode == 1
    assert p.stdout.startswith(b'jplot:  Data source error:') or p.stdout.startswith(b'jplot:  Cannot get window size:')


def test_stdin_tty_requires_source():
    master, slave = __import__('pty').openpty()
    try:
        proc = subprocess.Popen([str(EXE), 'x'], stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env={**os.environ, 'TERM_PROGRAM':'iTerm.app', 'TERM':'xterm'})
        os.close(slave)
        out, err = proc.communicate(timeout=4)
        assert proc.returncode == 1
        assert out == b'jplot:  neither --url nor stdin is provided\n'
        assert err == b''
    finally:
        os.close(master)


class Handler(http.server.BaseHTTPRequestHandler):
    requests = 0
    body = b'{"value":1}'
    status = 200
    def do_GET(self):
        type(self).requests += 1
        self.send_response(type(self).status)
        self.send_header('Content-Length', str(len(type(self).body)))
        self.end_headers()
        self.wfile.write(type(self).body)
    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    Handler.requests = 0
    srv = socketserver.TCPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{srv.server_address[1]}/data'
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=2)


def test_http_invalid_url_exact_error():
    p = run(['--url=not-a-url', 'value'], env=iterm())
    assert p.returncode == 1
    assert p.stdout == b'jplot:  Data source error:  input error: Get "not-a-url": unsupported protocol scheme ""'


def test_http_connection_refused_exact_error():
    p = run(['--url=http://127.0.0.1:9999/data', 'value'], env=iterm(), timeout=5)
    assert p.returncode == 1
    assert p.stdout == b'jplot:  Data source error:  input error: Get "http://127.0.0.1:9999/data": dial tcp 127.0.0.1:9999: connect: connection refused'


def test_http_reads_json_body_and_ignores_stdin(server):
    Handler.body = b'{"value":1}'
    p = run(['--url', server, 'value'], data=b'not json\n', env=iterm())
    assert p.returncode == 1
    assert p.stdout.startswith(b'jplot:  Cannot get window size:')
    assert Handler.requests >= 1


def test_http_poll_interval_100ms(server):
    Handler.body = b'{"value":1}'
    proc = subprocess.Popen([str(EXE), '--url', server, '--interval=100ms', 'value'], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env={**os.environ, 'TERM_PROGRAM':'iTerm.app', 'TERM':'xterm'})
    try:
        time.sleep(0.8)
        proc.terminate()
        out, err = proc.communicate(timeout=4)
        assert Handler.requests >= 5
        assert proc.returncode == 1
        assert out == b'jplot:  Cannot get window size: inappropriate ioctl for device\n' or out == b'jplot:  Cannot get window size:  inappropriate ioctl for device\n'
        assert err == b''
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=2)


def test_url_last_repeated_value_takes_effect(server):
    Handler.body = b'{"value":1}'
    p = run(['--url=http://127.0.0.1:9999/ignored', '--url='+server, 'value'], data=b'not json\n', env=iterm())
    assert p.returncode == 1
    assert p.stdout.startswith(b'jplot:  Cannot get window size:')
    assert Handler.requests >= 1


def test_http_status_does_not_replace_json_decode_error(server):
    Handler.status = 500
    Handler.body = b'<html>failure</html>'
    p = run(['--url='+server, 'value'], env=iterm())
    assert p.returncode == 1
    assert p.stdout == b"jplot:  Data source error:  input error: invalid character '<' looking for beginning of value"
    Handler.status = 200


def test_options_stop_at_first_positional():
    p = run(['value', '--not-real'], data=b'{"value":1}\n', env=iterm())
    assert p.returncode == 1
    assert p.stdout.startswith(b'jplot:  Data source error:') or p.stdout.startswith(b'jplot:  Cannot get window size:')
    assert p.stderr == b''


def test_equals_and_separate_option_forms_reach_spec_validation():
    for args in (['-steps','10','-rows','0','-interval','500ms',':x'],
                 ['--steps=10','--rows=0','--interval=500ms',':x']):
        p = run(args, env=iterm())
        assert p.returncode == 1
        assert p.stdout == b'jplot:  Cannot parse spec:  invalid field option: \n'


def test_field_legacy_option_spelling_reaches_extraction():
    p = run(['marker:counter:x'], data=b'{"x":1}\n', env=iterm())
    assert p.returncode == 1
    assert p.stdout.startswith(b'jplot:  Cannot get window size:')


def test_bare_counter_is_path_not_option():
    p = run(['counter'], data=b'{"counter":1}\n', env=iterm())
    assert p.returncode == 1
    assert p.stdout.startswith(b'jplot:  Cannot get window size:')


def test_many_graph_arguments_and_fields_are_not_limited():
    fields = [f'f{i}' for i in range(20)]
    graphs = [f'f{i}' for i in range(50)]
    obj = '{' + ','.join(f'"f{i}":{i}' for i in range(50)) + '}'
    p = run(['+'.join(fields), *graphs], data=(obj+'\n').encode(), env=iterm(), timeout=8)
    assert p.returncode == 1
    assert p.stdout.startswith(b'jplot:  Cannot get window size:')
