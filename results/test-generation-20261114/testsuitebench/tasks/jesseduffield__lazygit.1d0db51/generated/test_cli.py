import json
import os
import re
import subprocess
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent
EXE = Path('/workspace/executable')
HELP = (EVAL / 'help.txt').read_text()
CONFIG = (EVAL / 'config.yaml').read_text()


def invoke(*args, cwd=None, env=None, input=None, timeout=5):
    child_env = os.environ.copy()
    child_env.pop('GIT_DIR', None)
    child_env.pop('GIT_WORK_TREE', None)
    child_env.pop('LG_CONFIG_FILE', None)
    child_env.update({'TERM': 'xterm-256color', 'HOME': str(EVAL), 'XDG_CONFIG_HOME': str(EVAL / 'xdg')})
    if env:
        child_env.update({k: str(v) for k, v in env.items()})
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd or EVAL, env=child_env,
                          input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout)


def txt(data):
    return data.decode('utf-8', errors='replace')


def repo(path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'init', '-q', str(path)], check=True)
    subprocess.run(['git', '-C', str(path), 'config', 'user.email', 'eval@example.test'], check=True)
    subprocess.run(['git', '-C', str(path), 'config', 'user.name', 'Eval'], check=True)
    return path


def test_help_long_and_short_are_exact():
    for flag in ('--help', '-h'):
        p = invoke(flag)
        assert p.returncode == 0 and p.stdout == b'' and txt(p.stderr) == HELP
        assert b'Commands:' not in p.stderr and b'\x1b' not in p.stderr


def test_help_dispatch_precedes_invalid_later_option_and_accepts_panel():
    a = invoke('status', '--help')
    b = invoke('--help', '--unknown=value')
    assert (a.returncode, a.stdout, txt(a.stderr)) == (0, b'', HELP)
    assert (b.returncode, b.stdout, txt(b.stderr)) == (0, b'', HELP)


def test_version_shape_is_stable_and_alias_matches():
    a, b = invoke('--version'), invoke('-v')
    assert a.returncode == b.returncode == 0
    assert a.stderr == b.stderr == b'' and a.stdout == b.stdout
    line = txt(a.stdout)
    assert line.endswith('\n') and line.count('\n') == 1
    fields = line[:-1].split(', ')
    assert [x.split('=', 1)[0] for x in fields] == ['commit', 'build date', 'build source', 'version', 'os', 'arch', 'git version']
    values = [x.split('=', 1)[1] for x in fields]
    assert all(values)
    assert re.fullmatch(r'[0-9a-fA-F]+', values[0])
    assert re.fullmatch(r'[0-9a-fA-F.]+', values[3])


def test_version_precedes_invalid_panel_and_invalid_config():
    bad = EVAL / 'missing config for version'
    p = invoke('badpanel', '--use-config-file', bad, '--version', cwd=EVAL)
    assert p.returncode == 0 and p.stderr == b'' and p.stdout.startswith(b'commit=')


def test_config_output_is_exact_even_with_bad_override():
    bad = EVAL / 'malformed-config.yml'
    bad.write_text('not: [valid')
    for args in [('--config',), ('-c',), ('--use-config-file', bad, '--config'), ('--config', '--use-config-dir', EVAL / 'elsewhere')]:
        p = invoke(*args)
        assert p.returncode == 0 and p.stderr == b'' and txt(p.stdout) == CONFIG


def test_config_dir_default_and_explicit_override():
    p = invoke('--print-config-dir')
    assert p.returncode == 0 and p.stderr == b''
    assert txt(p.stdout) == str(EVAL / 'xdg' / 'lazygit') + '\n'
    custom = EVAL / 'config-home' / 'custom///'
    p = invoke('-cd', '--use-config-dir', custom)
    assert p.returncode == 0 and p.stderr == b''
    assert txt(p.stdout) == str(custom).rstrip('/') + '\n'


def test_config_dir_env_and_legacy_search_precedence():
    explicit = EVAL / 'env-config-dir'
    p = invoke('-cd', env={'CONFIG_DIR': explicit})
    assert p.returncode == 0 and txt(p.stdout) == str(explicit) + '\n'
    xdg_home, xdg_system = EVAL / 'xh', EVAL / 'xs'
    legacy = xdg_system / 'jesseduffield' / 'lazygit' / 'config.yml'
    legacy.parent.mkdir(parents=True, exist_ok=True); legacy.write_text('')
    newer = xdg_home / 'jesseduffield' / 'lazygit' / 'config.yml'
    newer.parent.mkdir(parents=True, exist_ok=True); newer.write_text('')
    p = invoke('-cd', env={'XDG_CONFIG_HOME': xdg_home, 'XDG_CONFIG_DIRS': str(xdg_system)})
    assert p.returncode == 0 and txt(p.stdout) == str(legacy.parent) + '\n'


@pytest.mark.parametrize('flag', ['-v', '--version', '-c', '--config', '-cd', '--print-config-dir'], ids=['v-short','v-long','config-short','config-long','dir-short','dir-long'])
def test_information_modes_work_outside_repository(flag):
    p = invoke(flag, cwd=EVAL)
    assert p.returncode == 0 and p.stderr == b'' and p.stdout


@pytest.mark.parametrize('args, fragment', [
    (('--unknown',), 'Expected a following arg for flag --unknown'),
    (('--unknown=x',), 'Unknown flag: --unknown'),
    (('--filter',), 'Expected a following arg for flag -f'),
    (('--screen-mode',), 'Expected a following arg for flag -sm'),
    (('-dv',), 'Unknown flag'),
    (('one', 'two'), 'Unexpected argument: two'),
], ids=['unknown-long','unknown-equals','missing-filter','missing-screen','combined-short','two-positionals'])
def test_syntax_errors_have_usage(args, fragment):
    p = invoke(*args)
    assert p.returncode == 2 and p.stdout == b''
    err = txt(p.stderr)
    assert fragment in err and 'Usage:' in err and 'Flags:' in err


