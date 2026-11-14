import json
import os
import pathlib
import re
import subprocess
import tempfile

import pytest

EXE = pathlib.Path('/workspace/executable')


def run(*args, input=b'', cwd=None, env=None):
    e = os.environ.copy()
    # Make outcomes independent of a caller's environment unless a test opts in.
    e.pop('USER', None)
    e.pop('GOMPLATE_CONFIG', None)
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *map(str, args)], input=input, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=cwd, env=e, timeout=20)


def rendered(template, *args, **kw):
    return run('-i', template, *args, **kw)


def ok(p, out):
    assert p.returncode == 0, p.stderr
    assert p.stdout == out
    assert p.stderr == b''


def err(p, fragment):
    assert p.returncode != 0
    assert fragment.encode() in p.stderr


def test_cli_version_and_help():
    p = run('--version')
    ok(p, b'gomplate version 0.0.0\n')
    p = run('--help')
    assert p.returncode == 0 and p.stderr == b''
    assert p.stdout.startswith(b'Process text files with Go templates\n\nUsage:')
    assert b'Available Commands:' not in p.stdout


def test_cli_unknown_and_verbose():
    p = run('--unknown-argument')
    assert p.returncode == 1 and b'Usage:' in p.stdout
    assert b'Error: unknown flag: --unknown-argument' in p.stderr
    p = rendered('plain', '-V')
    assert p.returncode == 0 and p.stdout == b'plain' and p.stderr


def test_stdin_inline_delimiters_and_whitespace_suppression():
    ok(run(input=b'  \n\t'), b'')
    ok(run(input='a\r\n雪\n'.encode()), 'a\r\n雪\n'.encode())
    ok(rendered('x={{ 1 | printf "%d" }}'), b'x=1')
    ok(rendered('{{ .Env.TEST_VALUE }}', env={'TEST_VALUE': 'works'}), b'works')
    ok(rendered('<< 3 >>', '--left-delim', '<<', '--right-delim', '>>'), b'3')
    ok(rendered('{{ 2 }}', '--left-delim', '<<', '--right-delim', '>>'), b'{{ 2 }}')


def test_template_runtime_failure_is_json_and_streams_prefix():
    p = rendered('Hello {{ .Env.USER }}')
    err(p, '"level":"ERROR"')
    assert b'"err"' in p.stderr and p.stdout == b'Hello '
    assert json.loads(p.stderr.splitlines()[-1])['level'] == 'ERROR'
    p = rendered('{{ range .Items }}x')
    err(p, 'parse template')


def test_missing_key_modes_and_root():
    ok(rendered('{{.}}'), b'map[]')
    err(rendered('{{ .Missing }}'), 'map has no entry for key')
    ok(rendered('{{ .Missing }}', '--missing-key', 'default'), b'<no value>')
    ok(rendered('{{ .Missing }}', '--missing-key', 'invalid'), b'<no value>')
    ok(rendered('{{ .Missing }}', '--missing-key', 'zero'), b'')
    err(rendered('x', '--missing-key', 'ERROR'), 'not allowed value for the')


def test_template_control_scope_and_builtin_formatting():
    ok(rendered('{{range $i, $v := (coll.Slice "a" "b")}}{{$i}}:{{$v}};{{end}}'), b'0:a;1:b;')
    ok(rendered('{{if and true (not false)}}yes{{else}}no{{end}}|{{printf "%T" 4}}'), b'yes|int')
    ok(rendered('{{define "part"}}ok{{end}}{{template "part" .}}'), b'ok')
    err(rendered('{{ invalid_func }}'), 'function "invalid_func" not defined')


def test_file_pairing_modes_permissions_and_empty_output(tmp_path):
    src = tmp_path / 'in.t'; src.write_text('hey')
    os.chmod(src, 0o640)
    out = tmp_path / 'nested' / 'out'
    p = run('-f', src, '-o', out)
    assert p.returncode == 0 and out.read_bytes() == b'hey'
    assert out.stat().st_mode & 0o777 == 0o640
    absent = tmp_path / 'empty'
    (tmp_path / 'blank').write_text('')
    p = run('-f', tmp_path / 'blank', '-o', absent)
    assert p.returncode == 0 and not absent.exists()
    err(run('-f', src, '-f', src, '-o', out), 'failed to validate config')


def test_output_map_directory_selection_and_copy(tmp_path):
    root = tmp_path / 'src'; root.mkdir(); (root / 'a.t').write_text('A={{2}}')
    (root / 'b.txt').write_text('raw {{2}}')
    dest = tmp_path / 'dest'
    p = run('--input-dir', root, '--output-dir', dest, '--include', '*.t')
    assert p.returncode == 0 and (dest / 'a.t').read_bytes() == b'A=2'
    assert not (dest / 'b.txt').exists()
    p = run('--input-dir', root, '--output-dir', dest, '--exclude-processing', '*.txt')
    assert p.returncode == 0 and (dest / 'b.txt').read_bytes() == b'raw {{2}}'
    err(run('--input-dir', root, '--output-map', '{{invalid_func}}'), 'outFileNamer')


