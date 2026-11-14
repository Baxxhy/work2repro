import os
import signal
import subprocess
import time
from pathlib import Path

import pytest


EXE = Path(__file__).resolve().parent.parent / "executable"
USAGE = "usage: entr [-acdnprsxz] utility [argument [/_] ...] < filenames\n"
HINT = "hint: use -h to display option summary\n"
RELEASE = "release: 5.7\n"


def run(args=(), paths=b"", *, env=None, timeout=5, cwd=None, exe=None):
    return subprocess.run([str(exe or EXE), *map(str, args)], input=paths,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=env, cwd=cwd, timeout=timeout)


def base_env(**extra):
    e = os.environ.copy()
    e.pop("EV_TRACE", None)
    e.pop("ENTR_FOLLOW_SYMLINK", None)
    e.pop("ENTR_STATUS_SCRIPT", None)
    e.pop("ENTR_RESTART_SIGNAL", None)
    e["HOME"] = extra.pop("HOME", "/tmp")
    e.update(extra)
    return e


def test_help_exact_streams_and_status():
    p = run(["-h", "-n"])
    assert p.returncode == 1
    assert p.stdout == (b"summary:\n    -a  Do not consolidate events\n    -c  Clear screen before execution\n"
                        b"    -d  Track files added or removed from directories\n    -n  Non-interactive mode\n"
                        b"    -p  Wait for first event\n    -r  Run as a background process, use signal to restart\n"
                        b"    -s  Evaluate using a shell\n    -x  Format exit status\n    -z  Exit after the utility completes\n"
                        b"docs:\n    man entr\n")
    assert p.stderr == (b"release: 5.7\nusage: entr [-acdnprsxz] utility [argument [/_] ...] < filenames\n")
    assert b"commands:" not in p.stdout


@pytest.mark.parametrize("args", [(), ("-n",)], ids=["no-args", "only-option"])
def test_missing_utility(args):
    p = run(args)
    assert p.returncode == 1 and p.stdout == b""
    assert p.stderr == (RELEASE + USAGE + HINT).encode()


@pytest.mark.parametrize("args,char", [(["-q"], "q"), (["--help"], "-"),
                                        (["-nh"], "h"), (["-hn"], "h"),
                                        (["-n", "-h"], "h")],
                         ids=["unknown-short", "long-option", "clustered-h", "h-first-cluster", "h-after-option"])
def test_invalid_option_diagnostic(args, char):
    p = run(args)
    assert p.returncode == 1 and p.stdout == b""
    assert p.stderr.startswith(f"{EXE}: invalid option -- '{char}'\n".encode())
    assert p.stderr.endswith((RELEASE + USAGE + HINT).encode())


def test_invocation_spelling_is_preserved_in_option_error(tmp_path):
    link = tmp_path / "custom-entr"
    link.symlink_to(EXE)
    p = run(["-q"], exe=link)
    assert p.returncode == 1
    assert p.stderr.startswith(f"{link}: invalid option -- 'q'\n".encode())


@pytest.mark.parametrize("args", [["-n", "-z", "--", "-n"], ["-nz", "--help"]], ids=["dash-dash-utility", "long-arg-after-utility"])
def test_options_stop_at_utility(args):
    p = run(args, b"\n")
    assert p.returncode == 1
    assert b"No regular files to watch" in p.stderr


def test_stdin_empty_lines_and_no_valid_paths():
    for data in (b"", b"\n\n"):
        p = run(["-n", "-z", "/bin/true"], data)
        assert p.returncode == 1 and p.stdout == b""
        assert p.stderr == b"executable: No regular files to watch\n"


def test_invalid_paths_report_and_valid_path_still_runs(tmp_path):
    f = tmp_path / "valid file"
    f.write_bytes(b"")
    missing = tmp_path / "missing"
    data = b"\n" + os.fsencode(missing) + b"\n" + os.fsencode(f)  # no final newline
    p = run(["-n", "-z", "/bin/echo", "ok"], data)
    assert p.returncode == 0 and p.stdout == b"ok\n"
    assert f"executable: unable to stat '{missing}'\n".encode() in p.stderr


