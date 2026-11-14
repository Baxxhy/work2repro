import os
import subprocess
from pathlib import Path

EXE = Path('/workspace/executable')


def run(*args, env=None, input=None):
    e = os.environ.copy()
    for k in ('CHAMBER_SECRET_BACKEND','CHAMBER_S3_BUCKET','CHAMBER_KMS_KEY_ALIAS','CHAMBER_RETRIES','AWS_REGION','CHAMBER_AWS_SSM_ENDPOINT','CHAMBER_AWS_SECRETS_MANAGER_ENDPOINT','AWS_ENDPOINT_URL'):
        e.pop(k, None)
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *map(str,args)], input=input, text=True, capture_output=True, env=e)


def test_version_exact_and_backend_independent():
    p=run('version','ignored','--backend','bad',env={'CHAMBER_SECRET_BACKEND':'invalid'})
    assert (p.returncode,p.stdout,p.stderr)==(0,'chamber dev\n','')


def test_version_can_follow_consumed_option():
    p=run('--backend','list','version')
    assert (p.returncode,p.stdout,p.stderr)==(0,'chamber dev\n','')


def test_no_args_is_help():
    p=run()
    assert p.returncode==0 and p.stdout.startswith('CLI for storing secrets\n\nUsage:\n') and p.stdout.endswith('Use "chamber [command] --help" for more information about a command.\n') and p.stderr==''


def test_help_aliases():
    for args in [('-h',),('--help',),('help',)]:
        p=run(*args)
        assert p.returncode==0 and p.stdout.startswith('CLI for storing secrets\n') and p.stderr==''


def test_version_help():
    p=run('help','version')
    assert p.returncode==0 and 'print version\n\nUsage:\n  chamber version [flags]' in p.stdout and 'Global Flags:\n' in p.stdout and p.stderr==''


def test_leaf_help_has_global_flags():
    p=run('find','--help')
    assert p.returncode==0 and 'Find the given secret across all services\n\nUsage:\n  chamber find <secret name> [flags]' in p.stdout
    assert '  -v, --by-value   Find parameters by value\n' in p.stdout and 'Global Flags:\n' in p.stdout and p.stderr==''


def test_tag_group_help_and_unknown_subcommand_succeed():
    for args in [('tag',),('tag','bogus')]:
        p=run(*args)
        assert p.returncode==0 and 'work with tags on secrets' in p.stdout and 'Use "chamber tag [command] --help"' in p.stdout
        assert p.stderr==''


def test_unknown_command_exact():
    p=run('no-such-command')
    assert p.returncode==1 and p.stdout=='' and p.stderr=='Error: unknown command "no-such-command" for "chamber"\nRun \'chamber --help\' for usage.\n'


def test_unknown_flag_rejected_even_with_help():
    p=run('--does-not-exist','--help')
    assert p.returncode==1 and p.stdout=='' and 'unknown flag: --does-not-exist' in p.stderr


def test_version_flag_is_not_root_option():
    p=run('--version')
    assert p.returncode==1 and 'unknown flag: --version' in p.stderr


def test_root_options_accept_equals_and_boolean_false():
    p=run('find','--backend=null','--by-value=false','anything')
    assert p.returncode==0 and p.stdout=='Service\n' and p.stderr==''


def test_null_backend_empty_commands():
    cases=[(('list','svc'), 'Key\tVersion\t\tLastModified\tUser\n'),(('list-services',),'Service\n'),(('history','svc','key'),'Event\tVersion\t\tDate\tUser\n'),(('find','term'),'Service\n'),(('find','--by-value','term'),'Service\t\tKey\n'),(('export','svc'),'{}\n'),(('env','svc'),'')]
    for args,out in cases:
        p=run(*args,'--backend=null')
        assert (p.returncode,p.stdout,p.stderr)==(0,out,'')


def test_null_list_services_ignores_extra_positionals():
    for args in [('list-services','a','b'),('list-services','a','b','c','d')]:
        p=run(*args,'--backend=null')
        assert (p.returncode,p.stdout,p.stderr)==(0,'Service\n','')