def test_config_yaml_precedence_and_disabled_discovery(tmp_path):
    (tmp_path / '.gomplate.yaml').write_text('in: configured\n')
    p = run(cwd=tmp_path, env={'GOMPLATE_CONFIG': ''})
    # stdin is empty because disabling config means the default stdin template.
    ok(p, b'')
    (tmp_path / 'bad.yaml').write_text('x: [\n')
    err(run('--config', tmp_path / 'bad.yaml', '-i', 'x', cwd=tmp_path), 'parsing config file')
    p = run('--config=', '-i', 'cli', cwd=tmp_path)
    ok(p, b'cli')


def test_datasource_context_and_parsers(tmp_path):
    (tmp_path / 'd.json').write_text('{"name":"N","n":3}')
    p = run('-d', 'd=d.json', '-i', '{{(ds "d").name}}|{{(ds "d").n}}', cwd=tmp_path)
    ok(p, b'N|3')
    p = rendered('{{json `{"a":1}` | index "a"}}|{{yaml "x: yes" | index "x"}}')
    assert p.returncode == 0 and p.stdout.startswith(b'1|')
    err(rendered('{{ data.YAML "key: value\n  bad_indent: value" }}'), 'error calling YAML')


def test_serializers_collections_and_jq():
    ok(rendered('{{dict "b" 2 "a" 1 | json}}'), b'{"a":1,"b":2}')
    ok(rendered('{{coll.Keys (dict "b" 2 "a" 1)}}'), b'[a b]')
    ok(rendered('{{coll.Slice 1 2 2 | uniq | reverse}}'), b'[2 1]')
    ok(rendered('{{coll.Merge (dict "a" 1) (dict "a" 2 "b" 3) | json}}'), b'{"a":1,"b":3}')
    ok(rendered('{{jq ".x + 1" (dict "x" 4)}}'), b'5')
    err(rendered('{{jq "[invalid syntax" (coll.Slice)}}'), 'jq parsing expression')


def test_environment_conversion_and_math():
    ok(rendered('{{getenv "EVAL_X" "d"}}|{{env.HasEnv "EVAL_EMPTY"}}', env={'EVAL_X':'v','EVAL_EMPTY':''}), b'v|true')
    ok(rendered('{{conv.ToBools true 1 "yes" 42}}'), b'[true true true false]')
    ok(rendered('{{conv.ToInts 1 2.5 "3"}}|{{math.Div 10 4}}|{{seq 4 2}}'), b'[1 2 3]|2.5|[1 2 3 4]')
    err(rendered('{{conv.Atoi "x"}}'), 'invalid syntax')
    err(rendered('{{math.Div 10 0}}'), 'division by 0')


def test_strings_regex_paths_and_files(tmp_path):
    ok(rendered('{{strings.Slug "Hellö, Wôrld! Free @ last"}}|{{strings.Split "," "a,,b"}}'), b'hello-world-free-at-last|[a  b]')
    ok(rendered('{{regexp.Replace "([a-z]+)" "<$1>" "ab cd"}}'), b'<ab> <cd>')
    err(rendered('{{regexp.Find "[" "x"}}'), 'error calling Find')
    ok(rendered('{{path.Join "a" "../b"}}|{{filepath.Ext "x.tar.gz"}}'), b'b|.gz')
    (tmp_path / 'f').write_bytes(b'abc')
    ok(rendered('{{file.Read "f"}}', cwd=tmp_path), b'abc')
    err(rendered('{{file.Write "../escape" "x"}}', cwd=tmp_path), 'not contained by working directory')


def test_time_random_base64_and_crypto():
    ok(rendered('{{(time.Unix 0).Format "2006-01-02"}}'), b'1970-01-01')
    ok(rendered('{{base64.Encode "hello"}}|{{base64.Decode "aGVsbG8="}}'), b'aGVsbG8=|hello')
    err(rendered('{{base64.Decode "aGVsbG8"}}'), 'illegal base64 data')
    ok(rendered('{{crypto.SHA256 "abc"}}'), b'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
    ok(rendered('{{len (random.Alpha 20)}}|{{random.Number 4 4}}'), b'20|4')


def test_network_uuid_semver_and_validation():
    ok(rendered('{{net.ParseAddr "::ffff:192.168.1.1"}}'), b'::ffff:192.168.1.1')
    ok(rendered('{{net.LookupIPs "localhost"}}'), b'[127.0.0.1]')
    ok(rendered('{{uuid.Nil}}|{{uuid.IsValid "550e8400-e29b-41d4-a716-446655440000"}}'), b'00000000-0000-0000-0000-000000000000|true')
    ok(rendered('{{semver.Semver "1.2"}}'), b'1.2.0')
    ok(rendered('{{test.Ternary "yes" "no" true}}|{{test.Kind 2}}'), b'yes|int')
    err(rendered('{{test.Assert "no" false}}'), 'assertion failed: no')


def test_experimental_cidr_and_metadata_defaults():
    err(rendered('{{net.CIDRHost 1 "192.168.1.0/24"}}'), 'experimental function')
    ok(rendered('{{net.CIDRHost 1 "192.168.1.0/24"}}', '--experimental'), b'192.168.1.1')
    ok(rendered('{{aws.EC2Meta "x" "d"}}', env={'AWS_TIMEOUT':'5'}), b'd')
    err(rendered('{{gcp.Meta "x" "d"}}', env={'GCP_TIMEOUT':' 100 '}), 'panic: invalid GCP_TIMEOUT')
