import os
import subprocess
from pathlib import Path

import pytest


BIN = Path('/workspace/executable')
B = '\x1b[0;34m'
R = '\x1b[0;31m'
Z = '\x1b[0m'


@pytest.fixture
def ctx(tmp_path):
    home = tmp_path / 'home'
    cfg = tmp_path / 'config-home'
    data = tmp_path / 'data-home'
    home.mkdir()
    cfg.mkdir()
    data.mkdir()
    env = os.environ.copy()
    for k in ('HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME'):
        env.pop(k, None)
    env.update(HOME=str(home), XDG_CONFIG_HOME=str(cfg), XDG_DATA_HOME=str(data))
    return {'env': env, 'cfg': cfg / 'jot' / 'config', 'registry': data / 'jot' / 'vaults', 'home': home, 'base': tmp_path}


def run(ctx, *args):
    return subprocess.run([str(BIN), *map(str, args)], env=ctx['env'], text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)


def runtime(ctx, expected, *args):
    p = run(ctx, *args)
    assert p.returncode == 0
    assert p.stderr == ''
    assert p.stdout == expected
    return p


def make_vault(ctx, name='V', parent=None):
    parent = parent or ctx['base']
    runtime(ctx, f'vault {B}{name}{Z} created\n', 'vault', name, parent)
    return Path(parent) / name


def enter(ctx, name='V'):
    runtime(ctx, f'entered {B}{name}{Z}\n', 'enter', name)


def test_fresh_files_and_config(ctx):
    p = run(ctx, 'config', 'editor')
    assert p.returncode == 0 and p.stderr == ''
    assert p.stdout == f'editor: {B}nvim{Z}\n'
    assert ctx['cfg'].read_text() == "editor = 'nvim'\nconflict = true\n"
    assert ctx['registry'].read_text() == '[vaults]\n'


def test_config_persistence_and_exact_values(ctx):
    for value in ('a b', '', 'λ\'q', 'very-long-' + 'x' * 120):
        runtime(ctx, f'set {B}editor{Z} to {B}{value}{Z}\n', 'config', 'editor', value)
        runtime(ctx, f'editor: {B}{value}{Z}\n', 'config', 'editor')
    runtime(ctx, f'set {B}conflict{Z} to {B}false{Z}\n', 'config', 'conflict', 'false')
    runtime(ctx, f'conflict: {B}false{Z}\n', 'cf', 'conflict')


def test_config_invalid_values_and_parser(ctx):
    p = run(ctx, 'config', 'nope')
    assert p.returncode != 0 and 'isn\'t a valid value' in p.stderr and p.stdout == ''
    p = run(ctx, 'config', 'editor', 'vim', 'emacs')
    assert p.returncode != 0 and "Found argument 'emacs'" in p.stderr
    before = ctx['cfg'].read_bytes()
    p = run(ctx, 'config', 'conflict', 'True')
    assert p.returncode != 0 and 'ParseBoolError' in p.stderr and 'panicked at src/state/config.rs' in p.stderr
    assert ctx['cfg'].read_bytes() == before


def test_help_and_parser_basics(ctx):
    p = run(ctx)
    assert p.returncode == 2 and p.stdout == '' and 'usage: jt <command>' in p.stderr
    p = run(ctx, '--help')
    assert p.returncode == 0 and p.stderr == ''
    assert 'ᵥ₀.₁.₂' in p.stdout and '\x1b[0;34mcommands:\x1b[0m' in p.stdout
    for command in ('vault','vl','note','nt','folder','fd','enter','en','open','op','opdir','od','chdir','cd','list','ls','remove','rm','rename','rn','move','mv','vmove','vm','config','cf'):
        p = run(ctx, command, '--help')
        assert p.returncode == 0 and p.stderr == '' and 'USAGE:' in p.stdout and '-h, --help' in p.stdout
    p = run(ctx, 'open', 'n', 'extra')
    assert p.returncode == 2 and "Found argument 'extra'" in p.stderr
    p = run(ctx, '--version')
    assert p.returncode != 0 and 'Found argument' in p.stderr


def test_missing_arguments_and_alias_validation(ctx):
    for args, placeholder in [(('enter',), '<vault name>'), (('open',), '<note name>'), (('chdir',), '<folder path>'), (('remove',), '<item type>'), (('rename',), '<item type>'), (('move',), '<item type>'), (('vmove',), '<item type>')]:
        p = run(ctx, *args)
        assert p.returncode == 2 and placeholder in p.stderr and 'USAGE:' in p.stderr
    p = run(ctx, 'ls', '-l')
    assert p.returncode == 2 and "Found argument '-l'" in p.stderr


def test_vault_lifecycle_registry_and_active_state(ctx):
    parent = ctx['base']
    root = make_vault(ctx, 'A', parent)
    assert (root / '.jot' / 'data').exists()
    assert "name = 'A'" in (root / '.jot' / 'data').read_text()
    p = run(ctx, 'vault')
    assert p.returncode == 0 and p.stdout == '   A\n'
    runtime(ctx, f'entered {B}A{Z}\n', 'en', 'A')
    assert run(ctx, 'vault').stdout == f'👉 {B}A{Z}\n'
    assert run(ctx, 'vault', '-l').stdout == f'👉 {B}A{Z} \t {parent}\n'
    runtime(ctx, f'vault {B}A{Z} renamed to {B}B{Z}\n', 'rename', 'vault', 'A', 'B')
    assert (parent / 'B' / '.jot' / 'data').exists()
    runtime(ctx, f'folder {B}B{Z} removed\n', 'remove', 'vault', 'B')
    runtime(ctx, R + 'error' + Z + ': not inside a vault\n', 'list')


