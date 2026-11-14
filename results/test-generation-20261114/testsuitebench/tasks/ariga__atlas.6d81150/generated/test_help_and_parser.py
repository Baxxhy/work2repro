import pytest

from conftest import EXECUTABLE


ROOT_HELP = """Manage your database schema as code

Usage:
  atlas [command]

Available Commands:
  completion  Generate the autocompletion script for the specified shell
  help        Help about any command
  license     Display license information
  migrate     Manage versioned migration files
  schema      Work with Atlas schemas.
  version     Prints this Atlas CLI version information.

Flags:
  -h, --help   help for atlas

Use \"atlas [command] --help\" for more information about a command.
"""


@pytest.mark.parametrize("args", [(), ("-h",), ("--help",), ("help",)], ids=["empty", "short", "long", "help"])
def test_root_help_exact(invoke, args):
    r = invoke(*args)
    assert r.returncode == 0
    assert r.stdout.decode() == ROOT_HELP
    assert r.stderr == b""


@pytest.mark.parametrize("args, required", [
    (("schema", "--help"), ["atlas schema [command]", "Apply an atlas schema", "--var <name>=<value>"]),
    (("help", "migrate"), ["atlas migrate [command]", "migrate apply", "migrate validate"]),
    (("migrate", "help"), ["atlas migrate [command]", "migrate apply", "migrate validate"]),
    (("help", "migrate", "apply"), ["Usage:\n  atlas migrate apply [flags] [amount]", "--baseline", "Global Flags:"]),
    (("schema", "apply", "--help"), ["Examples:", "-s, --schema strings", "print SQL without executing it"]),
])
def test_group_and_nested_help_routes(invoke, args, required):
    r = invoke(*args)
    assert r.returncode == 0 and r.stderr == b""
    out = r.stdout.decode()
    for part in required:
        assert part in out


@pytest.mark.parametrize("args, expected", [
    (("version",), "atlas unofficial version - development\nhttps://github.com/ariga/atlas/releases/latest\nTo download an official version, visit: https://atlasgo.io/getting-started#installation\n"),
    (("license",), "LICENSE\nAtlas is licensed under Apache 2.0 as found in https://github.com/ariga/atlas/blob/master/LICENSE.\n"),
])
def test_version_and_license_are_exact(invoke, args, expected):
    r = invoke(*args)
    assert r.returncode == 0 and r.stdout.decode() == expected and r.stderr == b""


@pytest.mark.parametrize("args, expected", [
    (("--version",), "Error: unknown flag: --version\n"),
    (("-v",), "Error: unknown shorthand flag: 'v' in -v\n"),
    (("--invalid1", "--invalid2"), "Error: unknown flag: --invalid1\n"),
    (("schema", "apply", "-u"), "Error: flag needs an argument: 'u' in -u\n"),
])
def test_parser_diagnostics(invoke, args, expected):
    r = invoke(*args)
    assert r.returncode == 1 and r.stdout == b"" and r.stderr.decode() == expected


@pytest.mark.parametrize("args, expected", [
    (("schema", "inspect"), 'Error: required flag(s) "url" not set\n'),
    (("schema", "apply", "--url="), 'Error: required flag(s) "url" not set\n'),
    (("migrate", "diff"), 'Error: required flag(s) "to", "dev-url" not set\n'),
    (("schema", "apply", "--tx-mode", "nope"), 'Error: required flag(s) "url" not set\n'),
])
def test_required_inputs_and_validation_order(invoke, args, expected):
    r = invoke(*args)
    assert r.returncode == 1 and r.stdout == b""
    assert r.stderr.decode().startswith(expected)


def test_tx_mode_validated_before_desired_schema(invoke):
    r = invoke("schema", "apply", "--tx-mode", "nope", "--url", "sqlite://file?mode=memory", "--to", "file:///tmp/missing.hcl")
    assert r.returncode == 1 and r.stdout == b""
    assert r.stderr.decode().startswith('Error: unknown tx-mode "nope"')


@pytest.mark.parametrize("args", [("schema", "nonexistent"), ("migrate", "nonexistent"), ("completion", "invalid")])
def test_unknown_immediate_group_child_prints_help(invoke, args):
    r = invoke(*args)
    assert r.returncode == 0 and r.stderr == b"" and b"Usage:" in r.stdout


def test_unknown_root_command_and_help_topic(invoke):
    r = invoke("unknowncommand")
    assert r.returncode == 1 and r.stderr.decode() == 'Error: unknown command "unknowncommand" for "atlas"\nRun \'atlas --help\' for usage.\n'
    h = invoke("help", "unknowncommand")
    assert h.returncode == 0 and b"Unknown help topic [`unknowncommand`]" in h.stdout

