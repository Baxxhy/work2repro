import os
import pathlib
import subprocess
import tempfile

import pytest


EVAL = pathlib.Path(__file__).resolve().parent
EXE = pathlib.Path(os.environ.get("EXECUTABLE", EVAL.parent / "executable"))


def run(*args, data=b"", cwd=None):
    return subprocess.run(
        [str(EXE), *args], input=data, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, cwd=cwd, timeout=30,
    )


def test_empty_redirected_stdin_is_silent():
    p = run(data=b"")
    assert (p.returncode, p.stdout, p.stderr) == (0, b"", b"")


@pytest.mark.parametrize("data,expected", [
    (b"a", "⠁\n"), (b"a\n", "⠁\n"), (b"\n", "⠀\n"),
    (b"", ""), (b"a\r\n", "⠁\n"),
], ids=["no-final-lf", "final-lf", "empty-line", "empty-stream", "crlf"])
def test_line_splitting_and_basic_rendering(data, expected):
    p = run(data=data)
    assert p.returncode == 0 and p.stderr == b""
    assert p.stdout.decode() == expected


@pytest.mark.parametrize("data,expected", [
    (b"  abc  ", "⠀⠉⠁\n"),
    (b"a b", "⠉⠁\n"),
    (b"\tX", "⠈\n"),
    ("é".encode(), "⠁\n"),
    (b"\xef\xbb\xbf", "⠁\n"),
    (b"\x00", "⠁\n"),
    ("e\u0301".encode(), "⠉\n"),
], ids=["indent-trailing", "internal-space", "tab-byte", "multibyte", "bom", "nul", "combining"])
def test_unicode_byte_offsets_and_whitespace(data, expected):
    p = run(data=data)
    assert (p.returncode, p.stdout.decode(), p.stderr) == (0, expected, b"")


def test_lossy_decode_replaces_invalid_utf8():
    p = run(data=b"\xff")
    assert p.returncode == 0 and p.stderr == b"" and p.stdout.decode() == "⠁\n"


def test_strict_decode_rejects_invalid_utf8():
    p = run("--encoding", "utf8", data=b"\xff")
    assert p.returncode == 1 and p.stdout == b""
    assert p.stderr == b"code-minimap: stream did not contain valid UTF-8\n"


def test_file_and_stdin_use_same_pipeline(tmp_path):
    f = tmp_path / "source.txt"
    f.write_bytes(b"  abc\n")
    file_p = run(str(f))
    stdin_p = run(data=f.read_bytes())
    assert file_p.returncode == stdin_p.returncode == 0
    assert file_p.stderr == stdin_p.stderr == b""
    assert file_p.stdout == stdin_p.stdout


def test_literal_dash_is_filename(tmp_path):
    p = run("-", cwd=tmp_path)
    assert p.returncode == 1 and p.stdout == b""
    assert p.stderr.startswith(b"code-minimap: ") and b"No such file or directory" in p.stderr


@pytest.mark.parametrize("args,expected", [
    (("-H", "2"), "⠉\n"), (("--horizontal-scale=2",), "⠉\n"),
    (("-H=2.5",), "⠉⠁\n"), (("--horizontal-scale", "0.5"), "\n"),
    (("-V", "0"), "⠁\n"), (("--vertical-scale=-1",), "⠁\n"),
], ids=["short-separated", "long-equals", "short-equals", "fractional", "vertical-zero", "negative-vertical"])
def test_scale_options(args, expected):
    p = run(*args, data=b"a")
    assert (p.returncode, p.stdout.decode(), p.stderr) == (0, expected, b"")


def test_vertical_coalescing_and_frame_packing():
    p = run(data=b"aaaa\nbbbb\ncccc\ndddd")
    assert p.returncode == 0 and p.stdout.decode() == "⣿⣿\n"


def test_vertical_factor_greater_than_one_does_not_add_rows():
    p = run("-V", "2", data=b"a\nb\nc\nd\ne")
    assert p.returncode == 0 and p.stdout.decode() == "⣿\n⠁\n"


