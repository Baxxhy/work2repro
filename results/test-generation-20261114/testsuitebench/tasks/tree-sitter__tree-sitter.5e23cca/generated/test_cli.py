import json
import os
import pathlib
import subprocess

import pytest


EXE = pathlib.Path('/workspace/executable')


def invoke(*args, cwd, env=None, stdin=None):
    merged = os.environ.copy()
    merged.update({'NO_COLOR': '1'})
    if env:
        merged.update({k: str(v) for k, v in env.items()})
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd, env=merged,
                          input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_version_and_global_precedence(tmp_path):
    r = invoke('--version', '--bogus', cwd=tmp_path)
    assert (r.returncode, r.stdout, r.stderr) == (0, b'tree-sitter 0.27.0\n', b'')
    r = invoke('-V', cwd=tmp_path)
    assert r.returncode == 0 and r.stdout == b'tree-sitter 0.27.0\n' and not r.stderr


def test_main_help_and_no_argument_behavior(tmp_path):
    help_result = invoke('--help', cwd=tmp_path)
    assert help_result.returncode == 0 and b'Generates and tests parsers\n' in help_result.stdout
    assert b'  init-config' in help_result.stdout and b'  complete' in help_result.stdout
    no_args = invoke(cwd=tmp_path)
    assert no_args.returncode == 2 and not no_args.stdout
    assert b'Usage: executable <COMMAND>' in no_args.stderr


@pytest.mark.parametrize('command,summary', [
    ('build', b'Compile a parser'), ('parse', b'Parse files'), ('query', b'Search files using a syntax tree query'),
    ('highlight', b'Highlight a file'), ('test', b"Run a parser's tests"), ('fuzz', b'Fuzz a parser'),
    ('tags', b'Generate a list of tags'), ('version', b'Display or increment the version of a grammar'),
    ('playground', b'Start local playground for a parser in the browser'), ('dump-languages', b'Print info about all known language parsers'),
    ('complete', b'Generate shell completions'), ('init-config', b'Generate a default config file'),
])
def test_command_help(command, summary, tmp_path):
    r = invoke(command, '--help', '--bad-option', cwd=tmp_path)
    assert r.returncode == 0 and not r.stderr and summary in r.stdout
    assert b'Usage: executable ' + command.encode() in r.stdout


@pytest.mark.parametrize('alias,canonical', [('i','init'),('g','generate'),('gen','generate'),('b','build'),('p','parse'),('t','test'),('f','fuzz'),('q','query')], ids=['init','g','gen','build','parse','test','fuzz','query'])
def test_alias_help(alias, canonical, tmp_path):
    a = invoke(alias, '--help', cwd=tmp_path)
    b = invoke(canonical, '--help', cwd=tmp_path)
    assert a.returncode == b.returncode == 0
    assert a.stdout == b.stdout


def test_unknown_command_option_and_eager_help(tmp_path):
    r = invoke('bogus', cwd=tmp_path)
    assert r.returncode == 2 and not r.stdout
    assert b"error: unrecognized subcommand 'bogus'" in r.stderr and b"try '--help'" in r.stderr
    r = invoke('highlight', '--unknown-flag', cwd=tmp_path)
    assert r.returncode == 2 and not r.stdout and b"unexpected argument '--unknown-flag'" in r.stderr
    r = invoke('generate', '--help', '--grammar-path', cwd=tmp_path)
    assert r.returncode == 0 and b'Generate a parser' in r.stdout


def test_unknown_option_guidance_and_boolean_grouping(tmp_path):
    for args, needles in [
        (('generate','--grammar-path'), (b"unexpected argument '--grammar-path'", b'Usage: executable generate [OPTIONS] [GRAMMAR_PATH]')),
        (('generate','--abi-version','15'), (b"a similar argument exists: '--abi'", b'Usage: executable generate --abi <VERSION> [GRAMMAR_PATH]')),
        (('test','--filter','foo'), (b"a similar argument exists: '--file-name'", b'Usage: executable test --file-name <FILE_NAME>')),
    ]:
        r = invoke(*args, cwd=tmp_path)
        assert r.returncode == 2 and not r.stdout
        for needle in needles: assert needle in r.stderr
    r = invoke('parse','-jq=foo',cwd=tmp_path)
    assert r.returncode == 2 and not r.stdout and b"unexpected argument '-=' found" in r.stderr


