from conftest import failed, ok


def test_core_joins_grouping_cte_and_set_operations(run):
    q = ("with x as (select 1 i union all select 2), y as (select 2 i union all select 3) "
         "select x.i, count(*) n from x join y using(i) group by x.i having count(*)=1 order by 1")
    r = run("-csv", "-c", q)
    ok(r)
    assert r.stdout == "i,n\n2,1\n"
    r = run("-csv", "-c", "select 1 union all select 1 intersect select 2")
    ok(r)
    assert "1" in r.stdout


def test_recursive_cte_and_qualify(run):
    r = run("-csv", "-c", "with recursive t(i) as (values (1) union all select i+1 from t where i<4) select i from t order by i")
    ok(r)
    assert r.stdout == "i\n1\n2\n3\n4\n"
    r = run("-csv", "-c", "select i, row_number() over(order by i) rn from range(5) t(i) qualify rn=2")
    ok(r)
    assert "1,2" in r.stdout


def test_dml_returning_and_rollback(run):
    r = run("-csv", "-c", "create table t(i int)", "-c", "insert into t values (1),(2) returning i", "-c", "update t set i=i+10 where i=1 returning i", "-c", "delete from t where i=2 returning i")
    ok(r)
    assert "1" in r.stdout and "12" in r.stdout and "2" in r.stdout
    r = run("-csv", "-c", "create table t(i int)", "-c", "begin", "-c", "insert into t values(1)", "-c", "rollback", "-c", "select count(*) from t")
    ok(r)
    assert r.stdout.endswith("0\n")


def test_unique_primary_key_and_check_constraints(run):
    r = run("-c", "create table t(i int primary key, v int check(v>0)); insert into t values (1,1),(1,2)")
    assert r.returncode != 0 and "Constraint Error" in r.stderr
    r = run("-c", "create table t(i int check(i>0)); insert into t values (-1)")
    assert r.returncode != 0 and "Constraint Error" in r.stderr


def test_transaction_context_exact_categories(run):
    for q, msg in (("begin; begin", "cannot start a transaction within a transaction"),
                   ("commit", "cannot commit - no transaction is active"),
                   ("rollback", "cannot rollback - no transaction is active")):
        r = run("-c", q)
        assert r.returncode == 1 and "TransactionContext Error" in r.stderr and msg in r.stderr


def test_error_in_one_shot_stops_later_statements(run):
    r = run("-csv", "-c", "begin; create table t(i int primary key); insert into t values (1),(1); select 99; rollback")
    assert r.returncode == 1 and "Constraint Error" in r.stderr
    assert "99" not in r.stdout
    assert "Current transaction is aborted" not in r.stderr


def test_types_casts_null_three_valued_logic_and_nested_values(run):
    r = run("-csv", "-c", "select typeof(1::utinyint), try_cast('bad' as int) is null, null = 1, [1,2][-1]")
    ok(r)
    assert "UTINYINT,true,,2" in r.stdout or "UTINYINT,true,NULL,2" in r.stdout
    r = run("-csv", "-c", "select hex(('abcdef'::blob)[2:4]), array_slice('abcdef'::blob,2,4)")
    ok(r)
    assert "626364" in r.stdout


def test_cast_errors_and_try_cast(run):
    r = run("-c", "select 999999999999999999999999::tinyint")
    assert r.returncode != 0 and ("Conversion Error" in r.stderr or "Out of Range Error" in r.stderr)
    r = run("-csv", "-c", "select try_cast('x' as integer) is null")
    ok(r)
    assert "true" in r.stdout


def test_functions_numeric_string_hash_temporal(run):
    r = run("-csv", "-c", "select md5('hello'), sha1('hello'), sha256('hello'), array_to_string(['a','b','c'], null)")
    ok(r)
    assert "5d41402abc4b2a76b9719d911017c592" in r.stdout
    assert "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d" in r.stdout
    assert "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824" in r.stdout
    assert "a,b,c" in r.stdout
    r = run("-csv", "-c", "select date_part('month', date '2024-02-29'), last_day(date '2024-02-01')")
    ok(r)
    assert "2,2024-02-29" in r.stdout


def test_lambda_transform_and_array_to_string_null_separator(run):
    r = run("-csv", "-c", "select list_transform([1,2,3], lambda x: x*2), array_to_string(['a','b'], null)")
    ok(r)
    assert "[2, 4, 6]" in r.stdout and "a,b" in r.stdout