def test_whitespace_sentinel_and_empty_horizontal_rows():
    p = run(data=b"   \n")
    assert p.stdout.decode() == "⠀\n"
    q = run("-H", "0", data=b"a")
    assert (q.returncode, q.stdout, q.stderr) == (0, b"\n", b"")


@pytest.mark.parametrize("args,data,expected", [
    (("--padding", "2"), b"a", "⠁ \n"),
    (("--padding=0",), b"a", "⠁\n"),
    (("--padding", "3"), b"a\n", "⠁  \n"),
    (("--padding", "2", "-H", "0"), b"a", "  \n"),
], ids=["pad-short", "pad-zero", "pad-final-lf", "pad-zero-width"])
def test_padding(args, data, expected):
    p = run(*args, data=data)
    assert (p.returncode, p.stdout.decode(), p.stderr) == (0, expected, b"")


def test_options_can_follow_file(tmp_path):
    f = tmp_path / "x"
    f.write_bytes(b"a")
    p = run(str(f), "-H", "2")
    assert p.returncode == 0 and p.stdout.decode() == "⠉\n"


def test_double_dash_makes_option_spelling_a_filename(tmp_path):
    p = run("--", "--horizontal-scale", cwd=tmp_path)
    assert p.returncode == 1 and b"No such file or directory" in p.stderr


def test_missing_path_error_is_stable(tmp_path):
    p = run(str(tmp_path / "missing"))
    assert (p.returncode, p.stdout, p.stderr) == (
        1, b"", b"code-minimap: No such file or directory (os error 2)\n")


def test_directory_input_error(tmp_path):
    p = run(str(tmp_path))
    assert p.returncode == 1 and p.stdout == b""
    assert p.stderr == b"code-minimap: Is a directory (os error 21)\n"


def test_version_exact():
    p = run("--version")
    assert (p.returncode, p.stdout, p.stderr) == (0, b"code-minimap 0.6.8\n", b"")


def test_help_exact_and_short_help():
    expected = ("A high performance code minimap generator\n\n"
        "Usage: executable [OPTIONS] [FILE] [COMMAND]\n\n"
        "Commands:\n  completion\n          Generate shell completion file\n  help\n"
        "          Print this message or the help of the given subcommand(s)\n\n"
        "Arguments:\n  [FILE]\n          File to read\n\nOptions:\n"
        "  -H, --horizontal-scale <HSCALE>\n          Specify horizontal scale factor [default: 1.0]\n"
        "  -V, --vertical-scale <VSCALE>\n          Specify vertical scale factor [default: 1.0]\n"
        "      --padding <PADDING>\n          Specify padding width\n"
        "      --encoding <ENCODING>\n          Specify input encoding [default: utf8-lossy] [possible values: utf8-lossy, utf8]\n"
        "      --version\n          Print version\n  -h, --help\n          Print help\n")
    for args in [("--help",), ("-h",), ("--help", "--padding", "2"), ("bogus", "--help")]:
        p = run(*args)
        assert (p.returncode, p.stdout.decode(), p.stderr) == (0, expected, b"")


def test_help_command_and_completion_help():
    main = run("help")
    assert main.returncode == 0 and b"Commands:\n  completion\n" in main.stdout
    for args in [("help", "completion"), ("completion", "--help")]:
        p = run(*args)
        assert p.returncode == 0 and p.stderr == b""
        assert b"Generate shell completion file\n\nUsage: executable completion <SHELL>" in p.stdout
        assert b"[possible values: bash, elvish, fish, powershell, zsh]" in p.stdout


