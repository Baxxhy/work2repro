import json
import os
from pathlib import Path


def test_parameter_list_cartesian_order_and_json(invoke):
    r = invoke('--debug-mode', '--runs=1', '-L', 'x', '1,2', '-L', 'y', 'a,b', '--export-json', 'params.json', 'echo {x} {y}')
    assert r.returncode == 0, r.stderr
    data = json.load(open('params.json'))['results']
    assert [d['command'] for d in data] == ['echo 1 a', 'echo 2 a', 'echo 1 b', 'echo 2 b']
    assert [d['parameters'] for d in data] == [{'x':'1','y':'a'}, {'x':'2','y':'a'}, {'x':'1','y':'b'}, {'x':'2','y':'b'}]


def test_parameter_escaping_empty_and_literal_data(invoke):
    r = invoke('--runs=1', '-L', 'v', r'a\,b,,x\\y,', '--export-json', 'escape.json', "echo '{v}'")
    assert r.returncode == 0, r.stderr
    ds = json.load(open('escape.json'))['results']
    assert [d['parameters']['v'] for d in ds] == ['a,b', '', 'x\\y', '']


def test_parameter_scan_decimal_exactness(invoke):
    r = invoke('--debug-mode', '--runs=1', '-P', 'n', '0.0', '1.0', '-D', '0.33', '--export-json', 'scan.json', 'echo {n}')
    assert r.returncode == 0, r.stderr
    assert [d['parameters']['n'] for d in json.load(open('scan.json'))['results']] == ['0.00', '0.33', '0.66', '0.99']


def test_parameter_unknown_and_unused_display(invoke):
    r = invoke('--runs=1', '-L', 'unused', 'x,y', 'echo {undefined_param}')
    assert r.returncode == 0
    assert 'echo {undefined_param} (unused = x)' in r.stdout


def test_parameter_substitution_is_literal(invoke):
    r = invoke('--runs=1', '--show-output', '-L', 'v', 'test;whoami,$HOME', "echo 'arg:{v}'")
    assert r.returncode == 0, r.stderr
    assert 'arg:test;whoami' in r.stdout and 'arg:$HOME' in r.stdout


def test_parameter_validation_errors(invoke):
    r = invoke('--runs=1', '-P', 'x', '0.1', '0.3', 'echo {x}')
    assert r.returncode != 0 and 'A step size is required' in r.stderr
    r = invoke('--runs=1', '-P', 'x', '2', '1', '-D', '1', 'echo {x}')
    assert r.returncode != 0 and 'Error: Empty parameter range' in r.stderr
    r = invoke('--runs=1', '-P', 'x', '0', '1', '-D', '0.0', 'echo {x}')
    assert r.returncode != 0 and 'Zero is not a valid parameter step' in r.stderr
    r = invoke('--runs=1', '-P', 'x', '1.5.5', '2', '-D', '0.1', 'echo {x}')
    assert r.returncode != 0 and 'Invalid decimal: two decimal points' in r.stderr


def test_duplicate_and_mixed_parameter_types(invoke):
    r = invoke('--runs=1', '-L', 'x', 'a', '-L', 'x', 'b', 'echo {x}')
    assert r.returncode != 0 and 'Error: Duplicate parameter names: x' in r.stderr
    r = invoke('--runs=1', '-L', 'x', 'a', '-P', 'y', '1', '2', 'echo {x}')
    assert r.returncode != 0 and 'cannot be used with' in r.stderr


def test_parameter_names_apply_to_benchmark(invoke):
    r = invoke('--runs=1', '-L', 'x', '1,2', '-n', 'name-{x}', 'echo {x}')
    assert r.returncode == 0 and 'Benchmark 1: name-1' in r.stdout and 'Benchmark 2: name-2' in r.stdout


def test_hook_lifecycle_counts(invoke, workdir):
    marker = workdir / 'events'
    hook = f"echo x >> '{marker}'"
    r = invoke('--runs=2', '--warmup=1', '--setup', hook, '--prepare', hook,
               '--conclude', hook, '--cleanup', hook, 'true')
    assert r.returncode == 0, r.stderr
    assert marker.read_text().splitlines() == ['x'] + ['x']*3 + ['x']*3 + ['x']


def test_hook_failure_stops_and_reports(invoke, workdir):
    marker = workdir / 'order'
    write = f"echo x >> '{marker}'"
    r = invoke('--runs=2', '--setup', write, '--prepare', 'false', '--cleanup', write, 'true')
    assert r.returncode != 0 and 'The preparation command terminated with a non-zero exit code.' in r.stderr
    assert marker.read_text().splitlines() == ['x']


def test_repeatable_hook_cardinality(invoke):
    r = invoke('--runs=1', 'true', 'true', 'true', '--prepare', 'true', '--prepare', 'true')
    assert r.returncode != 0 and "The '--prepare' option has to be provided just once or N times, where N=3" in r.stderr
