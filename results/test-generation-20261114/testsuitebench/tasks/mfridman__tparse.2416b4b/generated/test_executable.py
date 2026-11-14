import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXE = ROOT / "executable"


def ev(action, pkg="example/p", test=None, elapsed=None, output=None, time=None, **extra):
    d = {"Action": action, "Package": pkg}
    if test is not None: d["Test"] = test
    if elapsed is not None: d["Elapsed"] = elapsed
    if output is not None: d["Output"] = output
    if time is not None: d["Time"] = time
    d.update(extra)
    return d


def stream(*events):
    if len(events) == 1 and not isinstance(events[0], dict):
        events = tuple(events[0])
    return "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events)


def run(data="", *args, env=None, cwd=None):
    e = os.environ.copy()
    e.pop("NO_COLOR", None)
    if env: e.update(env)
    return subprocess.run([str(EXE), *args], input=data, text=True, capture_output=True,
                          env=e, cwd=cwd, timeout=8)


def test_help_and_version_are_exact():
    h = run("", "--help")
    assert h.returncode == 0 and h.stderr == ""
    assert h.stdout.startswith("Usage:\n    go test ./... -json | tparse [options...]\n")
    assert h.stdout.endswith("    -trimpath          Remove path prefix from package names in output, simplifying their display.\n")
    v = run("", "-v")
    assert (v.returncode, v.stdout, v.stderr) == (0, "tparse version: (devel)\n", "")


@pytest.mark.parametrize("args,fragment", [
    (["-unknown"], "flag provided but not defined: -unknown"),
    (["-file"], "flag needs an argument: -file"),
    (["-slow", "abc"], 'invalid value "abc" for flag -slow'),
], ids=["unknown-flag", "missing-value", "invalid-integer"])
def test_flag_parse_errors(args, fragment):
    p = run("", *args)
    assert p.returncode == 2 and fragment in p.stderr and "Usage:" in p.stderr


def test_invalid_enum_is_nonfatal_and_exact():
    p = run("", "-sort", "Elapsed")
    assert p.returncode == 0 and p.stdout == ""
    assert p.stderr == 'invalid option:"Elapsed". The -sort flag must be one of: name, elapsed or cover\n'


def test_no_events_and_malformed_after_event():
    expected = "no parsable events: Make sure to run go test with -json flag\n"
    p = run("plain text\n")
    assert (p.returncode, p.stdout, p.stderr) == (1, "", expected)
    p = run(stream(ev("pass")) + "{bad json}\n")
    assert p.returncode == 1 and p.stdout == "" and p.stderr


def test_empty_stdin_pipe_is_rejected():
    p = run("")
    assert p.returncode == 1 and p.stdout == ""
    assert "stdin must be a pipe, or use -file" in p.stderr


def test_file_input_precedes_stdin_and_paths_with_spaces(tmp_path):
    f = tmp_path / "events with spaces.json"
    f.write_text(stream(ev("pass", "file/pkg", elapsed=1.25)))
    p = run("not json", "-file", str(f), "-nocolor")
    assert p.returncode == 0 and "file/pkg" in p.stdout and "1.25s" in p.stdout


def test_summary_counts_subtests_and_package_status_is_authoritative():
    data = stream(ev("pass", test="Parent/ok", elapsed=.2), ev("fail", test="Parent/bad", elapsed=.4),
                  ev("fail", test="Parent", elapsed=.5), ev("pass", elapsed=3.77))
    p = run(data, "-nocolor")
    assert p.returncode == 0
    for value in ("PASS", "3.77s", "3", "1", "0"):
        assert value in p.stdout
    assert "example/p" in p.stdout


def test_package_failure_fails_even_without_details():
    p = run(stream(ev("pass", test="ok", elapsed=.1), ev("fail", elapsed=.2)), "-nocolor")
    assert p.returncode == 1 and "FAIL" in p.stdout and "example/p" in p.stdout


def test_selectors_include_failed_rows_but_filter_pass_and_skip():
    data = stream(ev("pass", test="Tpass", elapsed=1), ev("skip", test="Tskip", elapsed=2),
                  ev("fail", test="Tfail", elapsed=3), ev("pass", elapsed=4))
    passed = run(data, "-pass", "-nocolor").stdout
    assert "Tpass" in passed and "Tfail" in passed and "Tskip" not in passed
    skipped = run(data, "-skip", "-nocolor").stdout
    assert "Tskip" in skipped and "Tfail" in skipped and "Tpass" not in skipped
    all_rows = run(data, "-all", "-nocolor").stdout
    assert all(x in all_rows for x in ("Tpass", "Tskip", "Tfail"))


def test_slow_limit_is_per_package_and_does_not_change_counts():
    data = "".join(stream(ev("pass", "pkg/a", f"A{i}", t) for i, t in enumerate([5, 3, 1, .5])) +
                   stream(ev("pass", "pkg/b", f"B{i}", t) for i, t in enumerate([4, 2])) +
                   stream(ev("pass", "pkg/a", elapsed=6), ev("pass", "pkg/b", elapsed=5)))
    p = run(data, "-pass", "-slow", "2", "-nocolor")
    assert p.returncode == 0
    for s in ("A0", "A1", "B0", "B1"): assert s in p.stdout
    for s in ("A2", "A3"): assert s not in p.stdout
    assert "4" in p.stdout and "2" in p.stdout


def test_sort_elapsed_and_trim_prefix():
    data = stream(ev("pass", "org/a", elapsed=1), ev("pass", "org/z", elapsed=3))
    p = run(data, "-sort=elapsed", "-trimpath=org/", "-nocolor")
    assert p.returncode == 0
    assert p.stdout.index("z") < p.stdout.index("a")
    assert "org/a" not in p.stdout and "org/z" not in p.stdout


