import os
import subprocess
from pathlib import Path

import pytest


EVAL = Path(__file__).resolve().parent
EXE = Path(os.environ.get("PUEUE_EXECUTABLE", "/workspace/executable"))


def invoke(*args, cwd=None, env=None, timeout=10):
    child_env = os.environ.copy()
    for key in ("PUEUE_CONFIG_PATH", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_RUNTIME_DIR"):
        child_env.pop(key, None)
    child_env.update({"HOME": str(EVAL / "home"), "XDG_CONFIG_HOME": str(EVAL / "xdg"),
                      "XDG_DATA_HOME": str(EVAL / "data"), "XDG_RUNTIME_DIR": str(EVAL / "runtime"),
                      "NO_COLOR": "1", "COLUMNS": "120"})
    if env:
        child_env.update(env)
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd or EVAL, env=child_env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def write_config(tmp_path, text):
    path = tmp_path / "pueue.yml"
    path.write_text(text, encoding="utf-8")
    return path


def assert_parse_error(result, contains):
    assert result.returncode == 2
    assert result.stdout == b""
    assert contains.encode() in result.stderr
    assert b"For more information, try '--help'." in result.stderr


def test_version_forms_and_global_verbose_flags():
    for args in [("--version",), ("-V",), ("-v", "--version"), ("-vv", "--version"),
                 ("-vvv", "--version"), ("-v", "-v", "-v", "-v", "--version"),
                 ("--verbose", "--verbose", "--version")]:
        result = invoke(*args)
        assert result.returncode == 0
        assert result.stdout == b"pueue 4.0.4\n"
        assert result.stderr == b""


def test_top_level_help_includes_commands_and_global_options():
    for flag in ("-h", "--help"):
        result = invoke(flag)
        assert result.returncode == 0
        out = result.stdout.decode()
        assert out.startswith("Interact with the Pueue daemon")
        assert "add" in out and "shutdown" in out and "completions" in out
        assert "--config" in out and "--profile" in out and "--color" in out
        assert result.stderr == b""


@pytest.mark.parametrize("command", ["add", "remove", "switch", "stash", "enqueue", "start", "restart",
                                      "pause", "kill", "send", "edit", "env", "group", "status", "log",
                                      "follow", "wait", "clean", "reset", "shutdown", "parallel", "completions"],
                         ids=["add", "remove", "switch", "stash", "enqueue", "start", "restart", "pause",
                              "kill", "send", "edit", "env", "group", "status", "log", "follow", "wait",
                              "clean", "reset", "shutdown", "parallel", "completions"])
def test_each_command_has_standalone_help(command):
    result = invoke(command, "--help")
    assert result.returncode == 0
    assert result.stdout
    assert result.stderr == b""


def test_unknown_subcommand_uses_clap_diagnostic():
    result = invoke("nonexistent")
    assert_parse_error(result, "error: unrecognized subcommand 'nonexistent'")
    assert b"Usage: executable [OPTIONS] [COMMAND]" in result.stderr


def test_negative_log_id_is_rejected_before_configuration():
    result = invoke("log", "-1")
    assert result.returncode == 2
    assert result.stdout == b""
    assert b"error: unexpected argument '-1' found" in result.stderr
    assert b"tip: to pass '-1' as a value, use '-- -1'" in result.stderr
    assert b"Usage:" in result.stderr and b"--help" in result.stderr


def test_nonnumeric_kill_id_diagnostic_is_exact():
    result = invoke("kill", "abc")
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr.decode() == ("error: invalid value 'abc' for '[TASK_IDS]...': invalid digit found in string\n\n"
                                     "For more information, try '--help'.\n")


def test_attached_negative_priority_is_accepted_as_argument_then_connects(tmp_path):
    secret = tmp_path / "secret"
    secret.write_bytes(b"secret")
    config = write_config(tmp_path, f"shared:\n  unix_socket_path: /missing/pueue.sock\n  shared_secret_path: {secret}\n")
    result = invoke("-c", config, "add", "--priority=-17", "true")
    assert result.returncode != 2
    assert b"invalid value" not in result.stderr


def test_separated_negative_priority_is_parser_error():
    result = invoke("add", "--priority", "-17", "true")
    assert result.returncode == 2
    assert result.stdout == b""
    assert b"error: unexpected argument '-1' found" in result.stderr
    assert b"Usage: executable add [OPTIONS] <COMMAND>..." in result.stderr


def test_parallel_nonnumeric_is_exact_parser_error():
    result = invoke("parallel", "abc")
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr.decode() == ("error: invalid value 'abc' for '[PARALLEL_TASKS]': invalid digit found in string\n\n"
                                     "For more information, try '--help'.\n")


def test_invalid_signal_is_a_parser_error():
    result = invoke("kill", "--signal", "INVALIDSIGNAL", "0")
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr.decode() == ("error: invalid value 'INVALIDSIGNAL' for '--signal <SIGNAL>': Matching variant not found\n\n"
                                     "For more information, try '--help'.\n")


def test_wait_status_is_case_sensitive_and_log_full_conflicts_with_lines():
    result = invoke("wait", "--status", "DONE")
    assert_parse_error(result, "invalid value 'DONE'")
    result = invoke("log", "--lines", "3", "--full")
    assert_parse_error(result, "cannot be used with")


def test_group_and_all_selection_conflict_is_parser_error():
    for command in ("start", "pause", "kill", "stash", "enqueue", "log", "wait"):
        result = invoke(command, "--group", "alpha", "--all")
        assert result.returncode == 2
        assert result.stdout == b""
        assert b"cannot be used with" in result.stderr


def test_invalid_delay_is_rejected_before_config_loading():
    for value in ("not-a-valid-delay", "April 21 2027 3:00 PM"):
        result = invoke("add", "--delay", value, "true")
        assert result.returncode == 2
        assert result.stdout == b""
        assert b"could not parse as seconds or date expression" in result.stderr
        assert b"For more information, try '--help'." in result.stderr


def test_add_option_conflicts_are_reported_before_connecting():
    cases = [(("add", "--immediate", "--stashed", "true"), "--immediate' cannot be used with '--stashed"),
             (("add", "--immediate", "--delay", "1", "true"), "--delay <delay>' cannot be used with '--immediate"),
             (("add", "--follow", "true"), "the following required arguments were not provided")]
    for args, diagnostic in cases:
        result = invoke(*args)
        assert_parse_error(result, diagnostic)


def test_help_and_completions_do_not_require_configuration_or_daemon(tmp_path):
    for shell, prefix in (("bash", "_pueue() {"), ("fish", "# Print an optspec"),
                          ("zsh", "#compdef pueue"), ("elvish", "use builtin;"),
                          ("nushell", "module completions {")):
        result = invoke("completions", shell)
        assert result.returncode == 0
        assert result.stdout.decode().startswith(prefix)
        assert result.stderr == b""
    output_dir = tmp_path / "generated"
    output_dir.mkdir()
    result = invoke("completions", "bash", output_dir)
    assert result.returncode == 0 and result.stdout == b""
    assert sorted(p.name for p in output_dir.iterdir()) == ["pueue.bash"]


def test_invalid_completion_shell_lists_possible_values():
    result = invoke("completions", "invalid")
    assert result.returncode != 0
    assert b"invalid value" in result.stderr
    assert b"possible values:" in result.stderr


def test_explicit_missing_config_is_structured_and_fails_before_connecting():
    missing = str(EVAL / "absent-config.yml")
    result = invoke("-c", missing, "status")
    err = result.stderr.decode(errors="replace")
    assert result.returncode != 0 and result.stdout == b""
    assert "Failed to read configuration." in err
    assert f'I/O error at path "{missing}"' in err
    assert "No such file or directory" in err
    assert "Location:" in err and "pueue/src/bin/pueue.rs" in err


def test_cli_config_overrides_missing_environment_config(tmp_path):
    secret = tmp_path / "secret"
    secret.write_bytes(b"secret")
    path = write_config(tmp_path, f"shared:\n  unix_socket_path: /missing/pueue.sock\n  shared_secret_path: {secret}\n")
    result = invoke("-c", path, "status", env={"PUEUE_CONFIG_PATH": str(tmp_path / "absent-env.yml")})
    assert result.returncode != 0
    assert b"absent-env.yml" not in result.stderr
    assert b"/missing/pueue.sock" in result.stderr


@pytest.mark.parametrize("yaml_text,expected", [
    ("client:\n  restart_in_place: nope\n", "expected a boolean"),
    ("client:\n  max_status_lines: -1\n", "expected usize"),
    ("shared:\n  pueue_directory: []\n", "expected path string"),
    ("shared:\n  pueue_directory: [x]\n", "expected path string"),
    ("client:\n  edit_mode: invalid_mode\n", "unknown variant `invalid_mode`, expected `toml` or `files`"),
    ("daemon:\n  env_vars: nope\n", "expected a map"),
    ("daemon:\n  shell_command: nope\n", "expected a sequence"),
], ids=["boolean", "unsigned", "path", "path-sequence", "edit-mode", "mapping", "sequence"])
def test_invalid_configuration_types_fail_before_connection(tmp_path, yaml_text, expected):
    config = write_config(tmp_path, yaml_text)
    result = invoke("-c", config, "status")
    assert result.returncode != 0 and result.stdout == b""
    text = result.stderr.decode(errors="replace")
    assert "Failed to read configuration." in text
    assert expected in text
    assert "Location:" in text


def test_explicit_missing_profile_is_a_wrapped_config_error(tmp_path):
    config = write_config(tmp_path, "profiles: {}\n")
    result = invoke("-c", config, "-p", "nonexistent", "status")
    err = result.stderr.decode(errors="replace")
    assert result.returncode != 0
    assert 'Couldn\'t find profile with name "nonexistent"' in err
    assert "Location:" in err


def test_absent_socket_report_preserves_nested_causes(tmp_path):
    sock = str(tmp_path / "missing.sock")
    secret = tmp_path / "secret"
    secret.write_bytes(b"secret")
    config = write_config(tmp_path, f"shared:\n  unix_socket_path: {sock}\n  shared_secret_path: {secret}\n")
    result = invoke("-c", config, "status")
    err = result.stderr.decode(errors="replace")
    assert result.returncode != 0
    assert "Failed to initialize client." in err
    assert "Failed to initialize stream." in err
    assert f'I/O error at path "{sock}"' in err
    assert "while connecting to daemon" in err
    assert "No such file or directory" in err
