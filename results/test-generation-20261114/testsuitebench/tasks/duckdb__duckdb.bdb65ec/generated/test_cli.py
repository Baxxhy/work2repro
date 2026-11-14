from conftest import failed, ok


def test_version_contract(run):
    r = run("--version")
    ok(r)
    assert r.stdout == "v0.0.1 (Unknown Version) 780a7396\n"
    assert r.stderr == ""


def test_version_alias_and_sql_version(run):
    r = run("-version")
    ok(r)
    assert r.stdout.splitlines() == ["v0.0.1 (Unknown Version) 780a7396"]
    r = run("-csv", "-c", "select version()")
    ok(r)
    assert r.stdout.strip() == "version()\nv0.0.1"


def test_help_has_documented_options_and_styling(run):
    r = run("-help")
    ok(r)
    for word in ("FILENAME", "[SQL]", "OPTIONS:", "-ascii", "-bail", "-storage-version", "-unsigned"):
        assert word in r.stdout
    assert "\x1b[" in r.stdout


def test_unknown_option_and_question_mark_are_errors(run):
    for option in ("-?", "--definitely-unknown"):
        r = run(option)
        assert r.returncode == 1
        assert option in r.stderr
        assert "-help" in r.stderr


def test_positional_commands_run_in_order(run):
    r = run("-csv", ":memory:", "create table t(i int)", "insert into t values (1),(2)", "select sum(i) from t")
    ok(r)
    assert "3" in r.stdout


def test_repeated_c_options_and_alias_s(run):
    r = run("-csv", "-c", "create table t(i int)", "-s", "insert into t values (5)", "-c", "select i from t")
    ok(r)
    assert r.stdout.endswith("5\n")


def test_stdin_multiline_and_recovery(run):
    sql = "create table t(i int);\ninsert into t values (7);\nselect * from missing_table;\nselect i+1 from t;\n"
    r = run("-csv", stdin=sql)
    assert r.returncode != 0
    assert "Catalog Error" in r.stderr
    assert "8" in r.stdout


def test_stdin_quotes_comments_and_dot_command_position(run):
    text = "-- comment\ncreate table t(s varchar);\ninsert into t values ('first\nsecond');\nselect s from t;\n"
    r = run("-csv", stdin=text)
    ok(r)
    assert '"first\nsecond"' in r.stdout
    r = run("-csv", "-c", "select '.tables' as literal")
    ok(r)
    assert ".tables" in r.stdout


def test_double_dash_output_aliases_and_stdin(run):
    r = run("--csv", "--header", stdin="select 6 as n;")
    ok(r)
    assert r.stdout == "n\n6\n"


def test_repeated_init_is_suppressed_by_double_dash(run, tmp_path):
    missing = tmp_path / "does-not-exist.sql"
    r = run("-init", missing, "--no-init", "--no-stdin")
    ok(r)
    assert r.stderr == ""


def test_bail_stops_after_first_error(run):
    r = run("-csv", "-bail", stdin="select * from absent; select 42;")
    assert r.returncode != 0
    assert "42" not in r.stdout


def test_c_failure_prevents_later_command_line_commands(run):
    r = run("-csv", "-c", "select * from absent", "-c", "select 42")
    assert r.returncode == 1
    assert "42" not in r.stdout


def test_no_stdin_and_exit_codes(run):
    r = run("-no-stdin")
    ok(r)
    assert r.stdout == ""
    r = run("-no-stdin", "-c", ".exit 7")
    assert r.returncode == 7


def test_init_suppression_applies_regardless_of_order(run, tmp_path):
    init = tmp_path / "missing init.sql"
    for args in (("-no-init", "-init", init), ("-init", init, "--no-init")):
        r = run(*args, "-no-stdin")
        ok(r)
        assert r.stderr == ""


def test_init_precedes_commands_and_notices(run, tmp_path):
    init = tmp_path / "init.sql"
    init.write_text("create table initialized(i int);")
    r = run("-csv", "-init", init, "-c", "select count(*) from initialized", "-no-stdin")
    ok(r)
    assert "-- Loading resources from" in r.stderr
    assert "0" in r.stdout


def test_missing_script_is_io_error(run):
    r = run("-f", "missing-script.sql")
    assert r.returncode == 1
    assert "IO Error" in r.stderr


def test_format_unavailable_extension_asymmetry(run, tmp_path):
    r = run("-format", "select 1")
    ok(r)
    assert (r.stdout, r.stderr) == ("", "")
    f = tmp_path / "query.sql"
    f.write_text("select 1")
    r = run("-format-file", f)
    ok(r)
    assert r.stdout == ""
    assert "Catalog Error" in r.stderr and "autocomplete" in r.stderr


def test_invalid_storage_version_status_zero_and_no_sql(run):
    r = run("-storage-version", "invalid_ver", "-c", "select 123")
    ok(r)
    assert "Invalid Input Error" in r.stderr and "invalid_ver" in r.stderr
    assert "123" not in r.stdout


def test_missing_storage_variant_requires_new_format(run, tmp_path):
    db = tmp_path / "variant.duckdb"
    r = run(db, "create table v(x variant)")
    failed(r, "VARIANT columns are not supported in storage versions prior to v1.5.0")
    db2 = tmp_path / "variant-new.duckdb"
    r = run("-storage-version", "v1.5.0", db2, "create table v(x variant)", "insert into v values (1)")
    ok(r)


def test_empty_file_is_not_silently_initialized(run, tmp_path):
    db = tmp_path / "empty.duckdb"
    db.touch()
    r = run(db, "select 1")
    assert r.returncode == 1 and "not a valid DuckDB database file" in r.stderr


def test_persistent_database_reopens_and_isolates(run, tmp_path):
    first = tmp_path / "one.duckdb"
    second = tmp_path / "two.duckdb"
    ok(run(first, "create table t(i int)", "insert into t values (9)"))
    r = run("-csv", first, "select sum(i) from t")
    ok(r)
    assert r.stdout.endswith("9\n")
    r = run("-csv", second, "show tables")
    ok(r)
    assert "t" not in r.stdout


def test_readonly_reads_and_rejects_writes(run, tmp_path):
    db = tmp_path / "ro.duckdb"
    ok(run(db, "create table t(i int)", "insert into t values (3)"))
    r = run("--readonly", "-csv", db, "select * from t")
    ok(r)
    assert "3" in r.stdout
    r = run("-readonly", db, "insert into t values (4)")
    assert r.returncode != 0 and "read-only" in r.stderr.lower()


def test_safe_mode_blocks_filesystem_and_shell_commands(run, tmp_path):
    path = tmp_path / "out.csv"
    r = run("--safe", "-c", f"copy (select 1) to '{path}'")
    assert r.returncode == 1
    assert "Permission Error" in r.stderr and "file system operations are disabled" in r.stderr
    r = run("-safe", "-c", ".shell echo unsafe")
    assert r.returncode != 0 and ".sh/.system cannot be used in -safe mode" in r.stderr


def test_dot_safe_mode_and_safe_block_categories(run):
    r = run("-csv", stdin=".safe_mode\nselect 2;\n.output /tmp/blocked\n")
    assert r.returncode != 0
    assert "2" in r.stdout
    assert ".output/.once/.excel cannot be used in -safe mode" in r.stderr


def test_readonly_temp_objects_are_allowed(run, tmp_path):
    db = tmp_path / "readonly-temp.duckdb"
    ok(run(db, "create table base(i int)"))
    r = run("-readonly", "-csv", db, "create temp table temp_t(i int)", "insert into temp_t values (2)", "select * from temp_t")
    ok(r)
    assert "2" in r.stdout
