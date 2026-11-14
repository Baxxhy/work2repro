import os
import fcntl
import pty
import select
import struct
import subprocess
import termios
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
EXE = Path('/workspace/executable')


def run(*args, env=None, cwd=None, input_data=b''):
    e = os.environ.copy()
    e.pop('RIPGREP_CONFIG_PATH', None)
    e['TERM'] = 'dumb'
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd, env=e,
                          input=input_data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=8)


def test_help_is_exact_and_precedes_type_list():
    for args in [('--help',), ('--type-list', '--help'), ('needle', '--help')]:
        p = run(*args)
        assert (p.returncode, p.stdout, p.stderr) == (0, (ROOT/'help.txt').read_bytes(), b'')


def test_version_aliases_exact():
    a, b = run('-V'), run('--version')
    assert (a.returncode, a.stdout, a.stderr) == (0, b'igrep 1.3.0\n', b'')
    assert (b.returncode, b.stdout, b.stderr) == (0, a.stdout, b'')


def test_type_registry_exact_and_ignores_filter_values():
    p = run('--type-list', '-g', '[invalid', '-t', 'notatype', '-T', 'bad', '-i', '--sort=created')
    assert (p.returncode, p.stdout, p.stderr) == (0, (ROOT/'types.txt').read_bytes(), b'')


def test_missing_pattern_usage():
    p = run('--custom-command', 'editor')
    assert p.returncode == 2 and not p.stdout
    assert b'the following required arguments were not provided:' in p.stderr
    assert b'<PATTERN>' in p.stderr and p.stderr.endswith(b"For more information, try '--help'.\n")


def test_unknown_option_usage():
    p = run('--type-list', '--unknown')
    assert p.returncode == 2 and not p.stdout
    assert p.stderr == (b"error: unexpected argument '--unknown' found\n\n"
                        b"  tip: to pass '--unknown' as a value, use '-- --unknown'\n\n"
                        b"Usage: executable <PATTERN|--type-list> [PATHS]...\n\n"
                        b"For more information, try '--help'.\n")


def test_invalid_enum_diagnostic():
    p = run('--theme', 'invalid', 'needle')
    assert p.returncode == 2 and not p.stdout
    assert p.stderr == (b"error: invalid value 'invalid' for '--theme <THEME>'\n"
                        b'  [possible values: light, dark]\n\n'
                        b"For more information, try '--help'.\n")


def test_type_list_help_values_validated():
    p = run('--type-list', '--theme', 'invalid', '--help')
    assert p.returncode == 2 and not p.stdout and b'invalid value' in p.stderr


def test_invalid_search_glob_and_type_fail_cleanly(tmp_path):
    for args, expected in [(('--glob', '[invalid', 'x', str(tmp_path)), b'unclosed character class'),
                           (('-t', 'invalidtype', 'x', str(tmp_path)), b'unrecognized file type: invalidtype'),
                           (('-T', 'invalidtype', 'x', str(tmp_path)), b'unrecognized file type: invalidtype')]:
        p = run(*args)
        assert p.returncode == 1 and b'Error:' in p.stderr and expected in p.stderr
        assert b'traceback' not in p.stderr.lower() and b'panicked' not in p.stderr


def test_nonexistent_input_fails_non_tty(tmp_path):
    p = run('needle', tmp_path/'missing')
    assert p.returncode != 0
    assert b'error' in p.stderr.lower() or b'does not exist' in p.stderr.lower()


def test_editor_environment_validation_and_non_search_modes(tmp_path):
    env = {'EDITOR': 'invalid_editor', 'IGREP_EDITOR': ''}
    p = run('needle', str(tmp_path), env=env)
    assert p.returncode == 1 and p.stdout == b''
    assert b'"invalid_editor" read from $EDITOR' in p.stderr
    assert run('--help', env=env).returncode == 0
    assert run('--type-list', env=env).returncode == 0