def test_argument_errors_conflicts_and_typed_values(tmp_path):
    cases = [
        (('complete','bash'), b"unexpected argument 'bash' found"),
        (('query',), b"required arguments were not provided"),
        (('complete','--shell','invalid'), b"invalid value 'invalid' for '--shell <SHELL>'"),
        (('parse','--encoding','invalid'), b"invalid value 'invalid' for '--encoding <ENCODING>'"),
        (('parse','--timeout','abc'), b"invalid value 'abc' for '--timeout <TIMEOUT>'"),
        (('parse','--test-number','abc'), b"invalid value 'abc' for '--test-number <TEST_NUMBER>'"),
        (('version','--bump','invalid'), b"invalid value 'invalid' for '--bump <BUMP>'"),
        (('test','--stat','invalid'), b"invalid value 'invalid' for '--stat <STAT>'"),
        (('fuzz','--grammar-path','x','--edits','abc','--iterations','1'), b"invalid value 'abc' for '--edits <EDITS>'"),
    ]
    for args, needle in cases:
        r = invoke(*args, cwd=tmp_path)
        assert r.returncode == 2 and not r.stdout and needle in r.stderr
        if b'invalid value' in needle: assert b'Usage:' not in r.stderr


def test_declared_conflicts(tmp_path):
    cases = [
        (('test','--grammar-path','DIR','--rebuild'), b"'--grammar-path <GRAMMAR_PATH>' cannot be used with '--rebuild'"),
        (('highlight','--grammar-path','DIR','--rebuild'), b"'--grammar-path <GRAMMAR_PATH>' cannot be used with '--rebuild'"),
        (('fuzz','--grammar-path','DIR','--rebuild'), b"'--grammar-path <GRAMMAR_PATH>' cannot be used with '--rebuild'"),
        (('parse','--grammar-path','DIR','--rebuild'), b"'--grammar-path <GRAMMAR_PATH>' cannot be used with '--rebuild'"),
        (('parse','--paths','FILE','--test-number','1'), b"'--paths <PATHS_FILE>' cannot be used with '--test-number <TEST_NUMBER>'"),
        (('parse','--test-number','1','SOURCE'), b"'--test-number <TEST_NUMBER>' cannot be used with '[PATHS]...'"),
        (('highlight','--test-number','1','SOURCE'), b"'--test-number <TEST_NUMBER>' cannot be used with '[PATHS]...'"),
        (('version','1.2.3','--bump','patch'), b"'[VERSION]' cannot be used with '--bump <BUMP>'"),
        (('parse','--json','--json-summary'), b"'--json' cannot be used with '--json-summary'"),
        (('parse','--stat','--json'), b"'--stat' cannot be used with '--json'"),
        (('generate','--json','--report-states-for-rule','source_file'), b"'--json' cannot be used with '--report-states-for-rule <REPORT_STATES_FOR_RULE>'"),
    ]
    for args, phrase in cases:
        r = invoke(*args, cwd=tmp_path)
        assert r.returncode == 2 and not r.stdout and phrase in r.stderr


def test_init_config_default_and_existing_file(tmp_path):
    home = tmp_path / 'home'; home.mkdir()
    r = invoke('init-config', cwd=tmp_path, env={'HOME': home, 'XDG_CONFIG_HOME': tmp_path/'xdg'})
    path = home/'.config/tree-sitter/config.json'
    assert r.returncode == 0 and not r.stdout and path.is_file()
    assert str(path) in r.stderr
    data = json.loads(path.read_text())
    assert list(data) == ['parser-directories','theme']
    assert data['parser-directories'] == [str(home/x) for x in ('github','src','source','projects','dev','git')]
    assert len(data['theme']) == 26 and data['theme']['embedded'] is None
    before = path.read_bytes()
    r = invoke('init-config', cwd=tmp_path, env={'HOME': home, 'XDG_CONFIG_HOME': tmp_path/'xdg'})
    assert r.returncode == 1 and not r.stdout and path.read_bytes() == before


def test_config_explicit_path_failure_and_precedence(tmp_path):
    r = invoke('dump-languages','--config-path',tmp_path/'missing.json',cwd=tmp_path)
    assert r.returncode == 1 and not r.stdout
    assert b'No such file or directory (os error 2)' in r.stderr and str(tmp_path/'missing.json').encode() in r.stderr
    config = tmp_path/'config.json'; config.write_text('{"parser-directories": []}')
    r = invoke('dump-languages','--config-path',config,cwd=tmp_path)
    assert r.returncode == 0 and b'not configured any parser directories' in r.stderr


