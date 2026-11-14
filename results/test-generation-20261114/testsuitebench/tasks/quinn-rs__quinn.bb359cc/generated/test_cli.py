import os
import subprocess
from pathlib import Path

import pytest

BIN = Path('/workspace/executable')
TOP = """Usage: executable <COMMAND>

Commands:
  server  Run as a perf server
  client  Run as a perf client
  help    Print this message or the help of the given subcommand(s)

Options:
  -h, --help  Print help
"""


def run(*args, timeout=5, env=None):
    e = os.environ.copy()
    e.pop('RUST_LOG', None)
    if env:
        e.update(env)
    return subprocess.run([str(BIN), *args], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout, env=e)


def test_no_args_exact_top_help_on_stderr():
    p = run()
    assert p.returncode == 2 and p.stdout == b'' and p.stderr.decode() == TOP


@pytest.mark.parametrize('args', [('--help',), ('-h',), ('help',), ('--help', '--unknown')],
                         ids=['long', 'short', 'help-command', 'help-precedence'])
def test_top_help_aliases(args):
    p = run(*args)
    assert p.returncode == 0 and p.stdout.decode() == TOP and p.stderr == b''


def test_option_terminator_does_not_make_help_a_flag():
    p = run('--', '--help')
    assert p.returncode == 2 and not p.stdout
    assert "unrecognized subcommand '--help'" in p.stderr.decode()


@pytest.mark.parametrize('args,usage', [
    (('server', '--unknown'), 'Usage: executable server [OPTIONS]'),
    (('client', '--unknown'), 'Usage: executable client [OPTIONS] [HOST]'),
    (('server', '--initial-mtu'), 'Usage: executable server [OPTIONS]'),
], ids=['server-unknown', 'client-unknown', 'missing-value'])
def test_cli_errors_stderr_only(args, usage):
    p = run(*args)
    assert p.returncode == 2 and p.stdout == b''
    assert p.stderr.decode().startswith('error:') and usage in p.stderr.decode()


@pytest.mark.parametrize('opt,val', [
    ('--download-size', '1.5M'), ('--upload-size', '-1'),
    ('--send-buffer-size', '1MB'), ('--recv-buffer-size', '1K'),
    ('--stream-receive-window', '1.2'), ('--receive-window', 'M'), ('--send-window', '1Gx'),
], ids=['download-decimal', 'upload-negative', 'send-buffer-unit', 'recv-buffer-case',
        'stream-window-decimal', 'receive-window-empty-number', 'send-window-suffix'])
def test_size_parser_rejects_invalid_forms(opt, val):
    p = run('client', f'{opt}={val}')
    s = p.stderr.decode()
    assert p.returncode == 2 and p.stdout == b'' and s.startswith('error: invalid value')
    assert "For more information, try '--help'." in s


@pytest.mark.parametrize('args', [
    ('server', '--listen=not-an-address'), ('client', '--local-addr=127.0.0.1'),
    ('client', '--ip=localhost'),
], ids=['listen-syntax', 'local-missing-port', 'ip-hostname'])
def test_socket_and_ip_validation(args):
    p = run(*args)
    assert p.returncode == 2 and p.stdout == b'' and 'invalid' in p.stderr.decode()


def test_unsigned_width_validation_and_congestion_enum():
    p = run('server', '--initial-mtu=65536')
    assert p.returncode == 2 and '65536 is not in 0..=65535' in p.stderr.decode()
    p = run('server', '--congestion=reno')
    assert p.returncode == 2 and '[possible values: cubic, bbr, new-reno]' in p.stderr.decode()


@pytest.mark.parametrize('opt,metavar', [('--listen', 'LISTEN'), ('--initial-mtu', 'INITIAL_MTU')],
                         ids=['listen', 'mtu'])
def test_duplicate_options_rejected(opt, metavar):
    val = '[::]:0' if opt == '--listen' else '1200'
    p = run('server', opt, val, opt, val)
    assert p.returncode == 2 and f"' {opt}" not in p.stderr.decode()
    assert f"the argument '{opt} <{metavar}>' cannot be used multiple times" in p.stderr.decode()


def test_cert_and_key_are_paired_during_cli_validation():
    p = run('server', '--cert=cert.pem')
    assert p.returncode == 2 and "a value is required" not in p.stderr.decode()
    assert '--key <KEY>' in p.stderr.decode()


def test_boolean_switch_rejects_equals_value():
    p = run('server', '--conn-stats=true')
    assert p.returncode == 2
    assert "unexpected value 'true' for '--conn-stats'" in p.stderr.decode()


def test_client_second_host_is_rejected():
    p = run('client', 'one.example:4433', 'two.example:4433')
    assert p.returncode == 2 and "unexpected argument 'two.example:4433'" in p.stderr.decode()

