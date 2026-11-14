import json
import os
import pathlib
import subprocess

import pytest


EVAL = pathlib.Path(__file__).resolve().parent
BIN = pathlib.Path(os.environ.get("AGRIND_EXECUTABLE", "/workspace/executable"))


def run(query=None, data="", *args, input_bytes=None, cwd=None, cli_args=()):
    cmd = [str(BIN), *map(str, cli_args), *map(str, args)]
    if query is not None:
        cmd.append(query)
    raw = data.encode() if input_bytes is None else input_bytes
    return subprocess.run(cmd, input=raw, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=cwd or EVAL, timeout=20)


def out(result):
    return result.stdout.decode("utf-8", errors="replace")


def err(result):
    return result.stderr.decode("utf-8", errors="replace")


def test_cli_version_and_help():
    v = run(None, cli_args=["--version"])
    assert (v.returncode, v.stdout, v.stderr) == (0, b"ag 0.19.6\n", b"")
    h = run(None, cli_args=["--help"])
    assert h.returncode == 0 and not h.stderr
    assert b"Usage:" in h.stdout and b"QUERY" in h.stdout and b"--alias-dir" in h.stdout


def test_missing_query_and_unknown_flag():
    r = run()
    assert r.returncode != 0 and r.stdout == b"" and r.stderr == b"Error: MissingQuery\n"
    r = run(None, cli_args=["--invalid-flag"])
    assert r.returncode == 2 and r.stdout == b""
    assert r.stderr.decode() == "error: unexpected argument '--invalid-flag' found\n\n  tip: to pass '--invalid-flag' as a value, use '-- --invalid-flag'\n\nUsage: executable [OPTIONS] [QUERY]\n\nFor more information, try '--help'.\n"


def test_file_overrides_stdin_and_lossy_utf8(tmp_path):
    f = tmp_path / "in.log"
    f.write_bytes(b"file\n")
    r = run("*", "stdin\n", "--file", f)
    assert r.returncode == 0 and out(r) == "file\n"
    r = run("*", input_bytes=b"left\xffright\n")
    assert r.returncode == 0 and out(r) == "left\ufffdright\n"


def test_missing_file_contract():
    r = run("*", cli_args=["--file", "/definitely/not/present/agrind"])
    assert r.returncode == 1 and r.stdout == b""
    assert r.stderr == b'Error: Os { code: 2, kind: NotFound, message: "No such file or directory" }\n'


def test_filter_terms_globs_case_and_precedence():
    data = "error one\nWARN two\nerror timeout\nother\n"
    r = run('(error OR warn) AND NOT timeout', data)
    assert out(r) == "error one\nWARN two\n"
    assert out(run('err*timeout', data)) == "error timeout\n"
    assert out(run('"ERROR"', "error\nERROR\n")) == "ERROR\n"
    assert out(run('"*STAR*"', "*STAR*\nSTAR\n")) == "*STAR*\n"


def test_filter_implicit_and_and_boolean_words_are_terms():
    assert out(run("db-1 response", "DB-1 got response\ndb-1 only\n")) == "DB-1 got response\n"
    assert out(run("true", "true\nTRUE story\nfalse\n")) == "true\nTRUE story\n"
    assert out(run("false", "true\nFALSEhood\nfalse\n")) == "FALSEhood\nfalse\n"


def test_raw_records_trim_trailing_whitespace_and_empty_input():
    assert out(run("*", "  value \t\n   \n\t\n")) == "  value\n\n\n"
    assert out(run("*", "")) == ""
    r = run("* | count", "")
    assert r.returncode == 0 and out(r) == "No data\n"


def test_large_line_and_record_count_are_not_truncated():
    long_record = "x" * 100_000
    data = long_record + "\n" + ("row\n" * 100_000)
    r = run("*", data)
    lines = out(r).splitlines()
    assert r.returncode == 0 and len(lines) == 100_001
    assert lines[0] == long_record and lines[-1] == "row"


def test_json_types_malformed_continues_and_nonobject():
    r = run("* | json", '{"z":[1,true,null],"a":"é"}\nnope\n[1,2]\n', "-o", "json")
    assert r.returncode == 0
    assert out(r) == '{"a":"é","z":[1,true,null]}\n{}\n'
    assert err(r) == "error: Expected JSON, found nope\n"


def test_json_from_retains_source_fields():
    r = run('* | logfmt | json from payload', 'payload="{\\"x\\":7}"\n', "-o", "json")
    assert r.returncode == 0
    assert json.loads(out(r)) == {"payload": '{"x":7}', "x": 7}


