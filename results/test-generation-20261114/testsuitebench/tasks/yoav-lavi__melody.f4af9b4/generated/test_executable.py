import os
import re
import subprocess
from pathlib import Path

import pytest

E = Path('/workspace/executable')
ROOT = E.parent


def run(*args, input=None, cwd=None, env=None):
    e = os.environ.copy()
    e.pop('CLICOLOR_FORCE', None)
    e.pop('NO_COLOR', None)
    if env:
        e.update(env)
    return subprocess.run([str(E), *map(str, args)], input=input, text=True,
                          capture_output=True, cwd=cwd or ROOT, env=e, timeout=8)


def compile_src(src, expected, *args):
    p = run(*args, input=src)
    assert p.returncode == 0
    assert p.stdout == expected + '\n'
    assert p.stderr == ''


@pytest.mark.parametrize('src,out', [
    ('', ''), ('   \n\t', ''), ('// only comment\n', ''), ('/*a\n b*/', ''),
    ('"#"; some of <word>;', r'#\w+'),
    ('5 to 10 of "a"; <space>; option of "b"; 2 of <digit>; either { "foo"; "bar"; "baz"; }', r'a{5,10} b?\d{2}(?:foo|bar|baz)'),
    ('"a"; "b"; <digit>;', r'ab\d'),
    ('"[](){}*+?|^$.";', r'\[\]\(\)\{\}\*\+\?\|\^\$\.'),
    (r'"hello \'quoted\'";', "hello 'quoted'"),
    (r'"hello \"quoted\"";', 'hello "quoted"'),
    (r'"\\";', r'\\'),
    (r'2 of "\n";', r'\n{2}'),
    ('"café 😀 مرحبا 日本語";', 'café 😀 مرحبا 日本語'),
    ('`[a-z]+`;', '[a-z]+'), ('`(?=[a-z])`;', '(?=[a-z])'),
    ('a to z; 0 to 9; ! to /; A to A;', '[a-z][0-9][!-/][A-A]'),
    ('not START to END;', '[^START-END]'),
    ('<start>; <end>; <char>; <whitespace>; <newline>; <tab>; <return>; <feed>; <null>; <digit>; <word>; <vertical>; <alphabetic>; <alphanumeric>; <space>; <boundary>; <backspace>;', r'^$ .\s\n\t\r\f\0\d\w\v[a-zA-Z][a-zA-Z0-9] \b[\b]'),
    ('not <whitespace>; not <newline>; not <tab>; not <return>; not <feed>; not <null>; not <digit>; not <word>; not <vertical>; not <alphabetic>; not <alphanumeric>; not <space>; not <boundary>; not <backspace>;', r'\S[^\n][^\t][^\r][^\f][^\0]\D\W[^\v][^a-zA-Z][^a-zA-Z0-9][^ ][^\B][^\b]'),
    ('<category::letter>; not <category::number>;', r'\p{L}\P{N}'),
    ('5 of <category::letter>; 3 of not <category::number>;', r'\p{L}{5}\P{N}{3}'),
    ('match { "a"; "b"; } capture { "x"; } capture _Name { "y"; }', '(?:ab)(x)(?<_Name>y)'),
    ('either { "a"; "b"; "c"; }', '(?:a|b|c)'),
    ('either { match { "a"; "b"; } "c"; }', '(?:(?:ab)|c)'),
    ('either { either { "a"; "b"; } "c"; }', '(?:(?:a|b)|c)'),
    ('ahead { some of "a"; <digit>; } not ahead { "b"; } behind { "x"; } not behind { "y"; }', r'(?=a+\d)(?!b)(?<=x)(?<!y)'),
    ('0 of "a"; 1 of "b"; 7 to 7 of "c"; 0 to 5 of "d"; over 5 of "e";', 'a{0}b{1}c{7,7}d{0,5}e{6,}'),
    ('lazy some of "a"; lazy any of "b"; lazy option of "c"; lazy 5 of "d"; lazy over 5 of "e"; lazy 5 to 6 of "f";', 'a+?b*?c??d{5}?e{6,}?f{5,6}?'),
    ('3 of "abc"; some of capture { "a"; } capture { some of "a"; }', '(?:abc){3}(a)+(a+)'),
    ('3 of match { 5 of "A"; 0 to 9; }', '(?:A{5}[0-9]){3}'),
    ('capture email { some of a to z; "@"; some of a to z; "."; 2 to 4 of a to z; }', r'(?<email>[a-z]+@[a-z]+\.[a-z]{2,4})'),
    ('some of not 0 to 9; any of not a to z;', '[^0-9]+[^a-z]*'),
])
def test_compile_behavior(src, out):
    compile_src(src, out)