def test_literal_whitespace_path_is_not_trimmed(tmp_path):
    f = tmp_path / "with space\tname"
    f.touch()
    p = run(["-n", "-z", "/bin/true"], os.fsencode(f) + b"\n")
    assert p.returncode == 0
    assert p.stderr == b""


def test_directory_and_symlink_are_accepted(tmp_path):
    d = tmp_path / "dir"
    d.mkdir()
    target = tmp_path / "target"
    target.touch()
    link = tmp_path / "link"
    link.symlink_to(target)
    p = run(["-n", "-z", "/bin/true"], os.fsencode(d) + b"\n" + os.fsencode(link) + b"\n")
    assert p.returncode == 0
    assert p.stderr == b""


def test_fifo_is_rejected(tmp_path):
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)
    p = run(["-n", "-z", "/bin/true"], os.fsencode(fifo) + b"\n")
    assert p.returncode == 1
    assert f"executable: unable to stat '{fifo}'\n".encode() in p.stderr
    assert p.stderr.endswith(b"executable: No regular files to watch\n")


def test_large_path_list_and_hardlink_deduplication(tmp_path):
    paths = []
    for i in range(205):
        f = tmp_path / f"file-{i}"
        f.touch()
        paths.append(f)
    alias = tmp_path / "hardlink"
    os.link(paths[0], alias)
    data = b"\n".join(os.fsencode(p) for p in [paths[0], alias, *paths]) + b"\n"
    p = run(["-n", "-z", "/bin/echo", "ok"], data)
    assert p.returncode == 0 and p.stdout == b"ok\n"
    assert p.stderr == b""


def test_follow_symlink_environment_and_leading_edge_spelling(tmp_path):
    target = tmp_path / "target file"
    target.touch()
    link = tmp_path / "link"
    link.symlink_to(target)
    p = run(["-n", "-z", "/bin/printf", "%s", "/_"], os.fsencode(link) + b"\n",
            env=base_env(ENTR_FOLLOW_SYMLINK="1"))
    assert p.returncode == 0 and p.stdout == os.fsencode(link)


@pytest.mark.parametrize("value", ["HUP", "SIGHUP", "INT", "SIGINT", "QUIT", "SIGQUIT", "TERM", "SIGTERM"],
                         ids=["hup", "sig-hup", "int", "sig-int", "quit", "sig-quit", "term", "sig-term"])
def test_recognized_restart_signal_values(value, tmp_path):
    f = tmp_path / "f"
    f.touch()
    p = run(["-n", "-z", "/bin/true"], os.fsencode(f) + b"\n",
            env=base_env(ENTR_RESTART_SIGNAL=value))
    assert p.returncode == 0 and p.stderr == b""


def test_nonexistent_utility_and_arguments(tmp_path):
    f = tmp_path / "watch"
    f.touch()
    p = run(["-n", "-z", "not-a-real-utility-xyz"], os.fsencode(f) + b"\n")
    assert p.returncode == 1
    assert p.stderr == b"executable: exec not-a-real-utility-xyz: No such file or directory\n"


def test_direct_exec_arguments_path_cwd_and_streams(tmp_path):
    watch = tmp_path / "watch"
    watch.touch()
    tool = tmp_path / "tool"
    tool.write_text("#!/bin/sh\nprintf '%s|%s|%s' \"$PWD\" \"$1\" \"$2\"\nprintf 'err' >&2\n")
    tool.chmod(0o755)
    p = run(["-n", "-z", str(tool), "a b", "*"], os.fsencode(watch) + b"\n", cwd=tmp_path)
    assert p.returncode == 0
    assert p.stdout == f"{tmp_path}|a b|*".encode()
    assert p.stderr == b"err"


def test_argument_boundaries_many_args_and_large_binary_output(tmp_path):
    watch = tmp_path / "watch"
    watch.touch()
    script = tmp_path / "emit"
    script.write_text("#!/usr/bin/python3\nimport os,sys\nos.write(1, bytes(range(256))*512)\nos.write(2,b'Z'*120000)\nprint(len(sys.argv)-1, file=sys.stdout)\n")
    script.chmod(0o755)
    args = [f"arg{i}" for i in range(220)]
    p = run(["-n", "-z", str(script), *args], os.fsencode(watch) + b"\n")
    assert p.returncode == 0
    assert p.stdout.startswith(bytes(range(256)) * 512)
    assert p.stdout.endswith(b"220\n")
    assert p.stderr == b"Z" * 120000


