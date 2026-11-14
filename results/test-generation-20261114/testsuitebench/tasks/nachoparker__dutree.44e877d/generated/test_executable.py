import os
import re
import subprocess
from pathlib import Path

import pytest


EXE = Path('/workspace/executable')


def run(args=(), cwd=None, env=None):
    e = os.environ.copy()
    e.pop('LS_COLORS', None)
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd, env=e,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def decoded(p):
    return p.stdout.decode('utf-8', 'replace')


def header(out):
    return out.splitlines()[0]


def row_names(out):
    return [line[3:].split(' ', 1)[0] for line in out.splitlines()[1:] if '├─ ' in line or '└─ ' in line]


def test_help_and_version(tmp_path):
    a = run(['--help'], tmp_path)
    b = run(['-h'], tmp_path)
    assert a.returncode == b.returncode == 0
    assert a.stdout == b.stdout and not a.stderr and not b.stderr
    assert a.stdout.decode().splitlines()[0] == f'Usage: {EXE} [options] <path> [<path>..]'
    assert a.stdout.endswith(b'print version number\n')
    assert not a.stdout.endswith(b'\n\n')
    for opt in ('-v', '--version'):
        p = run([opt], tmp_path)
        assert (p.returncode, p.stdout, p.stderr) == (0, b'dutree version 0.2.18\n', b'')


@pytest.mark.parametrize('args,diagnostic', [
    (['--nope'], b"Unrecognized option: 'nope'"),
    (['-z'], b"Unrecognized option: 'z'"),
    (['-d1', '--depth=2'], b"Option 'depth' given more than once"),
    (['-a', '--aggr=1K'], b"Option 'aggr' given more than once"),
    (['-s', '--summary'], b"Option 'summary' given more than once"),
    (['-u', '--usage'], b"Option 'usage' given more than once"),
    (['-b', '--bytes'], b"Option 'bytes' given more than once"),
    (['-f', '--files-only'], b"Option 'files-only' given more than once"),
    (['-H', '--no-hidden'], b"Option 'no-hidden' given more than once"),
    (['-A', '--ascii'], b"Option 'ascii' given more than once"),
    (['-x'], b"Argument to option 'x' missing"),
])
def test_parser_errors(args, diagnostic, tmp_path):
    p = run(args, tmp_path)
    assert p.returncode == 1 and diagnostic in p.stderr
    assert p.stdout.startswith(b'Usage: ')
    assert p.stdout.endswith(b'print version number\n')


def test_help_parses_all_tokens_before_action(tmp_path):
    p = run(['--help', '--', '--nope'], tmp_path)
    assert p.returncode == 1 and b"Unrecognized option: 'nope'" in p.stderr
    assert p.stdout.startswith(b'Usage: ')


def test_path_validation_atomic_and_broken_link(tmp_path):
    good = tmp_path / 'good'
    good.write_text('x')
    missing = tmp_path / 'missing'
    (tmp_path / 'broken').symlink_to('absent')
    for bad in (missing, tmp_path / 'broken'):
        p = run([good, bad], tmp_path)
        assert p.returncode == 1 and p.stdout == b''
        assert f"path {bad} doesn't exist\n".encode() == p.stderr


def test_default_path_and_names_and_collection(tmp_path):
    (tmp_path / 'z').write_bytes(b'x' * 5)
    (tmp_path / 'a').write_bytes(b'y' * 2)
    p = run(['-b', '.'], tmp_path)
    assert p.returncode == 0 and not p.stderr
    assert header(decoded(p)).startswith(f'[ {tmp_path.name} ')
    names = row_names(decoded(p))
    assert names.index('z') < names.index('a')
    assert header(decoded(run(['-d0', '-b'], tmp_path))).startswith(f'[ {tmp_path.name} ')
    c = run(['-b', 'a', 'z'], tmp_path)
    assert header(decoded(c)).startswith('[ <collection> ')
    assert row_names(decoded(c))[:2] == ['z', 'a']


def test_depth_tree_and_cutoff_recursive_bytes(tmp_path):
    d = tmp_path / 'dir'
    (d / 'sub').mkdir(parents=True)
    (d / 'sub' / 'leaf').write_bytes(b'12345')
    full = run(['-b', d], tmp_path)
    shallow = run(['-d1', '-b', d], tmp_path)
    zero = run(['-d0', '-b', d], tmp_path)
    assert 'leaf' in decoded(full) and 'leaf' not in decoded(shallow)
    assert 'sub' in decoded(shallow) and 'sub' not in decoded(zero)
    assert header(decoded(full)) == header(decoded(shallow))
    assert header(decoded(shallow)) == header(decoded(zero))


def test_filters_are_exact_composable_and_roots_unfiltered(tmp_path):
    root = tmp_path / 'root'
    (root / 'dir').mkdir(parents=True)
    (root / 'dir' / 'inside').write_bytes(b'1234')
    (root / '.hidden').write_bytes(b'1')
    (root / 'keep').write_bytes(b'12')
    (root / 'match.txt').write_bytes(b'123')
    p = run(['-b', '-H', '-f', '-x', 'keep', root], tmp_path)
    names = row_names(decoded(p))
    assert names == ['match.txt']
    # Exclusion is an exact basename, not a glob or regular expression.
    q = run(['-b', '-x', '*.txt', root], tmp_path)
    assert 'match.txt' in decoded(q)
    r = run(['-x', 'root', root], tmp_path)
    assert header(decoded(r)).startswith('[ root ')


