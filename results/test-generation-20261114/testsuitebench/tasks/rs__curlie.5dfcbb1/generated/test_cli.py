import json
import os
import pathlib
import subprocess
import sys
import textwrap

import pytest


ROOT = pathlib.Path(__file__).resolve().parent
EXE = pathlib.Path('/workspace/executable')
FAKE = ROOT / 'fakebin'
CAPTURE = ROOT / 'captured.json'


@pytest.fixture(autouse=True)
def fake_curl(tmp_path):
    FAKE.mkdir(exist_ok=True)
    curl = FAKE / 'curl'
    curl.write_text(textwrap.dedent('''\
        #!/usr/bin/env python3
        import json, os, sys
        with open(os.environ['CURL_CAPTURE'], 'w') as f:
            json.dump(sys.argv[1:], f)
        out = os.environ.get('CURL_STDOUT', '')
        err = os.environ.get('CURL_STDERR', '')
        sys.stdout.buffer.write(out.encode('utf-8', 'surrogatepass'))
        sys.stderr.buffer.write(err.encode('utf-8', 'surrogatepass'))
        raise SystemExit(int(os.environ.get('CURL_STATUS', '0')))
    '''))
    curl.chmod(0o755)
    yield
    CAPTURE.unlink(missing_ok=True)


def invoke(*args, stdin=b'', env=None, exe=EXE):
    e = os.environ.copy()
    e.update({'PATH': str(FAKE) + os.pathsep + e.get('PATH', ''),
              'CURL_CAPTURE': str(CAPTURE), 'HOME': str(ROOT)})
    if env:
        e.update(env)
    CAPTURE.unlink(missing_ok=True)
    p = subprocess.run([str(exe), *args], input=stdin, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, env=e, cwd=ROOT)
    argv = json.loads(CAPTURE.read_text()) if CAPTURE.exists() else None
    return p, argv


def test_internal_version_is_exact_and_does_not_call_curl():
    p, argv = invoke('version')
    assert p.returncode == 0
    assert p.stdout == b'curlie v0.0.0-LOCAL (0000-00-00T00:00:00Z)\n'
    assert argv is None


def test_version_is_special_only_as_exact_single_argument():
    p, argv = invoke('VERSION')
    assert b'curlie v0.0.0-LOCAL' not in p.stdout
    assert argv is not None and 'VERSION' in argv


def test_no_arguments_special_curl_translation():
    p, argv = invoke()
    assert argv == ['-h', 'all', '-H', 'Accept: application/json, */*']


@pytest.mark.parametrize('args,expected', [
    (('get', 'example.com'), ['-X', 'GET', 'example.com']),
    (('head', 'example.com'), ['-I', 'example.com']),
    (('post', 'example.com'), ['-X', 'POST', 'example.com']),
    (('PATCH', 'example.com'), ['-X', 'PATCH', 'example.com']),
], ids=['lower-get', 'head-special', 'post', 'patch'])
def test_method_translation(args, expected):
    p, argv = invoke(*args)
    assert argv[:len(expected)] == expected
    assert argv[-4:] == ['-s', '-S', '-d@-', '-H'] or argv[-3:] == ['-s', '-S', '-H']


def test_method_token_alone_is_forwarded_without_url():
    _, argv = invoke('POST')
    assert argv[:2] == ['-X', 'POST']
    assert 'Accept: application/json, */*' in argv


def test_url_and_automatic_defaults_and_stdin_data():
    p, argv = invoke('example.com')
    assert argv == ['example.com', '-s', '-S', '-d@-', '-H', 'Content-Type: application/json',
                    '-H', 'Accept: application/json, */*']
    assert b'http://example.com\n' in p.stderr


def test_data_items_make_sorted_compact_json():
    _, argv = invoke('POST', 'example.com', 'name=value', 'age:=25', 'x=a=b')
    assert argv[:5] == ['-X', 'POST', '-d', '{"age":25,"name":"value","x":"a=b"}', 'example.com']
    assert '-d@-' not in argv
    assert 'Content-Type: application/json' in argv


def test_json_escaping_and_typed_values():
    _, argv = invoke('example.com', 'key=a b"\\é', 'arr:=[1,true,null,{"x":-0.5}]')
    data = argv[argv.index('-d') + 1]
    assert json.loads(data) == {'arr': [1, True, None, {'x': -0.5}], 'key': 'a b"\\é'}
    assert data == json.dumps(json.loads(data), ensure_ascii=False, separators=(',', ':'), sort_keys=True)


