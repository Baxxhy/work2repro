import os
import re
import subprocess
import tempfile
from pathlib import Path

EXE = "/workspace/executable"

HELP = ("  json-tui {OPTIONS} [file]\n\n"
        "    A JSON terminal UI\n\n"
        "  OPTIONS:\n\n"
        "      file                              A JSON file. Omit to read from stdin.\n"
        "      -h, --help                        Display this help menu.\n"
        "      -v, --version                     Print version.\n"
        "      -k, --key, --keybinding           Display key binding.\n"
        "      -f, --fullscreen                  Display the JSON in fullscreen, in an\n"
        "                                        alternate buffer\n"
        "      \"--\" can be used to terminate flag options and force all following\n"
        "      arguments to be treated as positional options\n\n"
        "    If no file is given, json-tui reads JSON from the standard input\n"
        "    Please report bugs to:https://github.com/ArthurSonzogni/json-tui/issues\n")

def run(args=(), data=b""):
    return subprocess.run([EXE, *args], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=5)

def test_help_is_exact_for_both_spellings():
    for flag in ("-h", "--help"):
        p = run([flag])
        assert (p.returncode, p.stdout, p.stderr) == (0, HELP.encode(), b"")

def test_version_exact_and_clusters():
    for args in (("-v",), ("--version",), ("-vk",), ("-kv",)):
        p = run(args)
        assert (p.returncode, p.stdout, p.stderr) == (0, b"1.4.1\n", b"")

def test_help_precedence_and_ignores_file():
    p = run(["missing-file", "--keybinding", "--version", "--help"])
    assert (p.returncode, p.stdout, p.stderr) == (0, HELP.encode(), b"")

def test_invalid_args_precede_info_and_no_usage_noise():
    for args in (("--bogus", "--help"), ("a", "b", "--version"),
                 ("--ver",), ("---help",), ("--key=true",),
                 ("--fullscreen=true",), ("-f=true",), ("-x",)):
        p = run(args)
        assert (p.returncode, p.stdout, p.stderr) == (1, b"", b"Invalid arguments\n")

def test_terminator_and_literal_hyphen_are_paths():
    p = run(["--", "--help"])
    assert p.returncode == 1 and p.stdout == b""
    assert p.stderr == b"Could not open file --help\n"
    p = run(["-"])
    assert p.returncode == 1 and p.stderr == b"Could not open file -\n"

def test_key_table_spellings_are_identical_and_have_control_bytes():
    outputs = [run([x]) for x in ("-k", "--key", "--keybinding")]
    assert all(p.returncode == 0 and p.stderr == b"" for p in outputs)
    assert outputs[0].stdout == outputs[1].stdout == outputs[2].stdout
    out = outputs[0].stdout
    assert out.endswith("┘".encode() + b"\0\n")
    assert b"\r\n" in out and b"\x1b[36m\x1b[49m" in out
    assert "Navigate".encode() in out and "Mouse::WheelDown".encode() in out

def test_info_action_precedence_key_ignores_missing_file():
    p = run(["--keybinding", "missing.json"])
    assert p.returncode == 0 and p.stderr == b""
    assert b"Mouse::WheelUp" in p.stdout

def test_file_open_preserves_path_and_suppresses_stdin_notice(tmp_path):
    name = tmp_path / "space ü'! file.json"
    p = run([str(name)])
    assert (p.returncode, p.stdout, p.stderr) == (1, b"", f"Could not open file {name}\n".encode())

def test_directory_is_parsed_as_empty_file(tmp_path):
    p = run([str(tmp_path)])
    assert p.returncode == 1 and p.stdout == b""
    assert p.stderr.startswith(b"\n[json.exception.parse_error.101] parse error at line 1, column 1:")
    assert b"empty input" in p.stderr and p.stderr.endswith(b"\n")

def test_stdin_notice_is_flushed_even_for_empty_input():
    p = run([], b"")
    assert p.returncode == 1
    assert p.stdout == b"Reading from stdin..."
    assert p.stderr.startswith(b"\n[json.exception.parse_error.101] parse error at line 1, column 1:")

def test_malformed_input_diagnostic_examples():
    cases = [(b"not json", b"line 1, column 2: syntax error while parsing value - invalid literal; last read: 'no'"),
             (b"[}", b"line 1, column 2: syntax error while parsing value - unexpected '}'; expected '[', '{', or a literal"),
             (b"{}{}", b"line 1, column 3: syntax error while parsing value - unexpected '{'; expected end of input"),
             (b"{'key': 1}", b"syntax error while parsing object key - invalid literal; last read: '{''; expected string literal"),
             (b"[1,]", b"syntax error while parsing value - unexpected ']'; expected '[', '{', or a literal"),
             (b"{\"x\": 1,}", b"syntax error while parsing object key - unexpected '}'; expected string literal")]
    for data, fragment in cases:
        p = run([], data)
        assert p.returncode == 1 and p.stdout == b"Reading from stdin..."
        assert p.stderr.startswith(b"\n[json.exception.parse_error.101] parse error at ")
        assert fragment in p.stderr and p.stderr.endswith(b"\n")

def test_invalid_utf8_is_reported():
    p = run([], b'"\xff"')
    assert p.returncode == 1 and b"ill-formed UTF-8 byte" in p.stderr

def test_accepts_scalar_and_strict_number_forms_without_parse_error():
    for data in (b"null", b"true", b"false", b"-0", b"9223372036854775807",
                 b"-9223372036854775808", b"9999999999999999999", b"1e308", b"1e-308",
                 b'"multilingual \xe4\xbd\xa0\xf0\x9f\x98\x80"'):
        p = run([], data)
        assert p.returncode == 0, (data, p.stderr)
        assert p.stdout.startswith(b"Reading from stdin...")

