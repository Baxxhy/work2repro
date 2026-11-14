import os
import subprocess
from pathlib import Path

import pytest


EXE = Path('/workspace/executable')
HELP = ("usage: nnn [OPTIONS] [PATH]\n\n"
"The unorthodox terminal file manager.\n\n"
"positional args:\n  PATH   start dir/file [default: .]\n\n"
"optional args:\n"
" -a      auto NNN_FIFO\n -A      no dir auto-enter during filter\n -b key  open bookmark key (trumps -s/S)\n"
" -B      use bsdtar for archives\n -c      cli-only NNN_OPENER (trumps -e)\n -C      8-color scheme\n"
" -d      detail mode\n -D      dirs in context color\n -e      text in $VISUAL/$EDITOR/vi\n -E      internal edits in EDITOR\n"
" -f      use history file\n -F val  fifo mode [0:preview 1:explore]\n -g      regex filters\n -H      show hidden files\n"
" -i      show current file info\n -J      no auto-advance on selection\n -K      detect key collision and exit\n -l val  set scroll lines\n"
" -n      type-to-nav mode\n -N      use native prompt\n -o      open files only on Enter\n -p file selection file [-:stdout]\n"
" -P key  run plugin key\n -Q      no quit confirmation\n -r      use advcpmv patched cp, mv\n -R      no rollover at edges\n"
" -s name load session by name\n -S      persistent session\n -t secs timeout to lock\n -T key  sort order [a/d/e/r/s/t/v]\n"
" -u      use selection (no prompt)\n -U      show user and group\n -V      show version\n -x      notis, selection sync, xterm title\n"
" -z      in order fuzzy filters\n -0      null separator in picker mode\n -h      show help\n\nv5.2\nBSD 2-Clause\nhttps://github.com/jarun/nnn\n")


def run(args=(), *, cwd=None, env=None, data=b'', argv0=None):
    command = [str(EXE), *map(str, args)]
    if argv0 is not None:
        command[0] = argv0
    e = os.environ.copy()
    e.update({'TERM': 'xterm', 'LC_ALL': 'C.UTF-8'})
    if env:
        e.update(env)
    return subprocess.run(command, input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=cwd, env=e, timeout=5)


def test_help_is_exact_and_terminates_scanning():
    for args in [('-h',), ('-h', '-V'), ('-h', '-X'), ('--', '-h')]:
        p = run(args)
        # After --, -h is a path and therefore follows ordinary empty-input behavior.
        if args == ('--', '-h'):
            assert p.returncode == 1 and p.stdout == b'' and p.stderr == b'0 entries\n'
        else:
            assert (p.returncode, p.stdout, p.stderr) == (0, HELP.encode(), b'')


def test_version_exact_and_terminates_before_later_arguments():
    for args in [('-V',), ('-V', '-h'), ('-V', '-X'), ('-V', 'some path')]:
        p = run(args, env={'NNN_ORDER': 'x:/tmp'})
        assert (p.returncode, p.stdout, p.stderr) == (0, b'5.2\n', b'')


def test_key_check_is_silent_and_immediate():
    p = run(('-K', 'ignored', '-H'))
    assert (p.returncode, p.stdout, p.stderr) == (0, b'', b'')


@pytest.mark.parametrize('option', ['b', 'F', 'l', 'p', 'P', 's', 't', 'T'], ids=['bookmark','fifo','scroll','picker','plugin','session','timeout','sort'])
def test_required_argument_diagnostic(option):
    p = run(('-' + option,), argv0='/workspace/executable')
    assert p.returncode == 1
    assert p.stdout == HELP.encode()
    assert p.stderr == f"/workspace/executable: option requires an argument -- '{option}'\n".encode()


@pytest.mark.parametrize('args,char', [(['-X'], 'X'), (['-X','-h'], 'X'), (['-X','-Y'], 'X'), (['--invalid'], '-'), (['--help'], '-')], ids=['unknown','stops-before-help','first-error','long','unsupported-help'])
def test_invalid_option_reports_first_error(args, char):
    p = run(args, argv0='/workspace/executable')
    assert p.returncode == 1
    assert p.stdout == HELP.encode()
    assert p.stderr == f"/workspace/executable: invalid option -- '{char}'\n".encode()


def test_error_prefix_tracks_invocation_spelling():
    p = run(('-Z',), argv0='./executable')
    assert p.stderr == b"./executable: invalid option -- 'Z'\n"


@pytest.mark.parametrize('args', [(), ('-H',), ('-d','-i','-U'), ('-x',), ('-p','-'), ('-F','garbage'), ('-T','x')], ids=['plain','hidden','display-flags','xterm-notify','picker-stdout','native-fifo-conversion','unknown-sort-key'])
def test_empty_nonterminal_fails_promptly(args, tmp_path):
    p = run(args, cwd=tmp_path)
    assert p.returncode == 1
    assert p.stderr == b'0 entries\n'
    assert p.stdout == (b'\x1b[23;0t' if '-x' in args else b'')


