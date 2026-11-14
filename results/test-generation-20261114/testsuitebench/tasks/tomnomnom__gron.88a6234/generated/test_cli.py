import json
import os
import pathlib
import subprocess
import tempfile

EVAL = pathlib.Path(__file__).resolve().parent
EXE = pathlib.Path('/workspace/executable')


def run(args=(), data='', *, env=None, timeout=30, input_bytes=None):
    e = os.environ.copy()
    e.update({'NO_COLOR': '1'})
    if env:
        e.update(env)
    raw = data.encode() if input_bytes is None else input_bytes
    return subprocess.run([str(EXE), *map(str, args)], input=raw, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=e, timeout=timeout)


def out(p):
    return p.stdout.decode('utf-8', 'replace')


def err(p):
    return p.stderr.decode('utf-8', 'replace')


def test_version_and_help():
    p = run(['--version'])
    assert (p.returncode, p.stdout, p.stderr) == (0, b'gron version dev\n', b'')
    p = run(['--help'], timeout=2)
    assert p.returncode == 0
    assert all(x in err(p) for x in ('Transform JSON', 'gron [OPTIONS]', '--ungron'))


def test_forward_nested_exact_and_trailing_newline():
    p = run(['-m'], '{"x":{"y":[1,2]},"empty":{}}')
    assert p.returncode == 0
    assert out(p) == ('json = {};\njson.empty = {};\njson.x = {};\njson.x.y = [];\n'
                      'json.x.y[0] = 1;\njson.x.y[1] = 2;\n')


@__import__('pytest').mark.parametrize('value,statement', [
    ('"just a string"', 'json = "just a string";\n'),
    ('42', 'json = 42;\n'), ('true', 'json = true;\n'), ('null', 'json = null;\n'),
    ('{}', 'json = {};\n'), ('[]', 'json = [];\n')], ids=['string','number','bool','null','object','array'])
def test_forward_root_types(value, statement):
    p = run(['-m'], value)
    assert p.returncode == 0 and out(p) == statement


def test_paths_reserved_and_escaped_keys():
    obj = {'_under_scores': 1, 'ಠ_ಠ': 2, 'class': 3, '123': 4, '': 5,
           'has.dot': 6, 'key"with"quotes': 7, 'key\\with\\backslashes': 8,
           'white space': 9, 'if': 10}
    p = run(['-m'], json.dumps(obj, ensure_ascii=False))
    s = out(p)
    for path in ('json._under_scores', 'json.ಠ_ಠ', 'json["class"]', 'json["123"]',
                 'json[""]', 'json["has.dot"]', 'json["key\\"with\\"quotes"]',
                 'json["key\\\\with\\\\backslashes"]', 'json["white space"]', 'json["if"]'):
        assert path + ' = ' in s


def test_unicode_controls_and_separators():
    p = run(['-m'], json.dumps({'日本': 'مرحبا Кириллица 😀\n\t\u2028\u2029'}, ensure_ascii=False))
    s = out(p)
    assert '日本' in s and 'مرحبا Кириллица 😀' in s
    assert '\\n\\t\\u2028\\u2029' in s
    assert '\x1b' not in s


def test_number_lexemes_preserved():
    text = '{"large":999999999999.999999,"small":0.0000000001,"scientific":1.23e10,"neg":-5.6e-7,"precise":3.141592653589793}'
    s = out(run(['-m'], text))
    for n in ('999999999999.999999', '0.0000000001', '1.23e10', '-5.6e-7', '3.141592653589793'):
        assert n in s


def test_sorted_paths_and_numeric_array_indices():
    p = run(['-m'], '{"key2":0,"key10":0,"z":0,"a":0,"three-b":0,"two":0,"arr":[0,0,0,0,0,0,0,0,0,0,0]}')
    lines = out(p).splitlines()
    assert lines[0] == 'json = {};'
    positions = {v: lines.index(v) for v in ('json.a = 0;', 'json.missing = 0;') if v in lines}
    assert lines.index('json.a = 0;') < lines.index('json.z = 0;')
    assert lines.index('json.key10 = 0;') < lines.index('json.key2 = 0;')
    indices = [lines.index(f'json.arr[{i}] = 0;') for i in range(11)]
    assert indices == sorted(indices)
    assert lines.index('json.two = 0;') < lines.index('json["three-b"] = 0;')


def test_no_sort_retains_parent_before_children():
    p = run(['-m', '--no-sort'], '{"z":{"child":1},"a":2}')
    lines = out(p).splitlines()
    assert p.returncode == 0 and lines[0] == 'json = {};'
    assert lines.index('json.z = {};') < lines.index('json.z.child = 1;')
    assert set(lines) == {'json = {};', 'json.z = {};', 'json.z.child = 1;', 'json.a = 2;'}


