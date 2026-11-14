import subprocess
from conftest import EXECUTABLE

def invoke(*args, cwd='/workspace'):
    return subprocess.run([str(EXECUTABLE),*args],cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)

def test_version_long_exact():
    p=invoke('--version'); assert (p.returncode,p.stdout,p.stderr)==(0,'git-trim 0.4.4\n','')

def test_version_short_exact():
    p=invoke('-V'); assert (p.returncode,p.stdout,p.stderr)==(0,'git-trim 0.4.4\n','')

def test_long_help_is_plain_and_complete():
    p=invoke('--help'); assert p.returncode==0 and p.stderr=='' and p.stdout.endswith('\n')
    assert 'Usage: executable [OPTIONS]' in p.stdout and '--update-interval <UPDATE_INTERVAL>' in p.stdout
    assert '\x1b' not in p.stdout and 'proper, safer, faster alternative' in p.stdout

def test_short_help_is_compact():
    p=invoke('-h'); assert p.returncode==0 and p.stderr==''
    assert "Print help (see more with '--help')" in p.stdout
    assert 'proper, safer, faster alternative' not in p.stdout and 'They might not be reflected' not in p.stdout

def test_help_precedes_other_options():
    p=invoke('--help','--unknown-flag'); assert p.returncode==0 and p.stderr=='' and p.stdout.startswith('Automatically trims')

def test_separator_makes_help_positional():
    p=invoke('--','--help'); assert p.returncode==2 and "unexpected argument '--help' found" in p.stderr

def test_unknown_option_diagnostic_exact():
    p=invoke('--unknown-flag'); assert p.returncode==2
    assert p.stderr=="error: unexpected argument '--unknown-flag' found\n\nUsage: executable [OPTIONS]\n\nFor more information, try '--help'.\n"

def test_positionals_are_rejected():
    p=invoke('add'); assert p.returncode==2 and "unexpected argument 'add' found" in p.stderr

def test_missing_value_reports_expected_option(repo):
    repo.init(); repo.git('remote','add','origin','../remote.git')
    p=repo.run('--no-update','--bases'); assert p.returncode==2 and 'a value is required for' in p.stderr and '--bases <BASES>' in p.stderr

def test_invalid_delete_diagnostic_exact(repo):
    repo.init(); repo.git('remote','add','origin','../remote.git')
    p=repo.run('--no-update','--delete','invalid-range')
    assert p.returncode==2
    assert p.stderr=="error: invalid value 'invalid-range' for '--delete <DELETE>': Invalid delete range format `invalid-range`\n\nFor more information, try '--help'.\n"

def test_update_interval_invalid_diagnostic_exact(repo):
    repo.init(); repo.git('remote','add','origin','../remote.git')
    p=repo.run('--update-interval','invalid')
    assert p.returncode==2
    assert p.stderr=="error: invalid value 'invalid' for '--update-interval <UPDATE_INTERVAL>': invalid digit found in string\n\nFor more information, try '--help'.\n"

def test_update_interval_repetition_rejected(repo):
    repo.init(); repo.git('remote','add','origin','../remote.git')
    p=repo.run('--update-interval','1','--update-interval','2')
    assert p.returncode==2 and 'cannot be used multiple times' in p.stderr

def test_update_interval_bounds(repo):
    repo.init(); repo.git('remote','add','origin','../remote.git')
    p=repo.run('--no-update','--update-interval=18446744073709551616')
    assert p.returncode==2 and 'invalid value' in p.stderr

def test_separate_negative_interval_is_unexpected(repo):
    repo.init(); repo.git('remote','add','origin','../remote.git')
    p=repo.run('--update-interval','-1')
    assert p.returncode==2 and "unexpected argument '-1'" in p.stderr

def test_attached_negative_interval_is_invalid_value(repo):
    repo.init(); repo.git('remote','add','origin','../remote.git')
    p=repo.run('--update-interval=-1')
    assert p.returncode==2 and "invalid value '-1'" in p.stderr

def test_combined_short_value_syntax_rejects_trailing_value(repo):
    repo.init(); repo.git('remote','add','origin','../remote.git')
    p=repo.run('-bd','merged:origin')
    assert p.returncode==2 and "unexpected argument 'merged:origin'" in p.stderr

def test_flag_conflict_order_is_symmetric(repo):
    repo.init(); repo.commit(); repo.git('remote','add','origin','../remote.git')
    pairs=[('--no-update','--update',"Error: Flag 'update' and 'no-update' cannot be used simultaneously\n"),('--no-confirm','--confirm',"Error: Flag 'confirm' and 'no-confirm' cannot be used simultaneously\n"),('--no-detach','--detach',"Error: Flag 'detach' and 'no-detach' cannot be used simultaneously\n")]
    for left,right,msg in pairs:
        p=repo.run('--bases','absent',left,right)
        assert p.returncode==255 and p.stderr==msg

def test_short_base_alias(repo):
    repo.init(); repo.commit(); repo.git('remote','add','origin','../remote.git'); repo.git('update-ref','refs/remotes/origin/main','HEAD')
    p=repo.run('--no-update','--base','main','--dry-run')
    assert p.returncode==0 and 'Branches that will remain:' in p.stdout

def test_multiple_value_options_allow_equals_and_separate_forms_in_any_order(repo):
    repo.init(); repo.commit(); repo.git('remote','add','origin','../remote.git'); repo.git('update-ref','refs/remotes/origin/main','HEAD')
    p=repo.run('--dry-run','--delete=merged:origin','--no-update','--bases','main','--protected=release-*')
    assert p.returncode==0 and 'main [base]' in p.stdout
