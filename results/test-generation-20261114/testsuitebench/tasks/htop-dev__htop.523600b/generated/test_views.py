import os
import pwd
import subprocess
import sys
import time

import pytest


FIELDS = ["PID", "Command", "STATE", "PPID", "PGRP", "SESSION", "TTY", "TPGID", "MINFLT", "CMINFLT", "MAJFLT", "CMAJFLT", "UTIME", "STIME", "CUTIME", "CSTIME", "PRIORITY", "NICE", "STARTTIME", "PROCESSOR", "M_VIRT", "M_RESIDENT", "M_SHARE", "M_TRS", "M_DRS", "M_LRS", "ST_UID", "PERCENT_CPU", "PERCENT_MEM", "USER", "TIME", "NLWP", "TGID", "PERCENT_NORM_CPU", "ELAPSED", "SCHEDULERPOLICY", "RCHAR", "WCHAR", "SYSCR", "SYSCW", "RBYTES", "WBYTES", "CNCLWB", "IO_READ_RATE", "IO_WRITE_RATE", "IO_RATE", "CGROUP", "CCGROUP", "CONTAINER", "ISCONTAINER", "OOM", "IO_PRIORITY", "M_PSS", "M_SWAP", "M_PSSWP", "CTXT", "SECATTR", "COMM", "EXE", "CWD", "AUTOGROUP_ID", "AUTOGROUP_NICE", "M_PRIV"]


def test_every_documented_sort_column_is_accepted(invoke):
    for field in FIELDS:
        r = invoke("-n", "1", "-s", field, timeout=5)
        assert r.returncode == 0 and r.stdout, field


@pytest.mark.parametrize("field", ["INVALID_KEY_XYZ", "pid"], ids=["unknown", "wrong-case"])
def test_invalid_sort_key_rejected(invoke, field):
    r = invoke("-n", "1", "-s", field)
    assert r.returncode != 0 and r.stderr


def test_sort_last_wins_and_equals_form(invoke):
    assert invoke("-n", "1", "-s", "INVALID_KEY_XYZ", "-s", "PID").returncode == 0
    assert invoke("-n", "1", "--sort-key=PID").returncode == 0


def test_pid_filter_normal_and_large_list(invoke, plain):
    r = invoke("-n", "1", "-p", "1")
    out = plain(r.stdout)
    assert r.returncode == 0 and "PID" in out
    assert "1" in out
    pidlist = ",".join(str(i) for i in range(1, 10001))
    many = invoke("-n", "1", "-p", pidlist, timeout=5)
    assert many.returncode == 0 and many.stderr == b"" and b"PID" in many.stdout


def test_pid_list_tolerates_spaces_duplicates_trailing_and_missing(invoke, plain):
    for value in ("1, 1,", "999999999999"):
        r = invoke("-n", "1", "--pid=" + value)
        assert r.returncode == 0 and "PID" in plain(r.stdout)


def test_user_filters(invoke, plain):
    for args in (("-u", "root"), ("--user=root",), ("-u", "0"), ("-u",)):
        r = invoke(*args, "-n", "1")
        assert r.returncode == 0 and "PID" in plain(r.stdout)
    current = pwd.getpwuid(os.geteuid()).pw_name
    assert invoke("-u", current, "-n", "1").returncode == 0


@pytest.mark.parametrize("user", ["not_a_real_user_eval", "-2", "abc123", "999999999999"], ids=["unknown-name", "negative", "mixed", "overflow"])
def test_invalid_users_rejected(invoke, user):
    r = invoke("-u", user, "-n", "1")
    assert r.returncode != 0 and any(x in r.stderr.lower() for x in (b"invalid", b"user", b"error"))


def test_command_filter_semantics_and_empty_match(invoke, plain):
    p = subprocess.Popen(["sleep", "20"])
    try:
        time.sleep(0.05)
        for value in ("sleep", "SLEEP", "bash|sleep", "test.*"):
            r = invoke("-n", "1", "-F", value)
            assert r.returncode == 0 and len(r.stdout) > 50
            assert "PID" in plain(r.stdout)
        matched = invoke("-n", "1", "-F", "sleep")
        assert "sleep" in plain(matched.stdout).lower()
        empty = invoke("-n", "1", "-F", "zz_no_such_command_eval")
        assert empty.returncode == 0 and "PID" in plain(empty.stdout)
    finally:
        p.terminate()
        p.wait(timeout=2)


def test_filter_is_fixed_text_and_accepts_alternatives(invoke):
    assert invoke("-n", "1", "--filter=bash|python").returncode == 0
    assert invoke("-n", "1", "--filter=test.*").returncode == 0


def test_tree_and_sort_compose_with_filters(invoke, plain):
    for args in (("-t",), ("-t", "-s", "PID"), ("-t", "-p", "1"), ("-t", "-u", "root"), ("-t", "-F", "sleep"), ("-t", "-s", "PERCENT_CPU", "--readonly", "--no-meters")):
        r = invoke(*args, "-n", "2")
        assert r.returncode == 0 and len(plain(r.stdout)) > 50


@pytest.mark.parametrize("duration", ["0", "1", "5", "50", "999", "-1"], ids=["zero", "one", "five", "fifty", "large", "negative"])
def test_highlight_duration_values(invoke, duration):
    r = invoke("--highlight-changes=" + duration, "-n", "1")
    assert r.returncode == 0 and r.stdout and r.stderr == b""


def test_optional_highlight_and_short_options(invoke):
    for args in (("-H",), ("-H", "5"), ("-H", "-n", "1"), ("-n", "1", "-d", "0", "-C", "-U", "-M", "-t")):
        if args[0] == "-H" and "-n" not in args:
            args = (*args, "-n", "1")
        r = invoke(*args)
        assert r.returncode == 0 and r.stdout


@pytest.mark.parametrize("token", ["--drop-capabilities", "--drop-capabilities=off", "--drop-capabilities=basic", "--drop-capabilities=strict"], ids=["bare", "off", "basic", "strict"])
def test_drop_capabilities_is_explicitly_unsupported(invoke, token):
    r = invoke(token, "-n", "1")
    assert r.returncode == 1 and r.stdout == b"" and b"unrecognized option" in r.stderr and token.encode() in r.stderr


def test_options_can_be_repeated_and_last_scalar_wins(invoke):
    r = invoke("-n", "2", "-d", "0", "-s", "PID", "-s", "USER", "-C", "-C", "--no-unicode", "--no-mouse", "--no-meters", "--no-function-bar", "--readonly", "-t", "-n", "1")
    assert r.returncode == 0 and r.stdout

