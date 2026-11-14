import re

from conftest import EXECUTABLE


def test_help_banner_and_alias(invoke):
    expected = ("\n _ __ _____   _(_)__  _____\n| '__/ _ \\ \\ / / \\ \\ / / _ \\\n"
                "| | |  __/\\ V /| |\\ V /  __/\n|_|  \\___| \\_/ |_| \\_/ \\___/\n\n"
                "Example:\n  revive -config c.toml -formatter friendly -exclude a.go -exclude b.go ./...\n\n")
    for flag in ("-help", "--help"):
        result = invoke(flag)
        assert result.returncode == 0
        assert result.stdout.decode() == expected
        assert result.stderr.startswith(f"Usage of {EXECUTABLE}:".encode())


def test_version_output_is_standalone(invoke):
    result = invoke("-version", "-config", "/missing/config.toml")
    assert result.returncode == 0
    assert result.stderr == b""
    out = result.stdout.decode()
    assert re.fullmatch(r"Version:\t\S+\nCommit:\t\t\S+\nBuilt\t\t.+\n", out)


def test_missing_flag_value_has_usage_and_banner(invoke):
    result = invoke("-config")
    assert result.returncode == 2
    assert b"flag needs an argument" in result.stderr
    assert result.stdout.startswith(b"\n _ __ _____")


def test_unknown_flag_has_usage_and_banner(invoke):
    result = invoke("-unknown-test-flag")
    assert result.returncode == 2
    assert b"flag provided but not defined: -unknown-test-flag" in result.stderr
    assert result.stdout.startswith(b"\n _ __ _____")


def test_unknown_formatter_is_fatal(invoke, tmp_path):
    result = invoke("-formatter", "not-a-formatter", cwd=tmp_path)
    assert result.returncode == 1
    assert b"unknown formatter not-a-formatter" in result.stderr
    assert result.stdout == b""
