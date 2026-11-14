import json
import os
import re
import stat
import subprocess
from pathlib import Path

import pytest


EXE = Path('/workspace/executable')


def run(cwd, *args, timeout=12):
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def put(root, name, text=''):
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')
    return p


def tree(root, entry, *flags):
    p = run(root, 'tree', '--json', *flags, entry)
    assert p.returncode == 0, p.stderr
    assert p.stderr == ''
    return json.loads(p.stdout)


def test_version_and_main_help(tmp_path):
    v = run(tmp_path, '--version')
    assert (v.returncode, v.stdout, v.stderr) == (0, 'dep-tree version v0.23.4\n', '')
    for args in [(), ('help',), ('--help',), ('-h',)]:
        p = run(tmp_path, *args)
        assert p.returncode == 0 and p.stderr == ''
        assert p.stdout.startswith('\n      ____') and p.stdout.endswith('\n')
        assert 'Additional Commands:' in p.stdout


@pytest.mark.parametrize('cmd', ['entropy', 'tree', 'check', 'explain', 'config', 'help'], ids=['entropy-help','tree-help','check-help','explain-help','config-help','help-help'])
def test_command_help(cmd, tmp_path):
    p = run(tmp_path, cmd, '--help')
    assert p.returncode == 0 and p.stderr == ''
    assert 'Usage:' in p.stdout
    assert run(tmp_path, 'help', cmd).stdout == p.stdout


def test_init_is_config_help_alias(tmp_path):
    assert run(tmp_path, 'init', '--help').stdout == run(tmp_path, 'config', '--help').stdout


def test_parser_errors_and_command_scoped_flags(tmp_path):
    for args, fragment in [(('--made-up',), 'Error: unknown flag: --made-up'),
                           (('--json',), 'Error: unknown flag: --json'),
                           (('--overlap-left',), 'Error: unknown flag: --overlap-left'),
                           (('--help', '--wat'), 'Error: unknown flag: --wat')]:
        p = run(tmp_path, *args)
        assert p.returncode == 1 and fragment in p.stderr
        if '--help' in args:
            assert p.stdout == ''


def test_boolean_parsing_and_default_entropy_route(tmp_path):
    put(tmp_path, 'main.js', '')
    a = run(tmp_path, 'main.js', '--no-browser-open')
    b = run(tmp_path, 'entropy', 'main.js', '--no-browser-open')
    assert a.returncode == b.returncode == 0
    q = run(tmp_path, 'tree', '--json=maybe', 'main.js')
    assert q.returncode == 1 and 'invalid argument "maybe" for "--json" flag' in q.stderr
    q = run(tmp_path, 'tree', '--json=false')
    assert q.returncode == 1 and 'requires at least 1 arg' in q.stderr


def test_unknown_word_is_default_entrypoint(tmp_path):
    p = run(tmp_path, 'chekc', '--no-browser-open')
    assert p.returncode == 1 and 'Error: chekc does not match with any existing file' in p.stderr


def test_tree_json_diamond_and_exact_top_level(tmp_path):
    put(tmp_path, 'main.js', "import './left.js'; import './right.js';")
    put(tmp_path, 'left.js', "import './shared.js';")
    put(tmp_path, 'right.js', "import './shared.js';")
    put(tmp_path, 'shared.js', '')
    result = tree(tmp_path, 'main.js')
    assert set(result) == {'tree', 'circularDependencies', 'errors'}
    assert result == {'tree': {'main.js': {'left.js': {'shared.js': None}, 'right.js': {'shared.js': None}}},
                      'circularDependencies': [], 'errors': {}}


def test_tree_direct_import_forms_and_dedup(tmp_path):
    put(tmp_path, 'a.js', "import x from './b';\nconst y = require('./c.js');\nimport('./b.js');\nexport * from './d.js';")
    for n in ['b.js', 'c.js', 'd.js']:
        put(tmp_path, n)
    result = tree(tmp_path, 'a.js')
    assert result['tree'] == {'a.js': {'b.js': None, 'c.js': None, 'd.js': None}}


def test_tree_cycles_and_cycle_cut(tmp_path):
    put(tmp_path, 'a.js', "import './b.js';")
    put(tmp_path, 'b.js', "import './c.js';")
    put(tmp_path, 'c.js', "import './a.js';")
    d = tree(tmp_path, 'a.js')
    assert d['tree'] == {'a.js': {'b.js': {'c.js': None}}}
    assert d['circularDependencies'] == [['a.js', 'b.js', 'c.js', 'a.js']]


def test_missing_js_import_is_recoverable(tmp_path):
    put(tmp_path, 'main.js', "import './missing.js';")
    d = tree(tmp_path, 'main.js')
    assert d['tree'] == {'main.js': None}
    assert d['errors'] and any('missing.js' in e for vals in d['errors'].values() for e in vals)


