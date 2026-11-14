import json
import os
import pathlib
import subprocess

import pytest


EVAL = pathlib.Path(__file__).resolve().parent
EXE = pathlib.Path(os.environ.get("EXECUTABLE", "/workspace/executable"))


@pytest.fixture
def tree(tmp_path):
    return tmp_path


def write(root, name, content=b""):
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
    return p


def call(*args, cwd=None, stdin=None, env=None):
    e = os.environ.copy()
    e["NO_COLOR"] = "1"
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd, input=stdin,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=e)


def scan(root, *args):
    p = call(*args, "-o", "json", str(root))
    assert p.returncode == 0, p.stderr.decode("utf-8", "replace")
    return json.loads(p.stdout)


def totals(obj):
    t = obj["Total"]
    return t["blanks"], t["code"], t["comments"]


def test_version_and_exact_help():
    v = call("--version")
    assert (v.returncode, v.stdout, v.stderr) == (0, b"tokei 14.0.0 compiled with serialization support: json\n", b"")
    h = call("--help")
    assert h.returncode == 0 and h.stderr == b""
    assert h.stdout.startswith(b"Count your code, quickly.\nSupport this project on GitHub Sponsors:")
    assert b"Usage: executable [OPTIONS] [input]..." in h.stdout and b"  -h, --help" in h.stdout


def test_empty_scan_has_exact_zero_shape(tree):
    got = scan(tree)
    assert got == {"Total": {"blanks": 0, "code": 0, "comments": 0, "reports": [], "children": {}, "inaccurate": False}}


def test_line_endings_empty_and_binary_compatibility(tree):
    write(tree, "x.c", b"line1\nline2\r\nline3\rline4")
    write(tree, "empty.rs", b"")
    write(tree, "bytes.py", b"\x00\x01\x02\xff\x00")
    got = scan(tree)
    assert got["C"]["reports"][0]["stats"]["code"] == 3
    assert got["Rust"]["reports"][0]["stats"] == {"blanks": 0, "code": 0, "comments": 0, "blobs": {}}
    assert got["Python"]["reports"][0]["stats"]["code"] == 1
    assert totals(got) == (0, 4, 0)


def test_lexer_string_comment_blank_and_unicode_rules(tree):
    write(tree, "x.c", 'const char *s = "// no"; /* comment */\n/* only */\nint x; // tail\n\n\n')
    got = scan(tree)
    assert (got["C"]["blanks"], got["C"]["code"], got["C"]["comments"]) == (2, 2, 1)
    write(tree, "u.py", "π = 'λ'\n# café\n　\n")
    got = scan(tree, str(tree / "u.py"))
    assert (got["Python"]["blanks"], got["Python"]["code"], got["Python"]["comments"]) == (0, 2, 1)


def test_language_detection_case_compound_and_shebang(tree):
    for name, text in [("a.PY", "x=1\n"), ("b.tar.gz.rs", "fn main() {}\n"), ("test.spec.ts", "let x: number = 1;\n"), ("script", "#!/usr/bin/env bash\necho ok\n")]:
        write(tree, name, text)
    got = scan(tree)
    assert {k for k in got if k != "Total"} == {"Python", "Rust", "TypeScript", "BASH"}
    write(tree, "nope", "#!/usr/bin/ruby\nputs 1\n")
    assert "Ruby" not in scan(tree, str(tree / "nope"))


def test_unknown_and_special_name_handling(tree):
    write(tree, "Dockerfile", "FROM scratch\n")
    write(tree, "mystery.xyz", "anything\n")
    got = scan(tree)
    assert "Dockerfile" in got and len(got["Dockerfile"]["reports"]) == 1
    assert len(got) == 2
    p = call("-v", str(tree))
    assert p.returncode == 0 and b"WARN" in p.stderr and b"Unknown extension: xyz" in p.stderr


def test_hidden_exclude_types_and_multiple_roots(tree):
    write(tree, "visible.py", "x=1\n")
    write(tree, ".hidden.py", "x=2\n")
    write(tree, "vendor/a.py", "x=3\n")
    write(tree, "a.js", "let x=1;\n")
    assert totals(scan(tree)) == (0, 1, 0)
    assert totals(scan(tree, "--hidden")) == (0, 3, 0)
    assert totals(scan(tree, "--hidden", "-e", "vendor", "-t", "python,javascript")) == (0, 2, 0)
    p = call("-o", "json", str(tree / "visible.py"), str(tree / "visible.py"))
    assert json.loads(p.stdout)["Total"]["code"] == 2


def test_ignore_categories_and_no_ignore_parent(tree):
    root = tree / "repo"
    write(root, ".gitignore", "vcs.py\n")
    write(root, ".ignore", "dot.py\n")
    write(root, ".tokeignore", "tok.py\n")
    for n in ("vcs.py", "dot.py", "tok.py", "keep.py"):
        write(root, n, "x=1\n")
    assert totals(scan(root)) == (0, 1, 0)
    assert totals(scan(root, "--no-ignore-vcs")) == (0, 2, 0)
    assert totals(scan(root, "--no-ignore-dot")) == (0, 2, 0)
    assert totals(scan(root, "--no-ignore")) == (0, 4, 0)
    parent = tree / "parent"
    write(parent, ".ignore", "repo/blocked.py\n")
    write(parent / "repo", "blocked.py", "x=1\n")
    assert totals(scan(parent / "repo")) == (0, 0, 0)
    assert totals(scan(parent / "repo", "--no-ignore-parent")) == (0, 1, 0)


