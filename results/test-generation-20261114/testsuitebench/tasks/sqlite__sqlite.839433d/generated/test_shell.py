import os
import subprocess
from pathlib import Path

import pytest


EVAL = Path(__file__).resolve().parent
EXE = Path(os.environ.get("SQLITE_EXECUTABLE", "/workspace/executable"))


def invoke(*args, stdin=None, cwd=None):
    return subprocess.run(
        [str(EXE), *map(str, args)], input=stdin, capture_output=True,
        cwd=cwd or EVAL, timeout=15,
    )


def ok(*args, stdin=None, cwd=None):
    p = invoke(*args, stdin=stdin, cwd=cwd)
    assert p.returncode == 0, (p.returncode, p.stdout, p.stderr)
    return p


def test_version_cli_and_sql():
    p = ok("--version")
    assert p.stdout.decode().startswith("3.54.0")
    p = ok(":memory:", "select sqlite_version();")
    assert p.stdout == b"3.54.0\n"


def test_version_dot_command_exact():
    p = ok(":memory:", stdin=".version\n")
    assert p.stdout.decode().splitlines() == [
        "SQLite 3.54.0 2026-04-14 20:02:49 49b3bac482c831f503c7f90c35959e7ea731950e991baba86b2ab95987d2539b",
        "zlib version 1.2.11", "gcc-11.4.0 (64-bit)",
    ]


def test_help_on_stderr():
    p = invoke("--help")
    assert p.returncode == 0
    out = p.stderr.decode(errors="replace")
    assert all(x in out for x in ("Usage:", "OPTIONS", "FILENAME", "-csv", "-table"))


def test_hash_lines_are_ignored():
    p = ok(":memory:", stdin="# SELECT 4;\n# .shell echo BAD\n")
    assert p.stdout == p.stderr == b""


def test_multiline_sql_and_comments():
    p = ok(":memory:", stdin="-- lead\nSELECT 'a;\nb' /* ; */;\nSELECT 2;\n")
    assert p.stdout == b"a;\nb\n2\n"


def test_default_list_and_null_separator():
    p = ok(":memory:", "select 1, null, 'x';")
    assert p.stdout == b"1||x\n"
    p = ok("-nullvalue", "NULL", "-separator", "::", ":memory:", "select null,2;")
    assert p.stdout == b"NULL::2\n"


def test_row_separator_option():
    p = ok("-separator", ",", "-newline", "!", ":memory:", "select 1 union all select 2;")
    assert p.stdout == b"1!2!"


def test_headers_order_with_mode_options():
    assert ok("-header", "-list", ":memory:", "select 1 as answer;").stdout == b"1\n"
    assert ok("-list", "-header", ":memory:", "select 1 as answer;").stdout == b"answer\n1\n"


def test_column_mode_has_headers_by_default():
    out = ok("-column", ":memory:", "select 1 as num, 'test' as str;").stdout.decode()
    assert out.splitlines()[0].split() == ["num", "str"]
    assert "1" in out and "test" in out


def test_csv_quoting_and_crlf():
    p = ok("-csv", "-header", ":memory:", "select 'a,b' as x, 'say \"hi\"' as y;")
    assert p.stdout == b'x,y\r\n"a,b","say ""hi"""\r\n'


def test_ascii_mode_delimiters():
    p = ok("-ascii", ":memory:", "select 1,2 union all select 3,4;")
    assert p.stdout == b"1\x1f2\x1e3\x1f4\x1e"


def test_quote_mode_blob_and_control_escape():
    p = ok("-quote", ":memory:", "select X'48656C6C6F', 'line1'||char(10)||'line2';")
    assert p.stdout == b"x'48656c6c6f',unistr('line1\\u000aline2')\n"


def test_json_rows_null_and_escaping():
    p = ok("-json", ":memory:", "select 1 as n, null as z, 'a\"b' as s;")
    import json
    assert json.loads(p.stdout) == [{"n": 1, "z": None, "s": 'a"b'}]


def test_json_empty_result_emits_nothing():
    assert ok("-json", ":memory:", "select 1 where 0;").stdout == b""


def test_mode_list_contains_supported_modes():
    p = ok(":memory:", stdin=".mode --list\n")
    assert b"available modes: ascii box c column count csv html" in p.stdout
    assert b"markdown" in p.stdout and b"quote" in p.stdout and b"tabs" in p.stdout


def test_sql_errors_continue_then_exit_nonzero():
    p = invoke(":memory:", stdin="select 1;\nselect * from missing_table;\nselect 2;\n")
    assert p.returncode != 0
    assert p.stdout == b"1\n2\n"
    assert b"missing_table" in p.stderr


def test_bail_stops_after_first_sql_error():
    p = invoke("-bail", ":memory:", stdin="select * from missing_table;\nselect 2;\n")
    assert p.returncode != 0 and p.stdout == b""


def test_exit_status_and_quit_semantics():
    assert invoke(":memory:", stdin="select 1;\n.quit 7\nselect 2;\n").stdout == b"1\n"
    assert invoke(":memory:", stdin=".exit 7\n").returncode == 7


