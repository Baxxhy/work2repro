"""Behavioral tests for the Pastel-compatible executable."""
import os
import re
import subprocess
from pathlib import Path

import pytest


EVAL = Path(__file__).resolve().parent
EXE = Path(os.environ.get("EXECUTABLE", "/workspace/executable"))


def run(*args, input=None, env=None):
    e = os.environ.copy()
    e["NO_COLOR"] = "1"
    e.pop("PASTEL_COLOR_MODE", None)
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *map(str, args)], input=input, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=e, timeout=10)


def assert_ok(p, out=None):
    assert p.returncode == 0, p.stderr
    if out is not None:
        assert p.stdout == out


def assert_cli_error(p, fragment):
    assert p.returncode == 2
    assert p.stdout == ""
    assert fragment in p.stderr
    assert p.stderr.rstrip().endswith("For more information, try '--help'.")


def test_version_and_main_help():
    assert_ok(run("--version"), "pastel 0.11.0\n")
    p = run("--help")
    assert_ok(p)
    for s in ("A command-line tool to generate, analyze, convert and manipulate colors",
              "Usage: executable [OPTIONS] <COMMAND>", "Commands:", "Options:",
              "--color-picker", "--force-color", "--color-mode", "--help", "--version"):
        assert s in p.stdout
    for cmd in ("color", "colorblind", "colorcheck", "complement", "darken", "desaturate",
                "distinct", "format", "gradient", "gray", "lighten", "list", "mix", "paint",
                "pick", "random", "rotate", "saturate", "set", "sort-by", "textcolor", "to-gray", "help"):
        assert re.search(r"^  " + re.escape(cmd) + r"\s{2,}.+$", p.stdout, re.M)


def test_help_forms_and_global_option_position():
    assert run().returncode == 2
    p = run("color", "--help")
    assert_ok(p)
    assert "Usage: executable color" in p.stdout
    assert run("color", "-h").stdout != p.stdout
    p = run("format", "-h")
    assert_ok(p)
    assert "Convert a color to the given format" in p.stdout
    assert "[possible values:" in p.stdout
    assert_cli_error(run("color", "--color-mode", "off"), "unexpected argument")
    assert_cli_error(run("--mode=off", "color"), "unexpected argument")


def test_unknown_command_diagnostic_is_exact():
    p = run("bogus")
    assert p.returncode == 2
    assert p.stdout == ""
    assert p.stderr == ("error: unrecognized subcommand 'bogus'\n\n"
                        "Usage: executable [OPTIONS] <COMMAND>\n\n"
                        "For more information, try '--help'.\n")


@pytest.mark.parametrize("value,expected", [
    ("red", "hsl(0,100.0%,50.0%)\n"),
    ("blue", "hsl(240,100.0%,50.0%)\n"),
    ("green", "hsl(120,100.0%,25.1%)\n"),
    ("#FF5733", "hsl(11,100.0%,60.0%)\n"),
    ("F57", "hsl(348,100.0%,66.7%)\n"),
    ("#FF5733AA", "hsla(11,100.0%,60.0%,0.667)\n"),
    ("rgb(50%,60%,70%)", "hsl(211,25.1%,60.2%)\n"),
    ("hsv(210,22.2%,60.0%)", "hsl(210,14.3%,53.3%)\n"),
    ("gray(0.5)", "hsl(0,0.0%,50.2%)\n"),
], ids=["name-red", "name-blue", "css-green", "hex-long", "hex-short", "hex-alpha",
        "rgb-percent", "hsv-convert", "gray-expression"])
def test_color_parser_normative_cases(value, expected):
    assert_ok(run("color", value), expected)


@pytest.mark.parametrize("value", ["#gg0000", "#00", "#00000", "12345", "1234567",
                                      "123456789", "rgb(10,0)", "rgb(a,b,c)", "RGB(1,2,3)",
                                      "hsl(360,100,50)", "lab(10;20;30)", "light   blue", "blu"],
                         ids=["bad-hex-char", "bad-hex-2", "bad-hex-5", "bad-hex-5digits",
                              "bad-hex-7digits", "bad-hex-9digits", "rgb-arity", "rgb-nonnumeric",
                              "uppercase-function", "hsl-missing-percent", "lab-separator",
                              "partial-name-spacing", "unknown-name"])
