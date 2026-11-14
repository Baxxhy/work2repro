import json
import os
import subprocess
from pathlib import Path

import pytest


EVAL = Path(__file__).resolve().parent
EXE = Path(os.environ.get("VALIDATOR", "/workspace/executable"))


def invoke(args=(), schema=None, instances=(), stdin=None, cwd=None):
    """Write inputs in a private eval subdirectory and invoke the required CLI."""
    d = Path(cwd) if cwd else EVAL / "inputs"
    d.mkdir(parents=True, exist_ok=True)
    if schema is not None:
        (d / "schema.json").write_text(schema if isinstance(schema, str) else json.dumps(schema, ensure_ascii=False), encoding="utf-8")
    cmd = [str(EXE), *map(str, args)]
    if schema is not None:
        cmd.append(str(d / "schema.json"))
    for name, value in instances:
        p = d / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False), encoding="utf-8")
        cmd.extend(["--instance", str(p)])
    return subprocess.run(cmd, input=stdin, text=True, capture_output=True, timeout=8)


def test_help_and_version_contract():
    h = subprocess.run([str(EXE), "--help"], text=True, capture_output=True, timeout=5)
    assert h.returncode == 0 and h.stderr == ""
    assert h.stdout.splitlines()[0] == "Usage: executable [OPTIONS] [SCHEMA]"
    for x in ("Arguments:", "Options:", "The JSON Schema to validate with", "may be specified multiple times", "Select output style", "[default: text]", "4, 6, 7, 2019, 2020", "text, flag, list, hierarchical", "--assert-format", "--no-assert-format", "--cacert", "--connect-timeout", "--errors-only", "--timeout", "--insecure"):
        assert x in h.stdout
    for opt in ("--version", "-v"):
        p = subprocess.run([str(EXE), opt], text=True, capture_output=True, timeout=5)
        assert (p.returncode, p.stdout, p.stderr) == (0, "Version: 0.41.0\n", "")


def test_help_is_immediate_and_end_of_options_is_respected():
    a = subprocess.run([str(EXE), "--help", "--unknown"], text=True, capture_output=True)
    assert a.returncode == 0 and a.stdout.startswith("Usage:")
    b = subprocess.run([str(EXE), "--unknown", "--help"], text=True, capture_output=True)
    assert b.returncode == 2 and b.stdout == "" and "unexpected argument" in b.stderr
    c = subprocess.run([str(EXE), "--" , "--help"], text=True, capture_output=True)
    assert c.returncode == 1 and c.stdout.startswith("Error: ")


@pytest.mark.parametrize("args,needle", [
    (("--draft", "3"), "invalid value"), (("--output", "xml"), "invalid value"),
    (("--timeout", "NaN"), "must be a non-negative finite number"),
    (("--timeout", "1", "--timeout", "2"), "cannot be used multiple times"),
    (("--output", "text", "--output", "flag"), "cannot be used multiple times"),
], ids=["draft-enum", "output-enum", "nan-timeout", "duplicate-timeout", "duplicate-output"])
def test_cli_value_errors(args, needle):
    p = subprocess.run([str(EXE), *args], text=True, capture_output=True)
    assert p.returncode == 2 and p.stdout == "" and p.stderr.startswith("error:")
    assert needle in p.stderr and "For more information, try '--help'." in p.stderr


def test_cli_missing_extra_unknown_and_negative_timeout():
    cases = [([], "<SCHEMA>"), (["--unknown"], "unexpected argument '--unknown' found"),
             (["a", "b"], "unexpected argument 'b' found"), (["--timeout"], "a value is required"),
             (["--timeout", "-1"], "unexpected argument '-1' found")]
    for args, needle in cases:
        p = subprocess.run([str(EXE), *args], text=True, capture_output=True)
        assert p.returncode == 2 and p.stdout == "" and needle in p.stderr