def test_dot_invalid_boolean_has_nonfatal_exact_diagnostic():
    p = invoke(":memory:", stdin=".changes invalid\n")
    assert p.returncode == 0
    assert p.stderr == b'ERROR: Not a boolean value: "invalid". Assuming "no".\n'


def test_unknown_dot_command_fails():
    p = invoke(":memory:", stdin=".not_a_command\n")
    assert p.returncode == 1
    assert p.stderr


def test_option_unknown_and_vfs_errors():
    p = invoke("-definitely-unknown")
    assert p.returncode == 1 and b"unknown option" in p.stderr and b"-definitely-unknown" in p.stderr
    p = invoke("-vfs", "does-not-exist", ":memory:", "select 1;")
    assert p.returncode == 1 and b'no such VFS: "does-not-exist"' in p.stderr


def test_small_screenwidth_is_accepted():
    p = ok("-screenwidth", "10", ":memory:", "select 1;")
    assert p.stdout == b"1\n" and p.stderr == b""


def test_readonly_blocks_write(tmp_path):
    db = tmp_path / "readonly.db"
    ok(str(db), "create table t(x); insert into t values(1);")
    p = invoke("-readonly", str(db), "insert into t values(2);")
    assert p.returncode != 0
    assert ok(str(db), "select count(*) from t;").stdout == b"1\n"


def test_ifexists_does_not_create(tmp_path):
    db = tmp_path / "absent.db"
    p = invoke("-ifexists", str(db), "select 1;")
    assert p.returncode != 0 and not db.exists()


def test_init_runs_before_cmd_and_sql(tmp_path):
    init = tmp_path / "init.sql"
    init.write_text(".nullvalue NA\n")
    p = ok("-init", str(init), "-cmd", "select null;", ":memory:", "select null;")
    assert p.stdout == b"NA\nNA\n"


def test_missing_init_does_not_prevent_sql():
    p = invoke("-init", "/nonexistent/file.sql", ":memory:", "select 1;")
    assert p.returncode == 0 and p.stdout == b"1\n"
    assert b'cannot open: "/nonexistent/file.sql"' in p.stderr


def test_output_once_restores_stdout(tmp_path):
    a, b = tmp_path / "all.txt", tmp_path / "once.txt"
    script = f'.output {a}\nselect 1;\n.once {b}\nselect 2;\nselect 3;\n.output stdout\n'
    p = ok(":memory:", stdin=script)
    assert a.read_bytes() == b"1\n"
    assert b.read_bytes() == b"2\n"
    assert p.stdout == b"3\n"


def test_dot_print_and_read(tmp_path):
    sql = tmp_path / "commands.sql"
    sql.write_text("select 9;\n")
    p = ok(":memory:", stdin=f".print hello world\n.read {sql}\n")
    assert p.stdout == b"hello world\n9\n"


def test_read_pipe_form_is_rejected():
    p = invoke(":memory:", stdin=".read |printf 'select 9;\\n'\n")
    assert p.returncode == 1 and p.stderr == b"Usage: .read FILE\n"


def test_core_sql_value_types_and_underscore_numbers():
    p = ok(":memory:", "select 500_000, 0xFF_FF, typeof(null), typeof(1.5), typeof(x'00');")
    assert p.stdout == b"500000|65535|null|real|blob\n"


def test_aggregates_filter_and_order():
    sql = "with t(x) as (values(1),(2),(2),(null)) select count(*),count(x),sum(x),group_concat(x, ',' order by x desc),sum(x) filter(where x>1) from t;"
    p = ok(":memory:", sql)
    assert p.stdout == b"4|3|5|2,2,1|4\n"


def test_recursive_cte():
    sql = "with cnt(x) as (values(1) union all select x+1 from cnt where x<5) select group_concat(x, ',') from cnt;"
    assert ok(":memory:", sql).stdout == b"1,2,3,4,5\n"


def test_window_functions_and_frames():
    sql = "with t(x) as (values(10),(20),(30)) select x,row_number() over(order by x),sum(x) over(order by x rows between unbounded preceding and current row) from t order by x;"
    assert ok(":memory:", sql).stdout == b"10|1|10\n20|2|30\n30|3|60\n"


def test_join_outer_and_using_column_shape():
    sql = "with a(id,x) as (values(1,'a'),(2,'b')), b(id,y) as (values(2,'B'),(3,'C')) select * from a full join b using(id) order by id;"
    assert ok(":memory:", sql).stdout == b"1|a||\n2|b|B\n3||C\n"


def test_dml_returning_and_upsert():
    sql = "create table t(id primary key,v); insert into t values(1,'a') returning id,v; insert into t values(1,'b') on conflict(id) do update set v=excluded.v returning v; select v from t;"
    assert ok(":memory:", sql).stdout == b"1|a\nb\nb\n"


def test_transactions_savepoint_rollback():
    sql = "create table t(x); begin; insert into t values(1); savepoint s; insert into t values(2); rollback to s; release s; commit; select group_concat(x, ',') from t;"
    assert ok(":memory:", sql).stdout == b"1\n"


