import json
import os
import pty
import re
import select
import signal
import struct
import subprocess
import termios
import time
import fcntl
from pathlib import Path

import pytest


BIN = Path('/workspace/executable')
EVAL = Path(__file__).resolve().parent


def run(args=(), data=None, env=None, timeout=4):
    e = os.environ.copy()
    e.update({'TERM': 'xterm', 'HOME': str(EVAL), 'XDG_CONFIG_HOME': str(EVAL / 'empty-config')})
    if env:
        e.update(env)
    return subprocess.run([str(BIN), *map(str, args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=e, timeout=timeout)


def config(contents, suffix='.json'):
    p = EVAL / ('case' + suffix)
    p.write_text(contents, encoding='utf-8')
    return str(p)


def tui(args, data, keys, timeout=5):
    """Run with pipes for data/result and a separate controlling terminal for keys."""
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 25, 80, 0, 0))
    env = os.environ.copy()
    env.update({'TERM': 'xterm', 'HOME': str(EVAL), 'XDG_CONFIG_HOME': str(EVAL / 'empty-config')})
    proc = subprocess.Popen([str(BIN), *map(str, args)], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                            pass_fds=(slave,), preexec_fn=lambda: (os.setsid(), fcntl.ioctl(slave, termios.TIOCSCTTY, 0)))
    os.close(slave)
    try:
        proc.stdin.write(data)
        proc.stdin.close()
        proc.stdin = None
        time.sleep(.18)
        os.write(master, keys)
        out, err = proc.communicate(timeout=timeout)
        return proc.returncode, out, err
    finally:
        os.close(master)
        if proc.poll() is None:
            proc.kill()


def test_help_format_and_option_coverage():
    p = run(['--help'])
    assert p.returncode == 0
    s = p.stdout.decode(errors='replace')
    assert s.startswith('\nUsage: peco [options] [FILE]\n\nOptions:\n')
    assert s.endswith('\n') and '\x1b' not in s
    for phrase in ['show this help message and exit', 'initial value for query', 'path to the settings file',
                   'print the version and exit', 'number of lines to keep in search buffer',
                   'expect NUL (\\0) as separator for target/output', 'position of the initial index',
                   'specify the default filter', 'specify the prompt string', 'layout to be used',
                   'select first item', 'exit immediately', 'select all items',
                   'specify action on user cancel', 'use a prefix', 'execute command instead of finishing/terminating peco',
                   'print out the current query', 'enable ANSI color code support', 'display height',
                   'top-down-query-bottom', "executed via '/bin/sh -c'", "'cmd /c'"]:
        assert phrase in s
    assert '  -b, --buffer-size     number of lines to keep in search buffer' in s


def test_help_alias_and_valid_options_do_not_change_help():
    a = run(['-h']).stdout
    b = run(['--query', 'x', '--layout=bottom-up', '--help']).stdout
    assert a == b


def test_unknown_option_even_with_help():
    p = run(['--help', '--bogus'])
    assert p.returncode == 1
    e = p.stderr.decode(errors='replace')
    assert "unknown flag `bogus'" in e and 'Usage: peco [options] [FILE]' in e
    assert 'Error: failed to setup peco' in e


def test_version_shape_and_ignores_missing_config():
    p = run(['--rcfile', str(EVAL / 'missing'), '--version'])
    assert p.returncode == 0
    assert re.fullmatch(rb'peco version v0\.5\.\d+ \(built with go\d+\.\d+(?:\.\d+)?\)\n', p.stdout)


def test_double_dash_is_ignored_and_options_after_file_are_parsed():
    p = run(['--', '--version'])
    assert p.returncode == 0 and re.fullmatch(rb'peco version v0\.5\.\d+ \(built with go\d+\.\d+(?:\.\d+)?\)\n', p.stdout)
    first = EVAL / 'first-file'
    second = EVAL / 'second-file'
    first.write_bytes(b'first\n')
    second.write_bytes(b'second\n')
    q = run([str(first), str(second), '--select-all'])
    assert q.returncode == 0 and q.stdout == b'first\n'


@pytest.mark.parametrize('args,needle', [
    (['--query'], "expected argument for flag `--query'"),
    (['-b'], "expected argument for flag `-b, --buffer-size'"),
    (['--height', '-5'], "expected argument for flag `--height', but got option `-5'"),
    (['--bogus'], "unknown flag `bogus'"),
    (['-Z'], "unknown flag `Z'"),
    (['--initial-index=x'], "invalid argument for flag `--initial-index' (expected int):"),
    (['-bn'], "invalid argument for flag `-b, --buffer-size' (expected int):"),
    (['--layout=sideways'], "unknown layout: 'sideways'"),
])
def test_invalid_cli_arguments(args, needle):
    p = run(args)
    assert p.returncode == 1
    assert needle in p.stderr.decode(errors='replace')
    assert 'Error: failed to setup peco' in p.stderr.decode(errors='replace')


