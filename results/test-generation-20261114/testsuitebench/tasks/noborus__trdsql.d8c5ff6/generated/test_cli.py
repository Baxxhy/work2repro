import os
import subprocess
from pathlib import Path
import json
import gzip
import pytest

EVAL = Path(__file__).resolve().parent
EXE = Path('/workspace/executable')

def run(*args, cwd=None, stdin=None):
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd or EVAL, input=stdin,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def put(tmp_path, name, data):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data if isinstance(data, bytes) else data.encode())
    return p

def out(p): return p.stdout.decode('utf-8', 'replace')
def err(p): return p.stderr.decode('utf-8', 'replace')

# CLI contract

def test_version_exact():
    p = run('-version')
    assert (p.returncode, p.stdout, p.stderr) == (0, b'trdsql version devel\n', b'')

def test_long_version():
    p = run('--version')
    assert p.returncode == 0 and out(p).startswith('trdsql version') and not p.stderr

@pytest.mark.parametrize('args', [(), ('--help',), ('-help',), ('',)], ids=['no-query','long-help','short-help-long','empty-query'])
def test_usage_is_stderr_with_status_two(args):
    p = run(*args)
    assert p.returncode == 2 and not p.stdout
    assert out(type('X', (), {'stdout':p.stderr})()) .startswith('trdsql - Execute SQL queries')
    assert 'Examples:' in err(p)

def test_short_h_help_is_success():
    p = run('-h')
    assert p.returncode == 0 and not p.stdout and p.stderr

def test_help_takes_precedence_over_unknown_flag():
    p = run('-unknown', '--help')
    assert p.returncode == 2 and 'Usage' in err(p)

def test_unknown_flag_reports_usage():
    p = run('-notaflag', 'SELECT 1')
    assert p.returncode == 2 and 'flag provided but not defined: -notaflag' in err(p) and 'Usage' in err(p)

def test_missing_value_and_invalid_integer():
    a = run('-out')
    b = run('-ilr', 'wat', 'SELECT 1')
    assert a.returncode == 2 and 'flag needs an argument' in err(a)
    assert b.returncode == 2 and 'invalid value "wat" for flag -ilr' in err(b) and 'parse error' in err(b)

def test_boolean_flags_do_not_consume_following_word():
    p = run('-ig', 'false')
    assert p.returncode == 1 and 'syntax error' in err(p)

def test_double_dash_makes_help_sql_comment():
    p = run('--', '--help')
    assert p.returncode == 0 and not p.stdout and not p.stderr

def test_positional_sql_joined_and_options_may_precede_query():
    p = run('-ojson', 'SELECT', '1 + 2 AS answer')
    assert p.returncode == 0 and json.loads(out(p)) == [{'answer': 3}]

# SQL core

def test_literals_alias_arithmetic_and_functions():
    p = run('-ojson', "SELECT UPPER('abc') AS u, LOWER('XY') AS l, LENGTH('hey') AS n, 1+2 AS x")
    assert p.returncode == 0
    assert json.loads(out(p)) == [{'u':'ABC','l':'xy','n':3,'x':3}]

def test_case_coalesce_nullif_and_cast():
    p = run('-ojson', "SELECT CASE WHEN 2 > 1 THEN CAST('42' AS INTEGER) ELSE 0 END AS n, COALESCE(NULL, 'ok') AS v, NULLIF(1,1) AS z")
    assert p.returncode == 0 and json.loads(out(p)) == [{'n':42,'v':'ok','z':None}]

def test_concatenation_and_substr():
    p = run('-ojson', "SELECT SUBSTR('abcdef',2,3) AS s, 'a' || 'b' AS c")
    assert p.returncode == 0 and json.loads(out(p)) == [{'s':'bcd','c':'ab'}]

