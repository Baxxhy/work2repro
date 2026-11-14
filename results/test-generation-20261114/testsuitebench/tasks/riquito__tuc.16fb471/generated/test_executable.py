import os
import subprocess
from pathlib import Path

import pytest

EXE = Path('/workspace/executable')


def run(*args, data=b'', file_data=None, env=None):
    path = None
    if file_data is not None:
        path = Path(__file__).parent / 'input.tmp'
        path.write_bytes(file_data)
        args = (*args, str(path))
    e = os.environ.copy()
    e.pop('NO_COLOR', None)
    e['TERM'] = 'dumb'
    if env:
        e.update(env)
    try:
        return subprocess.run([str(EXE), *map(str, args)], input=data, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=e, timeout=15)
    finally:
        if path and path.exists():
            path.unlink()


def ok(args, inp=b'', expected=b'', **kw):
    p = run(*args, data=inp, **kw)
    assert p.returncode == 0, p.stderr
    assert p.stdout == expected
    assert p.stderr == b''


def err(args, inp=b'', message=None):
    p = run(*args, data=inp)
    assert p.returncode == 1
    assert p.stdout == b''
    if message is not None:
        assert p.stderr == message
    return p.stderr


def test_version_exact():
    ok(['--version'], expected=b'tuc 1.3.0\n')


def test_help_no_color_exact_and_help_overrides_errors():
    p = run('--help', '--unknown', 'x', '--', '-h')
    assert p.returncode == 0 and not p.stderr
    assert p.stdout.startswith(b'tuc 1.3.0\nCut text (or bytes)')
    assert all(x in p.stdout for x in [b'USAGE:', b'FLAGS:', b'OPTIONS:', b'--fields', b'--delimiter'])


def test_no_args_help_even_with_stdin():
    p = run(data=b'ignored')
    assert p.returncode == 0 and p.stdout.startswith(b'tuc') and len(p.stdout) > 100


@pytest.mark.parametrize('args,source,expected', [
    (['-d', '-', '-f', '3,2'], b'a-b-c-d', b'cb\n'),
    (['-d', '-', '-f', '3,1:2'], b'a-b-c-d', b'ca-b\n'),
    (['-d', '-', '-f', '2,2,1'], b'a-b-c-d-e', b'bba\n'),
    (['-d', '-', '-f', '-3:-1'], b'a-b-c-d-e', b'c-d-e\n'),
    (['-d', ',', '-f', '1:100'], b'a,b,c', b'a,b,c\n'),
    (['-d', '-', '-f', '1:3', '-r', ' -> '], b'a-b-c', b'a -> b -> c\n'),
    (['-d', '-', '-f', '3,2', '-j'], b'a-b-c-d', b'c-b\n'),
    (['-d', '-', '-f', '1:3', '--no-join'], b'a-b-c', b'a-b-c\n'),
])
def test_field_selection_and_join(args, source, expected):
    ok(args, source, expected)


@pytest.mark.parametrize('args,source,expected', [
    (['-d', '||', '-f', '2'], b'a||b||||c', b'b\n'),
    (['-d', ',', '-f', '1:'], b',a,,b,', b',a,,b,\n'),
    (['-d', '', '-f', '1'], b'abc', b'\n'),
    (['-d', '', '-f', '2'], b'abc', b'a\n'),
    (['-d', '', '-f', '1:'], b'abc', b'abc\n'),
    (['-d', '→', '-f', '2'], 'x→y'.encode(), b'y\n'),
])
def test_literal_delimiters(args, source, expected):
    ok(args, source, expected)


def test_records_crlf_empty_and_final_unterminated():
    ok(['-d', ':', '-f', '2'], b'a:x\r\n\na:y\r', b'x\ny\r\n')
    ok(['-d', ':', '-f', '2'], b'', b'')
    ok(['-d', ':', '-f', '2', '-s'], b'\na:x\n', b'x\n')


def test_zero_terminated_records():
    ok(['-z', '-d', '_', '-f', '2'], b'hello_world\0foo_bar', b'world\0bar\0')
    ok(['-z', '-d', '_', '-f', '1:'], b'a_b\nq_r\0', b'a_b\nq_r\0')


