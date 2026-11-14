import json
import os
import re
import subprocess
from pathlib import Path

import pytest


BIN = Path('/workspace/executable')


def invoke(tmp_path, *args):
    return subprocess.run([str(BIN), *map(str, args)], cwd=tmp_path,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def module(tmp_path, files, name='testpkg'):
    (tmp_path / 'go.mod').write_text(f'module {name}\n\ngo 1.22\n')
    for name, body in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    return tmp_path


def basic(tmp_path):
    return module(tmp_path, {'main.go': '''package testpkg
import "encoding/json"
func Bad(v any) error { _, err := json.Marshal(v); return err }
func Good(v any) error { _, err := json.Marshal(v); if err != nil { return wrap(err) }; return nil }
func wrap(error) error { return nil }
func Clean() error { return nil }
'''})


def test_help_is_exact_and_short_circuits(tmp_path):
    p = invoke(tmp_path, '--help', './does-not-exist')
    expected = '''wrapcheck: Checks that errors returned from external packages are wrapped

Usage: wrapcheck [-flag] [package]


Flags:
  -V\tprint version and exit
  -all
    \tno effect (deprecated)
  -c int
    \tdisplay offending line with this many lines of context (default -1)
  -cpuprofile string
    \twrite CPU profile to this file
  -debug string
    \tdebug flags, any subset of "fpstv"
  -diff
    \twith -fix, don't update the files, but print a unified diff
  -fix
    \tapply all suggested fixes
  -flags
    \tprint analyzer flags in JSON
  -json
    \temit JSON output
  -memprofile string
    \twrite memory profile to this file
  -source
    \tno effect (deprecated)
  -tags string
    \tno effect (deprecated)
  -test
    \tindicates whether test files should be analyzed, too (default true)
  -trace string
    \twrite trace log to this file
  -v\tno effect (deprecated)
'''
    assert p.returncode == 0 and p.stdout == b'' and p.stderr.decode() == expected


def test_no_arguments_shows_help_and_fails(tmp_path):
    p = invoke(tmp_path)
    assert p.returncode == 1 and b'Usage: wrapcheck' in p.stderr and not p.stdout


def test_flags_json_exact_inventory_and_no_newline(tmp_path):
    p = invoke(tmp_path, '-flags', '.')
    assert p.returncode == 0 and p.stderr == b'' and p.stdout.endswith(b']') and not p.stdout.endswith(b'\n')
    items = json.loads(p.stdout)
    assert [(x['Name'], x['Bool'], x['Usage']) for x in items] == [
        ('V', True, 'print version and exit'), ('all', True, 'no effect (deprecated)'),
        ('c', False, 'display offending line with this many lines of context'),
        ('diff', True, 'with -fix, don\'t update the files, but print a unified diff'),
        ('flags', True, 'print analyzer flags in JSON'), ('json', True, 'emit JSON output'),
        ('source', True, 'no effect (deprecated)'), ('tags', False, 'no effect (deprecated)'),
        ('test', True, 'indicates whether test files should be analyzed, too'), ('v', True, 'no effect (deprecated)')]
    assert all(set(x) == {'Name', 'Bool', 'Usage'} for x in items)


def test_version_full_and_invalid_values(tmp_path):
    p = invoke(tmp_path, '-V=full', 'not-a-package')
    assert p.returncode == 0 and not p.stderr
    line = p.stdout.decode().strip()
    assert line.startswith(str(BIN) + ' version ') and len(line) > 50
    assert re.search(r'buildID=[0-9a-f]{64}$', line)
    for value in ('true', 'short', 'invalid'):
        q = invoke(tmp_path, '-V=' + value, '.')
        assert q.returncode == 1 and q.stdout == b''
        assert q.stderr.decode() == f'wrapcheck: unsupported flag value: -V={value} (use -V=full)\n'


def test_clean_text_mode_is_silent(tmp_path):
    module(tmp_path, {'main.go': 'package testpkg\nfunc F() error { return nil }\n'})
    p = invoke(tmp_path, '.')
    assert p.returncode == 0 and p.stdout == p.stderr == b''


def test_external_error_text_position_and_canonical_signature(tmp_path):
    basic(tmp_path)
    p = invoke(tmp_path, '.')
    assert p.returncode == 3 and p.stdout == b''
    lines = p.stderr.decode().splitlines()
    assert len(lines) == 1
    assert lines[0] == f'{tmp_path}/main.go:3:59: error returned from external package is unwrapped: sig: func encoding/json.Marshal(v any) ([]byte, error)'


def test_json_output_schema_and_finding_status(tmp_path):
    basic(tmp_path)
    p = invoke(tmp_path, '--json', '.')
    assert p.returncode == 0 and p.stderr == b'' and p.stdout.endswith(b'\n')
    data = json.loads(p.stdout)
    assert list(data) == ['testpkg']
    ds = data['testpkg']['wrapcheck']
    assert len(ds) == 1 and list(ds[0]) == ['posn', 'message']
    assert ds[0]['posn'] == f'{tmp_path}/main.go:3:59'
    assert ds[0]['message'] == 'error returned from external package is unwrapped: sig: func encoding/json.Marshal(v any) ([]byte, error)'


def test_context_includes_requested_source_lines(tmp_path):
    basic(tmp_path)
    p = invoke(tmp_path, '-c=1', '.')
    out = p.stderr.decode().splitlines()
    assert p.returncode == 3 and out[1].startswith('2\t') and out[2].startswith('3\t') and out[3].startswith('4\t')


def test_fix_suppresses_findings_without_modifying_source(tmp_path):
    basic(tmp_path)
    src = tmp_path / 'main.go'
    before = src.read_bytes()
    p = invoke(tmp_path, '-fix', '.')
    assert p.returncode == 0 and not p.stdout and not p.stderr
    assert src.read_bytes() == before
    q = invoke(tmp_path, '-json', '-fix', '.')
    assert q.returncode == 0 and q.stdout == q.stderr == b''


def test_diff_keeps_findings_and_emits_no_patch(tmp_path):
    basic(tmp_path)
    p = invoke(tmp_path, '-diff', '.')
    assert p.returncode == 3 and b'error returned from external package is unwrapped' in p.stderr
    assert not any(x in p.stderr for x in (b'---', b'+++', b'@@'))


def test_reassignment_and_multiple_returns_report_each_error(tmp_path):
    module(tmp_path, {'main.go': '''package testpkg
import ("encoding/json"; "encoding/xml")
func F(v any) error {
  _, e := json.Marshal(v)
  _, e = xml.Marshal(v)
  return e
}
func G(v any) (any, error) { return json.Marshal(v) }
'''})
    p = invoke(tmp_path, '.')
    assert p.returncode == 3
    lines = p.stderr.decode().splitlines()
    assert len(lines) == 2
    assert 'func encoding/xml.Marshal(v any) ([]byte, error)' in lines[0]
    assert 'func encoding/json.Marshal(v any) ([]byte, error)' in lines[1]


def test_interfaces_and_local_interfaces_are_reported(tmp_path):
    module(tmp_path, {'main.go': '''package testpkg
import "io"
type Reader interface { Read([]byte) (int, error) }
func A(r Reader, x io.Reader, b []byte) error { _, e := r.Read(b); return e }
func B(x io.Reader, b []byte) error { _, e := x.Read(b); return e }
'''})
    p = invoke(tmp_path, '-json', '.')
    assert p.returncode == 0
    msgs = [d['message'] for d in json.loads(p.stdout)['testpkg']['wrapcheck']]
    assert len(msgs) == 2
    assert all('error returned from interface method should be wrapped' in x for x in msgs)
    assert any('func (io.Reader).Read(p []byte) (n int, err error)' in x for x in msgs)
    assert any('func (testpkg.Reader).Read([]byte) (int, error)' in x for x in msgs)


def test_configuration_replace_and_extra_filters(tmp_path):
    basic(tmp_path)
    (tmp_path / '.wrapcheck.yaml').write_text('ignoreSigs: []\n')
    p = invoke(tmp_path, '.')
    assert p.returncode == 3 and 'json.Marshal(' in p.stderr.decode()
    (tmp_path / '.wrapcheck.yaml').write_text('ignoreSigs:\n  - json.Marshal(\n')
    q = invoke(tmp_path, '.')
    assert q.returncode == 0 and q.stderr == b''


def test_internal_errors_configuration(tmp_path):
    module(tmp_path, {'main.go': '''package testpkg
func local() error { return nil }
func F() error { e := local(); return e }
'''})
    (tmp_path / '.wrapcheck.yaml').write_text('reportInternalErrors: true\n')
    p = invoke(tmp_path, '.')
    assert p.returncode == 3 and 'package-internal error should be wrapped' in p.stderr.decode()


def test_test_files_default_and_test_false(tmp_path):
    module(tmp_path, {'main.go': 'package testpkg\nfunc Base() {}\n', 'extra_test.go': '''package testpkg
import "encoding/json"
func TestHelper(v any) error { _, err := json.Marshal(v); return err }
'''})
    a = invoke(tmp_path, '.')
    b = invoke(tmp_path, '-test=false', '.')
    assert a.returncode == 3 and 'extra_test.go' in a.stderr.decode()
    assert b.returncode == 0 and not b.stderr


def test_flag_errors_include_usage_and_normalized_name(tmp_path):
    p = invoke(tmp_path, '--nonexistent-flag')
    assert p.returncode == 2 and not p.stdout
    assert b'flag provided but not defined: -nonexistent-flag' in p.stderr
    assert b'Usage: wrapcheck' in p.stderr
    q = invoke(tmp_path, '-c=abc', '.')
    assert q.returncode == 2 and b'invalid value "abc" for flag -c: parse error' in q.stderr


def test_invalid_package_has_loader_failure(tmp_path):
    module(tmp_path, {'main.go': 'package testpkg\nfunc F() { missing() }\n'})
    p = invoke(tmp_path, '.')
    assert p.returncode == 1
    assert b'undefined: missing' in p.stderr and p.stderr.rstrip().endswith(b'wrapcheck: analysis skipped due to errors in package')


def test_invalid_regexp_and_glob_fail_before_analysis(tmp_path):
    basic(tmp_path)
    (tmp_path / '.wrapcheck.yaml').write_text('ignoreSigRegexps:\n  - "["\n')
    p = invoke(tmp_path, '.')
    assert p.returncode == 1 and not p.stdout and b'unable to compile regexp [' in p.stderr
    (tmp_path / '.wrapcheck.yaml').write_text('ignorePackageGlobs:\n  - "["\n')
    q = invoke(tmp_path, '.')
    assert q.returncode == 1 and not q.stdout
    assert q.stderr == b'wrapcheck: unable to compile globs %!s(<nil>): unexpected end of input\n\n'


def test_profile_flags_create_nonempty_artifacts_and_keep_json_valid(tmp_path):
    basic(tmp_path)
    paths = [tmp_path / 'cpu.prof', tmp_path / 'mem.prof', tmp_path / 'trace.out']
    args = ['-cpuprofile', paths[0], '-memprofile', paths[1], '-trace', paths[2], '-json', '.']
    p = invoke(tmp_path, *args)
    assert p.returncode == 0 and json.loads(p.stdout)
    assert all(x.is_file() and x.stat().st_size > 100 for x in paths)
    assert b'To view the trace, run:' in p.stderr and str(paths[2]).encode() in p.stderr
