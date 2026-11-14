"""Black-box tests for the yq contract in spec.md."""
import os
import subprocess
from pathlib import Path

import pytest

EXE = Path('/workspace/executable')


def run(*args, data=None, cwd=None, env=None):
    return subprocess.run([str(EXE), *map(str, args)], input=data, text=True,
                          capture_output=True, cwd=cwd, env=env, timeout=10)


def ok(p, out=None):
    assert p.returncode == 0, p.stderr
    if out is not None:
        assert p.stdout == out


def test_version_and_root_help():
    p = run('--version')
    ok(p)
    assert p.stdout.startswith('yq (https://github.com/mikefarah/yq/) version v')
    assert p.stdout.endswith('\n')
    p = run('--help')
    ok(p)
    for word in ('Usage:', 'Available Commands:', 'eval', 'eval-all', 'completion'):
        assert word in p.stdout


def test_eval_help_and_aliases():
    p = run('eval', '--help'); ok(p)
    assert 'Evaluate Sequence' in p.stdout and 'yq eval' in p.stdout
    p = run('eval-all', '--help'); ok(p)
    assert 'all' in p.stdout.lower()


def test_format_aliases_and_compact_flags():
    p = run('-n', '-pj', '{"x": 2}')
    ok(p)
    assert 'x' in p.stdout and '2' in p.stdout
    assert p.stderr == 'Flag --tojson has been deprecated, please use -o=json instead\n'
    p = run('-n', '-o=json', '{"x": 2}')
    ok(p, '{\n  "x": 2\n}\n')
    assert p.stderr == ''


def test_unknown_flag_and_format_diagnostics():
    p = run('--invalid-flag-that-does-not-exist')
    assert p.returncode != 0 and p.stderr.startswith('Error: unknown flag: --invalid-flag-that-does-not-exist')
    p = run('-n', '-o=badformat', '.')
    assert p.returncode != 0
    assert p.stderr == "Error: unknown format 'badformat' please use [yaml|y|kyaml|ky|json|j|props|p|csv|c|tsv|t|xml|x|base64|uri|toml|hcl|h|shell|s|lua|l|ini|i]\n"


def test_stdin_null_input_and_expression_file(tmp_path):
    ok(run('.', data='a: apple\n'), 'a: apple\n')
    ok(run('-n', '.apple = "tree"'), 'apple: tree\n')
    expr = tmp_path / 'expr'; expr.write_bytes(b'.a\r\n')
    ok(run('--from-file', expr, data='a: apple\n'), 'apple\n')


def test_null_input_rejects_files_and_empty_input_fallback(tmp_path):
    f = tmp_path / 'data.yml'; f.write_text('a: 1\n')
    p = run('-n', '.', f)
    assert p.returncode != 0 and 'cannot pass files in when using null-input flag' in p.stderr
    ok(run('.', data=''), '\n')
    ok(run('.', data='\n\n'), '\n\n')


def test_version_format_stdin_hcl_equals_flag():
    p = run('eval', '-p=hcl', '-o=yaml', '-', data='a = "apple"\n')
    ok(p, 'a: "apple"\n')


def test_completion_outputs_and_protocol():
    p = run('completion', 'bash'); ok(p)
    assert p.stdout.startswith('# bash completion V2 for yq')
    assert len(p.stdout.splitlines()) > 100 and 'COMPREPLY' in p.stdout and '__complete' in p.stdout
    assert p.stderr == ''
    alias = run('shell-completion', 'bash'); ok(alias, p.stdout)
    z = run('completion', 'zsh'); ok(z)
    assert z.stdout.startswith('#compdef yq\ncompdef _yq yq\n') and '__complete' in z.stdout
    f = run('completion', 'fish'); ok(f)
    assert f.stdout.startswith('# fish completion for yq') and 'commandline' in f.stdout
    pw = run('completion', 'powershell'); ok(pw)
    assert pw.stdout.startswith('# powershell completion for yq') and 'Register-ArgumentCompleter' in pw.stdout
    c = run('__complete', '')
    ok(c, 'completion\tGenerate the autocompletion script for the specified shell\n'
         'eval\t(default) Apply the expression to each document in each yaml file in sequence\n'
         'eval-all\tLoads _all_ yaml documents of _all_ yaml files and runs expression once\n'
         'help\tHelp about any command\n:4\n')
    assert c.stderr == 'Completion ended with directive: ShellCompDirectiveNoFileComp\n'