def test_list_services_prefix_is_unvalidated():
    for prefix in ['', '/a// ', '☃\\!:x']:
        p=run('list-services',prefix,'--backend=null')
        assert (p.returncode,p.stdout,p.stderr)==(0,'Service\n','')


def test_invalid_backend_operational_and_export_context():
    p=run('list','svc','--backend','not-real')
    assert p.returncode==1 and p.stdout=='' and p.stderr=='Error: Failed to get secret store: invalid backend `NOT-REAL`\n'
    p=run('export','svc','--backend=not-real')
    assert p.returncode==1 and p.stdout=='' and p.stderr=='Error: invalid backend `NOT-REAL`\n'


def test_empty_environment_backend_is_invalid():
    p=run('list','svc',env={'CHAMBER_SECRET_BACKEND':''})
    assert p.returncode==1 and p.stderr=='Error: Failed to get secret store: invalid backend ``\n'


def test_explicit_backend_overrides_invalid_environment():
    p=run('list','svc','--backend=null',env={'CHAMBER_SECRET_BACKEND':'bad'})
    assert (p.returncode,p.stdout,p.stderr)==(0,'Key\tVersion\t\tLastModified\tUser\n','')


def test_null_ignores_invalid_retry_mode():
    p=run('list','svc','--backend=null','--retry-mode=garbage')
    assert (p.returncode,p.stdout,p.stderr)==(0,'Key\tVersion\t\tLastModified\tUser\n','')


def test_ssm_retry_configuration_errors():
    p=run('list','svc','--backend=ssm','--retry-mode=garbage')
    assert p.returncode==1 and p.stdout=='' and 'Invalid retry mode garbage' in p.stderr
    p=run('list','svc','--backend=ssm',env={'CHAMBER_RETRIES':'nope'})
    assert p.returncode==1 and p.stderr=='Error: Failed to get secret store: Cannot parse $CHAMBER_RETRIES to an integer.\n'


def test_s3_requires_bucket():
    for backend in ('s3','s3-kms'):
        p=run('list','svc','--backend='+backend)
        assert p.returncode==1 and p.stdout=='' and p.stderr=='Error: Failed to get secret store: Must set bucket for s3 backend\n'


def test_explicit_kms_alias_backend_rules():
    p=run('list','svc','--backend=ssm','--kms-key-alias=x')
    assert p.returncode==1 and p.stderr=='Error: Failed to get secret store: Unable to use --kms-key-alias with this backend. Use CHAMBER_KMS_KEY_ALIAS instead.\n'
    p=run('list','svc','--backend=s3','--backend-s3-bucket=b','--kms-key-alias=x')
    assert p.returncode==1 and p.stderr=='Error: Failed to get secret store: Unable to use --kms-key-alias with this backend.\n'
    p=run('list','svc','--backend=null','--kms-key-alias=x')
    assert (p.returncode,p.stdout,p.stderr)==(0,'Key\tVersion\t\tLastModified\tUser\n','')


def test_cardinality_fails_before_backend():
    cases=[(('list',),'accepts 1 arg(s), received 0'),(('list','a','b'),'accepts 1 arg(s), received 2'),(('read','svc'),'accepts 2 arg(s), received 1'),(('delete','svc','k','x'),'accepts 2 arg(s), received 3'),(('write','svc','k'),'accepts 3 arg(s), received 2'),(('import','svc'),'accepts 2 arg(s), received 1'),(('tag','read','svc'),'accepts 2 arg(s), received 1'),(('tag','write','svc','key'),'requires at least 3 arg(s), only received 2')]
    for args,msg in cases:
        p=run(*args,'--backend=null')
        assert p.returncode==1 and p.stdout=='' and msg in p.stderr


def test_list_services_initializes_backend_even_with_extra_args():
    p=run('list-services','a','b','--backend=bad')
    assert p.returncode==1 and p.stderr=='Error: Failed to get secret store: invalid backend `BAD`\n'


