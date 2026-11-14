import os
import pathlib
import subprocess
import tempfile

import pytest


EXE = "/workspace/executable"


def run(*args, cwd=None, input_text=None, env=None):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run([EXE, *map(str, args)], cwd=cwd, input=input_text,
                          text=True, capture_output=True, env=merged, timeout=12)


def project(tmp_path, module="example.com/acme/app"):
    (tmp_path / "go.mod").write_text("module " + module + "\n")
    return tmp_path


def test_help_and_version_metadata():
    h = run("-help")
    assert h.returncode == 0 and h.stdout == ""
    assert "Usage of /workspace/executable:" in h.stderr
    assert "-imports-order string" in h.stderr and 'default "file"' in h.stderr
    v = run("-version")
    assert v.returncode == 0
    for line in ("version:", "built with:", "tag:", "commit:", "source: github.com/incu6us/goimports-reviser/v3"):
        assert line in v.stdout
    assert "go1." in v.stdout


def test_flat_arguments_parse_errors_and_dash_termination(tmp_path):
    project(tmp_path)
    noarg = run("-recursive", cwd=tmp_path)
    assert noarg.returncode == 1 and "no file(s) or directory(ies) specified" in noarg.stderr
    unknown = run("-wat", cwd=tmp_path)
    assert unknown.returncode == 2 and "flag provided but not defined" in unknown.stderr
    invalid = run("-format=maybe", cwd=tmp_path)
    assert invalid.returncode == 2 and "invalid boolean value" in invalid.stderr
    missing = run("--", "--help", cwd=tmp_path)
    assert missing.returncode == 1 and "--help" in missing.stderr and "Usage of" not in missing.stderr
    word = run("add", cwd=tmp_path)
    assert word.returncode == 1 and "add" in word.stderr


def test_group_sort_aliases_comments_and_parenthesized_shape(tmp_path):
    project(tmp_path)
    f = tmp_path / "main.go"
    f.write_text('package main\nimport (\n "z.example/z" // zed\n "net/http"\n myos "os"\n "fmt"\n "a.example/a" /* alpha */\n)\nfunc main() {}\n')
    r = run("-project-name", "example.com/acme/app", "-separate-named", "-output", "stdout", f)
    assert r.returncode == 0
    out = r.stdout
    assert out.index('"fmt"') < out.index('"net/http"') < out.index('myos "os"')
    assert out.index('"a.example/a"') < out.index('"z.example/z"')
    assert "// zed" in out and "/* alpha */" in out
    assert "import (\n" in out and out.endswith("\n")
    assert f.read_text().startswith("package main\nimport (")


def test_project_company_order_and_repeated_groups(tmp_path):
    project(tmp_path, "testmodule")
    f = tmp_path / "x.go"
    f.write_text('package p\nimport (\n "testmodule/z"\n "corp/x"\n "third.example/a"\n "fmt"\n)\n')
    r = run("-project-name=testmodule", "-company-prefixes", "corp/", "-imports-order", "project,company,std,general", "-output=stdout", f)
    assert r.returncode == 0
    assert r.stdout.index('"testmodule/z"') < r.stdout.index('"corp/x"') < r.stdout.index('"fmt"') < r.stdout.index('"third.example/a"')
    repeated = run("-project-name=testmodule", "-imports-order=std,general,std,company,project", "-output", "stdout", f)
    assert repeated.returncode == 0 and repeated.stdout.count('"fmt"') == 2


@pytest.mark.parametrize("order,fragment", [
    ("std,general", "use default at least 4 parameters"),
    ("std,general,wat", 'unknown order group type: "wat"'),
], ids=["short-order", "unknown-order"])
def test_invalid_import_order(tmp_path, order, fragment):
    project(tmp_path)
    f = tmp_path / "x.go"
    f.write_text("package p\n")
    r = run("-project-name=x", "-imports-order", order, f)
    assert r.returncode == 1 and fragment in r.stderr


def test_rm_unused_handles_usage_and_preserves_block_shape(tmp_path):
    project(tmp_path)
    f = tmp_path / "x.go"
    f.write_text('package p\nimport (\n "fmt"\n "os"\n)\nfunc f() { fmt.Println(os.Args) }\n')
    f.write_text(f.read_text().replace('fmt.Println(os.Args)', 'fmt.Println("ok")'))
    r = run("-project-name=x", "-rm-unused", "-output=stdout", f)
    assert r.returncode == 0 and '"fmt"' in r.stdout and '"os"' not in r.stdout
    assert "import (\n\t\"fmt\"\n)" in r.stdout
    g = tmp_path / "unused.go"
    g.write_text('package p\nimport "os"\n')
    r2 = run("-project-name=x", "-rm-unused", "-output", "stdout", g)
    assert r2.returncode == 0 and "import" not in r2.stdout


def test_special_groups_and_alias_preservation(tmp_path):
    project(tmp_path)
    f = tmp_path / "x.go"
    f.write_text('package p\nimport (\n . "stdlike"\n _ "z.example/side"\n myfmt "fmt"\n)\n')
    r = run("-project-name=none", "-imports-order", "std,general,company,project,blanked,dotted", "-output", "stdout", f)
    assert r.returncode == 0 and 'myfmt "fmt"' in r.stdout and '. "stdlike"' in r.stdout and '_ "z.example/side"' in r.stdout
    assert r.stdout.index('_ "z.example/side"') < r.stdout.index('. "stdlike"')