@pytest.mark.parametrize("args,frag", [
    (("--horizontal-scale=abc",), b"invalid value 'abc' for '--horizontal-scale <HSCALE>': invalid float literal"),
    (("--padding=abc",), b"invalid value 'abc' for '--padding <PADDING>'"),
    (("--encoding", "invalid"), b"invalid value 'invalid' for '--encoding <ENCODING>'"),
    (("--unknown-flag",), b"unexpected argument '--unknown-flag' found"),
    (("--padding", "-1"), b"unexpected argument '-1' found"),
    (("--padding=-1",), b"invalid value '-1' for '--padding <PADDING>'"),
    (("-HV", "2"), b"invalid value 'V' for '--horizontal-scale <HSCALE>'"),
    (("-HV2",), b"invalid value 'V2' for '--horizontal-scale <HSCALE>'"),
    (("-VH2",), b"invalid value 'H2' for '--vertical-scale <VSCALE>'"),
    (("",), b"a value is required for '[FILE]' but none was supplied"),
    (("-", "-"), b"unexpected argument '-' found"),
], ids=["bad-float", "bad-padding", "bad-encoding", "unknown", "negative-separated", "negative-equals", "short-joined-hv", "short-joined-hv2", "short-joined-vh2", "empty-positional", "two-dashes"])
def test_cli_parse_errors(args, frag):
    p = run(*args)
    assert p.returncode == 2 and p.stdout == b"" and frag in p.stderr
    assert p.stderr.endswith(b"\n")


def test_completion_missing_invalid_uppercase_and_extra_shell():
    cases = [(("completion",), b"following required arguments were not provided"),
             (("completion", "invalid-shell"), b"invalid value 'invalid-shell'"),
             (("completion", "BASH"), b"invalid value 'BASH'"),
             (("completion", "bash", "zsh"), b"unexpected argument 'zsh' found"),
             (("completion", "bash", "--version"), b"unexpected argument '--version' found")]
    for args, fragment in cases:
        p = run(*args)
        assert p.returncode == 2 and p.stdout == b"" and fragment in p.stderr


def test_bash_completion_script_has_expected_structure():
    p = run("completion", "bash")
    assert p.returncode == 0 and p.stderr == b"" and p.stdout.endswith(b"\n")
    assert p.stdout.startswith(b"_code-minimap() {\n")
    for token in [b"complete -F _code-minimap", b"--horizontal-scale", b"utf8-lossy utf8", b"code__minimap__completion"]:
        assert token in p.stdout


@pytest.mark.parametrize("shell,prefix,markers", [
    ("elvish", b"\nuse builtin;\n", [b"edit:completion:arg-completer[code-minimap]", b"utf8-lossy"]),
    ("fish", b"# Print an optspec", [b"function __fish_code_minimap_global_optspecs", b"complete -c code-minimap"]),
    ("powershell", b"\nusing namespace System.Management.Automation", [b"Register-ArgumentCompleter", b"CompletionResult"]),
    ("zsh", b"#compdef code-minimap\n", [b"autoload -U is-at-least", b"_code-minimap_commands"]),
], ids=["elvish", "fish", "powershell", "zsh"])
def test_other_completion_scripts(shell, prefix, markers):
    p = run("completion", shell)
    assert p.returncode == 0 and p.stderr == b"" and p.stdout.startswith(prefix)
    assert p.stdout.endswith(b"\n")
    for marker in markers:
        assert marker in p.stdout


def test_scales_keep_fractional_behavior():
    p = run("-H", "1.5", data=b"a")
    assert p.returncode == 0 and p.stdout.decode() == "⠁\n"
    q = run("-H", "0.001", data=b"abc")
    assert q.returncode == 0 and q.stdout.decode() == "\n"


def test_large_line_and_many_lines(tmp_path):
    f = tmp_path / "large"
    f.write_bytes(b"x" * 100000)
    p = run(str(f))
    assert p.returncode == 0 and p.stderr == b""
    assert len(p.stdout.decode().rstrip("\n")) == 50000
    f.write_bytes(b"x\n" * 9999 + b"x")
    p = run(str(f))
    assert p.returncode == 0 and p.stderr == b""
    assert len(p.stdout.splitlines()) == 2500


def test_large_indentation_and_scale(tmp_path):
    f = tmp_path / "indent"
    f.write_bytes(b" " * 250 + b"x")
    p = run(str(f))
    assert p.returncode == 0 and len(p.stdout.decode().rstrip("\n")) == 126
    q = run("-H", "100", str(f))
    assert q.returncode == 0 and len(q.stdout.decode().rstrip("\n")) == 12550
