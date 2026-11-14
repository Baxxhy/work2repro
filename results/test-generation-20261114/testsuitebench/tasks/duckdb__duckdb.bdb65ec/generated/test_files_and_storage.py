from conftest import failed, ok


def test_copy_csv_roundtrip_and_read_csv(run, tmp_path):
    csv = tmp_path / "data.csv"
    db = tmp_path / "copy.duckdb"
    r = run("-c", f"copy (select 1 as id, 'a,b' as s union all select 2, null) to '{csv}' (header)")
    ok(r)
    assert csv.exists()
    r = run("-csv", db, f"create table t as select * from read_csv_auto('{csv}')", "select * from t order by id")
    ok(r)
    assert "id,s" in r.stdout and '1,"a,b"' in r.stdout and "2," in r.stdout


def test_copy_from_to_missing_paths_are_io_errors(run, tmp_path):
    missing = tmp_path / "absent.csv"
    r = run("-c", f"select * from read_csv_auto('{missing}')")
    assert r.returncode == 1 and "IO Error" in r.stderr
    r = run("-c", f"copy (select 1) to '{tmp_path / 'no-dir' / 'x.csv'}'")
    assert r.returncode == 1 and "IO Error" in r.stderr


def test_null_path_list_is_parser_error(run):
    for query, function in (("select * from read_csv_auto(null)", "read_csv_auto"), ("select * from glob(null)", "glob")):
        r = run("-c", query)
        assert r.returncode == 1
        assert f"{function} cannot take NULL list as parameter" in r.stderr


def test_attach_cross_database_and_detach(run, tmp_path):
    db = tmp_path / "attached.duckdb"
    r = run("-csv", "-c", f"attach '{db}' as other", "-c", "create table other.main.t(i int)", "-c", "insert into other.main.t values(8)", "-c", "select * from other.main.t", "-c", "detach other")
    ok(r)
    assert "8" in r.stdout
    r = run("-csv", db, "select * from t")
    ok(r)
    assert "8" in r.stdout


def test_attached_transaction_single_database_write_limit(run, tmp_path):
    db = tmp_path / "other.duckdb"
    r = run("-c", "create table t(i int); begin; insert into t values(1);",)
    ok(r)
    # Attach and write to two catalogs in one transaction.
    r = run("-c", f"attach '{db}' as o; create table main.t(i int); create table o.main.t(i int); begin; insert into main.t values(1); insert into o.main.t values(2)")
    assert r.returncode == 1 and "TransactionContext Error" in r.stderr
    assert "single transaction can only write to a single attached database" in r.stderr


def test_export_import_across_command_sources(run, tmp_path):
    export = tmp_path / "exported"
    r = run("-c", "create table a as select * from range(3) t(i)", "-c", f"export database '{export}'", "-c", "drop table a", "-c", f"import database '{export}'", "-csv", "-c", "select sum(i) from a")
    ok(r)
    assert r.stdout.endswith("3\n")


def test_checkpoint_and_reopen_preserve_altered_schema(run, tmp_path):
    db = tmp_path / "alter.duckdb"
    ok(run(db, "create table t(i int)", "insert into t values(2)", "alter table t add column s varchar default 'x'", "checkpoint"))
    r = run("-csv", db, "select * from t")
    ok(r)
    assert "i,s" in r.stdout and "2,x" in r.stdout


def test_unique_allows_multiple_nulls_and_primary_key_does_not(run):
    r = run("-c", "create table t(i int unique); insert into t values(null),(null)")
    ok(r)
    r = run("-c", "create table t(i int primary key); insert into t values(null)")
    assert r.returncode != 0 and "Constraint Error" in r.stderr


def test_foreign_key_checks_and_cascade_rejected(run):
    r = run("-c", "create table p(i int primary key); create table c(i int references p(i)); insert into c values(2)")
    assert r.returncode != 0 and "Constraint Error" in r.stderr
    r = run("-c", "create table p(i int primary key); create table c(i int references p(i) on delete cascade)")
    assert r.returncode != 0 and "CASCADE" in r.stderr.upper()


def test_invalid_header_rejected_cleanly(run, tmp_path):
    db = tmp_path / "bad.duckdb"
    db.write_bytes(b"not a duckdb database")
    r = run(db, "select 1")
    assert r.returncode == 1 and "IO Error" in r.stderr


def test_dot_import_missing_arguments_use_stdout(run):
    r = run("-c", ".import")
    assert r.returncode == 1 and r.stderr == ""
    assert r.stdout.startswith("ERROR: missing FILE argument. Usage:") and "\x1b[" in r.stdout
    r = run("-c", ".import file.csv")
    assert r.returncode == 1 and r.stderr == ""
    assert r.stdout.startswith("ERROR: missing TABLE argument. Usage:")


def test_extensions_and_unloaded_owned_types(run):
    r = run("-c", "select 'x'::json")
    assert r.returncode != 0 and "json" in r.stderr.lower() and "extension" in r.stderr.lower()
    r = run("-c", "load json")
    assert r.returncode != 0
    r = run("-c", "set TimeZone='ECT'")
    assert r.returncode != 0 and "exists in the icu extension" in r.stderr


def test_safe_mode_disables_file_read_and_attach(run, tmp_path):
    csv = tmp_path / "safe.csv"
    csv.write_text("i\n1\n")
    r = run("-safe", "-c", f"select * from read_csv('{csv}')")
    assert r.returncode == 1 and "Permission Error" in r.stderr and str(csv) in r.stderr
    r = run("-safe", "-c", f"attach '{tmp_path / 'db.duckdb'}' as x")
    assert r.returncode == 1 and "Permission Error" in r.stderr


def test_readonly_alias_has_same_write_behavior(run, tmp_path):
    db = tmp_path / "readonly.duckdb"
    ok(run(db, "create table t(i int)"))
    a = run("-readonly", db, "create table x(i int)")
    b = run("--readonly", db, "create table x(i int)")
    assert a.returncode != 0 and b.returncode != 0
    assert "read-only" in a.stderr.lower() and "read-only" in b.stderr.lower()
