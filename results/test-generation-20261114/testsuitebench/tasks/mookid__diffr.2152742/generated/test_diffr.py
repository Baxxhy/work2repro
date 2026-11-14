import os
import re
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
PROGRAM = Path(os.environ.get("DIFFR_EXECUTABLE", ROOT / "executable"))
ESC = b"\x1b"
RESET = ESC + b"[0m"
RED = RESET + ESC + b"[31m"
GREEN = RESET + ESC + b"[32m"
RRED = RESET + ESC + b"[1m" + ESC + b"[38;2;255;255;255m" + ESC + b"[41m"
RGREEN = RESET + ESC + b"[1m" + ESC + b"[38;2;255;255;255m" + ESC + b"[42m"
SHORT_HELP = (b"diffr 0.1.5\nNathan Moreau <nathan.moreau@m4x.org>\n\n"
              b"diffr adds word-level diff on top of unified diffs.\n"
              b"word-level diff information is displayed using text attributes.\n\n"
              b"USAGE:\n    diffr reads from standard input and writes to standard output.\n\n"
              b"    Typical usage is for interactive use of diff:\n"
              b"    diff -u <file1> <file2> | diffr\n    git show | diffr\n\n"
              b"OPTIONS:\n        --colors <COLOR_SPEC>...    Configure color settings.\n"
              b"        --line-numbers              Display line numbers.\n"
              b"    -h, --help                      Prints help information\n"
              b"    -V, --version                   Prints version information\n")


def run(data=b"", *args):
    return subprocess.run([str(PROGRAM), *args], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=20)


def strip_sgr(data):
    return re.sub(rb"\x1b\[[^\x1b]*?m", b"", data)


def test_empty_pipe_is_empty_and_does_not_wait():
    p = run()
    assert (p.returncode, p.stdout, p.stderr) == (0, b"", b"")


def test_plain_lines_are_single_independently_framed_spans():
    p = run(b"abc\nlast")
    assert p.returncode == 0
    assert p.stdout == RESET + b"abc" + RESET + b"\n" + RESET + b"last" + RESET
    assert p.stderr == b""


def test_outside_metadata_and_file_headers_are_not_changes():
    data = b"diff --git a/a b/a\n--- a/a\n+++ b/a\nBinary files a and b differ\n"
    p = run(data)
    assert p.returncode == 0
    assert strip_sgr(p.stdout) == data
    assert p.stdout == b"".join(RESET + line[:-1] + RESET + b"\n" for line in data.splitlines(keepends=True))


def test_leading_space_before_hunk_header_does_not_start_hunk():
    data = b"  @@ -1 +1 @@\n+ordinary\n"
    p = run(data)
    assert strip_sgr(p.stdout) == data
    assert p.stdout == b"".join(RESET + x[:-1] + RESET + b"\n" for x in data.splitlines(keepends=True))


def test_word_refinement_byte_exact_example():
    data = b"@@ -1 +1 @@\n-server_port = 8080\n+server_port = 3000\n"
    expected = (RESET + b"@@ -1 +1 @@" + RESET + b"\n" +
                RED + b"-" + RESET + RED + b"server_port = " + RESET + RRED + b"8080" + RESET + RED + RESET + b"\n" +
                GREEN + b"+" + RESET + GREEN + b"server_port = " + RESET + RGREEN + b"3000" + RESET + GREEN + RESET + b"\n")
    p = run(data)
    assert p.returncode == 0
    assert p.stdout == expected


def test_lone_addition_is_refined_but_marker_is_base_faced():
    p = run(b"@@ -0,0 +1 @@\n+hello\n")
    assert p.stdout == (RESET + b"@@ -0,0 +1 @@" + RESET + b"\n" +
                        GREEN + b"+" + RESET + RGREEN + b"hello" + RESET + b"\n")


def test_shared_tokens_can_match_across_changed_lines():
    data = b"@@ -1,2 +1,2 @@\n-hello\n-world\n+hello\n+world\n"
    p = run(data)
    assert p.returncode == 0
    assert strip_sgr(p.stdout) == data
    assert p.stdout.count(RRED) == 0
    assert p.stdout.count(RGREEN) == 0


def test_context_warning_and_mixed_line_endings_preserve_bytes():
    data = b"@@ -1,3 +1,3 @@\r\n a\r\n\ No newline at end of file\n-b\r\n+c\n"
    p = run(data)
    assert p.returncode == 0
    assert strip_sgr(p.stdout) == data
    assert b"\\ No newline at end of file" in p.stdout