def test_invalid_colors_are_runtime_errors(value):
    p = run("color", value)
    assert p.returncode == 1
    assert p.stdout == ""
    assert p.stderr == f"[pastel error]: Could not parse color '{value}'\n"


def test_color_input_batch_stdin_placeholders_and_fail_fast():
    assert_ok(run("color", input="red\nblue"), "hsl(0,100.0%,50.0%)\nhsl(240,100.0%,50.0%)\n")
    assert_ok(run("color", "-", "green", "-", input="red\nblue\n"),
              "hsl(0,100.0%,50.0%)\nhsl(120,100.0%,25.1%)\nhsl(240,100.0%,50.0%)\n")
    assert_ok(run("color", input=""), "")
    p = run("color", "red", "bad", "blue")
    assert p.returncode == 1 and p.stdout == "hsl(0,100.0%,50.0%)\n"
    assert "Could not parse color 'bad'" in p.stderr
    p = run("color", input="red\n \nblue\n")
    assert p.returncode == 1 and p.stdout == "hsl(0,100.0%,50.0%)\n"
    assert "Could not parse color ''" in p.stderr


@pytest.mark.parametrize("kind,value,expected", [
    ("hex", "red", "#ff0000\n"), ("rgb", "red", "rgb(255, 0, 0)\n"),
    ("rgb-float", "red", "rgb(1.000, 0.000, 0.000)\n"),
    ("hsl", "red", "hsl(0, 100.0%, 50.0%)\n"),
    ("hsv", "red", "hsv(0, 100.0%, 100.0%)\n"),
    ("cmyk", "red", "cmyk(0, 100, 100, 0)\n"), ("lab", "red", "Lab(53, 80, 67)\n"),
    ("lch", "red", "LCh(53, 105, 40)\n"), ("oklab", "red", "OkLab(0.6279, 0.2249, 0.1258)\n"),
    ("oklch", "red", "OkLCh(0.6279, 0.2577, 29.2232)\n"),
    ("luminance", "red", "0.213\n"), ("brightness", "red", "0.299\n"),
    ("name", "#ff5733", "tomato\n"), ("ansi-8bit-value", "red", "196\n"),
], ids=["hex", "rgb", "rgb-float", "hsl", "hsv", "cmyk", "lab", "lch", "oklab",
        "oklch", "luminance", "brightness", "nearest-name", "ansi-index"])
def test_format_normative_records(kind, value, expected):
    assert_ok(run("format", kind, value), expected)


def test_format_alpha_and_raw_ansi():
    assert_ok(run("format", "hex", "#FF5733AA"), "#ff5733aa\n")
    assert_ok(run("format", "rgb", "#FF5733AA"), "rgba(255, 87, 51, 0.667)\n")
    assert_ok(run("format", "ansi-24bit-escapecode", "red"), "\x1b[38;2;255;0;0m")
    assert_ok(run("format", "ansi-8bit-escapecode", "red", "blue"),
              "\x1b[38;5;196m\x1b[38;5;21m")


def test_format_types_and_modes():
    p = run("format", "bogus", "red")
    assert_cli_error(p, "invalid value 'bogus' for '[type]'")
    assert_ok(run("--color-mode", "off", "format", "hex", "red"), "#ff0000\n")
    assert_ok(run("--force-color", "format", "hex", "red"),
              "\x1b[38;2;0;0;0;48;2;255;0;0m#ff0000\x1b[0m\n")
    assert_ok(run("--color-mode", "8bit", "format", "hex", "red"),
              "\x1b[38;5;16;48;5;196m#ff0000\x1b[0m\n")


