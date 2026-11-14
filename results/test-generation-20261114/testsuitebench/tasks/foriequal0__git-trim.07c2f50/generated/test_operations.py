def setup(r):
    r.init(); base=r.commit('base','root','base'); r.git('branch','main'); r.git('remote','add','origin','../remote.git')
    r.git('update-ref','refs/remotes/origin/main',base); r.git('symbolic-ref','refs/remotes/origin/HEAD','refs/remotes/origin/main')
    r.git('config','branch.main.remote','origin'); r.git('config','branch.main.merge','refs/heads/main')
    r.git('branch','done',base); r.git('config','branch.done.remote','origin'); r.git('config','branch.done.merge','refs/heads/done'); r.git('update-ref','refs/remotes/origin/done',base)
    return base

def test_dry_run_leaves_refs_unchanged(repo):
    setup(repo); before=repo.git('show-ref').stdout
    p=repo.run('--no-update','--bases','main','--dry-run')
    assert p.returncode==0 and repo.git('show-ref').stdout==before
    assert 'Delete branch done (dry run).' in p.stdout

def test_no_confirm_deletes_both_sides(repo):
    setup(repo); p=repo.run('--no-update','--bases','main','--no-confirm')
    assert p.returncode==0 and 'Deleted branch done (was ' in p.stdout
    assert repo.git('show-ref','--verify','refs/heads/done',check=False).returncode!=0
    assert repo.git('show-ref','--verify','refs/remotes/origin/done',check=False).returncode!=0

def test_declining_confirmation_cancels_without_mutation(repo):
    setup(repo); before=repo.git('show-ref').stdout
    p=repo.run('--no-update','--bases','main',input='n\n')
    assert p.returncode==0 and 'Confirm?' in p.stdout and 'Cancelled' in p.stdout
    assert repo.git('show-ref').stdout==before

def test_empty_confirmation_declines_by_default(repo):
    setup(repo); p=repo.run('--no-update','--bases','main',input='\n')
    assert p.returncode==0 and 'Cancelled' in p.stdout

def test_no_candidates_never_prompts(repo):
    setup(repo); p=repo.run('--no-update','--bases','main','--delete','stray')
    assert p.returncode==0 and 'Confirm?' not in p.stdout

def test_no_detach_protects_current_branch_but_remote_can_be_removed(repo):
    setup(repo); repo.git('checkout','done')
    p=repo.run('--no-update','--bases','main','--no-detach','--dry-run')
    assert p.returncode==0 and 'done [merged, but: HEAD]' in p.stdout
    assert 'Delete merged remote refs:\n  - origin, refs/heads/done' in p.stdout
    assert 'Delete branch done (dry run).' not in p.stdout

def test_current_branch_detach_simulation_order(repo):
    setup(repo); repo.git('checkout','done')
    p=repo.run('--no-update','--bases','main','--dry-run')
    assert p.returncode==0
    a=p.stdout.index("Note: switching to 'refs/heads/done' (dry run)")
    b=p.stdout.index("You are in 'detached HED' state... blah blah...",a)
    c=p.stdout.index('HEAD is now at ',b); d=p.stdout.index('Delete branch done (dry run).',c)
    assert a<b<c<d

def test_local_only_deletion_preserves_remote(repo):
    setup(repo); p=repo.run('--no-update','--bases','main','--delete','merged-local','--no-confirm')
    assert p.returncode==0
    assert repo.git('show-ref','--verify','refs/heads/done',check=False).returncode!=0
    assert repo.git('show-ref','--verify','refs/remotes/origin/done',check=False).returncode==0

def test_remote_only_deletion_preserves_local(repo):
    setup(repo); p=repo.run('--no-update','--bases','main','--delete','merged-remote:origin','--no-confirm')
    assert p.returncode==0
    assert repo.git('show-ref','--verify','refs/heads/done',check=False).returncode==0
    assert repo.git('show-ref','--verify','refs/remotes/origin/done',check=False).returncode!=0

def test_bad_scoped_delete_range_reports_empty_scope(repo):
    setup(repo); p=repo.run('--no-update','--bases','main','--delete','merged:','--dry-run')
    assert p.returncode!=0 and 'Scope parse error for delete range' in p.stderr and 'Scope is empty' in p.stderr

def test_retained_report_has_trailing_blank_line(repo):
    setup(repo); p=repo.run('--no-update','--bases','main','--delete','stray','--dry-run')
    assert p.returncode==0 and p.stdout.endswith('\n\n')

def test_worktree_checked_out_branch_is_retained(repo, tmp_path):
    setup(repo); repo.git('branch','checked',repo.git('rev-parse','HEAD').stdout.strip())
    linked=tmp_path/'linked'; repo.git('worktree','add',str(linked),'checked')
    p=repo.run('--no-update','--bases','main','--delete','local','--dry-run')
    assert p.returncode==0 and f'checked [merged, but: worktree at {linked}]' in p.stdout
    assert '  - checked (non-tracking)' not in p.stdout

def test_config_delete_whitespace_is_trimmed(repo):
    setup(repo); repo.config('trim.delete',' merged:origin ')
    p=repo.run('--no-update','--bases','main','--dry-run')
    assert p.returncode==0 and 'Delete merged local branches:' in p.stdout

def test_update_interval_zero_is_accepted(repo):
    setup(repo); p=repo.run('--no-update','--bases','main','--update-interval=0','--dry-run')
    assert p.returncode==0

def test_positive_flag_overrides_negative_when_both_absent_pairing(repo):
    setup(repo); p=repo.run('--no-update','--update','--bases','main','--dry-run','--update-interval','0')
    # A local update is valid and the resulting report remains well formed.
    assert p.returncode==0 and 'Branches that will remain:' in p.stdout