def test_completion_errors_and_help():
    for args, part in [(('completion',), 'accepts 1 arg(s), received 0'),
                       (('completion','bash','zsh'), 'accepts 1 arg(s), received 2'),
                       (('completion','Bash'), 'invalid argument "Bash"')]:
        p = run(*args); assert p.returncode != 0 and part in p.stderr and 'yq completion [bash|zsh|fish|powershell]' in p.stderr
    p = run('completion', '--help'); ok(p)
    for s in ('Aliases:', 'completion, shell-completion', 'Bash:', 'Zsh:', 'Fish:'):
        assert s in p.stdout


def test_document_and_file_indexes(tmp_path):
    a=tmp_path/'a.yml'; b=tmp_path/'b.yml'
    a.write_text('x: 1\n---\nx: 2\n'); b.write_text('x: 3\n')
    ok(run('documentIndex', a, b), '0\n1\n0\n')
    ok(run('fileIndex', a, b), '0\n0\n1\n')
    ok(run('eval-all', '[.]', a, b), '- x: 1\n- x: 2\n- x: 3\n')


def test_eval_all_merges_all_documents(tmp_path):
    f=tmp_path/'docs.yml'; f.write_text('a: 1\n---\nb: 2\n')
    ok(run('eval-all', '. as $item ireduce ({}; . * $item)', f), 'a: 1\nb: 2\n')


def test_document_separators_and_scalar_streams(tmp_path):
    f=tmp_path/'many.yml'; f.write_text('a: 1\n---\nb: 2\n')
    ok(run('.', f), 'a: 1\n---\nb: 2\n')
    ok(run('-N', '.', f), 'a: 1\nb: 2\n')
    ok(run('-n', '[1, null, 2, null, 3] | .[] | select(. != null)'), '1\n2\n3\n')


def test_error_diagnostics_and_exit_status():
    p=run('bad syntax ][')
    assert p.returncode != 0 and p.stderr == 'Error: 1:1: lexer: invalid input text "bad syntax ]["\n'
    p=run('-n', '-e', 'empty')
    assert p.returncode == 1 and p.stderr == 'Error: no matches found\n'
    p=run('-n', '-e', 'false, true'); assert p.returncode == 0
    p=run('-n', 'error("custom error message")')
    assert p.returncode != 0 and p.stderr == 'Error: custom error message\n' and p.stdout == ''


def test_yaml_identity_updates_and_pretty_print():
    src='"removeQuotes": "please"\narr: [one, two]\n'
    ok(run('-P', '.', data=src), 'removeQuotes: please\narr:\n  - one\n  - two\n')
    ok(run('-n', '.a = ""', data=''), 'a: ""\n')
    ok(run('-I', '0', '.', data='obj:\n  nested:\n    deep: value\n'), 'obj:\n    nested:\n        deep: value\n')


def test_yaml_types_merges_and_tags():
    ok(run('.', data='yes: yes\non: ON\nno: no\ntruth: true\nnum: 0x10\n'),
       'yes: yes\non: ON\nno: no\ntruth: true\nnum: 0x10\n')
    ok(run('.a type', data='a: "12"\n'), '!!str\n')
    ok(run('.a tag = "!!int"', data='a: "12"\n'), 'a: "12"\n')
    ok(run('.service.timeout', data='defaults: &d\n  timeout: 30\nservice:\n  <<: *d\n'), '30\n')


def test_json_roundtrip_precision_and_indent():
    ok(run('-p', 'json', '-o', 'json', '.', data='{"n":9999999999999,"s":"Café"}'),
       '{\n  "n": 9999999999999,\n  "s": "Café"\n}\n')
    ok(run('-n', '-o=json', '-I=0', '{"x": [1, 2]}'), '{"x":[1,2]}\n')


