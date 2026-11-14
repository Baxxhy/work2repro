import os
import re
import subprocess
import time
from pathlib import Path

import pytest

EXE = Path('/workspace/executable')


def run(*args, input=None, timeout=8, cwd=None, env=None):
    return subprocess.run([str(EXE), *map(str, args)], input=input, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout, cwd=cwd, env=env)


@pytest.mark.parametrize('flag', ['--help', '-h'], ids=['long-help', 'short-help'])
def test_help_exact(flag):
    p = run(flag)
    expected = """loop 0.6.1
Rich Jones <miserlou@gmail.com>
UNIX's missing `loop` command

USAGE:
    executable [FLAGS] [OPTIONS] [input]...

FLAGS:
    -D, --error-duration    Exit with timeout error code on duration
    -h, --help              Prints help information
    -l, --only-last         Only print the output of the last execution of the command
    -i, --stdin             Read from standard input
        --summary           Provide a summary
    -C, --until-changes     Keep going until the output changes
    -f, --until-fail        Keep going until the command exit status is non-zero
    -S, --until-same        Keep going until the output changes
    -s, --until-success     Keep going until the command exit status is zero
    -V, --version           Prints version information

OPTIONS:
    -b, --count-by <count_by>                Amount to increment the counter by [default: 1]
    -e, --every <every>                      How often to iterate. ex., 5s, 1h1m1s1ms1us [default: 1us]
        --for <ffor>                         A comma-separated list of values, placed into 4ITEM. ex., red,green,blue
    -d, --for-duration <for_duration>        Keep going until the duration has elapsed (example 1m30s)
    -n, --num <num>                          Number of iterations to execute
    -o, --offset <offset>                    Amount to offset the initial counter by [default: 0]
    -c, --until-contains <until_contains>    Keep going until the output contains this string
    -r, --until-error <until_error>          Keep going until the command exit status is the value given
    -m, --until-match <until_match>          Keep going until the output matches this regular expression
    -t, --until-time <until_time>            Keep going until a future time, ex. \"2018-04-20 04:20:00\" (Times in UTC.)

ARGS:
    <input>...    The command to be looped
"""
    # Help text's documented column positions are significant.
    # Correct alignment is checked exactly against the public contract.
    assert p.returncode == 0
    assert p.stdout == expected
    assert p.stderr == ''


def test_help_left_to_right_and_no_subcommands():
    p = run('--help', '--badflag')
    assert p.returncode == 0 and p.stderr == '' and 'COMMANDS:' not in p.stdout
    p = run('--badflag', '--help')
    assert p.returncode != 0 and "Found argument '--badflag'" in p.stderr


@pytest.mark.parametrize('flag', ['--version', '-V'], ids=['long-version', 'short-version'])
def test_version(flag):
    p = run(flag)
    assert (p.returncode, p.stdout, p.stderr) == (0, 'loop 0.6.1\n', '')


@pytest.mark.parametrize('args', [[], ['--num', '1'], ['']], ids=['no-args', 'controls-only', 'empty-command'])
def test_missing_command(args):
    p = run(*args)
    assert (p.returncode, p.stdout, p.stderr) == (0, 'No command supplied, exiting.\n', '')


def test_command_joining_options_and_shell():
    assert run('--num', '1', 'printf', 'hello').stdout == 'hello\n'
    assert run('--num', '1', 'printf hello').stdout == 'hello\n'
    assert run('--num', '1', 'printf', 'hi', '|', 'tr', 'a-z', 'A-Z').stdout == 'HI\n'
    assert run('--num', '1', '--', 'printf', '%s', '$((2+3))').stdout == '5\n'
    assert run('--num', '1', 'printf', 'x;', 'printf', 'y').stdout == 'xy\n'


