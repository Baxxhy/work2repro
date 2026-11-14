import pathlib
import re

import pytest

from conftest import make_book, run_mdbook


def test_rustdoc_chapter_tests_pass_and_log_chapter(tmp_path):
    root = make_book(tmp_path / "book", chapters={"chapter_1.md": "# Chapter\n\n```rust\nassert_eq!(2 + 2, 4);\n```\n"})
    p = run_mdbook("test", root)
    assert p.returncode == 0, p.stderr
    assert "Testing chapter 'Chapter': chapter_1.md" in p.stderr


def test_rustdoc_failures_report_end_summary(tmp_path):
    root = make_book(tmp_path / "book", chapters={"chapter_1.md": "# Bad\n\n```rust\nassert_eq!(1, 2);\n```\n"})
    p = run_mdbook("test", root)
    assert p.returncode == 101
    assert "FAILED" in p.stderr and "One or more tests failed" in p.stderr


def test_compile_fail_that_compiles_is_failure(tmp_path):
    root = make_book(tmp_path / "book", chapters={"chapter_1.md": "# Bad\n\n```rust,compile_fail\nlet x = 1;\n```\n"})
    p = run_mdbook("test", root)
    assert p.returncode == 101
    assert "Test compiled successfully, but it's marked `compile_fail`" in p.stderr


def test_chapter_filter_selects_title_or_source(tmp_path):
    summary = "- [First](one.md)\n- [Second](nested/two.md)\n"
    root = make_book(tmp_path / "book", summary, {"one.md": "# First\n", "nested/two.md": "# Second\n"})
    p = run_mdbook("test", "--chapter", "nested/two.md", root)
    assert p.returncode == 0, p.stderr
    assert "Testing chapter 'Second': nested/two.md" in p.stderr
    assert "Testing chapter 'First': one.md" not in p.stderr


def test_chapter_filter_missing_fails(tmp_path):
    root = make_book(tmp_path / "book")
    p = run_mdbook("test", "--chapter", "absent", root)
    assert p.returncode == 101 and "Chapter not found: absent" in p.stderr


@pytest.mark.parametrize("shell,required", [
    ("bash", ["_mdbook() {", "complete -F _mdbook"]),
    ("zsh", ["#compdef mdbook", "autoload -U is-at-least", "case $state in"]),
    ("fish", ["__fish_mdbook_global_optspecs", "complete -c mdbook"]),
    ("powershell", ["using namespace System.Management.Automation", "Register-ArgumentCompleter -Native -CommandName 'mdbook'"]),
    ("elvish", ["use builtin;", "use str;", "edit:completion:arg-completer[mdbook]"]),
], ids=["bash", "zsh", "fish", "powershell", "elvish"])
def test_completion_scripts_have_shell_structure(shell, required):
    p = run_mdbook("completions", shell)
    assert p.returncode == 0 and p.stderr == ""
    for text in required:
        assert text in p.stdout
    assert all(cmd in p.stdout for cmd in ["init", "build", "test", "clean", "serve"])
    if shell == "bash":
        # Bash completion output is executable syntax, not just descriptive text.
        import subprocess
        check = subprocess.run(["bash", "-n"], input=p.stdout, text=True, capture_output=True)
        assert check.returncode == 0, check.stderr