def test_logfmt_parses_types_quotes_and_bare_keys():
    r = run("* | logfmt", 'level=info msg="server started" port=8080 enabled=true bare\n', "-o", "json")
    assert json.loads(out(r)) == {"level": "info", "msg": "server started", "port": 8080, "enabled": True, "bare": None}


def test_logfmt_empty_assignment_compatibility():
    r = run("* | logfmt", 'empty= null_val= number=-42.7\nquoted="" bare\nempty=\n', "-o", "json")
    rows = [json.loads(line) for line in out(r).splitlines()]
    assert rows == [{"number": -42.7}, {"quoted": "bare"}, {"empty": ""}]


def test_plain_parse_conversion_noconvert_nodrop_and_whitespace():
    data = "INFO\t00042\ninvalid\n"
    r = run('* | parse "* *" as level, code', data, "-o", "json")
    assert [json.loads(x) for x in out(r).splitlines()] == [{"level": "INFO", "code": 42}]
    r = run('* | parse "* *" as level, code noconvert nodrop', data, "-o", "json")
    rows = [json.loads(x) for x in out(r).splitlines()]
    assert rows == [{"level": "INFO", "code": "00042"}, {"level": None, "code": None}]


def test_regex_named_captures_and_noconvert():
    r = run('* | parse regex "id=(?P<id>\\d+)" noconvert', 'id=00042\nno match\n', "-o", "json")
    assert [json.loads(x) for x in out(r).splitlines()] == [{"id": "00042"}]


def test_split_separator_quotes_empty_and_indexing():
    r = run('* | logfmt | split(parts) on "." as pieces | fields pieces', 'parts="name..power"\n', "-o", "json")
    assert json.loads(out(r)) == {"pieces": ["name", "power"]}
    r = run('* | split on "." | fields _split', '.a.\n..\n', "-o", "json")
    assert [json.loads(x)["_split"] for x in out(r).splitlines()] == [["a"], []]
    r = run('* | split on " " | fields _split', '"hello world" foo\n', "-o", "json")
    assert json.loads(out(r))["_split"] == ["hello world", "foo"]


def test_fields_calculated_fields_and_nested_path():
    r = run('* | json | user.name as copy | fields user.name, copy', '{"user":{"name":"Ada","id":4},"x":1}\n', "-o", "json")
    assert json.loads(out(r)) == {"user": {"name": "Ada", "id": 4}, "copy": "Ada"}
    assert out(run('* | json | fields absent', '{"x":1}\n', "-o", "json")) == ""


def test_expressions_functions_and_predicates():
    data = '{"x":-2,"s":"héllo","empty":"","blank":"  ","n":2.5}\n'
    r = run('* | json | abs(x) as magnitude | substring(s,1,3) as part | round(n) as rounded | isBlank(blank) as blankish', data, "-o", "json")
    assert json.loads(out(r)) == {"x": -2, "s": "héllo", "empty": "", "blank": "  ", "n": 2.5, "magnitude": 2, "part": "él", "rounded": 3, "blankish": True}
    assert out(run('* | json | where isEmpty(empty)', data, "-o", "json"))


def test_arithmetic_coercion_and_runtime_errors():
    r = run('* | json | x + y as total', '{"x":1.5,"y":2.5}\n{"x":"1,000","y":2}\n', "-o", "json")
    assert [json.loads(x)["total"] for x in out(r).splitlines()] == [4.0, 1002]
    r = run('* | json | x * 10 as total', '{"x":"text"}\n')
    assert r.returncode == 0 and err(r) == "error: Expected numeric operands, found text * 10\n"


def test_where_and_limits():
    assert [json.loads(x)["n"] for x in out(run('* | json | where n >= 2 | limit 2', '{"n":1}\n{"n":2}\n{"n":3}\n{"n":4}\n', "-o", "json")).splitlines()] == [2, 3]
    assert [json.loads(x)["n"] for x in out(run('* | json | limit -2', '{"n":1}\n{"n":2}\n{"n":3}\n', "-o", "json")).splitlines()] == [2, 3]
    r = run('* | json | where 5', '{"n":1}\n')
    assert r.returncode == 1 and "Error: Expected boolean expression" in err(r)


def test_aggregates_group_order_null_and_distinct():
    data = '{"g":"a","v":2}\n{"g":"b","v":1}\n{"g":"a","v":3}\n'
    r = run('* | json | count, sum(v), average(v), min(v), max(v) by g', data, "-o", "json")
    rows = json.loads(out(r))
    assert rows == [{"g": "a", "_count": 2, "_sum": 5, "_average": 2.5, "_min": 2, "_max": 3}, {"g": "b", "_count": 1, "_sum": 1, "_average": 1, "_min": 1, "_max": 1}]
    r = run('* | json | count_distinct(x)', '{"x":1}\n{"x":1.0}\n{"x":"1"}\n{}\n{"x":null}\n', "-o", "json")
    assert json.loads(out(r))[0]["_countDistinct"] == 3


