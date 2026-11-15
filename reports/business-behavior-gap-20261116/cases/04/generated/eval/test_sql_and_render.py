from conftest import failed, ok


def sql(run, query, *options):
    return run(*options, "-c", query)


def test_csv_header_and_csv_escaping(run):
    r = sql(run, "select 1 as n, 'a,\"b' as s", "-csv")
    ok(r)
    assert r.stdout == 'n,s\n1,"a,""b"""\n'


def test_json_rows_shape_null_and_empty(run):
    r = sql(run, "select * from range(2)", "-json")
    ok(r)
    assert r.stdout == '[{"range":0},\n{"range":1}]\n'
    r = sql(run, "select null as n, true as b", "-json")
    ok(r)
    assert r.stdout == '[{"n":null,"b":"true"}]\n'
    r = sql(run, "select 1 as n where false", "-json")
    ok(r)
    assert r.stdout == "[]\n"


def test_jsonlines_empty_and_string_newline(run):
    r = sql(run, "select 'a\\nb' as s", "--jsonlines")
    ok(r)
    assert r.stdout == '{"s":"a\\nb"}\n'
    r = sql(run, "select 1 where false", "-jsonlines")
    ok(r)
    assert r.stdout == "\n"


def test_list_null_defaults_and_custom_separator(run):
    r = sql(run, "select 1 as a, null as b, 3 as c", "-list")
    ok(r)
    assert r.stdout == "a|b|c\n1|NULL|3\n"
    r = run("-list", "-separator", "::", "-nullvalue", "", "-c", "select 'x' a, null b")
    ok(r)
    assert r.stdout == "a::b\nx::\n"


def test_quote_mode_quotes_text_not_numbers(run):
    r = sql(run, "select 1 as n, 'a''b' as s", "-quote")
    ok(r)
    assert r.stdout == "'n'|'s'\n1|'a''b'\n"


def test_markdown_keeps_heading_when_noheader(run):
    r = run("-markdown", "-noheader", "-c", "select 4 as value")
    ok(r)
    assert "| value |" in r.stdout and "| ---:" in r.stdout


def test_html_escapes_cells(run):
    r = sql(run, "select '<&>' as x", "-html")
    ok(r)
    assert "<th>x</th>" in r.stdout and "&lt;&amp;&gt;" in r.stdout


def test_tcl_and_insert_dot_modes(run):
    r = run("-c", ".mode tcl", "-c", "select 1 a, 'hello' b")
    ok(r)
    assert '"a" "b"' in r.stdout and '"1" "hello"' in r.stdout
    r = run("-c", ".mode insert mytable", "-c", "select 1 a, 'hello' b")
    ok(r)
    assert "INSERT INTO mytable(a,b) VALUES(1,'hello');" in r.stdout


def test_dot_insert_target_rejected_for_other_mode(run):
    r = run("-c", ".mode csv sometable")
    assert r.returncode == 1
    assert "TABLE argument can only be used with .mode insert" in r.stderr


def test_format_can_switch_between_commands(run):
    r = run("-c", ".mode csv", "-c", "select 1 as n", "-c", ".mode box", "-c", "select 2 as n")
    ok(r)
    assert "n\n1\n" in r.stdout
    assert "┌" in r.stdout and "2" in r.stdout


def test_default_duckbox_has_types_and_numeric_alignment(run):
    r = run("-c", "select 42 as answer")
    ok(r)
    assert "answer" in r.stdout and "int32" in r.stdout and "42" in r.stdout


def test_line_mode_and_dot_mode(run):
    r = sql(run, "select 1 as n, 'x' as s", "-line")
    ok(r)
    assert "n = 1" in r.stdout and "s = x" in r.stdout


def test_once_persists_until_output_reset(run, tmp_path):
    out = tmp_path / "captured.txt"
    r = run("-c", f".once {out}", "-c", "select 1", "-c", "select 2", "-c", ".output", "-c", "select 3")
    ok(r)
    assert "1" not in r.stdout and "2" not in r.stdout and "3" in r.stdout
    assert "1" in out.read_text() and "2" in out.read_text()


def test_changes_is_accepted_without_row_count_noise(run):
    r = run("-c", ".changes on", "-c", "create table t(i int)", "-c", "insert into t values (1),(2)")
    ok(r)
    assert r.stdout == "" and r.stderr == ""


def test_timer_appends_runtime_to_stdout(run):
    r = run("-c", ".timer on", "-c", "select 1")
    ok(r)
    assert "Run Time (s): real" in r.stdout
    assert r.stderr == ""


def test_dot_version_first_two_lines(run):
    r = run("-c", ".version")
    ok(r)
    assert r.stdout.splitlines()[:2] == ["DuckDB v0.0.1 (Unknown Version) 780a7396", "gcc-11.4.0"]


def test_schema_canonicalizes_type_and_indent_option(run):
    for option in ("-indent", "--indent"):
        r = run("-c", "create table test(id int primary key, v varchar not null)", "-c", f".schema {option} test")
        ok(r)
        assert r.stdout == "CREATE TABLE test(id INTEGER PRIMARY KEY, v VARCHAR NOT NULL);;\n"


def test_show_and_call_table_function(run):
    r = run("-csv", "-c", "create table table1(mylittlecolumn integer)", "-c", "show table1")
    ok(r)
    assert "column_name,column_type,null,key,default,extra" in r.stdout
    assert "mylittlecolumn,INTEGER" in r.stdout
    r = run("-csv", "-c", "call range(4)")
    ok(r)
    assert r.stdout.splitlines() == ["range", "0", "1", "2", "3"]


def test_dot_dump_replays_schema_and_rows(run):
    r = run("-csv", "-c", "create table t(i int)", "-c", "insert into t values (2)", "-c", ".dump t")
    ok(r)
    assert "CREATE TABLE" in r.stdout and "INSERT INTO" in r.stdout and "2" in r.stdout


def test_unimplemented_dot_commands_are_named_errors(run):
    for command in (".sha3sum", ".clone"):
        r = run("-c", command)
        assert r.returncode != 0 and "Unknown Command Error" in r.stderr


def test_dot_last_retention_only_for_truncated_duckbox(run):
    r = run("-c", ".maxrows 1", "-c", "select * from range(3)", "-c", "select count(*) from _", "-c", ".last")
    ok(r)
    assert "3" in r.stdout
    r = run("-c", "select 77", "-c", ".last")
    ok(r)
    assert r.stdout.count("77") == 1
    r = run("-c", "select * from _")
    assert r.returncode == 1 and 'no result available' in r.stderr


def test_error_categories_and_source_excerpt(run):
    r = run("-c", "select * from table_that_does_not_exist")
    assert r.returncode == 1 and "Catalog Error" in r.stderr and "LINE 1:" in r.stderr and "^" in r.stderr
    r = run("-c", "select 1 + 'not-an-int'")
    assert r.returncode != 0 and ("Binder Error" in r.stderr or "Conversion Error" in r.stderr)


def test_format_mode_table_argument_error_phrase(run):
    r = run("-c", ".mode json target")
    assert r.returncode == 1 and "TABLE argument can only be used with .mode insert" in r.stderr
