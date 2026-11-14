def basic_clone(r):
    r.init(); base=r.commit('base.txt','base','base'); r.git('branch','main'); r.git('remote','add','origin','../origin.git')
    r.git('update-ref','refs/remotes/origin/main',base); r.git('symbolic-ref','refs/remotes/origin/HEAD','refs/remotes/origin/main')
    r.git('config','branch.main.remote','origin'); r.git('config','branch.main.merge','refs/heads/main')
    return base

def test_implicit_remote_head_discovery_protects_tracking_base(repo):
    basic_clone(repo); p=repo.run('--no-update','--bases=','--dry-run')
    assert p.returncode==0 and 'main [base]' in p.stdout and 'origin/main [base]' in p.stdout

def test_default_merged_range_selects_local_and_upstream(repo):
    base=basic_clone(repo); repo.git('checkout','-b','feature'); repo.commit('feature','work','feature')
    feature=repo.git('rev-parse','HEAD').stdout.strip(); repo.git('checkout','main'); repo.git('merge','--no-ff','feature','-m','merge feature')
    repo.git('update-ref','refs/remotes/origin/feature',feature)
    repo.git('config','branch.feature.remote','origin'); repo.git('config','branch.feature.merge','refs/heads/feature')
    p=repo.run('--no-update','--bases','main','--dry-run')
    assert p.returncode==0 and 'Delete merged local branches:\n  - feature' in p.stdout
    assert 'Delete merged remote refs:\n  - origin, refs/heads/feature' in p.stdout
    assert 'Delete branch feature (dry run).' in p.stdout

def test_range_selects_local_and_remote_independently(repo):
    feature=basic_clone(repo); repo.git('branch','feature',feature); repo.git('config','branch.feature.remote','origin'); repo.git('config','branch.feature.merge','refs/heads/feature')
    repo.git('update-ref','refs/remotes/origin/feature',feature)
    p=repo.run('--no-update','--bases','main','--delete','merged-local','--dry-run')
    assert 'Delete merged local branches:\n  - feature' in p.stdout
    assert 'Delete merged remote refs:' not in p.stdout
    assert 'origin/feature [merged, but: delete range `merged-remote:origin` was not given]' in p.stdout

def test_local_only_range_skips_untracked_candidate(repo):
    base=basic_clone(repo); repo.git('branch','localdone',base)
    p=repo.run('--no-update','--bases','main','--delete','local','--dry-run')
    assert 'Delete merged local branches:\n  - localdone (non-tracking)' in p.stdout

def test_stray_selection_and_deletion_section(repo):
    base=basic_clone(repo); repo.git('branch','gone',base); repo.git('config','branch.gone.remote','origin'); repo.git('config','branch.gone.merge','refs/heads/gone')
    p=repo.run('--no-update','--bases','main','--delete','stray','--dry-run')
    assert 'Delete stray local branches:\n  - gone' in p.stdout

def test_protected_pattern_retains_selected_local(repo):
    base=basic_clone(repo); repo.git('branch','release-1',base); repo.git('config','branch.release-1.remote','origin'); repo.git('config','branch.release-1.merge','refs/heads/release-1'); repo.git('update-ref','refs/remotes/origin/release-1',base)
    p=repo.run('--no-update','--bases','main','--protected','release-*','--dry-run')
    assert 'release-1 [merged, but: protected by a pattern `release-*`]' in p.stdout
    assert '  - release-1' not in p.stdout

def test_protection_cli_replaces_config(repo):
    base=basic_clone(repo); repo.git('branch','hotfix-1',base); repo.git('config','branch.hotfix-1.remote','origin'); repo.git('config','branch.hotfix-1.merge','refs/heads/hotfix-1'); repo.git('update-ref','refs/remotes/origin/hotfix-1',base)
    repo.config('trim.protected','release-*')
    p=repo.run('--no-update','--bases','main','--protected','hotfix-*','--dry-run')
    assert 'hotfix-1 [merged, but: protected by a pattern `hotfix-*`]' in p.stdout

def test_empty_cli_bases_allows_no_discovered_base(repo):
    repo.init(); repo.commit('f','x'); repo.git('remote','add','origin','../missing.git')
    p=repo.run('--no-update','--bases=','--dry-run')
    assert p.returncode==0 and p.stderr=='' and 'Branches that will remain:' in p.stdout

def test_explicit_empty_configured_bases_is_error(repo):
    repo.init(); repo.commit(); repo.git('remote','add','origin','../remote.git'); repo.config('trim.bases','')
    p=repo.run('--no-update')
    assert p.returncode==1 and 'I found that `git config trim.bases` is empty!' in p.stderr and p.stderr.endswith('Error: No base branch is found!\n')

def test_whitespace_in_configured_base_is_not_trimmed(repo):
    repo.init(); repo.commit(); repo.git('remote','add','origin','../remote.git'); repo.config('trim.bases',' develop')
    p=repo.run('--no-update'); assert p.returncode==1 and p.stderr=="Error: could not use ' develop' as valid reference name; class=Reference (4); code=InvalidSpec (-12)\n"

def test_configured_delete_items_trim_and_accumulate(repo):
    basic_clone(repo); repo.config('trim.delete',' merged:origin ')
    p=repo.run('--no-update','--bases','main','--dry-run')
    assert p.returncode==0 and 'Branches that will remain:' in p.stdout