@pytest.mark.parametrize('src,out', [
    ('let .x = { "first"; } .x; let .x = { "second"; } .x;', 'firstsecond'),
    ('let .a = { "x"; } let .b = { .a; "y"; } .b .a;', 'xyx'),
    ('let .x = { some of "a"; } capture c { .x; } either { .x; "b"; } ahead { .x; }', '(?<c>a+)(?:a+|b)(?=a+)'),
])
def test_variables(src, out): compile_src(src, out)


def test_file_input_path_stdin_and_cwd(tmp_path):
    f = tmp_path / 'source.unusual'
    f.write_text('"é";', encoding='utf-8')
    p = run(str(f), cwd='/')
    assert (p.returncode, p.stdout, p.stderr) == (0, 'é\n', '')
    p = run('-', input='"stdin";')
    assert (p.returncode, p.stdout, p.stderr) == (0, 'stdin\n', '')


def test_output_overwrites_without_newline(tmp_path):
    f = tmp_path / 'out.regex'; f.write_text('old trailing data')
    p = run('-o', f, input='"new";')
    assert (p.returncode, p.stdout, p.stderr, f.read_bytes()) == (0, '', '', b'new')


def test_output_missing_parent_fails(tmp_path):
    f = tmp_path / 'missing' / 'x'
    p = run('-o', f, input='"a";')
    assert p.returncode == 74 and p.stdout == '' and p.stderr == f'Error: {f}\n'
    assert not f.parent.exists()


@pytest.mark.parametrize('args,code,needle', [
    (('--unknown',), 2, "unexpected argument '--unknown'"),
    (('a', 'b'), 2, 'unexpected argument'),
    (('--output',), 2, "a value is required for '--output <OUTPUT_FILE_PATH>'"),
    (('--test',), 2, "a value is required for '--test <test>'"),
    (('-t', 'x', '-t', 'y'), 2, "cannot be used multiple times"),
    (('-t', 'x', '-f', 'f'), 2, "cannot be used with"),
    (('-t', 'x', '-o', 'f'), 2, "cannot be used with"),
])
def test_argument_errors(args, code, needle):
    p = run(*args)
    assert p.returncode == code and p.stdout == '' and needle in p.stderr


def test_help_and_version_exact():
    p = run('--help'); assert p.returncode == 0 and p.stderr == ''
    assert p.stdout.startswith('A CLI wrapping the Melody language compiler\n\nUsage: executable [OPTIONS] [INPUT_FILE_PATH]\n')
    assert p.stdout.endswith('  -V, --version                             Print version\n')
    assert run('-h').stdout == p.stdout
    p = run('--version'); assert (p.returncode, p.stdout, p.stderr) == (0, 'melody_cli 0.20.0\n', '')
    assert run('-V').stdout == 'melody_cli 0.20.0\n'


@pytest.mark.parametrize('src,msg', [
    ('<bogus>;', 'unrecognized symbol'), ('<foo::bar>;', 'unrecognized symbol namespace'),
    ('<category::bogus>;', 'unrecognized unicode category'), ('.x;', 'uninitialized variable'),
    ('not <start>;', 'negative start not allowed'), ('not <end>;', 'negative end not allowed'),
    ('not <char>;', 'negative char not allowed'), ('9 to 2 of "x";', 'invalid quantifier range'),
    ('2 of <start>;', 'unexpected special symbol in quantifier'),
    ('some of ahead { "a"; }', 'unexpected assertion in quantifier'),
    ('let .x = { "x"; } 2 of .x;', 'unexpected variable invocation in quantifier'),
    ('2 of let .x = { "x"; }', 'unexpected skipped node in quantifier'),
])
def test_semantic_errors(src, msg):
    p = run(input=src)
    assert p.returncode == 65 and p.stdout == '' and msg in p.stderr


@pytest.mark.parametrize('src,position,expectation', [
    ('some of', '1:8', 'literal, raw'), ('5 of', '1:5', 'literal, raw'),
    ('some of some of "a";', '1:9', 'literal, raw'), ('lazy lazy some of "a";', '1:6', 'amount, some'),
    ('over abc of "a";', '1:6', 'amount'), ('capture 123 { "a"; }', '1:9', 'block or identifier'),
    ('match NAME { "a"; }', '1:7', 'block'), ('either NAME { "a"; }', '1:8', 'block'),
    ('match test { "a"; }', '1:7', 'block'),
])
def test_syntax_diagnostics(src, position, expectation):
    p = run(input=src)
    assert p.returncode == 65 and p.stdout == ''
    assert f'Error:  --> {position}\n' in p.stderr and f'= expected {expectation}' in p.stderr


