import os
import pathlib
import subprocess

import pytest


BIN = pathlib.Path('/workspace/executable')


@pytest.fixture
def tree(tmp_path):
    (tmp_path / 'alpha.txt').write_text('a')
    (tmp_path / 'UPPER.TXT').write_text('bb')
    (tmp_path / 'beta.rs').write_text('')
    (tmp_path / 'a.foo').write_text('x')
    (tmp_path / 'directory_foo').mkdir()
    (tmp_path / 'directory_foo' / 'deep.txt').write_text('deep')
    (tmp_path / '.hidden').write_text('h')
    (tmp_path / '.secret_dir').mkdir()
    (tmp_path / '.secret_dir' / 'inside').write_text('i')
    (tmp_path / 'dir.name').mkdir()
    (tmp_path / 'dir.name' / 'archive.tar.gz').write_text('12345')
    return tmp_path


def run(*args, cwd=None, env=None):
    e = os.environ.copy()
    e.update({'NO_COLOR': '1'})
    if env:
        e.update(env)
    return subprocess.run([str(BIN), *map(str, args)], cwd=cwd, env=e,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def lines(p):
    assert p.returncode == 0, p.stderr.decode(errors='replace')
    return p.stdout.decode().splitlines()


def test_version_aliases_and_help_precedence():
    for opt in ('--version', '-V'):
        p = run(opt)
        assert (p.returncode, p.stdout, p.stderr) == (0, b'fd 10.3.0\n', b'')
    for opt in ('--help', '-h'):
        p = run(opt, '--definitely-invalid')
        assert p.returncode == 0 and not p.stderr
        assert p.stdout.startswith(b'A program to find entries in your filesystem\n\nUsage: executable')
        assert b'--search-path' in p.stdout


def test_no_pattern_and_empty_pattern(tree):
    got = set(lines(run('', tree)))
    assert {'alpha.txt', '.hidden', 'directory_foo/', 'directory_foo/deep.txt'} <= got
    assert str(tree) + '/alpha.txt' in got


def test_regex_basename_full_path_and_regex_constructs(tree):
    assert set(lines(run('foo', tree))) == {str(tree) + '/a.foo', str(tree) + '/directory_foo/'}
    assert lines(run('^alpha\\.txt$', tree)) == [str(tree) + '/alpha.txt']
    assert lines(run('foo', '--full-path', tree)) == [str(tree) + '/a.foo', str(tree) + '/directory_foo/']
    assert lines(run(r'^[a-z]+\.rs$', tree)) == [str(tree) + '/beta.rs']
    assert str(tree) + '/alpha.txt' in lines(run(r'^(alpha|beta)\.(txt|rs)$', tree))


def test_glob_braces_recursive_and_regex_override(tree):
    assert set(lines(run('--glob', '*.{txt,rs}', tree))) == {
        str(tree) + '/alpha.txt', str(tree) + '/UPPER.TXT', str(tree) + '/beta.rs'}
    assert set(lines(run('-g', '**/*.txt', tree))) == {
        str(tree) + '/alpha.txt', str(tree) + '/UPPER.TXT', str(tree) + '/directory_foo/deep.txt'}
    assert lines(run('--glob', '--regex', 'alpha', tree)) == [str(tree) + '/alpha.txt']


def test_fixed_strings_case_and_and_filters(tree):
    assert lines(run('-F', '.', tree)) == []
    assert set(lines(run('-F', 'TXT', tree))) == {str(tree) + '/alpha.txt', str(tree) + '/UPPER.TXT'}
    assert lines(run('-s', 'alpha', tree)) == [str(tree) + '/alpha.txt']
    assert set(lines(run('-i', 'ALPHA', tree))) == {str(tree) + '/alpha.txt'}
    assert lines(run('alpha', '--and', r'\.txt$', tree)) == [str(tree) + '/alpha.txt']
    assert lines(run('alpha', '--and', 'beta', tree)) == []


def test_hidden_and_type_filtering(tree):
    assert not any('.hidden' in x or '.secret' in x for x in lines(run('', tree)))
    assert str(tree) + '/.hidden' in lines(run('--hidden', '', tree))
    assert str(tree) + '/.secret_dir/inside' in lines(run('-H', '', tree))
    assert set(lines(run('-tf', '', tree))) == {str(tree) + '/alpha.txt', str(tree) + '/UPPER.TXT', str(tree) + '/beta.rs', str(tree) + '/a.foo', str(tree) + '/directory_foo/deep.txt', str(tree) + '/dir.name/archive.tar.gz'}
    assert lines(run('-td', '', tree)) == [str(tree) + '/dir.name/', str(tree) + '/directory_foo/']


def test_depth_extensions_and_sizes(tree):
    assert lines(run('', '--max-depth', '1', tree)) == [str(tree) + '/UPPER.TXT', str(tree) + '/a.foo', str(tree) + '/alpha.txt', str(tree) + '/beta.rs', str(tree) + '/dir.name/', str(tree) + '/directory_foo/']
    assert lines(run('', '--exact-depth', '2', tree)) == [str(tree) + '/dir.name/archive.tar.gz', str(tree) + '/directory_foo/deep.txt']
    assert set(lines(run('', '-e', 'TXT', tree))) == {str(tree) + '/alpha.txt', str(tree) + '/UPPER.TXT', str(tree) + '/directory_foo/deep.txt'}
    assert lines(run('', '-e', '.gz', '-S', '5b', tree)) == [str(tree) + '/dir.name/archive.tar.gz']
    assert lines(run('', '-S', '+5b', tree)) == [str(tree) + '/dir.name/archive.tar.gz']
    assert run('', '-S', '5', tree).returncode == 2


def test_modification_time_cutoffs(tree):
    old = tree / 'beta.rs'
    os.utime(old, (1_600_000_000, 1_600_000_000))
    assert str(tree) + '/beta.rs' not in lines(run('', '--changed-within', '@1700000000', tree))
    assert str(tree) + '/beta.rs' in lines(run('', '--changed-before', '@1700000000', tree))
    assert run('', '--changed-within', 'nonsense', tree).returncode == 1


def test_roots_are_independent_and_validation(tree, tmp_path):
    sub = tree / 'directory_foo'
    got = lines(run('', tree, tree, sub))
    assert got.count(str(sub) + '/deep.txt') == 3
    p = run('', tree / 'missing', tree)
    assert p.returncode == 0 and b"Search path" in p.stderr and str(tree).encode() in p.stdout
    p = run('', tree / 'missing')
    assert p.returncode == 1 and b'No valid search paths' in p.stderr
    assert run('[invalid', tree / 'missing').returncode == 1


def test_order_and_directory_slashes(tree):
    out = lines(run('', tree))
    assert out == sorted(out)
    assert all(not x.endswith('/') or pathlib.Path(x.rstrip('/')).is_dir() for x in out)
    assert str(tree) + '/dir.name/' in out


def test_ignore_exclude_prune_and_containment(tmp_path):
    (tmp_path / '.ignore').write_text('skip/\n*.tmp\n')
    (tmp_path / 'skip').mkdir(); (tmp_path / 'skip' / 'inside').touch()
    (tmp_path / 'keep').mkdir(); (tmp_path / 'keep' / 'x.tmp').touch(); (tmp_path / 'keep' / 'needle').touch()
    assert set(lines(run('', tmp_path))) == {str(tmp_path) + '/keep/', str(tmp_path) + '/keep/needle'}
    assert str(tmp_path) + '/skip/inside' in lines(run('-I', '', tmp_path))
    assert str(tmp_path) + '/keep/x.tmp' not in lines(run('', '--exclude', '*.tmp', tmp_path))
    assert str(tmp_path) + '/keep/needle' not in lines(run('', '--ignore-contain', 'needle', tmp_path))
    assert str(tmp_path) + '/keep/needle' not in lines(run('^keep$', '--prune', tmp_path))
    assert lines(run('', '--exclude', '', tmp_path)) == []


def test_format_substitutions_and_separator(tree):
    path = str(tree) + '/dir.name/archive.tar.gz'
    assert lines(run('archive', '--format', 'path={} name={/} parent={//} noext={.} base={/.}', tree)) == [f'path={path} name=archive.tar.gz parent={tree}/dir.name noext={tree}/dir.name/archive.tar base=archive.tar']
    assert lines(run('alpha', '--format', '{{}}{}{{}}', tree)) == ['{}' + str(tree) + '/alpha.txt{}']
    assert lines(run('alpha', '--path-separator', '##', tree)) == [str(tree).replace('/', '##') + '##alpha.txt']


def test_base_directory_search_path_and_pattern_path_error(tree, tmp_path):
    p = run('alpha', '--base-directory', tree.parent, '--search-path', tree.name)
    assert lines(p) == [tree.name + '/alpha.txt']
    bad = run(str(tree / 'dir.name'), tree)
    assert bad.returncode == 1 and b'--full-path' in bad.stderr
    assert run('', '--base-directory', tree / 'missing').returncode == 1


def test_print0_absolute_relative_and_quiet(tree):
    p = run('alpha', '-0', tree)
    assert p.returncode == 0 and p.stdout == (b'./' + str(tree).encode() + b'/alpha.txt\0') or p.stdout.endswith(b'alpha.txt\0')
    assert lines(run('alpha', '--absolute-path', tree)) == [str(tree) + '/alpha.txt']
    q = run('alpha', '--quiet', tree)
    assert (q.returncode, q.stdout) == (0, b'')
    q = run('absent', '--has-results', tree)
    assert q.returncode == 1 and not q.stdout


def test_limits_threads_and_argument_errors(tree):
    assert len(lines(run('', '--max-results', '2', tree))) == 2
    assert len(lines(run('', '-1', tree))) == 1
    assert lines(run('', '--threads', '1', tree)) == lines(run('', '--threads', '4', tree))
    for args in [('--threads', '0'), ('--threads', 'x'), ('--max-results', '-1'), ('--max-buffer-time', 'bad')]:
        assert run('', *args, tree).returncode == 2
    assert run('--unknown-option', tree).returncode == 2


def test_symlinks_follow_and_broken_links(tmp_path):
    (tmp_path / 'real').mkdir(); (tmp_path / 'real' / 'child').touch()
    (tmp_path / 'link').symlink_to(tmp_path / 'real', target_is_directory=True)
    (tmp_path / 'broken').symlink_to('absent')
    assert str(tmp_path) + '/link/child' not in lines(run('', tmp_path))
    assert str(tmp_path) + '/link/child' in lines(run('--follow', '', tmp_path))
    assert str(tmp_path) + '/broken' in lines(run('-tl', '', tmp_path))
    assert str(tmp_path) + '/link' not in lines(run('-tl', '', tmp_path, '--follow'))


def test_exec_substitution_and_batch(tree):
    p = run('alpha', '-x', '/usr/bin/printf', '<%s>', '{}', cwd=tree)
    assert p.returncode == 0 and p.stdout == b'<./alpha.txt>'
    p = run('alpha', '-X', '/usr/bin/printf', '<%s>', '{}', cwd=tree)
    assert p.returncode == 0 and p.stdout == b'<./alpha.txt>'
    p = run('archive', '-x', '/usr/bin/printf', '%s', '{.}', cwd=tree)
    assert p.stdout == b'archive.tar'
    assert run('alpha', '-x', '/no/such/command', cwd=tree).returncode == 1


def test_exec_batch_validation_and_batch_size(tree):
    assert run('', '-X', '/usr/bin/echo', '{}', '{}', tree).returncode == 2
    assert run('', '-X', '{}', tree).returncode == 2
    p = run('alpha', '-X', '/usr/bin/printf', '%s', '{}', '--batch-size', '1', cwd=tree)
    assert p.returncode == 0 and p.stdout == b'./alpha.txt'


def test_custom_ignore_file_and_missing_diagnostic(tree, tmp_path):
    ignore = tmp_path / 'custom'; ignore.write_text('alpha.txt\n')
    assert str(tree) + '/alpha.txt' not in lines(run('', '--ignore-file', ignore, tree))
    p = run('', '--ignore-file', tmp_path / 'absent', tree)
    assert p.returncode == 0 and p.stderr.count(b'Malformed pattern in custom ignore file') == 1


def test_one_file_system_aliases_and_smart_case(tree):
    baseline = lines(run('', tree))
    for opt in ('--one-file-system', '--mount', '--xdev'):
        assert lines(run('', opt, tree)) == baseline
    assert lines(run('alpha', tree)) == lines(run('ALPHA', tree))
    assert lines(run('ALPHA', '--case-sensitive', tree)) == []


def test_non_utf8_safe_text_names_and_nul_output(tmp_path):
    name = 'space 漢字 é 😃.txt'
    (tmp_path / name).write_text('payload')
    p = run('', '-0', tmp_path)
    assert p.returncode == 0 and name.encode() in p.stdout and p.stdout.endswith(b'\0')
    p = run('', tmp_path, '-x', '/usr/bin/printf', '%s', '{}')
    assert p.returncode == 0 and name.encode() in p.stdout


def test_completion_modes():
    for shell, start in [('bash', b'_executable() {'), ('zsh', b'#compdef executable'), ('fish', b'complete -c executable'), ('powershell', b'\nusing namespace'), ('elvish', b'use builtin')]:
        p = run('--gen-completions', shell)
        assert p.returncode == 0 and p.stdout.startswith(start) and b'executable' in p.stdout
        if shell == 'fish':
            assert len([x for x in p.stdout.splitlines() if x.strip()]) > 50