def test_leading_edge_substitution_first_only_and_preserves_spelling(tmp_path):
    f = tmp_path / "a file;name"
    f.touch()
    p = run(["-n", "-z", "/bin/printf", "%s|%s|%s", "/_", "/_", "_"], os.fsencode(f) + b"\n")
    assert p.returncode == 0
    assert p.stdout == os.fsencode(f) + b"|/_|_"


def test_shell_mode_shell_semantics_and_leading_edge_as_zero(tmp_path):
    f = tmp_path / "payload"
    f.write_text("shell-data")
    p = run(["-n", "-s", "-z", "printf '%s:' \"$0\"; cat \"$0\"; printf ':ok'"], os.fsencode(f) + b"\n")
    assert p.returncode == 0
    assert p.stdout == os.fsencode(f) + b":shell-data:ok"


def test_shell_requires_one_command_argument(tmp_path):
    f = tmp_path / "f"
    f.touch()
    p = run(["-n", "-s", "-z", "/bin/true", "extra"], os.fsencode(f) + b"\n")
    assert p.returncode == 1
    assert p.stderr == b"executable: -s requires commands to be formatted as a single argument\n"


@pytest.mark.parametrize("code", [0, 42, 255], ids=["zero", "ordinary", "max-byte"])
def test_z_propagates_exit_status(tmp_path, code):
    f = tmp_path / "f"
    f.touch()
    p = run(["-n", "-z", "/bin/sh", "-c", f"exit {code}"], os.fsencode(f) + b"\n")
    assert p.returncode == code


def test_z_propagates_signal_status(tmp_path):
    f = tmp_path / "f"
    f.touch()
    p = run(["-n", "-z", "/bin/sh", "-c", "kill -TERM $$"], os.fsencode(f) + b"\n")
    assert p.returncode == 143


def test_pager_default_and_existing_environment(tmp_path):
    f = tmp_path / "f"
    f.touch()
    script = "printf '%s|%s' \"$PAGER\" \"$CUSTOM_KEEP\""
    for pager, expected in ((None, "/bin/cat"), ("custom pager", "custom pager")):
        env = base_env(CUSTOM_KEEP="kept")
        if pager is not None:
            env["PAGER"] = pager
        p = run(["-n", "-s", "-z", script], os.fsencode(f) + b"\n", env=env)
        assert p.returncode == 0
        assert p.stdout == f"{expected}|kept".encode()


@pytest.mark.parametrize("signal_value,diagnostic", [("sigterm", "sigterm"), ("", ""), ("0", "0"), ("SIGKILL", "KILL"), ("USR1", "USR1")], ids=["lowercase", "empty", "numeric", "stripped-prefix", "unsupported-name"])
def test_restart_signal_validation_even_without_restart(tmp_path, signal_value, diagnostic):
    f = tmp_path / "f"
    f.touch()
    env = base_env(ENTR_RESTART_SIGNAL=signal_value)
    p = run(["-n", "-z", "/bin/true"], os.fsencode(f) + b"\n", env=env)
    assert p.returncode == 1 and p.stdout == b""
    assert p.stderr == f"executable: unrecognized signal: {diagnostic} <> (HUP, INT, QUIT, TERM, USR1, USR2)\n".encode()


@pytest.mark.parametrize("args", [["-r", "-x"], ["-x", "-r"]], ids=["restart-first", "format-first"])
def test_restart_and_format_options_are_mutually_exclusive(args):
    p = run(args)
    assert p.returncode == 1 and p.stdout == b""
    assert p.stderr == b"executable: -r and -x may not be combined\n"


def test_clear_screen_prefix_one_and_two(tmp_path):
    f = tmp_path / "f"
    f.touch()
    for opts, prefix in (("-cnz", b"\x1b[2J\x1b[H"), ("-ccnz", b"\x1b[2J\x1b[3J\x1b[H")):
        p = run([opts, "/bin/printf", "x"], os.fsencode(f) + b"\n")
        assert p.returncode == 0
        assert p.stdout == prefix + b"x"


