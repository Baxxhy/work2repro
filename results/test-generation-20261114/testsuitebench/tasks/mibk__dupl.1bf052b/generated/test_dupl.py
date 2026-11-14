import os
import subprocess
from pathlib import Path

import pytest


EVAL = Path(__file__).resolve().parent
EXE = Path(os.environ.get("DUPL_EXECUTABLE", "/workspace/executable"))
EMPTY_TEXT = "\nFound total 0 clone groups.\n"


def run(args=(), *, cwd=None, stdin=None, executable=EXE):
    return subprocess.run(
        [str(executable), *map(str, args)], cwd=cwd, input=stdin,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
    )


def go_file(path, body="func f() { println(1) }\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("package p\n" + body, encoding="utf-8")
    return path


def test_help_variants_have_status_two_and_exact_usage():
    expected = """Usage: dupl [flags] [paths]

Paths:
  If the given path is a file, dupl will use it regardless of
  the file extension. If it is a directory, it will recursively
  search for *.go files in that directory.

  If no path is given, dupl will recursively search for *.go
  files in the current directory.

Flags:
  -files
    \tread file names from stdin one at each line
  -html
    \toutput the results as HTML, including duplicate code fragments
  -plumbing
    \tplumbing (easy-to-parse) output for consumption by scripts or tools
  -t, -threshold size
    \tminimum token sequence size as a clone (default 15)
  -vendor
    \tcheck files in vendor directory
  -v, -verbose
    \texplain what is being done

Examples:
  dupl -t 100
    \tSearch clones in the current directory of size at least
    \t100 tokens.
  dupl $(find app/ -name '*_test.go')
    \tSearch for clones in tests in the app directory.
  find app/ -name '*_test.go' |dupl -files
    \tThe same as above.
"""
    for flag in ("-h", "--help", "-help"):
        p = run([flag])
        assert p.returncode == 2
        assert p.stdout == b""
        assert p.stderr.decode() == expected


@pytest.mark.parametrize("flag", ["-Verbose", "-unknown", "--bogus"], ids=["case-sensitive", "single-dash", "double-dash"])
def test_unknown_flags_print_error_then_usage(flag):
    p = run([flag])
    err = p.stderr.decode()
    assert p.returncode == 2
    assert p.stdout == b""
    assert err.startswith(f"flag provided but not defined: -{flag.lstrip('-')}\nUsage: dupl")


@pytest.mark.parametrize("args,prefix", [
    (["-t"], "flag needs an argument: -t"),
    (["-threshold"], "flag needs an argument: -threshold"),
    (["-t", "abc"], 'invalid value "abc" for flag -t: parse error'),
], ids=["missing-t", "missing-threshold", "invalid-integer"])
def test_integer_flag_errors(args, prefix):
    p = run(args)
    assert p.returncode == 2
    assert p.stdout == b""
    assert p.stderr.decode().startswith(prefix + "\nUsage:")


def test_flag_parsing_stops_at_first_positional(tmp_path):
    d = tmp_path / "folder"
    d.mkdir()
    p = run([d, "-t", "15"])
    assert p.returncode == 1
    assert "lstat -t: no such file or directory" in p.stderr.decode()
    assert b"Found total" not in p.stdout


def test_standalone_double_dash_ends_flag_parsing(tmp_path):
    f = go_file(tmp_path / "-source.go")
    p = run(["--", f])
    assert p.returncode == 0
    assert p.stderr == b""
    assert p.stdout.decode().endswith("Found total 0 clone groups.\n")


def test_integer_aliases_and_equals_forms_accept_signed_values(tmp_path):
    f = go_file(tmp_path / "one.go")
    for args in (["-t", "-1"], ["--threshold=0"], ["-t=999999", "-threshold", "999999"]):
        p = run([*args, f])
        assert p.returncode == 0
        assert p.stderr == b""
        assert p.stdout.decode().endswith("Found total 0 clone groups.\n")


def test_conflicting_formats_fail_before_input_processing(tmp_path):
    p = run(["-html", "-plumbing", tmp_path / "missing"])
    assert p.returncode == 1
    assert p.stdout == b""
    assert "you can have either plumbing or HTML output" in p.stderr.decode()
    assert "lstat" not in p.stderr.decode()


def test_nonexistent_positional_path_is_fatal_and_timestamped(tmp_path):
    p = run([tmp_path / "missing.go"])
    err = p.stderr.decode()
    assert p.returncode == 1
    assert "lstat " + str(tmp_path / "missing.go") + ": no such file or directory" in err
    assert err[:4].isdigit() and err[4:5] == "/"
    assert b"Found total" not in p.stdout


def test_empty_directory_and_empty_formats(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    p = run([d])
    assert p.returncode == 0 and p.stdout == EMPTY_TEXT.encode() and p.stderr == b""
    p = run(["-plumbing", d])
    assert p.returncode == 0 and p.stdout == b""
    p = run(["-html", d])
    assert p.returncode == 0
    assert p.stdout.decode().startswith('<!DOCTYPE html>\n<meta charset="utf-8"/>\n<title>Duplicates</title>\n<style>')
    assert "Found total" not in p.stdout.decode()


def test_explicit_non_go_file_is_parsed_and_errors_are_nonfatal(tmp_path):
    bad = tmp_path / "note.txt"
    bad.write_text("This is not Go\n")
    p = run([bad])
    assert p.returncode == 0
    assert "note.txt:1:1: expected 'package', found This" in p.stderr.decode()
    assert p.stdout == EMPTY_TEXT.encode()


def test_empty_source_gets_parse_error(tmp_path):
    f = tmp_path / "empty.go"
    f.write_bytes(b"")
    p = run([f])
    assert p.returncode == 0
    assert "expected 'package', found 'EOF'" in p.stderr.decode()


def test_crawling_uses_only_go_files_but_explicit_file_ignores_extension(tmp_path):
    d = tmp_path / "tree"
    go_file(d / "valid.go")
    (d / "bad.txt").write_text("This is not Go")
    p = run([d])
    assert p.returncode == 0 and p.stderr == b""
    q = run([d / "bad.txt"])
    assert q.returncode == 0 and b"expected 'package'" in q.stderr


def test_vendor_is_skipped_unless_flagged_and_explicit_path_is_included(tmp_path):
    d = tmp_path / "project"
    go_file(d / "vendor" / "dep.go")
    plain = run([d])
    assert plain.returncode == 0 and plain.stderr == b""
    with_vendor = run(["-vendor", d])
    assert with_vendor.returncode == 0
    direct = run([d / "vendor" / "dep.go"])
    assert direct.returncode == 0 and direct.stderr == b""


def test_files_mode_ignores_positional_paths_and_removes_one_dot_slash(tmp_path):
    a = go_file(tmp_path / "a.go")
    p = run(["-files", tmp_path / "missing"], cwd=tmp_path, stdin="./a.go\n")
    assert p.returncode == 0 and p.stderr == b""
    assert p.stdout == EMPTY_TEXT.encode()


def test_files_mode_continues_after_missing_and_directory_lines(tmp_path):
    good = go_file(tmp_path / "valid.go")
    (tmp_path / "directory").mkdir()
    p = run(["-files"], cwd=tmp_path, stdin="missing.go\ndirectory\nvalid.go\n")
    err = p.stderr.decode()
    assert p.returncode == 0
    assert "missing.go" in err and "directory" in err
    assert p.stdout == EMPTY_TEXT.encode()


def test_files_mode_empty_input_is_empty_success(tmp_path):
    p = run(["-files"], cwd=tmp_path, stdin="")
    assert p.returncode == 0 and p.stderr == b""
    assert p.stdout == EMPTY_TEXT.encode()


def test_symlink_file_preserves_link_path(tmp_path):
    target = go_file(tmp_path / "real.go")
    link = tmp_path / "alias.go"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")
    p = run([link])
    assert p.returncode == 0
    assert p.stderr == b""


def test_symlink_directory_is_not_walked_and_is_nonfatal(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "dirlink"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    p = run([link])
    assert p.returncode == 0
    assert "is a directory" in p.stderr.decode()


def test_verbose_emits_exactly_two_timestamped_lines_even_for_empty_input(tmp_path):
    p = run(["-v", "--verbose", tmp_path])
    lines = p.stderr.decode().splitlines()
    assert p.returncode == 0
    assert len(lines) == 2
    assert lines[0].endswith("Building suffix tree")
    assert lines[1].endswith("Searching for clones")
    for line in lines:
        assert len(line) >= 20 and line[:4].isdigit() and line[4:5] == "/"
    assert p.stdout == EMPTY_TEXT.encode()


def test_verbose_fatal_path_logs_building_but_not_searching(tmp_path):
    p = run(["-verbose", tmp_path / "missing"])
    lines = p.stderr.decode().splitlines()
    assert p.returncode == 1
    assert any(x.endswith("Building suffix tree") for x in lines)
    assert not any(x.endswith("Searching for clones") for x in lines)


def test_structural_clones_ignore_names_literals_comments_and_operators(tmp_path):
    a = tmp_path / "a.go"
    b = tmp_path / "b.go"
    a.write_text("package a\nfunc alpha(x int) int { // comment\n if x > 3 { return x + 1 }; return 0\n}\n")
    b.write_text("package z\nfunc beta(y int) int {\n if y < 99 { return y - 8 }; return 2\n}\n")
    p = run([a, b])
    assert p.returncode == 0 and p.stderr == b""
    out = p.stdout.decode()
    assert "found 2 clones:" in out
    assert str(a) in out and str(b) in out
    assert out.endswith("Found total 1 clone groups.\n")


def test_threshold_boundary_excludes_too_large_threshold(tmp_path):
    a = tmp_path / "a.go"
    b = tmp_path / "b.go"
    src = "package p\nfunc f() { var x int; x = 1; if x == 1 { x++ } }\n"
    a.write_text(src)
    b.write_text(src.replace("package p", "package q"))
    low = run(["-t", "1", a, b])
    high = run(["-threshold=999999", a, b])
    assert low.returncode == 0 and "Found total 0 clone groups." not in low.stdout.decode()
    assert high.returncode == 0 and high.stdout == EMPTY_TEXT.encode()


def test_plumbing_has_only_cyclic_duplicate_lines(tmp_path):
    paths = [tmp_path / (n + ".go") for n in ("a", "b", "c")]
    for p in paths:
        p.write_text("package p\nfunc f() { var x int; x = 1; if x == 1 { x++ } }\n")
    result = run(["-plumbing", *paths])
    assert result.returncode == 0 and result.stderr == b""
    lines = result.stdout.decode().splitlines()
    assert len(lines) == 3
    assert all("duplicate of " in line for line in lines)
    assert "Found total" not in result.stdout.decode()


def test_html_escapes_source_fragment_and_uses_start_heading(tmp_path):
    a, b = tmp_path / "a.go", tmp_path / "b.go"
    src = "package p\nfunc f() { println(\"<&>\") }\n"
    a.write_text(src)
    b.write_text(src)
    p = run(["-html", a, b])
    assert p.returncode == 0
    out = p.stdout.decode()
    assert "<h1>#1 found 2 clones</h1>" in out
    assert "<pre>" in out and "&lt;" in out and "&amp;" in out and "&gt;" in out
    assert "Found total" not in out and "</html>" not in out


def test_comments_affect_reported_lines_but_not_clone_structure(tmp_path):
    a, b = tmp_path / "a.go", tmp_path / "b.go"
    a.write_text("package p\n// extra line\nfunc f() { println(1) }\n")
    b.write_text("package p\nfunc f() { println(9) }\n")
    p = run(["-plumbing", a, b])
    assert p.returncode == 0
    out = p.stdout.decode()
    assert str(a) + ":3-3" in out
    assert str(b) + ":2-2" in out