@pytest.mark.parametrize("cmd,expected", [
    (("complement", "red"), "hsl(180,100.0%,50.0%)\n"),
    (("rotate", "90", "red"), "hsl(90,100.0%,50.0%)\n"),
    (("rotate", "--", "-90", "red"), "hsl(270,100.0%,50.0%)\n"),
    (("lighten", ".2", "red"), "hsl(0,100.0%,70.0%)\n"),
    (("darken", ".2", "red"), "hsl(0,100.0%,30.0%)\n"),
    (("lighten", "--", "-0.1", "red"), "hsl(0,100.0%,40.0%)\n"),
    (("darken", "--", "-0.1", "red"), "hsl(0,100.0%,60.0%)\n"),
    (("saturate", ".2", "hsl(180,50%,50%)"), "hsl(180,70.0%,50.0%)\n"),
    (("desaturate", ".2", "hsl(180,50%,50%)"), "hsl(180,30.0%,50.0%)\n"),
], ids=["complement", "rotate-positive", "rotate-negative", "lighten", "darken",
        "negative-lighten", "negative-darken", "saturate", "desaturate"])
def test_hsl_transforms(cmd, expected):
    assert_ok(run(*cmd), expected)


def test_to_gray_textcolor_and_gray_command():
    assert_ok(run("to-gray", "red", "blue", "green"),
              "hsl(0,0.0%,49.8%)\nhsl(240,0.0%,29.8%)\nhsl(120,0.0%,42.7%)\n")
    assert_ok(run("textcolor", "red", "navy", "white"),
              "hsl(0,0.0%,0.0%)\nhsl(0,0.0%,100.0%)\nhsl(0,0.0%,0.0%)\n")
    assert_ok(run("gray", ".5"), "hsl(0,0.0%,50.0%)\n")
    assert_ok(run("gray", "5"), "hsl(0,0.0%,100.0%)\n")
    p = run("gray", "0", ".25", ".5", ".75", "1", "5")
    assert_cli_error(p, "unexpected argument '.25' found")
    assert "Usage: executable gray <lightness>" in p.stderr


def test_set_coordinates():
    cases = [("hsl-hue", "180", "red", "hsl(180,100.0%,50.0%)\n"),
             ("hsl-saturation", ".5", "red", "hsl(0,50.0%,50.0%)\n"),
             ("hsl-lightness", ".7", "red", "hsl(0,100.0%,70.0%)\n"),
             ("red", "128", "blue", "hsl(270,100.0%,50.0%)\n"),
             ("alpha", ".5", "red", "hsla(0,100.0%,50.0%,0.5)\n"),
             ("hue", "180", "red", "hsl(167,100.0%,31.6%)\n")]
    for prop, val, color, expected in cases:
        assert_ok(run("set", prop, val, color), expected)
    assert_cli_error(run("set", "saturation", ".5", "red"), "invalid value 'saturation'")


def test_mix_spaces_fraction_and_stdin_partners():
    expected = {"Lab": "hsl(320,100.0%,39.6%)\n", "RGB": "hsl(300,100.0%,25.1%)\n",
                "HSL": "hsl(300,100.0%,50.0%)\n", "LCh": "hsl(329,100.0%,49.2%)\n",
                "OkLab": "hsl(283,32.2%,48.0%)\n"}
    for space, out in expected.items():
        assert_ok(run("mix", "red", "blue", "--colorspace", space), out)
    assert_ok(run("mix", "--fraction", "0", "--colorspace", "RGB", "red", "blue"),
              "hsl(240,100.0%,50.0%)\n")
    assert_ok(run("mix", "red", input="blue\ngreen\n"),
              "hsl(320,100.0%,39.6%)\nhsl(40,100.0%,31.6%)\n")
    assert_ok(run("mix", "red", input=""), "")
    assert_cli_error(run("mix"), "required arguments were not provided")