def test_embedded_sgr_is_removed_only_inside_recognized_hunk():
    data = b"outside\x1b[31mX\n@@ -1 +1 @@\n-a\x1b[31mb\n+c\x1b[32md\n"
    p = run(data)
    assert p.returncode == 0
    assert b"outside\x1b[31mX" in p.stdout
    assert strip_sgr(p.stdout) == b"outside\x1b[31mX\n@@ -1 +1 @@\n-ab\n+cd\n"


@pytest.mark.parametrize("arg", ["help", "version", "show", "config", "file.diff", "--unknown"], ids=["help-word", "version-word", "show", "config", "path", "unknown-flag"])
def test_invalid_positional_and_flag_arguments(arg):
    p = run(b"", arg)
    assert p.returncode == 2
    assert p.stdout == b""
    assert p.stderr.startswith(("bad argument: '" + arg + "'\n").encode())
    assert b"diffr 0.1.5" in p.stderr


@pytest.mark.parametrize("args,opt", [((), "--colors"), ((), "--large-diff-threshold")], ids=["colors", "threshold"])
def test_required_option_values(args, opt):
    p = run(b"", opt)
    assert (p.returncode, p.stdout, p.stderr) == (2, b"", f"option requires an argument: '{opt}'\n".encode())


def test_long_help_takes_precedence_anywhere_even_after_double_dash():
    for args in [("badarg", "--help"), ("--help", "--unknown"), ("--", "--help")]:
        p = run(b"", *args)
        assert p.returncode == 0 and p.stderr == b""
        assert p.stdout.startswith(b"diffr 0.1.5\n")
        assert b"USAGE:\n" in p.stdout and b"ouput" in p.stdout
        assert b"\x1b" not in p.stdout


def test_short_help_ordinary_precedence_and_version_output():
    p = run(b"", "-h")
    assert p.returncode == 0 and p.stderr == b""
    assert p.stdout == SHORT_HELP
    assert run(b"", "bad", "-h").returncode == 2
    for flag in ("-V", "--version"):
        v = run(b"", flag)
        assert (v.returncode, v.stdout, v.stderr) == (0, b"", b"diffr 0.1.5\n")
    assert run(b"", "bad", "--version").returncode == 2


@pytest.mark.parametrize("spec,needle", [
    ("bogus:bold", b"unexpected face name: got 'bogus'"),
    ("added:bogus", b"unexpected attribute name: got 'bogus'"),
    ("added:foreground:orange", b"unrecognized color name 'orange'"),
    ("added:foreground:256", b"ansi256 color number"),
    ("added:background:1,2,999", b"RGB color triple"),
    ("added:foreground", b"missing color value for face 'added'"),
    ("", b"unexpected face name: got ''"),
    (":", b"unexpected face name: got ''"),
    ("added:", b"unexpected attribute name: got ''"),
], ids=["face", "attribute", "named-color", "ansi256-range", "rgb-range", "missing-color", "empty", "colon", "trailing-colon"])
def test_color_specification_errors(spec, needle):
    p = run(b"", "--colors", spec)
    assert p.returncode == 255 and p.stdout == b""
    assert needle in p.stderr and p.stderr.endswith(b"\n")
    assert p.stderr.count(b"\n") == 1


def test_color_spec_assignments_accumulate_and_emit_fixed_order_codes():
    p = run(b"@@ -0,0 +1 @@\n+x\n", "--colors", "added:foreground:blue:bold", "--colors", "added:italic")
    assert p.returncode == 0
    assert RESET + b"[1m" + ESC + b"[3m" + ESC + b"[34m+x" in p.stdout


@pytest.mark.parametrize("style", ["wide", "", "FIXED"], ids=["unknown", "empty", "case-sensitive"])
def test_invalid_line_number_style(style):
    p = run(b"", "--line-numbers", style)
    assert p.returncode == 255
    assert b"unexpected line number style" in p.stderr


@pytest.mark.parametrize("value,fragment", [("-1", b"invalid digit"), ("x", b"invalid digit"), ("18446744073709551616", b"number too large")], ids=["negative", "nondigit", "overflow"])
def test_invalid_threshold_values(value, fragment):
    p = run(b"", "--large-diff-threshold", value)
    assert p.returncode == 255 and fragment in p.stderr