def test_environment_cwd_and_redirection(tmp_path):
    env = os.environ.copy(); env['SUITE_VALUE'] = 'kept'
    p = run('--num', '1', 'printf', '$SUITE_VALUE > out', cwd=tmp_path, env=env)
    assert p.returncode == 0 and p.stdout == '' and (tmp_path / 'out').read_text() == 'kept'


def test_captured_output_stderr_normalization_and_exit_status():
    assert run('--num', '1', 'printf', 'hello').stdout == 'hello\n'
    assert run('--num', '2', 'printf', 'x').stdout == 'x\nx\n'
    assert run('--num', '1', 'printf', "'a\\n\\n'").stdout == 'a\n\n'
    p = run('--num', '1', 'printf', 'bad >&2; exit 42')
    assert (p.returncode, p.stdout, p.stderr) == (0, 'bad\n', '')


@pytest.mark.parametrize('value,count', [('2.5', 2), ('0', 0), ('-1', 0)], ids=['fractional', 'zero', 'negative-equals'])
def test_num_bounds(value, count):
    p = run('--num='+value, '--', 'printf', 'x')
    assert p.returncode == 0 and p.stdout == 'x\n' * count


def test_num_long_range_and_short_syntax():
    assert run('-ln', '1', '--', 'printf', 'x').stdout == 'x\n'
    assert run('-n=1', '--', 'printf', 'x').stdout == 'x\n'
    assert run('--num', '100', '--', 'true').returncode == 0
    for args in [('--num', '-1', 'true'), ('-n', '-2.9', 'true')]:
        p = run(*args)
        assert p.returncode != 0 and 'Found argument' in p.stderr


def test_for_item_delimiters_repeat_and_environment():
    assert run('--for', 'a,,c', '--', 'printf', '<%s>', '$ITEM').stdout == '<a>\n<>\n<c>\n'
    assert run('--for', 'one  two\nthree', '--', 'printf', '<%s>', '$ITEM').stdout == '<one  two>\n<three>\n'
    assert run('--for', 'a,b', '--num', '4', '--', 'printenv', 'ITEM').stdout == 'a\nb\nb\nb\n'
    assert run('--for=', '--', 'printenv', 'ITEM').stdout == '\n'
    assert run('--for', '雪,é', '--', 'printf', '%s', '$ITEM').stdout == '雪\né\n'


def test_stdin_items_and_empty_stdin():
    p = run('--stdin', '--', 'printf', '<%s>', '$ITEM', input='a b\r\n\n雪')
    assert p.returncode == 0 and p.stdout == '<a b>\n<>\n<雪>\n'
    assert run('--', 'printenv', 'ITEM', input='one\ntwo\n').stdout == 'one\ntwo\n'
    p = run('--stdin', '--num', '2', '--', 'printf', 'x', input='')
    assert p.returncode == 0 and p.stdout == 'x\nx\n'


def test_count_formatting_and_counter_variables():
    p = run('--num', '3', '--offset', '10', '--count-by', '2', '--', 'printf', '%s/%s', '$COUNT', '$ACTUALCOUNT')
    assert p.stdout == '10/0\n12/1\n14/2\n'
    assert run('--num', '3', '--count-by', '0.1', '--', 'printf', '%s', '$COUNT').stdout == '0.0\n0.1\n0.2\n'
    assert run('--num', '3', '--count-by', '1.50', '--', 'printf', '%s', '$COUNT').stdout == '0.00\n1.50\n3.00\n'
    assert run('--num', '3', '--count-by', '2.5e1', '--', 'printf', '%s', '$COUNT').stdout == '0.0\n25.0\n50.0\n'
    assert run('--num', '3', '--count-by', '1e-3', '--', 'printf', '%s', '$COUNT').stdout == '0\n0\n0\n'
    assert run('--num', '3', '--count-by', '0.123456789', '--', 'printf', '%s', '$COUNT').stdout == '0.000000000\n0.123456789\n0.246913578\n'
    assert run('--num', '3', '--offset', '0.5', '--', 'printf', '%s', '$COUNT').stdout == '0\n2\n2\n'