def test_where_like_between_in_null_and_distinct():
    p = run('-ojson', "SELECT DISTINCT x FROM (SELECT 'Abc' x UNION ALL SELECT 'abc' UNION ALL SELECT NULL) WHERE x LIKE 'a%' AND x IS NOT NULL")
    assert p.returncode == 0 and json.loads(out(p)) == [{'x':'Abc'}]

def test_sort_limit_and_offset():
    p = run('-ojson', 'SELECT x FROM (SELECT 3 x UNION ALL SELECT 1 UNION ALL SELECT 2) ORDER BY x DESC LIMIT 2 OFFSET 1')
    assert p.returncode == 0 and json.loads(out(p)) == [{'x':2},{'x':1}]

def test_aggregates_group_having_and_null_ignoring(tmp_path):
    f=put(tmp_path,'agg.csv','g,v\na,1\na,\nb,3\n')
    p=run('-ih','-ojson',f"SELECT g, COUNT(*) AS n, COUNT(v) AS cv, SUM(CAST(v AS INTEGER)) AS s, AVG(CAST(v AS INTEGER)) AS a FROM {f} GROUP BY g HAVING COUNT(*) > 0 ORDER BY g")
    assert p.returncode == 0 and json.loads(out(p)) == [{'g':'a','n':2,'cv':2,'s':1,'a':1},{'g':'b','n':1,'cv':1,'s':3,'a':3}]

def test_union_and_union_all():
    a=run('-ojson','SELECT 1 AS x UNION SELECT 1 UNION SELECT 2')
    b=run('-ojson','SELECT 1 AS x UNION ALL SELECT 1')
    assert a.returncode == b.returncode == 0
    assert json.loads(out(a)) == [{'x':1},{'x':2}]
    assert json.loads(out(b)) == [{'x':1},{'x':1}]

def test_row_number_window():
    p=run('-ojson','SELECT ROW_NUMBER() OVER (ORDER BY x) AS n, x FROM (SELECT 2 x UNION ALL SELECT 1)')
    assert p.returncode == 0 and json.loads(out(p)) == [{'n':1,'x':1},{'n':2,'x':2}]

# Input files, precedence, records, options

def test_headerless_and_header_csv(tmp_path):
    f=put(tmp_path,'data.csv','a,b\n1,2\n')
    p=run('-ojson',f'SELECT * FROM {f}')
    q=run('-ih','-oh',f'SELECT * FROM {f}')
    assert p.returncode == q.returncode == 0
    assert json.loads(out(p)) == [{'c1':'a','c2':'b'},{'c1':'1','c2':'2'}]
    assert out(q) == 'a,b\n1,2\n'

def test_query_file_and_table_option_precedence(tmp_path):
    f=put(tmp_path,'d.csv','x\n7\n')
    q=put(tmp_path,'query.sql',f'SELECT x FROM {f}')
    p=run('-q',q,'SELECT 999')
    t=run('-t',f,'-q',q,'SELECT 999')
    assert p.returncode == t.returncode == 0
    assert out(p) == '7\n' and out(t) == '7\n'

def test_missing_query_file_error():
    p=run('-q','missing-query-file.sql')
    assert p.returncode == 1 and 'ERROR: open missing-query-file.sql: no such file or directory' in err(p)

def test_csv_quoted_embedded_newline_and_quote(tmp_path):
    f=put(tmp_path,'quoted.csv','v\n"a,b"\n"line1\nline2"\n"say ""hi"""\n')
    p=run('-ih','-ojson',f'SELECT v FROM {f}')
    assert p.returncode == 0
    assert json.loads(out(p)) == [{'v':'a,b'},{'v':'line1\nline2'},{'v':'say "hi"'}]

def test_skip_header_row_limit_row_number(tmp_path):
    f=put(tmp_path,'skip.csv','discard\nname\nx\ny\nz\n')
    p=run('-is','1','-ih','-inum','-ilr','2','-ojson',f'SELECT * FROM {f}')
    assert p.returncode == 0 and json.loads(out(p)) == [{'num':1,'name':'x'},{'num':2,'name':'y'}]

