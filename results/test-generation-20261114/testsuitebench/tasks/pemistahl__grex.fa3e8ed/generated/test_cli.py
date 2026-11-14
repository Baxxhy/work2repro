import os
import subprocess
from pathlib import Path

import pytest

BIN = Path('/workspace/executable')


def run(*args, input_bytes=None):
    return subprocess.run([str(BIN), *args], input=input_bytes, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd='/tmp', timeout=20)


def ok(args, expected, input_bytes=None):
    p = run(*args, input_bytes=input_bytes)
    assert p.returncode == 0, (p.returncode, p.stderr)
    assert p.stdout == expected.encode('utf-8')
    assert p.stderr == b''


def err(args, status, contains=None, input_bytes=None):
    p = run(*args, input_bytes=input_bytes)
    assert p.returncode == status
    assert p.stdout == b''
    if contains is not None:
        assert contains.encode() in p.stderr


@pytest.mark.parametrize('args,want', [
    (['foo'], '^foo$\n'),
    (['foo','foa'], '^fo[ao]$\n'),
    (['a','b','c'], '^[a-c]$\n'),
    (['hello','world'], '^(?:hello|world)$\n'),
    ([''], '^$\n'),
    (['abc','abd'], '^ab[cd]$\n'),
    (['abc','bc'], '^a?bc$\n'),
    (['abc','ab'], '^abc?$\n'),
    (['abcdef','abcxyz'], '^abc(?:def|xyz)$\n'),
    (['defabc','xyzabc'], '^(?:def|xyz)abc$\n'),
    (['xa','xb','ya','yb'], '^[xy][ab]$\n'),
    (['bar','foo'], '^(?:bar|foo)$\n'),
    (['test','testing','tester','tested'], '^test(?:ing|e[dr])?$\n'),
    (['a.b','a*c','a+d'], '^a(?:\\*c|\\+d|\\.b)$\n'),
    (['test[0]','test[1]'], '^test\\[[01]\\]$\n'),
])
def test_canonical_core(args, want):
    ok(args, want)


def test_deterministic_and_deduplicated():
    ok(['foo','bar','foo'], '^(?:bar|foo)$\n')
    ok(['bar','foo'], '^(?:bar|foo)$\n')


def test_literal_hyphens_and_positional_parser():
    ok(['--no-such-flag'], '^\\-\\-no\\-such\\-flag$\n')
    ok(['-a'], '^\\-a$\n')
    ok(['-x','foo','--no-anchors'], '(?x)\n^\n  (?:\n    --no\\-anchors\n    |\n    foo\n  )\n$\n')
    ok(['-x','--no-anchors','foo'], '(?x)\n  foo\n')
    ok(['--','-x'], '^\\-x$\n')


def test_value_options_and_bool_value_error():
    ok(['--min-repetitions=1','foo'], '^foo$\n')
    err(['--no-start-anchor=foo'], 2, 'unexpected value')


def test_input_required_and_conflict_diagnostics():
    err([], 2, 'the following required arguments were not provided')
    p = run()
    assert p.stderr.decode() == "error: the following required arguments were not provided:\n  --file <FILE>\n  <INPUT>...\n\nUsage: grex [OPTIONS] {INPUT...|--file <FILE>}\n\nFor more information, try '--help'.\n"
    err(['--file','/tmp/no-such-grex-input','foo'], 2, "cannot be used with '[INPUT]...'")
    err(['--file'], 2, "a value is required for '--file <FILE>'")


def test_stdin_and_line_splitting():
    ok(['-'], '^(?:bar|foo)$\n', b'foo\nbar\n')
    ok(['-'], '^line\\rwith\\rcarriage\\rreturns$\n', b'line\rwith\rcarriage\rreturns\n')
    ok(['-'], '^foo$\n', b'foo')
    ok(['-'], '^(?:alpha|beta)$\n', b'alpha\r\nbeta\r\n')


