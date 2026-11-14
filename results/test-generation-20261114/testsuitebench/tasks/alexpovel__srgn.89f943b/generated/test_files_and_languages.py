import os
import subprocess
from pathlib import Path

import pytest

EXE = Path('/workspace/executable')


def call(args, data=b'', cwd='/workspace/eval', env=None):
    e = os.environ.copy()
    for key in ('RUST_LOG', 'UPPER', 'LOWER', 'REPLACE'):
        e.pop(key, None)
    e['RUST_LOG'] = 'off'
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *map(str, args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=cwd, env=e, timeout=15)


@pytest.mark.parametrize('args,source,expected', [
    (['--python', 'comments', '--upper'], b'x = 1 # note\n', b'x = 1 # NOTE\n'),
    (['--python', 'function-names', '--upper'], b'def hello():\n    pass\nhello()\n', b'def HELLO():\n    pass\nhello()\n'),
    (['--rust', 'strings', '--upper'], b'fn main() { let x = "hi"; }\n', b'fn main() { let x = "HI"; }\n'),
    (['--go', 'strings', '--upper'], b'var x = "hello"\n', b'var x = "HELLO"\n'),
    (['--c', 'strings', '--upper'], b'char *x = "hello";\n', b'char *x = "HELLO";\n'),
    (['--csharp', 'strings', '--upper'], b'class A { string x = "hello"; }', b'class A { string x = "HELLO"; }'),
    (['--typescript', 'strings', '--upper'], b'const x = "hello";\n', b'const x = "HELLO";\n'),
    (['--hcl', 'strings', '--upper'], b'x = "hello"\n', b'x = "HELLO"\n'),
], ids=['python-comment', 'python-name', 'rust-string', 'go-string', 'c-string', 'csharp-string', 'typescript-string', 'hcl-string'])
def test_prepared_language_scopes(args, source, expected):
    p = call(args, source)
    assert p.returncode == 0 and p.stdout == expected


def test_language_scopes_intersect_and_join():
    source = b'def f():\n    x = "hello"\n\n"outside"\n'
    p = call(['--python', 'def', '--python', 'strings', '--upper'], source)
    assert p.stdout == b'def f():\n    x = "HELLO"\n\n"outside"\n'
    p = call(['--python', 'function-names', '--python', 'strings', '--join-language-scopes', '--upper'], source)
    assert p.stdout == b'def F():\n    x = "HELLO"\n\n"outside"\n'


def test_custom_query_file_and_language_parse_failures(tmp_path):
    q = tmp_path / 'query.scm'
    q.write_text('(string) @capture', encoding='utf-8')
    p = call(['--python-query-file', str(q), '--upper'], b'x="hi"\n')
    assert p.returncode == 0 and p.stdout == b'x="HI"\n'
    p = call(['--typescript-query', '(function_declaration', '--upper'], b'')
    assert p.returncode == 1 and b'Query error at 1:22. Invalid syntax' in p.stderr
    p = call(['--python', 'def', '--python-query', '(comment) @c', '--upper'], b'')
    assert p.returncode == 2 and b'cannot be used with' in p.stderr


def test_file_mutation_glob_dry_run_and_mode_bits(tmp_path):
    f = tmp_path / 'a file.txt'
    f.write_bytes(b'hello world\n')
    f.chmod(0o751)
    p = call(['--glob', str(f), 'hello', '--upper'])
    assert p.returncode == 0 and p.stdout == (str(f).encode() + b'\n')
    assert f.read_bytes() == b'HELLO world\n' and f.stat().st_mode & 0o777 == 0o751
    f.write_bytes(b'hello world\n')
    p = call(['--glob', str(f), '--dry-run', '--upper'])
    assert p.returncode == 0 and f.read_bytes() == b'hello world\n'
    assert b'hello world' in p.stdout and b'HELLO WORLD' in p.stdout


def test_file_walk_hidden_invalid_utf8_and_nul(tmp_path):
    visible = tmp_path / 'visible.txt'
    hidden = tmp_path / '.hidden.txt'
    invalid = tmp_path / 'invalid.txt'
    visible.write_bytes(b'hello\0world')
    hidden.write_bytes(b'hello')
    invalid.write_bytes(b'hello\xffworld')
    p = call(['--glob', '*.txt', 'hello', '--upper'], cwd=tmp_path)
    assert p.returncode == 0 and p.stdout == b'visible.txt\n'
    assert visible.read_bytes() == b'HELLO\0world'
    assert hidden.read_bytes() == b'hello' and invalid.read_bytes() == b'hello\xffworld'
    p = call(['--glob', '*.txt', '--hidden', 'hello', '--upper'], cwd=tmp_path)
    assert b'.hidden.txt\n' in p.stdout


def test_file_detection_and_fail_no_files(tmp_path):
    f = tmp_path / 'x.txt'
    f.write_bytes(b'file')
    p = call(['--glob', str(f), '--stdin-detection', 'force-readable', '--upper'], b'stdin')
    assert p.returncode == 0 and p.stdout == b'STDIN'
    assert f.read_bytes() == b'file'
    p = call(['--glob', str(tmp_path / 'missing*'), '--fail-no-files'])
    assert p.returncode == 1 and p.stderr == b'Error: No files found\n'


def test_utf8_nul_line_endings_and_large_multi_match():
    p = call(['hello', '--upper'], b'hello\0world\r\n')
    assert p.stdout == b'HELLO\0world\r\n'
    source = b'a' * 220000
    p = call(['a', '--upper'], source)
    assert p.returncode == 0 and p.stdout == b'A' * len(source)