def test_input_null_marker_and_empty_are_distinct(tmp_path):
    f=put(tmp_path,'null.csv','v\n""\nNA\n')
    p=run('-ih','-inull','NA','-ojson',f'SELECT v, v IS NULL AS isnull FROM {f}')
    assert p.returncode == 0 and json.loads(out(p)) == [{'v':'','isnull':0},{'v':None,'isnull':1}]

def test_custom_input_delimiter_and_guess_extensions(tmp_path):
    f=put(tmp_path,'pipe.psv','a|b\n1|2\n')
    semi=put(tmp_path,'semi.data','a;b\n3;4\n')
    p=run('-ih',f'SELECT * FROM {f}')
    q=run('-id',';','-ih',f'SELECT * FROM {semi}')
    assert p.returncode == q.returncode == 0
    assert out(p) == 'a\tb\n1\t2\n' if False else True
    assert out(p).strip() == '1,2'
    assert out(q).strip() == '3,4'

def test_glob_combines_lexically_and_later_header_is_data(tmp_path):
    put(tmp_path,'g/b.csv','x\n2\n')
    put(tmp_path,'g/a.csv','x\n1\n')
    p=run('-ih',f'SELECT x FROM {tmp_path}/g/*.csv ORDER BY x')
    assert p.returncode == 0 and out(p).splitlines() == ['1','2','x']

def test_missing_table_is_sql_error():
    p=run('SELECT * FROM definitely_missing_947.csv')
    assert p.returncode == 1 and 'export: no such table: definitely_missing_947.csv' in err(p)

def test_stdin_csv_input():
    p=run('-icsv','-ih','-ojson','SELECT * FROM -',stdin=b'a,b\n1,2\n')
    assert p.returncode == 0 and json.loads(out(p)) == [{'a':'1','b':'2'}]

def test_text_input_preserves_empty_physical_line(tmp_path):
    f=put(tmp_path,'lines.text','one\n\ntwo,three\n')
    p=run('-itext','-ojson',f'SELECT * FROM {f}')
    assert p.returncode == 0 and json.loads(out(p)) == [{'text':'one'},{'text':''},{'text':'two,three'}]

def test_json_nested_and_null(tmp_path):
    f=put(tmp_path,'items.json','[{"name":"A","obj":{"k":1}},{"name":"B","missing":null}]')
    p=run('-ojson',f'SELECT * FROM {f}')
    assert p.returncode == 0 and json.loads(out(p)) == [{'name':'A','obj':{'k':1}}, {'name':'B','obj':None}]

def test_jsonl_and_jq_path(tmp_path):
    f=put(tmp_path,'stream.jsonl','{"a":{"n":1}}\n{"a":{"n":2}}\n')
    p=run('-ijq','.a', '-ojson',f'SELECT * FROM {f}')
    assert p.returncode == 0 and json.loads(out(p)) == [{'n':'1'},{'n':'2'}]

def test_yaml_basic_and_jq(tmp_path):
    f=put(tmp_path,'data.yaml','- name: Ada\n  age: 7\n- name: Lin\n  age: 8\n')
    p=run('-ijq','.[]','-ojson',f'SELECT name FROM {f} ORDER BY name')
    assert p.returncode == 0 and json.loads(out(p)) == [{'name':'Ada'},{'name':'Lin'}]

def test_ltsv_split_first_colon_and_blank_lines(tmp_path):
    f=put(tmp_path,'data.ltsv','a:one:two\tb:hello world\n\n')
    p=run('-ojson',f'SELECT * FROM {f}')
    assert p.returncode == 0 and json.loads(out(p)) == [{'a':'one:two','b':'hello world'}]

def test_tbln_typed_values(tmp_path):
    f=put(tmp_path,'typed.tbln','; name: | n | ok |\n; type: | int | bool |\n| 42 | true |\n')
    p=run('-ojson',f'SELECT * FROM {f}')
    assert p.returncode == 0 and json.loads(out(p)) == [{'n':42,'ok':'true'}]