def test_schema_only_ignores_stdin_and_boolean_schemas():
    p = invoke(schema={"type": "string"}, stdin='not json')
    assert (p.returncode, p.stdout, p.stderr) == (0, "Schema is valid\n", "")
    for schema, valid in [(True, 0), (False, 1)]:
        p = invoke(("-d4",), schema=schema)
        assert p.returncode == valid


def test_json_and_file_runtime_failures_are_stdout_status_one():
    d = EVAL / "badjson"; d.mkdir(exist_ok=True)
    cases = [("empty.json", ""), ("tx.json", "tx"), ("trailing.json", "{} {}")]
    for fn, data in cases:
        (d / fn).write_text(data)
        p = subprocess.run([str(EXE), str(d / fn)], text=True, capture_output=True)
        assert p.returncode == 1 and p.stderr == "" and p.stdout.startswith("Error: ")
    p = subprocess.run([str(EXE), str(d / "missing")], text=True, capture_output=True)
    assert p.returncode == 1 and "No such file or directory (os error 2)" in p.stdout


def test_text_validation_multiple_errors_and_errors_only():
    inst = [("bad.json", {"name": 3, "age": 1})]
    p = invoke(schema={"type": "object", "required": ["missing", "also"], "properties": {"name": {"type": "string"}, "age": {"minimum": 4}}}, instances=inst)
    assert p.returncode == 1 and p.stderr == ""
    assert "bad.json" in p.stdout and "INVALID. Errors:" in p.stdout
    assert '"missing" is a required property' in p.stdout and '"also" is a required property' in p.stdout
    assert "is not of type \"string\"" in p.stdout and "less than the minimum of 4" in p.stdout
    q = invoke(("--errors-only",), schema={"type": "number"}, instances=[("ok.json", 8)])
    assert q.returncode == 0 and q.stdout == "" and q.stderr == ""


def test_core_types_bounds_composition_and_unicode():
    p = invoke(schema={"allOf": [{"type": ["string", "null"]}, {"minLength": 2, "pattern": "^a"}]}, instances=[("a.json", "x"), ("b.json", None)])
    assert p.returncode == 1 and "not of any" not in p.stdout and "shorter" in p.stdout
    p = invoke(schema={"minimum": 0.1, "multipleOf": 0.01}, instances=[("a.json", 0.11), ("b.json", 0.1)])
    assert p.returncode == 1 and "a.json" in p.stdout and "b.json - VALID" in p.stdout
    p = invoke(schema={"minLength": 2}, instances=[("u.json", "😀é"), ("v.json", "😀")])
    assert p.returncode == 1 and "u.json - VALID" in p.stdout and "v.json - INVALID" in p.stdout


def test_objects_arrays_dependencies_and_optimized_additional_properties():
    p = invoke(schema={"type": "object", "required": ["x"], "properties": {"a": {"type": "integer"}}, "patternProperties": {"^x": {"type": "string"}}, "additionalProperties": False}, instances=[("obj.json", {"a": "bad", "x1": 2, "z": 3})])
    assert p.returncode == 1 and '"x" is a required property' in p.stdout
    assert "not of type \"integer\"" in p.stdout and "not of type \"string\"" in p.stdout and "'z'" in p.stdout
    p = invoke(schema={"dependencies": {"credit": ["name"]}}, instances=[("dep.json", {"credit": 2})])
    assert p.returncode == 1 and '"name" is a required property' in p.stdout
    p = invoke(schema={"additionalProperties": False}, instances=[("extras.json", {"foo": "bar", "baz": 42, "qux": True})])
    assert p.returncode == 1 and "False schema does not allow 42" in p.stdout


def test_drafts_and_modern_keywords():
    p = invoke(("--draft=4",), schema={"const": 3}, instances=[("x.json", 4)])
    assert p.returncode == 0 and "x.json - VALID" in p.stdout
    p = invoke(("-d2020",), schema={"prefixItems": [{"type": "string"}], "items": False}, instances=[("x.json", ["ok", 1])])
    assert p.returncode == 1 and "Unevaluated" not in p.stdout
    p = invoke(("--draft", "2020"), schema={"items": [True]}, instances=[("x.json", [])])
    assert p.returncode == 1 and "Schema is invalid" in p.stdout


