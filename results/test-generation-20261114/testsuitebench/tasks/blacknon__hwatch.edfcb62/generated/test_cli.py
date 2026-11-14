import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

import pytest


EXE = Path(__file__).resolve().parent.parent / "executable"
HEADER = re.compile(rb"\x1b\[38;5;240m=====\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3})\]=========================\x1b\[0m\n")


def invoke(*args, cwd=None, env=None, timeout=4, input=None):
    merged = os.environ.copy()
    merged.pop("HWATCH", None)
    if env:
        merged.update(env)
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd, env=merged,
                          input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout)


def first_record(command, *options, **kwargs):
    p = invoke("--batch", "--interval", "0.03", *options, command, **kwargs)
    assert p.stdout, (p.returncode, p.stderr)
    m = HEADER.search(p.stdout)
    assert m, p.stdout[:300]
    return p, p.stdout[m.end():]


def stop_after_record(command, *options, wait=0.18, **kwargs):
    proc = subprocess.Popen([str(EXE), "--batch", "--interval", "0.03", *map(str, options), str(command)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            cwd=kwargs.get("cwd"), env={**os.environ, **kwargs.get("env", {})})
    try:
        time.sleep(wait)
        proc.send_signal(signal.SIGTERM)
        out, err = proc.communicate(timeout=2)
    finally:
        if proc.poll() is None:
            proc.kill()
    return out, err


def test_version_exact():
    p = invoke("--version")
    assert (p.returncode, p.stdout, p.stderr) == (0, b"hwatch 0.3.19\n", b"")
    assert invoke("-V").stdout == p.stdout


def test_help_aliases_and_validation_order():
    a, b = invoke("--help"), invoke("-h")
    assert a.returncode == b.returncode == 0
    assert a.stdout == b.stdout and a.stdout.endswith(b"\n") and not a.stderr
    assert b"Usage: executable [OPTIONS] [command]..." in a.stdout
    p = invoke("--interval", "bad", "--help")
    assert p.returncode == 2 and b"invalid float literal" in p.stderr and not p.stdout


def test_no_command_and_unknown_option_is_command():
    p = invoke()
    assert p.returncode == 2 and b"error: command not specified and logfile is empty." in p.stderr
    assert b"Usage" in p.stderr
    p = invoke("--unknown-before-help", "--interval", "bad", "--help")
    assert p.returncode == 0 and not p.stdout and not p.stderr


@pytest.mark.parametrize("flag,val,needle", [
    ("--interval", "abc", b"invalid float literal"),
    ("--limit", "-1", b"0..=4294967295"),
    ("--limit", "4294967296", b"0..=4294967295"),
    ("--tab-size", "65536", b"0..=65535"),
    ("--differences", "invalid", b"possible values"),
    ("--output", "invalid", b"possible values"),
])
def test_invalid_values(flag, val, needle):
    p = invoke(flag, val)
    assert p.returncode == 2 and needle in p.stderr and not p.stdout


def test_missing_values_diff_dependency_and_duplicate_boolean():
    for flag, msg in [("--shell", b"a value is required"), ("--aftercommand", b"a value is required"), ("--keymap", b"a value is required")]:
        p = invoke(flag)
        assert p.returncode == 2 and msg in p.stderr
    p = invoke("--diff-output-only")
    assert p.returncode == 2 and p.stdout == b""
    assert b"--differences [<differences>]" in p.stderr
    p = invoke("--batch", "--batch")
    assert p.returncode == 2 and b"cannot be used multiple times" in p.stderr


def test_optional_output_panic_and_optional_logfile():
    for opt in ("-o", "--output"):
        p = invoke(opt, "--", "printf x")
        assert p.returncode == 101 and not p.stdout
        assert b"called `Option::unwrap()` on a `None` value" in p.stderr
    with pytest.raises(subprocess.TimeoutExpired):
        invoke("-b", "-l", "--", "printf defaultlog", timeout=0.12)
    with pytest.raises(subprocess.TimeoutExpired):
        invoke("-b", "--logfile", "--", "printf defaultlog", timeout=0.12)


def test_batch_framing_payload_and_timestamp():
    for command, payload in [("printf hello", b"hello\n"), ("printf 'a\\n'", b"a\n\n"), ("true", b"\n")]:
        p, body = first_record(command)
        assert p.returncode == 0
        assert HEADER.search(p.stdout).group(1)
        assert body.startswith(payload)


def test_batch_output_views_and_control_unicode_preservation():
    p, body = first_record("printf '  hi\t世界🙂\r\\033[31m!\\033[0m'")
    assert body.startswith("  hi\t世界🙂\r\x1b[31m!\x1b[0m\n".encode())
    p, body = first_record("printf out; printf err >&2", "--output", "stdout")
    assert body.startswith(b"out\n")
    p, body = first_record("printf out; printf err >&2", "--output", "stderr")
    assert body.startswith(b"err\n")


def test_shell_syntax_environment_and_custom_shell():
    p, body = first_record("printf '%s' \"$EVAL_VALUE\" | tr a-z A-Z", env={"EVAL_VALUE": "hello"})
    assert body.startswith(b"HELLO\n")
    p, body = first_record("echo middle", "--shell", "bash -c 'echo before; {COMMAND}; echo after'")
    assert body.startswith(b"before\nmiddle\nafter\n")


def test_direct_exec_does_not_expand_shell_metacharacters():
    p, body = first_record("/usr/bin/printf '%s|%s|%s' '$HOME' '*' '$((2+3))'", "--exec")
    assert body.startswith(b"$HOME|*|$((2+3))\n")


def test_changed_records_only_and_beep():
    out, err = stop_after_record("printf fixed")
    assert not err
    assert len(HEADER.findall(out)) == 1
    out, err = stop_after_record("printf fixed", "--beep")
    assert not err and out.count(b"\x07\n") == 1


def test_log_json_lines_sentinel_and_fields(tmp_path):
    log = tmp_path / "watch.jsonl"
    out, err = stop_after_record("printf 'héllo\\n'", "--logfile", log)
    assert not err
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert rows[0] == {"timestamp":"", "command":"", "status":True, "output":"", "stdout":"", "stderr":""}
    assert rows[1]["command"] == "printf héllo\\n"
    assert rows[1]["status"] is True and rows[1]["stdout"] == "héllo\n"
    assert set(rows[1]) == {"timestamp", "command", "status", "output", "stdout", "stderr"}


def test_log_directory_error(tmp_path):
    path = tmp_path / "missing" / "x.jsonl"
    p = invoke("--logfile", path, "true")
    assert p.returncode == 2 and not p.stdout
    assert f'error: directory "{path.parent}" is not exists.'.encode() in p.stderr


def test_invalid_utf8_panics_after_batch_header():
    p = invoke("--batch", "--interval", "0.03", "python3 -c \"import os;os.write(1,b'\\xff')\"", timeout=3)
    assert p.returncode == 101
    assert HEADER.search(p.stdout) and b"stream did not contain valid UTF-8" in p.stderr


def test_hwatch_defaults_and_duplicate_detection():
    p = invoke("printf fromenv", env={"HWATCH":"--batch -n 0.03"}, timeout=0.15)
    assert p.stdout.startswith(b"\x1b[38;5;240m=====[")
    p = invoke("--batch", "true", env={"HWATCH":"--batch"})
    assert p.returncode == 2 and b"cannot be used multiple times" in p.stderr


@pytest.mark.parametrize("mapping", ["x=quit", "ctrl-a=help", "F12=none", "mouse-scroll_up=none", "shift-alt-right=none"] , ids=["key", "modifier", "function", "mouse", "multi-modifier"])
def test_keymap_valid_forms(mapping):
    # Non-TTY startup cannot expose dispatch, but valid mappings must pass parsing.
    p = invoke("--keymap", mapping)
    assert not (p.returncode == 1 and p.stderr == b"Failed to parse keymap.\n")


@pytest.mark.parametrize("mapping", ["=quit", "x=", "x=quit=help", "F13=help", "ctrl-unknown=help", "x=not_an_action"], ids=["empty-key", "empty-action", "multiple-equals", "unsupported-function", "bad-modifier", "bad-action"])
def test_keymap_invalid_forms(mapping):
    p = invoke("--keymap", mapping)
    assert p.returncode == 1 and p.stderr == b"Failed to parse keymap.\n"