def test_query_encoding_existing_query_and_unicode():
    _, argv = invoke('https://example.com/p?old=1', 'expr==a=b', 'query==café', 'empty==')
    assert 'https://example.com/p?old=1&expr=a%3Db&query=caf%C3%A9&empty=' in argv


def test_headers_preserve_order_and_suppress_matching_defaults():
    _, argv = invoke('example.com', 'accept:custom', 'X-A:a:b', 'ACCEPT:second', 'content-TYPE:raw')
    assert argv.count('accept:custom') == 1 and argv.count('ACCEPT:second') == 1
    assert argv.count('X-A:a:b') == 1 and argv.count('content-TYPE:raw') == 1
    assert not any(x.startswith('Accept: application') for x in argv)
    assert not any(x.startswith('Content-Type: application') for x in argv)


def test_explicit_data_flags_and_stdin_suppression():
    _, argv = invoke('example.com', '-d', 'a=b', '-d', '@file')
    assert argv[:5] == ['-d', 'a=b', '-d', '@file', 'example.com']
    assert '-d@-' not in argv


def test_empty_data_does_not_suppress_stdin_but_adds_content_type():
    _, argv = invoke('example.com', '-d', '')
    assert argv.count('-d@-') == 1
    assert argv[argv.index('-d') + 1] == ''
    assert 'Content-Type: application/json' in argv


def test_form_mode_repeats_fields_and_keeps_stdin_default():
    _, argv = invoke('-F', 'example.com', 'a=b', 'file=@x', 'name=with space')
    assert argv[:8] == ['-F', 'a=b', '-F', 'file=@x', '-F', 'name=with space', 'example.com', '-s']
    assert '-d@-' in argv and 'Content-Type: application/json' not in argv


def test_unknown_operands_retained_before_url():
    _, argv = invoke('example.com', 'path with spaces', 'baditem')
    assert argv[:2] == ['path with spaces', 'baditem']
    assert argv[2] == 'example.com'


def test_long_equals_options_remain_single_arguments():
    _, argv = invoke('--user=admin:pass', 'example.com', '--output=a.txt')
    assert argv[:3] == ['--user=admin:pass', '--output=a.txt', 'example.com']


@pytest.mark.parametrize('option,value', [
    ('-A', 'agent'), ('-b', 'cookie'), ('-c', 'jar'), ('-C', '3'), ('-D', 'headers'),
    ('-e', 'referer'), ('-E', 'cert'), ('-K', 'config'), ('-m', '2.5'), ('-o', 'out'),
    ('-r', '0-2'), ('-T', 'upload'), ('-u', 'user:pass'), ('-U', 'proxy:pass'),
    ('-w', '%{http_code}'), ('-x', 'proxy'), ('-X', 'CUSTOM'), ('-Y', '4'), ('-y', '5'),
    ('-z', 'date'), ('--connect-timeout', '2'), ('--data-binary', '@x'),
    ('--form-string', 'a=b'), ('--interface', 'lo'), ('--max-time', '3'),
    ('--resolve', 'host:80:127.0.0.1'), ('--user-agent', 'agent'),
], ids=['short-agent', 'short-cookie', 'short-cookie-jar', 'short-continue', 'short-dump-header',
       'short-referer', 'short-cert', 'short-config', 'short-max-time', 'short-output',
       'short-range', 'short-upload', 'short-user', 'short-proxy-user', 'short-write-out',
       'short-proxy', 'short-request', 'short-speed-limit', 'short-speed-time', 'short-time-cond',
       'long-connect-timeout', 'long-data-binary', 'long-form-string', 'long-interface',
       'long-max-time', 'long-resolve', 'long-user-agent'])
def test_value_options_keep_separate_values(option, value):
    _, argv = invoke(option, value, 'example.com')
    assert argv[:3] == [option, value, 'example.com']


def test_flag_options_preserve_spelling_and_order():
    flags = ['-0', '-4', '-6', '-I', '-k', '-L', '-O', '--anyauth', '--compressed',
             '--http1.1', '--http2', '--insecure', '--location', '--silent', '--tlsv1.2']
    _, argv = invoke(*flags, 'example.com')
    assert argv[:len(flags) + 1] == flags + ['example.com']


def test_symlink_basename_does_not_supply_method(tmp_path):
    link = tmp_path / 'post'
    link.symlink_to(EXE)
    _, argv = invoke('example.com', exe=link)
    assert argv == ['example.com', '-s', '-S', '-d@-', '-H', 'Content-Type: application/json',
                    '-H', 'Accept: application/json, */*']