def test_invalid_later_configured_delete_item_is_validated(repo):
    basic_clone(repo); repo.config('trim.delete','merged:origin'); repo.config('--add','trim.delete','local, bogus')
    p=repo.run('--no-update','--dry-run')
    assert p.returncode==1 and p.stderr=='Error: Invalid delete range format ` bogus`\n'

def test_cli_bases_replaces_config(repo):
    basic_clone(repo); repo.config('trim.bases','does-not-exist')
    p=repo.run('--no-update','--bases','main','--dry-run')
    assert p.returncode==0 and 'main [base]' in p.stdout

def test_protection_pattern_matches_path_and_slash(repo):
    base=basic_clone(repo); repo.git('branch','feature/sub',base); repo.git('config','branch.feature/sub.remote','origin'); repo.git('config','branch.feature/sub.merge','refs/heads/feature/sub'); repo.git('update-ref','refs/remotes/origin/feature/sub',base)
    p=repo.run('--no-update','--bases','main','--protected','feature/*','--dry-run')
    assert 'feature/sub [merged, but: protected by a pattern `feature/*`]' in p.stdout

def test_protection_is_case_sensitive(repo):
    base=basic_clone(repo); repo.git('branch','Release-1',base); repo.git('config','branch.Release-1.remote','origin'); repo.git('config','branch.Release-1.merge','refs/heads/Release-1'); repo.git('update-ref','refs/remotes/origin/Release-1',base)
    p=repo.run('--no-update','--bases','main','--protected','release-*','--dry-run')
    assert '  - Release-1' in p.stdout

def test_default_range_does_not_select_stray_or_nonupstream(repo):
    base=basic_clone(repo); repo.git('branch','orphaned',base); repo.git('config','branch.orphaned.remote','origin'); repo.git('config','branch.orphaned.merge','refs/heads/orphaned')
    repo.git('update-ref','refs/remotes/origin/other',base)
    p=repo.run('--no-update','--bases','main','--dry-run')
    assert 'orphaned [stray, but: delete range `stray` was not given]' in p.stdout
    assert 'origin/other *3' in p.stdout
    assert 'Delete stray local branches:' not in p.stdout

def test_empty_base_occurrence_exact_untracked_report(repo):
    repo.init(); repo.commit('f','x'); repo.git('remote','add','origin','../missing.git')
    p=repo.run('--no-update','--bases','','--dry-run')
    assert p.returncode==0
    assert p.stdout==('Branches that will remain:\n  local branches:\n    master *2\n  remote references:\n  Some branches are skipped. Consider following to scan them:\n    *2: Set an upstream to make it a tracking branch or add `--delete \'local\'` flag.\n\n')

def test_configured_boolean_and_cli_override(repo):
    basic_clone(repo); repo.config('trim.update','true')
    p=repo.run('--no-update','--bases','main','--dry-run')
    assert p.returncode==0 and not p.stdout.startswith('\n')

def test_bases_and_delete_long_equals_syntax(repo):
    basic_clone(repo)
    p=repo.run('--no-update','--bases=main','--delete=merged:origin','--dry-run')
    assert p.returncode==0 and 'main [base]' in p.stdout

def test_remote_only_base_protects_tracking_local(repo):
    base=basic_clone(repo); repo.git('branch','dev',base); repo.git('config','branch.dev.remote','origin'); repo.git('config','branch.dev.merge','refs/heads/dev'); repo.git('update-ref','refs/remotes/origin/dev',base)
    p=repo.run('--no-update','--bases','origin/dev','--delete','merged:origin','--dry-run')
    assert p.returncode==0
    assert 'origin/dev [base]' in p.stdout
    assert 'dev [merged, but: tracks base `origin/dev`]' in p.stdout or 'dev [base]' in p.stdout
    assert '  - dev' not in p.stdout

def test_squash_equivalent_branch_is_classified_as_merged(repo):
    base=basic_clone(repo); repo.git('checkout','-b','topic'); repo.commit('topic.txt','payload','topic change')
    topic=repo.git('rev-parse','HEAD').stdout.strip(); repo.git('checkout','main')
    repo.git('show','topic:topic.txt').stdout
    repo.git('checkout','topic','--','topic.txt'); repo.git('commit','-m','squashed equivalent')
    repo.git('update-ref','refs/remotes/origin/topic',topic); repo.git('config','branch.topic.remote','origin'); repo.git('config','branch.topic.merge','refs/heads/topic')
    p=repo.run('--no-update','--bases','main','--dry-run')
    assert p.returncode==0 and '  - topic' in p.stdout

def test_delete_scopes_are_validated_and_required(repo):
    basic_clone(repo)
    for value in ('merged-remote','diverged','remote'):
        p=repo.run('--no-update','--bases','main','--delete',value,'--dry-run')
        assert p.returncode==2 and 'invalid value' in p.stderr

def test_cli_delete_replaces_configured_delete(repo):
    base=basic_clone(repo); repo.git('branch','untracked-merged',base); repo.config('trim.delete','local')
    p=repo.run('--no-update','--bases','main','--delete','merged-local','--dry-run')
    assert p.returncode==0 and 'untracked-merged' not in p.stdout
