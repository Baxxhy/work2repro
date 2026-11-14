import os
import re
import subprocess
from pathlib import Path

import pytest

E = Path('/workspace/executable')


def run(args=(), data=None, env=None, cwd=None, timeout=8):
    base = {**os.environ, 'NO_COLOR': '1'}
    if env:
        base.update(env)
    return subprocess.run([str(E), *map(str, args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=base, cwd=cwd, timeout=timeout)


def test_version_exact():
    p = run(['--version'])
    assert (p.returncode, p.stdout, p.stderr) == (0, b'tspin 5.6.0\n', b'')


def test_help_documents_interface():
    p = run(['--help'])
    assert p.returncode == 0 and p.stderr == b''
    assert b'A log file highlighter\n\nUsage: executable [OPTIONS] [FILE]' in p.stdout
    assert all(x in p.stdout for x in (b'--config-path', b'--highlight', b'--disable-builtin-keywords', b'--pager'))
    assert b'Commands:' not in p.stdout and b'\x1b' not in p.stdout


@pytest.mark.parametrize('args', [('--bad-option',), ('--follow=true',), ('--exec',), ('--pager',), ('--config-path',), ('--highlight',), ('a','b')], ids=['unknown','switch-value','missing-exec','missing-pager','missing-config','missing-highlight','extra-file'])
def test_cli_syntax_errors(args):
    p = run(args)
    assert p.returncode == 2 and p.stdout == b'' and p.stderr.startswith(b'error:')


def test_highlighter_selection_choices_and_conflict():
    p = run(['--enable','nope'])
    assert p.returncode == 2 and b'possible values: numbers, urls, pointers' in p.stderr and b'similar value exists' in p.stderr
    p = run(['--enable','dates','--disable','json'], data=b'x\n')
    assert p.returncode == 1 and b'cannot both enable and disable highlighters' in p.stderr


def test_file_precedence_and_line_conventions(tmp_path):
    f = tmp_path / 'plain.log'
    f.write_bytes(b'abc\ndef')
    p = run(['--print', str(f)], data=b'ignored\n')
    assert p.returncode == 0 and p.stdout == b'abc\n'
    f.write_bytes(b'cr\r\n')
    assert run(['-p', f]).stdout == b'cr\n'
    f.write_bytes(b'')
    assert run(['-p', f]).stdout == b'\n'


def test_stdin_line_conventions_and_preservation():
    assert run(['--print'], b'abc').stdout == b'abc\n'
    assert run([], b'').stdout == b''
    payload = b'\t\n\nhello\x00\xe2\x98\x83\n'
    p = run(['--print', '--enable', 'json', '--disable-builtin-keywords'], payload)
    assert re.sub(rb'\x1b\[[0-9;]*m', b'', p.stdout) == payload


def test_missing_file_and_directory(tmp_path):
    missing = str(tmp_path / 'missing file')
    p = run(['--print', missing])
    assert p.returncode == 1 and p.stdout == b'' and missing.encode() in p.stderr
    p = run(['--print', tmp_path])
    assert p.returncode == 1 and p.stderr == 'Error:   × Path is not a file\n\n'.encode()


def test_piped_input_beats_exec_and_pager():
    p = run(['--exec','definitely-nonexistent-command','--pager','definitely-no-pager'], b'piped stdin\n')
    assert (p.returncode, p.stdout, p.stderr) == (0, b'piped stdin\n', b'')


def test_exec_print_without_input_is_empty():
    p = run(['--exec','false','--print'])
    assert (p.returncode, p.stdout, p.stderr) == (0, b'', b'')


def test_builtin_keywords_and_disable():
    p = run(['--print'], b'null TRUE true INFO WARNING GET HEAD\n')
    for x in (b'\x1b[3;31mnull\x1b[0m', b'TRUE', b'\x1b[37mINFO\x1b[0m', b'WARNING', b'\x1b[42;30m GET \x1b[0m', b'HEAD'):
        assert x in p.stdout
    p = run(['--print','--disable-builtin-keywords'], b'null INFO GET\n')
    assert p.stdout == b'null INFO GET\n'


def test_custom_literal_keywords():
    p = run(['--print','--highlight','red:a.b,$x','--highlight','blue:a.b'], b'a.b testing $x\n')
    assert b'\x1b[31ma.b\x1b[0m' in p.stdout and b'\x1b[31m$x\x1b[0m' in p.stdout
    assert b'testing' in p.stdout


def test_numbers_and_disable():
    p = run(['--print'], b'Numbers 123 45.67 -42 .5 a123b\n')
    for x in (b'\x1b[36m123\x1b[0m', b'\x1b[36m45.67\x1b[0m', b'-\x1b[36m42\x1b[0m', b'.\x1b[36m5\x1b[0m'):
        assert x in p.stdout
    assert b'a123b' in p.stdout
    assert run(['--print','--disable','numbers'], b'123\n').stdout == b'123\n'


def test_structural_groups_toggle():
    p = run(['--print','--enable','paths,urls'], b'/a/b https://example.org/a\n')
    assert b'\x1b[33m/\x1b[0m' in p.stdout and b'\x1b[2;32mhttps\x1b[0m' in p.stdout
    p = run(['--print','--disable','urls,paths,key-value-pairs'], b'https://example.org/a\n')
    assert p.stdout == b'https://example.org/a\n'


def test_dates_uuids_ips_pointers_processes_quotes_keyvalues():
    p = run(['--print'], b'2024-01-01T00:00:00Z 550e8400-e29b-41d4-a716-446655440000 0.0.0.0 0x12345678 nginx[123] key=value "hello"\n')
    for x in (b'\x1b[35m2024\x1b[0m', b'\x1b[31m-\x1b[0m', b'\x1b[3;34m5\x1b[0m', b'\x1b[33mnginx\x1b[0m', b'\x1b[2mkey\x1b[0m', b'\x1b[33m"hello"\x1b[0m'):
        assert x in p.stdout


def test_json_compacts_and_preserves_more_specific_keywords():
    p = run(['--print'], b'{"outer":{"items":[1,true,null,"x"]}}\n')
    visible = p.stdout.replace(b'\x1b[0m', b'')
    assert b'{ "outer": { "items": [ 1, true, null, "x" ] } }' in visible
    assert b'\x1b[3;31mtrue\x1b[0m' in p.stdout


def test_theme_overrides_and_custom_rules(tmp_path):
    theme = tmp_path / 'theme.toml'
    theme.write_text('[numbers]\nnumber={fg="red"}\n[[keywords]]\nwords=["ALERT"]\nstyle={fg="green",bold=true}\n[[regexes]]\nregex=\'Started (.*)\\.\'\nstyle={fg="blue"}\n')
    p = run(['--print','--config-path',theme], b'123 ALERT Started service.\n')
    assert b'\x1b[31m123\x1b[0m' in p.stdout
    assert b'\x1b[1;32mALERT\x1b[0m' in p.stdout
    assert b'Started \x1b[34mservice\x1b[0m.' in p.stdout


def test_bad_config_is_runtime_error(tmp_path):
    p = run(['--print','--config-path',tmp_path/'absent.toml'], b'123\n')
    assert p.returncode == 1 and p.stdout == b'' and p.stderr == 'Error:   × could not find the TOML file\n\n'.encode()
    f = tmp_path/'bad.toml'; f.write_text('[numbers]\nnumber="red"\n')
    p = run(['--print','--config-path',f], b'123\n')
    assert p.returncode == 1 and b'TOML parse error' in p.stderr and p.stdout == b''


def test_completion_generation_precedes_bad_input():
    for shell, marker in [('bash','_tspin()'),('fish','complete -c tspin'),('zsh','#compdef tspin')]:
        p = run(['--generate-'+shell+'-completions','/missing'])
        assert p.returncode == 0 and p.stderr == b'' and marker.encode() in p.stdout
        assert b'--enable' in p.stdout and b'numbers' in p.stdout and p.stdout.endswith(b'\n')
