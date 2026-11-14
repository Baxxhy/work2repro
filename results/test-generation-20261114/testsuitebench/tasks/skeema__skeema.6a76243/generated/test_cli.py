import os, re, subprocess
from pathlib import Path
import pytest

EXE = Path('/workspace/executable')

def run(args=(), cwd=None, env=None, data=None):
    e = os.environ.copy(); e['MYSQL_PWD']='test-secret'; e['HOME']=str((Path(cwd) if cwd else Path('/tmp')).resolve())
    if env: e.update(env)
    return subprocess.run([str(EXE), *map(str,args)], cwd=cwd, env=e, input=data, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)

def clean_stderr(s):
    return re.sub(r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', '', s)

@pytest.mark.parametrize('args', [(), ('help',), ('--help',), ('-?',)], ids=['empty','help','long-help','question-help'])
def test_main_help_identical(args):
    p=run(args)
    assert p.returncode == 0 and p.stdout.startswith('\nUsage:  skeema') and p.stdout.endswith('https://www.skeema.io/docs/commands\n\n')
    assert 'Commands:\n' in p.stdout and 'Global Options:\n' in p.stdout and p.stderr == ''

def test_version_format_and_precedence():
    for args in [('version',),('--version',),('format','--version')]:
        p=run(args)
        assert p.returncode == 0 and re.fullmatch(r'skeema version 1\.13\.2-community, commit [0-9a-f]{7,}, released \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\n',p.stdout)
        assert p.stderr == ''

def test_debug_version_both_orders():
    for args in [('--debug','version'),('version','--debug')]:
        p=run(args); assert p.returncode == 0 and p.stdout.startswith('skeema version 1.13.2-community,')
        assert '[DEBUG] Exit code 0 (SUCCESS)' in clean_stderr(p.stderr)

def test_unknown_command_diagnostic():
    for args in [('unknown-cmd',),('--debug','unknown-cmd')]:
        p=run(args); assert p.returncode == 78
        assert clean_stderr(p.stderr).strip().endswith('[ERROR] Unknown command "unknown-cmd"')

def test_global_parser_unknown_and_missing_values():
    cases=[(['--bogus'],78,'Unknown option "bogus"'),(['--user'],78,'Missing required value for option user'),(['-vh'],78,'Unknown option "v"')]
    for args,code,msg in cases:
        p=run(args); assert p.returncode==code and msg in clean_stderr(p.stderr)

def test_lone_required_short_option_quirk():
    p=run(['-u','version']); assert p.returncode==0 and p.stdout.startswith('\nUsage:  skeema')

def test_password_is_optional_value_and_secret_not_logged():
    p=run(['--password=topsecret','--debug','version'])
    assert p.returncode==0 and 'topsecret' not in p.stdout+p.stderr
    p=run(['--password','version'],data='')
    assert p.returncode==78 and 'Enter password:' in p.stderr and 'STDIN must be a TTY' in p.stderr and 'version' not in p.stdout

def test_help_unknown_target_and_version_help():
    p=run(['help','not-a-command']); assert p.returncode==2 and 'Unknown command "not-a-command"' in clean_stderr(p.stderr)
    for args in [('version','help'),('version','--help'),('--help=version')]:
        p=run(args); assert p.returncode==0 and p.stderr=='' and p.stdout.startswith('\nUsage:  skeema version [<options>]') and p.stdout.endswith('/commands/version\n\n')

@pytest.mark.parametrize('cmd,sections', [('init',['Init Options:','--schema','--strip-partitioning']),('diff',['External Tool Options:','SQL Generation Options:','Safety Options:','Sharding Options:']),('pull',['Pull Options:','--skip-new-schemas']),('format',['Format Options:','--skip-write']),('lint',['Linter Rule Options:','--lint-pk']),('push',['--dry-run','--foreign-key-checks'])],ids=['init','diff','pull','format','lint','push'])
def test_command_help_includes_documented_options(cmd,sections):
    p=run(['help',cmd]); assert p.returncode==0 and p.stderr=='' and p.stdout.startswith('\nUsage:  skeema '+cmd) and p.stdout.endswith('/commands/'+cmd+'\n\n')
    for part in sections: assert part in p.stdout

def test_host_schema_cli_placement_rejected():
    expected='The host option cannot be set via command line for this command.'
    for args in [['diff','--host','x'],['--host','x','diff'],['diff','--host=x','--schema','s']]:
        p=run(args); assert p.returncode==78 and expected in clean_stderr(p.stderr)
    p=run(['diff','--schema','s']); assert p.returncode==78 and 'schema option cannot be set' in clean_stderr(p.stderr)

def test_invalid_ignore_regex_short_circuits():
    for opt,pat in [('ignore-table','+'),('ignore-proc','***')]:
        p=run(['diff',f'--{opt}',pat]); assert p.returncode==78 and f'Invalid regexp for option {opt}: {pat}' in clean_stderr(p.stderr)

def test_ssl_mode_validation_and_empty_value_reaches_connection(tmp_path):
    p=run(['diff','--ssl-mode','verify-ca'],tmp_path); assert p.returncode==78 and 'Invalid connection options: Option ssl-mode' in clean_stderr(p.stderr)
    p=run(['diff','--ssl-mode='],tmp_path); assert p.returncode in (0,2) and 'Invalid connection options: Option ssl-mode' not in clean_stderr(p.stderr)

def test_skip_my_cnf_deprecation():
    p=run(['push','--skip-my-cnf']); assert p.returncode==0 and 'Option --my-cnf is deprecated.' in clean_stderr(p.stderr)

@pytest.mark.parametrize('value,detail', [('no_value','Option no_value is missing a value'),('opt=val,','Invalid comma placement in option value'),("opt='unterminated",'Unterminated quote in connect-options'),('autocommit=true','connect-options is not allowed to contain autocommit')],ids=['missing-pair','trailing-comma','unclosed-value','reserved-key'])
def test_bad_connect_options(value,detail):
    p=run(['diff','--connect-options',value]); assert p.returncode==78 and detail in clean_stderr(p.stderr)

def test_connect_options_tls_conflict():
    p=run(['diff','--connect-options','tls=preferred','--ssl-mode=required']); assert p.returncode==78 and 'should not also set the tls field' in clean_stderr(p.stderr)

@pytest.mark.parametrize('args,expected', [(['push','--debug'],'[DEBUG] Exit code 0 (SUCCESS)'),(['push','--temp-schema-binlog=off'],'Option --temp-schema-binlog is deprecated'),(['push','--lint-display-width=warning'],'Option --lint-display-width is deprecated'),(['push','--temp-schema-threads=3'],'Option --temp-schema-threads is deprecated')],ids=['debug','binlog-alias','deprecated-lint','deprecated-threads'])
def test_push_empty_directory_and_compatibility(args,expected,tmp_path):
    p=run(args,tmp_path); assert p.returncode==0 and expected in clean_stderr(p.stderr)

def test_mapped_diff_missing_host_warns_after_parse(tmp_path):
    (tmp_path/'.skeema').write_text('schema=mydb\n')
    p=run(['diff'],tmp_path); s=clean_stderr(p.stderr)
    assert p.returncode==0 and 'no host defined for environment "production"' in s and 'This command requires a hostname' in s

def test_diff_no_schema_for_selected_environment(tmp_path):
    (tmp_path/'.skeema').write_text('[production]\nschema=mydb\n')
    p=run(['diff','staging'],tmp_path); s=clean_stderr(p.stderr)
    assert p.returncode==0 and 'no schema defined for environment "staging"' in s and 'Other environments do define a schema name.' in s

def test_pull_mapped_tcp_refusal(tmp_path):
    (tmp_path/'.skeema').write_text('host=127.0.0.1\nport=3306\nschema=mydb\n')
    p=run(['pull','--skip-new-schemas'],tmp_path); s=clean_stderr(p.stderr)
    assert p.returncode==1 and 'Unable to connect to 127.0.0.1:3306' in s and 'connect: connection refused' in s

def test_diff_mapped_tcp_refusal(tmp_path):
    (tmp_path/'.skeema').write_text('host=127.0.0.1\nport=3306\nschema=mydb\n')
    p=run(['diff'],tmp_path); s=clean_stderr(p.stderr)
    assert p.returncode==2 and 'Skipping 127.0.0.1:3306' in s and 'connect: connection refused' in s and 'Skipped 1 operation due to problem' in s

def test_malformed_config_reports_line_and_stops(tmp_path):
    (tmp_path/'.skeema').write_text('[production\nschema=x\n')
    p=run(['diff'],tmp_path); assert p.returncode==78 and '.skeema line 1: unterminated section name' in clean_stderr(p.stderr)

def test_child_config_inherits_parent_connection(tmp_path):
    (tmp_path/'.skeema').write_text('host=127.0.0.1\n')
    child=tmp_path/'child'; child.mkdir(); (child/'.skeema').write_text('schema=db\nport=3307\n')
    p=run(['diff'],tmp_path); s=clean_stderr(p.stderr)
    assert p.returncode==2 and '127.0.0.1:3307' in s

def test_unmapped_sql_child_ignored(tmp_path):
    (tmp_path/'.skeema').write_text('host=127.0.0.1\nschema=rootdb\n')
    child=tmp_path/'not_a_schema'; child.mkdir(); (child/'table.sql').write_text('CREATE TABLE t (id int);\n')
    p=run(['diff'],tmp_path); assert p.returncode==2 and 'not_a_schema' not in clean_stderr(p.stderr)

def test_lint_empty_directory_heading(tmp_path):
    p=run(['lint'],tmp_path); assert p.returncode==0 and 'Linting '+str(tmp_path) in clean_stderr(p.stderr)

def test_format_empty_and_empty_environment(tmp_path):
    p=run(['format',''],tmp_path); assert p.returncode==0 and 'Reformatting '+str(tmp_path) in clean_stderr(p.stderr)

def test_format_check_only_heading(tmp_path):
    p=run(['format','--skip-write'],tmp_path); assert p.returncode==0 and 'Checking format of '+str(tmp_path) in clean_stderr(p.stderr)

def test_lint_invalid_severity_sequence(tmp_path):
    (tmp_path/'.skeema').write_text('host=localhost\nschema=db\nlint-pk=invalid_value\n')
    p=run(['lint'],tmp_path); s=clean_stderr(p.stderr)
    assert p.returncode==78 and 'Linting '+str(tmp_path) in s and 'Option lint-pk can only be set to one of these values' in s and 'Skipped 1 operation due to fatal errors' in s

def test_lint_missing_workspace_inputs(tmp_path):
    (tmp_path/'.skeema').write_text('schema=db\n')
    p=run(['lint'],tmp_path); s=clean_stderr(p.stderr)
    assert p.returncode==78 and 'Linting '+str(tmp_path) in s and 'needs either a host (with workspace=temp-schema) or flavor' in s

def test_sql_lexical_error_precedes_missing_host(tmp_path):
    (tmp_path/'.skeema').write_text('schema=db\n')
    (tmp_path/'a.sql').write_text('/* never closed')
    p=run(['diff'],tmp_path); assert p.returncode==2 and 'Comment starting with /* is never closed' in clean_stderr(p.stderr) and 'no host defined' not in clean_stderr(p.stderr)

def test_duplicate_create_detected_with_lines(tmp_path):
    (tmp_path/'.skeema').write_text('schema=db\n')
    (tmp_path/'a.sql').write_text('CREATE TABLE t (id int);\n')
    (tmp_path/'b.sql').write_text('\nCREATE TABLE t (id int);\n')
    p=run(['diff'],tmp_path); s=clean_stderr(p.stderr)
    assert p.returncode==2 and 'table `t` defined multiple times in same directory' in s and 'a.sql line 1' in s and 'b.sql line 2' in s

def test_non_sql_files_and_unmapped_descendant_noop(tmp_path):
    (tmp_path/'notes.txt').write_text('not sql;')
    p=run(['pull'],tmp_path); assert p.returncode==0 and p.stderr==''

def test_init_requires_host_and_empty_host_destination(tmp_path):
    p=run(['init'],tmp_path); assert p.returncode==78 and 'Option --host must be supplied on the command-line' in clean_stderr(p.stderr)
    p=run(['init',"--host="],tmp_path); assert p.returncode==73 and 'Cannot create dir : mkdir : no such file or directory' in clean_stderr(p.stderr)

def test_init_creates_destination_before_connection_failure(tmp_path):
    dest=tmp_path/'nested dir'/'schema'
    p=run(['init','--host','127.0.0.1','--port','3306','--dir',dest],tmp_path)
    assert p.returncode==2 and dest.is_dir() and 'Unable to connect to 127.0.0.1:3306' in clean_stderr(p.stderr)

def test_init_existing_destination_collision(tmp_path):
    dest=tmp_path/'already'; dest.mkdir(); (dest/'.skeema').write_text('')
    p=run(['init','--host','127.0.0.1','--dir',dest],tmp_path)
    assert p.returncode==78 and 'already has .skeema file' in clean_stderr(p.stderr)

def test_add_environment_requires_operand_without_mutation(tmp_path):
    original='[production]\nhost=localhost\nschema=db\n'; (tmp_path/'.skeema').write_text(original)
    p=run(['add-environment','--host','127.0.0.1'],tmp_path)
    assert p.returncode==78 and 'requires at least 1 args' in clean_stderr(p.stderr) and (tmp_path/'.skeema').read_text()==original