def test_service_validation_ordinary_and_label_capable():
    bad="Error: Failed to validate service: Failed to validate service name 'app:dev'. Only alphanumeric, dashes, forward slashes, full stops and underscores are allowed for service names. Service names must not start or end with a forward slash"
    p=run('read','app:dev','key','--backend=null')
    assert p.returncode==1 and p.stderr.startswith(bad)
    for name in ('top/app:QA_1','a/b:x:y'):
        p=run('list',name,'--backend=null')
        assert p.returncode==0 and p.stdout.startswith('Key\t')
    for name in ('app:dev','a:.x-y','a/b:x/z','a/b:'):
        p=run('list',name,'--backend=null')
        assert p.returncode==1 and 'Failed to validate service' in p.stderr


def test_service_validation_accepts_permitted_segment_chars():
    for name in ('_chamber','...','9_a-b.c','a//b','/a','a/'):
        p=run('read',name,'key','--backend=null')
        if name=='_chamber':
            assert p.returncode==1 and 'reserved for chamber' in p.stderr and 'Failed to read' in p.stderr
        else:
            assert p.returncode==1 and 'Failed to validate service' in p.stderr


def test_key_validation_and_normalized_storage_key_rules():
    p=run('read','svc','bad/key','--backend=null')
    assert p.returncode==1 and "Failed to validate key name 'bad/key'" in p.stderr
    for key in ('_x','.x','-x','9x','A-b.C'):
        p=run('read','svc',key,'--backend=null')
        assert p.returncode==1 and 'Not implemented for Null Store' in p.stderr


def test_null_mutation_and_point_read_errors():
    for args,expected in [(('write','s','k','v'),'Error: Write is not implemented for Null Store'),(('write','s','k','v','--tags','a=b'),'Error: WriteWithTags is not implemented for Null Store'),(('read','s','k'),'Error: Failed to read: Not implemented for Null Store'),(('delete','s','k'),'Error: Not implemented for Null Store'),(('tag','read','s','k'),'Error: Failed to read tags: Not implemented for Null Store'),(('tag','write','s','k','x=y'),'Error: Failed to write tags: Not implemented for Null Store'),(('tag','delete','s','k','x'),'Error: Failed to delete tags: Not implemented for Null Store')]:
        p=run(*args,'--backend=null')
        assert p.returncode==1 and p.stdout=='' and p.stderr==expected+'\n'


def test_read_integer_option_errors():
    p=run('read','s','k','-v','abc','--backend=null')
    assert p.returncode==1 and 'invalid argument "abc" for "-v, --version" flag' in p.stderr and 'strconv.ParseInt' in p.stderr


def test_unknown_local_flag_and_no_quiet_on_tags():
    p=run('find','term','--bogus')
    assert p.returncode==1 and 'unknown flag: --bogus' in p.stderr
    p=run('tag','read','s','k','--quiet')
    assert p.returncode==1 and 'unknown flag: --quiet' in p.stderr


def test_find_search_terms_are_not_validated():
    for term in ('','a/b','☃\n$HOME'):
        p=run('find',term,'--backend=null')
        assert (p.returncode,p.stdout,p.stderr)==(0,'Service\n','')


def test_null_export_formats_and_unsupported_format():
    for fmt in ('json','yaml'):
        p=run('export','svc','--format='+fmt,'--backend=null')
        assert p.returncode==0 and p.stdout.strip() in ('{}','') and p.stderr==''
    for fmt in ('csv','tsv','dotenv','tfvars','java-properties','properties'):
        p=run('export','svc','--format='+fmt,'--backend=null')
        assert (p.returncode,p.stdout,p.stderr)==(0,'','')
    p=run('export','svc','--format=xml','--backend=null')
    assert p.returncode==1 and p.stderr=='Error: Unable to export parameters: Unsupported export format: xml\n'


def test_write_dash_reads_stdin_and_singleline_eof_contract():
    p=run('write','s','k','-','--backend=null',input='value')
    assert p.returncode==1 and p.stderr=='Error: EOF\n'
    p=run('write','s','k','-','--singleline','--backend=null',input='first\nignored\n')
    assert p.returncode==1 and p.stderr=='Error: Write is not implemented for Null Store\n'


def test_write_accepts_leading_dash_value_after_separator():
    p=run('write','s','k','--','-leading','--backend=null')
    assert p.returncode==1 and 'Write is not implemented for Null Store' in p.stderr