@pytest.mark.parametrize('args,option', [(['--num', 'x', 'true'], '--num'), (['--count-by', 'x', 'true'], '--count-by'), (['--offset', 'x', 'true'], '--offset')], ids=['bad-num', 'bad-step', 'bad-offset'])
def test_invalid_numeric_values(args, option):
    p = run(*args)
    assert p.returncode != 0 and option in p.stderr and p.stdout == ''


def test_duration_actual_pacing():
    start = time.monotonic(); p = run('--num', '3', '--every', '100ms', '--', 'true', timeout=3); elapsed = time.monotonic()-start
    assert p.returncode == 0 and 0.25 <= elapsed <= 0.8
    start = time.monotonic(); p = run('--for-duration', '0', '--', 'true'); elapsed = time.monotonic()-start
    assert p.returncode == 0 and elapsed < 0.2
    start = time.monotonic(); p = run('--every', '50ms', '--for-duration', '1s', '--summary', '--', 'true', timeout=3); elapsed = time.monotonic()-start
    assert p.returncode == 0 and 0.8 <= elapsed <= 1.4
    assert 'Total runs:\t' in p.stdout


def test_duration_error_status_and_num_precedence():
    p = run('--for-duration', '1ms', '--every', '10ms', '--error-duration', '--', 'true', timeout=2)
    assert p.returncode == 124
    p = run('--for-duration', '1ms', '--every', '10ms', '--num', '1', '--error-duration', '--', 'true', timeout=2)
    assert p.returncode == 0
    assert run('--error-duration', '--num', '1', '--', 'true').returncode == 0


def test_until_time_deadlines_and_validation():
    assert run('--until-time', '2000-01-01 00:00:00', '--', 'printf', 'x').stdout == ''
    deadline = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(time.time()+0.5)) + '.500Z'
    start=time.monotonic(); p=run('--until-time', deadline, '--summary', '--', 'true', timeout=3); elapsed=time.monotonic()-start
    assert p.returncode == 0 and elapsed >= 0.3 and 'Total runs:\t' in p.stdout
    for value, message in [('bad', 'timestamp format is invalid'), ('2024-13-01 00:00:00', 'numeric component is out of range'), ('2024-01-01T00:00:00+00:00', 'timestamp format is invalid')]:
        p=run('--until-time', value, '--', 'true')
        assert p.returncode != 0 and message in p.stderr and p.stdout == ''


def test_until_contains_literal_complete_captured_output():
    assert run('--num', '4', '--until-contains', '[3]', '--for', 'x,a [3] substring,z', '--', 'printf', '$ITEM').stdout == 'x\na [3] substring\n'
    p=run('--num', '3', '--until-contains', '[3] str', '--for', 'a [3] substring,b,c', '--', 'printf', '$ITEM')
    assert p.stdout == 'a [3] substring\nb\nc\n'
    assert run('--num', '3', '--until-contains', '', '--', 'printf', 'first').stdout == 'first\n'


def test_until_match_per_line_and_regex_features():
    p=run('--for', 'test,test space,testspace', '--until-match', r'test\s', '--', 'echo', '$ITEM')
    assert p.stdout == 'test\ntest space\n'
    assert run('--for', 'one\nPATTERN5\nthree', '--until-match', '^PATTERN5$', '--', 'printf', '$ITEM').stdout == 'one\nPATTERN5\n'
    assert run('--num', '3', '--until-match', 'q*', '--summary', '--', 'true').stdout.endswith('Total runs:\t3\nSuccesses:\t3\nFailures:\t0\n')
    assert run('--num', '3', '--until-match', 'x', '--for', 'x', '--', 'printf', '').stdout == '\n'
    p=run('--num', '1', '--until-match', '(', '--', 'true')
    assert p.returncode != 0 and p.stdout == '' and p.stderr


