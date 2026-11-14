import json
from pathlib import Path

from conftest import write


def test_inspect_empty_sqlite_and_json(invoke):
    r = invoke("schema", "inspect", "--url", "sqlite://file?mode=memory")
    assert r.returncode == 0 and "schema \"main\" {\n}" in r.stdout.decode()
    j = invoke("schema", "inspect", "--url", "sqlite://file?mode=memory", "--format", "{{ json . }}")
    assert j.returncode == 0
    data = json.loads(j.stdout)
    assert data["schemas"][0]["name"] == "main"


def test_inspect_sqlite_table_metadata(invoke, tmp_path):
    db = tmp_path / "test.db"
    # Initialize using the same SQLite connection available on the platform.
    import sqlite3
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    con.close()
    r = invoke("schema", "inspect", "--url", f"sqlite:///{db}")
    assert r.returncode == 0
    out = r.stdout.decode()
    assert 'table "users"' in out and 'column "id"' in out and 'type = integer' in out
    assert 'column "name"' in out and 'null = false' in out


def test_schema_apply_dry_run_then_apply(invoke, tmp_path):
    db = tmp_path / "app.db"
    schema = write(tmp_path / "schema.hcl", 'schema "main" {}\ntable "users" { schema = schema.main column "id" { type = int } }\n')
    # Use a multiline, conventional HCL fixture to avoid parser-layout ambiguity.
    schema.write_text('schema "main" {}\ntable "users" {\n  schema = schema.main\n  column "id" { type = int }\n}\n')
    url = f"sqlite:///{db}"
    dry = invoke("schema", "apply", "--url", url, "--to", f"file://{schema}", "--dry-run")
    assert dry.returncode == 0 and "-- Planned Changes:" in dry.stdout.decode()
    assert not db.exists()


def test_schema_apply_and_inspect_persist(invoke, tmp_path):
    db = tmp_path / "apply.db"
    schema = write(tmp_path / "schema.hcl", 'schema "main" {}\ntable "users" {\n  schema = schema.main\n  column "id" { type = int }\n}\n')
    url = f"sqlite:///{db}"
    applied = invoke("schema", "apply", "--url", url, "--to", f"file://{schema}", "--auto-approve")
    assert applied.returncode == 0 and "CREATE TABLE" in applied.stdout.decode()
    seen = invoke("schema", "inspect", "--url", url)
    assert seen.returncode == 0 and 'table "users"' in seen.stdout.decode()


def test_inspect_driver_and_url_errors(invoke):
    r = invoke("schema", "inspect", "--url", "://missing-scheme")
    assert r.returncode == 1 and r.stdout == b"" and r.stderr.decode() == "Error: missing protocol scheme\n"
    p = invoke("schema", "inspect", "--url", "mysql://localhost:99999/db")
    assert p.returncode == 1 and p.stdout == b""
    assert p.stderr.decode() == "Error: mysql: query system variables: dial tcp: address 99999: invalid port\n"


def test_schema_diff_identical_and_change(invoke, tmp_path):
    db = tmp_path / "diff.db"
    schema = write(tmp_path / "schema.hcl", 'schema "main" {}\ntable "users" {\n  schema = schema.main\n  column "id" { type = int }\n}\n')
    url = f"sqlite:///{db}"
    first = invoke("schema", "diff", "--from", url, "--to", f"file://{schema}", "--dev-url", "sqlite://file?mode=memory")
    assert first.returncode == 0 and "CREATE TABLE" in first.stdout.decode()
    applied = invoke("schema", "apply", "--url", url, "--to", f"file://{schema}", "--auto-approve")
    assert applied.returncode == 0
    second = invoke("schema", "diff", "--from", url, "--to", f"file://{schema}", "--dev-url", "sqlite://file?mode=memory")
    assert second.returncode == 0 and second.stdout.decode() == "Schemas are synced, no changes to be made.\n"


def test_inspect_template_parse_error(invoke):
    r = invoke("schema", "inspect", "--url", "sqlite://file?mode=memory", "--format", "{{.Foo}")
    assert r.returncode == 1 and r.stdout == b""
    assert r.stderr.decode() == "Error: parse log format: template: format:1: bad character U+007D '}'\n"

