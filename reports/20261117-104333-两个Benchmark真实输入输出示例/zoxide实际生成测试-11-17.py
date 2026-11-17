import os
import pathlib
import subprocess

import pytest


BIN = pathlib.Path(os.environ.get("EXECUTABLE", "/workspace/executable"))


@pytest.fixture
def ctx(tmp_path):
    data = tmp_path / "data with ü"
    data.mkdir()
    cwd = tmp_path / "work"
    cwd.mkdir()
    env = os.environ.copy()
    for key in ("_ZO_MAXAGE", "_ZO_EXCLUDE_DIRS", "_ZO_RESOLVE_SYMLINKS", "_ZO_ECHO", "_ZO_FZF_OPTS"):
        env.pop(key, None)
    env["_ZO_DATA_DIR"] = str(data)

    def call(*args, extra=None, cwd_override=None):
        e = env.copy()
        if extra:
            e.update(extra)
        return subprocess.run([str(BIN), *map(str, args)], cwd=cwd_override or cwd, env=e,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    return tmp_path, cwd, data, call


def add_dir(ctx, name, *args):
    _, cwd, _, call = ctx
    p = cwd / name
    p.mkdir(parents=True, exist_ok=True)
    r = call("add", *args, str(p))
    assert r.returncode == 0, r.stderr
    assert r.stdout == b"" and r.stderr == b""
    return str(p)


def test_root_version_help_and_bare_invocation(ctx):
    *_, call = ctx
    assert call("--version").stdout == b"zoxide 0.9.9\n"
    h = call("--help")
    bare = call()
    assert h.returncode == 0 and h.stdout.startswith(b"zoxide 0.9.9\n")
    assert bare.returncode == 2 and bare.stderr == h.stdout


@pytest.mark.parametrize("args", [("add",), ("init",), ("import",), ("add", "--score", "x", "/tmp")], ids=["add-required", "init-required", "import-required", "bad-score"])
def test_usage_errors_are_status_two(ctx, args):
    *_, call = ctx
    r = call(*args)
    assert r.returncode == 2 and not r.stdout and r.stderr.startswith(b"error:")


def test_add_normalizes_accumulates_and_query_formats_scores(ctx):
    _, cwd, _, call = ctx
    p = cwd / "space ü & dir"
    p.mkdir()
    assert call("add", str(p / "." )).returncode == 0
    assert call("add", "--score=2", str(p)).returncode == 0
    q = call("query", "--score", "--list")
    assert q.returncode == 0
    assert q.stdout.decode().splitlines() == ["  12.0 " + str(p)]


def test_add_batch_validation_is_atomic(ctx):
    _, cwd, _, call = ctx
    good = cwd / "good"
    good.mkdir()
    assert call("add", str(good), str(cwd / "missing")).returncode == 1
    assert call("query", "--list").stdout == b""


def test_keyword_matching_order_literal_and_final_component(ctx):
    _, cwd, _, call = ctx
    p = cwd / "alpha" / "beta" / "gamma"
    p.mkdir(parents=True)
    assert call("add", str(p)).returncode == 0
    assert call("query", "--list", "alpha", "gamma").stdout == (str(p) + "\n").encode()
    assert call("query", "--list", "gamma", "alpha").stdout == b""
    assert call("query", "--list", "alpha", "gamma").returncode == 0
    assert call("query", "--list", "a.*", "gamma").stdout == b""


def test_query_no_match_and_single_excluded_diagnostic(ctx):
    p = add_dir(ctx, "only")
    *_, call = ctx
    r = call("query", "does-not-exist")
    assert r.returncode == 1 and r.stderr == b"zoxide: no match found\n"
    r = call("query", "--exclude", p)
    assert r.returncode == 1 and r.stderr == b"zoxide: you are already in the only match\n"


def test_all_controls_unavailable_pruning_and_list_empty_success(ctx):
    _, cwd, _, call = ctx
    p = cwd / "gone"
    p.mkdir()
    call("add", str(p))
    p.rmdir()
    assert call("query", "--all", "gone").stdout == (str(p) + "\n").encode()
    assert call("query", "gone").returncode == 1
    assert call("query", "--all", "--list", "gone").returncode == 0
    assert call("query", "--all", "--list", "gone").stdout == b""


def test_exclusion_globs_prune_database(ctx):
    _, cwd, _, call = ctx
    a, b = cwd / "keep", cwd / "skip-me"
    a.mkdir(); b.mkdir()
    call("add", str(a), str(b))
    assert call("query", "--list", extra={"_ZO_EXCLUDE_DIRS": str(cwd / "skip*")}).stdout == (str(a) + "\n").encode()
    assert call("query", "--all", "--list").stdout == (str(a) + "\n").encode()


def test_maxage_validation_and_zero_ages_out(ctx):
    _, cwd, _, call = ctx
    p = cwd / "aged"; p.mkdir()
    r = call("add", str(p), extra={"_ZO_MAXAGE": "12.5"})
    assert r.returncode == 1 and r.stderr.startswith(b"zoxide: unable to parse _ZO_MAXAGE as integer: 12.5\n")
    r = call("add", str(p), extra={"_ZO_MAXAGE": "0"})
    assert r.returncode == 0
    assert call("query", "--list", "aged").stdout == b""


def test_remove_is_atomic_and_exact(ctx):
    _, cwd, _, call = ctx
    a, b = cwd / "a", cwd / "b"
    a.mkdir(); b.mkdir(); call("add", str(a), str(b))
    r = call("remove", str(a), str(cwd / "absent"))
    assert r.returncode == 1
    assert set(call("query", "--list").stdout.decode().splitlines()) == {str(a), str(b)}
    assert call("remove", str(a)).returncode == 0
    assert call("query", "--list").stdout == (str(b) + "\n").encode()
    assert call("remove").returncode == 0


def test_import_z_preserves_verbatim_path_and_edit_reload_protocol(ctx):
    _, _, data, call = ctx
    f = data.parent / "in.txt"
    f.write_text("relative path|3|0\n")
    assert call("import", "--from", "z", str(f)).returncode == 0
    r = call("edit", "reload")
    assert r.returncode == 0 and r.stdout == b"   0.8\trelative path\0"


def test_import_merges_duplicates_and_requires_merge_for_nonempty(ctx):
    _, _, data, call = ctx
    f = data.parent / "in.txt"; f.write_text("x|2|5\nx|3|8\n")
    assert call("import", "--from", "z", str(f)).returncode == 0
    assert call("import", "--from", "z", str(f)).stderr == b"zoxide: current database is not empty, specify --merge to continue anyway\n"
    assert call("import", "--merge", "--from", "z", str(f)).returncode == 0
    # score display is age-adjusted; duplicated rank remains observable in edit protocol.
    r = call("edit", "reload")
    assert b"\tx\0" in r.stdout


def test_edit_increment_decrement_delete_verbatim(ctx):
    *_, call = ctx
    assert call("edit", "increment", "rel\tative").stdout.endswith(b"rel\tative\0")
    assert call("edit", "decrement", "rel\tative").stdout.endswith(b"rel\tative\0")
    assert call("edit", "delete", "rel\tative").stdout == b""
    assert call("edit", "delete", "rel\tative").returncode == 0


def test_data_dir_validation_and_corrupt_database_fail_cleanly(ctx):
    _, _, data, call = ctx
    r = call("query", "--list", extra={"_ZO_DATA_DIR": "relative"})
    assert r.returncode == 1 and r.stderr == b"zoxide: _ZO_DATA_DIR must be an absolute path\n"
    (data / "db.zo").write_bytes(b"\0\0\0\0")
    r = call("edit", "reload")
    assert r.returncode == 1 and r.stderr.startswith(b"zoxide:")


def test_import_errors_are_runtime_errors(ctx):
    _, _, data, call = ctx
    f = data.parent / "bad.txt"; f.write_text("relative|-|0\n")
    r = call("import", "--from", "z", str(f))
    assert r.returncode == 1 and b"zoxide: import error" in r.stderr and b"invalid rank: -" in r.stderr


def test_init_shell_aliases_and_flags(ctx):
    *_, call = ctx
    for shell in ("bash", "posix", "ksh"):
        r = call("init", shell, "--no-cmd")
        assert r.returncode == 0 and r.stdout.startswith(b"#")
    r = call("init", "bash", "--cmd", "jump", "--no-cmd")
    assert r.returncode == 0 and b"__zoxide_z" in r.stdout
