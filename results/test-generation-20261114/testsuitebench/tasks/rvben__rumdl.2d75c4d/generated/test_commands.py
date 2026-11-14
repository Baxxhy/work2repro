import json
from pathlib import Path


def test_rule_catalog_count_and_fixable_filter(run, project):
    all_rules = run(['rule', '--output-format', 'json'], cwd=project)
    assert all_rules.returncode == 0
    rows = json.loads(all_rules.stdout)
    assert len(rows) == 67
    assert [x['code'] for x in rows] == sorted((x['code'] for x in rows))
    fixable = run(['rule', '--fixable', '--output-format', 'json'], cwd=project)
    codes = {x['code'] for x in json.loads(fixable.stdout)}
    assert len(codes) == 64
    assert not ({'MD033', 'MD054', 'MD059'} & codes)


def test_rule_categories_and_single_rule_metadata(run, project):
    r = run(['rule', '--category', 'heading'], cwd=project)
    assert r.returncode == 0 and b'Total: 11 rules' in r.stdout
    assert b'MD001 - Heading levels should only increment by one level at a time' in r.stdout
    single = run(['rule', '001'], cwd=project)
    assert single.returncode == 0 and b'Name: heading-increment' in single.stdout


def test_schema_print_is_valid_json(run, project):
    r = run(['schema', 'print'], cwd=project)
    assert r.returncode == 0
    schema = json.loads(r.stdout)
    assert schema['$schema'].endswith('json-schema-2.1.0.json')
    assert set(schema['properties']) == {'global', 'per-file-ignores', 'per-file-flavor', 'code-block-tools'}


def test_schema_generate_and_check_are_idempotent(run, project):
    first = run(['schema', 'generate'], cwd=project)
    target = project / 'rumdl.schema.json'
    assert first.returncode == 0 and target.exists()
    content = target.read_bytes()
    assert not content.endswith(b'\n')
    second = run(['schema', 'generate'], cwd=project)
    assert second.returncode == 0 and b'already up-to-date' in second.stdout
    check = run(['schema', 'check'], cwd=project)
    assert check.returncode == 0 and b'up-to-date' in check.stdout


def test_schema_check_missing_file_is_error(run, project):
    r = run(['schema', 'check'], cwd=project)
    assert r.returncode == 2 and not r.stdout
    assert b'Schema file not found' in r.stderr and b'rumdl schema generate' in r.stderr


def test_import_json_dry_run_converts_options(run, project):
    source = project / 'markdownlint.json'
    source.write_text('{"default": true, "MD013": false, "MD007": {"indent": 3}}')
    r = run(['import', str(source), '--dry-run'], cwd=project)
    assert r.returncode == 0
    assert b'[global]' in r.stdout and b'disable = ["MD013"]' in r.stdout
    assert b'[MD007]' in r.stdout and b'style = "fixed"' in r.stdout
    assert r.stdout.endswith(b'\n\n\n')


def test_import_missing_file_is_usage_failure(run, project):
    r = run(['import', '/nonexistent/config.json'], cwd=project)
    assert r.returncode == 2 and not r.stdout
    assert r.stderr == b'Import error: Failed to read config file /nonexistent/config.json: No such file or directory (os error 2)\n'


def test_import_refuses_existing_output_without_overwriting(run, project):
    source = project / 'source.json'
    target = project / 'out.toml'
    source.write_text('{"MD013": false}')
    target.write_bytes(b'keep me')
    r = run(['import', str(source), '--output', str(target)], cwd=project)
    assert r.returncode == 2 and not r.stdout
    assert target.read_bytes() == b'keep me'
    assert b'already exists' in r.stderr


def test_init_creates_configuration_and_refuses_overwrite(run, project):
    first = run(['init'], cwd=project)
    target = project / '.rumdl.toml'
    assert first.returncode == 0 and target.exists()
    content = target.read_bytes()
    assert b'[global]' in content and b'respect-gitignore = true' in content
    second = run(['init'], cwd=project)
    assert second.returncode == 2 and target.read_bytes() == content
    assert b'already exists' in second.stderr


def test_clean_missing_cache_is_success(run, project):
    r = run(['clean'], cwd=project)
    assert r.returncode == 0
    assert r.stdout == b'No cache found at .rumdl_cache (nothing to clean)\n'


def test_clean_removes_only_cache_directory(run, project):
    cache = project / '.rumdl_cache'
    cache.mkdir()
    (cache / 'entry').write_text('cached')
    outside = project / 'important'
    outside.write_text('preserve')
    r = run(['clean'], cwd=project)
    assert r.returncode == 0 and not cache.exists()
    assert outside.read_text() == 'preserve'


def test_clean_rejects_cache_dir_option(run, project):
    r = run(['clean', '--cache-dir', 'somewhere'], cwd=project)
    assert r.returncode == 2 and b'unexpected argument' in r.stderr


def test_vscode_missing_editor_is_clean_usage_error(run, project):
    r = run(['vscode', '--status'], cwd=project, env={'PATH': ''})
    assert r.returncode == 2 and not r.stdout
    assert b'VS Code (or compatible editor) not found' in r.stderr