@pytest.mark.parametrize("flag,expected", [("--sort", ["Python", "Rust", "JavaScript"]), ("--rsort", ["JavaScript", "Rust", "Python"])], ids=["descending", "ascending"])
def test_sorting_order(flag, expected, tree):
    write(tree, "a.py", "a\nb\nc\n")
    write(tree, "b.rs", "a\nb\n")
    write(tree, "c.js", "a\n")
    p = call("-o", "json", flag, "files", str(tree))
    assert p.returncode == 0
    assert list(json.loads(p.stdout))[:-1] == expected


def test_cli_types_exact_tokens(tree):
    write(tree, "a.py", "x=1\n")
    write(tree, "b.rs", "fn main() {}\n")
    write(tree, "c.js", "let x=1;\n")
    assert set(scan(tree, "-t", "Python,RUST")) == {"Python", "Rust", "Total"}
    assert set(scan(tree, "-t", "Python, RUST")) == {"Python", "Total"}
    assert set(scan(tree, "-t", " python, RUST ")) == {"Total"}


def test_missing_path_is_runtime_error_without_stdout(tree):
    p = call(str(tree / "missing.py"))
    assert p.returncode == 1 and p.stdout == b""
    assert p.stderr == f"Error: '{tree / 'missing.py'}' not found.\n".encode()


@pytest.mark.parametrize("args", [["--wat"], ["--sort", "invalid"], ["--sort", "lines", "--rsort", "lines"], ["--columns"], ["-c", "-1"], ["--files=1"]], ids=["unknown", "bad-sort", "sort-conflict", "missing-value", "negative-separated", "boolean-attached"])
def test_cli_validation_errors(args):
    p = call(*args)
    assert p.returncode == 2 and p.stdout == b""
    assert p.stderr


def test_output_json_shape_and_streaming_records(tree):
    f = write(tree, "space name.py", "x=1\n# comment\n\n")
    got = scan(tree)
    report = got["Python"]["reports"][0]
    assert report["stats"] == {"blanks": 1, "code": 1, "comments": 1, "blobs": {}}
    assert report["name"].endswith("space name.py")
    assert got["Total"]["children"]["Python"] == [report]
    p = call("--streaming", "json", str(f))
    rows = [json.loads(line) for line in p.stdout.splitlines()]
    assert rows == [{"language": "Python", "stats": {"name": str(f), "stats": {"blanks": 1, "blobs": {}, "code": 1, "comments": 1}}}]


def test_duplicate_and_overlapping_inputs_keep_reports(tree):
    f = write(tree, "a.py", "x=1\n")
    p = call("-o", "json", str(tree), str(f))
    got = json.loads(p.stdout)
    assert got["Total"]["code"] == 2 and len(got["Python"]["reports"]) == 2


def test_symlinks_are_not_followed(tree):
    write(tree, "real.py", "x=1\n")
    (tree / "link.py").symlink_to(tree / "real.py")
    (tree / "loop").symlink_to(tree, target_is_directory=True)
    got = scan(tree)
    assert got["Total"]["code"] == 1 and len(got["Python"]["reports"]) == 1


def test_cli_columns_and_formats_and_files(tree):
    write(tree, "x.py", "x=1\n")
    p = call("--columns", "120", "--files", str(tree))
    assert p.returncode == 0
    assert all(len(line) == 120 for line in p.stdout.decode().splitlines() if set(line) <= {"━", "─"})
    p = call("--num-format", "commas", str(tree))
    assert p.returncode == 0 and b"Total" in p.stdout


def test_invalid_glob_is_diagnostic_but_scan_succeeds(tree):
    write(tree, "x.py", "x=1\n")
    p = call("-o", "json", "-e", "[invalid(pattern", str(tree))
    assert p.returncode == 0 and json.loads(p.stdout)["Total"]["code"] == 1
    assert b"error parsing glob '![invalid(pattern': unclosed character class; missing ']'" in p.stderr


def test_configuration_precedence_and_types(tree):
    write(tree, "a.py", "x=1\n")
    write(tree, "b.rs", "fn main() {}\n")
    write(tree, "tokei.toml", 'types = ["Python"]\n')
    assert set(scan(tree)) == {"Python", "Total"}
    write(tree, ".tokeirc", 'types = ["Rust"]\n')
    assert set(scan(tree)) == {"Python", "Total"}
    write(tree, "tokei.toml", 'types = ["python"]\n')
    assert set(scan(tree)) == {"Python", "Rust", "Total"}


def test_input_option_validates_but_does_not_replace_scan(tree):
    write(tree, "x.py", "x=1\n")
    prior = write(tree, "prior.json", '{"Total":{"code":999}}')
    ordinary = call("-o", "json", str(tree))
    supplied = call("--input", str(prior), "-o", "json", cwd=tree)
    assert json.loads(ordinary.stdout)["Total"]["code"] == json.loads(supplied.stdout)["Total"]["code"]
    bad = write(tree, "bad.json", "not json")
    p = call("--input", str(bad), "-o", "json", cwd=tree)
    assert p.returncode == 1 and b"Failed to parse input file" in p.stderr