@pytest.mark.parametrize('src', ['"a";//tail', '"unterminated', '`unterminated', 'some of "a"', 'lazy "a";', 'lazy lazy some of "a";', 'not "x";'])
def test_invalid_syntax_is_rejected(src):
    p = run(input=src)
    assert p.returncode == 65 and p.stdout == '' and p.stderr.startswith('Error:  --> ')


@pytest.mark.parametrize('src,hay,expected', [
    ('"hello";', 'hello world', "'hello worl...' matched"),
    ('<start>; "hello"; <end>;', 'hello world', "'hello worl...' did not match"),
    ('"x";', 'x', "'x' matched"), ('"x";', 'y', "'y' did not match"),
    ('option of "a";', 'bbb', "'bbb' matched"),
    ('2 to 4 of "a";', 'aaaaa', "'aaaaa' matched"),
    ('"x";', 'aaaaaaaaaa', "'aaaaaaaaaa' did not match"),
    ('"x";', 'aaaaaaaaaaa', "'aaaaaaaaaa..." + "' did not match"),
    ('"é";', 'é', "'é' matched"),
])
def test_string_test_mode(src, hay, expected):
    p = run('--test', hay, input=src)
    assert (p.returncode, p.stdout, p.stderr) == (0, expected + '\n', '')


def test_test_file_reads_all_and_reports_path(tmp_path):
    f = tmp_path / 'test data.txt'; f.write_text('prefix\n😀target\n' + 'x' * 25000, encoding='utf-8')
    p = run('--test-file', f, input='"target";')
    assert (p.returncode, p.stdout, p.stderr) == (0, f'{f} matched\n', '')
    p = run('-f', f, input='"missing";')
    assert p.returncode == 0 and p.stdout == f'{f} did not match\n'


@pytest.mark.parametrize('path,code', [('/nonexistent/melody-file', 65), ('/proc/version', 65)])
def test_source_read_errors(path, code):
    p = run(path)
    assert p.returncode == code and p.stdout == '' and p.stderr == f'Error: unable read file at path {path}\n'


def test_test_file_read_error():
    p = run('--test-file', '/nonexistent/test-file', input='"x";')
    assert p.returncode == 74 and p.stdout == '' and p.stderr == 'Error: unable read file at path /nonexistent/test-file\n'


@pytest.mark.parametrize('shell', ['bash', 'zsh', 'fish', 'elvish', 'powershell'], ids=['bash','zsh','fish','elvish','powershell'])
def test_completion_scripts(shell):
    p = run('--generate-completions', shell)
    assert p.returncode == 0 and p.stderr == '' and p.stdout.endswith('\n')
    assert 'melody' in p.stdout and '--test-file' in p.stdout


def test_unknown_completion():
    p = run('--generate-completions', 'Bash')
    assert (p.returncode, p.stdout, p.stderr) == (0, '', "Unknown or unsupported shell: 'Bash'\nTry one of: 'bash', 'zsh', 'fish', 'elvish', 'powershell'\n\n")


def test_flags_can_follow_source_and_double_dash_ends_options(tmp_path):
    f = tmp_path / 'src'; f.write_text('"x";')
    p = run(str(f), '--test', 'x')
    assert (p.returncode, p.stdout, p.stderr) == (0, "'x' matched\n", '')
    q = tmp_path / '--help'; q.write_text('"ok";')
    p = run('--', str(q))
    assert (p.returncode, p.stdout, p.stderr) == (0, 'ok\n', '')
    p = run('--', '--help')
    assert p.returncode == 65 and p.stdout == ''


def test_long_inputs_and_output(tmp_path):
    literal = 'a' * 1200
    p = run(input='"' + literal + '";')
    assert p.returncode == 0 and p.stdout == literal + '\n'
    f = tmp_path / 'large'; src = 'either {' + ''.join('"x";' for _ in range(100)) + '}'
    p = run('-o', f, input=src)
    assert p.returncode == 0 and len(f.read_text()) > 100 and '\n' not in f.read_text()
    p = run(input='999999 of "x";')
    assert p.returncode == 0 and p.stdout == 'x{999999}\n'
