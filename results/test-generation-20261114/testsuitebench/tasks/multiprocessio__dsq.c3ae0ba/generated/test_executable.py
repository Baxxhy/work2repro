import json
import os
import subprocess
from pathlib import Path

import pytest

EXE = Path('/workspace/executable')


def call(*args, data=None, env=None, cwd=None):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run([str(EXE), *map(str, args)], input=data, text=True,
                          capture_output=True, env=merged, cwd=cwd, timeout=20)


@pytest.fixture
def csvfile(tmp_path):
    p = tmp_path / 'people.csv'
    p.write_text('id,name,age,active\n1,Ted,88,true\n2,Marjory,56,false\n3,Micah,33,true\n', encoding='utf-8')
    return p


def rows(proc):
    assert proc.returncode == 0, proc.stderr
    assert proc.stderr == ''
    return json.loads(proc.stdout)


def test_help_contract():
    p = call('--help')
    assert p.returncode == 0 and p.stdout == ''
    assert p.stderr.startswith('dsq (Version latest) - commandline SQL engine for data files\n\nUsage:')
    assert 'subcommands' not in p.stderr.lower()
    assert p.stderr.endswith('\n')


def test_help_takes_precedence():
    p = call('unknown.xyz', '--help')
    assert p.returncode == 0 and p.stdout == '' and 'Usage:' in p.stderr


def test_version_and_short_version():
    for flag in ('--version', '-v'):
        p = call(flag)
        assert p.returncode == 0 and p.stdout == ''
        assert 'dsq' in p.stderr and 'latest' in p.stderr and 'Usage:' not in p.stderr
    assert call('--version').stderr == 'dsq latest\n'


def test_no_arguments_diagnostic():
    p = call()
    assert p.returncode != 0 and p.stdout == '' and p.stderr == 'No input files.\n'


def test_query_looking_alone_is_filename():
    p = call('SELECT 1')
    assert p.returncode == 1 and p.stdout == ''
    assert p.stderr == 'Unknown mimetype for file: SELECT 1.\n'


def test_direct_csv_dump_preserves_strings(csvfile):
    assert rows(call(csvfile)) == [
        {'id': '1', 'name': 'Ted', 'age': '88', 'active': 'true'},
        {'id': '2', 'name': 'Marjory', 'age': '56', 'active': 'false'},
        {'id': '3', 'name': 'Micah', 'age': '33', 'active': 'true'}]


def test_csv_select_and_exact_multiline_json(csvfile):
    p = call(csvfile, 'select name from {} order by name')
    assert rows(p) == [{'name': 'Marjory'}, {'name': 'Micah'}, {'name': 'Ted'}]
    assert p.stdout == '[{"name":"Marjory"},\n{"name":"Micah"},\n{"name":"Ted"}]\n'


def test_empty_result_and_limit_zero(csvfile):
    assert call(csvfile, 'select * from {} where 0').stdout == '[]\n'
    assert call(csvfile, 'select * from {} limit 0').stdout == '[]\n'


def test_csv_rfc4180_and_unusual_headers(tmp_path):
    p = tmp_path / 'quoted.csv'
    p.write_text(' first\t,select,body\n"a,b",x,"line1\nline2"\n', encoding='utf-8')
    got = rows(call(p, 'select " first\t", "select", body from {}'))
    assert got == [{' first\t': 'a,b', 'select': 'x', 'body': 'line1\nline2'}]


def test_json_native_types_and_jsonl(tmp_path):
    j = tmp_path / 'data.json'
    j.write_text('[{"n":2,"b":true,"nil":null,"s":"é"}]', encoding='utf-8')
    jl = tmp_path / 'data.jsonl'
    jl.write_text('{"n":2,"b":true,"nil":null,"s":"é"}\n', encoding='utf-8')
    expected = [{'n': 2, 'b': True, 'nil': None, 's': 'é'}]
    assert rows(call(j)) == expected
    assert rows(call(jl)) == expected