def test_coverage_cached_and_no_tests():
    data = stream(ev("output", "pkg/cov", output="coverage: 60.5% of statements\n"),
                  ev("pass", "pkg/cov", elapsed=1), ev("output", "pkg/cache", output="ok  pkg/cache 0.2s (cached)\n"),
                  ev("pass", "pkg/cache", elapsed=.2), ev("output", "pkg/empty", output="?  \tpkg/empty\t[no test files]\n"),
                  ev("pass", "pkg/empty", elapsed=0))
    p = run(data, "-notests", "-nocolor")
    assert p.returncode == 0
    assert "60.5%" in p.stdout and "(cached)" in p.stdout and "NOTEST" in p.stdout and "[no test files]" in p.stdout


def test_no_test_only_is_displayed_and_does_not_fail():
    p = run(stream(ev("output", "empty", output="?  \tempty\t[no test files]\n"), ev("pass", "empty", elapsed=0)), "-nocolor")
    assert p.returncode == 0 and "NOTEST" in p.stdout and "empty" in p.stdout


def test_formats_and_no_color():
    data = stream(ev("pass", "strings", "A", .2), ev("pass", "strings", "B", .1), ev("pass", "strings", elapsed=3.77))
    plain = run(data, "-format", "plain", "-nocolor").stdout
    assert "Status   Elapsed   Package" in plain and "3.77s" in plain and "╭" not in plain
    md = run(data, "-format", "markdown", "-nocolor").stdout
    assert "| Status | Elapsed | Package | Cover | Pass | Fail | Skip |" in md
    assert "|--------|---------|" in md
    colored = run(data)
    assert "\x1b[92mPASS\x1b[0m" in colored.stdout
    no_color = run(data, env={"NO_COLOR": ""})
    assert "\x1b[" not in no_color.stdout


def test_follow_filters_framework_and_timestamp():
    data = stream(ev("output", output="=== RUN   TestX\nlog line\n--- PASS: TestX (0.1s)\n"),
                  ev("pass", test="TestX", elapsed=.1), ev("output", output="ok  \texample/p\t0.1s\n"), ev("pass", elapsed=.1))
    p = run(data, "-follow", "-nocolor")
    assert p.returncode == 0 and "log line\n" in p.stdout
    assert "=== RUN" not in p.stdout and "--- PASS:" not in p.stdout
    verbose = run(data, "-follow-verbose", "-nocolor").stdout
    assert "=== RUN" in verbose and "--- PASS:" in verbose
    ts = run(data, "-follow", "-include-timestamp", "-nocolor").stdout
    assert "2024" not in ts  # absent timestamps do not invent one


def test_follow_output_file_takes_precedence(tmp_path):
    out = tmp_path / "raw.txt"
    data = stream(ev("output", output="visible raw\n"), ev("pass", elapsed=.1))
    p = run(data, "-follow", "-follow-output", str(out), "-nocolor")
    assert p.returncode == 0 and out.read_text() == "visible raw\n"
    assert "visible raw" not in p.stdout and "example/p" in p.stdout


def test_progress_uses_full_path_and_precedes_summary():
    p = run(stream(ev("pass", "org/pkg", elapsed=.14)), "-progress", "-trimpath", "org/", "-nocolor")
    assert p.returncode == 0 and "[PASS]\t     0.14s\torg/pkg\n" in p.stdout
    assert p.stdout.index("[PASS]") < p.stdout.rindex("╭")


def test_panic_and_race_control_exit_and_output():
    panic = stream(ev("output", output="panic: exploded\ngoroutine 1 [running]:\n trace\n"), ev("fail", elapsed=.1))
    p = run(panic, "-nocolor")
    assert p.returncode == 1 and "PANIC" in p.stdout and "panic: exploded" in p.stdout
    race = stream(ev("output", output="WARNING: DATA RACE\nrace details\n"), ev("pass", test="T", elapsed=.1), ev("pass", elapsed=.2))
    p = run(race, "-nocolor")
    assert p.returncode == 1 and "WARNING: DATA RACE" not in p.stdout and "PASS" in p.stdout


def test_failure_output_is_rendered_and_terminal_fail_exits_one():
    data = stream(ev("output", test="T", output="    test.go:20: assertion failed\n", pkg="example/p"),
                  ev("fail", test="T", elapsed=.1), ev("fail", elapsed=.2))
    p = run(data, "-nocolor")
    assert p.returncode == 1 and "package: example/p" in p.stdout and "assertion failed" in p.stdout


def test_build_events_forward_to_stderr_but_are_not_packages():
    data = stream(ev("build-output", "", output="compiler message\n", ImportPath="x"), ev("build-fail", "", ImportPath="x"))
    p = run(data)
    assert p.returncode == 1 and p.stdout == ""
    assert "compiler message\n" in p.stderr and p.stderr.endswith("found no go test packages\n")


def test_bare_package_skip_is_success():
    p = run(stream(ev("skip", elapsed=0)), "-nocolor")
    assert p.returncode == 0 and "0.00s" in p.stdout and "1" in p.stdout


def test_compare_shows_coverage_delta(tmp_path):
    old = tmp_path / "old.json"
    old.write_text(stream(ev("output", output="coverage: 50.0% of statements\n"), ev("pass", elapsed=1)))
    current = stream(ev("output", output="coverage: 60.5% of statements\n"), ev("pass", elapsed=1))
    p = run(current, "-compare", str(old), "-nocolor")
    assert p.returncode == 0 and "60.5% (+10.5%)" in p.stdout