def test_curl_version_option_is_not_internal_version():
    p, argv = invoke('--version', env={'CURL_STDOUT': 'curl 9.1\nProtocols: http\nFeatures: x\n'})
    assert argv == ['--version', '-s', '-S', '-H', 'Accept: application/json, */*']
    assert p.stdout.startswith(b'curl 9.1\n')


def test_display_url_for_non_http_scheme_uses_http_prefix():
    p, argv = invoke('--curl', 'ftp://ftp.example.com/file.txt')
    assert p.stderr == b'http://ftp://ftp.example.com/file.txt\n'
    assert 'ftp://ftp.example.com/file.txt' in p.stdout.decode()


def test_compound_short_options_expand_and_consume_attached_value():
    _, argv = invoke('-vHX:1', 'example.com')
    assert argv[:5] == ['-v', '-H', 'X:1', 'example.com', '-s']


def test_unknown_options_are_forwarded_and_options_may_follow_url():
    _, argv = invoke('example.com', '--strange', '-Lkv')
    assert argv[:5] == ['--strange', '-L', '-k', '-v', 'example.com']


def test_standalone_double_dash_makes_option_spelling_positional():
    p, argv = invoke('--curl', '--', '-s')
    assert p.stdout.startswith(b'curl ')
    assert '-s' in p.stdout.decode()


def test_url_normalization_and_display_basis():
    cases = [('//example.com:8080', 'example.com:8080', b'http://example.com:8080\n'),
             (':5000/api', 'localhost:5000/api', b'http://:5000/api\n'),
             ('http://:8080', 'http://localhost:8080', b'http://:8080\n'),
             ('http://:', 'http://localhost', b'http://:\n')]
    for url, operand, display in cases:
        p, argv = invoke('--curl', url)
        assert operand in argv
        assert p.stderr.startswith(display)


def test_http_unicode_path_encoded_but_query_retained():
    _, argv = invoke('--curl', 'https://example.com/café/東?x=%2F')
    assert 'https://example.com/caf%C3%A9/%E6%9D%B1?x=%2F' in argv


def test_dry_run_exact_default_and_no_child():
    p, argv = invoke('--curl', 'http://example.com')
    assert argv is None
    assert p.stderr == b'http://example.com\n'
    assert p.stdout == (b'curl http://example.com -s -S -d@- -H "Content-Type: application/json" '
                        b'-H "Accept: application/json, */*"\n')


def test_dry_run_method_json_and_headers():
    p, _ = invoke('--curl', 'POST', 'http://example.com', 'name=value', 'age:=25')
    assert p.stdout == (b'curl -X POST -d {"age":25,"name":"value"} http://example.com -s -S '
                        b'-H "Content-Type: application/json" -H "Accept: application/json, */*"\n')


def test_dry_run_quotes_spaces_and_escapes_quotes_and_backslashes():
    p, _ = invoke('--curl', 'example.com', 'X-Test:a b"c\\d')
    assert b'-H "X-Test:a b\\"c\\\\d"' in p.stdout


def test_pretty_is_removed_and_generated_verbose_unless_silent():
    _, argv = invoke('--pretty', 'example.com')
    assert '--pretty' not in argv and '-v' in argv
    _, argv = invoke('--pretty', '-s', 'example.com')
    assert '--pretty' not in argv and '-v' not in argv and '-s' in argv


def test_response_stream_and_curl_status_are_forwarded():
    p, _ = invoke('example.com', env={'CURL_STDOUT': 'body\x00tail', 'CURL_STDERR': 'diagnostic\n', 'CURL_STATUS': '28'})
    assert p.stdout == b'body\x00tail'
    assert p.stderr.startswith(b'http://example.com\n')
    assert p.returncode == 28


def test_curl_empty_help_output_is_not_synthesized():
    p, argv = invoke('--help', 'http')
    assert argv[:2] == ['--help', 'http']
    assert p.stdout == b''


def test_help_mixed_with_url_is_a_request():
    p, argv = invoke('http://bad.invalid', '--nonesuch', '-h')
    assert p.stderr.startswith(b'http://bad.invalid\n')
    assert argv[:3] == ['--nonesuch', '-h', 'http://bad.invalid']


def test_curl_stdout_stderr_and_failure_status_are_preserved():
    p, _ = invoke('example.com', env={'CURL_STDOUT': 'abc', 'CURL_STDERR': 'curl: (6) bad\n', 'CURL_STATUS': '6'})
    assert p.stdout == b'abc'
    assert p.stderr == b'http://example.com\ncurl: (6) bad\n'
    assert p.returncode == 6
