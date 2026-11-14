import json


def test_stdin_check_routes_diagnostics_to_stderr(run, project):
    r = run(['check', '--no-config', '--enable', 'MD009', '-'], cwd=project, input=b'text   \n')
    assert r.returncode == 1 and r.stdout == b''
    assert b'<stdin>:1:' in r.stderr and b'[MD009]' in r.stderr


def test_stdin_filename_changes_diagnostic_path(run, project):
    r = run(['check', '--no-config', '--enable', 'MD009', '--stdin-filename', 'notes.md', '--stdin'],
            cwd=project, input=b'text   \n')
    assert r.returncode == 1 and b'notes.md:1:' in r.stderr


def test_fmt_stdin_outputs_only_formatted_document(run, project):
    r = run(['fmt', '--no-config', '-'], cwd=project, input=b'# H\ntext\n')
    assert r.returncode == 0
    assert r.stdout == b'# H\n\ntext\n' and r.stderr == b''


def test_fmt_stdin_clean_input_is_echoed(run, project):
    source = b'# H\n\ntext\n'
    r = run(['fmt', '--no-config', '--quiet', '-'], cwd=project, input=source)
    assert r.returncode == 0 and r.stdout == source and r.stderr == b''


def test_missing_check_path_is_runtime_failure(run, project):
    r = run(['check', '--no-config', 'missing.md'], cwd=project)
    assert r.returncode == 1 and r.stdout == b''
    assert b'missing.md' in r.stderr


def test_missing_fmt_path_returns_success_but_reports_error(run, project):
    r = run(['fmt', '--no-config', '/nonexistent/file.md'], cwd=project)
    assert r.returncode == 0 and r.stdout == b''
    assert r.stderr == b'Error: Failed to find markdown files: File not found: /nonexistent/file.md\n'


def test_explicit_file_can_have_non_markdown_extension(run, project):
    path = project / 'note.txt'
    path.write_text('text   \n')
    r = run(['check', '--no-config', '--enable', 'MD009', str(path)], cwd=project)
    assert r.returncode == 1 and b'[MD009]' in r.stdout


def test_default_directory_scan_excludes_txt(run, project):
    (project / 'note.txt').write_text('text   \n')
    r = run(['check', '--no-config', '--enable', 'MD009'], cwd=project)
    assert r.returncode == 0
    assert b'No markdown files found to check.' in r.stdout


def test_explicit_file_operand_takes_precedence_over_directory_scan(run, project):
    (project / 'a.md').write_text('a   \n')
    (project / 'b.md').write_text('b   \n')
    r = run(['check', '--no-config', '--enable', 'MD009', '.', 'a.md'], cwd=project)
    assert r.returncode == 1
    assert b'a.md:' in r.stdout and b'b.md:' not in r.stdout


def test_exclude_wins_over_include_for_explicit_file(run, project):
    (project / 'doc.md').write_text('text   \n')
    r = run(['check', '--no-config', '--enable', 'MD009', '--include', '*.md', '--exclude', 'doc.md', 'doc.md'], cwd=project)
    assert r.returncode == 0 and b'[MD009]' not in r.stdout
    assert b'ignored because of exclude pattern' in r.stderr


def test_configured_include_does_not_filter_explicit_directory(run, project):
    (project / 'rumdl.toml').write_text('[global]\ninclude = ["src/*.md"]\n')
    (project / 'docs').mkdir()
    (project / 'docs' / 'one.md').write_text('a   \n')
    (project / 'docs' / 'temp').mkdir()
    (project / 'docs' / 'temp' / 'two.md').write_text('b   \n')
    r = run(['check', '--enable', 'MD009', '--verbose', 'docs'], cwd=project)
    assert r.returncode == 1
    assert b'docs/one.md' in r.stdout and b'docs/temp/two.md' in r.stdout


def test_gitignore_filters_directory_scan_but_not_explicit_file(run, project):
    (project / '.gitignore').write_text('skip.md\n')
    (project / 'keep.md').write_text('clean\n')
    (project / 'skip.md').write_text('text   \n')
    scan = run(['check', '--no-config', '--enable', 'MD009'], cwd=project)
    assert scan.returncode == 0 and b'1 file' in scan.stdout
    explicit = run(['check', '--no-config', '--enable', 'MD009', 'skip.md'], cwd=project)
    assert explicit.returncode == 1 and b'[MD009]' in explicit.stdout


def test_no_config_ignores_project_disable(run, project):
    (project / 'rumdl.toml').write_text('[global]\ndisable = ["MD009"]\n')
    path = project / 'doc.md'
    path.write_text('text   \n')
    configured = run(['check', str(path)], cwd=project)
    isolated = run(['check', '--no-config', str(path)], cwd=project)
    assert configured.returncode == 0
    assert isolated.returncode == 1 and b'[MD009]' in isolated.stdout


def test_cli_output_format_overrides_environment(run, project):
    path = project / 'doc.md'
    path.write_text('# H\n\n### H3\n')
    r = run(['check', '--no-config', '--enable', 'MD001', '--output-format', 'json', str(path)],
            cwd=project, env={'RUMDL_OUTPUT_FORMAT': 'text'})
    assert r.returncode == 1
    assert json.loads(r.stdout)[0]['rule'] == 'MD001'
