import json
import os
import pathlib
import subprocess
import textwrap

import pytest


BIN = pathlib.Path('/workspace/executable')


def invoke(args=(), cwd=None, stdin=None, env=None):
    return subprocess.run([str(BIN), *map(str, args)], cwd=cwd, input=stdin,
                          text=True, capture_output=True, env=env, timeout=20)


@pytest.fixture
def project(tmp_path):
    (tmp_path / 'rules').mkdir()
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'sgconfig.yml').write_text(
        f'ruleDirs:\n- {tmp_path / "rules"}\ntestConfigs:\n- testDir: {tmp_path / "tests"}\n', encoding='utf8')
    return tmp_path


def rule(path, body, rid='r', language='JavaScript', **fields):
    data = {'id': rid, 'language': language, 'message': 'msg', 'severity': 'warning', 'rule': body}
    data.update(fields)
    # JSON flow mappings are valid YAML and safely quote arbitrary values.
    path.write_text(json.dumps(data), encoding='utf8')


def test_version_and_help_are_available_without_project(tmp_path):
    v = invoke(['--version'], tmp_path)
    assert v.returncode == 0 and v.stdout.strip() == 'ast-grep 0.42.1'
    h = invoke(['--help'], tmp_path)
    assert h.returncode == 0 and all(x in h.stdout for x in ['run', 'scan', 'test', 'new', 'lsp', 'completions', 'help'])


def test_no_arguments_is_full_help_on_stderr(tmp_path):
    r = invoke([], tmp_path)
    assert r.returncode == 2 and not r.stdout
    assert r.stderr.startswith('Search and Rewrite code at large scale using precise AST pattern\n\nUsage: executable')
    assert "For more information" not in r.stderr


def test_run_structural_metavariables_and_json_ranges(tmp_path):
    f = tmp_path / 'a.js'
    f.write_text('const π = 1;\nconsole.log(π);\nconsole.log(2, 3);\n', encoding='utf8')
    r = invoke(['run', '-p', 'console.log($X)', '-l', 'js', '--json=compact', f], tmp_path)
    assert r.returncode == 0
    rows = json.loads(r.stdout)
    assert [x['text'] for x in rows] == ['console.log(π)']
    assert rows[0]['language'] == 'JavaScript'
    assert rows[0]['metaVariables']['single']['X']['text'] == 'π'
    assert rows[0]['range']['byteOffset']['start'] == len('const π = 1;\n'.encode())


def test_run_no_match_json_modes(tmp_path):
    f = tmp_path / 'a.js'; f.write_text('foo();')
    p = invoke(['run', '-p', 'bar()', '-l', 'js', '--json=compact', f], tmp_path)
    assert p.returncode == 1 and json.loads(p.stdout) == []
    s = invoke(['run', '-p', 'bar()', '-l', 'js', '--json=stream', f], tmp_path)
    assert s.returncode == 1 and s.stdout == ''


def test_run_exact_structure_and_nested_search(tmp_path):
    f = tmp_path / 'a.js'; f.write_text('function f(){ if (x) { target(1); } } target(1, 2);')
    yes = invoke(['-p', 'target($X)', '-l', 'js', '--json=compact', f], tmp_path)
    assert yes.returncode == 0 and len(json.loads(yes.stdout)) == 1
    no = invoke(['-p', 'target(1)', '-l', 'js', f], tmp_path)
    assert no.returncode == 1


def test_run_language_inference_and_aliases(tmp_path):
    f = tmp_path / 'a.py'; f.write_text('print(1)')
    r = invoke(['-p', 'print($X)', '--json=compact', f], tmp_path)
    assert r.returncode == 0 and json.loads(r.stdout)[0]['language'] == 'Python'


def test_run_stdin_requires_language_and_accepts_python(tmp_path):
    missing = invoke(['run', '--stdin', '-p', 'f()'], tmp_path, 'f()')
    assert missing.returncode == 2
    got = invoke(['run', '--stdin', '-l', 'py', '-p', 'print($X)', '--json=compact'], tmp_path, 'print(7)')
    assert got.returncode == 0 and json.loads(got.stdout)[0]['metaVariables']['single']['X']['text'] == '7'