def descriptor(root, version='1.2.3', extra=None):
    root.mkdir(parents=True, exist_ok=True)
    obj = {'metadata': {'version': version}, 'grammars': [{'name':'test','scope':'source.test'}]}
    if extra: obj.update(extra)
    (root/'tree-sitter.json').write_text(json.dumps(obj))
    return root


def test_version_read_bump_and_project_sync(tmp_path):
    grammar = descriptor(tmp_path/'grammar')
    r = invoke('version','--grammar-path',grammar,cwd=tmp_path)
    assert r.returncode == 0 and not r.stdout and b'Current version: 1.2.3' in r.stderr
    (grammar/'Makefile').write_text('VERSION := 1.2.3\n')
    (grammar/'Cargo.toml').write_text('[package]\nversion = "1.2.3"\n')
    (grammar/'package.json').write_text('{"version":"1.2.3","other":1}\n')
    (grammar/'pyproject.toml').write_text('[project]\nversion = "1.2.3"\n')
    (grammar/'CMakeLists.txt').write_text('project(test VERSION "1.2.3" LANGUAGES C)\n')
    r = invoke('version','--grammar-path',grammar,'--bump','minor',cwd=tmp_path)
    assert r.returncode == 0 and not r.stdout and b'Bumping version 1.2.3 to 1.3.0' in r.stderr
    assert json.loads((grammar/'tree-sitter.json').read_text())['metadata']['version'] == '1.3.0'
    for rel in ('Makefile','Cargo.toml','package.json','pyproject.toml','CMakeLists.txt'):
        assert '1.3.0' in (grammar/rel).read_text()


def test_version_requires_complete_descriptor_and_valid_semver(tmp_path):
    grammar = tmp_path/'grammar'; grammar.mkdir()
    (grammar/'tree-sitter.json').write_text('{"metadata":{"version":"3.4.5"},"grammars":[{"name":"test"}]}')
    r = invoke('version','--grammar-path',grammar,cwd=tmp_path)
    assert r.returncode == 1 and not r.stdout and b'missing field `scope`' in r.stderr
    r = invoke('version','--grammar-path',grammar,'1.2',cwd=tmp_path)
    assert r.returncode == 1 and not r.stdout


@pytest.mark.parametrize('shell,marker', [('bash',b'_tree-sitter()'),('zsh',b'#compdef tree-sitter'),('fish',b'complete -c tree-sitter'),('elvish',b'use builtin'),('power-shell',b'System.Management.Automation'),('nushell',b'export extern tree-sitter')],ids=['bash','zsh','fish','elvish','powershell','nushell'])
def test_completion_for_each_shell(shell, marker, tmp_path):
    r = invoke('complete','--shell',shell,cwd=tmp_path)
    assert r.returncode == 0 and r.stdout and not r.stderr and marker in r.stdout


def test_playground_export_copies_wasm_and_expands_template(tmp_path):
    grammar = tmp_path/'grammar'; (grammar/'src').mkdir(parents=True)
    (grammar/'src/grammar.json').write_text('{"name":"sample_lang","rules":{}}')
    wasm = b'\x00\xffwasm\x01'
    (grammar/'tree-sitter-sample_lang.wasm').write_bytes(wasm)
    out = tmp_path/'export'
    r = invoke('playground','--grammar-path',grammar,'--export',out,cwd=tmp_path)
    assert r.returncode == 0 and not r.stderr and r.stdout.startswith(b'Exported playground to ')
    assert (out/'tree-sitter-parser.wasm').read_bytes() == wasm
    html = (out/'index.html').read_text()
    assert html.startswith('<!DOCTYPE html>') and 'tree-sitter sample_lang' in html
    assert 'window.initializePlayground({local: true})' in html and 'tree-sitter-parser.wasm' not in html


def test_playground_export_missing_wasm_reports_context(tmp_path):
    grammar = tmp_path/'grammar'; (grammar/'src').mkdir(parents=True)
    (grammar/'src/grammar.json').write_text('{"name":"sample","rules":{}}')
    r = invoke('playground','--grammar-path',grammar,'--export',tmp_path/'out',cwd=tmp_path)
    assert r.returncode == 1 and not r.stdout and b'Failed to read tree-sitter-sample.wasm' in r.stderr
    assert b'Run `tree-sitter build --wasm` first.' in r.stderr