def test_exec_requires_separator_and_reports_usage():
    p=run('exec','svc','/bin/true','--backend=null')
    assert p.returncode==1 and p.stdout=='' and p.stderr.startswith("Error: please separate services and command with '--'. See usage\nUsage:")


def test_exec_missing_service_and_command_errors():
    p=run('exec','--','/bin/true','--backend=null')
    assert p.returncode==1 and p.stderr.startswith('Error: at least one service must be specified: requires at least 1 arg(s), only received 0\n')
    p=run('exec','svc','--','--backend=null')
    assert p.returncode==1 and p.stderr.startswith('Error: must specify command to run. See usage: requires at least 1 arg(s), only received 0\n')


def test_exec_is_transparent_and_preserves_arguments_and_exit_code():
    p=run('exec','svc','--backend=null','--','/usr/bin/python3','-c','import sys; print(repr(sys.argv[1:])); sys.exit(42)','a b','','雪')
    assert p.returncode==42 and p.stdout=="['a b', '', '雪']\n" and p.stderr==''


def test_exec_resolves_path_and_reports_missing_command():
    p=run('exec','svc','--backend=null','--','chamber-no-such-command-xyz')
    assert p.returncode==1 and p.stdout=='' and 'executable file not found in $PATH' in p.stderr


def test_exec_pristine_removes_inherited_custom_environment():
    p=run('exec','svc','--pristine','--backend=null','--','/usr/bin/python3','-c','import os; print(os.getenv("EVAL_PRIVATE", "MISSING"))',env={'EVAL_PRIVATE':'present'})
    assert p.returncode==0 and p.stdout=='MISSING\n' and p.stderr==''


def test_strict_without_sentinel_succeeds():
    p=run('exec','svc','--strict','--backend=null','--','/usr/bin/python3','-c','print("ok")',env={'EVAL_RANDOM':'ordinary'})
    assert p.returncode==0 and p.stdout=='ok\n' and p.stderr==''


def test_strict_requires_normalized_parent_names_and_values():
    p=run('exec','svc','--strict','--backend=null','--','/bin/true',env={'raw-name':'chamberme'})
    assert p.returncode==1 and 'key `raw-name` with expected value `chamberme`, but key is not normalized like `RAW_NAME`' in p.stderr


def test_tag_validation_precedes_backend():
    p=run('tag','write','svc','key','bad!value','--backend=null')
    assert p.returncode==1 and p.stderr.startswith('Error: Failed to parse tag bad!value: tag must be in the form key=value\n')
    p=run('tag','write','svc','key','bad!=x','--backend=null')
    assert p.returncode==1 and 'Failed to validate tag key' in p.stderr
    p=run('tag','write','svc','key','good=bad!','--backend=null')
    assert p.returncode==1 and 'Failed to validate tag value' in p.stderr


def test_write_tags_string_map_parser():
    p=run('write','s','k','v','--tags','broken','--backend=null')
    assert p.returncode==1 and 'invalid argument "broken" for "-t, --tags" flag' in p.stderr
    p=run('write','s','k','v','--tags=','--backend=null')
    assert p.returncode==1 and 'invalid argument "" for "-t, --tags" flag' in p.stderr


def test_completion_group_fallback_and_shell_help():
    for args in [('completion',),('completion','unknown')]:
        p=run(*args)
        assert p.returncode==0 and p.stdout.startswith('Generate the autocompletion script for chamber for the specified shell.\n') and '  bash ' in p.stdout and p.stderr==''
    p=run('completion','fish','--help')
    assert p.returncode==0 and 'fish' in p.stdout and p.stderr==''


def test_completion_scripts_are_nonempty():
    for shell,marker in [('bash','__chamber_debug'),('fish','function __chamber_debug'),('zsh','#compdef chamber'),('powershell','Register-ArgumentCompleter')]:
        p=run('completion',shell)
        assert p.returncode==0 and p.stderr=='' and p.stdout.startswith(marker)


def test_fish_no_descriptions():
    p=run('completion','fish','--no-descriptions')
    assert p.returncode==0 and p.stdout.startswith('# fish completion for chamber') and '__completeNoDesc' in p.stdout and p.stderr==''