def test_empty_dedup_and_whitespace_preservation():
    ok(['','a',''], '^a$\n')
    ok(['',''], '^$\n')
    ok(['a  b'], '^a  b$\n')
    ok(['\ta\t'], '^\\ta\\t$\n')


def test_file_inputs_and_file_dash():
    d = Path('/workspace/eval'); f = d/'cases.txt'; name = d/'filename.txt'
    f.write_bytes(b'alpha\n\nbeta\n')
    name.write_text(str(f)+'\n', encoding='utf-8')
    ok(['--file',str(f)], '^(?:alph|bet)a$\n')
    ok(['-f',str(f)], '^(?:alph|bet)a$\n')
    ok(['--file','-'], '^(?:alph|bet)a$\n', str(name).encode()+b'\n')
    blank = d/'blank.txt'; blank.write_bytes(b'\n\n')
    ok(['-f',str(blank)], '^$\n')


def test_file_errors_and_zero_bytes():
    err(['-f','/tmp/grex-does-not-exist-xyz'], 1, 'error: the specified file could not be found')
    p = run('-f','/workspace')
    assert p.returncode != 0 and p.stdout == b'' and b'error: ' in p.stderr
    f = Path('/workspace/eval/empty'); f.write_bytes(b'')
    p = run('-f',str(f)); assert p.returncode == 101 and b'No test cases have been provided' in p.stderr
    p = run('-', input_bytes=b''); assert p.returncode == 101 and b'No test cases have been provided' in p.stderr
    err(['-'], 1, input_bytes=b'\xff')


def test_version_help_and_precedence():
    ok(['--version'], 'grex 1.4.6\n')
    ok(['-x','--version','foo'], 'grex 1.4.6\n')
    p = run('--help'); assert p.returncode == 0 and not p.stderr
    h = p.stdout.decode()
    assert h.startswith('grex ') and 'grex generates regular expressions from user-provided test cases.' in h
    assert 'Usage: grex [OPTIONS] {INPUT...|--file <FILE>}' in h
    for heading in ['Input:','Digit Options:','Whitespace Options:','Word Options:','Escaping Options:','Repetition Options:','Anchor Options:','Display Options:','Miscellaneous Options:']:
        assert heading in h
    for opt in ['-f, --file <FILE>','-d, --digits','-D, --non-digits','-s, --spaces','-S, --non-spaces','-w, --words','-W, --non-words','-e, --escape','--with-surrogates','-r, --repetitions','--min-repetitions','--min-substring-length','--no-start-anchor','--no-end-anchor','--no-anchors','-x, --verbose','-c, --colorize','-i, --ignore-case','-g, --capture-groups','-h, --help','-v, --version']:
        assert opt in h


def test_unicode_and_escaping():
    ok(['café','café'], '^caf(?:é|é)$\n')
    ok(['日本語'], '^日本語$\n')
    ok(['--escape','café'], '^caf\\u{e9}$\n')
    ok(['--escape','😀'], '^\\u{1f600}$\n')
    ok(['--escape','--with-surrogates','😀'], '^\\u{d83d}\\u{de00}$\n')
    ok(['--escape','y̆'], '^y\\u{306}$\n')
    err(['--with-surrogates','x'], 2, "--escape")
    ok(['a\\b'], '^a\\\\b$\n')
    ok(['test.txt'], '^test\\.txt$\n')


def test_shorthand_conversions_and_precedence():
    cases = [
        (['--digits','123','456','789'], '^\\d\\d\\d$\n'),
        (['--digits','١٢٣','٤٥٦'], '^\\d\\d\\d$\n'),
        (['--non-digits','abc'], '^\\D\\D\\D$\n'),
        (['--non-digits','123'], '^123$\n'),
        (['--spaces','hello world'], '^hello\\sworld$\n'),
        (['--spaces','  '], '^\\s\\s$\n'),
        (['--non-spaces','a b c'], '^\\S \\S \\S$\n'),
        (['--words','test123'], '^\\w\\w\\w\\w\\w\\w\\w$\n'),
        (['--non-words','abc'], '^abc$\n'),
        (['--digits','--words','abc123'], '^\\w\\w\\w\\d\\d\\d$\n'),
        (['--spaces','--non-digits','a b','1 2'], '^(?:1\\s2|\\D\\s\\D)$\n'),
        (['--words','--non-digits','abc','123'], '^\\w\\w\\w$\n'),
    ]
    for args,want in cases: ok(args,want)


