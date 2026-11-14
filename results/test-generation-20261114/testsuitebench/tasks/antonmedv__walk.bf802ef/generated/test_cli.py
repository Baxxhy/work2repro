import pytest

from conftest import run_pipe


HELP = """
  walk v1.13.0

  Usage: walk [path]

    arrows, hjkl  Move cursor
    enter         Enter directory
    backspace     Exit directory
    space         Toggle preview
    esc, q        Exit with cd
    ctrl+c        Exit without cd
    /             Fuzzy search
    d, delete     Delete file or dir
    y             Copy to clipboard
    .             Hide hidden files
    ?             Show help

  Flags:

    --icons        display icons
    --dir-only     show dirs only
    --hide-hidden  hide hidden files
    --preview      display preview
    --with-border  preview with border
    --fuzzy        fuzzy mode
"""


@pytest.mark.parametrize("flag", ["--version", "-v"], ids=["long-version", "short-version"])
def test_version_exact_noninteractive(program, flag):
    r = run_pipe(program, flag)
    assert r.returncode == 0
    assert r.stdout == b"v1.13.0\n"
    assert r.stderr == b""


@pytest.mark.parametrize("flag", ["--help", "-h"], ids=["long-help", "short-help"])
def test_help_exact_noninteractive(program, flag):
    r = run_pipe(program, flag)
    assert r.returncode == 1
    assert r.stdout == b""
    assert r.stderr.decode("utf-8") == HELP


def test_help_precedes_display_flags(program):
    r = run_pipe(program, "--icons", "--preview", "--help")
    assert r.returncode == 1
    assert r.stdout == b""
    assert r.stderr.decode() == HELP


def test_invalid_status_is_checked_before_help_and_version(program):
    for flag in ("--help", "--version"):
        r = run_pipe(program, flag, env={"WALK_STATUS_BAR": "InvalidFunc()"})
        assert r.returncode != 0
        assert b"panic: unknown name InvalidFunc (1:1)" in r.stderr


def test_unknown_status_diagnostic_shape(program):
    r = run_pipe(program, "--version", env={"WALK_STATUS_BAR": "InvalidFunc()"})
    lines = r.stderr.decode("utf-8", "replace").splitlines()
    assert lines[:3] == ["panic: unknown name InvalidFunc (1:1)", " | InvalidFunc()", " | ^"]
    assert any("status_bar.go:" in line for line in lines[3:])


def test_invalid_status_syntax_mentions_location_and_character(program):
    r = run_pipe(program, "--help", env={"WALK_STATUS_BAR": "@"})
    assert r.returncode != 0
    assert b"panic:" in r.stderr and b"status_bar.go:" in r.stderr and b"@" in r.stderr


@pytest.mark.parametrize("env", [
    {"WALK_OPEN_WITH": "broken; .txt:; :echo"},
    {"WALK_MAIN_COLOR": "not-a-real-color"},
], ids=["malformed-open-with", "arbitrary-color"])
def test_non_status_configuration_does_not_break_version(program, env):
    r = run_pipe(program, "--version", env=env)
    assert r.returncode == 0 and r.stdout == b"v1.13.0\n" and r.stderr == b""


@pytest.mark.parametrize("args", [
    (), ("--icons",), ("--preview", "/definitely/not/a/path"),
    ("--unknown",), ("--", "/tmp"),
], ids=["bare", "display-flag", "path-and-flag", "unknown-positional", "separator-is-positional"])
def test_interactive_invocations_require_controlling_tty(program, args):
    r = run_pipe(program, *args)
    assert r.returncode == 2
    assert r.stdout == b""
    assert b"could not open a new TTY" in r.stderr


def test_late_version_is_not_a_version_request(program):
    r = run_pipe(program, "--icons", "/definitely/not/a/path", "ignored", "-v", "--preview")
    assert r.returncode == 2
    assert r.stdout == b""
    assert b"could not open a new TTY" in r.stderr