def test_nested_json_flattening_and_arrays(tmp_path):
    p = tmp_path / 'nested.json'
    p.write_text('[{"location":{"city":"Toronto","address":{"number":1002}},"c":[1,2]}]', encoding='utf-8')
    got = rows(call(p, 'select "location.city", "location.address.number", c, c->1 as item from {}'))
    assert got == [{'location.city': 'Toronto', 'location.address.number': 1002, 'c': '[1,2]', 'item': '2'}]


def test_duplicate_flattened_names_fail(tmp_path):
    p = tmp_path / 'collision.json'
    p.write_text('[{"a.b":1,"a":{"b":2}}]', encoding='utf-8')
    r = call(p, 'select * from {}')
    assert r.returncode == 1 and r.stdout == '' and r.stderr == 'duplicate column name: a.b\n'


def test_csv_number_conversion_flag_and_environment(csvfile):
    p = tmp_path / 'nums.csv'
    p.write_text('v\n001\n+1\n0001.1\nhello\n', encoding='utf-8')
    assert rows(call(p)) == [{'v': '001'}, {'v': '+1'}, {'v': '0001.1'}, {'v': 'hello'}]
    converted = rows(call('-n', p))
    assert converted == [{'v': 1}, {'v': 1}, {'v': 1.1}, {'v': 'hello'}]
    assert rows(call(p, env={'DSQ_CONVERT_NUMBERS': 'true'})) == converted


def test_sql_where_expressions_functions_and_case(csvfile):
    q = "select name, age * 2 as doubled, upper(name) as up, case when age > 50 then 'old' else 'young' end as era from {} where name like 'M%' order by age"
    assert rows(call(csvfile, q)) == [
        {'name': 'Micah', 'doubled': 66, 'up': 'MICAH', 'era': 'young'},
        {'name': 'Marjory', 'doubled': 112, 'up': 'MARJORY', 'era': 'old'}]


def test_cast_and_sqlite_scalar_functions(csvfile):
    q = "select typeof(cast(age as integer)) as t, length(name) as n, substr(name,1,2) as s, coalesce(null,name) as c from {} where id='1'"
    assert rows(call(csvfile, q)) == [{'t': 'integer', 'n': 3, 's': 'Te', 'c': 'Ted'}]


def test_group_aggregates_and_having(csvfile):
    q = 'select active, count(*) as n, sum(cast(age as integer)) as total, avg(cast(age as integer)) as mean from {} group by active order by active'
    got = rows(call(csvfile, q))
    assert got == [{'active': 'false', 'n': 1, 'total': 56, 'mean': 56.0},
                   {'active': 'true', 'n': 2, 'total': 121, 'mean': 60.5}]
    assert rows(call(csvfile, 'select count(*) as n from {} having n > 2')) == [{'n': 3}]


def test_distinct_set_operations_and_offset(csvfile):
    assert rows(call(csvfile, 'select distinct active from {} order by active')) == [{'active': 'false'}, {'active': 'true'}]
    assert rows(call(csvfile, 'select name from {} order by name limit 1 offset 1')) == [{'name': 'Micah'}]
    assert len(rows(call(csvfile, 'select id from {} union all select id from {}',))) == 6


def test_cte_subquery_and_window(csvfile):
    q = 'with x as (select name, cast(age as integer) age from {}) select name, row_number() over (order by age) as rn from x order by rn'
    assert rows(call(csvfile, q)) == [{'name': 'Micah', 'rn': 1}, {'name': 'Marjory', 'rn': 2}, {'name': 'Ted', 'rn': 3}]
    assert rows(call(csvfile, 'select name from {} where id in (select id from {} where name="Ted")')) == [{'name': 'Ted'}]


def test_join_and_placeholder_order(csvfile, tmp_path):
    ages = tmp_path / 'ages.json'
    ages.write_text('[{"id":1,"age":88},{"id":2,"age":56},{"id":3,"age":33}]', encoding='utf-8')
    got = rows(call(csvfile, ages, 'select {0}.name as name, {1}.age as age from {0} join {1} on {0}.id={1}.id order by age'))
    assert got == [{'name': 'Micah', 'age': 33}, {'name': 'Marjory', 'age': 56}, {'name': 'Ted', 'age': 88}]