def test_on_cancel_validation_diagnostic():
    p = run(['--on-cancel', 'invalid-value'])
    assert p.returncode == 1
    assert p.stderr.decode(errors='replace').strip().endswith(
        'Error: failed to setup peco: failed to apply configuration: invalid --on-cancel value: invalid OnCancel value "invalid-value": must be "success" or "error"')


def test_stdin_without_data_fails_but_empty_file_is_valid():
    p = run([], b'')
    assert p.returncode == 1
    assert b'you must supply something to work with via filename or stdin' in p.stderr
    empty = EVAL / 'empty-input'
    empty.write_bytes(b'')
    q = run(['--exit-0', str(empty)])
    assert q.returncode == 1 and q.stdout == b''


def test_bad_file_reports_path():
    missing = str(EVAL / 'no-such-input')
    p = run([missing])
    assert p.returncode == 1
    assert b'failed to open file for input' in p.stderr and missing.encode() in p.stderr


def test_select_all_preserves_records_and_newline_semantics():
    p = run(['--select-all'], b' first \r\n\nsecond\t!\rthird')
    assert p.returncode == 0
    assert p.stdout == b' first \n\nsecond\t!\nthird\n'


def test_select_all_handles_bom_unicode_and_invalid_utf8_safely():
    p = run(['--select-all'], b'\xef\xbb\xbffirst\n\xf0\x9f\x8c\x8f e\xcc\x81\n\xffbad\n')
    assert p.returncode == 0
    assert p.stdout.startswith(b'\xef\xbb\xbffirst\n')
    assert b'\xffbad\n' in p.stdout or '\ufffdbad\n'.encode() in p.stdout


def test_select_all_with_null_splits_first_nul_and_preserves_result_bytes():
    p = run(['--null', '--select-all'], b'view\0out\0tail\n\0empty-display\nno-nul\n')
    assert p.returncode == 0
    assert p.stdout == b'out\0tail\nempty-display\nno-nul\n'


def test_ansi_mode_searchable_text_and_selected_output_bytes():
    record = b'\x1b[31mred\x1b[0m plain\n'
    p = run(['--ansi', '--select-all'], record)
    assert p.returncode == 0 and p.stdout == record
    q = run(['--ansi', '--null', '--select-all'], b'red\x1b[31m\0out\x1b[0m\n')
    assert q.returncode == 0 and q.stdout == b'out\x1b[0m\n'
    # Escape sequences are stripped from output when ANSI interpretation is disabled.
    r = run(['--select-all'], record)
    assert r.returncode == 0 and r.stdout == b'red plain\n'


def test_select_one_is_based_on_source_count_and_prints_query():
    p = run(['--select-1', '--query=does-not-match', '--print-query'], b'only\n')
    assert p.returncode == 0 and p.stdout == b'does-not-match\nonly\n'
    q = run(['--select-1', '--query=banana'], b'apple\nbanana\npear\n')
    # More than one source record must enter the TUI, even if query leaves one match.
    assert q.returncode == 1 and b'failed to initialize screen' in q.stderr


def test_exit_zero_name_means_empty_is_failure_and_nonempty_is_not_auto_selected():
    p = run(['--exit-0'], b'')
    assert p.returncode == 1 and p.stdout == b''
    q = run(['--exit-0'], b'a\nb\n')
    assert q.returncode == 1 and b'failed to initialize screen' in q.stderr


def test_select_all_only_shortcuts_for_empty_query():
    p = run(['--select-all', '--query=b'], b'a\nb\n')
    assert p.returncode == 1 and b'failed to initialize screen' in p.stderr
    q = run(['--select-all'], b'')
    assert q.returncode == 0 and q.stdout == b''


def test_buffer_size_retains_latest_records_and_cli_last_wins():
    data = ''.join(f'{i}\n' for i in range(1, 21)).encode()
    p = run(['-b10', '--buffer-size=3', '--select-all'], data)
    assert p.returncode == 0 and p.stdout == b'18\n19\n20\n'
    q = run(['--buffer-size=0', '--select-all'], data)
    assert q.stdout == data


def test_print_query_exact_and_empty_query_leading_line():
    p = run(['--print-query', '--select-all'], b'a\nb')
    assert p.stdout == b'\na\nb\n'
    q = run(['--print-query', '--select-1', '--query', r'  x\\☃  '], b'one')
    assert q.stdout == '  x\\☃  \none\n'.encode()


@pytest.mark.parametrize('value,fragment', [
    ('invalid', 'invalid height specification: "invalid"'),
    ('0', 'height must be positive: "0"'),
    ('0%', 'height percentage must be positive: "0%"'),
    ('-50%', 'height percentage must be positive: "-50%"'),
    ('101%', 'height percentage must not exceed 100: "101%"'),
    ('1.5', 'invalid height specification: "1.5"'),
    ('50%%', 'invalid height specification: "50%%"'),
])
def test_invalid_height_values(value, fragment):
    p = run(['--height', value])
    assert p.returncode == 1 and fragment in p.stderr.decode(errors='replace')


