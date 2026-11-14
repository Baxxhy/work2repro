import pytest

TOP = ("ethabi-cli 18.0.0\nEthereum ABI coder\n\nUSAGE:\n    executable <SUBCOMMAND>\n\n"
       "FLAGS:\n    -h, --help       Prints help information\n    -V, --version    Prints version information\n\n"
       "SUBCOMMANDS:\n    decode    Decode ABI call result\n    encode    Encode ABI call\n    help      Prints this message or the help of the given subcommand(s)\n")

def test_top_help_and_version(invoke):
    for args in [("--help",), ("-h",), ("help",)]:
        r = invoke(*args)
        assert r.returncode == 0 and r.stdout == TOP and not r.stderr
    for args in [("--version",), ("-V",), ("--version", "decode")]:
        r = invoke(*args)
        assert r.returncode == 0 and r.stdout == "ethabi-cli 18.0.0\n" and not r.stderr

def test_no_args_and_bad_command(invoke):
    for args in [(), ("wat",), ("--wat",)]:
        r = invoke(*args)
        assert r.returncode == 1 and not r.stdout and r.stderr.endswith("\n")
        assert "USAGE:" in r.stderr

@pytest.mark.parametrize("args,terms", [
    (("encode",), ("Encode ABI call", "function", "params", "help")),
    (("decode",), ("Decode ABI call result", "function", "params", "log", "help")),
    (("encode", "params"), ("Specify types of input params inline", "-v <type-or-param> <type-or-param>")),
    (("encode", "function"), ("Load function from JSON ABI file", "<abi-path>", "<function-name-or-signature>", "-p")),
    (("decode", "params"), ("<data>", "-t")),
    (("decode", "function"), ("<abi-path>", "<function-name-or-signature>", "<data>")),
    (("decode", "log"), ("Decode event log", "<event-name-or-signature>", "<data>", "-l")),
])
def test_subcommand_help(invoke, args, terms):
    r = invoke(*args, "--help")
    assert r.returncode == 0 and not r.stderr
    for term in terms:
        assert term in r.stdout

def test_routed_versions(invoke):
    routes = [("encode",), ("decode",), ("encode", "params"), ("encode", "function"),
              ("decode", "params"), ("decode", "function"), ("decode", "log")]
    for route in routes:
        r = invoke(*route, "-V")
        assert r.returncode == 0 and r.stdout.startswith("executable-" + "-".join(route[1:]))

def test_help_pseudo_command_errors(invoke):
    r = invoke("help", "decode")
    assert r.returncode == 0 and "Decode ABI call result" in r.stdout
    r = invoke("help", "--help")
    assert r.returncode == 1 and "wasn't recognized" in r.stderr