def test_csv_and_tsv_decoding_and_encoding():
    ok(run('-p=csv', '-o=yaml', '.', data='name,count\nAlice,2\nBob,3\n'),
       '- name: Alice\n  count: 2\n- name: Bob\n  count: 3\n')
    ok(run('-p=csv', '-o=csv', '.', data='name,value\nAlice,"a,b"\n'),
       'name,value\nAlice,"a,b"\n')
    ok(run('-n', '-o=csv', '[{"a":"x"},{"a":"y"}]'), 'a\nx\ny\n')


def test_properties_and_ini_conversions():
    ok(run('-p=properties', '-o=yaml', '.', data='port = 5432\nname = hi=there\n'),
       'port: "5432"\nname: hi=there\n')
    ok(run('-n', '-o=properties', '{items: [one, two]}'), 'items.0 = one\nitems.1 = two\n')
    ok(run('-p=ini', '-o=yaml', '.', data='port = 5432\n[server]\nhost = localhost\n'),
       'port: "5432"\nserver:\n  host: localhost\n')
    ok(run('-p=ini', '-o=yaml', '.', data=''), '{}\n')


def test_xml_decode_encode():
    ok(run('-p=xml', '-o=yaml', '.', data='<root><x>a</x><x>b</x></root>\n'),
       'root:\n  x:\n    - a\n    - b\n')
    p=run('-p=xml', '-o=yaml', '.', data='  <?xml version="1.0"?><root><count>42</count></root>')
    ok(p); assert 'count: "42"' in p.stdout
    ok(run('-o=xml', '.', data='hello\n'), 'hello')


def test_toml_hcl_lua_basic_formats():
    ok(run('-p=toml', '-o=yaml', '.', data='title = "app"\ncount = 2\n'), 'title: app\ncount: 2\n')
    ok(run('-p=hcl', '-o=yaml', '-', data='a = "apple"\n'), 'a: "apple"\n')
    ok(run('-p=lua', '-o=yaml', '.', data='return {a = 1, b = true}\n'), 'a: 1\nb: true\n')
    ok(run('-p=lua', '-o=yaml', '.', data='return nil\n'), '\n')


def test_base64_uri_and_sh_decoder_operators():
    ok(run('-o=base64', '.', data='"hello world"\n'), 'aGVsbG8gd29ybGQ=')
    ok(run('-n', '"this has & special () characters *" | @uri'), 'this+has+%26+special+%28%29+characters+%2A\n')
    ok(run('-n', '"aGVsbG8" | @base64d'), 'hello\n')
    ok(run('-n', '"%20+" | @urid'), '  \n')


def test_csv_toml_xml_security_errors():
    p=run('-p=json', '.', data='[{"name": "value"}')
    assert p.returncode != 0 and p.stderr == "Error: bad file '-': json: array of object unexpected end of JSON input\n"
    p=run('-p=xml', '.', data='text<root></root>\n')
    assert p.returncode != 0 and 'invalid XML: Encountered chardata' in p.stderr
    p=run('-p=toml', '.', data='empty =')
    assert p.returncode != 0 and p.stderr == "Error: bad file '-': expected value, not eof\n"


def test_navigation_paths_slices_and_collections():
    ok(run('-n', '[1,2,3,4] | .[-1], .[1:3]'), '4\n---\n- 2\n- 3\n')
    ok(run('.a.b[1] | path', data='a:\n  b:\n    - x\n    - y\n'), '- a\n- b\n- 1\n')
    ok(run('-n', '[5,2,5,1] | unique'), '- 5\n- 2\n- 1\n')
    ok(run('-n', '[1,2,3] | pick([2,0,2])'), '- 3\n- 1\n- 3\n')
    ok(run('-n', '[1,2,3,4] | omit([3,1])'), '- 1\n- 3\n')


def test_arithmetic_boolean_comparison_and_truthiness():
    ok(run('-n', '20 / 2, -10 % 3, "ab" * 3'), '10\n-1\nababab\n')
    ok(run('-n', '0 // "fallback", false // "fallback", "" // "fallback"'), '0\nfallback\n""\n')
    ok(run('-n', '"123" == 123, 0o12 == 0x0A, [1] == [1]'), 'true\nfalse\nfalse\n')
    ok(run('-n', '"abc" | contains("b")'), 'true\n')


