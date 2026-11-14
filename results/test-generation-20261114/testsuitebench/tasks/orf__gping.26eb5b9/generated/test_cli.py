import os
import subprocess
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent
PROGRAM = Path('/workspace/executable')


def run(*args, env=None, timeout=4):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run([str(PROGRAM), *args], text=True, capture_output=True,
                          env=merged, timeout=timeout)


HELP = """Ping, but with a graph.

Usage: executable [OPTIONS] [HOSTS_OR_COMMANDS]...

Arguments:
  [HOSTS_OR_COMMANDS]...  Hosts or IPs to ping, or commands to run if --cmd is provided. Can use cloud shorthands like aws:eu-west-1

Options:
      --cmd
          Graph the execution time for a list of commands rather than pinging hosts
  -n, --watch-interval <WATCH_INTERVAL>
          Watch interval seconds (provide partial seconds like '0.5'). Default for ping is 0.2, default for cmd is 0.5
  -b, --buffer <BUFFER>
          Determines the number of seconds to display in the graph [default: 30]
  -4
          Resolve ping targets to IPv4 address
  -6
          Resolve ping targets to IPv6 address
  -i, --interface <INTERFACE>
          Interface to use when pinging
  -s, --simple-graphics
          
      --vertical-margin <VERTICAL_MARGIN>
          Vertical margin around the graph (top and bottom) [default: 1]
      --horizontal-margin <HORIZONTAL_MARGIN>
          Horizontal margin around the graph (left and right) [default: 0]
  -c, --color <color>
          Assign color to a graph entry.
          
          This option can be defined more than once as a comma separated string, and the
          order which the colors are provided will be matched against the hosts or
          commands passed to gping.
          
          Hexadecimal RGB color codes are accepted in the form of '#RRGGBB' or the
          following color names: 'black', 'red', 'green', 'yellow', 'blue', 'magenta',
          'cyan', 'gray', 'dark-gray', 'light-red', 'light-green', 'light-yellow',
          'light-blue', 'light-magenta', 'light-cyan', and 'white'
      --clear
          Clear the graph from the terminal after closing the program
      --ping-args [<PING_ARGS>...]
          Extra arguments to pass to `ping`. These are platform dependent
  -h, --help
          Print help
  -V, --version
          Print version
"""


def test_help_long_is_exact():
    p = run('--help')
    assert p.returncode == 0 and p.stderr == ''
    assert p.stdout == HELP


def test_help_short_matches_long():
    p = run('-h')
    assert (p.returncode, p.stdout, p.stderr) == (0, HELP, '')


def test_help_is_immediate_but_unknown_before_help_is_error():
    assert run('--help', '--nonsense').stdout == HELP
    p = run('--nonsense', '--help')
    assert p.returncode != 0 and "error: unexpected argument '--nonsense' found" in p.stderr
    assert 'Usage:' in p.stderr and "For more information, try '--help'." in p.stderr


def test_version_forms():
    short = run('-V')
    assert (short.returncode, short.stderr, short.stdout) == (0, '', 'gping 1.20.1\n')
    long = run('--version')
    assert long.returncode == 0 and long.stderr == ''
    lines = long.stdout.splitlines()
    assert len(lines) == 4 and lines[0].startswith('gping ')
    assert lines[1].startswith('commit_hash: ') and lines[1][13:]
    assert lines[2].startswith('build_time: ') and lines[2][12:]
    assert lines[3].startswith('build_env: ') and lines[3][11:]


def test_missing_target_exact_error():
    p = run()
    assert p.returncode == 1
    assert p.stderr == 'Error: At least one host or command must be given (i.e gping google.com). Use --help for a full list of arguments.\n'


def test_ping_args_greedily_consumes_target():
    p = run('--ping-args', 'localhost')
    assert p.returncode == 1 and p.stderr.startswith('Error: At least one host or command')
    p = run('localhost', '--ping-args', '--', 'x')
    assert p.returncode == 1 and p.stderr.startswith('Error: At least one host or command')