def test_trim_greedy_compress():
    ok(['-d', '-', '-f', '1:', '-t', 'b'], b'---a--b---c---\n', b'a--b---c\n')
    ok(['-d', ' ', '-f', '1:3', '-g', '-j'], b'a  b   c', b'a  b   c\n')
    ok(['-d', '-', '-f', '2', '-p'], b'foo---bar', b'bar\n')
    ok(['-d', '-', '-f', '1:'], b'--foo---bar--', b'-foo---bar--\n')


def test_regex_split_and_replace_and_invalid_join():
    ok(['-e', '[0-9]+', '-f', '1:'], b'a123b456c', b'abc\n')
    ok(['-e', r'\s+', '-f', '1:3', '-r', '|'], b'a  b\tc', b'a|b|c\n')
    err(['-e', '[', '-f', '1'], message=b'tuc: runtime error. The regular expression is malformed. regex parse error:\n    [\n    ^\nerror: unclosed character class\n')
    assert b'regex parse error' in err(['-e', '(abc', '-f', '1'])
    err(['-e', r'\s+', '-f', '1,2', '-j'], message=b'tuc: runtime error. Cannot use --regex and --join without --replace-delimiter\n')


def test_complement_per_part():
    ok(['-d', '-', '-f', '2', '-m'], b'a-b-c-d', b'ac-d\n')
    ok(['-d', '-', '-f', '2', '-m', '-j'], b'a-b-c-d', b'a-c-d\n')
    ok(['-c', '2,4', '-m'], b'abcde', b'acdeabce\n')
    ok(['-d', '-', '-f', '2,4', '-m', '--json'], b'a-b-c-d-e', b'["a","c","d","e","a","b","c","e"]\n')
    err(['-d', '-', '-f', '1:', '-m'], b'a-b')


def test_formats_and_escapes():
    ok(['-d', '-', '-f', '({1}, {2})'], b'a-b', b'(a, b)\n')
    ok(['-d', '-', '-f', '{{{{nested}}}} {1}'], b'a-b', b'{{nested}} a\n')
    ok(['-c', '1-{5=MISSING}'], b'ab', b'1-MISSING\n')
    ok(['-d', '-', '-f', '{1}{2}', '--json'], b'a-b', b'["a","b"]\n')


def test_fallback_oob_and_partial_output():
    ok(['-d', ' ', '-f', '1,4=NA', '--fallback-oob', 'G'], b'a b', b'aNA\n')
    ok(['-d', ' ', '-f', '1,4', '--fallback-oob='], b'a b', b'a\n')
    p = run('-d', ' ', '-f', '1,4', data=b'a b c\n')
    assert p.returncode == 1 and p.stdout == b'a' and p.stderr == b'Error: Out of bounds: 4\n'
    p = run('-d', ' ', '-f', '1,4', '-j', data=b'a b c\n')
    assert p.returncode == 1 and p.stdout == b'a ' and p.stderr == b'Error: Out of bounds: 4\n'


def test_only_delimited_and_character_exception():
    ok(['-d', ',', '-f', '2', '-s'], b'abc\na,b\nc,d', b'b\nd\n')
    ok(['-c', '1:2', '-d', ',', '-s'], b'ab\na,b\n', b'ab\na,\n')


def test_json_serialization_and_zero_records():
    ok(['-d', '/', '-f', '1,2,1:3', '--json'], b'a/b/c/d', b'["a","b","a","b","c"]\n')
    ok(['-d', ',', '-f', '1:2', '--json'], b'a"\\\n,b', b'["a\\"\\\\\\n","b"]\n')
    ok(['-d', ',', '-f', '1:', '--json'], b'\n,a,', b'\n["","a",""]\n')
    ok(['-z', '-d', '_', '-f', '1:', '--json'], b'a_b\0', b'["a","b"]\0')


def test_characters_codepoints_and_records():
    ok(['-c', '1:2'], 'e\u030acafé'.encode(), 'e\u030a\n'.encode())
    ok(['-c', '1,2,3', '-r', '-'], b'abc', b'a-b-c\n')
    ok(['-c', '1:3'], b'abc\ndef', b'abc\ndef\n')


def test_bytes_raw_stream_and_no_terminator():
    ok(['-b', '1:3'], b'abc\ndef', b'abc')
    ok(['-b', '1:4'], 'café'.encode(), b'caf\xc3')
    ok(['-b', '{1}:{5}'], b'hello', b'h:o')
    p = run('-b', '1,9=X', '--fallback-oob', 'G', data=b'abc')
    assert p.returncode == 1 and p.stdout == b'a' and p.stderr == b'Error: Out of bounds: 9\n'