def test_schema_json_and_pretty(csvfile):
    p = call('-c', csvfile)
    assert p.returncode == 0 and p.stderr == ''
    schema = json.loads(p.stdout)
    assert schema['kind'] == 'array' and schema['array']['kind'] == 'object'
    assert set(schema['array']['object']) == {'id', 'name', 'age', 'active'}
    pretty = call('--pretty', csvfile, 'select id,name from {} order by id')
    assert pretty.returncode == 0 and pretty.stderr == ''
    assert '+----+--------+' in pretty.stdout and '(3 rows)' in pretty.stdout


def test_schema_of_query_result(csvfile):
    p = call('--schema', csvfile, 'select count(*) as total from {}')
    assert json.loads(p.stdout)['array']['object']['total']['scalar'] == 'number'


def test_stdin_csv_json_and_unknown_type():
    assert rows(call('-s', 'csv', 'select count(*) as n from {}', data='x\n1\n2\n')) == [{'n': 2}]
    assert rows(call('--stdin', 'application/json', data='[{"x":4}]')) == [{'x': 4}]
    p = call('--stdin', 'not/a-type', data='anything')
    assert p.returncode == 0 and p.stdout == '"anything"\n' and p.stderr == ''


def test_sql_file_matches_inline(csvfile, tmp_path):
    qf = tmp_path / 'query.sql'
    qf.write_text('\n select name from {} order by name; \n', encoding='utf-8')
    assert rows(call(csvfile, '-f', qf)) == rows(call(csvfile, 'select name from {} order by name'))


def test_cache_path_is_content_addressed(csvfile, tmp_path):
    a = call(csvfile, '--cache-file')
    b = call('-D', csvfile)
    assert a.returncode == b.returncode == 0
    assert a.stdout == b.stdout and 'dsq-cache-' in a.stdout and a.stdout.rstrip().endswith('.db')
    assert a.stderr == b.stderr == 'Cache invalid, re-import required.\n'
    csvfile.write_text(csvfile.read_text() + '4,New,20,false\n', encoding='utf-8')
    c = call(csvfile, '-D')
    assert c.stdout != a.stdout


@pytest.mark.parametrize('args,expected', [
    ((), 'No input files.\n'), (('-s',), 'Must specify stdin mimetype.\n'),
    (('-f',), 'Must specify a SQL file.\n')], ids=['no-input', 'stdin-missing-value', 'sql-file-missing-value'])
def test_argument_diagnostics(args, expected):
    p = call(*args)
    assert p.returncode != 0 and p.stdout == '' and p.stderr == expected


def test_unknown_file_and_missing_file_diagnostics(tmp_path):
    p = call('file.unknown')
    assert p.returncode == 1 and p.stdout == '' and p.stderr == 'Unknown mimetype for file: file.unknown.\n'
    missing = tmp_path / 'missing.csv'
    p = call(missing)
    assert p.returncode != 0 and p.stdout == '' and 'open ' + str(missing) in p.stderr


def test_sql_errors_are_clean(csvfile):
    for query, message in [('select * from', 'incomplete input'), ('select missing from {}', 'no such column: missing'),
                           ('select nope() from {}', 'no such function: nope'), ('select * from {} offset 1', 'syntax error')]:
        p = call(csvfile, query)
        assert p.returncode == 1 and p.stdout == '' and message in p.stderr
        assert 'Traceback' not in p.stderr


def test_verbose_and_no_sqlite_writer_preserve_result(csvfile):
    base = call(csvfile, 'select count(*) as n from {}')
    alt = call('--no-sqlite-writer', csvfile, 'select count(*) as n from {}')
    assert rows(base) == rows(alt)
    verbose = call('--verbose', csvfile, 'select count(*) as n from {}')
    assert verbose.returncode == 0 and json.loads(verbose.stdout) == [{'n': 3}]
    assert '[INFO]' in verbose.stderr
