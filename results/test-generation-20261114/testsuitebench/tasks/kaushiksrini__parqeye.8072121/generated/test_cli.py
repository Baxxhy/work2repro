import os
import subprocess
from pathlib import Path

import pytest


EXEC = Path('/workspace/executable')
HELP = ("Command line tool to visualize parquet files\n\n"
        "Usage: executable <PATH>\n\n"
        "Arguments:\n  <PATH>  Path to the parquet file\n\n"
        "Options:\n  -h, --help     Print help\n  -V, --version  Print version\n")
VERSION = "parqeye 0.0.2\n"


def invoke(*args, cwd='/workspace', env=None, stdin=None, timeout=3):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run([str(EXEC), *args], cwd=cwd, env=merged,
                          input=stdin, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout)


def test_both_help_spellings_are_exact_immediate_actions():
    for option in ('-h', '--help'):
        p = invoke(option, 'does-not-exist')
        assert (p.returncode, p.stdout, p.stderr) == (0, HELP.encode(), b'')
        assert b'\x1b' not in p.stdout


def test_help_position_and_precedence():
    for args in [('--help', 'x'), ('x', '--help'), ('--help', '--version')]:
        p = invoke(*args)
        assert (p.returncode, p.stdout, p.stderr) == (0, HELP.encode(), b'')
    p = invoke('--foo', '--help')
    assert p.returncode == 2 and p.stdout == b'' and b"unexpected argument '--foo' found" in p.stderr


def test_both_version_spellings_are_exact_and_ignore_trailing_values():
    for args in [('-V',), ('--version',), ('--version', 'extra')]:
        p = invoke(*args, env={'PARQUET_TEST_DATA': 'invalid'})
        assert (p.returncode, p.stdout, p.stderr) == (0, VERSION.encode(), b'')


@pytest.mark.parametrize('option', ['-H', '--HELP', '--VERSION'], ids=['capital-short-help','capital-help','capital-version'])
def test_options_are_case_sensitive(option):
    p = invoke(option)
    assert p.returncode == 2 and p.stdout == b''
    assert f"unexpected argument '{option}' found".encode() in p.stderr


def test_required_path_diagnostics_including_separator():
    expected = ("error: the following required arguments were not provided:\n  <PATH>\n\n"
                "Usage: executable <PATH>\n\nFor more information, try '--help'.\n").encode()
    for args in [(), ('--',)]:
        p = invoke(*args)
        assert (p.returncode, p.stdout, p.stderr) == (2, b'', expected)


def test_extra_positional_is_second_even_with_more_values():
    p = invoke('first', 'second', 'third')
    expected = b"error: unexpected argument 'second' found\n\nUsage: executable <PATH>\n\nFor more information, try '--help'.\n"
    assert (p.returncode, p.stdout, p.stderr) == (2, b'', expected)


@pytest.mark.parametrize(('token','reported'), [('--unknown','--unknown'), ('--unknown=value','--unknown'), ('-file.parquet','-f'), ('--path=file.parquet','--path')], ids=['unknown','long-value','short-cluster','unsupported-path-option'])
def test_unknown_option_reports_expected_token(token, reported):
    p = invoke(token)
    assert p.returncode == 2 and p.stdout == b''
    assert f"unexpected argument '{reported}' found".encode() in p.stderr
    assert b"tip: to pass" in p.stderr and b"Usage: executable <PATH>" in p.stderr


def test_version_value_form_is_invalid():
    p = invoke('--version=1')
    assert p.returncode == 2 and p.stdout == b''
    assert p.stderr.startswith(b"error: unexpected value '1' for '--version' found")
    assert b"Usage: executable <PATH>" in p.stderr


def test_double_dash_literal_and_single_dash_are_paths():
    for path in ('--unknown', '-'):
        p = invoke('--', path)
        assert p.returncode != 2
        assert b'failed to initialize terminal' in p.stderr or b'Error:' in p.stderr
    p = invoke('-', stdin=b'PAR1xxxx')
    assert p.returncode != 0


def test_valid_syntax_requires_interactive_terminal_before_file_processing(tmp_path):
    file = tmp_path / 'anything.data'
    file.write_bytes(b'not parquet')
    p = invoke(str(file))
    assert p.returncode != 0 and p.returncode != 2
    assert b'panicked' in p.stderr and b'failed to initialize terminal' in p.stderr
    assert b'No such device or address' in p.stderr


def test_path_text_is_never_executed_and_missing_path_fails(tmp_path):
    marker = tmp_path / 'marker'
    name = f"$(touch {marker})"
    p = invoke(str(tmp_path / name))
    assert p.returncode != 0
    assert not marker.exists()


@pytest.mark.parametrize('payload', [b'', b'PAR1', b'garbage!!', b'PAR1PAR1', b'\x00'*32, b'\xff'*32, b'PAR1' + b'x'*20 + b'PAR1'], ids=['empty','short-magic','text','magic-only','zeros','ones','footer-missing-byte'])
def test_malformed_inputs_fail_nonzero_without_hanging(tmp_path, payload):
    f = tmp_path / 'bad.parquet'
    f.write_bytes(payload)
    p = invoke(str(f), timeout=2)
    assert p.returncode != 0


def test_directory_and_broken_symlink_fail_promptly(tmp_path):
    link = tmp_path / 'broken'
    link.symlink_to(tmp_path / 'absent')
    for target in (str(tmp_path), str(link)):
        p = invoke(target, timeout=2)
        assert p.returncode != 0


def test_relative_path_uses_cwd_and_does_not_modify_input(tmp_path):
    f = tmp_path / 'odd name ü.parquet'
    original = b'not a parquet file'
    f.write_bytes(original)
    p = invoke(f.name, cwd=str(tmp_path))
    assert p.returncode != 0
    assert f.read_bytes() == original


@pytest.mark.parametrize('value', ['', '   ', '/invalid/path'], ids=['empty','whitespace','invalid'])
def test_environment_does_not_change_immediate_actions(value):
    for option, expected in [('--help', HELP.encode()), ('--version', VERSION.encode())]:
        p = invoke(option, env={'PARQUET_TEST_DATA': value})
        assert (p.returncode, p.stdout, p.stderr) == (0, expected, b'')
