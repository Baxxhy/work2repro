import re

import pytest


def test_help_is_substantial_and_complete(invoke):
    r = invoke("--help")
    out = r.stdout.decode("utf-8", "replace")
    assert r.returncode == 0 and len(r.stdout) > 500
    assert all(x in out for x in ("htop", "help", "--help", "--version", "--delay", "--filter", "--sort-key"))
    assert "-d" in out or "--delay" in out


def test_repeated_help_and_help_precedes_bad_argument(invoke):
    for args in (("-h", "--help"), ("--help", "--no-such-option")):
        r = invoke(*args)
        assert r.returncode == 0 and b"htop" in r.stdout and r.stderr == b""


def test_version_format_and_precedence(invoke):
    for flag in ("-V", "--version"):
        r = invoke(flag, "--bad-option")
        out = r.stdout.decode("utf-8", "replace")
        assert r.returncode == 0 and "htop" in out
        assert re.search(r"\d+\.\d+", out) and "--help" not in out and len(r.stdout) < 200


def test_sort_key_help_lists_fields(invoke):
    r = invoke("--sort-key=help")
    out = r.stdout.decode("utf-8", "replace")
    assert r.returncode == 0 and out.count("\n") > 20
    assert all(x in out for x in ("PID", "USER", "PERCENT_CPU", "PERCENT_MEM", "Command", "STATE", "process"))


@pytest.mark.parametrize("args", [("--unknown-option", "-n", "1"), ("--=value", "-n", "1"), ("-z", "-n", "1")], ids=["unknown-long", "malformed-long", "unknown-short"])
def test_unknown_options_fail(invoke, args):
    r = invoke(*args)
    assert r.returncode != 0 and r.stderr
    if args[0] == "--unknown-option":
        assert r.returncode == 1 and r.stdout == b"" and b"unrecognized option" in r.stderr and args[0].encode() in r.stderr


def test_positional_argument_fails(invoke):
    r = invoke("stray", "-n", "1")
    assert r.returncode != 0 and r.stderr
    assert any(x in r.stderr.lower() for x in (b"unsupported", b"argv", b"error"))


@pytest.mark.parametrize("arg", ["-n", "-d", "-s", "-p", "-F"], ids=["count", "delay", "sort", "pid", "filter"])
def test_required_option_value(invoke, arg):
    r = invoke(arg)
    assert r.returncode != 0 and r.stderr


@pytest.mark.parametrize("args", [("-F", ""), ("--filter=",)], ids=["short-empty", "long-empty"])
def test_empty_filter_rejected(invoke, args):
    r = invoke(*args, "-n", "1")
    assert r.returncode != 0 and any(x in r.stderr.lower() for x in (b"invalid", b"filter", b"error"))


@pytest.mark.parametrize("args", [("-n", "abc"), ("-n", "0"), ("-n", "-1"), ("-d", "abc", "-n", "1"), ("-H", "abc", "-n", "1")], ids=["nonnumeric-count", "zero-count", "negative-count", "nonnumeric-delay", "nonnumeric-highlight"])
def test_invalid_numeric_values(invoke, args):
    r = invoke(*args)
    assert r.returncode != 0 and r.stderr
    if args[:2] == ("-n", "0"):
        assert r.returncode == 1 and r.stdout == b""
        assert r.stderr == b"Error: maximum iteration count must be positive.\n"


def test_default_frame_contains_meters_process_data_and_cursor_control(invoke, plain):
    r = invoke("-n", "1")
    visible = plain(r.stdout)
    assert r.returncode == 0 and r.stderr == b"" and len(r.stdout) > 200
    assert b"\x1b[" in r.stdout
    for word in ("CPU", "Mem", "Swp", "Tasks", "Load", "Uptime", "PID", "USER"):
        assert word.lower() in visible.lower()
    assert "COMMAND" in visible.upper() or "COMMAND" in visible.upper()
    assert re.search(r"\bF[0-9]+\b", visible)


def test_refresh_output_grows_and_large_count_completes(invoke):
    one = invoke("-n", "1")
    five = invoke("-n", "5")
    assert len(one.stdout) > 200 and len(five.stdout) > 300
    long = invoke("-n", "100", timeout=5)
    assert long.returncode == 0 and len(long.stdout) > 3000


def test_delay_is_clamped_and_capture_is_accelerated(invoke):
    r = invoke("-n", "5", "-d", "100", timeout=5)
    assert r.returncode == 0 and len(r.stdout) > 300
    assert invoke("-n", "1", "-d", "0").returncode == 0


def test_terminal_and_locale_variants(invoke):
    for term in ("xterm", "xterm-256color", "linux", "dumb"):
        r = invoke("-n", "1", env={"TERM": term})
        assert r.returncode == 0 and r.stdout
    for locale in ("LC_CTYPE", "LC_ALL"):
        for value in (("C",) if locale == "LC_CTYPE" else ("C", "en_US.UTF-8")):
            r = invoke("-n", "1", env={locale: value})
            assert r.returncode == 0 and r.stdout


@pytest.mark.parametrize("term", ["", "unknown"], ids=["empty", "unsupported"])
def test_bad_terminal_has_exact_diagnostic(invoke, term):
    r = invoke("-n", "1", env={"TERM": term})
    assert r.returncode == 1 and r.stdout == b""
    assert r.stderr == b"Error opening terminal: unknown.\n"


def test_color_unicode_and_no_color_environment(invoke):
    normal = invoke("-n", "1")
    mono = invoke("-n", "1", "--no-color")
    no_color_env = invoke("-n", "1", env={"NO_COLOR": "1"})
    empty_env = invoke("-n", "1", env={"NO_COLOR": ""})
    assert b"\x1b[" in normal.stdout and b"\x1b[" in mono.stdout
    assert mono.stdout.count(b"\x1b[") < normal.stdout.count(b"\x1b[")
    assert no_color_env.stdout.count(b"\x1b[") < 500
    assert empty_env.stdout.count(b"\x1b[") >= no_color_env.stdout.count(b"\x1b[")
    assert invoke("-n", "1", "-U").returncode == 0


@pytest.mark.parametrize("args", [("--no-meters",), ("--no-function-bar",), ("-M",), ("--no-mouse",), ("--readonly",), ("--no-meters", "--no-function-bar", "-M", "--readonly")], ids=["no-meters", "no-function-bar", "short-no-mouse", "long-no-mouse", "readonly", "combined"])
def test_display_reduction_options_keep_process_view(invoke, plain, args):
    r = invoke(*args, "-n", "1")
    out = plain(r.stdout)
    assert r.returncode == 0 and len(r.stdout) > 100
    assert "PID" in out and ("Command" in out or "COMMAND" in out)


def test_no_meters_removes_meter_and_function_bar_is_independent(invoke, plain):
    normal = plain(invoke("-n", "1").stdout)
    reduced = plain(invoke("--no-meters", "--no-function-bar", "-n", "1").stdout)
    assert "CPU" in normal and "CPU" not in reduced
    assert not re.search(r"\bF[0-9]+\b", reduced)