@pytest.mark.parametrize('arg', ['badpanel', 'branchy'], ids=['badpanel','similar-name'])
def test_invalid_panel_is_runtime_error(arg):
    p = invoke(arg)
    assert p.returncode == 1 and p.stdout == b''
    assert re.search(r'\d{4}/\d\d/\d\d \d\d:\d\d:\d\d Invalid git arg value:', txt(p.stderr))
    assert arg in txt(p.stderr) and 'status, branch, log, stash' in txt(p.stderr)


@pytest.mark.parametrize('arg', ['-', ''], ids=['dash','empty'])
def test_empty_parser_key_panics_without_usage(arg):
    p = invoke(arg)
    assert p.returncode == 2 and p.stdout == b''
    assert txt(p.stderr).startswith('panic: cant add parsed value with no key or value')
    assert 'Usage:' not in txt(p.stderr)


def test_path_validation_unicode_spaces_and_conflict():
    root = EVAL / 'repos with spaces' / '例'
    repo(root)
    good = invoke('--path', root, '--version')
    assert good.returncode == 0 and good.stderr == b''
    missing = EVAL / 'absent repo 例'
    bad = invoke('-p', missing, '--version')
    assert bad.returncode == 1 and bad.stdout == b'' and str(missing) in txt(bad.stderr)
    incompatible = invoke('--path', root, '--work-tree', root, '--version')
    assert incompatible.returncode == 1 and '--path option is incompatible' in txt(incompatible.stderr)


def test_work_tree_missing_is_reported():
    missing = EVAL / 'no work tree'
    p = invoke('--work-tree', missing, '--version')
    assert p.returncode == 1 and p.stdout == b'' and f'Failed to change directory to {missing}' in txt(p.stderr)


def test_config_yaml_parse_error_and_missing_later_file():
    malformed = EVAL / 'bad yaml.yml'; malformed.write_text('one: x\ntwo: y\nthree [\n')
    p = invoke('--use-config-file', malformed)
    assert p.returncode != 0 and re.search(r'\d{4}/\d\d/\d\d \d\d:\d\d:\d\d ', txt(p.stderr))
    absent = EVAL / 'missing second ü.yml'
    valid = EVAL / 'first good.yml'; valid.write_text('gui:\n  showRandomTip: false\n')
    p = invoke('--use-config-file', f'{valid},{absent}')
    assert p.returncode != 0 and str(absent) in txt(p.stderr)


def test_invalid_config_enum_rejected_but_config_mode_bypasses():
    cfg = EVAL / 'invalid enum.yml'; cfg.write_text('gui:\n  statusPanelView: nope\n')
    p = invoke('--use-config-file', cfg)
    assert p.returncode != 0 and 'gui.statusPanelView' in txt(p.stderr) and 'nope' in txt(p.stderr)
    p = invoke('--use-config-file', cfg, '--config')
    assert p.returncode == 0 and txt(p.stdout) == CONFIG and p.stderr == b''


def test_explicit_config_file_supersedes_environment_file():
    bad = EVAL / 'env invalid.yml'; bad.write_text('gui:\n  statusPanelView: nope\n')
    good = EVAL / 'env valid.yml'; good.write_text('gui:\n  showRandomTip: false\n')
    p = invoke('--use-config-file', good, env={'LG_CONFIG_FILE': bad})
    # Interactive startup reaches terminal initialization; valid config must not fail validation.
    assert p.returncode != 0 and 'gui.statusPanelView' not in txt(p.stderr)


def test_daemon_kind_one_accepts_object_instruction():
    p = invoke(env={'LAZYGIT_DAEMON_KIND': '1', 'LAZYGIT_DAEMON_INSTRUCTION': '{"unknown":true}'})
    assert p.returncode == 0 and p.stdout == b'' and p.stderr == b''


def test_help_and_version_precede_daemon_dispatch():
    env = {'LAZYGIT_DAEMON_KIND': '1', 'LAZYGIT_DAEMON_INSTRUCTION': '{"unknown":true}'}
    p = invoke('--help', env=env)
    assert p.returncode == 0 and txt(p.stderr) == HELP and p.stdout == b''
    p = invoke('--version', env=env)
    assert p.returncode == 0 and p.stderr == b'' and p.stdout.startswith(b'commit=')


def test_debug_log_is_json_append_only_and_custom_path():
    log = EVAL / 'state' / 'nested' / 'debug.jsonl'
    log.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        invoke('--debug', env={'LAZYGIT_LOG_PATH': log})
    rows = [json.loads(x) for x in log.read_text().splitlines()]
    assert len(rows) >= 2 and all({'level','msg','time'} <= row.keys() for row in rows)
    assert any('command' in row for row in rows)
    assert all(row['level'] and row['time'] for row in rows)


def test_debug_custom_log_does_not_create_parent():
    log = EVAL / 'absent-parent' / 'debug.log'
    p = invoke('--debug', env={'LAZYGIT_LOG_PATH': log})
    assert p.returncode != 0 and 'Unable to log to log file' in txt(p.stderr)
    assert not log.parent.exists()


def test_no_terminal_startup_reports_terminal_error():
    env = {'TERM': '', 'LAZYGIT_LOG_PATH': EVAL / 'term-error.log'}
    p = invoke(env=env)
    assert p.returncode == 1 and 'terminal entry not found: term not set' in txt(p.stderr)