def test_entrypoint_globs_and_directory_validation(tmp_path):
    put(tmp_path, 'src/a.js'); put(tmp_path, 'src/b.js')
    assert tree(tmp_path, '**/a.js')['tree'] == {'src/a.js': None}
    p = run(tmp_path, 'tree', '--json', 'src')
    assert p.returncode == 1 and 'no valid files' in p.stderr
    p = run(tmp_path, 'tree', '--json', 'absent.js')
    assert p.returncode == 1 and 'absent.js does not match' in p.stderr


def test_unsupported_and_mixed_language_inputs(tmp_path):
    put(tmp_path, 'x.txt')
    p = run(tmp_path, 'tree', '--json', 'x.txt')
    assert p.returncode == 1 and 'none of the provided files belong' in p.stderr
    put(tmp_path, 'a.dl'); put(tmp_path, 'b.js')
    p = run(tmp_path, 'entropy', 'a.dl', 'b.js', '--no-browser-open', '--render-path', 'mix.html')
    assert p.returncode == 0 and p.stdout == 'mix.html\n' and (tmp_path/'mix.html').exists()


def test_tree_requires_one_entrypoint_and_json_has_no_progress(tmp_path):
    put(tmp_path, 'a.js'); put(tmp_path, 'b.py')
    p = run(tmp_path, 'tree', '--json', '*.js', '*.py')
    assert p.returncode == 1 and 'only 1 entrypoint' in p.stderr
    p = run(tmp_path, 'tree', '--json', 'a.js')
    assert p.returncode == 0 and p.stderr == '' and p.stdout.endswith('\n')


def test_filters_exclude_nodes_and_filter_entrypoint(tmp_path):
    put(tmp_path, 'main.js', "import './helper.js';")
    put(tmp_path, 'helper.js')
    d = tree(tmp_path, 'main.js', '--exclude=helper.js')
    assert d['tree'] == {'main.js': None}
    p = run(tmp_path, 'tree', '--json', '--exclude', 'main.js', 'main.js')
    assert p.returncode == 1 and 'explicitly ignored' in p.stderr


def test_only_patterns_accumulate_and_malformed_filter(tmp_path):
    put(tmp_path, 'main.js', "import './a.js'; import './b.js';")
    put(tmp_path, 'a.js'); put(tmp_path, 'b.js')
    d = tree(tmp_path, 'main.js', '--only=main.js', '--only=**/a.js')
    assert d['tree'] == {'main.js': {'a.js': None}}
    p = run(tmp_path, 'tree', '--json', '--only=[invalid', 'main.js')
    assert p.returncode == 1 and 'only pattern' in p.stderr


def test_config_generator_exact_mode_and_no_overwrite(tmp_path):
    p = run(tmp_path, 'config')
    assert p.returncode == 0 and p.stdout == p.stderr == ''
    cfg = tmp_path/'.dep-tree.yml'
    assert cfg.exists() and stat.S_IMODE(cfg.stat().st_mode) == 0o600
    content = cfg.read_bytes()
    p = run(tmp_path, 'init')
    assert p.returncode == 1 and '.dep-tree.yml' in p.stderr and 'already exists' in p.stderr
    assert cfg.read_bytes() == content


def test_custom_config_is_mandatory_and_yaml_validation(tmp_path):
    put(tmp_path, 'a.js')
    p = run(tmp_path, 'tree', '--json', '--config', 'missing.yml', 'a.js')
    assert p.returncode == 1 and 'open missing.yml' in p.stderr
    put(tmp_path, 'bad.yml', 'only: [\n')
    p = run(tmp_path, 'tree', '--json', '-c=bad.yml', 'a.js')
    assert p.returncode == 1 and 'not a valid yml file' in p.stderr


def test_python_imports_and_conditional_flag(tmp_path):
    put(tmp_path, 'main.py', 'import helper\n')
    put(tmp_path, 'helper.py')
    assert tree(tmp_path, 'main.py')['tree'] == {'main.py': {'helper.py': None}}
    put(tmp_path, 'conditional.py', 'if True:\n    import helper\n')
    assert tree(tmp_path, 'conditional.py', '--python-exclude-conditional-imports')['tree'] == {'conditional.py': None}


def test_dl_language_diamond_and_bad_syntax(tmp_path):
    put(tmp_path, 'a.dl', 'import x from ./b.dl\nimport y from ./c.dl\n')
    put(tmp_path, 'b.dl', 'import z from ./d.dl\n')
    put(tmp_path, 'c.dl', 'import z from ./d.dl\n')
    put(tmp_path, 'd.dl')
    assert tree(tmp_path, 'a.dl')['tree'] == {'a.dl': {'b.dl': {'d.dl': None}, 'c.dl': {'d.dl': None}}}
    put(tmp_path, 'bad.dl', 'import x ./b.dl\n')
    p = run(tmp_path, 'tree', '--json', 'bad.dl')
    assert p.returncode == 1 and 'from' in p.stderr and 'bad.dl' in p.stderr