def test_run_strictness_smart_vs_cst(tmp_path):
    f = tmp_path / 'a.js'; f.write_text('foo(a,);')
    smart = invoke(['-p', 'foo(a)', '-l', 'js', f], tmp_path)
    cst = invoke(['-p', 'foo(a)', '-l', 'js', '--strictness', 'cst', f], tmp_path)
    assert smart.returncode == 0 and cst.returncode == 1


def test_run_rewrite_update_all(tmp_path):
    f = tmp_path / 'a.js'; f.write_text('f(1);\n')
    r = invoke(['run', '-p', 'f($X)', '-r', 'g($X)', '-U', '-l', 'js', f], tmp_path)
    assert r.returncode == 0 and f.read_text() == 'g(1);\n' and 'Applied 1 changes' in r.stderr


def test_scan_rule_and_json_metadata(tmp_path):
    f = tmp_path / 'a.js'; f.write_text('console.log(1);')
    rule(tmp_path / 'rules' / 'r.yml', {'pattern': 'console.log($X)'}, metadata={'x': 2})
    r = invoke(['scan', '--json', '--include-metadata', f], tmp_path)
    assert r.returncode == 0
    obj = json.loads(r.stdout.splitlines()[0])[0]
    assert obj['ruleId'] == 'r' and obj['metadata'] == {'x': 2}


def test_scan_inline_rule_without_id_keeps_empty_id(tmp_path):
    f = tmp_path / 'a.js'; f.write_text('foo();')
    doc = 'language: JavaScript\nrule:\n  pattern: foo()\n'
    r = invoke(['scan', '--inline-rules', doc, '--json', f], tmp_path)
    assert r.returncode == 0 and json.loads(r.stdout.splitlines()[0])[0]['ruleId'] == ''


def test_scan_multiple_yaml_documents_and_severity_exit(tmp_path):
    f = tmp_path / 'a.js'; f.write_text('one(); two();')
    docs = 'language: JavaScript\nseverity: error\nrule:\n  pattern: one()\n---\nlanguage: JavaScript\nseverity: warning\nrule:\n  pattern: two()\n'
    r = invoke(['scan', '--inline-rules', docs, '--json', f], tmp_path)
    assert r.returncode == 1 and [x['text'] for x in json.loads(r.stdout.splitlines()[0])] == ['one()', 'two()']


def test_scan_no_project_and_rule_file_mode(tmp_path):
    no = invoke(['scan'], tmp_path)
    assert no.returncode == 3 and 'No ast-grep project configuration' in no.stderr
    f = tmp_path / 'a.js'; f.write_text('foo()')
    rf = tmp_path / 'only.yml'; rule(rf, {'pattern': 'foo()'})
    yes = invoke(['scan', '--rule', rf, f], tmp_path)
    assert yes.returncode == 0


def test_scan_file_allow_and_ignore_globs(project):
    (project / 'a.js').write_text('foo()')
    (project / 'skip.test.js').write_text('foo()')
    rule(project / 'rules' / 'r.yml', {'pattern': 'foo()'}, files=['**/*.js'], ignores=['**/*.test.js'])
    r = invoke(['scan', '--json'], project)
    assert r.returncode == 0 and len(json.loads(r.stdout.splitlines()[0])) == 1


def test_scan_sarif_and_github_formats(tmp_path):
    f = tmp_path / 'a.js'; f.write_text('foo()')
    rf = tmp_path / 'r.yml'; rule(rf, {'pattern': 'foo()'}, rid='r', severity='error')
    sarif = invoke(['scan', '--rule', rf, '--format', 'sarif', f], tmp_path)
    assert sarif.returncode == 1 and json.loads(sarif.stdout)['version'] == '0.42.1'
    gh = invoke(['scan', '--rule', rf, '--format', 'github', f], tmp_path)
    assert gh.returncode == 1 and '::error file=' in gh.stdout