def test_option_operand_first_file_and_ignore_extra():
    with tempfile.TemporaryDirectory(dir=EVAL) as d:
        f = pathlib.Path(d) / 'in.json'
        f.write_text('{"f":1}')
        p = run(['-m', f, 'does-not-exist'])
    assert p.returncode == 0 and 'json.f = 1;\n' in out(p)


def test_json_path_value_exact_and_roundtrip():
    p = run(['-j'], '{"a":1,"nested":{"items":[true,null]}}')
    assert p.returncode == 0
    assert out(p) == ('[[],{}]\n[["a"],1]\n[["nested"],{}]\n[["nested","items"],[]]\n'
                      '[["nested","items",0],true]\n[["nested","items",1],null]\n')
    q = run(['-u','-j'], out(p))
    assert q.returncode == 0 and json.loads(out(q)) == {'a':1,'nested':{'items':[True,None]}}


def test_json_mode_empty_roots_and_unicode():
    assert out(run(['-j'], '{}')) == '[[],{}]\n'
    assert out(run(['-j'], '[]')) == '[[],[]]\n'
    p = run(['-j'], '{"😀":"日本\n"}')
    assert '😀' in out(p) and '日本' in out(p) and '\\n' in out(p)


def test_stream_mixed_records_and_empty_input():
    p = run(['-m','-s'], '{"a":1}\n{"b":2}\n')
    assert p.returncode == 0
    assert out(p) == 'json = [];\njson[0] = {};\njson[0].a = 1;\njson[1] = {};\njson[1].b = 2;\n'
    q = run(['-s'], '')
    assert q.returncode == 0 and out(q) == 'json = [];\n'


def test_stream_json_mode_and_primitives():
    p = run(['-s','-j'], '1\n"x"\nfalse\nnull\n[]\n')
    assert p.returncode == 0
    assert out(p) == '[[],[]]\n[[0],1]\n[[1],"x"]\n[[2],false]\n[[3],null]\n[[4],[]]\n'


@__import__('pytest').mark.parametrize('contents', ['\n{"b":2}', '{"a":1}\n  \n{"b":2}', '{"a":1}\ninvalid json here\n{"b":2}'], ids=['leading-blank','middle-blank','malformed'])
def test_stream_stops_at_first_bad_record(contents):
    p = run(['-s','-m'], contents)
    assert p.returncode == 3
    assert out(p).startswith('json = [];\n')
    assert 'json[1]' not in out(p) if contents.startswith('{') else 'json[0]' not in out(p)
    assert err(p).startswith('failed to form statements: ')


def test_stream_1000_records():
    data = ''.join(f'{i}\n' for i in range(1000))
    p = run(['-s','-j'], data, timeout=45)
    assert p.returncode == 0
    lines = out(p).splitlines()
    assert len(lines) == 1001 and lines[1] == '[[0],0]' and lines[-1] == '[[999],999]'


def test_values_scalars_and_ignores_containers_noise():
    src = 'json = {};\nnoise\njson.a = "hello";\njson[0] = 42;\njson.b = true;\njson.c = null;\njson.d = [];\n'
    p = run(['-v'], src)
    assert p.returncode == 0 and out(p) == 'hello\n42\ntrue\nnull\n'


def test_values_empty_and_decoded_string_lines():
    p = run(['-v'], 'json.a = "";\njson.b = "a\\nb";\njson.c = 1e10;\n')
    assert p.returncode == 0 and out(p) == '\na\nb\n1e10\n'


def test_values_invalid_records_and_empty_record_error():
    for source in ('noise\n', 'json.a = [;\n'):
        p = run(['-v'], source)
        assert p.returncode == 0 and not p.stdout and not p.stderr
    p = run(['-v'], '\n')
    assert p.returncode == 5 and err(p) == "failed to parse '' as gron statement\n"


def test_reverse_pretty_sorted_and_roundtrip_types():
    src = 'json = {};\njson.z = "日本";\njson.bool_false = false;\njson.empty_array = [];\njson.name = "test";\njson.nested = {};\njson.nested.value = 123;\n'
    p = run(['-u'], src)
    assert p.returncode == 0
    assert out(p) == '{\n  "bool_false": false,\n  "empty_array": [],\n  "name": "test",\n  "nested": {\n    "value": 123\n  },\n  "z": "日本"\n}\n'


def test_reverse_infers_ancestors_and_sparse_arrays():
    p = run(['-u'], 'json.users[0].email = "alice@example.com";\n')
    assert p.returncode == 0 and json.loads(out(p)) == {'users':[{'email':'alice@example.com'}]}
    p = run(['-u'], 'json = [];\njson[5] = "value";\n')
    assert json.loads(out(p)) == [None,None,None,None,None,'value']


def test_reverse_last_wins_and_container_redeclarations_merge():
    src = 'json = {};\njson.x = 1;\njson.x = {};\njson.x.sub = 2;\njson = {};\njson.y = 3;\n'
    p = run(['-u'], src)
    assert p.returncode == 0 and json.loads(out(p)) == {'x':{'sub':2},'y':3}
    p = run(['-u'], 'json = [];\njson[0] = 1;\njson = [];\njson[1] = 2;\n')
    assert p.returncode == 0 and json.loads(out(p)) == [1,2]