def test_composition_aggregation_and_references():
    p = invoke(schema={"anyOf": [{"type": "string"}, {"minimum": 5}]}, instances=[("x.json", False)])
    assert p.returncode == 1 and "not valid under any" in p.stdout and "not of type" not in p.stdout
    p = invoke(schema={"$defs": {"node": {"type": "object", "properties": {"next": {"$ref": "#/$defs/node"}}}}, "$ref": "#/$defs/node"}, instances=[("tree.json", {"next": {"next": {}}})])
    assert p.returncode == 0
    p = invoke(schema={"$ref": "#/missing"})
    assert p.returncode == 1 and "Pointer '/missing' does not exist" in p.stdout


def test_structured_outputs_and_pointer_escaping():
    inst = [("special.json", {"a/b~c": 2})]
    schema = {"type": "object", "properties": {"a/b~c": {"type": "string"}}}
    for mode in ("flag", "list", "hierarchical"):
        p = invoke(("--output=" + mode,), schema=schema, instances=inst)
        assert p.returncode == 1 and p.stderr == ""
        rec = json.loads(p.stdout)
        assert rec["output"] == mode and rec["instance"].endswith("special.json") and rec["schema"].endswith("schema.json")
        if mode == "flag":
            assert rec["payload"] == {"valid": False}
        elif mode == "list":
            assert rec["payload"]["valid"] is False
            assert all("details" not in n for n in rec["payload"]["details"])
            assert any(n["instanceLocation"] == "/a~1b~0c" for n in rec["payload"]["details"])
        else:
            assert rec["payload"]["valid"] is False


def test_schema_meta_validation_errors_only_and_order_are_stable():
    p = invoke(schema={"type": "invalid"})
    assert p.returncode == 1 and p.stdout.startswith('Schema is invalid. Error: "invalid"')
    p = invoke(("--errors-only",), schema={"minimum": 0}, instances=[("good.json", 1)])
    assert p.returncode == 0 and p.stdout == ""
    args = ("--output", "list")
    q1 = invoke(args, schema={"type": "string"}, instances=[("x.json", 1)])
    q2 = invoke(args, schema={"type": "string"}, instances=[("x.json", 1)])
    assert q1.stdout == q2.stdout


def test_format_and_content_assertions():
    p = invoke(("--assert-format",), schema={"format": "ipv4"}, instances=[("ok.json", "127.0.0.1"), ("bad.json", "192.168.001.1")])
    assert p.returncode == 1 and "bad.json - INVALID" in p.stdout and "ok.json - VALID" in p.stdout
    p = invoke(("--draft=7",), schema={"contentEncoding": "base64"}, instances=[("bad.json", "%%%")])
    assert p.returncode == 1 and "content encoding" in p.stdout


def test_annotations_conditionals_and_unevaluated_keywords():
    schema = {"if": {"properties": {"kind": {"const": "a"}}}, "then": {"required": ["x"]}, "else": {"required": ["y"]}}
    p = invoke(("--draft=7",), schema=schema, instances=[("x.json", {"kind": "a"})])
    assert p.returncode == 1 and '"x" is a required property' in p.stdout
    schema = {"properties": {"fixed": {}}, "unevaluatedProperties": False}
    p = invoke(("-d2020",), schema=schema, instances=[("x.json", {"fixed": 1, "b": 2, "a": 3})])
    assert p.returncode == 1 and "Unevaluated properties are not allowed" in p.stdout and "'a', 'b'" in p.stdout


def test_unicode_large_numbers_and_nested_values():
    p = invoke(schema={"type": "integer", "minimum": 18446744073709551617}, instances=[("big.json", 18446744073709551618)])
    assert p.returncode == 0
    p = invoke(schema={"maxLength": 100000}, instances=[("long.json", "x" * 100000)])
    assert p.returncode == 0
    p = invoke(schema={"type": "object", "required": ["雪"]}, instances=[("unicode.json", {"雪": "é"})])
    assert p.returncode == 0