# Output forms

def test_csv_quoting_header_and_custom_quote():
    p=run('-oh',"SELECT 'O\"range' AS x UNION ALL SELECT 'a,b'")
    assert p.returncode == 0 and out(p) == 'x\n"O""range"\n"a,b"\n'

def test_csv_quote_all_custom_delimiter_and_crlf():
    p=run('-ocsv','-od',';','-oaq','-ocrlf','SELECT 1 AS x, 2 AS y')
    assert p.returncode == 0 and p.stdout == b'"1";"2"\r\n'

def test_json_pretty_null_and_html_escape():
    p=run('-ojson',"SELECT '<&>' AS x, NULL AS n")
    assert p.returncode == 0
    assert json.loads(out(p)) == [{'x':'<&>','n':None}]
    assert '\\u003c' in out(p) and '\\u0026' in out(p) and '\\u003e' in out(p)

def test_jsonl_compact_rows():
    p=run('-ojsonl','SELECT 1 AS x UNION ALL SELECT 2')
    assert p.returncode == 0 and out(p) == '{"x":1}\n{"x":2}\n'

def test_ltsv_and_raw_delimiter():
    p=run('-oltsv','SELECT 1 AS x, 2 AS y')
    q=run('-oraw','-od','||','SELECT 1, 2')
    assert p.returncode == q.returncode == 0
    assert out(p) == 'x:1\ty:2\n' and out(q) == '1||2\n'

def test_raw_header_empty_result_and_null_marker():
    p=run('-oraw','-oh','SELECT 1 AS x WHERE 0')
    q=run('-oraw','-onull','N','SELECT NULL')
    assert p.returncode == q.returncode == 0 and out(p) == 'x\n' and out(q) == 'N\n'

def test_yaml_output_native_and_empty():
    p=run('-oyaml',"SELECT 'word' AS x, 3 AS n, NULL AS z")
    q=run('-oyaml','SELECT 1 WHERE 0')
    assert p.returncode == q.returncode == 0
    assert '- x: word' in out(p) and '  n: 3' in out(p) and '  z: null' in out(p)
    assert out(q) == '[]\n'

def test_table_and_vertical_output_shapes():
    p=run('-oat','SELECT 30 AS age')
    q=run('-ovf','SELECT 30 AS age')
    assert p.returncode == q.returncode == 0
    assert '+-----+' in out(p) and '| age |' in out(p) and '|  30 |' in out(p)
    assert out(q).startswith('---[ 1]------------------------\n') and 'age | 30' in out(q)

def test_tbln_output_metadata_and_empty():
    p=run('-otbln',"SELECT 1 AS n, 'x' AS s")
    q=run('-otbln','SELECT 1 AS n WHERE 0')
    assert p.returncode == q.returncode == 0
    assert out(p) == '; name: | n | s |\n; type: | text | text |\n| 1 | x |\n'
    assert out(q) == '; name: | n |\n; type: | text |\n'

# Multi-statement, destinations, analysis, config/debug, errors

def test_sequential_statements_keep_prior_output(tmp_path):
    f=put(tmp_path,'d.csv','a\n1\n')
    p=run('-ih',f'SELECT a FROM {f}; SELECT missing FROM {f}')
    assert p.returncode == 1 and out(p) == '1\n' and 'no such column: missing' in err(p)

def test_semicolon_inside_string_is_not_statement_boundary():
    p=run("SELECT 'a;b'")
    assert p.returncode == 0 and out(p) == 'a;b\n'

def test_update_delete_then_select(tmp_path):
    f=put(tmp_path,'mut.csv','id,v\n1,a\n2,b\n')
    p=run('-ih',f"UPDATE {f} SET v='z' WHERE id='1'; DELETE FROM {f} WHERE id='2'; SELECT v FROM {f}")
    assert p.returncode == 0 and out(p) == 'z\n'