def test_repetitions_and_thresholds():
    for args,want in [
        (['--repetitions','ababab'], '^(?:ab){3}$\n'),
        (['--repetitions','aaabbbccc'], '^a{3}b{3}c{3}$\n'),
        (['--repetitions','--digits','123456789'], '^\\d{9}$\n'),
        (['--repetitions','abab','ababab'], '^(?:ab){2,3}$\n'),
        (['--repetitions','--min-repetitions','3','aaa'], '^aaa$\n'),
        (['--repetitions','--min-repetitions','3','aaaa'], '^a{4}$\n'),
        (['--repetitions','--min-substring-length','2','ababab'], '^(?:ab){3}$\n'),
        (['--repetitions','--min-substring-length','3','ababab'], '^ababab$\n'),
    ]: ok(args,want)
    err(['--min-repetitions','0','foo'],2,'Value must not be zero')
    err(['--min-substring-length','0','foo'],2,'Value must not be zero')
    err(['--min-repetitions','nope','foo'],2,'Value is not a valid unsigned integer')
    err(['--min-repetitions','-1','foo'],2,'Value is not a valid unsigned integer')
    ok(['--min-repetitions','1000000000','foo'], '^foo$\n')


def test_anchors_case_and_capture():
    for args,want in [
        (['--no-start-anchor','foo'],'foo$\n'),(['--no-end-anchor','foo'],'^foo\n'),
        (['--no-anchors','foo'],'foo\n'),(['--no-start-anchor','--no-end-anchor','foo'],'foo\n'),
        (['--no-anchors',''],'\n'),(['--ignore-case','Hello','HELLO','hello'],'(?i)^hello$\n'),
        (['--ignore-case','İSTANBUL'],'(?i)^İSTANBUL$\n'),
        (['--capture-groups','bar','foo'],'^(bar|foo)$\n'),
        (['--capture-groups','abc','ab'],'^abc?$\n'),
        (['--ignore-case','--no-anchors','Hello'],'(?i)hello\n'),
    ]: ok(args,want)


def test_verbose_layout():
    ok(['--verbose','foo','foa'], '(?x)\n^\n  fo[ao]\n$\n')
    ok(['--verbose','abc','def'], '(?x)\n^\n  (?:\n    abc\n    |\n    def\n  )\n$\n')
    ok(['--verbose','--capture-groups','a','ab','abc'], '(?x)\n^\n  a\n  (\n    bc?\n  )?\n$\n')
    ok(['--verbose','--no-anchors','test'], '(?x)\n  test\n')
    ok(['--verbose','--no-anchors',''], '(?x)\n  \n')
    ok(['--verbose','--ignore-case','Hello','WORLD'], '(?ix)\n^\n  (?:\n    hello\n    |\n    world\n  )\n$\n')


def test_colorization():
    esc='\x1b['; reset=esc+'0m'
    ok(['--colorize','foo'], esc+'1;33m^'+reset+'foo'+esc+'1;33m$'+reset+'\n')
    ok(['--colorize','abc','def'], esc+'1;33m^'+reset+esc+'1;32m(?:'+reset+'abc'+esc+'1;31m|'+reset+'def'+esc+'1;32m)'+reset+esc+'1;33m$'+reset+'\n')


def test_scale_and_long_inputs():
    s='a'*10240
    ok([s], '^'+s+'$\n')
    args=['x'+str(i) for i in range(500)]
    p=run(*args)
    assert p.returncode == 0 and p.stderr == b'' and p.stdout.endswith(b'\n')