def test_reverse_json_records_without_ancestor_markers():
    p = run(['-u','-j'], '[["a",0],1]\n[["a",1],2]\n')
    assert p.returncode == 0 and json.loads(out(p)) == {'a':[1,2]}


def test_reverse_noise_and_combined_stream_option():
    p = run(['-u'], '--\nrandom noise\njson = {};\njson.a = 1;\n')
    assert p.returncode == 0 and json.loads(out(p)) == {'a':1}
    for args in (['-s','-u'], ['-u','-s'], ['--stream','--ungron']):
        q = run(args, 'json = {};\n')
        assert q.returncode == 0 and out(q) == '{}\n'


def test_reverse_json_layout_errors_and_empty_input():
    for src, diagnostic in (('[ ["a"], 1, "extra" ]\n','invalid JSON layout'),
                            ('["string_not_array", 123]\n','invalid JSON layout')):
        p = run(['-u'], src)
        assert p.returncode == 5 and not p.stdout and diagnostic in err(p)
    for src in ('', ' \t\n'):
        p = run(['-u'], src)
        assert p.returncode == 5 and not p.stdout and err(p) == 'no statements were parsed\n'


@__import__('pytest').mark.parametrize('src,fragment', [
    ('json.a = 1\n','statement has no value'),
    ('json.likes = [;\n','invalid value'),
    ('json.123invalid = 1;\n','invalid statement'),
    ('json[abc] = "test";\n','invalid statement'),
    ('json[-1] = 1;\n','invalid statement'),
    ('json["\\q"] = 1;\n','invalid quoted key'),
], ids=['semicolon','value','identifier','bracket','negative-index','escaped-key'])
def test_reverse_bad_statements_are_fatal(src, fragment):
    p = run(['-u'], src)
    assert p.returncode == 5 and fragment in err(p)


def test_reverse_container_type_conflicts():
    p = run(['-u'], 'json = {};\njson = [];\n')
    assert p.returncode == 5 and 'failed to merge statements: cannot merge object with non-object' in err(p)
    p = run(['-u'], 'json = [];\njson = {};\n')
    assert p.returncode == 5 and 'failed to merge statements: cannot merge array with non-array' in err(p)


def test_reverse_number_lexemes_and_deep_statements():
    src = 'json = {};\njson.a = 9007199254740991;\njson.b = 0.123456789012345;\njson.c = 1.5e-5;\njson.d = 1.23e10;\njson.e = -0;\n'
    p = run(['-u'], src)
    assert p.returncode == 0
    for n in ('9007199254740991','0.123456789012345','1.5e-5','1.23e10','-0'):
        assert n in out(p)
    path = 'json' + '.x' * 50
    q = run(['-u'], f'{path} = 1;\n')
    assert q.returncode == 0


def test_symlink_basename_ungron():
    link = EVAL / 'ungron'
    try:
        link.symlink_to(EXE)
        p = subprocess.run([str(link)], input=b'json = {};\njson.a = 1;\n', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    finally:
        link.unlink(missing_ok=True)
    assert p.returncode == 0 and json.loads(out(p)) == {'a':1}


def test_forward_errors_and_missing_file():
    p = run([], '{invalid json}')
    assert p.returncode == 3 and err(p) == "failed to form statements: invalid character 'i' looking for beginning of object key string\n"
    p = run([], '')
    assert p.returncode == 3 and err(p) == 'failed to form statements: EOF\n'
    p = run([], '{"a":1,')
    assert p.returncode == 3 and err(p) == 'failed to form statements: unexpected EOF\n'
    p = run(['/no/such/eval-file'])
    assert p.returncode == 1 and 'no such file or directory' in err(p).lower()


def test_color_forced_and_mono_precedence():
    plain = run(['-m','-c'], '{"test":1}')
    expected = '\x1b[34;1mjson\x1b[0;22m = \x1b[35m{}\x1b[0m;\n\x1b[34;1mjson\x1b[0;22m.\x1b[34;1mtest\x1b[0;22m = \x1b[31m1\x1b[0m;\n'
    assert plain.returncode == 0 and out(plain) == expected
    p = run(['-m'], '{"test":1}')
    assert p.returncode == 0 and '\x1b[' not in out(p)


def test_large_statement_and_stream_line_limits():
    value = 'x' * 100000
    p = run(['-u'], 'json.a = ' + json.dumps(value) + ';\n', timeout=30)
    assert p.returncode == 0 and len(json.loads(out(p))['a']) == 100000
    big = json.dumps({'x':'y' * 500000})
    p = run(['-s','-j'], big + '\n', timeout=35)
    assert p.returncode == 0 and len(out(p)) > 500000