def test_rust_modules_and_missing_mod_error(tmp_path):
    put(tmp_path, 'Cargo.toml', '[package]\nname="sample"\n')
    put(tmp_path, 'src/lib.rs', 'pub mod a;\nmod absent;')
    put(tmp_path, 'src/a.rs', '')
    d = tree(tmp_path, 'src/lib.rs')
    assert d['tree'] == {'src/lib.rs': {'src/a.rs': None}}
    assert any('could not find mod absent' in e for e in d['errors']['src/lib.rs'])


def test_go_local_imports(tmp_path):
    put(tmp_path, 'go.mod', 'module example.com/app\n')
    put(tmp_path, 'main.go', 'package main\nimport "example.com/app/helper"\n')
    put(tmp_path, 'helper/helper.go', 'package helper\n')
    d = tree(tmp_path, 'main.go')
    assert d['tree'] == {'main.go': {'helper/helper.go': None}}


def test_explain_direct_edges_overlap_and_counts(tmp_path):
    put(tmp_path, 'package.json', '{"name":"demo"}')
    put(tmp_path, 'a.js', "import './b.js'; import './c.js';")
    put(tmp_path, 'b.js', "import './c.js';")
    put(tmp_path, 'c.js')
    p = run(tmp_path, 'explain', '*.js', 'c.js')
    assert p.returncode == 0 and p.stdout == 'a.js -> c.js\nb.js -> c.js\n'
    p = run(tmp_path, 'explain', '--overlap-left', '*.js', 'c.js')
    assert p.returncode == 0 and p.stdout == 'a.js -> c.js\nb.js -> c.js\n'
    p = run(tmp_path, 'explain', 'a.js')
    assert p.returncode == 1 and 'accepts 2 arg(s), received 1' in p.stderr
    p = run(tmp_path, 'explain', '-lr', '*.js', 'c.js')
    assert p.returncode == 1 and 'only one of' in p.stderr


def test_check_requires_config_and_reports_rule_violations(tmp_path):
    put(tmp_path, 'src/a.js', "import '../b.js';")
    put(tmp_path, 'b.js')
    p = run(tmp_path, 'check')
    assert p.returncode == 1 and 'when using the `check` subcommand' in p.stderr
    put(tmp_path, '.dep-tree.yml', "check:\n  entrypoints: [src/a.js]\n  deny:\n    'src/**': ['b.js']\n")
    p = run(tmp_path, 'check')
    assert p.returncode == 1 and 'Check failed' in p.stderr and 'src/a.js' in p.stderr


def test_entropy_html_embeds_valid_data_and_mode(tmp_path):
    put(tmp_path, 'main.js', "import './dep.js';")
    put(tmp_path, 'dep.js', '')
    p = run(tmp_path, 'entropy', 'main.js', '--no-browser-open', '--render-path', 'graph.html')
    assert p.returncode == 0 and p.stdout == 'graph.html\n'
    html = (tmp_path/'graph.html').read_text(encoding='utf-8')
    assert len(html.encode()) > 50000 and '<!doctype html>' in html.lower()
    assert '<html lang="en">' in html and '<title>Dep Tree</title>' in html and '</html>' in html
    assert stat.S_IMODE((tmp_path/'graph.html').stat().st_mode) == 0o600
    match = re.search(r'Jt\(KC,"__INLINE_DATA",(\{.*?\})\);', html, re.S)
    assert match
    data = json.loads(match.group(1))
    assert set(data) >= {'nodes', 'links', 'enableGui'}
    assert len(data['nodes']) == 2 and len(data['links']) == 1
    assert sum(bool(n['isEntrypoint']) for n in data['nodes']) == 1
    assert all(isinstance(n['id'], int) and isinstance(n['loc'], int) and isinstance(n['size'], int) for n in data['nodes'])


def test_entropy_gui_flag_and_unwritable_path(tmp_path):
    put(tmp_path, 'a.js')
    p = run(tmp_path, 'entropy', 'a.js', '--enable-gui', '--no-browser-open', '--render-path', 'gui.html')
    assert p.returncode == 0
    html = (tmp_path/'gui.html').read_text()
    match = re.search(r'Jt\(KC,"__INLINE_DATA",(\{.*?\})\);', html, re.S)
    assert json.loads(match.group(1))['enableGui'] is True
    p = run(tmp_path, 'entropy', 'a.js', '--no-browser-open', '--render-path', 'missing/out.html')
    assert p.returncode == 1 and p.stderr.startswith('Error:')