def test_noninteractive_child_stdin_is_not_a_tty(tmp_path):
    f = tmp_path / "f"
    f.touch()
    p = run(["-n", "-z", "/usr/bin/tty"], os.fsencode(f) + b"\n")
    assert p.returncode == 1
    assert p.stdout == b"not a tty\n"


def test_interactive_without_controlling_terminal_fails_cleanly(tmp_path):
    f = tmp_path / "f"
    f.touch()
    p = run(["-z", "/bin/true"], os.fsencode(f) + b"\n", env=base_env())
    assert p.returncode == 1 and p.stdout == b""
    assert p.stderr == b"executable: unable to get terminal attributes, use '-n' to run non-interactively\n"


def _wait_for(path, predicate, timeout=4):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            if predicate(path.read_bytes()):
                return True
        except OSError:
            pass
        time.sleep(.025)
    return False


def test_file_write_triggers_postponed_run_and_z_exits(tmp_path):
    watched = tmp_path / "watched"
    watched.touch()
    log = tmp_path / "log"
    proc = subprocess.Popen([str(EXE), "-n", "-p", "-z", "/bin/sh", "-c", f"echo run >> '{log}'"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        time.sleep(.2)
        assert proc.poll() is None and not log.exists()
        watched.write_text("changed")
        out, err = proc.communicate(timeout=5)
        assert proc.returncode == 0, (out, err)
        assert log.read_text().splitlines() == ["run"]
    finally:
        if proc.poll() is None:
            proc.kill(); proc.wait()


def test_rename_away_while_postponed_exits_one(tmp_path):
    watched = tmp_path / "watched"
    watched.touch()
    proc = subprocess.Popen([str(EXE), "-n", "-p", "-z", "/bin/echo", "ran"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        time.sleep(.2)
        watched.rename(tmp_path / "away")
        out, err = proc.communicate(timeout=5)
        assert proc.returncode == 1 and out == b""
        assert err == f"executable: cannot open '{watched}': No such file or directory\n".encode()
    finally:
        if proc.poll() is None:
            proc.kill(); proc.wait()


def test_trace_reports_open_max_and_changed_path(tmp_path):
    watched = tmp_path / "watched"
    watched.touch()
    env = base_env(EV_TRACE="1")
    proc = subprocess.Popen([str(EXE), "-n", "-p", "-z", "/bin/true"], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    try:
        time.sleep(.15)
        watched.write_text("x")
        out, err = proc.communicate(timeout=5)
        assert proc.returncode == 0 and out == b""
        assert b"open_max: " in err
        assert b"fflags: 0x" in err and os.fsencode(watched) in err
    finally:
        if proc.poll() is None:
            proc.kill(); proc.wait()


def test_double_x_formats_status_and_creates_default_filter(tmp_path):
    watched = tmp_path / "watched"
    watched.touch()
    home = tmp_path / "home with spaces"
    home.mkdir()
    env = base_env(HOME=str(home))
    p = run(["-nxxz", "/bin/sh", "-c", "exit 42"], os.fsencode(watched) + b"\n", env=env)
    assert p.returncode == 42
    assert p.stdout == f"entr: created '{home}/.entr/status.awk'\nsh returned exit code 42\n".encode()
    filter_file = home / ".entr" / "status.awk"
    assert filter_file.read_text() == '# http://eradman.com/entrproject/status-filters.html\n/^signal/ { print $3, "terminated by signal", $2; }\n/^exit/ { print $3, "returned exit code", $2; }\n'
    assert (filter_file.stat().st_mode & 0o777) == 0o640
    assert (filter_file.parent.stat().st_mode & 0o777) == 0o750


def test_double_x_existing_status_filter_is_used_without_announcement(tmp_path):
    watched = tmp_path / "watched"
    watched.touch()
    script = tmp_path / "filter.awk"
    script.write_text('{ print "custom", $1, $2, $3 }\n')
    env = base_env(ENTR_STATUS_SCRIPT=str(script))
    p = run(["-nxxz", "/bin/sh", "-c", "exit 7"], os.fsencode(watched) + b"\n", env=env)
    assert p.returncode == 7
    assert p.stdout == b"custom exit 7 sh\n"


def test_double_x_shell_status_uses_shell_basename_and_signal(tmp_path):
    watched = tmp_path / "watched"
    watched.touch()
    script = tmp_path / "filter.awk"
    script.write_text('{ print $1, $2, $3 }\n')
    env = base_env(ENTR_STATUS_SCRIPT=str(script), SHELL="/bin/bash")
    p = run(["-nxxsz", "kill -TERM $$"], os.fsencode(watched) + b"\n", env=env)
    assert p.returncode == 143
    assert p.stdout == b"signal 15 bash\n"


def test_single_x_linux_awk_incompatibility(tmp_path):
    watched = tmp_path / "watched"
    watched.touch()
    env = base_env(ENTR_STATUS_SCRIPT=str(tmp_path / "existing.awk"))
    Path(env["ENTR_STATUS_SCRIPT"]).write_text("{print $0}\n")
    p = run(["-nxz", "/bin/true"], os.fsencode(watched) + b"\n", env=env)
    assert p.returncode == 0
    assert b"awk: not an option: -S\n" in p.stderr


def test_non_restart_monitor_continues_after_utility_and_runs_again(tmp_path):
    watched = tmp_path / "watched"
    watched.touch()
    log = tmp_path / "log"
    proc = subprocess.Popen([str(EXE), "-n", "/bin/sh", "-c", f"echo x >> '{log}'"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        assert _wait_for(log, lambda b: b.count(b"x\n") >= 1)
        watched.write_text("event")
        assert _wait_for(log, lambda b: b.count(b"x\n") >= 2)
    finally:
        proc.send_signal(signal.SIGINT)
        proc.communicate(timeout=5)
    assert proc.returncode == 0


def test_restart_mode_replaces_child_on_file_event(tmp_path):
    watched = tmp_path / "watched"
    watched.touch()
    log = tmp_path / "starts"
    proc = subprocess.Popen([str(EXE), "-n", "-r", "/bin/sh", "-c",
                             f"echo start >> '{log}'; exec sleep 30"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        assert _wait_for(log, lambda b: b.count(b"start\n") >= 1)
        watched.write_text("event")
        assert _wait_for(log, lambda b: b.count(b"start\n") >= 2)
        proc.send_signal(signal.SIGINT)
        proc.communicate(timeout=5)
        assert proc.returncode == 0
    finally:
        if proc.poll() is None:
            proc.kill(); proc.wait()


def test_directory_tracking_addition_runs_then_exits_two(tmp_path):
    directory = tmp_path / "dir"
    directory.mkdir()
    listed = directory / "listed"
    listed.touch()
    log = tmp_path / "log"
    proc = subprocess.Popen([str(EXE), "-nd", "/bin/sh", "-c", f"echo x >> '{log}'"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        assert _wait_for(log, lambda b: b.count(b"x\n") >= 1)
        (directory / "sibling").touch()
        out, err = proc.communicate(timeout=5)
        assert proc.returncode == 2
        assert log.read_text().splitlines() == ["x", "x"]
        assert b"directory altered" in err
    finally:
        if proc.poll() is None:
            proc.kill(); proc.wait()


def test_hidden_entry_counting_requires_double_d(tmp_path):
    directory = tmp_path / "dir"
    directory.mkdir()
    listed = directory / "listed"
    listed.touch()
    for opts, expected_exit in (("-nd", 0), ("-ndd", 2)):
        hidden = directory / f".hidden-{opts}"
        log = tmp_path / f"log-{opts}"
        proc = subprocess.Popen([str(EXE), opts, "/bin/sh", "-c", f"echo x >> '{log}'"],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            assert _wait_for(log, lambda b: bool(b))
            hidden.touch()
            if expected_exit == 2:
                _, err = proc.communicate(timeout=5)
                assert proc.returncode == 2 and b"directory altered" in err
            else:
                time.sleep(.25)
                assert proc.poll() is None
        finally:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT); proc.communicate(timeout=5)