@pytest.mark.parametrize('args,fragment', [
    (('-n', '-1', 'a'), "unexpected argument '-1' found"),
    (('--buffer', '-1', 'a'), "unexpected argument '-1' found"),
    (('--simple-graphics=1', 'a'), "unexpected value '1' for '--simple-graphics'"),
    (('--watch-interval',), "a value is required for '--watch-interval <WATCH_INTERVAL>'"),
    (('--buffer',), "a value is required for '--buffer <BUFFER>'"),
], ids=['negative-separated-watch', 'negative-separated-buffer', 'flag-value', 'missing-watch', 'missing-buffer'])
def test_option_parse_errors(args, fragment):
    p = run(*args)
    assert p.returncode != 0 and fragment in p.stderr


@pytest.mark.parametrize('value,reason', [
    ('abc', 'invalid float literal'), ('', 'cannot parse float from empty string')],
    ids=['text', 'empty'])
def test_watch_interval_float_validation(value, reason):
    p = run('--watch-interval='+value, 'x')
    assert p.returncode == 1
    assert f"error: invalid value '{value}' for '--watch-interval <WATCH_INTERVAL>': {reason}" in p.stderr


def test_watch_interval_accepts_numeric_edges_and_attached_negative():
    for v in ['0', '0.0001', '0.5', '2', '-1']:
        p = run('--watch-interval='+v, '--help')
        assert p.returncode == 0
    p = run('-n=-1', '127.0.0.1')
    assert p.returncode == 1 and 'No such device or address' in p.stderr


@pytest.mark.parametrize('value,reason', [
    ('abc', 'invalid digit found in string'), ('', 'cannot parse integer from empty string'),
    ('999999999999999999999999999', 'number too large to fit in target type'),
    ('-1', 'invalid digit found in string'),
], ids=['text', 'empty', 'overflow', 'negative-attached'])
def test_buffer_validation(value, reason):
    p = run('--buffer='+value, '127.0.0.1')
    assert p.returncode == 1 and f"error: invalid value '{value}' for '--buffer <BUFFER>': {reason}" in p.stderr


@pytest.mark.parametrize('opt,value,reason', [
    ('--vertical-margin', '-1', '-1 is not in 0..=65535'),
    ('--horizontal-margin', '65536', '65536 is not in 0..=65535'),
    ('--vertical-margin', '999999', '999999 is not in 0..=65535'),
    ('--horizontal-margin', 'x', 'invalid digit found in string'),
], ids=['vertical-negative', 'horizontal-overflow', 'vertical-overflow', 'horizontal-text'])
def test_margin_validation(opt, value, reason):
    p = run(opt+'='+value, '127.0.0.1')
    metavar = 'VERTICAL_MARGIN' if opt == '--vertical-margin' else 'HORIZONTAL_MARGIN'
    assert p.returncode == 1 and f"for '{opt} <{metavar}>': {reason}" in p.stderr


def test_family_exclusion_and_cmd_conflicts():
    p = run('-4', '-6', 'localhost')
    assert p.returncode != 0 and "the argument '-4' cannot be used with '-6'" in p.stderr
    p = run('--cmd', '--ping-args', 'x')
    assert p.returncode != 0 and "the argument '--cmd' cannot be used with '--ping-args [<PING_ARGS>...]'" in p.stderr
    p = run('--cmd', '--cmd', 'echo x')
    assert p.returncode != 0 and "the argument '--cmd' cannot be used multiple times" in p.stderr


def test_ipv4_ipv6_cluster_conflict():
    p = run('-46', 'localhost')
    assert p.returncode != 0 and "cannot be used with" in p.stderr


GOOD_COLORS = ['black','red','green','yellow','blue','magenta','cyan','gray','dark-gray','light-red','light-green','light-yellow','light-blue','light-magenta','light-cyan','white','#000000','#FFFFFF','#ff0000','#AbCdEf']

@pytest.mark.parametrize('color', GOOD_COLORS, ids=[f'color-{i}' for i in range(len(GOOD_COLORS))])
def test_valid_colors(color):
    p = run('--color='+color, '--help')
    assert p.returncode == 0

@pytest.mark.parametrize('color', ['', '   ', ',red', 'FF0000', '#FF', '#12345', '#GGGGGG', 'red;blue'], ids=['empty','spaces','leading-empty','no-hash','short-hex','five-hex','bad-hex','semicolon'])
def test_invalid_colors_exact(color):
    p = run('--color='+color, '--help')
    assert p.returncode == 1
    assert p.stderr == 'Error: Invalid color code: `'+color+'`\n\nCaused by:\n    Failed to parse Colors\n'


