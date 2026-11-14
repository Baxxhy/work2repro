import json
from pathlib import Path


def check_file(run, project, name, content, *args):
    path = project / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    return path, run(['check', '--no-config', *args, str(path)], cwd=project)


def test_heading_hierarchy_reports_location_and_message(run, project):
    path, r = check_file(run, project, 'doc.md', '# Title\n\n### Skipped\n', '--enable', 'MD001')
    assert r.returncode == 1
    assert b'doc.md:3:1: [MD001] Expected heading level 2, but found heading level 3' in r.stdout


def test_heading_hierarchy_fix_rewrites_entire_heading(run, project):
    path, r = check_file(run, project, 'doc.md', '# H1\n\n### H3\n', '--enable', 'MD001', '--fix')
    assert r.returncode == 0
    assert path.read_text() == '# H1\n\n## H3\n'
    assert b'[fixed]' in r.stdout


def test_trailing_spaces_are_detected_and_fixed(run, project):
    path, r = check_file(run, project, 'doc.md', '# Title   \n', '--enable', 'MD009')
    assert r.returncode == 1 and b'[MD009]' in r.stdout
    _, fixed = check_file(run, project, 'doc.md', '# Title   \n', '--enable', 'MD009', '--fix')
    assert fixed.returncode == 0 and path.read_bytes() == b'# Title\n'


def test_no_tabs_rule_and_fix(run, project):
    path, r = check_file(run, project, 'doc.md', '\ttext\n', '--enable', 'MD010')
    assert r.returncode == 1 and b'[MD010]' in r.stdout
    _, fixed = check_file(run, project, 'doc.md', '\ttext\n', '--enable', 'MD010', '--fix')
    assert fixed.returncode == 0 and path.read_bytes() == b'    text\n'


def test_code_blocks_are_ignored_by_trailing_space_rule(run, project):
    _, r = check_file(run, project, 'doc.md', '```text\ncode   \n```\n', '--enable', 'MD009')
    assert r.returncode == 0
    assert b'[MD009]' not in r.stdout


def test_unfixable_html_finding_survives_check_fix(run, project):
    path, r = check_file(run, project, 'doc.md', '<div>hello</div>\n', '--enable', 'MD033', '--fix')
    assert r.returncode == 1
    assert path.read_text() == '<div>hello</div>\n'
    assert b'[MD033]' in r.stdout and b'[*]' not in r.stdout


def test_inline_disable_suppresses_rule(run, project):
    _, r = check_file(run, project, 'doc.md', '<!-- rumdl-disable MD009 -->\ntext   \n', '--enable', 'MD009')
    assert r.returncode == 0 and b'[MD009]' not in r.stdout


def test_inline_disable_next_line_only_suppresses_next_line(run, project):
    _, r = check_file(run, project, 'doc.md', '<!-- rumdl-disable-next-line MD009 -->\nfirst   \nsecond   \n', '--enable', 'MD009')
    assert r.returncode == 1
    assert r.stdout.count(b'[MD009]') == 1
    assert b'doc.md:3:' in r.stdout


def test_unicode_and_crlf_are_preserved_by_fix(run, project):
    path = project / 'emoji.md'
    path.write_bytes('# Título 😀   \r\n')
    r = run(['fmt', '--no-config', str(path)], cwd=project)
    assert r.returncode == 0
    assert path.read_bytes() == '# Título 😀\r\n'.encode()


def test_fail_on_never_reports_but_succeeds(run, project):
    _, r = check_file(run, project, 'doc.md', '# H1\n\n### H3\n', '--enable', 'MD001', '--fail-on', 'never')
    assert r.returncode == 0 and b'[MD001]' in r.stdout


def test_error_severity_changes_threshold(run, project):
    (project / 'rumdl.toml').write_text('[MD009]\nseverity = "error"\n')
    path = project / 'doc.md'
    path.write_text('text   \n')
    warning_only = run(['check', '--enable', 'MD009', '--fail-on', 'error', str(path)], cwd=project)
    assert warning_only.returncode == 1
    assert b'[MD009]' in warning_only.stdout


def test_json_output_is_valid_and_has_finding_fields(run, project):
    path = project / 'doc.md'
    path.write_text('# H1\n\n### H3\n')
    r = run(['check', '--no-config', '--enable', 'MD001', '-o', 'json', str(path)], cwd=project)
    assert r.returncode == 1
    rows = json.loads(r.stdout)
    assert len(rows) == 1
    assert rows[0]['rule'] == 'MD001' and rows[0]['line'] == 3 and rows[0]['column'] == 1
    assert rows[0]['fix']['replacement'] == '## H3'


def test_junit_output_is_well_formed_xml(run, project):
    import xml.etree.ElementTree as ET
    path = project / 'doc.md'
    path.write_text('![x]()\n')
    r = run(['check', '--no-config', '--enable', 'MD042', '--output-format', 'junit', str(path)], cwd=project)
    assert r.returncode == 1
    root = ET.fromstring(r.stdout)
    assert root.tag == 'testsuites'
    assert root.find('.//testcase') is not None


def test_sarif_output_has_version_and_results(run, project):
    path = project / 'doc.md'
    path.write_text('# H1\n\n### H3\n')
    r = run(['check', '--no-config', '--enable', 'MD001', '--output-format', 'sarif', str(path)], cwd=project)
    assert r.returncode == 1
    data = json.loads(r.stdout)
    assert data['version'] == '2.1.0'
    assert data['runs'][0]['tool']['driver']['version'] == '0.1.13'
    assert data['runs'][0]['results'][0]['ruleId'] == 'MD001'
