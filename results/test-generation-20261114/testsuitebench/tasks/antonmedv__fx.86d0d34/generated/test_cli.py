import json
import os
import subprocess
from pathlib import Path

BIN = "/workspace/executable"


def run(*args, data=None, env=None, cwd="/workspace/eval", timeout=8):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run([BIN, *map(str, args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=cwd, env=merged, timeout=timeout)


def out(*args, data=None):
    p = run(*args, data=data)
    assert p.returncode == 0, (p.returncode, p.stdout, p.stderr)
    assert p.stderr == b""
    return p.stdout


def test_help_and_version_precedence():
    p = run("--version")
    assert (p.returncode, p.stdout, p.stderr) == (0, b"39.2.0\n", b"")
    assert run("-v").stdout == b"39.2.0\n"
    assert run("-V").stdout == b"39.2.0\n"
    assert run("--help").stdout.startswith(b"\n  fx 39.2.0\n")
    assert run("--help").stdout.endswith(b"\n\n")
    assert run("--help").stderr == b""
    assert run("--help", "--version").stdout.startswith(b"\n  fx")
    assert run("--version", "--help").stdout == b"39.2.0\n"
    assert run("missing-file", "--version", "--help").stdout == b"39.2.0\n"


def test_themes_exports():
    p = run("--themes")
    assert p.returncode == 0
    assert b'export FX_THEME="0"' in p.stdout and b'export FX_THEME="1"' in p.stdout
    for word in (b'"string"', b'"number"', b'"boolean"', b'"null"'):
        assert word in p.stdout
    assert p.stderr == b"\n" * 14
    x = json.loads(out("--export-themes"))
    assert isinstance(x, dict) and len(x) >= 10 and ("0" in x or "1" in x)
    assert all(isinstance(v, list) and v and all(isinstance(c, str) for c in v) for v in x.values())


def test_completion_flags():
    assert out("--comp", "bash").startswith(b"complete -o filenames -C fx fx")
    assert out("--comp=zsh").count(b"_fx()") >= 1
    z = out("--comp", "zsh")
    assert b"#compdef fx" in z and b"local " in z and b"compdef _fx fx" in z
    assert b"complete --command fx" in out("--comp", "fish")
    assert out("--comp", "powershell")
    assert out("--comp", "bogus") == b"unknown shell type\n"
    p = run("--comp")
    assert p.returncode == 2 and b"needs an argument" in p.stderr and b"-comp" in p.stderr


def test_flags_and_piped_source_semantics():
    assert out("-rs", data=b"123\ntrue\n") == b"[\n  \"123\",\n  \"true\"\n]\n"
    assert out("-sr", data=b"123\ntrue\n") == out("-rs", data=b"123\ntrue\n")
    p = run("--", data=b"1")
    assert p.returncode == 1 and b"Unexpected token" in p.stderr
    p = run("--raw=1", data=b"1")
    assert p.returncode == 1 and b"Invalid left-hand side in assignment" in p.stderr
    assert out("--slurp", data=b"") == b"[]\n"
    p = run(".", data=b"")
    assert (p.returncode, p.stdout, p.stderr) == (0, b"", b"")
    p = run(".", data=b"\n")
    assert p.returncode == 1 and p.stdout == b"" and p.stderr.startswith(b"Unexpected character '\\x00' on line 2.")


def test_json_stream_and_scalars():
    assert out(".", data=b'"hi"\n[1,2]\n{"x":true}\n') == b'hi\n[\n  1,\n  2\n]\n{\n  "x": true\n}\n'
    assert out(".", data=b'"a\\n\\u2603"') == "a\n☃\n".encode()
    assert out(".", data=b'9007199254740991') == b"9007199254740991\n"
    assert out(".", data=b'9007199254740992') == b"9007199254740992\n"
    assert out(".", data=b'-9007199254740992') == b"-9007199254740992\n"
    assert out(".", data=b'-NaN') == b"-NaN\n"
    assert out(".", data=b'undefined') == b"undefined\n"
    assert out(".", data=b'{"a":1,"b":2,"a":3}') == b'{\n  "a": 3,\n  "b": 2\n}\n'


def test_relaxed_and_strict_json():
    assert json.loads(out(".", data=b'{/*c*/"a":[1,2,],//x\n"b":true,}')) == {"a": [1, 2], "b": True}
    for raw in (b"[1,]", b"// hi\n1", b"undefined", b"NaN", b"Infinity"):
        p = run("--strict", ".", data=raw)
        assert p.returncode == 1 and p.stdout == b""
    p = run("--strict", ".", data=b"[1,2,]")
    assert b"Trailing comma is not allowed in strict mode" in p.stderr
    p = run("--strict", ".", data=b'"\\g"')
    assert p.returncode == 1 and b"escape" in p.stderr.lower()
    p = run(".", data=b'"a\\/b"')
    assert p.returncode == 2 and p.stdout == b"" and p.stderr.startswith(b"panic: invalid syntax\n")
    p = run(".", data=b'"\\ud83d\\ude00"')
    assert p.returncode == 2 and p.stderr.startswith(b"panic: invalid syntax\n")
    p = run(".", data=b'"\\g"')
    assert p.returncode == 2 and b"panic:" in p.stderr


def test_parse_errors_and_queries():
    p = run(".", data=b"{invalid}")
    assert p.returncode == 1 and p.stdout == b"" and b"Expected object key to be a string" in p.stderr
    assert b"  {invalid}\n  .^" in p.stderr
    p = run("nonexistent()", data=b"1")
    assert p.returncode == 1 and p.stdout == b""
    assert p.stderr == b"\n  nonexistent()\n  ^^^^^^^^^^^^^\n\nReferenceError: nonexistent is not defined\n"
    p = run("x +", data=b"1")
    assert p.returncode == 1 and b"Unexpected token" in p.stderr


def test_raw_and_slurp():
    assert out("-r", ".[1]", data=b"Hello World\nThis is line 2\nLine 3 here\n") == b"e\nh\ni\n"
    assert out("--raw", ".length", data=b"abc") == b"3\n"
    assert out("--raw", "map(x => x.toUpperCase())", data=b"abc\ndef\n") == b"ABC\nDEF\n"
    assert out("--slurp", ".length", data=b'{"a":1}\n{"b":2}\n') == b"2\n"
    assert out("--slurp", ".", data=b"1") == b"[\n  1\n]\n"
    assert out("--raw", "--slurp", ".", data=b"\nA\n") == b'[\n  "",\n  "A"\n]\n'


def test_pipeline_paths_and_missing_values():
    assert out(".a", "x + 2", data=b'{"a":3}') == b"5\n"
    assert out("x => x.name", data=b'{"name":"Ada"}') == b"Ada\n"
    assert out(".items[1].name", data=b'{"items":[{}, {"name":"ok"}]}') == b"ok\n"
    assert out("x[\"a.b\"]", data=b'{"a.b":4}') == b"4\n"
    assert out(".[0]", data=b'[5,6]') == b"5\n"
    p = run(".missing", data=b"{}")
    assert (p.returncode, p.stdout, p.stderr) == (0, b"", b"undefined\n")
    p = run(".[999999999999]", data=b"[]")
    assert (p.returncode, p.stdout, p.stderr) == (0, b"", b"undefined\n")
    p = run(".[1.5]", data=b'["a","b","c"]')
    assert (p.returncode, p.stdout, p.stderr) == (0, b"", b"undefined\n")
    p = run("void 5", data=b"1")
    assert (p.returncode, p.stdout, p.stderr) == (0, b"", b"undefined\n")


def test_collection_shorthands():
    assert json.loads(out("@.name", data=b'[{"name":"a"},{"name":"b"}]')) == ["a", "b"]
    assert json.loads(out("?.age >= 18", data=b'[{"age":10},{"age":20}]')) == [{"age": 20}]
    assert json.loads(out("?.age >= 18 && x.active === true", data=b'[{"age":20,"active":true},{"age":20}]')) == [{"age": 20, "active": True}]
    assert json.loads(out(".[]", data=b"[1,2]")) == [1, 2]
    assert json.loads(out(".[].name", data=b'[{"name":"a"},{"name":"b"}]')) == ["a", "b"]
    assert json.loads(out(".[][]", data=b"[[1,2],[3]]")) == [1, 2, 3]
    for q in ("map(.id)", "filter(.age >= 18)", "map(.)", "[.name]", ".field]", ".a..b"):
        p = run(q, data=b'{"name":"x"}')
        assert p.returncode == 1 and p.stdout == b""


def test_expression_language_and_literals():
    cases = [
        ("1 + 2 * 3", b"7\n"), ("2 ** 3", b"8\n"), ("5 % 2", b"1\n"),
        ("1 === 1", b"true\n"), ("1 == '1'", b"true\n"),
        ("!0", b"true\n"), ("null ?? 4", b"4\n"), ("true ? 2 : 3", b"2\n"),
        ('typeof null', b"object\n"), ('typeof undefined', b"undefined\n"),
        ('[1,2,3].map(n=>n*2)', b"[\n  2,\n  4,\n  6\n]\n"),
        ('({a:1,b:2}).a', b"1\n"), ('({[x.key]: x.val})', b'{\n  "a": 2\n}\n'),
        ('[...x,3]', b"[\n  1,\n  2,\n  3\n]\n"),
        ('`hi ${x.name}`', b"hi Ada\n"),
    ]
    payloads = [b"1", b"1", b"1", b"1", b"1", b"1", b"1", b"1", b"1", b"1",
                b"1", b'{"key":"a","val":2}', b"[1,2]", b'{"name":"Ada"}']
    for i, ((q, expected), data) in enumerate(zip(cases, payloads)):
        p = run(q, data=data)
        assert p.returncode == 0 and p.stdout == expected and p.stderr == b"", (i, p.stdout, p.stderr)


def test_array_methods_and_helpers():
    checks = [
        ('[1,2,3,4].filter(n=>n%2===0)', b'[\n  2,\n  4\n]\n'),
        ('[1,2,3,4].reduce((a,b)=>a+b,0)', b'10\n'),
        ('[3,1,4].sort((a,b)=>b-a)', b'[\n  4,\n  3,\n  1\n]\n'),
        ('[1,2,3].find(n=>n>1)', b'2\n'), ('[1,2,3].findIndex(n=>n>1)', b'1\n'),
        ('[1,2,3].some(n=>n===2)', b'true\n'), ('[1,2,3].every(n=>n>0)', b'true\n'),
        ('[1,2,3].at(-1)', b'3\n'), ('[1,2,3].slice(1,-1)', b'[\n  2\n]\n'),
        ('"a,b,c".split(",")', b'[\n  "a",\n  "b",\n  "c"\n]\n'),
        ('len("😀é")', b'3\n'), ('len({a:1,b:2})', b'2\n'),
        ('keys([10,20])', b'[\n  "0",\n  "1"\n]\n'), ('values([10,20])', b'[\n  10,\n  20\n]\n'),
        ('flatten([[1,2],[3]])', b'[\n  1,\n  2,\n  3\n]\n'),
        ('chunk(2)', b'[\n  [ 1, 2 ],\n  [ 3 ]\n]\n'),
        ('uniq([1,1,2])', b'[\n  1,\n  2\n]\n'),
    ]
    for q, expected in checks:
        data = b"[1,2,3]" if q in ("chunk(2)",) else b"1"
        p = run(q, data=data)
        assert p.returncode == 0 and p.stdout == expected, (q, p.stdout, p.stderr)


def test_strings_objects_globals_and_numbers():
    assert out('"hello".substring(1,4)', data=b"1") == b"ell\n"
    assert out('"42".padStart(5,"0")', data=b"1") == b"00042\n"
    assert out('"hello".charCodeAt(0)', data=b"1") == b"104\n"
    assert out('"hello".replace("l","x")', data=b"1") == b"hexlo\n"
    assert out('Object.keys({a:1,b:2})', data=b"1") == b'[\n  "a",\n  "b"\n]\n'
    assert out('JSON.stringify({a:1})', data=b"1") == b'{"a":1}\n'
    assert out('parseInt("12px")', data=b"1") == b"12\n"
    assert out('Math.sqrt(9)', data=b"1") == b"3\n"
    assert out('toBase64("hello")', data=b"1") == b"aGVsbG8=\n"
    assert out('fromBase64("SGVsbG8gV29ybGQ=")', data=b"1") == b"Hello World\n"
    p = run('fromBase64("abc!")', data=b"1")
    assert p.returncode == 1 and p.stderr.endswith(b"GoError: illegal base64 data at input byte 3\n")
    assert out('YAML.stringify({a:1,nested:{b:true},items:[1,2],nothing:null,empty:{}})', data=b"1") == (
        b"a: 1\nnested:\n  b: true\nitems:\n- 1\n- 2\nnothing: null\nempty: {}\n\n")


def test_more_query_builtins_and_error_contracts():
    checks = [
        ('[1,2,3].includes(2)', b'true\n'), ('[1,2,3].indexOf(2)', b'1\n'),
        ('[1,2,3].lastIndexOf(2)', b'1\n'), ('[1,2,3].join("-")', b'1-2-3\n'),
        ('[1,2,3].concat([4])', b'[\n  1,\n  2,\n  3,\n  4\n]\n'),
        ('[1,2,3].flatMap(n=>[n,n])', b'[\n  1,\n  1,\n  2,\n  2,\n  3,\n  3\n]\n'),
        ('"abc".toUpperCase()', b'ABC\n'), ('" abc ".trim()', b'abc\n'),
        ('"abc".startsWith("a")', b'true\n'), ('"abc".endsWith("c")', b'true\n'),
        ('"abc".includes("b")', b'true\n'), ('"abc".slice(1,-1)', b'b\n'),
        ('Object.values({a:1,b:2})', b'[\n  1,\n  2\n]\n'),
        ('Object.entries({a:1})', b'[\n  [ "a", 1 ]\n]\n'),
        ('Object.fromEntries([["a",1]])', b'{\n  "a": 1\n}\n'),
        ('Array.isArray([])', b'true\n'), ('isFinite("2")', b'true\n'),
        ('Math.max(1,5,3)', b'5\n'), ('(new Date()).getFullYear() > 2020', b'true\n'),
    ]
    for q, expected in checks:
        p = run(q, data=b"1")
        assert p.returncode == 0 and p.stdout == expected and p.stderr == b"", (q, p.stdout, p.stderr)
    for q, fragment in [("len(42)", b"Cannot get length of number"),
                        ("noSuchName", b"ReferenceError"),
                        ("throw new Error(\"message\")", b"message")]:
        p = run(q, data=b"1")
        assert p.returncode == 1 and p.stdout == b"" and fragment in p.stderr


def test_yaml_and_toml():
    assert json.loads(out("--yaml", ".", data=b'a: 1\nb:\n - true\n - x\n')) == {"a": 1, "b": [True, "x"]}
    assert json.loads(out("--yaml", "--slurp", ".", data=b"---\na: 1\n---\nb: 2\n")) == [{"a": 1}, {"b": 2}]
    p = run("--yaml", ".", data=b"a: [1, 2\n")
    assert p.returncode == 1 and p.stderr == b"" and b"[1:4] sequence end token ']' not found" in p.stdout
    assert out("--toml", ".", data=b'title="hi"\n[nested]\nx=2\n') == b'{\n  "title": "hi",\n  "nested": {\n    "x": 2\n  }\n}\n'
    p = run("--yaml", "--toml", data=b"a: 1")
    assert p.returncode == 1 and p.stdout == b"Error: can't use both --yaml and --toml flags together\n"
    for args in (("--raw", "--yaml"), ("--toml", "-r")):
        p = run(*args, data=b"1")
        assert p.returncode == 1 and p.stdout == b"Error: can't use --yaml/--toml and --raw flags together\n"


def test_file_errors_and_save(tmp_path):
    missing = str(tmp_path / "absent.json")
    p = run(missing, ".")
    assert p.returncode == 1 and missing.encode() in p.stderr and b"no such file or directory" in p.stderr.lower()
    source = tmp_path / "data.json"
    source.write_text('{"a":1}', encoding="utf-8")
    p = run(str(source), 'v=>{v.a=2;v.b=[3,4];return save(v)}')
    assert p.returncode == 0 and p.stderr == b"" and b'"a": 2' in p.stdout
    assert json.loads(source.read_text()) == {"a": 2, "b": [3, 4]}
    assert run(str(source), ".b[1]").stdout == b"4\n"
    p = run("save(1)", data=b"1")
    assert p.returncode == 1 and b"specify a file as the first argument" in p.stderr
    p = run("save(undefined)", data=b"1")
    assert p.returncode == 1 and b"Cannot save undefined" in p.stderr
    target = tmp_path / "target.json"; target.write_text('{"v":1}')
    link = tmp_path / "link.json"; link.symlink_to(target)
    p = run(str(link), 'save({v:2})')
    assert p.returncode != 0 and b"cannot save to a symbolic link" in p.stderr.lower()
    assert json.loads(target.read_text()) == {"v": 1}


def test_config_and_environment(tmp_path):
    (tmp_path / ".fxrc.js").write_text("function double(x) { return x * 2; }", encoding="utf-8")
    p = run("double(5)", data=b"1", cwd=str(tmp_path))
    assert p.returncode == 0 and p.stdout == b"10\n"
    for theme in ("0", "1", "2", "🔥"):
        p = run(".", data=b"1", env={"FX_THEME": theme})
        assert p.returncode == 0
    p = run(".", data=b"1", env={"FX_THEME": "invalid_theme"})
    assert p.returncode == 1 and b"unknown theme" in p.stderr.lower()
    for val in ("true", "yes", "on", "1", "false"):
        assert run(".", data=b"1", env={"FX_SHOW_SIZE": val}).returncode == 0
    for indent in ("2", "...."):
        assert run(".", data=b'{"a":1}', env={"FX_INDENT": indent}).returncode == 0


def test_formatting_and_output_destinations():
    assert out(".", data=b"[1,2,3]") == b"[\n  1,\n  2,\n  3\n]\n"
    assert b"[ 1, 2 ]" in out(".", data=b"[[1,2],[3,4]]")
    p = run("--no-inline", ".", data=b"[[1,2]]")
    assert p.returncode == 0 and b"[ 1, 2 ]" not in p.stdout
    assert out(".", data=b'[{"x":1,"y":2},{"x":3,"y":4}]') == b'[\n  { "x": 1, "y": 2 },\n  { "x": 3, "y": 4 }\n]\n'
    p = run("JSON.stringify(x.map(v=>v%2 ? v : skip))", data=b"[1,2,3,4]")
    assert p.returncode == 0 and p.stdout == b"[1,null,3,null]\n"
    p = run("x.value > 2 ? x : skip", data=b'{"value":1}\n{"value":3}')
    assert p.returncode == 0 and p.stdout == b'{\n  "value": 3\n}\n'
    p = run("console.log('a', 2); x", data=b"3")
    assert p.returncode == 0 and p.stdout == b"a 2\n3\n"