@pytest.mark.parametrize('value', ['-1', '2', '999'], ids=['negative','two','large'])
def test_fifo_mode_out_of_range_fails_silently(value):
    p = run(('-F', value))
    assert (p.returncode, p.stdout, p.stderr) == (1, b'', b'')


@pytest.mark.parametrize('args', [('-g','-z'), ('-z','-g')], ids=['regex-then-fuzzy','fuzzy-then-regex'])
def test_filter_modes_conflict(args):
    p = run(args)
    assert (p.returncode, p.stdout, p.stderr) == (1, b'', b'')


def test_environment_filter_conflict_precedes_help_or_version():
    for args in [('-V',), ('-h',)]:
        p = run(args, env={'NNN_OPTS':'g'})
        assert (p.returncode, p.stdout, p.stderr) == (1, b'', b'')


@pytest.mark.parametrize('value', ['F1','Tv','sname','F1Tvsname','Y'], ids=['fifo-value-not-attached','sort-value-not-attached','session-value-not-attached','combined','unknown-letter'])
def test_environment_options_are_processed_one_letter_at_a_time(value):
    p = run(('-V',), env={'NNN_OPTS': value})
    assert p.returncode == 1
    assert p.stdout == HELP.encode()
    assert p.stderr == b''


def test_empty_and_valid_environment_options_do_not_break_version():
    for opts in ['', 'HdR']:
        p = run(('-V',), env={'NNN_OPTS': opts, 'NNN_COLORS':'nonsense', 'NNN_FCOLORS':'x'})
        assert (p.returncode, p.stdout, p.stderr) == (0, b'5.2\n', b'')


def test_version_ignores_unknown_order_rule():
    p = run(('-V',), env={'NNN_ORDER':'x:/tmp'})
    assert (p.returncode, p.stdout, p.stderr) == (0, b'5.2\n', b'')


def test_first_positional_path_only_and_multiple_paths_are_not_usage_error(tmp_path):
    first = tmp_path / 'first dir'
    first.mkdir()
    (first / 'entry').touch()
    other = tmp_path / 'second'
    other.mkdir()
    p = run((str(first), str(other)), cwd=tmp_path)
    assert p.returncode == 1 and p.stderr == b'0 entries\n' and p.stdout == b''


@pytest.mark.parametrize('target_kind', ['directory','file-parent'], ids=['trailing-directory','new-file-parent'])
def test_noninteractive_start_does_not_create_missing_paths(target_kind, tmp_path):
    target = tmp_path / 'missing' / ('newdir' if target_kind == 'directory' else 'newfile')
    spelling = str(target) + ('/' if target_kind == 'directory' else '')
    p = run((spelling,), cwd=tmp_path)
    assert p.returncode == 1 and p.stderr == b'0 entries\n' and p.stdout == b''
    assert not (tmp_path / 'missing').exists()


def test_picker_bad_parent_has_diagnostic_and_creates_nothing(tmp_path):
    dest = tmp_path / 'absent' / 'selection'
    p = run(('-p', str(dest)), cwd=tmp_path)
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr.endswith(b': No such file or directory\n')
    assert not dest.parent.exists()


def test_picker_destination_is_unlinked_before_noninteractive_exit(tmp_path):
    dest = tmp_path / 'selected'
    dest.write_text('old')
    p = run(('-p', str(dest)), cwd=tmp_path)
    assert p.returncode == 1 and p.stdout == b'' and p.stderr == b'0 entries\n'
    assert not dest.exists()


def test_picker_dash_never_creates_file_named_dash(tmp_path):
    p = run(('-p','-'), cwd=tmp_path)
    assert p.returncode == 1 and p.stdout == b'' and p.stderr == b'0 entries\n'
    assert not (tmp_path / '-').exists()


def test_empty_nonterminal_does_not_create_user_fifo(tmp_path):
    fifo = tmp_path / 'events'
    p = run((), cwd=tmp_path, env={'NNN_FIFO': str(fifo)})
    assert p.returncode == 1 and p.stderr == b'0 entries\n'
    assert not fifo.exists()


def test_nonterminal_path_list_uses_nul_not_newline(tmp_path):
    for name in ['.hidden', 'folder', 'invalid']:
        q = tmp_path / name
        q.mkdir() if name == 'folder' else q.touch()
    p = run((), cwd=tmp_path, data=b'.hidden\nfolder\ninvalid\n')
    assert p.returncode == 1
    assert p.stderr == b''


def test_broken_startup_bookmark_is_checked_after_empty_input(tmp_path):
    p = run(('-b','broken_test'), cwd=tmp_path, env={'NNN_BMS': f'broken_test:{tmp_path / "absent"}'})
    assert p.returncode == 1 and p.stdout == b'' and p.stderr == b'0 entries\n'