def test_lines_selection_and_quirks():
    ok(['-l', '1,3'], b'a\nb\nc\n', b'a\nc\n')
    ok(['-l', '1,3', '--no-join'], b'a\nb\nc\n', b'ac\n')
    ok(['-l', '-1'], b'a\nb\nc\n', b'a\nb\nc\n')
    p = run('-l', '3,1', data=b'a\nb\nc\n')
    assert p.returncode == 1 and p.stdout == b'' and p.stderr == b'Error: Out of bounds: 3\n'


@pytest.mark.parametrize('spec,message', [
    ('X', b"failed to parse 'X': Not a number `X`\n"),
    ('0', b"failed to parse '0': Zero is not a valid field\n"),
    ('', b"failed to parse '': UserBoundsList must contain at least one UserBounds\n"),
    ('1,,2', b"failed to parse '1,,2': Field format error: empty field\n"),
    ('3:1', b"failed to parse '3:1': Field left value cannot be greater than right value\n"),
    ('{1', b"failed to parse '{1': Field format error: missing closing parenthesis\n"),
])
def test_bounds_diagnostics(spec, message):
    err(['-d', ',', '-f', spec], b'a,b', message)


def test_zero_invalid_and_incompatible_options():
    err(['-M', '0', '-f', '1'], message=b"tuc: runtime error. --fixed-memory cannot be 0\n")
    err(['-j', '--no-join'], message=b"tuc: runtime error. It's not possible to use --join and --no-join simultaneously\n")
    err(['--json', '-r', '|'], message=b'tuc: runtime error. The use of --replace with --json is not supported\n')
    err(['-p', '-b', '1'], message=b'tuc: runtime error. Delimiters can be compressed only with --fields and --lines\n')
    err(['-c', '1', '--no-join'], message=b"tuc: runtime error. Since --characters implies --join, you can't pass --no-join\n")


def test_unknown_arguments_and_value_option_missing():
    p = run('--bogus', 'file1', 'file2')
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr == b'tuc: unexpected arguments: ["--bogus", "file1", "file2"]\nTry \'tuc --help\' for more information.\n'
    p = run('--delimiter')
    assert p.returncode == 1 and p.stderr.startswith(b"the '--delimiter' option doesn't have an associated value")


def test_file_precedence_no_mmap_and_io_errors():
    ok(['-d', ',', '-f', '2', '--no-mmap'], b'wrong', b'b\n', file_data=b'a,b')
    p = run('-f', '1', '/path/definitely/missing/tuc-eval-file')
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr == b'tuc: runtime error. The file "/path/definitely/missing/tuc-eval-file" does not exist\n'
    p = run('-f', '1', '/workspace')
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr == b'tuc: runtime error. The path "/workspace" is not a file\n'


def test_fixed_memory_chunked_and_supported_quirks():
    ok(['-M', '1', '-d', '-', '-f', '2,4', '-j'], b'a-b-c-d-e\n', b'-b-d\n')
    ok(['-M', '1', '-d', '-', '-f', '2:4', '-j'], b'a-b-c-d-e\n', b'-b-c-d\n')
    ok(['-M', '1', '-d', '-', '-f', '1:'], b'a-b-c\n', b'a-b-c\n')


def test_scale_records_fields_and_long_record():
    inp = b'x\n' * 50000
    ok(['-d', ',', '-f', '1'], inp, b'x\n' * 50000)
    fields = b','.join([b'x'] * 10000)
    ok(['-d', ',', '-f', '10000'], fields, b'x\n')
    long = b'x' * (2 * 1024 * 1024)
    ok(['-d', ',', '-f', '1'], long, long + b'\n')


def test_fixed_memory_validation():
    p = run('-M', '1', '-d', '||', '-f', '1', data=b'a')
    assert p.returncode == 1 and p.stderr == b'tuc: runtime error. Delimiter must be 1 byte wide for FastOpt\n'
    p = run('-M', '1', '-d', '-', '-f', '2,1', data=b'a-b')
    assert p.returncode == 1 and p.stderr == b'tuc: runtime error. Bounds cannot be converted to ForwardBounds\n'
