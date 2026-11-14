import os
import re
import subprocess
from pathlib import Path

EXE = Path('/workspace/executable')
HELP = """Usage: executable [OPTIONS] [FILENAME]

Arguments:
  [FILENAME]  Profile data filename

Options:
      --sorted   Whether to sort the stacks by time spent
      --echo     Print data to stdout on exit. Useful when piping to other tools
      --debug    Show debug info
  -h, --help     Print help
  -V, --version  Print version
"""


def run(args=(), data=b'', timeout=4):
    return subprocess.run([str(EXE), *map(str, args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout)


def test_long_help_exact():
    p = run(['--help'])
    assert p.returncode == 0
    assert p.stdout.decode() == HELP
    assert p.stderr == b''


def test_short_help_interface():
    p = run(['-h'])
    assert p.returncode == 0 and p.stderr == b''
    assert 'Usage: executable [OPTIONS] [FILENAME]' in p.stdout.decode()
    assert '[FILENAME]  Profile data filename' in p.stdout.decode()


def test_version_flags_exact():
    for flag in ('--version', '-V'):
        p = run([flag])
        assert p.returncode == 0 and p.stdout == b'flamelens 0.3.1\n' and p.stderr == b''


def test_version_is_immediate_and_ignores_later_arguments():
    p = run(['--debug', '--version', '--nonsense', 'one', 'two'])
    assert p.returncode == 0 and p.stdout == b'flamelens 0.3.1\n' and p.stderr == b''


def _syntax(args, *needles):
    p = run(args)
    assert p.returncode == 2 and p.stdout == b''
    err = p.stderr.decode(errors='replace')
    assert err.startswith('error:')
    assert "For more information, try '--help'." in err
    assert 'Usage: executable [OPTIONS] [FILENAME]' in err
    for needle in needles:
        assert needle in err


def test_unknown_long_option_diagnostic():
    _syntax(['--nonexistent'], '--nonexistent', 'did you mean', '--')


def test_unknown_short_option_diagnostic():
    _syntax(['-x'], '-x')


def test_rejects_second_positional():
    _syntax(['one', 'two'], 'unexpected argument', 'two')


def test_rejects_unsupported_output_forms():
    _syntax(['--output', 'x'], '--output')
    _syntax(['-o', 'x'], '-o')


def test_rejects_boolean_attached_value_with_special_usage():
    p = run(['--sorted=1'])
    assert p.returncode == 2 and p.stdout == b''
    err = p.stderr.decode(errors='replace')
    assert err.startswith('error:') and "unexpected value '1'" in err
    assert 'no more were expected' in err
    assert 'Usage: executable --sorted [FILENAME]' in err
    assert "For more information, try '--help'." in err


def test_sorted_echo_still_preserves_original_text_and_appends_newline():
    src = b'# header\na; b 4\ninvalid\na 2'
    p = run(['--sorted', '--echo'], data=src)
    assert p.stdout == src + b'\n'
    assert p.returncode == 1
    err = p.stderr.decode(errors='replace')
    assert 'Error: Os' in err and 'kind:' in err


def test_echo_adds_extra_newline_even_when_input_has_newline():
    src = b'a 1\n'
    p = run(['--echo'], data=src)
    assert p.stdout == src + b'\n'
    assert p.returncode == 1


def test_non_tty_stdin_fails_promptly_without_echo_output():
    p = run(data=b'a 1\n', timeout=3)
    assert p.returncode == 1 and p.stdout == b''
    err = p.stderr.decode(errors='replace')
    assert 'Error: Os' in err and 'kind:' in err


def test_empty_stdin_and_sorted_empty_stdin_fail_promptly():
    for args in ([], ['--sorted']):
        p = run(args, timeout=3)
        assert p.returncode == 1 and p.stdout == b''
        err = p.stderr.decode(errors='replace')
        assert 'Error: Os' in err and 'kind:' in err


def test_missing_file_reports_panic_style_not_found():
    missing = '/workspace/eval/no-such-profile.folded'
    p = run([missing])
    err = p.stderr.decode(errors='replace')
    assert p.returncode == 101 and p.stdout == b''
    assert re.search(r"thread 'main' \([0-9]+\) panicked at src/main.rs:", err)
    assert 'Could not read file:' in err and 'NotFound' in err
    assert 'No such file or directory' in err


def test_invalid_utf8_file_is_read_failure():
    path = Path('/workspace/eval/invalid-utf8.folded')
    path.write_bytes(b'a 1\n\xff')
    try:
        p = run([path])
    finally:
        path.unlink(missing_ok=True)
    err = p.stderr.decode(errors='replace')
    assert p.returncode == 101 and p.stdout == b''
    assert 'Could not read file:' in err and 'InvalidData' in err and 'UTF-8' in err


def test_invalid_utf8_stdin_is_panic_style_parse_failure():
    p = run(data=b'\xff')
    err = p.stderr.decode(errors='replace')
    assert p.returncode == 101 and p.stdout == b''
    assert re.search(r"thread 'main' \([0-9]+\) panicked at src/main.rs:", err)
    assert 'Could not parse stdin:' in err


def test_double_dash_ends_option_parsing_for_dashed_filename():
    path = Path('/workspace/eval/-profile.folded')
    path.write_text('a 1\n', encoding='utf-8')
    try:
        p = subprocess.run([str(EXE), '--', '-profile.folded'], cwd='/workspace/eval',
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
    finally:
        path.unlink(missing_ok=True)
    assert p.returncode == 1 and p.stdout == b''
    assert b'Error: Os' in p.stderr and b'kind:' in p.stderr
