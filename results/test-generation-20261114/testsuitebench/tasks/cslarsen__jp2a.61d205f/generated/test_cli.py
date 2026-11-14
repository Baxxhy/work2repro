import os
import subprocess

import pytest

from conftest import EXE


def run(*args, env=None, data=None):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run([EXE, *map(str, args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=merged, timeout=15)


VERSION = (b"jp2a 1.0.8\nCopyright 2006-2016 Christian Stigen Larsen\n"
          b"Distributed under the GNU General Public License (GPL) v2.\n")


def test_version_exact_streams():
    p = run("--version")
    assert p.returncode == 0 and p.stdout == b"" and p.stderr == VERSION


def test_version_short_alias():
    p = run("-V")
    assert (p.returncode, p.stdout, p.stderr) == (0, b"", VERSION)


@pytest.mark.parametrize("flag", ["--width", "--height", "--chars", "--html-fontsize",
                                    "--size=abc", "--size=10xabc", "--term-width=10", "--", "-bv", "-o=x"],
                         ids=["width-missing", "height-missing", "chars-missing", "fontsize-missing",
                              "size-nonnumeric", "size-bad-height", "term-width-value", "bare-dashdash",
                              "bundled-short-flags", "short-output-alias"])
def test_unknown_option_is_an_error_with_help(flag):
    p = run(flag)
    assert p.returncode == 1 and p.stdout == b""
    assert p.stderr.startswith(b"Unknown option " + flag.encode() + b"\n\n")
    assert b"Usage: jp2a" in p.stderr


def test_command_like_words_are_inputs():
    p = run("add")
    assert p.returncode == 1 and p.stdout == b"" and p.stderr == b"Can't open add\n"


def test_no_inputs_and_options_only():
    for args in [(), ("--border", "--invert")]:
        p = run(*args)
        assert p.returncode == 1 and p.stdout == b""
        assert p.stderr.startswith(b"No files specified.\n\njp2a 1.0.8\n")


def test_html_fill_warning_exact(jpeg):
    p = run("--html-fill", "--size=4x3", jpeg)
    assert p.returncode == 0
    assert p.stderr == b"warning: --html-fill has changed to --fill\n"


def test_missing_input_preserves_previous_output(jpeg):
    p = run("--size=4x3", jpeg, "missing-path")
    assert p.returncode == 1 and p.stdout.startswith(b"   .")
    assert p.stderr == b"Can't open missing-path\n"


def test_output_file_truncates_and_keeps_all_images(jpeg, tmp_path):
    dest = tmp_path / "out"
    dest.write_bytes(b"stale")
    p = run("--size=4x3", f"--output={dest}", jpeg, jpeg)
    assert p.returncode == 0 and p.stdout == b"" and p.stderr == b""
    assert dest.read_bytes().count(b"\n") == 6


def test_output_dash_means_stdout(jpeg, tmp_path):
    p = run("--size=4x3", "--output=-", jpeg, env={"TMPDIR": str(tmp_path)})
    assert p.returncode == 0 and p.stdout.endswith(b"\n") and not (tmp_path / "-").exists()


def test_output_empty_and_uncreatable_errors(jpeg, tmp_path):
    p = run("--output=", jpeg)
    assert (p.returncode, p.stdout, p.stderr) == (1, b"", b"Empty output filename.\n")
    dest = tmp_path / "absent" / "out"
    p = run(f"--output={dest}", jpeg)
    assert (p.returncode, p.stdout, p.stderr) == (1, b"", f"Could not open '{dest}' for writing.\n".encode())


def test_stdin_input_and_empty_stdin(jpeg):
    payload = open(jpeg, "rb").read()
    p = run("--size=4x3", "-", data=payload)
    q = run("-", data=b"")
    assert p.returncode == 0 and p.stdout.endswith(b"\n")
    assert (q.returncode, q.stdout, q.stderr) == (1, b"", b"Empty input file\n")


def test_non_jpeg_diagnostic(tmp_path):
    f = tmp_path / "not.bin"
    f.write_bytes(b"not an image")
    p = run(f)
    assert (p.returncode, p.stdout, p.stderr) == (1, b"", b"Not a JPEG file: starts with 0x6e 0x6f\n")


def test_truncated_header_diagnostic(tmp_path):
    f = tmp_path / "short.jpg"
    f.write_bytes(b"\xff\xd8\xff\xe0")
    p = run(f)
    assert p.returncode == 1 and p.stdout == b""
    assert p.stderr == b"Premature end of JPEG file\nJPEG datastream contains no image\n"


def test_size_plain_rows_and_palette(jpeg):
    p = run("--size=4x3", "--chars=0123456789ABCDEF", jpeg)
    assert p.returncode == 0
    assert p.stdout == b"257B\n268B\n379B\n"


def test_sampling_static_last_y_across_images(jpeg):
    p = run("--size=4x3", "--chars=0123456789ABCDEF", jpeg, jpeg)
    assert p.returncode == 0
    assert p.stdout == b"257B\n268B\n379B\n268B\n268B\n379B\n"


def test_border_wraps_content(jpeg):
    p = run("--size=4x3", "--chars=aa", "--border", jpeg)
    assert p.returncode == 0
    assert p.stdout == b"+----+\n|aaaa|\n|aaaa|\n|aaaa|\n+----+\n"


def test_clear_prefix_per_image(jpeg):
    p = run("--size=1x1", "--clear", jpeg, jpeg)
    assert p.returncode == 0 and p.stdout.count(b"\x1b[2J\x1b[0;0H") == 2


def test_last_size_and_dimensions(jpeg):
    p = run("--width=2", "--size=4x3", "--width=2", jpeg)
    assert p.returncode == 0
    rows = p.stdout.splitlines()
    assert len(rows) == 2 and all(len(row) == 2 for row in rows)


@pytest.mark.parametrize("args", [("--width=-1",), ("--height=-2",), ("--size=-1x2",), ("--size=1x0",)],
                         ids=["negative-width", "negative-height", "negative-size", "one-zero-size"])
def test_invalid_dimensions(args, jpeg):
    p = run(*args, jpeg)
    assert (p.returncode, p.stdout, p.stderr) == (1, b"", b"Invalid width or height specified\n")


def test_dimension_zero_requests_terminal(jpeg):
    for arg in ("--width=0", "--height=0", "--size=0x0"):
        p = run(arg, jpeg, env={"TERM": ""})
        assert p.returncode == 1 and p.stdout == b""
        assert p.stderr == b"Terminal type '' not recognized.\n"


def test_explicit_dimensions_do_not_need_term(jpeg):
    p = run("--size=1x1", jpeg, env={"TERM": ""})
    assert p.returncode == 0 and len(p.stdout.splitlines()) == 1


def test_term_absent_and_unknown_diagnostics(jpeg):
    absent = os.environ.copy()
    absent.pop("TERM", None)
    p = subprocess.run([EXE, jpeg], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       env=absent, timeout=15)
    assert p.returncode == 1 and p.stdout == b"" and p.stderr == b"Environment variable TERM not set.\n"
    for env, expected in [({"TERM": ""}, b"Terminal type '' not recognized.\n"),
                          ({"TERM": "not-a-terminal"}, b"Terminal type 'not-a-terminal' not recognized.\n")]:
        p = run(jpeg, env=env)
        assert p.returncode == 1 and p.stdout == b"" and p.stderr == expected


def test_palette_minimum_and_repeated_palette(jpeg):
    p = run("--size=2x1", "--chars=a", jpeg)
    assert (p.returncode, p.stdout, p.stderr) == (1, b"", b"You must specify at least two characters in --chars.\n")
    p = run("--size=4x3", "--chars=aa", jpeg)
    assert p.returncode == 0 and p.stdout == b"aaaa\naaaa\naaaa\n"


def test_invert_toggle_and_background_order(jpeg):
    a = run("--size=4x3", "--chars=01", jpeg)
    b = run("--size=4x3", "--chars=01", "--invert", "--invert", jpeg)
    c = run("--size=4x3", "--chars=01", "--invert", jpeg)
    assert a.stdout == b.stdout and c.stdout != a.stdout


def test_flipx_and_flipy(jpeg):
    plain = run("--size=4x3", "--chars=0123456789ABCDEF", jpeg).stdout
    fx = run("--size=4x3", "--chars=0123456789ABCDEF", "--flipx", jpeg).stdout
    fy = run("--size=4x3", "--chars=0123456789ABCDEF", "--flipy", jpeg).stdout
    rows = plain.decode().splitlines()
    assert fx.decode().splitlines() == [s[::-1] for s in rows]
    assert fy.decode().splitlines() == rows[::-1]


def test_ansi_grayscale_and_fill(jpeg):
    p = run("--size=4x3", "--chars=aa", "--colors", jpeg)
    assert p.returncode == 0 and b"\x1b[37ma\x1b[0m" in p.stdout
    fill = run("--size=4x3", "--chars=aa", "--colors", "--fill", jpeg)
    assert b"\x1b[47ma\x1b[0m" in fill.stdout


def test_grayscale_forces_color_capable_output(jpeg):
    p = run("--size=4x3", "--chars=aa", "--grayscale", jpeg)
    assert p.returncode == 0 and b"\x1b[" in p.stdout


def test_html_wrapper_title_font_and_raw(jpeg):
    p = run("--size=1x1", "--html", "--html-title=A<&>", "--html-fontsize=-5", jpeg)
    assert p.returncode == 0
    assert p.stdout.startswith(b"<?xml version='1.0' encoding='ISO-8859-1'?>\n")
    assert b"<title>A<&></title>" in p.stdout and b"font-size:-5pt;" in p.stdout
    raw = run("--size=1x1", "--html-raw", jpeg)
    assert raw.returncode == 0 and b"<html" not in raw.stdout and b"<!DOCTYPE" not in raw.stdout


def test_html_no_bold_and_light_background(jpeg):
    p = run("--size=1x1", "--html", "--html-no-bold", "--background=light", jpeg)
    assert b"background-color: white;" in p.stdout and b"font-weight: normal;" in p.stdout


def test_html_color_escapes_cells(jpeg):
    p = run("--size=2x1", "--html", "--colors", "--chars=<&", jpeg)
    assert p.returncode == 0 and b"<span style='color:#" in p.stdout
    assert b"&lt;" in p.stdout or b"&amp;" in p.stdout
    assert b"<br/>" in p.stdout


def test_rgb_channel_weights_change_rendering(rgb_jpeg):
    opts = ("--size=2x1", "--chars=0123456789")
    red = run(*opts, "--red=1", "--green=0", "--blue=0", rgb_jpeg)
    green = run(*opts, "--red=0", "--green=1", "--blue=0", rgb_jpeg)
    assert red.returncode == green.returncode == 0 and red.stdout != green.stdout


def test_invalid_weight_sum_and_numeric_suffix(rgb_jpeg):
    p = run("--size=2x1", "--red=1junk", rgb_jpeg)
    assert (p.returncode, p.stdout) == (1, b"")
    assert p.stderr == b"Weights 1.000000 + GREEN + BLUE must equal 1.0\n" or p.stderr.startswith(b"Weights ")


def test_file_url_matches_local(jpeg):
    p = run("--size=4x3", jpeg)
    u = run("--size=4x3", "file://" + os.path.abspath(jpeg))
    assert p.returncode == u.returncode == 0 and p.stdout == u.stdout


def test_debug_local_is_silent(jpeg):
    p = run("--size=2x1", "--debug", jpeg)
    assert p.returncode == 0 and p.stderr == b""