def test_debug_query_formats(tmp_path):
    r = invoke(['-p', 'f($X)', '-l', 'js', '--debug-query=pattern', '--stdin'], tmp_path, '')
    assert r.returncode == 1 and 'Debug Pattern:' in r.stderr and 'MetaVar $X' in r.stderr
    a = invoke(['-p', 'f()', '-l', 'js', '--debug-query=sexp', '--stdin'], tmp_path, '')
    assert 'Debug Sexp:' in a.stderr


def test_completions_shell_and_help(tmp_path):
    r = invoke(['completions', 'bash'], tmp_path)
    assert r.returncode == 0 and len(r.stdout) > 100 and 'executable' in r.stdout
    h = invoke(['completions', '--help'], tmp_path)
    assert h.returncode == 0 and 'Usage: executable completions' in h.stdout


def test_argument_errors_for_invalid_language_and_style(tmp_path):
    bad = invoke(['run', '-p', 'f()', '-l', 'invalid', '--stdin'], tmp_path, '')
    assert bad.returncode == 2 and 'invalid is not supported!' in bad.stderr
    js = invoke(['run', '-p', 'foo', '-l', 'js', '--json=invalid'], tmp_path)
    assert js.returncode == 2 and "invalid value 'invalid'" in js.stderr and not js.stdout


def test_run_context_and_files_with_matches(tmp_path):
    (tmp_path / 'a.js').write_text('foo();\nbar();\n')
    (tmp_path / 'b.js').write_text('foo();')
    r = invoke(['run', '-p', 'foo()', '-l', 'js', '--files-with-matches', tmp_path], tmp_path)
    assert r.returncode == 0 and len(r.stdout.strip().splitlines()) == 2


def test_test_runner_updates_snapshot_and_passes(project):
    rule(project / 'rules' / 'r.yml', {'pattern': 'foo()'}, rid='r', fix='bar()')
    (project / 'tests' / 'r-test.yml').write_text('id: r\nvalid:\n- "bar()"\ninvalid:\n- "foo()"\n')
    update = invoke(['test', '-U'], project)
    assert update.returncode == 0 and (project / 'tests' / '__snapshots__' / 'r-snapshot.yml').exists()
    again = invoke(['test'], project)
    assert again.returncode == 0 and 'test result: ok.' in again.stdout


def test_test_runner_reports_bad_expectation(project):
    rule(project / 'rules' / 'r.yml', {'pattern': 'foo()'}, rid='r')
    (project / 'tests' / 'r-test.yml').write_text('id: r\nvalid:\n- "foo()"\n')
    r = invoke(['test', '--skip-snapshot-tests'], project)
    assert r.returncode == 4 and '[Noisy]' in r.stdout


def test_new_project_and_rule_templates(tmp_path):
    r = invoke(['new', 'project', '--yes'], tmp_path)
    assert r.returncode == 0 and (tmp_path / 'sgconfig.yml').exists()
    made = invoke(['new', 'rule', 'My-Rule', '--lang', 'js', '--yes'], tmp_path)
    assert made.returncode == 0 and (tmp_path / 'rules' / 'My-Rule.yml').exists()
    assert (tmp_path / 'rule-tests' / 'My-Rule-test.yml').exists()


def test_new_requires_project_for_items(tmp_path):
    r = invoke(['new', 'rule', '--yes'], tmp_path)
    assert r.returncode == 3 and 'No ast-grep project configuration is found.' in r.stderr


def test_run_stdin_interactive_rejected(tmp_path):
    r = invoke(['run', '-p', 'foo()', '-l', 'js', '--stdin', '-i'], tmp_path, 'foo()')
    assert r.returncode == 7 and 'Interactive mode is incompatible' in r.stderr


def test_unicode_text_preserved_in_rewrite(tmp_path):
    f = tmp_path / 'u.js'; f.write_text('const s = "雪"; foo(s);', encoding='utf8')
    r = invoke(['run', '-p', 'foo($X)', '-r', 'bar($X)', '-l', 'js', '-U', f], tmp_path)
    assert r.returncode == 0 and '"雪"' in f.read_text(encoding='utf8') and 'bar(' in f.read_text()