def test_until_changes_and_same_fixed_baseline():
    assert run('--num', '5', '--until-changes', '--', 'printf', '$ACTUALCOUNT').stdout == '0\n1\n'
    assert run('--num', '5', '--until-changes', '--', 'printf', 'same').stdout == 'same\nsame\n'
    assert run('--num', '5', '--until-same', '--', 'printf', 'same').stdout == 'same\nsame\n'
    assert run('--num', '4', '--until-same', '--', 'printf', 'x$ACTUALCOUNT').stdout == 'x0\nx1\nx2\nx3\n'
    assert run('--for', '1,2,3,4,5,5,6,7', '--until-same', '--only-last', '--', 'echo', '$ITEM').stdout == '7\n'
    p=run('--num', '4', '--until-same', '--summary', '--', 'if [ "$ACTUALCOUNT" = 0 ]; then printf first; else printf repeat; fi')
    assert p.stdout.endswith('Total runs:\t4\nSuccesses:\t4\nFailures:\t0\n')


def test_status_stops():
    p=run('--num', '5', '--until-success', '--summary', '--', 'test', '$ACTUALCOUNT', '-ge', '2')
    assert p.stdout.endswith('Total runs:\t3\nSuccesses:\t1\nFailures:\t2 (1, 1)\n')
    p=run('--num', '5', '--until-fail', '--summary', '--', 'test', '$ACTUALCOUNT', '-lt', '2')
    assert p.stdout.endswith('Total runs:\t3\nSuccesses:\t2\nFailures:\t1 (1)\n')
    p=run('--num', '5', '--until-error', '42', '--summary', '--', 'sh', '-c', 'if [ "$ACTUALCOUNT" = 2 ]; then exit 42; else exit 7; fi')
    assert p.returncode == 0 and p.stdout.endswith('Total runs:\t3\nSuccesses:\t0\nFailures:\t3 (7, 7, 42)\n')
    p=run('--num', '3', '--until-error', 'any', '--summary', '--', 'sh', '-c', 'if [ "$ACTUALCOUNT" = 0 ]; then exit 0; else exit 7; fi')
    assert p.stdout.endswith('Total runs:\t2\nSuccesses:\t1\nFailures:\t1 (7)\n')
    p=run('--num', '3', '--until-error', 'no-code', '--summary', '--', 'true')
    assert p.stdout.endswith('Total runs:\t3\nSuccesses:\t3\nFailures:\t0\n')


def test_only_last_and_summary_accounting():
    assert run('--num', '3', '--only-last', '--', 'printf', 'line%s\nsecond', '$ACTUALCOUNT').stdout == 'line2\nsecond\n'
    p=run('--num', '4', '--only-last', '--summary', '--', 'sh', '-c', 'if [ "$ACTUALCOUNT" = 1 ] || [ "$ACTUALCOUNT" = 3 ]; then exit 127; fi; printf run')
    assert p.stdout == 'run\nTotal runs:\t4\nSuccesses:\t2\nFailures:\t2 (127, 127)\n'
    assert run('--num', '0', '--summary', '--', 'true').stdout == 'Total runs:\t0\nSuccesses:\t0\nFailures:\t0\n'


@pytest.mark.parametrize('args,needle', [(['--badflag','true'], "Found argument '--badflag'"), (['--every','invalid','true'], 'expected number at 0'), (['--for-duration','notvalid','true'], 'expected number at 0'), (['--every','0.5s','true'], 'invalid character at 1'), (['--every','-5s','true'], "Found argument '-5' which wasn't expected")], ids=['unknown', 'bad-every', 'bad-duration', 'fraction-duration', 'negative-duration'])
def test_cli_diagnostics(args, needle):
    p=run(*args)
    assert p.returncode != 0 and needle in p.stderr and p.stdout == ''
    if args[0] == '--badflag':
        assert 'USAGE:' in p.stderr and 'For more information try --help' in p.stderr