@pytest.mark.parametrize('bad', ['*','\\','/','?','%',':','|','"','<','>','../escape'], ids=['star','backslash','slash','question','percent','colon','pipe','quote','lt','gt','traversal'])
def test_invalid_names_do_not_mutate(ctx, bad):
    p = run(ctx, 'vault', 'V' + bad, ctx['base'])
    assert p.returncode == 0 and p.stderr == '' and p.stdout == R + 'error' + Z + ': invalid name\n'
    assert not (ctx['base'] / ('V' + bad)).exists()


def test_names_note_normalization_and_collisions(ctx):
    root = make_vault(ctx)
    enter(ctx)
    for n in ('under_score-9','A b λ','n.md'):
        runtime(ctx, f'note {B}{n}{Z} created\n', 'note', n)
    assert (root/'n.md').exists() and not (root/'n.md.md').exists()
    runtime(ctx, R+'error'+Z+': a note named n.md already exists in this location\n', 'note', 'n.md')
    runtime(ctx, f'folder {B}A b λ{Z} created\n', 'folder', 'A b λ')
    runtime(ctx, R+'error'+Z+': a folder named A b λ already exists in this location\n', 'folder', 'A b λ')


def test_no_active_vault_errors(ctx):
    expected = R+'error'+Z+': not inside a vault\n'
    for args in [('note','x'),('folder','x'),('list',),('open','x'),('chdir','.'),('remove','note','x'),('rename','note','x','y'),('move','note','x','..')]:
        runtime(ctx, expected, *args)
    runtime(ctx, R+'error'+Z+": vault x doesn't exist\n", 'vmove','folder','x','missing')


def test_navigation_and_recursive_listing(ctx):
    root = make_vault(ctx)
    enter(ctx)
    runtime(ctx, f'folder {B}a{Z} created\n','folder','a')
    runtime(ctx, 'folder changed\n','chdir','a')
    runtime(ctx, f'folder {B}b{Z} created\n','folder','b')
    runtime(ctx, 'folder changed\n','cd','b')
    runtime(ctx, f'note {B}deep{Z} created\n','note','deep')
    assert run(ctx,'list').stdout == f'V > a/b\n└── {B}deep{Z}\n'
    runtime(ctx, R+'error'+Z+': path crosses the bounds of vault\n','chdir','../../..')
    runtime(ctx, R+'error'+Z+': new location is same as old location\n','chdir','.')
    runtime(ctx, 'folder changed\n','chdir','../')
    assert run(ctx,'list','note').stdout == ''
    runtime(ctx, 'folder changed\n','chdir','..')
    assert run(ctx,'list','nt').stdout == ''
    assert (root/'a'/'b'/'deep.md').read_bytes() == b''


def test_filtered_lists_and_aliases(ctx):
    root = make_vault(ctx)
    enter(ctx)
    for n in ('one','two.md'):
        run(ctx,'note',n)
    run(ctx,'folder','docs')
    run(ctx,'chdir','docs')
    run(ctx,'note','nested')
    run(ctx,'chdir','..')
    assert run(ctx,'list','note').stdout == run(ctx,'ls','nt').stdout
    assert run(ctx,'list','folder').stdout == run(ctx,'ls','fd').stdout
    assert 'docs' not in run(ctx,'list','note').stdout
    assert 'nested' not in run(ctx,'list','note').stdout
    assert '.jot' in run(ctx,'list','folder').stdout


def test_rename_remove_and_move_preserve_contents(ctx):
    root = make_vault(ctx)
    enter(ctx)
    run(ctx,'note','old')
    (root/'old.md').write_bytes(b'\x00content\xff')
    runtime(ctx, f'note {B}old{Z} renamed to {B}new name{Z}\n','rename','note','old','new name')
    assert (root/'new name.md').read_bytes() == b'\x00content\xff'
    run(ctx,'folder','dest')
    runtime(ctx,'note new name moved\n','move','note','new name','dest/')
    assert (root/'dest'/'new name.md').read_bytes() == b'\x00content\xff'
    runtime(ctx,'folder changed\n','chdir','dest')
    runtime(ctx, f'note {B}new name{Z} removed\n','rm','nt','new name')
    assert not (root/'dest'/'new name.md').exists()
    runtime(ctx, f'folder {B}dest{Z} removed\n','remove','fd','dest')


def test_vmove_independent_vaults_and_vault_move(ctx):
    parent = ctx['base']
    a = make_vault(ctx,'A',parent)
    b = make_vault(ctx,'B',parent)
    enter(ctx,'A')
    run(ctx,'folder','box')
    run(ctx,'note','inside')
    runtime(ctx, f'note {B}inside{Z} moved to vault {B}B{Z}\n','vm','nt','inside','B')
    assert (b/'inside.md').exists() and not (a/'inside.md').exists()
    destination = ctx['base'] / 'elsewhere'
    destination.mkdir()
    runtime(ctx, f'vault {B}A{Z} moved\n','move','vault','A',destination)
    assert (destination/'A'/'box').is_dir()
    assert 'A' in run(ctx,'vault').stdout


def test_operation_error_precedence_and_collision(ctx):
    root = make_vault(ctx)
    enter(ctx)
    runtime(ctx, R+'error'+Z+': note nope not found\n','remove','note','nope')
    runtime(ctx, R+'error'+Z+': folder nope not found\n','remove','folder','nope')
    runtime(ctx, R+'error'+Z+': new name is same as old name\n','rename','note','missing','missing')
    run(ctx,'note','x')
    run(ctx,'folder','d')
    runtime(ctx, R+'error'+Z+': new location is same as old location\n','move','note','x','.')
    (root/'d'/'x.md').write_text('occupied')
    runtime(ctx, R+'error'+Z+': a note named x already exists in this location\n','move','note','x','d')