def test_color_split_trim_repeat_and_first_invalid():
    p = run('--color= red,,blue ', '--color=#AbCdEf', '--help')
    assert p.returncode == 0
    p = run('--color=invalid1,invalid2', '--help')
    assert p.returncode == 1 and 'Invalid color code: `invalid1`' in p.stderr


def test_cloud_expansion_precedes_resolution():
    cases = [('aws:us-east-1', 'ec2.us-east-1.amazonaws.com'),
             ('gcp:europe-west1', 'storage.europe-west1.rep.googleapis.com'),
             ('gcp:', 'cloud.google.com')]
    for shorthand, expanded in cases:
        p = run(shorthand)
        assert p.returncode == 1 and f'Error: Resolving {expanded}\n' in p.stderr


def test_cloud_expansion_preserves_extra_colon_and_case():
    p = run('aws:us-east-1:8080')
    assert p.returncode == 1 and 'Error: Resolving ec2.us-east-1:8080.amazonaws.com' in p.stderr
    p = run('AWS:us-east-1')
    assert p.returncode == 1 and 'Error: Resolving AWS:us-east-1' in p.stderr


@pytest.mark.parametrize('host', ['', '...', '-', 'bad host', 'bad!host', '999.999.999.999'], ids=['empty','dots','dash','space','punctuation','malformed-ip'])
def test_resolution_errors_are_safe_and_structured(host):
    p = run(host)
    assert p.returncode == 1 and f'Error: Resolving {host}\n\nCaused by:\n    failed to lookup address information:' in p.stderr


def test_idna_and_linux_resolver_messages():
    p = run('тест.example.com')
    assert p.returncode == 1 and 'Error: Resolving xn--e1aybc.example.com' in p.stderr
    assert 'No address associated with hostname' in p.stderr
    p = run('test_host.example.com')
    assert p.returncode == 1 and 'Error: Resolving test_host.example.com' in p.stderr
    assert 'No address associated with hostname' in p.stderr


def test_wrong_family_literal_errors():
    p = run('-4', '::1')
    assert p.returncode == 1 and p.stderr == "Error: Could not resolve '::1' to IPv4\n"
    p = run('-6', '127.0.0.1')
    assert p.returncode == 1 and p.stderr == "Error: Could not resolve '127.0.0.1' to IPv6\n"


def test_first_resolution_failure_stops_before_later_hosts():
    p = run('host1.invalid', '127.0.0.1')
    assert p.returncode == 1 and 'Error: Resolving host1.invalid' in p.stderr
    assert '127.0.0.1' not in p.stderr


def test_double_dash_makes_following_tokens_positional():
    p = run('--', '-n', '0.2', 'a')
    assert p.returncode == 1 and 'Error: Resolving -n' in p.stderr


def test_empty_command_legacy_panic():
    p = run('--cmd', '')
    assert p.returncode == 101 and p.stderr.startswith('\nthread \'main\' (')
    assert 'Must specify a command to watch\nnote: run with `RUST_BACKTRACE=1`' in p.stderr


def test_max_buffer_parses_then_panics_during_startup():
    p = run('--buffer=18446744073709551615', '127.0.0.1')
    assert p.returncode == 101
    assert p.stderr.startswith('\nthread \'main\' (')
    assert 'called `Result::unwrap()` on an `Err` value: OutOfRangeError(())' in p.stderr


def test_valid_ping_target_reaches_terminal_initialization_without_tty():
    p = run('127.0.0.1')
    assert p.returncode == 1
    assert p.stderr == 'Error: No such device or address (os error 6)\n'


def test_invalid_color_and_resolution_precede_terminal_initialization():
    p = run('--color=orange', '127.0.0.1')
    assert p.returncode == 1 and p.stderr.startswith('Error: Invalid color code: `orange`')
    p = run('--color=red', 'host1.invalid')
    assert p.returncode == 1 and p.stderr.startswith('Error: Resolving host1.invalid\n')


def test_double_dash_single_dash_positional():
    p = run('-')
    assert p.returncode == 1 and p.stderr.startswith('Error: Resolving -\n')


def test_repeated_watch_interval_is_rejected():
    p = run('--watch-interval=0.1', '-n=0.2', '127.0.0.1')
    assert p.returncode != 0 and 'cannot be used multiple times' in p.stderr