def test_prepare_execute_reuse_and_direct_parameter_error(run):
    r = run("-csv", "-c", "prepare p as select $1 + 2", "-c", "execute p(3)", "-c", "execute p(5)", "-c", "deallocate p")
    ok(r)
    assert "5" in r.stdout and "7" in r.stdout
    r = run("-c", "select ?")
    assert r.returncode == 1 and "Prepared statement parameters cannot be used directly" in r.stderr


def test_sparse_numbered_parameters_prepare_successfully(run):
    r = run("-c", "prepare p as select $1+$3")
    ok(r)
    assert r.stdout == "" and r.stderr == ""


def test_macros_and_views(run):
    r = run("-csv", "-c", "create macro twice(x) as x*2", "-c", "create table t(i int)", "-c", "insert into t values (2),(3)", "-c", "create view v as select twice(i) as n from t", "-c", "select sum(n) from v")
    ok(r)
    assert r.stdout.endswith("10\n")


def test_dropping_view_dependency_then_query_errors(run):
    r = run("-c", "create table t(i int); create view v as select * from t; drop table t")
    ok(r)
    r = run("-c", "create table t(i int); create view v as select * from t; drop table t; select * from v")
    assert r.returncode == 1 and "Catalog Error: Table with name t does not exist!" in r.stderr


def test_index_uniqueness_and_sequences(run):
    r = run("-c", "create table t(i int); create unique index idx on t(i); insert into t values(1),(1)")
    assert r.returncode != 0 and "Constraint Error" in r.stderr
    r = run("-csv", "-c", "create sequence s start 4 increment 2", "-c", "select nextval('s'), nextval('s')")
    ok(r)
    assert "4,6" in r.stdout


def test_table_functions_and_information_schema(run):
    r = run("-csv", "-c", "create table sample(i int)", "-c", "select table_name from information_schema.tables where table_name='sample'", "-c", "select count(*) from duckdb_triggers()")
    ok(r)
    assert "sample" in r.stdout and "0" in r.stdout
    r = run("-csv", "-c", "select * from duckdb_connection_count()")
    ok(r)
    assert "count\n1\n" in r.stdout


def test_setting_evaluates_expressions_and_allowed_configs(run):
    r = run("-csv", "-c", "set threads=concat('2','')", "-c", "select current_setting('threads')")
    ok(r)
    assert "2" in r.stdout
    r = run("-csv", "-c", "set allowed_configs=['max_expression_depth']", "-c", "set lock_configuration=true", "-c", "set max_expression_depth=50", "-c", "select current_setting('max_expression_depth')")
    ok(r)
    assert "50" in r.stdout


def test_explain_and_geometry_roundtrip(run):
    r = run("-csv", "-c", "explain select sum(i) from range(4) t(i)")
    ok(r)
    assert "EXPLAIN" in r.stdout and "AGGREGATE" in r.stdout.upper()
    r = run("-csv", "-c", "select st_astext(st_geomfromwkb(st_aswkb('POINT (1 2)'::geometry)))")
    ok(r)
    assert "POINT (1 2)" in r.stdout


def test_variant_memory_and_nth_value_zero_semantics(run):
    r = run("-csv", "-c", "select 1::variant")
    ok(r)
    r = run("-csv", "-c", "select nth_value(i,0) over(order by i) from range(3) t(i)")
    ok(r)
    assert r.stdout.splitlines() == ["nth_value(i, 0) OVER (ORDER BY i)", "", "", ""]


def test_error_json_configuration(run):
    r = run("-c", "set errors_as_json=true; select * from missing_table")
    assert r.returncode == 1
    assert '"exception_type":"Catalog"' in r.stderr
    assert '"name":"missing_table"' in r.stderr


def test_deprecated_lambda_warning_and_warning_as_error(run):
    r = run("-csv", "-c", "select list_transform([1,2], x -> x+1)")
    ok(r)
    assert "WARNING:" in r.stdout and "Deprecated lambda arrow" in r.stdout
    assert r.stderr == ""
    r = run("-c", "set warnings_as_errors=true; select list_transform([1], x -> x+1)")
    assert r.returncode != 0


def test_trigger_parser_special_diagnostics(run):
    r = run("-c", "create trigger x")
    assert r.returncode == 1 and "Parser Error" in r.stderr and "LINE 1:" in r.stderr
    r = run("-c", "drop trigger x")
    assert r.returncode == 1 and r.stderr == "Parser Error: syntax error at end of input\n"
