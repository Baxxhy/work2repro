def setup_repo(r, bare=False):
    r.init(bare=bare)

def test_no_repository_exact_error(outside):
    from conftest import EXECUTABLE
    import subprocess
    p=subprocess.run([str(EXECUTABLE),'--no-update'],cwd=outside,text=True,capture_output=True)
    assert p.returncode==1
    assert p.stdout=='' and p.stderr=="Error: could not find repository at '.'; class=Repository (6); code=NotFound (-3)\n"

def test_empty_repository_without_remotes_fails_first(repo):
    repo.init(); repo.commit()
    p=repo.run('--no-update')
    assert (p.returncode,p.stdout,p.stderr)==(1,'','Error: git-trim requires at least one remote\n')

def test_empty_nonbare_repository_without_remotes(repo):
    repo.init(); p=repo.run('--no-update')
    assert (p.returncode,p.stdout,p.stderr)==(1,'','Error: git-trim requires at least one remote\n')

def test_bare_without_remotes_fails_before_base_discovery(repo):
    repo.init(bare=True); p=repo.run('--no-update')
    assert (p.returncode,p.stdout,p.stderr)==(1,'','Error: git-trim requires at least one remote\n')

def test_remote_but_no_implicit_base_reports_guidance(repo):
    repo.init(); repo.commit(); repo.git('remote','add','origin','../missing.git')
    p=repo.run('--no-update')
    assert p.returncode==1
    assert p.stdout=='You also can set bases manually with any of following commands:\n'
    assert "I can't detect base branch!" in p.stderr and 'Error: No base branch is found!\n' in p.stderr

def test_explicit_base_and_dry_run_has_structured_plan(repo):
    repo.init(); repo.commit('f','base'); repo.git('branch','main'); repo.git('remote','add','origin','../missing.git')
    repo.git('update-ref','refs/remotes/origin/main','HEAD')
    p=repo.run('--no-update','--bases','main','--dry-run')
    assert p.returncode==0 and p.stderr==''
    assert p.stdout.startswith('Branches that will remain:\n  local branches:')
    assert 'main [base]' in p.stdout and 'origin/main [base]' in p.stdout

def test_bare_with_explicit_base_requires_worktree(repo):
    repo.init(bare=True); repo.git('remote','add','origin','../missing.git'); repo.git('update-ref','refs/heads/master','HEAD',check=False)
    p=repo.run('--no-update','--bases','master','--dry-run')
    assert p.returncode==1 and p.stdout=='' and p.stderr=='Error: Bare repository is not supported\n'

def test_pair_conflict_checked_after_repository_open(repo):
    repo.init(); p=repo.run('--update','--no-update')
    assert p.returncode==1 and 'could not find repository' not in p.stderr

def test_pair_conflicts_in_repository_are_status_255(repo):
    repo.init(); repo.commit(); repo.git('remote','add','origin','../remote.git')
    for yes,no,expected in [('--update','--no-update',"Error: Flag 'update' and 'no-update' cannot be used simultaneously\n"),(' --confirm','--no-confirm',"Error: Flag 'confirm' and 'no-confirm' cannot be used simultaneously\n"),('--detach','--no-detach',"Error: Flag 'detach' and 'no-detach' cannot be used simultaneously\n")]:
        yes=yes.strip(); p=repo.run('--bases','missing',yes,no)
        assert p.returncode==255 and p.stdout=='' and p.stderr==expected

def test_nonempty_missing_url_remote_is_ignored(repo):
    repo.init(); repo.commit('f','main'); repo.git('branch','main'); repo.git('remote','add','origin','../remote.git')
    repo.git('update-ref','refs/remotes/origin/main','HEAD')
    repo.git('remote','add','broken',''); repo.git('config','remote.broken.fetch','+refs/heads/*:refs/remotes/broken/*')
    p=repo.run('--no-update','--bases','main','--dry-run')
    assert p.returncode==0 and 'origin/main [base]' in p.stdout and 'broken/' not in p.stdout

def test_config_boolean_failure(repo):
    repo.init(); repo.commit(); repo.git('remote','add','origin','../missing.git'); repo.config('trim.update','maybe')
    p=repo.run('--no-update'); assert p.returncode==1 and p.stderr=="Error: failed to parse 'maybe' as a boolean value; class=Config (7)\n"

def test_config_integer_failure(repo):
    repo.init(); repo.commit(); repo.git('remote','add','origin','../missing.git'); repo.config('trim.updateInterval','oops')
    p=repo.run('--no-update'); assert p.returncode==1 and p.stderr=="Error: failed to parse 'oops' as an integer; class=Config (7)\n"

def test_negative_config_interval_panics_as_documented(repo):
    repo.init(); repo.commit(); repo.git('remote','add','origin','../missing.git'); repo.config('trim.updateInterval','-1')
    p=repo.run('--no-update'); assert p.returncode==101
    assert "`git config trim.updateInterval` cannot be negative value" in p.stderr
    assert p.stderr.splitlines()[-1]=='note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace'
