import os
import pathlib
import pty
import re
import select
import shutil
import struct
import subprocess
import termios
import time
import fcntl
import array

import pytest


E = pathlib.Path('/workspace/executable')


def run(args=(), cwd=None, env=None, timeout=5):
    return subprocess.run([str(E), *args], cwd=cwd, env=env, capture_output=True, timeout=timeout)


def git(cwd, *args, env=None):
    p = subprocess.run(['git', *args], cwd=cwd, env=env, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    d = tmp_path / 'repo'
    d.mkdir()
    git(d, 'init', '-b', 'master')
    git(d, 'config', 'user.name', 'Test User')
    git(d, 'config', 'user.email', 'test@example.com')
    (d / 'file.txt').write_text('first\n')
    git(d, 'add', '.')
    git(d, 'commit', '-m', 'First commit')
    return d


def commit(d, name, content=None):
    p = d / ((name.lower().replace(' ', '_')) + '.txt')
    p.write_text(content or name + '\n')
    git(d, 'add', '.')
    git(d, 'commit', '-m', name)


def screen(d, keys=b'q', size=(80, 24), env=None, delay=.25):
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', size[1], size[0], 0, 0))
    childenv = os.environ.copy()
    childenv.update({'TERM': 'xterm-256color', 'LC_ALL': 'C.UTF-8'})
    if env:
        childenv.update(env)
    proc = subprocess.Popen([str(E)], cwd=d, stdin=slave, stdout=slave, stderr=slave, env=childenv, close_fds=True)
    os.close(slave)
    data = bytearray()
    end = time.monotonic() + delay
    while time.monotonic() < end:
        ready, _, _ = select.select([master], [], [], .03)
        if ready:
            try: data.extend(os.read(master, 65536))
            except OSError: break
    if proc.poll() is None:
        try: os.write(master, keys)
        except OSError: pass
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and proc.poll() is None:
        ready, _, _ = select.select([master], [], [], .05)
        if ready:
            try: data.extend(os.read(master, 65536))
            except OSError: break
    if proc.poll() is None:
        proc.kill()
    proc.wait(timeout=2)
    try:
        while True: data.extend(os.read(master, 65536))
    except OSError: pass
    os.close(master)
    return proc.returncode, bytes(data)


def visible(raw):
    # Keep printable UTF-8 and line breaks; sufficient for content assertions.
    s = raw.decode('utf-8', 'replace')
    s = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', s)
    s = re.sub(r'\x1b\][^\x07]*(?:\x07|\x1b\\)', '', s)
    return s


HELP = ('A TUI tool to visualize Git commit graphs with branch genealogy\n\n'
        'Usage: executable\n\nOptions:\n  -h, --help     Print help\n  -V, --version  Print version\n')


@pytest.mark.parametrize('args', [('-h',), ('--help',), ('--help','--bad-option'), ('-hV',)], ids=['short','long','help-precedence','combined'])
def test_help_exact(args):
    p = run(args)
    assert p.returncode == 0 and p.stdout == HELP.encode() and p.stderr == b''


@pytest.mark.parametrize('flag', ['-V', '--version'], ids=['short-version','long-version'])
def test_version_exact(flag):
    p = run([flag])
    assert p.returncode == 0 and p.stdout == b'keifu 0.2.3\n' and p.stderr == b''


def test_version_attached_value_diagnostic():
    p = run(['--version=1'])
    assert p.returncode == 2 and p.stdout == b''
    assert p.stderr == (b"error: unexpected value '1' for '--version' found; no more were expected\n\n"
                        b'Usage: executable --version\n\nFor more information, try \'--help\'.\n')


@pytest.mark.parametrize('arg', ['--invalid-flag', '-z', 'operand', '-- --help'], ids=['unknown-long','unknown-short','positional','after-terminator'])
def test_invalid_argument_diagnostic(arg):
    args = arg.split() if arg.startswith('-- ') else [arg]
    p = run(args)
    offending = args[-1] if args[0] == '--' else args[0]
    assert p.returncode == 2 and p.stdout == b''
    assert p.stderr == (f'error: unexpected argument \'{offending}\' found\n\nUsage: executable\n\nFor more information, try \'--help\'.\n').encode()


def test_bare_option_terminator_launches_tui_in_repo(repo):
    p = run(['--'], cwd=repo, timeout=3)
    assert p.returncode == 1 and p.stdout == b'' and p.stderr
    assert b'Usage: executable' not in p.stderr and b'repository not found' not in p.stderr


def test_repository_discovery_failure_diagnostic(tmp_path):
    p = run(cwd=tmp_path)
    assert p.returncode == 1 and p.stdout == b''
    assert b'Git repository not found' in p.stderr
    assert b'Please run inside a Git repository' in p.stderr
    assert b'could not find repository' in p.stderr
    assert b'Usage: executable' not in p.stderr


def test_pipe_startup_fails_as_terminal_error(repo):
    p = run(cwd=repo, timeout=3)
    assert p.returncode == 1 and not p.stdout and p.stderr
    assert b'repository not found' not in p.stderr.lower()
    assert b'Usage: executable' not in p.stderr


def test_nested_directory_discovers_repo(repo):
    nested = repo / 'a' / 'b'; nested.mkdir(parents=True)
    p = run(cwd=nested)
    assert p.returncode == 1 and p.stderr
    assert b'repository not found' not in p.stderr.lower()


def test_clean_repo_graph_and_metadata(repo):
    commit(repo, 'Second commit')
    code, raw = screen(repo)
    s = visible(raw)
    assert code == 0 and 'Commits' in s and 'Commit Detail' in s and 'Changed Files' in s
    assert '[master] Second commit' in s and 'First commit' in s
    assert 'Commit:' in s and 'Author: Test User <test@example.com>' in s
    assert '1 files changed  +1 -0' in s and ' A second_commit.txt +1 -0' in s


def test_empty_repository_and_status(repo):
    blank = repo.parent / 'blank'; blank.mkdir(); git(blank, 'init', '-b', 'main')
    code, raw = screen(blank)
    s = visible(raw)
    assert code == 0 and 'Select a commit' in s and 'Changed Files' in s
    assert '   main   ' in s


def test_layout_80x24_and_author_tier(repo):
    code, raw = screen(repo, size=(80,24))
    s = visible(raw)
    assert code == 0 and '┌ Commits ' in s and '┌ Commit Detail ' in s
    assert '[master] First commit' in s and 'Test Use' in s


def test_layout_narrow_and_long_unicode_content(repo):
    git(repo, 'checkout', '-b', 'feature/very-long-name')
    (repo / '長い.txt').write_text('雪\n'); git(repo, 'add', '.'); git(repo, 'commit', '-m', 'Unicode 雪だるま ☃ message')
    code, raw = screen(repo, size=(25,24))
    s = visible(raw)
    assert code == 0 and 'Commits' in s and 'Commit Detail' in s and 'Changed Files' in s
    assert 'index outside of buffer' not in s


def test_uncommitted_row_and_detail(repo):
    (repo / 'file.txt').write_text('changed\n'); git(repo, 'add', 'file.txt')
    code, raw = screen(repo)
    s = visible(raw)
    assert code == 0 and 'uncommitted changes (1)' in s
    assert 'Uncommitted Changes' in s and '1 files with changes' in s


def test_navigation_selection_updates_details(repo):
    commit(repo, 'Second commit'); commit(repo, 'Third commit')
    code, raw = screen(repo, keys=b'jq')
    s = visible(raw)
    assert code == 0 and 'Third commit' in s and 'Second commit' in s
    # after j, second commit details must be selected
    assert 'Second commit' in s


def test_help_overlay_and_close_does_not_quit(repo):
    code, raw = screen(repo, keys=b'?qq')
    s = visible(raw)
    assert code == 0 and 'Navigation' in s and 'Move down' in s and 'Git Operations' in s


def test_branch_creation_and_deletion_modal(repo):
    code, raw = screen(repo, keys=b'bfeature/test\rq')
    s = visible(raw)
    assert code == 0 and 'feature/test' in s
    assert git(repo, 'branch', '--list', 'feature/test') == 'feature/test'


def test_fetch_missing_origin_reports_error_without_exit(repo):
    code, raw = screen(repo, keys=b'fq')
    s = visible(raw)
    assert code == 0 and 'git fetch failed' in s and 'ERROR' in s


def test_checkout_detached_commit(repo):
    commit(repo, 'Second commit')
    code, raw = screen(repo, keys=b'j\rq')
    s = visible(raw)
    assert code == 0
    assert git(repo, 'rev-parse', '--abbrev-ref', 'HEAD') == 'HEAD'


@pytest.mark.parametrize('contents', ['', '[refresh]\nauto_refresh = "wrong"\n', 'not toml = ['], ids=['empty','wrong-type','malformed'])
def test_configuration_problems_do_not_prevent_startup(repo, tmp_path, contents):
    cfg = tmp_path / 'config'; target = cfg / 'keifu'; target.mkdir(parents=True)
    (target / 'config.toml').write_text(contents)
    code, raw = screen(repo, env={'XDG_CONFIG_HOME': str(cfg)})
    assert code == 0 and 'Commits' in visible(raw)


def test_diverged_branches_are_both_shown(repo):
    git(repo, 'checkout', '-b', 'feature')
    commit(repo, 'Feature work')
    git(repo, 'checkout', 'master')
    commit(repo, 'More work on master')
    code, raw = screen(repo)
    s = visible(raw)
    assert code == 0 and '[master] More work on master' in s and '[feature] Feature work' in s


def test_multiple_refs_and_branch_overlay(repo):
    git(repo, 'branch', 'develop')
    code, raw = screen(repo, keys=b'j?q')
    s = visible(raw)
    assert code == 0 and '[master] +1' in s and 'Branches' in s and 'develop' in s


def test_search_overlay_supports_query(repo):
    git(repo, 'branch', 'feature/auth')
    git(repo, 'branch', 'feature/search')
    code, raw = screen(repo, keys=b'/feat\rq')
    s = visible(raw)
    assert code == 0 and 'Search branches' in s and 'feature/auth' in s and 'feature/search' in s


def test_confirm_delete_branch(repo):
    git(repo, 'branch', 'develop')
    # j selects the second branch item on the current commit; d, then y confirms.
    code, raw = screen(repo, keys=b'jd yq'.replace(b' ', b''))
    s = visible(raw)
    assert code == 0 and git(repo, 'branch', '--list', 'develop') == ''
