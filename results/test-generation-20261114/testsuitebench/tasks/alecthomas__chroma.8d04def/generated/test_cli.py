import json
import os
import pathlib
import subprocess
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent
EXE = pathlib.Path('/workspace/executable')


def run(args=(), data=b'', cwd=None):
    return subprocess.run([str(EXE), *map(str, args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=cwd, timeout=45)


def safe(b):
    return repr(b)


def ok(p):
    assert p.returncode == 0, f'exit={p.returncode} stdout={safe(p.stdout)} stderr={safe(p.stderr)}'
    assert not p.stderr, f'unexpected stderr={safe(p.stderr)}'


def toks(args, data):
    p = run(['--json', *args], data)
    ok(p)
    return json.loads(p.stdout)


def test_empty_inputs_and_json_layout():
    p = run(['--json'], b'')
    ok(p)
    assert p.stdout == b'[\n\n]\n'
    for fmt in ('terminal', 'noop'):
        p = run(['-f', fmt], b'')
        ok(p)
        assert p.stdout == b''


def test_help_and_version():
    p = run(['--version'])
    ok(p)
    assert p.stdout == b'?-?-?\n'
    p = run(['--help'])
    ok(p)
    assert p.stdout.startswith(b'Usage: executable [<files> ...] [flags]\n')
    assert b'--html-highlight=N[:M][,...]' in p.stdout


def test_python_builtin_and_json_escaping():
    t = toks(['-l', 'python'], b'print("hello")')
    assert [(x['type'], x['value']) for x in t] == [
        ('NameBuiltin', 'print'), ('Punctuation', '('), ('LiteralStringDouble', '"hello"'), ('Punctuation', ')')]
    t = toks(['-l', 'python'], b'x = "<&>"\r\n')
    assert ''.join(x['value'] for x in t) == 'x = "<&>"\n'
    p = run(['--json', '-l', 'python'], b'x = "<&>"')
    ok(p)
    assert b'\\u003c' in p.stdout and b'\\u0026' in p.stdout and b'\\u003e' in p.stdout


def test_go_keyword_and_trace_records():
    p = run(['--json', '-l', 'go', '--trace'], b'package main\n')
    assert p.returncode == 0, f'exit={p.returncode} stdout={safe(p.stdout)} stderr={safe(p.stderr)}'
    values = json.loads(p.stdout)
    assert [(x['type'], x['value']) for x in values] == [
        ('KeywordNamespace', 'package'), ('TextWhitespace', ' '), ('NameOther', 'main'), ('TextWhitespace', '\n')]
    rows = [json.loads(x) for x in p.stderr.splitlines()]
    assert len(rows) == 4
    assert [r['pos'] for r in rows] == [0, 7, 8, 12]
    assert all(list(r) == ['lexer', 'state', 'rule', 'pattern', 'pos', 'length', 'elapsedMs'] for r in rows)
    assert all(isinstance(r['elapsedMs'], (int, float)) for r in rows)


def test_file_order_concatenation_json_and_prevalidation(tmp_path):
    a, b = tmp_path / 'a.py', tmp_path / 'b.go'
    a.write_text('print(1)', encoding='utf-8')
    b.write_text('package main\n', encoding='utf-8')
    p = run(['--json', str(a), str(b)])
    ok(p)
    # One complete formatter result per file, with no headings or separators.
    assert p.stdout.count(b'[\n') == 2
    assert p.stdout.endswith(b']\n[\n') is False
    missing = tmp_path / 'missing'
    p = run([str(a), str(missing)])
    assert p.returncode == 80 and p.stdout == b''
    assert p.stderr == f'executable: error: [<files> ...]: stat {missing}: no such file or directory\n'.encode()


def test_autodetect_filename_hints_and_fail_mode():
    assert toks(['--filename', 'x.py'], b'def f(): pass')[0]['type'] == 'Keyword'
    # Unknown text falls back in lenient mode and fails silently in strict mode.
    p = run(['--json'], b'random text without clear language')
    ok(p)
    assert ''.join(x['value'] for x in json.loads(p.stdout)) == 'random text without clear language'
    p = run(['--fail'], b'random text without clear language')
    assert p.returncode == 1 and p.stdout == p.stderr == b''
    p = run(['--fail', '--filename', 'x.py', '--json'], b'arbitrary bytes')
    ok(p)


def test_explicit_unknown_lexer_plaintext_and_fail():
    p = run(['--json', '-l', 'not-a-lexer'], b'plain')
    ok(p)
    assert ''.join(x['value'] for x in json.loads(p.stdout)) == 'plain'
    p = run(['--fail', '-l', 'not-a-lexer'], b'plain')
    assert p.returncode == 1 and not p.stdout and not p.stderr


def test_normalization_unicode_controls_and_long_line():
    source = ('漢字🙂e\u0301\x00\x01\rX\r\n' + 'a' * 100000).encode()
    t = toks(['-l', 'text'], source)
    value = ''.join(x['value'] for x in t)
    assert value == source.decode().replace('\r\n', '\n').replace('\r', '\n')
    assert len(value) == len(source.decode().replace('\r\n', '\n').replace('\r', '\n'))


def test_terminal_exact_truecolor_and_unbuffered():
    expected = (b'\x1b[38;2;102;217;239mdef\x1b[0m'
                b'\x1b[38;2;248;248;242m \x1b[0m'
                b'\x1b[38;2;166;226;46mfunc\x1b[0m'
                b'\x1b[38;2;248;248;242m():\x1b[0m'
                b'\x1b[38;2;248;248;242m \x1b[0m'
                b'\x1b[38;2;102;217;239mpass\x1b[0m')
    a = run(['-f', 'terminal16m', '-l', 'python', '-s', 'monokai'], b'def func(): pass')
    ok(a)
    assert a.stdout == expected
    b = run(['--unbuffered', '-f', 'terminal16m', '-l', 'python', '-s', 'monokai'], b'def func(): pass')
    ok(b)
    assert a.stdout == b.stdout


def test_html_escape_lines_links_and_highlight():
    p = run(['--html', '-l', 'text', '--html-only', '--html-lines', '--html-linkable-lines',
             '--html-base-line', '200', '--html-highlight', '201'], b'<&"\nsecond')
    ok(p)
    out = p.stdout
    assert b'&#34;' in out and b'&lt;' in out and b'&amp;' in out
    assert b'href="#L200"' in out and b'href="#L201"' in out
    assert b'class="line hl"' in out
    assert b'200' in out and b'201' in out


def test_html_tab_width_fragment_invariant_and_table():
    args = ['--html', '-l', 'text', '--html-only']
    p1 = run([*args, '--html-tab-width', '1'], b'a\tb')
    p100 = run([*args, '--html-tab-width', '100'], b'a\tb')
    ok(p1); ok(p100)
    assert p1.stdout == p100.stdout and b'a\tb' in p1.stdout
    p = run(['--html', '-l', 'text', '--html-lines', '--html-lines-table'], b'a\nb')
    ok(p)
    assert b'<table class="lntable">' in p.stdout and p.stdout.count(b'<td class="lntd">') == 2


def test_bad_highlight_range_diagnostic():
    p = run(['--html', '--html-highlight', '1:2:3'], b'x')
    assert p.returncode == 1
    assert p.stderr == b'executable: error: range should be N[:M], not "1:2:3"\n'


def test_invalid_formatter_parser_status():
    p = run(['-f', 'notreal'], b'x')
    assert p.returncode == 80
    assert p.stderr == (b'executable: error: --formatter must be one of "html","json","noop","svg","terminal","terminal16","terminal16m","terminal256","terminal8","tokens" but got "notreal"\n')
    assert p.stdout == b''


def test_check_reports_all_go_error_tokens_and_stdin_ignores_check(tmp_path):
    f = tmp_path / 'bad.go'
    f.write_bytes(b'package main\nvar x = "')
    p = run(['--check', str(f)])
    ok(p)
    assert p.stdout.startswith(str(f).encode() + b':2:8 ')
    assert p.stdout.endswith(b'"\\\""\n')
    p = run(['--check', '--json', '-l', 'text'], b'hello')
    ok(p)
    assert json.loads(p.stdout)[0]['value'] == 'hello'


def test_svg_document_dimensions_and_escaping():
    p = run(['--svg', '-l', 'text'], b'a\tb\n')
    ok(p)
    assert p.stdout.startswith(b'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE svg')
    assert b'<svg width="56px"' in p.stdout
    assert b'&#160;&#160;&#160;&#160;' in p.stdout and p.stdout.endswith(b'</svg>\n')


def test_xml_export_basics_and_existing_dir(tmp_path):
    p = run(['--xml', str(tmp_path)])
    assert p.returncode == 0, f'exit={p.returncode} stderr={safe(p.stderr)}'
    assert len(list(tmp_path.glob('*.xml'))) == 280
    py = tmp_path / 'python.xml'
    raw = py.read_bytes()
    assert len(raw) == 20449 and raw.startswith(b'<lexer>\n') and raw.endswith(b'</lexer>')
    assert py.stat().st_mode & 0o777 == 0o600
    root = ET.fromstring(raw)
    assert root.findtext('./config/name') == 'Python'
    assert [x.text for x in root.findall('./config/alias')] == ['python', 'py']
    assert any('Go' in x and 'not serialisable' in x for x in p.stderr.decode().splitlines())
    p2 = run(['--xml', str(tmp_path)])
    assert p2.returncode == 0 and len(p2.stderr.splitlines()) == 284


def test_xml_missing_directory(tmp_path):
    d = tmp_path / 'absent'
    p = run(['--xml', str(d)])
    assert p.returncode != 0
    assert p.stderr == f'executable: error: --xml: stat {d}: no such file or directory\n'.encode()
