import os
import subprocess
from pathlib import Path

EXE = Path('/workspace/executable')
VERSION = 'tig version 2.6.0-g87c9c25\nncursesw version 6.3.20211021\n'
HELP = '''tig 2.6.0-g87c9c25 \n
Usage: tig        [options] [revs] [--] [paths]
   or: tig log    [options] [revs] [--] [paths]
   or: tig show   [options] [revs] [--] [paths]
   or: tig reflog [options] [revs]
   or: tig blame  [options] [rev] [--] path
   or: tig grep   [options] [pattern]
   or: tig refs   [options]
   or: tig stash  [options]
   or: tig status
   or: tig <      [git command output]

Options:
  +<number>       Select line <number> in the first view
  -v, --version   Show version and exit
  -h, --help      Show help message and exit
  -C <path>       Start in <path>
'''

def run(*args, cwd=None, env=None, stdin=b''):
    e = os.environ.copy(); e.update(env or {})
    return subprocess.run([str(EXE), *args], cwd=cwd, env=e, input=stdin,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)

def test_version_exact_and_repository_independent():
    for arg in ('-v', '--version'):
        p = run(arg, cwd='/tmp', stdin=b'ignored')
        assert (p.returncode, p.stdout, p.stderr) == (0, VERSION.encode(), b'')

def test_help_exact_and_repository_independent():
    p = run('--help', cwd='/tmp', stdin=b'ignored')
    assert (p.returncode, p.stdout, p.stderr) == (0, HELP.encode(), b'')

def test_first_info_flag_wins_and_short_circuits_bad_arguments():
    cases = [(['-v', '--help', '--invalid-flag', '+bad'], VERSION),
             (['--help', '-v', '--invalid-flag', '+bad'], HELP),
             (['status', '--version', '--invalid-flag'], VERSION),
             (['--', '--help'], None)]
    for args, expected in cases:
        p = run(*args)
        if expected is not None:
            assert p.returncode == 0 and p.stdout.decode() == expected and p.stderr == b''
        else:
            assert p.returncode != 0

def test_help_subcommands_route_to_main_help():
    for sub in ('log', 'show', 'reflog', 'blame', 'grep', 'refs', 'stash', 'status'):
        p = run(sub, '--help')
        assert p.returncode == 0 and p.stdout.decode() == HELP and not p.stderr

def test_special_c_help_does_not_consume_help_as_directory():
    p = run('-C', '--help')
    assert p.returncode == 0 and p.stdout.decode() == HELP and not p.stderr

def test_help_is_escape_free_and_has_operands():
    p = run('-h')
    assert b'\x1b' not in p.stdout
    assert b'blame  [options] [rev] [--] path' in p.stdout
    assert b'grep   [options] [pattern]' in p.stdout

def test_detached_change_directory_failure_is_exact():
    p = run('-C', '/nonexistent', '--help')
    assert p.returncode == 1
    assert p.stdout == b''
    assert p.stderr == b'tig: Failed to change directory to /nonexistent\n'

def test_attached_c_is_revision_not_directory(tmp_path):
    p = run('-Cdoes-not-exist', cwd=tmp_path)
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr == b'tig: No revisions match the given arguments.\n'

def test_bare_c_falls_through_revision_resolution(tmp_path):
    p = run('-C', cwd=tmp_path)
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr == b'tig: No revisions match the given arguments.\n'

def test_unknown_options_fail_with_diagnostic():
    for arg in ('--invalid-flag', '--definitely-not-a-real-option', '-Z'):
        p = run(arg)
        assert p.returncode != 0 and p.stderr.strip()

def test_missing_blame_path_and_grep_pattern_fail():
    for args in (('blame',), ('grep',)):
        p = run(*args)
        assert p.returncode != 0 and p.stderr.strip()

def test_case_sensitive_subcommands_are_not_aliases(tmp_path):
    for word in ('Status', 'LOG', 'Show'):
        p = run(word, cwd=tmp_path)
        assert p.returncode != 0
        assert b'No revisions match the given arguments' in p.stderr

def test_non_decimal_plus_is_revision_input(tmp_path):
    for token in ('+text', '+', '-1', '+:command'):
        p = run(token, cwd=tmp_path)
        assert p.returncode != 0
        assert b'No revisions match the given arguments' in p.stderr

def test_prefix_selection_is_not_hoisted_over_subcommand(tmp_path):
    for args in (('+5', 'status'), ('+3', 'status'), ('+2', 'blame', 'README.md')):
        p = run(*args, cwd=tmp_path)
        assert p.returncode == 1 and p.stdout == b''
        assert p.stderr == b'tig: No revisions match the given arguments.\n'

def test_unresolvable_revision_has_expected_diagnostic(tmp_path):
    p = run('not-a-real-revision', cwd=tmp_path)
    assert p.returncode != 0
    assert b'No revisions match the given arguments' in p.stderr

def test_no_tty_fails_promptly_for_views():
    for args in ((), ('status',), ('show',), ('+1',)):
        p = run(*args, stdin=b'')
        assert p.returncode == 1 and b'Failed to open tty' in p.stderr
