import json
import math
import os
import re
import time


def test_version(invoke):
    r = invoke('--version')
    assert r.returncode == 0
    assert 'hyperfine' in r.stdout and '1.20.0' in r.stdout


def test_measured_runs_and_report(invoke):
    r = invoke('--runs=3', '--warmup=2', 'echo "hello world"')
    assert r.returncode == 0, r.stderr
    assert 'Benchmark 1: echo "hello world"' in r.stdout
    assert 'Time (mean ± σ):' in r.stdout and 'Range (min … max):' in r.stdout
    assert re.search(r'3 runs\s*\n ', r.stdout)
    assert '[User:' in r.stdout and 'System:' in r.stdout
    assert 'Summary' not in r.stdout


def test_single_run_has_abs_layout(invoke):
    r = invoke('-r', '1', 'true')
    assert r.returncode == 0
    assert 'Time (abs ≡):' in r.stdout
    assert 'Time (mean ± σ):' not in r.stdout and 'Range (min … max):' not in r.stdout


def test_multiple_commands_and_comparison(invoke):
    r = invoke('--debug-mode', '--runs=1', 'sleep 1.0', 'sleep 2.0', 'sleep 3.0')
    assert r.returncode == 0
    assert all(f'Benchmark {i}:' in r.stdout for i in (1, 2, 3))
    assert 'Summary' in r.stdout and 'sleep 1.0 ran' in r.stdout
    assert '2.00 ± 0.00 times faster than sleep 2.0' in r.stdout
    assert '3.00 ± 0.00 times faster than sleep 3.0' in r.stdout


def test_runs_count_and_validation(invoke):
    r = invoke('--runs=3', '--export-json', 'runs.json', 'true')
    assert r.returncode == 0, r.stderr
    assert len(json.load(open('runs.json'))['results'][0]['times']) == 3


def test_run_option_conflicts(invoke):
    r = invoke('--runs=2', '--min-runs=1', 'true')
    assert r.returncode != 0 and 'cannot be used with' in r.stderr
    r = invoke('--min-runs=4', '--max-runs=2', 'true')
    assert r.returncode != 0 and 'Conflicting requirements for the number of runs (empty range, min is larger than max)' in r.stderr


def test_invalid_count_and_warmup(invoke):
    for opt in ('--runs', '--warmup'):
        r = invoke(opt, 'abc', 'true')
        assert r.returncode != 0 and f"Could not read numeric integer argument to '{opt}'" in r.stderr


def test_wall_and_cpu_time(invoke):
    r = invoke('-N', '--runs=1', '--export-json', 'timing.json', "python3 -c 'import time; time.sleep(0.06)'")
    assert r.returncode == 0, r.stderr
    d = json.load(open('timing.json'))['results'][0]
    assert d['mean'] >= .045 and d['system'] + d['user'] < d['mean'] / 2


def test_cpu_and_memory_observations(invoke):
    r = invoke('-N', '--runs=3', '--export-json', 'cpu.json', "python3 -c 'sum(range(100000))'")
    assert r.returncode == 0, r.stderr
    d = json.load(open('cpu.json'))['results'][0]
    assert len(d['memory_usage_byte']) == 3 and max(d['memory_usage_byte']) > 1_000_000
    assert d['user'] > 0


def test_shell_semantics_and_raw_command(invoke):
    cmd = 'echo test | tr a-z A-Z | cat'
    r = invoke('--runs=1', '--show-output', cmd)
    assert r.returncode == 0 and 'TEST' in r.stdout and f'Benchmark 1: {cmd}' in r.stdout


def test_direct_mode_quotes_literals_and_multiple_commands(invoke):
    r = invoke('-N', '--runs=1', '--show-output', "echo 'hello world' argument2", 'printf test')
    assert r.returncode == 0 and 'hello world argument2' in r.stdout and 'test' in r.stdout
    assert 'Benchmark 1:' in r.stdout and 'Benchmark 2:' in r.stdout


def test_direct_missing_program_error(invoke):
    r = invoke('-N', '--runs=1', 'definitely-no-such-program-xyz')
    assert r.returncode != 0 and "Error: Failed to run command 'definitely-no-such-program-xyz':" in r.stderr


def test_time_unit_conversion(invoke):
    r = invoke('--runs=1', '--time-unit=microsecond', 'sleep 0.02')
    assert r.returncode == 0 and 'µs' in r.stdout
    r = invoke('--runs=1', '--time-unit=second', 'sleep 0.02')
    assert r.returncode == 0 and re.search(r'0\.0\d+ s', r.stdout)


def test_report_separator_and_no_single_comparison(invoke):
    r = invoke('--runs=1', 'echo hi')
    assert r.returncode == 0
    assert re.search(r'\n \n\Z', r.stdout)
    assert 'Summary' not in r.stdout and 'times faster than' not in r.stdout


def test_sort_command_debug(invoke):
    r = invoke('--debug-mode', '--runs=1', '--sort=command', 'sleep 2', 'sleep 1')
    assert r.returncode == 0
    assert r.stdout.index('2.00 ±  0.00  sleep 2') < r.stdout.index('1.00          sleep 1')


def test_styles(invoke):
    r = invoke('--style=basic', '--runs=1', 'true')
    assert r.returncode == 0 and '\x1b[' not in r.stdout and 'Benchmark 1:' in r.stdout
    r = invoke('--style=none', '--runs=1', 'true')
    assert r.returncode == 0 and 'Benchmark 1:' not in r.stdout and 'Time (' not in r.stdout
    r = invoke('--style=color', '--runs=1', 'true')
    assert r.returncode == 0 and '\x1b[1m' in r.stdout and '\x1b[32m' in r.stdout


def test_invalid_enum(invoke):
    r = invoke('--time-unit=nanosecond', 'true')
    assert r.returncode != 0 and "invalid value 'nanosecond'" in r.stderr and 'microsecond, millisecond, second' in r.stderr


def test_show_output_and_style_conflict(invoke):
    r = invoke('--style=basic', '--show-output', 'echo x')
    assert r.returncode == 2 and r.stdout == '' and "cannot be used with '--show-output'" in r.stderr