def test_aggregation_threshold_suffixes_and_invalid_values(tmp_path):
    root = tmp_path / 'r'
    root.mkdir()
    (root / 'small').write_bytes(b'1' * 4)
    (root / 'equal').write_bytes(b'1' * 1024)
    p = run(['-b', '-a1K', root], tmp_path)
    names = row_names(decoded(p))
    assert 'equal' in names and '<aggregated>' in names
    assert names[-1] == '<aggregated>'
    assert 'small' not in names
    for val in ('abc', '1MB', '1.5M', '-2'):
        q = run([f'--aggr={val}', root], tmp_path)
        assert q.returncode == 1 and q.stdout == b''
        assert f"invalid argument '{val}'\n".encode() == q.stderr
    z = run(['-b', '-a0', root], tmp_path)
    assert 'small' in row_names(decoded(z))


def test_summary_equals_explicit_and_overrides_values(tmp_path):
    root = tmp_path / 'r'
    root.mkdir()
    (root / 'sub').mkdir()
    (root / 'sub' / 'leaf').write_bytes(b'x')
    a = run(['-s', '-b', root], tmp_path)
    b = run(['-d1', '-a1M', '-b', root], tmp_path)
    assert a.stdout == b.stdout
    assert 'leaf' not in decoded(a)
    c = run(['-s', '-d0', '-a0', '-b', root], tmp_path)
    assert c.stdout == a.stdout


def test_size_mode_bytes_symlinks_sparse(tmp_path):
    target = tmp_path / 'target'
    target.write_bytes(b'hello world')
    link = tmp_path / 'link'
    link.symlink_to('target')
    sparse = tmp_path / 'sparse'
    with sparse.open('wb') as f:
        f.truncate(2 * 1024 * 1024)
    apparent = run(['-d0', '-b', target], tmp_path)
    assert header(decoded(apparent)).endswith('11 B ]')
    symlink = run(['-d0', '-b', link], tmp_path)
    assert header(decoded(symlink)).endswith('6 B ]')
    usage = run(['-d0', '-u', '-b', sparse], tmp_path)
    assert header(decoded(usage)).endswith(' B ]')
    assert re.search(r'\[ sparse \d+ B \]', header(decoded(usage)))


def test_depth_fallback_uses_unfiltered_descendants(tmp_path):
    root = tmp_path / 'root'
    (root / 'dir').mkdir(parents=True)
    (root / 'dir' / 'excluded').write_bytes(b'x' * 19)
    # At depth one, filters below dir are not applied during fallback measurement.
    p = run(['-d1', '-x', 'excluded', '-b', root], tmp_path)
    assert header(decoded(p)).endswith(' B ]')
    assert 'dir' in decoded(p) and 'excluded' not in decoded(p)


def test_width_ascii_bars_and_formatted_sizes(tmp_path):
    root = tmp_path / 'r'
    root.mkdir()
    (root / 'item').write_bytes(b'x' * 1024)
    p = run(['-A', root], tmp_path)
    line = next(x for x in decoded(p).splitlines()[1:] if 'item' in x)
    assert len(line) == 80
    assert '│' in line and '├─' in line and '#' in line
    assert line.endswith('1.00 KiB')
    b = run(['-A', '-b', root], tmp_path)
    assert '1024 B' in decoded(b)


def test_unicode_names_and_invalid_utf8(tmp_path):
    root = tmp_path / 'r'
    root.mkdir()
    (root / ('x' * 20 + '👩\u200d👩\u200d👧\u200d👦Z')).write_text('x')
    os.open(os.fsencode(root) + b'/bad\xff', os.O_CREAT | os.O_WRONLY, 0o600)
    p = run(['-A', root], tmp_path)
    out = decoded(p)
    assert '[invalid name]' in out
    assert 'xxxxxxxxxxxxxxxxxxxxZ' in out


def test_colors_priority_and_ascii_disables_color(tmp_path):
    root = tmp_path / 'r'
    root.mkdir()
    (root / 'file.txt').write_text('x')
    p = run([root], tmp_path, {'LS_COLORS': 'fi=1:*.txt=31'})
    assert '\x1b[31mfile.txt\x1b[0m' in decoded(p)
    q = run(['-A', root], tmp_path, {'LS_COLORS': 'fi=1:*.txt=31'})
    assert '\x1b[' not in decoded(q)
    assert not q.stderr


def test_ls_colors_quirks_and_parse_order(tmp_path):
    root = tmp_path / 'r'
    root.mkdir()
    f = root / 'f.txt'
    f.write_text('x')
    for value in ('bad', '=EMPTY:unknown=anything'):
        p = run(['-A', root], tmp_path, {'LS_COLORS': value})
        assert p.returncode == 101 and b'panicked at src/lib.rs:' in p.stderr
    p = run(['-A', root], tmp_path, {'LS_COLORS': 'fi=ok::*.txt=ignored'})
    assert '\x1b[okm' in decoded(p) and 'ignored' not in decoded(p)
    p = run(['--help'], tmp_path, {'LS_COLORS': 'bad'})
    assert p.returncode == 0 and not p.stderr
    p = run(['--aggr=wat', root], tmp_path, {'LS_COLORS': 'bad'})
    assert p.returncode == 101 and b'panicked at src/lib.rs:' in p.stderr


def test_short_optional_values_and_end_of_options(tmp_path):
    root = tmp_path / '-folder'
    root.mkdir()
    (root / 'child').write_text('x')
    p = run(['-d2', '--bytes', '--', str(root)], tmp_path)
    assert p.returncode == 0 and 'child' in decoded(p)
    q = run(['-da', str(root)], tmp_path)
    assert q.returncode == 0 and 'child' in decoded(q)
    r = run(['--depth', '2', '.'], tmp_path)
    # Long optional arguments require '='; "2" is a separate root path.
    assert r.returncode == 1 and r.stdout == b'' and b"path 2 doesn't exist" in r.stderr
