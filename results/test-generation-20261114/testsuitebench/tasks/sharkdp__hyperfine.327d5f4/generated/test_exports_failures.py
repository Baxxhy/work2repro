import csv
import json
from pathlib import Path


def test_json_schema_and_exit_codes(invoke):
    r = invoke('-i', '--runs=3', '--export-json', 'data.json', '/bin/false')
    assert r.returncode == 0, r.stderr
    obj = json.load(open('data.json'))
    assert list(obj) == ['results'] and len(obj['results']) == 1
    d = obj['results'][0]
    assert set(d) >= {'command','mean','stddev','median','user','system','min','max','times','exit_codes','memory_usage_byte'}
    assert d['exit_codes'] == [1,1,1] and len(d['times']) == 3
    assert 'Ignoring non-zero exit code' in r.stderr


def test_csv_columns_and_quoting(invoke):
    r = invoke('--runs=1', '-L', 'z', '2', '-L', 'a', '1', '--export-csv', 'data.csv', 'echo "hello,world"')
    assert r.returncode == 0, r.stderr
    rows = list(csv.reader(open('data.csv', newline='')))
    assert rows[0] == ['command','mean','stddev','median','user','system','min','max','parameter_a','parameter_z']
    assert rows[1][0] == 'echo "hello,world"' and rows[1][-2:] == ['1','2']


def test_all_table_formats(invoke):
    args = ['--runs=1','--export-markdown','m.md','--export-asciidoc','a.adoc','--export-orgmode','o.org','echo test | cat']
    r = invoke(*args)
    assert r.returncode == 0, r.stderr
    md = Path('m.md').read_text().splitlines()
    assert md[0].startswith('| Command | Mean [') and md[1].startswith('|:---|')
    assert all(line.startswith('|') and line.endswith('|') for line in md)
    ad = Path('a.adoc').read_text()
    assert ad.startswith('[cols="<,>,>,>,>"]\n|===') and ad.endswith('|===\n') and '| Relative' in ad
    org = Path('o.org').read_text().splitlines()
    assert org[0].startswith('| Command  |  Mean [') and org[1].count('+') == 4


def test_table_stdout_style_none(invoke):
    r = invoke('--style=none', '--runs=1', '--export-markdown', '-', 'echo hi')
    assert r.returncode == 0 and 'Benchmark 1:' not in r.stdout and '| Command |' in r.stdout


def test_input_file_reopened_each_run(invoke, workdir):
    inp = workdir / 'input'
    inp.write_text('sample\n')
    r = invoke('--runs=2', '--input', str(inp), '--show-output', "cat", '--export-json', 'stdin.json')
    assert r.returncode == 0 and r.stdout.count('sample') == 2
    r = invoke('--input', str(workdir / 'absent'), '--runs=1', 'cat')
    assert r.returncode != 0 and f"The file '{workdir / 'absent'}' specified as '--input' does not exist" in r.stderr


def test_output_file_overwrites_each_run(invoke, workdir):
    out = workdir / 'captured.txt'
    r = invoke('--runs=5', '--output', str(out), 'echo single')
    assert r.returncode == 0, r.stderr
    assert out.read_text() == 'single\n'


def test_failure_and_ignore_codes(invoke):
    r = invoke('--runs=2', '/bin/false')
    assert r.returncode != 0 and 'non-zero exit code 1' in r.stderr
    r = invoke('--runs=3', '--ignore-failure=1', '/bin/false')
    assert r.returncode == 0 and 'Ignoring non-zero exit code' in r.stderr
    r = invoke('--ignore-failure=abc', 'true')
    assert r.returncode != 0 and "Could not read numeric integer argument to '--ignore-failure'" in r.stderr


def test_reference_and_names_debug(invoke):
    r = invoke('--debug-mode', '--runs=1', '--reference', 'sleep 2.0', '--reference-name', 'Ref', '-n', 'Fast', 'sleep 1.0', 'sleep 3.0')
    assert r.returncode == 0
    assert 'Benchmark 1: Ref' in r.stdout and 'Benchmark 2: Fast' in r.stdout
    assert 'Ref ran' in r.stdout and '2.00 ± 0.00 times slower than Fast' in r.stdout


def test_name_cardinality_errors(invoke):
    r = invoke('--runs=1', '-L', 'x', '1,2,3', '-n', 'a', '-n', 'b', 'echo {x}')
    assert r.returncode != 0 and "'--command-name' has been specified 2 times" in r.stderr
    r = invoke('--runs=1', '-n', 'a', '-n', 'b', 'echo x')
    assert r.returncode != 0 and 'Too many --command-name options: Expected 1 at most' in r.stderr


def test_export_validation_before_benchmark(invoke, workdir):
    marker = workdir / 'ran'
    r = invoke('--runs=1', '--export-json', str(workdir / 'no-dir' / 'x.json'), f"touch '{marker}'")
    assert r.returncode != 0 and 'Could not create export file' in r.stderr
    assert not marker.exists()


def test_debug_reference_and_sort_comparison(invoke):
    r = invoke('--debug-mode', '--runs=1', '--reference', 'sleep 2.0', 'sleep 1.0', 'sleep 3.0')
    assert r.returncode == 0 and '2.00 ± 0.00 times slower than sleep 1.0' in r.stdout
    assert '1.50 ± 0.00 times faster than sleep 3.0' in r.stdout
