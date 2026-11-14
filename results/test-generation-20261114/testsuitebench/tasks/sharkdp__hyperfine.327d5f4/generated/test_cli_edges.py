import json
import re


def test_shell_selection_and_shell_expression(invoke):
    r = invoke('--runs=1', '--shell=/bin/sh', 'echo shell-ok')
    assert r.returncode == 0 and 'Benchmark 1:' in r.stdout
    r = invoke('--runs=1', '--shell=bash --norc', 'echo bash-ok')
    assert r.returncode == 0
    r = invoke('--shell=', 'true')
    assert r.returncode != 0 and r.stderr.strip() == "Error: An empty command has been specified for the '--shell <command>' option"
    r = invoke('--shell', "'unterminated", 'true')
    assert r.returncode != 0 and r.stderr.strip() == "Error: Failed to parse '--shell <command>' expression as command line: missing closing quote"


def test_shell_launch_error(invoke):
    r = invoke('--shell=/nonexistent/shell', 'true')
    assert r.returncode != 0
    assert r.stderr.strip() == "Error: Could not measure shell execution time. Make sure you can run '/nonexistent/shell -c ""'."


def test_show_output_warmup_and_streams(invoke):
    r = invoke('--runs=1', '--warmup=2', '--show-output', "printf 'out'; printf 'err' >&2")
    assert r.returncode == 0
    assert r.stdout.count('out') == 3 and r.stderr.count('err') == 3


def test_iteration_environment(invoke):
    r = invoke('--runs=3', "python3 -c 'import os; open(\"iter-\"+os.environ[\"HYPERFINE_ITERATION\"],\"w\").write(\"x\")'")
    assert r.returncode == 0
    assert all(__import__('pathlib').Path(f'iter-{i}').exists() for i in range(3))


def test_reference_duplicate_and_expansion(invoke):
    r = invoke('--debug-mode', '--runs=1', '--reference=sleep 1', 'sleep 1', 'sleep 2')
    assert r.returncode == 0
    assert r.stdout.count('Benchmark ') == 3
    assert 'Benchmark 1: sleep 1' in r.stdout and 'Benchmark 2: sleep 1' in r.stdout


def test_direct_mode_does_not_interpret_shell_operators(invoke):
    r = invoke('-N', '--runs=1', '--show-output', 'echo test1 && echo test2')
    assert r.returncode == 0 and 'test1 && echo test2' in r.stdout and '\ntest2\n' not in r.stdout


def test_failed_shell_benchmark_exit_code(invoke):
    r = invoke('--runs=2', 'exit 7')
    assert r.returncode != 0 and 'non-zero exit code 7' in r.stderr


def test_run_output_policy_pipe_and_null(invoke):
    for policy in ('null', 'pipe'):
        r = invoke('--runs=1', f'--output={policy}', 'echo hidden')
        assert r.returncode == 0 and 'hidden' not in r.stdout


def test_invalid_output_policy(invoke):
    r = invoke('--runs=1', '--output=invalid_policy', 'true')
    assert r.returncode != 0
    assert "Error: Unknown output policy 'invalid_policy'. Use './invalid_policy' to output to a file named 'invalid_policy'." in r.stderr


def test_min_max_runs_and_minimum_time(invoke):
    r = invoke('--min-runs=2', '--max-runs=3', '--min-benchmarking-time=0.01', '--export-json', 'bounded.json', 'true')
    assert r.returncode == 0, r.stderr
    count = len(json.load(open('bounded.json'))['results'][0]['times'])
    assert 2 <= count <= 3
    r = invoke('--min-benchmarking-time=nope', 'true')
    assert r.returncode != 0 and "Could not read numeric floating point argument to '--min-benchmarking-time': invalid float literal" in r.stderr


def test_required_command_errors(invoke):
    r = invoke()
    assert r.returncode != 0 and 'the following required arguments were not provided:' in r.stderr
    r = invoke('')
    assert r.returncode != 0 and "a value is required for '<command>...' but none was supplied" in r.stderr


def test_unknown_option_and_parameter_size(invoke):
    r = invoke('--invalid-option', 'true')
    assert r.returncode != 0 and "unexpected argument '--invalid-option' found" in r.stderr
    r = invoke('-P', 'n', '0', '100001', '-D', '1', 'echo {n}')
    assert r.returncode != 0 and 'Error: Parameter range is too large' in r.stderr


def test_long_command_not_truncated(invoke):
    payload = 'x' * 10000
    cmd = "printf '%s' '" + payload + "'"
    r = invoke('--runs=1', cmd, timeout=60)
    assert r.returncode == 0, r.stderr
    assert cmd[:100] in r.stdout


def test_shell_fast_command_warning(invoke):
    r = invoke('--runs=3', 'true')
    assert r.returncode == 0
    assert any(line.startswith('Warning:') for line in r.stderr.splitlines())