def test_aggregate_empty_and_chaining():
    assert out(run('* | json | count', "", "-o", "json")) == "No data\n"
    r = run('* | json | count by status | where _count >= 2 | sort by status', '{"status":2}\n{"status":2}\n{"status":1}\n', "-o", "json")
    assert json.loads(out(r)) == [{"status": 2, "_count": 2}]


def test_sort_numeric_direction_missing_keys_and_table_json():
    data = '{"n":10}\n{}\n{"n":2}\n'
    r = run('* | json | sort by n', data, "-o", "json")
    assert json.loads(out(r)) == [{}, {"n": 2}, {"n": 10}]
    r = run('* | json | sort by n desc', data, "-o", "json")
    assert json.loads(out(r)) == [{}, {"n": 10}, {"n": 2}]


def test_total_running_sum():
    r = run('* | json | total(n)', '{"n":1}\n{"n":2}\n{"n":3}\n', "-o", "json")
    assert [json.loads(x)["_total"] for x in out(r).splitlines()] == [1, 3, 6]


def test_dates_duration_and_timeslice():
    r = run('* | json | parseDate(ts) as date | timeslice(date) 5m as bucket | fields bucket', '{"ts":"2023-01-01T00:05:30Z"}\n', "-o", "json")
    assert json.loads(out(r))["bucket"] == "2023-01-01T00:05:00+00:00"
    r = run('* | json | parseDate(ts) - parseDate(other) as elapsed | fields elapsed', '{"ts":"2024-01-02T00:00:00Z","other":"2024-01-01T00:00:00Z"}\n', "-o", "json")
    assert json.loads(out(r))["elapsed"] == "PT86400S"


def test_output_json_logfmt_and_custom_format():
    data = '{"a":"hello world","b":2}\n'
    assert out(run('* | json', data, "-o", "logfmt")) == "a=hello world b=2\n"
    assert out(run('* | json', data, "-o", "format={a} {{x}} {missing}")) == "hello world {x} None\n"


def test_alias_builtin_apache():
    line = '127.0.0.1 - frank [10/Oct/2000:13:55:36 -0700] "GET /index.html HTTP/1.0" 200 123\n'
    r = run('* | apache', line, "-o", "json", "--no-alias")
    row = json.loads(out(r))
    assert row["ip"] == "127.0.0.1" and row["method"] == "GET" and row["status"] == 200 and row["contentlength"] == 123


def test_user_alias_dir_override_and_disabled(tmp_path):
    aliases = tmp_path / "aliases"
    aliases.mkdir()
    (aliases / "mine.toml").write_text('keyword = "mine"\ntemplate = """\nparse "*=*" as key, value\n"""\n')
    r = run('* | mine', 'x=7\n', "-o", "json", "--alias-dir", aliases)
    assert r.returncode == 0 and json.loads(out(r)) == {"key": "x", "value": 7}


@pytest.mark.parametrize("query,marker", [
    ("json()", "json does not take any parenthesized arguments"),
    ("logfmt()", "logfmt does not take any parenthesized arguments"),
    ("sum", "expecting a parenthesized argument"),
    ("count_distinct()", "Expecting a single expression to count"),
    ("timeslice 5m", "expecting a parenthesized argument"),
], ids=["json-parens", "logfmt-parens", "missing-sum-arg", "distinct-arg", "timeslice-parens"])
def test_invalid_query_diagnostics(query, marker):
    r = run(query, "")
    assert r.returncode == 1 and r.stdout == b"" and marker in err(r)


def test_unknown_function_and_invalid_regex():
    r = run('* | json | lengt(x) as y', '{"x":"abc"}\n')
    assert r.returncode == 1 and r.stdout == b"" and err(r) == "Error: Unknown function lengt\n"
    r = run('* | parse regex "(?P<x>["', "")
    assert r.returncode == 1 and "regex" in err(r).lower()


def test_no_alias_keeps_builtins_and_conflicting_flags_error():
    assert run('* | testmultioperator', '{}\n', "--no-alias").returncode == 0
    r = run("*", "", "--no-alias", "--alias-dir", "/tmp")
    assert r.returncode != 0 and err(r) == "Error: CantDisableAndOverride\n"
