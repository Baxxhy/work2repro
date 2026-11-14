import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXE = Path('/workspace/executable') if Path('/workspace/executable').exists() else ROOT / 'executable'


@pytest.fixture
def env(tmp_path):
    config, data = tmp_path / 'config', tmp_path / 'data'
    (data / 'applications').mkdir(parents=True)
    return {**os.environ, 'XDG_CONFIG_HOME': str(config), 'XDG_DATA_HOME': str(data),
            'XDG_DATA_DIRS': str(tmp_path / 'system-data')}


def run(env, *args):
    return subprocess.run([str(EXE), *args], env=env, capture_output=True, text=True)


def desktop(env, filename='app.desktop', name='App', exec_line='/bin/true', extra=''):
    p = Path(env['XDG_DATA_HOME']) / 'applications' / filename
    p.write_text(f'[Desktop Entry]\nName={name}\nExec={exec_line}\n{extra}', encoding='utf-8')
    return p


def test_no_args_and_versions(env):
    p = run(env)
    assert p.returncode == 2 and 'USAGE:' in p.stdout + p.stderr
    for args, expected in [(('--version',), 'handlr 0.6.4\n'), (('-V',), 'handlr 0.6.4\n')]:
        p = run(env, *args)
        assert (p.returncode, p.stdout, p.stderr) == (0, expected, '')


def test_top_help_exact_and_precedence(env):
    p = run(env, '--help')
    assert p.returncode == 0 and p.stderr == ''
    assert p.stdout.startswith('handlr 0.6.4\n\nUSAGE:\n')
    assert '    add       Add a handler for given mime/extension Note that the first handler is the default\n' in p.stdout
    p = run(env, '--help', '--nonsense')
    assert p.returncode == 0 and p.stdout == run(env, '--help').stdout
    assert 'autocomplete' not in p.stdout


@pytest.mark.parametrize('cmd,usage', [
    ('list', '    executable list [FLAGS]'), ('open', '    executable open <paths>...'),
    ('set', '    executable set <mime> <handler>'), ('unset', '    executable unset <mime>'),
    ('launch', '    executable launch <mime> [args]...'), ('get', '    executable get [FLAGS] <mime>'),
    ('add', '    executable add <mime> <handler>')], ids=['list','open','set','unset','launch','get','add'])
def test_each_help_and_version(env, cmd, usage):
    p = run(env, cmd, '--help')
    assert p.returncode == 0 and p.stderr == '' and usage in p.stdout
    assert 'FLAGS:' in p.stdout and '-h, --help' in p.stdout and '-V, --version' in p.stdout
    p = run(env, cmd, '--version')
    assert p.returncode == 0 and p.stdout == f'executable-{cmd} \n'


def test_launch_help_arguments_order(env):
    out = run(env, 'launch', '--help').stdout
    assert out.index('ARGS:') < out.index('<mime>') < out.index('<args>...') < out.index('FLAGS:')


def test_missing_required_arguments(env):
    for cmd, expected in [('set', '<mime>\n    <handler>'), ('unset','<mime>'), ('add','<mime>\n    <handler>'),
                          ('open','<paths>...'), ('launch','<mime>'), ('get','<mime>')]:
        p = run(env, cmd)
        assert p.returncode == 2 and expected in p.stderr and 'For more information try --help' in p.stderr
    p = run(env, 'get', '--json')
    assert p.returncode == 2 and 'executable get <mime> --json' in p.stderr


def test_unknown_command_suggestion(env):
    p = run(env, 'nope')
    assert p.returncode == 2 and 'nope' in p.stderr and 'did you mean' in p.stderr.lower()
    assert 'USAGE:' in p.stderr and '--help' in p.stderr


def test_unknown_flags_are_rejected_and_scoped(env):
    for args in [('list','--json'), ('get','--all','text/plain'), ('set','--bad','text/plain','app.desktop')]:
        p = run(env, *args)
        assert p.returncode == 2


def test_initialization_creates_exact_config(env):
    p = run(env, 'list')
    assert p.returncode == 0
    cfg = Path(env['XDG_CONFIG_HOME'])
    assert (cfg / 'mimeapps.list').read_bytes() == b''
    assert (cfg / 'handlr' / 'handlr.toml').read_text() == 'enable_selector = false\nselector = "rofi -dmenu -i -p \'Open With: \'"\n'


def test_existing_config_is_not_reformatted(env):
    cfg = Path(env['XDG_CONFIG_HOME']) / 'handlr'
    cfg.mkdir(parents=True)
    f = cfg / 'handlr.toml'
    f.write_text('# keep me\nenable_selector = false\nselector = "head"\n')
    assert run(env, 'list').returncode == 0
    assert f.read_text() == '# keep me\nenable_selector = false\nselector = "head"\n'
