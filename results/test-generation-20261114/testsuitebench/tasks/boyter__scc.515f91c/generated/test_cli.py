import csv
import json
import os
import subprocess
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent
EXE = Path('/workspace/executable')


@pytest.fixture
def tree(tmp_path):
    return tmp_path


def put(root, name, content):
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content if isinstance(content, bytes) else content.encode())
    return p


def run(args=(), cwd=None, stdin=None):
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd or EVAL,
                          input=stdin, text=True, capture_output=True, timeout=30)


def report(root, *opts):
    p = run([*opts, '--format', 'json', str(root)])
    assert p.returncode == 0, p.stdout + p.stderr
    return json.loads(p.stdout)


def byname(data):
    return {x['Name']: x for x in data}


def test_identity_help_and_language_aliases():
    v = run(['--version'])
    assert (v.returncode, v.stdout, v.stderr) == (0, 'scc version 3.7.0\n', '')
    h = run(['--help'])
    assert h.returncode == 0 and h.stdout.startswith('Sloc, Cloc and Code. Count lines of code in a directory with complexity estimation.\nUsage:\n  scc [flags] [files or directories]')
    a, b = run(['--languages']), run(['-l'])
    assert a.returncode == b.returncode == 0 and a.stdout == b.stdout
    assert all(x in a.stdout for x in ('Go (go)', 'Python (py,pyw,pyi)', 'JavaScript (js,cjs,mjs)'))


def test_physical_lines_bytes_and_empty_files(tree):
    put(tree, 'a.py', b'\n\n\nline1\r\nline2\r\nline3\r\n')
    put(tree, 'empty.py', b'')
    d = byname(report(tree))
    assert d['Python']['Count'] == 2
    assert (d['Python']['Lines'], d['Python']['Blank'], d['Python']['Code'], d['Python']['Bytes']) == (6, 3, 3, 24)


def test_unknown_extensions_skipped_and_utf8_paths_count(tree):
    put(tree, 'café-東京.py', 'print("привет")\n')
    put(tree, 'nope.xyz', 'hello\n')
    d = byname(report(tree))
    assert d['Python']['Count'] == 1 and d['Python']['Bytes'] == len('print("привет")\n'.encode())
    assert len(d) == 1


def test_comment_string_lexing_and_complexity(tree):
    put(tree, 'x.py', '''# comment\nx = "# not comment" # inline\n\nif x and (x > 1):\n    print(x)\n"""doc\nline's\n"""\n''')
    x = byname(report(tree))['Python']
    assert (x['Lines'], x['Code'], x['Comment'], x['Blank']) == (8, 3, 4, 1)
    assert x['Complexity'] >= 2


def test_language_case_and_include_exclude_extensions(tree):
    put(tree, 'A.GO', 'package x\n')
    put(tree, 'b.py', 'print(1)\n')
    put(tree, 'c.js', 'x()\n')
    assert set(byname(report(tree, '--include-ext', 'go'))) == {'Go'}
    assert report(tree, '--include-ext', 'GO') == []
    assert set(byname(report(tree, '--include-ext', 'go,py', '--exclude-ext', 'py'))) == {'Go'}
    assert report(tree, '--include-ext', '.go') == []


def test_repeated_extension_filters_accumulate(tree):
    put(tree, 'a.go', 'package a\n'); put(tree, 'b.py', 'x=1\n'); put(tree, 'c.js', 'x()\n')
    d = report(tree, '--include-ext', 'go,py', '--include-ext', 'js', '--exclude-ext', 'py', '--exclude-ext', 'js')
    assert set(byname(d)) == {'Go'}


def test_count_as_composition_and_later_replacement(tree):
    put(tree, 'a.new', 'class A {}\n'); put(tree, 'b.chead', 'int x;\n'); put(tree, 'c.py', 'print(1)\n')
    d = byname(report(tree, '--count-as', 'new:java,chead:C Header'))
    assert set(d) == {'Java', 'C Header'}
    d = byname(report(tree, '--count-as', 'new:java,chead:C Header', '--count-as', 'py:Ruby'))
    assert set(d) == {'Ruby'}