def test_out_file_format_inferred(tmp_path):
    f=put(tmp_path,'d.csv','a\n1\n')
    dest=tmp_path/'result.unknown.json'
    p=run('-ih','-out',dest,f'SELECT a FROM {f}')
    assert p.returncode == 0 and not p.stdout and json.loads(dest.read_text()) == [{'a':'1'}]

def test_out_without_guess_defaults_csv(tmp_path):
    dest=tmp_path/'result.json'
    p=run('-out',dest,'-out-without-guess','SELECT 1 AS x')
    assert p.returncode == 0 and dest.read_text() == '1\n'

def test_out_open_failure():
    p=run('-out','absent-parent-xyz/out.csv','SELECT 1')
    assert p.returncode == 1 and 'open absent-parent-xyz/out.csv: no such file or directory' in err(p)

def test_output_gzip_magic(tmp_path):
    dest=tmp_path/'x.csv.gz'
    p=run('-out',dest,'SELECT 1')
    assert p.returncode == 0 and not p.stdout
    assert gzip.decompress(dest.read_bytes()) == b'1\n'

def test_input_gzip_detected_by_magic_and_extension(tmp_path):
    f=put(tmp_path,'compressed.csv.gz',gzip.compress(b'a\n1\n'))
    p=run('-ih',f'SELECT a FROM {f}')
    assert p.returncode == 0 and out(p) == '1\n'

def test_analysis_and_analysis_commands(tmp_path):
    f=put(tmp_path,'analysis.csv','name,age\nAda,7\n')
    p=run('-a',f)
    q=run('-A',f)
    assert p.returncode == q.returncode == 0
    assert 'The table name is ' in out(p) and 'Data types:' in out(p) and 'Data samples:' in out(p) and 'Examples:' in out(p)
    assert q.stdout.count(b'\n') == 4 and not b'Examples:' in q.stdout

def test_missing_and_quoted_keyword_columns(tmp_path):
    f=put(tmp_path,'odd name.csv','select,full name,率\n1,Ada,2\n')
    p=run('-ih','-ojson',f'SELECT "select", "full name", "率" FROM "{f}"')
    assert p.returncode == 0 and json.loads(out(p)) == [{'select':'1','full name':'Ada','率':'2'}]

def test_invalid_sql_is_status_one_and_not_stdout():
    p=run('SELECT * FRON nowhere.csv')
    assert p.returncode == 1 and not p.stdout and 'syntax error' in err(p)

def test_explicit_sqlite_memory_dsn():
    p=run('-dsn',':memory:','SELECT 13')
    assert p.returncode == 0 and out(p) == '13\n'

# Data generality and serialization

def test_long_csv_field_and_unicode(tmp_path):
    value='🙂é漢Ж' * 2500
    f=put(tmp_path,'long.csv','v\n'+value+'\n')
    p=run('-ih','-ojson',f'SELECT v FROM {f}')
    assert p.returncode == 0 and json.loads(out(p)) == [{'v':value}]

def test_many_rows_and_aggregate_count(tmp_path):
    f=put(tmp_path,'many.csv','n\n'+''.join(f'{i}\n' for i in range(1200)))
    p=run('-ih','-ojson',f'SELECT COUNT(*) AS n, MIN(CAST(n AS INTEGER)) AS lo, MAX(CAST(n AS INTEGER)) AS hi FROM {f}')
    assert p.returncode == 0 and json.loads(out(p)) == [{'n':1200,'lo':0,'hi':1199}]

def test_int64_precision_and_short_numeric_json():
    p=run('-ojson','SELECT CAST(9223372036854775807 AS INTEGER) AS n, 0.0 AS z, 4.0 AS f')
    assert p.returncode == 0 and out(p).find('9223372036854775807') >= 0
    assert json.loads(out(p)) == [{'n':9223372036854775807,'z':0,'f':4}]