def test_gradient_samples_and_runtime_limits():
    assert_ok(run("gradient", "--number", "3", "red", "green", "blue"),
              "hsl(0,100.0%,50.0%)\nhsl(120,100.0%,25.1%)\nhsl(240,100.0%,50.0%)\n")
    assert_ok(run("gradient", "--number", "5", "red", "blue"),
              "hsl(0,100.0%,50.0%)\nhsl(339,100.0%,45.5%)\nhsl(320,100.0%,39.6%)\nhsl(287,100.0%,38.2%)\nhsl(240,100.0%,50.0%)\n")
    for count in ("0", "1"):
        p = run("gradient", "--number", count, "red", "blue")
        assert p.returncode == 1 and "specified color count must be larger than one" in p.stderr
    p = run("gradient", "red")
    assert p.returncode == 1 and "number of color arguments must be larger than one" in p.stderr


def test_sort_by_orders_reverse_unique_and_stdin():
    colors = ("red", "blue", "green", "yellow")
    hue = "hsl(0,100.0%,50.0%)\nhsl(60,100.0%,50.0%)\nhsl(120,100.0%,25.1%)\nhsl(240,100.0%,50.0%)\n"
    assert_ok(run("sort-by", "hue", *colors), hue)
    assert_ok(run("sort-by", "hue", "--reverse", *colors), "".join(reversed(hue.splitlines(keepends=True))))
    assert_ok(run("sort-by", "--unique", "hue", "red", "#ff0000", "blue"),
              "hsl(0,100.0%,50.0%)\nhsl(240,100.0%,50.0%)\n")
    assert_ok(run("sort-by", input="red\nblue\nyellow\n"),
              "hsl(0,100.0%,50.0%)\nhsl(60,100.0%,50.0%)\nhsl(240,100.0%,50.0%)\n")
    assert_cli_error(run("sort-by", "invalid", "red"), "invalid value 'invalid'")


def test_list_deterministic_orders_and_help_error():
    p = run("list")
    assert_ok(p)
    names = p.stdout.splitlines()
    assert len(names) == 139 and names[0] == "black" and names[-1] == "deeppink"
    assert "red" in names and "lightslategray" in names
    p = run("list", "--sort", "brightness")
    assert_ok(p)
    assert p.stdout.splitlines()[:20] == "black navy darkblue mediumblue blue midnightblue indigo maroon darkred purple darkmagenta darkgreen darkviolet darkslategray darkslateblue green red firebrick rebeccapurple brown".split()
    p = run("list", "--sort", "invalid")
    assert p.returncode == 2 and p.stdout == ""
    assert p.stderr == ("error: invalid value 'invalid' for '--sort <sort-order>'\n"
                        "  [possible values: brightness, luminance, hue, chroma, random]\n\n"
                        "For more information, try '--help'.\n")
    p = run("list", "--help")
    assert_ok(p)
    assert "Usage: executable list [OPTIONS]" in p.stdout and "Sort order" in p.stdout


def test_random_count_strategies_entropy_and_option_errors():
    assert_ok(run("random", "-n", "0"), "")
    for strategy in ("gray", "rgb", "vivid", "lch_hue"):
        p = run("random", "--number", "30", "--strategy", strategy)
        assert_ok(p)
        lines = p.stdout.splitlines()
        assert len(lines) == 30
        assert all(x.startswith("hsl(") and x.endswith(")") for x in lines)
        if strategy == "gray":
            assert all(",0.0%," in x for x in lines)
    p = run("random", "--number", "100")
    assert_ok(p)
    assert len(p.stdout.splitlines()) == 100
    p = run("random", "-n")
    assert p.returncode == 2 and p.stderr == ("error: a value is required for '--number <count>' but none was supplied\n\n"
                                               "For more information, try '--help'.\n")
    p = run("random", "--number", "-1")
    assert_cli_error(p, "unexpected argument '-1' found")
    assert_cli_error(run("random", "--strategy", "wat"), "invalid value 'wat'")