def test_count_as_overrides_known_and_content_remap(tree):
    put(tree, 'a.py', 'class A {}\n')
    put(tree, 'b.java', 'MAGIC\nclass B {}\n')
    put(tree, 'c.zzz', 'MAGIC\nx\n')
    assert set(byname(report(tree, '--count-as', 'py:Ruby'))) == {'Ruby'}
    assert set(byname(report(tree, '--remap-all', 'MAGIC:C Header'))) == {'Python', 'C Header'}
    assert set(byname(report(tree, '--remap-unknown', 'MAGIC:C Header'))) == {'Python', 'Java'}


def test_shebang_extensionless_and_unknown_extension(tree):
    put(tree, 'script', '#!/usr/bin/env ruby\nputs 1\n')
    put(tree, 'script.unknown', '#!/usr/bin/python\nprint(1)\n')
    d = byname(report(tree))
    assert 'Ruby' in d and len(d) == 1


def test_default_and_explicit_exclude_file_behavior(tree):
    put(tree, 'package-lock.json', '{}\n'); put(tree, 'package.json', '{}\n'); put(tree, 'other.json', '{}\n')
    assert byname(report(tree))['JSON']['Count'] == 2
    d = byname(report(tree, '--exclude-file', 'package.json'))
    assert d['JSON']['Count'] == 2


def test_directory_exclusions_and_not_match(tree):
    put(tree, 'keep.py', 'x=1\n'); put(tree, 'build/a.py', 'x=2\n'); put(tree, 'sub/test.py', 'x=3\n')
    assert byname(report(tree, '--exclude-dir', 'build/'))['Python']['Count'] == 2
    assert byname(report(tree, '--not-match', 'test/'))['Python']['Count'] == 2


def test_ignore_controls_and_count_ignore(tree):
    put(tree, '.gitignore', 'hidden.py\n')
    put(tree, 'hidden.py', 'x=1\n'); put(tree, 'visible.py', 'x=2\n')
    assert byname(report(tree))['Python']['Count'] == 1
    d = byname(report(tree, '--no-gitignore', '--count-ignore'))
    assert d['Python']['Count'] == 2 and 'gitignore' in d


def test_binary_large_and_empty_thresholds(tree):
    put(tree, 'binary.py', b'a\x00b\n'); put(tree, 'empty.py', b'')
    assert byname(report(tree))['Python']['Count'] == 1
    assert byname(report(tree, '--binary'))['Python']['Count'] == 2
    assert report(tree, '--no-large', '--large-byte-count', '0') == []


def test_generated_and_minified_markers(tree):
    put(tree, 'g.py', '# DO NOT EDIT\nx=1\n')
    put(tree, 'm.js', 'x' * 350 + '\n' + 'x' * 5 + '\n' + 'x' * 5)
    d = report(tree, '--gen', '--min')
    names = {r['Name'] for r in d}
    assert 'Python (gen)' in names and 'JavaScript (min)' in names
    assert byname(report(tree, '--no-gen'))['JavaScript']['Count'] == 1
    assert report(tree, '--no-min-gen') == []


def test_generated_markers_replace_defaults_and_prefix_limit(tree):
    put(tree, 'default.py', 'do not edit\nx=1\n')
    put(tree, 'custom.py', 'CUSTOM\nx=1\n')
    d = byname(report(tree, '--gen', '--generated-markers', 'CUSTOM'))
    assert 'Python (gen)' in d and d['Python (gen)']['Count'] == 1


def test_content_deduplication_and_duplicate_operands(tree):
    content = 'x=1\n'
    a = put(tree, 'a.py', content); put(tree, 'b.py', content)
    assert byname(report(tree))['Python']['Count'] == 2
    assert byname(report(tree, '--no-duplicates'))['Python']['Count'] == 1
    p = run(['--format', 'json', str(a), str(a)])
    assert json.loads(p.stdout)[0]['Count'] == 1


def test_uloc_dryness_and_character_percent(tree):
    put(tree, 'a.py', 'x\nyyy\n\n')
    d = json.loads(run(['--uloc', '--format', 'json', str(tree)]).stdout)
    assert d[0]['ULOC'] == 2
    t = run(['--character', '--percent', '--no-cocomo', str(tree)])
    assert 'MaxLine / MeanLine' in t.stdout and 'Percentage' in t.stdout
    assert 'DRYness %' in run(['--dryness', '--no-cocomo', str(tree)]).stdout


def test_no_complexity_keeps_json_field_zero(tree):
    put(tree, 'a.py', 'if x:\n  pass\n')
    x = byname(report(tree, '--no-complexity'))['Python']
    assert x['Complexity'] == 0


