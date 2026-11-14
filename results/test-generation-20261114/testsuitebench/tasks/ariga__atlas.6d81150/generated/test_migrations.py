import base64
import hashlib
from pathlib import Path

from conftest import write


def test_hash_empty_directory_exact(invoke, tmp_path):
    d = tmp_path / "migrations"
    d.mkdir()
    r = invoke("migrate", "hash", "--dir", f"file://{d}")
    assert r.returncode == 0 and r.stdout == b"" and r.stderr == b""
    assert (d / "atlas.sum").read_text() == "h1:47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=\n"


def test_hash_uses_cumulative_sha256_and_lexical_sql_only(invoke, tmp_path):
    d = tmp_path / "migs"
    d.mkdir()
    write(d / "2_b.sql", b"second\r\n")
    write(d / "1_a.sql", b"first\n")
    write(d / "ignored.txt", b"ignored")
    (d / "subdir").mkdir()
    r = invoke("migrate", "hash", "--dir", f"file://{d}")
    assert r.returncode == 0 and r.stdout == b"" and r.stderr == b""
    state = hashlib.sha256()
    entries = []
    for name, content in [("1_a.sql", b"first\n"), ("2_b.sql", b"second\r\n")]:
        state.update(name.encode()); state.update(content)
        digest = base64.b64encode(state.digest()).decode()
        entries.append((name, digest))
    directory = hashlib.sha256()
    for name, digest in entries:
        directory.update(name.encode()); directory.update(digest.encode())
    expected = "h1:" + base64.b64encode(directory.digest()).decode() + "\n"
    expected += "".join(f"{name} h1:{digest}\n" for name, digest in entries)
    assert (d / "atlas.sum").read_text() == expected


def test_validate_missing_and_repaired_checksum(invoke, tmp_path):
    d = tmp_path / "migrations"
    d.mkdir(); write(d / "20240101000001_init.sql", "CREATE TABLE t(id INTEGER);\n")
    r = invoke("migrate", "validate", "--dir", f"file://{d}")
    assert r.returncode == 1 and "checksum file not found" in r.stderr.decode()
    assert "checksum error in your migration directory" in r.stdout.decode()
    invoke("migrate", "hash", "--dir", f"file://{d}")
    ok = invoke("migrate", "validate", "--dir", f"file://{d}")
    assert ok.returncode == 0 and ok.stdout == b"" and ok.stderr == b""


def test_validate_detects_edit(invoke, tmp_path):
    d = tmp_path / "migrations"; d.mkdir()
    f = write(d / "1_init.sql", "SELECT 1;\n")
    invoke("migrate", "hash", "--dir", f"file://{d}")
    f.write_text("SELECT 2;\n")
    r = invoke("migrate", "validate", "--dir", f"file://{d}")
    assert r.returncode == 1 and "checksum mismatch" in r.stderr.decode()
    assert "L2: 1_init.sql was edited" in r.stdout.decode()


def test_validate_empty_directory_without_sum(invoke, tmp_path):
    d = tmp_path / "empty"; d.mkdir()
    r = invoke("migrate", "validate", "--dir", f"file://{d}")
    assert r.returncode == 0 and r.stdout == b"" and r.stderr == b""


def test_mem_hash_ignores_invalid_format(invoke):
    r = invoke("migrate", "hash", "--dir", "mem://x?format=nonesuch")
    assert r.returncode == 0 and r.stdout == b"" and r.stderr == b""


def test_new_creates_timestamped_file_and_hash(invoke, tmp_path):
    d = tmp_path / "migrations"
    r = invoke("migrate", "new", "sample", "--dir", f"file://{d}")
    assert r.returncode == 0 and r.stdout == b"" and r.stderr == b""
    sql = list(d.glob("*_sample.sql"))
    assert len(sql) == 1 and len(sql[0].name.split("_", 1)[0]) == 14
    assert sql[0].read_bytes() == b"" and (d / "atlas.sum").exists()


def test_import_empty_source_stdout_has_no_newline(invoke, tmp_path):
    source = tmp_path / "source"; source.mkdir()
    target = tmp_path / "target"; target.mkdir(); write(target / "occupied.txt", "keep")
    r = invoke("migrate", "import", "--from", f"file://{source}?format=liquibase", "--to", f"file://{target}")
    assert r.returncode == 0 and r.stdout == b"nothing to import" and r.stderr == b""
    assert (target / "occupied.txt").read_text() == "keep"


def test_migrate_apply_validation_and_amount_errors(invoke, tmp_path):
    d = tmp_path / "migrations"; d.mkdir()
    base = ("migrate", "apply", "--url", "sqlite://file?mode=memory", "--dir", f"file://{d}")
    r = invoke(*base, "0")
    assert r.returncode == 1 and r.stderr.decode().startswith("Error: cannot apply '0' migration files")
    n = invoke(*base, "--", "-1")
    assert n.returncode == 1 and n.stderr.decode().startswith("Error: cannot apply '-1' migration files")


def test_migrate_status_pending_and_latest(invoke, tmp_path):
    d = tmp_path / "migrations"; d.mkdir()
    write(d / "20240101000001_first.sql", "CREATE TABLE first_table(id INTEGER);\n")
    write(d / "20240101000002_second.sql", "CREATE TABLE second_table(id INTEGER);\n")
    invoke("migrate", "hash", "--dir", f"file://{d}")
    url = f"sqlite:///{tmp_path / 'status.db'}"
    pending = invoke("migrate", "status", "--url", url, "--dir", f"file://{d}")
    assert pending.returncode == 0
    assert "Migration Status: PENDING" in pending.stdout.decode()
    assert "-- Pending Files:   2" in pending.stdout.decode()
    applied = invoke("migrate", "apply", "--url", url, "--dir", f"file://{d}")
    assert applied.returncode == 0 and "2 migrations" in applied.stdout.decode()
    latest = invoke("migrate", "status", "--url", url, "--dir", f"file://{d}")
    assert latest.returncode == 0 and "Migration Status: OK" in latest.stdout.decode()
    assert "-- Pending Files:   0" in latest.stdout.decode()


def test_migrate_status_requires_directory_before_url(invoke):
    r = invoke("migrate", "status")
    assert r.returncode == 1 and r.stdout == b""
    assert r.stderr.decode().startswith("Error: sql/migrate: stat migrations: no such file or directory")


def test_migrate_import_golang_migrate_up_file(invoke, tmp_path):
    source = tmp_path / "foreign"; source.mkdir()
    write(source / "1_init.up.sql", "CREATE TABLE t(id INTEGER);\n")
    target = tmp_path / "atlas"
    r = invoke("migrate", "import", "--from", f"file://{source}?format=golang-migrate", "--to", f"file://{target}")
    assert r.returncode == 0 and r.stdout == b"" and r.stderr == b""
    assert (target / "1_init.sql").read_text() == "CREATE TABLE t(id INTEGER);\n"
    assert (target / "atlas.sum").exists()
