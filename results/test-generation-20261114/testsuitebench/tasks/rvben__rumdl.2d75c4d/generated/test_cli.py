import os


def test_version_forms(run, project):
    for args in (['--version'], ['-V'], ['version'], ['--version', '--help']):
        r = run(args, cwd=project)
        assert r.returncode == 0
        assert r.stdout == b'rumdl 0.1.13\n'


def test_no_args_and_unknown_command_are_usage_errors(run, project):
    r = run([], cwd=project)
    assert r.returncode == 2 and not r.stdout
    assert b'Usage: executable [OPTIONS] <COMMAND>' in r.stderr
    r = run(['not-a-command'], cwd=project)
    assert r.returncode == 2 and b'unrecognized subcommand' in r.stderr
    assert b'Usage: executable [OPTIONS] <COMMAND>' in r.stderr


def test_main_help_lists_commands(run, project):
    r = run(['--help'], cwd=project)
    assert r.returncode == 0
    for command in (b'check', b'fmt', b'init', b'rule', b'explain', b'config',
                    b'server', b'schema', b'import', b'vscode', b'completions', b'clean'):
        assert command in r.stdout


def test_help_dispatch_matches_subcommand_help(run, project):
    for command in ('check', 'fmt', 'init', 'import', 'completions', 'clean', 'vscode'):
        direct = run([command, '--help'], cwd=project)
        via_help = run(['help', command], cwd=project)
        assert direct.returncode == via_help.returncode == 0
        assert direct.stdout == via_help.stdout


def test_invalid_check_enum_is_usage_error(run, project):
    r = run(['check', '--fail-on', 'invalid', '/dev/null'], cwd=project)
    assert r.returncode == 2 and r.stdout == b''
    assert b"invalid value 'invalid'" in r.stderr
    assert b'[possible values: any, warning, error, never]' in r.stderr


def test_conflicting_fix_options_are_rejected(run, project):
    for args in (['check', '--fix', '--check'], ['check', '--check', '--fix']):
        r = run(args, cwd=project)
        assert r.returncode == 2 and not r.stdout
        assert b'--check and --fix cannot be used together' in r.stderr


def test_invalid_format_is_usage_error(run, project):
    r = run(['check', '--output-format', 'invalid', '/dev/null'], cwd=project)
    assert r.returncode == 2 and not r.stdout
    assert b'[possible values: text, full, concise, grouped, json, json-lines' in r.stderr


def test_unknown_rule_identifier_is_not_accepted_as_alias(run, project):
    for value in ('1', 'heading-increment'):
        r = run(['rule', value], cwd=project)
        assert r.returncode == 2 and not r.stdout
        assert f"Rule '{value}' not found.".encode() in r.stderr


def test_completions_list_and_invalid_shell(run, project):
    r = run(['completions', '--list'], cwd=project)
    assert r.returncode == 0 and b'Available shells:' in r.stdout
    assert all(s in r.stdout for s in (b'bash', b'zsh', b'fish', b'powershell', b'elvish'))
    r = run(['completions', 'invalid_shell'], cwd=project)
    assert r.returncode == 2 and not r.stdout
    assert b"invalid value 'invalid_shell'" in r.stderr


def test_completions_without_detectable_shell_fails_cleanly(run, project):
    r = run(['completions'], cwd=project, env={'SHELL': ''})
    assert r.returncode == 2 and not r.stdout
    assert b'Could not detect shell' in r.stderr


def test_config_unknown_query(run, project):
    r = run(['config', 'get', 'nonexistent.key'], cwd=project)
    assert r.returncode == 2 and not r.stdout
    assert r.stderr == b'Unknown config key: nonexistent.key\n'


def test_config_file_without_config(run, project):
    r = run(['config', 'file', '--isolated'], cwd=project)
    assert r.returncode == 0
    assert r.stdout == b'No configuration file loaded (--no-config/--isolated specified)\n'