def test_stdout_file_write_modes_and_exit_status(tmp_path):
    project(tmp_path)
    f = tmp_path / "x.go"
    original = 'package p\nimport ("z.example/z"; "fmt")\n'
    f.write_text(original)
    r = run("-project-name=x", "-output=stdout", "-set-exit-status", f)
    assert r.returncode == 1 and r.stdout.index('"fmt"') < r.stdout.index('"z.example/z"')
    assert f.read_text() == original
    w = run("-project-name=x", "-output=write", f)
    assert w.returncode == 0 and w.stdout == "" and f.read_text().index('"fmt"') < f.read_text().index('"z.example/z"')
    clean = run("-project-name=x", "-set-exit-status", "-output=stdout", f)
    assert clean.returncode == 0


def test_stdin_processing_and_errors(tmp_path):
    project(tmp_path)
    good = run("-project-name=x", "-", input_text='package p\nimport ("z.example/z"; "fmt")\n')
    assert good.returncode == 0 and good.stdout.index('"fmt"') < good.stdout.index('"z.example/z"')
    empty = run("-project-name=x", "-", input_text="")
    assert empty.returncode == 1 and "expected 'package', found 'EOF'" in empty.stderr
    bad = run("-project-name=x", "-", input_text="not go")
    assert bad.returncode == 1 and "<standard-input>" in bad.stderr and "invalid Go source" in bad.stderr
    unsupported = run("-project-name=x", "-rm-unused", "-", input_text="package p\n")
    assert unsupported.returncode == 1 and "-: no Go files in" in unsupported.stderr


def test_module_discovery_uses_target_and_explicit_name_bypasses_it(tmp_path):
    project(tmp_path / "one", "one.example/root/v2")
    targetdir = tmp_path / "one" / "sub"
    targetdir.mkdir()
    f = targetdir / "x.go"
    f.write_text('package p\nimport ("one.example/root/v2/pkg"; "fmt")\n')
    no_module = tmp_path / "outside.go"
    no_module.write_text("package p\n")
    fail = run(no_module)
    assert fail.returncode == 1 and "Could not determine project name for path" in fail.stderr
    okay = run("-project-name=override", "-output=stdout", no_module)
    assert okay.returncode == 0
    discovered = run("-output=stdout", f)
    assert discovered.returncode == 0 and discovered.stdout.index('"fmt"') < discovered.stdout.index('"one.example/root/v2/pkg"')


def test_directory_recursive_list_diff_excludes_and_file_selection(tmp_path):
    project(tmp_path)
    root = tmp_path / "src"
    (root / "nested").mkdir(parents=True)
    (root / "vendor").mkdir()
    changed = root / "nested" / "x.go"
    changed.write_text('package p\nimport ("z.example/z"; "fmt")\n')
    ignored = root / "vendor" / "v.go"
    ignored.write_text('package p\nimport ("z.example/z"; "fmt")\n')
    non_go = root / "readme.txt"
    non_go.write_text("unchanged")
    r = run("-recursive", "-project-name=x", "-excludes=vendor/", "-list-diff", "-output=write", root)
    assert r.returncode == 0 and str(changed) in r.stdout and str(ignored) not in r.stdout
    assert changed.read_text().index('"fmt"') > 0 and '"fmt"' in changed.read_text()
    assert ignored.read_text().startswith('package p\nimport ("z.example/z"')
    direct = run("-project-name=x", "-list-diff", changed)
    assert direct.returncode == 0 and str(changed) in direct.stdout


def test_generated_files_and_apply_flag(tmp_path):
    project(tmp_path)
    f = tmp_path / "gen.go"
    src = '// Code generated by tool. DO NOT EDIT.\npackage p\nimport ("z.example/z"; "fmt")\n'
    f.write_text(src)
    skipped = run("-project-name=x", f)
    assert skipped.returncode == 0 and f.read_text() == src
    listed = run("-project-name=x", "-list-diff", f)
    assert str(f) in listed.stdout
    applied = run("-project-name=x", "-apply-to-generated-files", f)
    assert applied.returncode == 0 and f.read_text() != src


def test_canonical_format_build_tags_and_no_imports(tmp_path):
    project(tmp_path)
    f = tmp_path / "x.go"
    f.write_text('//go:build !windows\n// package docs\npackage p\nfunc f(){\n    _ = 1+1\n}\n')
    r = run("-project-name=x", "-output=stdout", f)
    assert r.returncode == 0 and "//go:build !windows" in r.stdout and "\t_ = 1 + 1" in r.stdout
    assert "import" not in r.stdout


def test_file_path_and_local_deprecated_flags(tmp_path):
    project(tmp_path)
    a = tmp_path / "a.go"
    b = tmp_path / "b.go"
    a.write_text("package p\n")
    b.write_text("package q\n")
    r = run("-project-name=x", "-file-path", b, a)
    assert r.returncode == 1 and "-file-path is deprecated." in r.stderr and "All changes to file are applied" in r.stderr
    loc = run("-project-name=x", "-local", "corp/", "-company-prefixes", "ignored/", "-output=stdout", a)
    assert loc.returncode == 1 and "-local is deprecated" in loc.stderr and "-company-prefixes" in loc.stderr


def test_invalid_output_missing_and_malformed_sources(tmp_path):
    project(tmp_path)
    bad = tmp_path / "bad.go"
    bad.write_text('package p\nimport "unterminated\n')
    r = run("-project-name=x", bad)
    assert r.returncode == 1 and "invalid Go source content" in r.stderr and "bad.go" in r.stderr
    empty = tmp_path / "empty.go"
    empty.write_text("")
    e = run("-project-name=x", empty)
    assert e.returncode == 1 and "file is empty" in e.stderr
    missing = run("-project-name=x", tmp_path / "missing.go")
    assert missing.returncode == 1 and "no such file or directory" in missing.stderr
    invalid = run("-project-name=x", "-output=json", tmp_path / "package.go")
    assert invalid.returncode == 1 and "invalid output" in invalid.stderr