def test_distinct_fixed_colors_count_errors_and_verbose():
    assert_ok(run("distinct", "2", "red", "blue"), "hsl(0,100.0%,50.0%)\nhsl(240,100.0%,50.0%)\n")
    for count in ("0", "1"):
        p = run("distinct", count)
        assert p.returncode == 1 and "number of colors must be larger than one" in p.stderr
    p = run("distinct", "2", "red", "blue", "green")
    assert p.returncode == 1 and "fixed colors must be smaller" in p.stderr
    assert_cli_error(run("distinct", "2", "--metric", "cie76"), "invalid value 'cie76'")
    p = run("distinct", "3", "--verbose")
    assert_ok(p)
    assert len(p.stdout.splitlines()) == 3
    progress = p.stderr.splitlines()
    assert len(progress) >= 10
    assert all(len(re.findall(r"\b[0-9a-f]{6}\b", line)) >= 3 and line.endswith(" ") for line in progress)


def test_colorblind_exact_examples_and_invalid_type():
    for kind, color, output in [("prot", "red", "hsl(53,100.0%,24.7%)\n"),
                                ("deuter", "green", "hsl(52,70.1%,26.3%)\n"),
                                ("trit", "blue", "hsl(178,100.0%,19.6%)\n")]:
        assert_ok(run("colorblind", kind, color), output)
    assert_ok(run("colorblind", "prot", input=""), "")
    assert_cli_error(run("colorblind", "invalid_type", "red"), "invalid value 'invalid_type' for '<type>'")
    p = run("colorblind", "--help", env={"COLUMNS": "100"})
    assert_ok(p)
    assert "protanopia, deuteranopia, or" in p.stdout and "Usage: executable colorblind <type>" in p.stdout


def test_paint_modes_styles_background_and_stdin():
    assert_ok(run("--color-mode", "off", "paint", "red", "Hello", "World"), "Hello World\n")
    assert_ok(run("--color-mode", "24bit", "paint", "red", "Hello", "World"),
              "\x1b[38;2;255;0;0mHello World\x1b[0m\n")
    assert_ok(run("--color-mode", "8bit", "paint", "--on", "blue", "red", "X"),
              "\x1b[38;5;196;48;5;21mX\x1b[0m\n")
    assert_ok(run("--color-mode", "24bit", "paint", "--bold", "--italic", "--underline", "red", "X"),
              "\x1b[38;2;255;0;0;1;3;4mX\x1b[0m\n")
    assert_ok(run("paint", "default", "-n", "plain"), "plain")
    assert_ok(run("paint", "red", input="Text from stdin\n", env={"NO_COLOR": "1"}), "Text from stdin\n\n")
    assert_cli_error(run("paint", "-o"), "a value is required for '--on <bg-color>'")
    p = run("paint", "--help", env={"COLUMNS": "100"})
    assert_ok(p)
    assert "Print colored text using ANSI escape sequences" in p.stdout
    assert "Usage: executable paint [OPTIONS] <color> [text]..." in p.stdout


def test_color_mode_env_and_picker():
    assert_ok(run("color", "red", env={"PASTEL_COLOR_MODE": "bogus"}), "hsl(0,100.0%,50.0%)\n")
    assert_ok(run("paint", "red", "X", env={"PASTEL_COLOR_MODE": "8bit", "NO_COLOR": "1"}), "X\n")
    p = run("pick")
    assert p.returncode == 1 and "Could not find any external color picker tool" in p.stderr
    p = run("color", "pick")
    assert p.returncode == 1 and "Could not find any external color picker tool" in p.stderr


def test_colorcheck_fixed_ansi_stream_and_help_pick():
    p = run("colorcheck")
    assert_ok(p)
    assert len(p.stdout.encode("utf-8")) == 6244
    assert p.stdout.startswith("\n8-bit mode:\n" + " " * 30 + "\n")
    assert "\x1b[38;5;52;48;5;52m \x1b[0m" in p.stdout
    assert "\x1b[38;2;73;39;50;48;2;73;39;50m \x1b[0m" in p.stdout
    p = run("pick", "--help")
    assert_ok(p)
    assert "pick" in p.stdout.lower() and "count" in p.stdout.lower()