def test_config_explicit_missing_and_invalid_formats():
    missing = str(EVAL / 'absent-config.json')
    p = run(['--rcfile', missing, '--version'])
    # Version is processed before configuration.
    assert p.returncode == 0
    q = run(['--rcfile', missing, '--select-all'], b'x\n')
    assert q.returncode == 1 and b'failed to read config file' in q.stderr
    zero = config('', '.json')
    r = run(['--rcfile', zero, '--select-all'], b'x\n')
    assert r.returncode == 1 and b'failed to decode JSON' in r.stderr


def test_config_json_yaml_and_cli_override():
    j = config('{"Prompt":"JSON>","Layout":"bottom-up","Unknown":true}')
    p = run(['--rcfile', j, '--select-all', '--prompt=CLI>'], b'a\nb\n')
    assert p.returncode == 0 and p.stdout == b'a\nb\n'
    y = config('Prompt: YAML>\nLayout: top-down\n', '.yaml')
    q = run(['--rcfile', y, '--select-all'], b'z\n')
    assert q.returncode == 0 and q.stdout == b'z\n'


def test_config_invalid_value_and_keymap_type_errors():
    p = run(['--rcfile', config('{"Layout":"invalid-layout-name"}')], b'x\n')
    assert p.returncode == 1 and b'invalid layout type: invalid-layout-name' in p.stderr
    q = run(['--rcfile', config('{"Keymap":{"Enter":{}}}')], b'x\n')
    assert q.returncode == 1 and b'cannot unmarshal object into Go struct field Config.Keymap of type string' in q.stderr


def test_invalid_initial_filter_is_reported_during_setup():
    p = run(['--initial-filter=NoSuchFilter'], b'x\n')
    assert p.returncode == 1
    assert b'failed to set filter: specified filter was not found' in p.stderr


def test_config_bad_json_and_unknown_action_are_setup_errors():
    p = run(['--rcfile', config('{"Prompt":,}')], b'x\n')
    assert p.returncode == 1 and b'failed to decode JSON' in p.stderr
    q = run(['--rcfile', config('{"Keymap":{"F1":"peco.NoSuchAction"}}')], b'x\n')
    assert q.returncode == 1 and b'could not resolve peco.NoSuchAction: no such action' in q.stderr


def test_tui_finish_selects_current_record_and_cancel_is_empty():
    rc, out, _ = tui([], b'apple\nbanana\ncherry\n', b'\x0e\r')
    assert rc == 0 and out == b'banana\n'
    rc, out, _ = tui(['--print-query'], b'apple\nbanana\n', b'\x1b')
    assert rc == 0 and out == b''


def test_tui_on_cancel_error_and_query_filtering():
    rc, out, _ = tui(['--on-cancel=error'], b'a\nb\n', b'\x1b')
    assert rc == 1 and out == b''
    rc, out, _ = tui(['--query=ban'], b'apple\nbanana\n', b'\r')
    assert rc == 0 and out == b'banana\n'


def test_tui_selection_output_is_source_order_and_does_not_add_cursor():
    # C-v is rebound to ToggleSelection; move to third then second to prove source ordering.
    rcfile = config('{"Keymap":{"C-v":"peco.ToggleSelection"}}')
    rc, out, _ = tui(['--rcfile', rcfile], b'a\nb\nc\n', b'\x0e\x16\x0e\x16\r')
    assert rc == 0 and out == b'b\nc\n'


def test_tui_query_terms_and_case_sensitive_filter():
    rc, out, _ = tui(['--query=red -fox'], b'red fox\nred dog\nblue dog\n', b'\r')
    assert rc == 0 and out == b'red dog\n'
    rc, out, _ = tui(['--query=abc', '--initial-filter=CaseSensitive'], b'ABC\nabc\n', b'\r')
    assert rc == 0 and out == b'abc\n'


def test_tui_regex_and_fuzzy_filters():
    rc, out, _ = tui(['--query=^a.*z$', '--initial-filter=Regexp'], b'axz\naZZz\n', b'\r')
    assert rc == 0 and out == b'axz\n'
    rc, out, _ = tui(['--query=abc', '--initial-filter=Fuzzy'], b'a---b---c\nacb\n', b'\r')
    assert rc == 0 and out == b'a---b---c\n'


def test_no_tty_and_unset_term_diagnostics():
    p = run(['--query=x'], b'a\n', env={'TERM': ''})
    assert p.returncode == 1 and b'terminal entry not found: term not set' in p.stderr
    # Valid TERM but no controlling terminal is different from missing TERM.
    q = subprocess.run([str(BIN), '--query=x'], input=b'a\n', stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, env={**os.environ, 'TERM': 'xterm', 'HOME': str(EVAL),
                                                    'XDG_CONFIG_HOME': str(EVAL / 'empty-config')})
    assert q.returncode == 1 and b'open /dev/tty: no such device or address' in q.stderr