def test_empty_scan_and_missing_operand(tree):
    assert run(['--format', 'json', str(tree)]).stdout == '[]'
    p = run([str(tree / 'missing')])
    assert p.returncode == 1 and p.stdout == f'file or directory could not be read: {tree}/missing\n' and p.stderr == ''


def test_json_schema_and_no_trailing_newline(tree):
    put(tree, 'x.py', 'x=1\n')
    p = run(['--format', 'json', str(tree)])
    assert p.stdout.endswith(']') and not p.stdout.endswith('\n')
    row = json.loads(p.stdout)[0]
    assert list(row) == ['Name','Bytes','CodeBytes','Lines','Code','Comment','Blank','Complexity','Count','WeightedComplexity','Files','LineLength','ULOC']
    assert row['Files'] == [] and row['Count'] == 1


def test_csv_and_csv_stream_have_contract_headers(tree):
    put(tree, 'x.py', 'x=1\n')
    a = run(['--format', 'csv', str(tree)]).stdout
    b = run(['--format', 'csv-stream', str(tree)]).stdout
    assert next(csv.reader(a.splitlines())) == ['Language','Lines','Code','Comments','Blanks','Complexity','Bytes','Files','ULOC']
    assert next(csv.reader(b.splitlines())) == ['Language','Provider','Filename','Lines','Code','Comments','Blanks','Complexity','Bytes','Uloc']


def test_alternate_renderers_are_structured(tree):
    put(tree, 'x.py', 'x=1\n')
    y = run(['--format', 'cloc-yaml', str(tree)]).stdout
    h = run(['--format', 'html', str(tree)]).stdout
    ht = run(['--format', 'html-table', str(tree)]).stdout
    om = run(['--format', 'openmetrics', str(tree)]).stdout
    assert y.startswith('# https://github.com/boyter/scc/') and 'SUM:' in y
    assert '<html lang="en">' in h and '<table id="scc-table">' in h
    assert '<table id="scc-table">' in ht and '<html' not in ht
    assert om.startswith('# TYPE scc_files gauge\n') and '# EOF' not in om


def test_cocomo_controls_and_json2(tree):
    put(tree, 'x.py', 'x=1\n')
    p = run(['--format', 'json2', str(tree)])
    x = json.loads(p.stdout)
    assert set(x) == {'languageSummary','estimatedCost','estimatedScheduleMonths','estimatedPeople'}
    t = run(['--no-cocomo', str(tree)])
    assert 'Estimated Cost to Develop' not in t.stdout
    z = run(['--sloccount-format', str(tree)])
    assert 'Total Physical Source Lines of Code (SLOC)' in z.stdout


def test_format_multi_destinations_and_output(tree):
    put(tree, 'x.py', 'x=1\n')
    dest = tree / 'out.json'
    p = run(['--format-multi', f'json:{dest},csv:stdout', str(tree)])
    assert p.returncode == 0 and json.loads(dest.read_text())
    assert p.stdout.startswith('Language,Lines,Code,Comments,Blanks')
    target = tree / 'redirect.txt'
    p = run(['--output', str(target), '--format', 'json', str(tree)])
    assert p.stdout == f'results written to {target}\n' and json.loads(target.read_text())


def test_at_file_and_unknown_flag(tree):
    put(tree, 'x.py', 'x=1\n')
    argfile = put(tree, 'args', f'--format\njson\n{tree}\n')
    p = run(['@' + str(argfile)])
    assert p.returncode == 0 and json.loads(p.stdout)
    p = run(['--formt'])
    assert p.returncode == 1 and 'Error: unknown flag: --formt' in p.stderr and '--format' in p.stderr


def test_mcp_initialize_and_analyze(tree):
    put(tree, 'x.py', 'x=1\n')
    req = {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05'}}
    p = run(['--mcp'], cwd=tree, stdin=json.dumps(req)+'\n')
    assert p.returncode == 0
    obj = json.loads(p.stdout)
    assert obj['result']['protocolVersion'] == '2024-11-05'
    req = {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'analyze','arguments':{'path':str(tree)}}}
    p = run(['--mcp'], cwd=tree, stdin=json.dumps(req)+'\n')
    result = json.loads(p.stdout)['result']
    inner = json.loads(result['content'][0]['text'])
    assert inner['totals']['files'] == 1 and inner['totals']['lines'] == 1
