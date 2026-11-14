from conftest import invoke


def test_version_long(exe):
    r = invoke(exe, "--version")
    assert r.returncode == 0 and r.stderr == b""
    assert r.stdout == b"html2markdown\n\nGitVersion:  dev\nGitCommit:   none\nBuildDate:   unknown\n"


def test_version_short(exe):
    r = invoke(exe, "-v")
    assert r.returncode == 0 and r.stdout.startswith(b"html2markdown\n") and r.stderr == b""


def test_help_byte_contract(exe):
    r = invoke(exe, "--help")
    assert r.returncode == 0 and r.stderr == b""
    assert r.stdout.startswith(b"\n# html2markdown - convert html to markdown [version dev]\n")
    assert r.stdout.endswith(b"\n\n")
    assert b"malicious content. \n" in r.stdout
    assert b"Commands:" not in r.stdout and b"Subcommands:" not in r.stdout


def test_help_precedes_invalid_option(exe):
    r = invoke(exe, "--help", "--bogus")
    assert r.returncode == 0 and r.stderr == b"" and r.stdout.startswith(b"\n# html2markdown")


def test_words_are_not_subcommands(exe):
    for word in ("convert", "help", "version", "--", "unexpected arguments"):
        r = invoke(exe, word)
        assert r.returncode == 1 and r.stdout == b"" and b"unknown arguments" in r.stderr


def test_unknown_flag(exe):
    r = invoke(exe, "--not-real")
    assert r.returncode == 1 and r.stdout == b""
    assert b"unknown flag" in r.stderr and b"--not-real" in r.stderr


def test_requires_piped_input(exe):
    r = invoke(exe, "--input", "")
    assert r.returncode == 1 and r.stdout == b"" and b"empty string" in r.stderr


def test_empty_pipe_and_whitespace_pipe(exe):
    empty = invoke(exe, html="")
    white = invoke(exe, html=" \n\t ")
    assert empty.returncode == 0 and empty.stdout == b"\n" and empty.stderr == b""
    assert white.returncode == 0 and not white.stdout.strip()


def test_strong_delimiter_validation_and_last_value(exe):
    for val in ("*", "***", "_*", "  ", "＊＊"):
        r = invoke(exe, "--opt-strong-delimiter", val, html="<strong>x</strong>")
        assert r.returncode == 1 and val.encode() in r.stderr and b"exactly 2 characters" in r.stderr
    r = invoke(exe, "--opt-strong-delimiter=__", "--opt-strong-delimiter=**", html="<b>x</b>")
    assert r.returncode == 0 and r.stdout == b"**x**\n"


def test_duplicate_input_output_and_missing_value(exe, tmp_path):
    for args in (("--input", "a", "--input", "b"), ("--output", "a", "--output", "b")):
        r = invoke(exe, *args)
        assert r.returncode == 1 and b"another value has already been set" in r.stderr
    r = invoke(exe, "--domain")
    assert r.returncode == 1 and b"flag needs an argument" in r.stderr


def test_table_options_require_plugin(exe):
    for arg in ("--opt-table-header-promotion", "--opt-table-skip-empty-rows", "--opt-table-presentation-tables",
                "--opt-table-cell-padding-behavior=minimal", "--opt-table-newline-behavior=preserve",
                "--opt-table-span-cell-behavior=mirror"):
        r = invoke(exe, arg, html="<table></table>")
        assert r.returncode == 1 and b"requires --plugin-table to be enabled" in r.stderr


def test_table_invalid_enums(exe):
    cases = (("--opt-table-span-cell-behavior=bad", b"span cell behavior"),
             ("--opt-table-newline-behavior=bad", b"newline behavior"),
             ("--opt-table-cell-padding-behavior=bad", b"cell padding behavior"))
    for arg, message in cases:
        r = invoke(exe, "--plugin-table", arg, html="<table></table>")
        assert r.returncode == 1 and message in r.stderr and b'unknown value "bad"' in r.stderr