def test_threshold_values_and_hidden_option_do_not_lose_input():
    data = b"@@ -1 +1 @@\n-a b\n+a c\n"
    for value in ("0", "1", "123", "500", "999999"):
        p = run(data, "--large-diff-threshold", value)
        assert p.returncode == 0 and strip_sgr(p.stdout) == data


def test_color_attribute_resets_and_intense_named_color():
    data = b"@@ -0,0 +1 @@\n+x\n"
    p = run(data, "--colors", "added:foreground:blue:bold:italic:nobold:intense")
    assert p.returncode == 0
    assert RESET + ESC + b"[3m" + ESC + b"[38;5;12m+x" in p.stdout
    q = run(data, "--colors", "added:none")
    assert q.returncode == 0
    assert strip_sgr(q.stdout) == data


def test_line_number_compact_and_zero_side_suppression():
    data = b"@@ -0,0 +1,2 @@\n+a\n+b\n"
    p = run(data, "--line-numbers")
    assert p.returncode == 0
    assert strip_sgr(p.stdout).endswith(b"1+a\n2+b\n")
    d = run(b"@@ -1,2 +0,0 @@\n-a\n-b\n", "--line-numbers")
    assert strip_sgr(d.stdout).endswith(b"1-a\n2-b\n")


def test_line_number_styles_aligned_and_fixed():
    data = b"@@ -1,3 +1,3 @@\n hello\n-world\n+universe\n foo\n"
    cases = [("compact", b"  1 hello\n2  -world\n  2+universe\n  3 foo\n"),
             ("aligned", b"  1\thello\n2  \t-world\n  2\t+universe\n  3\tfoo\n"),
             ("fixed", b"      1 hello\n  2    -world\n      2+universe\n      3 foo\n")]
    for style, ending in cases:
        args = ("--line-numbers", style)
        p = run(data, *args)
        assert p.returncode == 0
        assert strip_sgr(p.stdout).endswith(ending)


def test_line_numbers_reset_on_hunks_and_headers_remain_unmargined():
    data = b"@@ -10 +20 @@\n-a\n+b\n@@ -3 +4 @@\n-c\n+d\n"
    p = run(data, "--line-numbers", "compact")
    plain = strip_sgr(p.stdout)
    assert plain.startswith(b"@@ -10 +20 @@\n10 -a\n  20+b\n@@ -3 +4 @@\n3 -c\n 4+d\n")


def test_trailing_changed_whitespace_gets_red_background():
    p = run(b"@@ -1 +1 @@\n-a  \n+b\t\n")
    assert p.returncode == 0
    assert ESC + b"[41m" in p.stdout


def test_unicode_invalid_bytes_nul_and_long_lines_round_trip():
    content = "café e\u0301 👩‍💻 שלום\tpunctuation !@#$%^&*()".encode() + b"\x00\xff\n" + b"x" * 40000
    data = b"ordinary " + content + b"\n"
    p = run(data)
    assert p.returncode == 0
    assert strip_sgr(p.stdout) == data


def test_many_hunks_and_lines_complete_without_losing_bytes():
    data = b"".join(b"@@ -1 +1 @@\n-a\n+b\n" for _ in range(1200))
    p = run(data)
    assert p.returncode == 0
    assert strip_sgr(p.stdout) == data


def test_debug_report_has_four_ordered_lines_and_does_not_change_stdout():
    data = b"plain\n"
    normal, debug = run(data), run(data, "--debug")
    assert debug.returncode == 0 and debug.stdout == normal.stdout
    lines = debug.stderr.decode("ascii").splitlines()
    assert len(lines) == 4
    labels = ["hunk processing time (ms)", "-- compute lcs (ms)", "-- optimize lcs (ms)", "total processing time (ms)"]
    for line, label in zip(lines, labels):
        assert label in line
        assert re.search(r"\d+", line)
        assert len(line) >= 35 + 15
    empty = run(b"", "--debug")
    assert empty.returncode == 0 and empty.stdout == b"" and len(empty.stderr.splitlines()) == 4


def test_malformed_diff_like_input_is_safe_and_preserved():
    data = b"@not a header\n+still outside\n@@ malformed\n+inside\nrandom\n-ordinary\n"
    p = run(data)
    assert p.returncode == 0
    assert strip_sgr(p.stdout) == data
