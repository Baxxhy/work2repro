import os
import subprocess
from pathlib import Path

import pytest

EXE = Path('/workspace/executable')


def run(data='', *args):
    return subprocess.run([str(EXE), *args], input=data.encode('utf-8'), stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd='/tmp', env={**os.environ, 'NO_COLOR': '1'})


def ok(data, *args, out):
    p = run(data, *args)
    assert p.returncode == 0
    assert p.stdout.decode('utf-8') == out
    assert p.stderr == b''


def bad(data, *args, prefix, code=1):
    p = run(data, *args)
    assert p.returncode == code
    assert p.stdout == b''
    assert p.stderr.decode('utf-8').startswith(prefix)


def test_default_yaml_to_json_and_empty_document():
    ok('a: 1\nb: [true, null]\n', out='{"a":1,"b":[true,null]}\n')
    ok('  \r\n ', out='')
    ok('---\n', out='null\n')


def test_format_selection_and_reencoding():
    ok('a: 1\n', 'y', out='{"a":1}\n')
    ok('{"x":1}', 'jy', out='x: 1\n')
    ok('x = 1\n', 'tj', out='{"x":1}\n')
    ok('', 'cj', out='{}\n')
    ok('{"x":1}', 'jj', out='{"x":1}\n')


def test_argv_flags_modifiers_and_validation_precedence():
    ok('x: "<a>&"\n', '-- e-yj', out='{"x":"\\u003ca\\u003e\\u0026"}\n')
    p = run('', '-h', '-p')
    assert p.returncode == 1 and p.stdout == b''
    assert b'invalid flags specified: p' in p.stderr
    bad('', '-jjk', prefix='Usage: ', code=1)
    assert run('', '-h').returncode == 0
    p = run('', '-v')
    assert (p.returncode, p.stdout, p.stderr) == (0, b'v0.0.0\n', b'')


def test_order_duplicates_and_yaml_resolution():
    ok('{z: 1, a: 2}\n', out='{"z":1,"a":2}\n')
    ok('x: yes\ny: TRUE\nz: 0xFF\n', out='{"x":"yes","y":true,"z":255}\n')
    ok('key: one\nkey: two\n', out='{"key":"one","key":"two"}\n')


def test_json_strictness_numbers_and_unicode():
    ok('{"n":1.0,"x":"🎉","m":1.23e10}', 'jj', out='{"n":1,"x":"🎉","m":12300000000}\n')
    ok('9223372036854775807', 'jy', out='9223372036854775807\n')
    bad('{x:1}', 'jj', prefix='Error parsing JSON:')
    bad('{"x":1,}', 'jj', prefix='Error parsing JSON:')
    bad('{"unicode":"\\uD83C\\uDF89"}', 'jj', prefix='Error parsing JSON: yaml: found invalid Unicode character escape code')


def test_yaml_anchors_merge_and_errors():
    ok('base: &b {z: 1, a: 2}\ncopy: *b\n', out='{"base":{"z":1,"a":2},"copy":{"z":1,"a":2}}\n')
    ok('base: &b {z: 1, a: 2}\nitem:\n  <<: *b\n  z: 9\n', out='{"base":{"z":1,"a":2},"item":{"z":1,"a":2,"z":9}}\n')
    bad('a: *missing\n', prefix='Error parsing YAML:')
    bad('a: &loop [*loop]\n', prefix='Error parsing YAML:')


def test_yaml_canonical_output_and_keys():
    ok('{"y":2,"n":13,"123":"v","🎉":"ok"}', 'jy', out='"y": 2\n"n": 13\n"123": v\n"\U0001F389": ok\n')
    ok('{"42":"v","true":"b"}', 'jyk', out='42: v\ntrue: b\n')
    bad('{"null":"v"}', 'jyk', prefix='Error writing YAML:')


def test_toml_values_order_indentation_and_null_omission():
    ok('{"first":1,"gone":null,"array":["string",42,null,true],"nested":{"a":null,"b":2}}', 'jt', out='first = 1\narray = ["string", 42, true]\n\n[nested]\nb = 2\n')
    ok('{"x":1,"child":{"y":2}}', 'jti', out='x = 1\n\n  [child]\n    y = 2\n')
    ok('["s",42,null,true]', 'jt', out='["s", 42, true]')
    bad('a = 1\na = 2\n', 'tj', prefix='Error parsing TOML:')


def test_hcl_blocks_order_and_canonical_encoding():
    ok('x = 1\n', 'cy', out='x: 1\n')
    ok('{"values":[false,true,false,0,1,"","x"]}', 'jc', out='"values" = [0, 1, "", "x"]')
    ok('resource "type" "a" { enabled = true }', 'cj', out='{"resource":[{"type":[{"a":[{"enabled":true}]}]}]}\n')
    bad('x = null\n', 'cj', prefix='Error parsing HCL:')


def test_special_floats_and_json_indentation():
    ok('x: .inf\ny: -.inf\nz: .nan\n', out='{"x":"Infinity","y":"-Infinity","z":"NaN"}\n')
    ok('{"x":"Infinity"}', 'jyn', out='x: Infinity\n')
    ok('{"a":[1,true]}', 'ji', out='{\n  "a": [\n    1,\n    true\n  ]\n}\n')


def test_parse_failure_is_stderr_only():
    bad(' \t\r\n', prefix='Error parsing YAML:')
    bad('', 'jj', prefix='Error parsing JSON:')
    bad('name = "test\n', 'tj', prefix='Error parsing TOML:')
    bad('a {\n', 'cj', prefix='Error parsing HCL:')