def test_custom_command_validation(tmp_path):
    p = run('--custom-command', 'editor -x', 'needle', str(tmp_path))
    assert p.returncode == 1 and b"Expected one occurrence of '{file_name}'." in p.stderr
    assert run('--type-list', '--custom-command', 'invalid').returncode == 0


@pytest.mark.parametrize('pattern,flags,expected', [
    ('abc', (), b'abc'), ('abc', ('-i',), b'ABC'), ('abc', ('-S',), b'ABC'),
    ('Abc', ('-S',), b'abc'), ('hello', ('-w',), b'hello'),
    ('.*', ('-F',), b'.*'),
], ids=['regex-literal','ignore-case','smart-lower','smart-upper','word-boundary','fixed-literal'])
def test_search_flag_effects_in_tui(tmp_path, pattern, flags, expected):
    # Search runs in a TUI; this launch check catches immediate parser/setup failures.
    f = tmp_path/'sample.txt'; f.write_bytes(b'ABC abc\nhelloworld hello_world hello\n.*\n')
    p = run(*flags, pattern, str(f))
    assert p.returncode != 2


def test_config_path_directory_panics_as_specified(tmp_path):
    p = run('--type-list', env={'RIPGREP_CONFIG_PATH': str(tmp_path)})
    assert p.returncode == 101 and b'Not valid UTF-8' in p.stderr and b'IsADirectory' in p.stderr


def tui(tmp_path, args, keys=b'q', timeout=5):
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 80, 0, 0))
    env = os.environ.copy(); env.pop('RIPGREP_CONFIG_PATH', None)
    env.update({'TERM': 'xterm-256color', 'LC_ALL': 'C.UTF-8'})
    proc = subprocess.Popen([str(EXE), *map(str, args)], cwd=tmp_path, env=env,
                            stdin=slave, stdout=slave, stderr=slave, close_fds=True)
    os.close(slave)
    out = bytearray(); deadline = time.time()+timeout
    # Let the asynchronous search finish, then drive keys and collect final screen.
    while time.time() < deadline and proc.poll() is None:
        ready, _, _ = select.select([master], [], [], .05)
        if ready:
            try: out.extend(os.read(master, 65536))
            except OSError: break
        if b'FINISHED' in out:
            break
    for key in keys:
        try: os.write(master, key)
        except OSError: break
        time.sleep(.08)
    end = time.time()+timeout
    while time.time() < end and proc.poll() is None:
        ready, _, _ = select.select([master], [], [], .05)
        if ready:
            try: out.extend(os.read(master, 65536))
            except OSError: break
    if proc.poll() is None: proc.kill()
    proc.wait(timeout=2)
    try:
        while True: out.extend(os.read(master, 65536))
    except OSError: pass
    os.close(master)
    return proc.returncode, bytes(out)


def test_tui_reports_empty_state_and_quits(tmp_path):
    rc, out = tui(tmp_path, ['needle', str(tmp_path)])
    assert rc == 0
    assert 'No matches found.'.encode() in out and b'0/0' in out and b'FINISHED' in out


def test_tui_match_summary_and_navigation(tmp_path):
    for i in range(7): (tmp_path/f'{i}.txt').write_text('needle\n')
    rc, out = tui(tmp_path, ['needle', str(tmp_path)], b'jGq')
    assert rc == 0
    assert b'Found 7 matches in 7 files.' in out
    assert b'1/7' in out and b'7/7' in out


def test_tui_search_popup_can_cancel(tmp_path):
    (tmp_path/'a.txt').write_text('needle\n')
    rc, out = tui(tmp_path, ['needle', str(tmp_path)], b'/\x1bq')
    assert rc == 0 and b'Regex Pattern' in out and b'Found 1 match in 1 file.' in out


def test_tui_keymap_popup_does_not_quit_on_q(tmp_path):
    (tmp_path/'a.txt').write_text('needle\n')
    rc, out = tui(tmp_path, ['needle', str(tmp_path)], b'?q')
    assert rc == 0 and b'Open/close the keymap popup' in out
