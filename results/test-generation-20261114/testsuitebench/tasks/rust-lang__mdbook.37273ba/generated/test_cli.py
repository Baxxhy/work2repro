import pathlib
import pytest

from conftest import run_mdbook


def test_version_long():
    p = run_mdbook("--version")
    assert (p.returncode, p.stdout, p.stderr) == (0, "mdbook v0.5.0-alpha.1\n", "")


def test_version_short():
    p = run_mdbook("-V")
    assert (p.returncode, p.stdout, p.stderr) == (0, "mdbook v0.5.0-alpha.1\n", "")


@pytest.mark.parametrize("command,name", [
    ("init", "mdbook-init"), ("build", "mdbook-build"), ("test", "mdbook-test"),
    ("clean", "mdbook-clean"), ("completions", "mdbook-completions"),
    ("watch", "mdbook-watch"), ("serve", "mdbook-serve"),
], ids=["init", "build", "test", "clean", "completions", "watch", "serve"])
def test_scoped_version(command, name):
    p = run_mdbook(command, "--version")
    assert p.returncode == 0
    assert p.stdout == f"{name} v0.5.0-alpha.1\n"


def test_no_args_is_error_with_help():
    p = run_mdbook()
    assert p.returncode == 2 and p.stdout == ""
    assert "Usage: executable [COMMAND]" in p.stderr
    assert "Commands:" in p.stderr


def test_unknown_command():
    p = run_mdbook("unknown-command")
    assert p.returncode == 2 and p.stdout == ""
    assert "error: unrecognized subcommand 'unknown-command'" in p.stderr


def test_unknown_top_level_option():
    p = run_mdbook("--unknown-flag")
    assert p.returncode == 2 and p.stdout == ""
    assert "error: unexpected argument '--unknown-flag' found" in p.stderr
    assert "tip: to pass" not in p.stderr


def test_help_command():
    p = run_mdbook("help")
    assert p.returncode == 0 and p.stderr == ""
    assert p.stdout.startswith("Creates a book from markdown files\n\nUsage: executable [COMMAND]")
    assert p.stdout.endswith("https://github.com/rust-lang/mdBook\n")


def test_help_for_subcommand():
    p = run_mdbook("help", "clean")
    assert p.returncode == 0 and p.stderr == ""
    assert p.stdout.startswith("Deletes a built book\n\nUsage: executable clean [OPTIONS] [dir]\n")
    assert "build.build-dir" in p.stdout


def test_init_help_short_circuits_later_unknown():
    p = run_mdbook("init", "--help", "--bogus-flag")
    assert p.returncode == 0 and p.stderr == ""
    assert p.stdout.startswith("Creates the boilerplate structure and files for a new book\n")
    assert p.stdout.endswith("Print version\n")


def test_unknown_before_help_is_error():
    p = run_mdbook("init", "--unknown", "--help")
    assert p.returncode == 2 and p.stdout == ""
    assert "unexpected argument '--unknown'" in p.stderr
    assert "tip: to pass '--unknown' as a value, use '-- --unknown'" in p.stderr


def test_missing_dest_value_canonical_diagnostic():
    p = run_mdbook("build", "--dest-dir")
    assert p.returncode == 2 and p.stdout == ""
    assert "a value is required for '--dest-dir <dest-dir>'" in p.stderr


def test_clustered_missing_dest_value():
    p = run_mdbook("build", "-od")
    assert p.returncode == 2 and p.stdout == ""
    assert "a value is required for '--dest-dir <dest-dir>'" in p.stderr


def test_completions_invalid_shell_exact():
    p = run_mdbook("completions", "invalid-shell")
    assert p.returncode == 2 and p.stdout == ""
    assert p.stderr == ("error: invalid value 'invalid-shell' for '<SHELL>'\n"
                        "  [possible values: bash, elvish, fish, powershell, zsh]\n\n"
                        "For more information, try '--help'.\n")


def test_completions_missing_shell_exact():
    p = run_mdbook("completions")
    assert p.returncode == 2 and p.stdout == ""
    assert "<SHELL>" in p.stderr and "Usage: executable completions <SHELL>" in p.stderr