def test_foreign_key_cascade():
    sql = "pragma foreign_keys=on; create table p(id primary key); create table c(pid references p(id) on delete cascade); insert into p values(1); insert into c values(1); delete from p where id=1; select count(*) from c;"
    assert ok(":memory:", sql).stdout == b"0\n"


def test_generated_columns_and_table_xinfo():
    sql = "create table t(a,b generated always as (a*2) stored); insert into t(a) values(3); select a,b from t; pragma table_xinfo(t);"
    p = ok(":memory:", sql)
    assert p.stdout.startswith(b"3|6\n")
    assert b"|3\n" in p.stdout


def test_strict_table_enforces_types():
    p = invoke(":memory:", "create table t(x integer) strict; insert into t values('not-an-int');")
    assert p.returncode != 0 and b"datatype mismatch" in p.stderr


def test_persistence_across_invocations_and_sqlite_header(tmp_path):
    db = tmp_path / "persist.db"
    ok(str(db), "create table t(x); insert into t values('saved');")
    assert db.read_bytes().startswith(b"SQLite format 3\x00")
    assert ok(str(db), "select x from t;").stdout == b"saved\n"


def test_compile_options_and_absent_fts5():
    p = ok(":memory:", "pragma compile_options;")
    opts = set(p.stdout.decode().splitlines())
    assert {"COMPILER=gcc-11.4.0", "ENABLE_FTS3", "ENABLE_FTS4", "ENABLE_PERCENTILE", "THREADSAFE=1"} <= opts
    assert "ENABLE_FTS5" not in opts


def test_recursive_triggers_start_disabled():
    assert ok(":memory:", "pragma recursive_triggers;").stdout == b"0\n"


def test_missing_optional_module_reports_feature():
    p = invoke(":memory:", "create virtual table x using geopoly; ")
    assert p.returncode != 0 and b"no such module: geopoly" in p.stderr


def test_json_functions_and_math():
    sql = "select json_extract('{\"a\":2}', '$.a'), round(sqrt(9),1), median(x) from (values(1),(3)) as t(x);"
    assert ok(":memory:", sql).stdout == b"2|3.0|2.0\n"


def test_foreign_key_check_and_writable_schema_defense():
    p = ok(":memory:", "pragma writable_schema=1; pragma writable_schema;")
    assert p.stdout == b"0\n"
    p = invoke(":memory:", "delete from sqlite_schema;")
    assert p.returncode != 0 and b"table sqlite_master may not be modified" in p.stderr


def test_schema_dot_commands_and_dump_insert_names():
    p = ok(":memory:", stdin="create table t(x,y); insert into t values(1,'x');\n.schema\n.dump t\n")
    assert b"CREATE TABLE t" in p.stdout
    assert b"INSERT INTO t VALUES(1,'x');" in p.stdout


def test_import_csv_creates_table_from_header(tmp_path):
    csvfile = tmp_path / "data.csv"
    csvfile.write_text('name,note\nAda,"hello, world"\n')
    p = ok(":memory:", stdin=f".mode csv\n.import {csvfile} people\n.mode list\nselect name,note from people;\n")
    assert p.stdout == b"Ada|hello, world\n"


def test_backup_and_restore(tmp_path):
    backup = tmp_path / "backup.db"
    p = ok(":memory:", stdin=f"create table t(x); insert into t values(7);\n.backup {backup}\n")
    assert backup.exists() and backup.stat().st_size > 0
    assert ok(str(backup), "select x from t;").stdout == b"7\n"


def test_parameter_binding():
    sql = ".parameter init\n.parameter set :x 42\nselect :x;\n"
    assert ok(":memory:", stdin=sql).stdout == b"42\n"


def test_limit_can_be_read_and_adjusted():
    p = ok(":memory:", stdin=".limit length 1000\n.limit length\n")
    assert b"1000" in p.stdout


def test_fts3_search():
    sql = "create virtual table docs using fts3(title,body); insert into docs values('one','quick brown fox'); insert into docs values('two','slow turtle'); select title from docs where docs match 'quick';"
    assert ok(":memory:", sql).stdout == b"one\n"


def test_rtree_overlap():
    sql = "create virtual table boxes using rtree(id,x1,x2,y1,y2); insert into boxes values(1,0,2,0,2),(2,5,6,5,6); select id from boxes where x1<=1 and x2>=1 and y1<=1 and y2>=1;"
    assert ok(":memory:", sql).stdout == b"1\n"


def test_dbstat_and_missing_dbdata():
    p = ok(":memory:", "create table t(x); insert into t values(1); select count(*) from dbstat where name='t';")
    assert int(p.stdout.strip()) >= 1
    p = invoke(":memory:", "select * from sqlite_dbdata;")
    assert p.returncode == 1 and p.stdout == b"" and b"no such table: sqlite_dbdata" in p.stderr


def test_versioned_pragma_and_integrity_check():
    sql = "pragma user_version=17; pragma user_version; pragma integrity_check;"
    assert ok(":memory:", sql).stdout == b"17\nok\n"