def test_length_sort_unique_and_transformations():
    ok(run('-n', '"Café ☕ España" | length'), '17\n')
    ok(run('-n', '[5, 2, 8, 1, 5, 9, 2, 3] | unique'), '- 5\n- 2\n- 8\n- 1\n- 9\n- 3\n')
    ok(run('-n', '[3,1,2] | sort'), '- 1\n- 2\n- 3\n')
    ok(run('-n', '"dogs are great" | sub("dogs"; "cats")'), 'cats are great\n')


def test_entries_reductions_and_mapping_updates():
    ok(run('-n', '{"a": 1, "b": 2} | to_entries | .[0].key'), 'a\n')
    ok(run('-n', 'null | to_entries'), '')
    ok(run('-n', '[1,2,3] | . as $x ireduce (0; . + $x)'), '6\n')
    ok(run('-n', '{"a":1,"b":2} + {"a":3,"c":4}'), 'a: 3\nb: 2\nc: 4\n')


def test_string_split_join_regex_and_env(tmp_path):
    ok(run('-n', '"a,,b," | split(",")'), '- a\n- ""\n- b\n- ""\n')
    ok(run('-n', '[1,true,null] | join(",")'), '1,true,\n')
    ok(run('-n', '"hello world" | match("h(.*?)o")'), 'string: hello\noffset: 0\nlength: 5\ncaptures:\n  - string: ell\n    offset: 1\n    length: 3\n')
    ev=os.environ.copy(); ev['YQ_TEST_VALUE']='42'
    ok(run('-n', 'env("YQ_TEST_VALUE")', env=ev), '42\n')
    ok(run('-n', 'strenv("YQ_TEST_VALUE")', env=ev), '42\n')


def test_environment_security_and_file_load(tmp_path):
    ev=os.environ.copy(); ev['YQ_TEST_VALUE']='secret'
    p=run('--security-disable-env-ops', '-n', 'strenv("YQ_TEST_VALUE")', env=ev)
    assert p.returncode != 0 and 'env operations have been disabled' in p.stderr
    f=tmp_path/'loaded.yml'; f.write_text('a: 1\n')
    ok(run('-n', f'load("{f}") | .a'), '1\n')
    p=run('-n', 'load(.a)'); assert p.returncode != 0 and p.stderr == 'Error: filename expression returned nil\n'
    p=run('--security-disable-file-ops', '-n', f'load("{f}")')
    assert p.returncode != 0 and 'file operations have been disabled' in p.stderr


def test_datetime_and_split_doc():
    ok(run('-n', 'from_unix(0)'), '1970-01-01T00:00:00Z\n')
    ok(run('-n', '"1970-01-01T00:00:00Z" | to_unix'), '0\n')
    ok(run('-n', 'split_doc'), '\n')
    ok(run('-n', '"{\\"a\\":1}" | @jsond'), 'a: 1\n')


def test_node_info_and_large_values():
    p=run('--debug-node-info', '.', data='hello\n'); ok(p)
    for s in ('kind: ScalarNode', "tag: '!!str'", 'value: hello', 'line: 1', 'column: 1'):
        assert s in p.stdout
    large='é'*10000
    ok(run('-n', f'"{large}" | length'), '20000\n')


def test_inplace_split_and_front_matter(tmp_path):
    f=tmp_path/'edit.yml'; f.write_text('a: 1\n')
    p=run('-i', '.a = 2', f); ok(p, '')
    assert f.read_text() == 'a: 2\n'
    p=run('-s', '$index', '.[]', data='[a, b]\n', cwd=tmp_path); ok(p, '')
    assert (tmp_path/'0.yml').read_text() == 'a\n' and (tmp_path/'1.yml').read_text() == 'b\n'
    ok(run('-f', 'extract', '.', data='---\ntitle: My Document\nauthor: Alice\n---\nbody\n'),
       '---\ntitle: My Document\nauthor: Alice\n')
    ok(run('-f', 'extract', '.', data='a: apple\nb: cat\n---\nbody\n'), 'a: apple\nb: cat\n')
