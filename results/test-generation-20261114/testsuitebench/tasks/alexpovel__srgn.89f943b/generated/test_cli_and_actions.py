import os
import subprocess
from pathlib import Path

import pytest

EXE = Path('/workspace/executable')


def run(args=(), data=b'', env=None, cwd='/workspace/eval'):
    merged = os.environ.copy()
    for key in ('UPPER', 'LOWER', 'TITLECASE', 'NORMALIZE', 'SQUEEZE', 'INVERT',
                'LITERAL_STRING', 'GERMAN_PREFER_ORIGINAL', 'GERMAN_NAIVE', 'REPLACE',
                'RUST_LOG'):
        merged.pop(key, None)
    if env:
        merged.update(env)
    return subprocess.run([str(EXE), *map(str, args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=cwd, env=merged, timeout=12)


@pytest.mark.parametrize('scope,expected', [
    ('def|jkl', b'abc DEF ghi JKL mno'),
    ('[abc]', b'ABCdefABC'),
    ('^start|end$', b' middle '),
], ids=['alternation-ranges', 'all-matches', 'anchors'])
def test_regex_scopes_are_global(scope, expected):
    source = {'def|jkl': b'abc def ghi jkl mno', '[abc]': b'abcdefabc', '^start|end$': b'start middle end'}[scope]
    p = run([scope, '--upper' if scope != '^start|end$' else '--delete'], source)
    assert p.returncode == 0 and p.stdout == (expected if scope != '^start|end$' else expected)


def test_regex_unicode_dot_multiline_and_empty_match_progress():
    p = run(['(?s)a.*b', '--upper'], b'a\ndata\nb')
    assert (p.returncode, p.stdout) == (0, b'A\nDATA\nB')
    p = run(['a*', '--upper'], b'aa x a')
    assert p.returncode == 0 and p.stdout == b'AA X A'


def test_unicode_case_normalization_and_fixed_action_order():
    assert run(['--upper'], 'straße мир'.encode()).stdout == 'STRAẞE МИР'.encode()
    assert run(['--lower'], 'ẞ'.encode()).stdout == 'ß'.encode()
    assert run(['--normalize'], 'Café Việt'.encode()).stdout == b'Cafe Viet'
    assert run(['--upper', '--lower'], b'AbC').stdout == b'abc'


def test_titlecase_headline_rules():
    assert run(['--titlecase'], b'the quick brown fox jumps over the lazy dog').stdout == b'The Quick Brown Fox Jumps Over the Lazy Dog'
    assert run([r'\w+', '--titlecase'], b'hello WORLD MiXeD').stdout == b'Hello World MiXeD'


@pytest.mark.parametrize('scope,source,expected', [
    ('.', b'a.b.c\n', b'\n'),
    (r'\n', b'a\nb\n', b'ab'),
    ('a+?', b'aaaa', b'[a][a][a][a]'),
], ids=['regex-dot-delete', 'replacement-newline-scope', 'lazy-global-replace'])
def test_delete_and_replacement(scope, source, expected):
    if scope == r'\n':
        p = run([scope, '--delete'], source)
    elif scope == '.':
        p = run([scope, '--delete'], source)
    else:
        p = run([scope, '--', '[$0]'], source)
    assert p.returncode == 0 and p.stdout == expected


def test_capture_expansion_and_named_numeric_slots():
    assert run([r'(\w+) (\w+)', '--', '$2 $1'], b'foo bar').stdout == b'bar foo'
    assert run([r'(?<x>a)(b)', '--', '${x}:${2}'], b'ab').stdout == b'a:b'
    assert run(['(.)', '--', '$$$1'], b'ab').stdout == b'$a$b'


def test_literal_scope_punctuation_escapes_and_empty():
    assert run(['.*+?[]', '--literal-string', '--delete'], b'x.*+?[]y').stdout == b'xy'
    assert run([r'\t', '--literal-string', '--delete'], b'a\tb').stdout == b'ab'
    assert run(['', '--literal-string', '--delete'], b'unchanged').stdout == b'unchanged'


def test_symbol_forward_inverse_and_german_modes():
    assert run(['--symbols'], b'--> -> != <= https://a->b ->').stdout == '⟶ → ≠ ≤ https://a->b →'.encode()
    assert run(['--symbols', '--invert'], '⟶≠'.encode()).stdout == b'-->!='
    assert run(['--german'], b'Gruess Gott! Schoene Gruesse').stdout == 'Grüß Gott! Schöne Grüße'.encode()
    assert run(['--german', '--german-naive'], b'Mueller Koenig').stdout == 'Müller König'.encode()


def test_pass_through_logging_and_line_views():
    p = run([], b'a\nb', env={'RUST_LOG': 'off'})
    assert (p.returncode, p.stdout, p.stderr) == (0, b'a\nb', b'')
    p = run(['--line-numbers', 'world', '--upper'], b'hello world\nno\n')
    assert p.stdout == b'(stdin):1:6-11:hello WORLD\n(stdin):2::no\n'
    p = run(['--only-matching', 'ab', '--upper'], b'ab cd ab\nno\n')
    assert p.stdout == b'(stdin):0-2;6-8:AB cd AB\n'


def test_fail_flags_and_invalid_regex_statuses():
    assert run(['x', '--fail-any'], b'ax').returncode == 1
    assert run(['x', '--fail-none'], b'abc').returncode == 1
    p = run(['(invalid', '--upper'], b'a')
    assert p.returncode == 1 and p.stderr.startswith(b'Error: Failed building regex')
    p = run(['a', '--upper', '--upper'], b'a')
    assert p.returncode == 2 and b"cannot be used multiple times" in p.stderr


def test_version_help_and_completion():
    assert run(['--version']).stdout == b'srgn 0.14.1\n'
    p = run(['--help'])
    assert p.returncode == 0 and p.stderr == b'' and p.stdout.count(b'Usage:') == 1
    assert b'Commands:' not in p.stdout and b'Subcommands:' not in p.stdout
    for shell in ('bash', 'elvish', 'fish', 'powershell', 'zsh'):
        p = run(['--completions', shell])
        assert p.returncode == 0 and b'srgn' in p.stdout and p.stdout


def test_cli_errors_and_env_defaults():
    p = run(['--glob'])
    assert p.returncode == 2 and b"a value is required for '--glob <GLOB>'" in p.stderr
    p = run(['--stdin-detection', 'bogus'])
    assert p.returncode == 2 and b'force-unreadable' in p.stderr
    assert run([], b'a', env={'UPPER': 'true'}).stdout == b'A'
    p = run([], b'a', env={'UPPER': '1'})
    assert p.returncode == 2 and b"invalid value '1' for '--upper'" in p.stderr


def test_query_language_scopes_and_search_format():
    src = b'def hello():\n    print("hello")\n'
    p = run(['--python', 'strings'], src, env={'RUST_LOG': 'off'})
    assert p.returncode == 0 and p.stdout == b'(stdin):2:11-16:    print("hello")\n'
    p = run(['--python', 'strings', '--upper'], src)
    assert p.stdout == b'def hello():\n    print("HELLO")\n'
    p = run(['--python-query', '(string) @s', '--upper'], b'x="hi"\n')
    assert p.returncode == 0 and p.stdout == b'x="HI"\n'

