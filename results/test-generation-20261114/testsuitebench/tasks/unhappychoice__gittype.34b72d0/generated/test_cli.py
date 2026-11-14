import os, subprocess, tempfile, pathlib, re
import pytest

BIN = '/workspace/executable'

@pytest.fixture
def envhome(tmp_path):
    e=os.environ.copy(); e['HOME']=str(tmp_path); e.pop('XDG_DATA_HOME',None)
    return e

def run(*args, env=None, cwd=None, input=None):
    return subprocess.run([BIN,*map(str,args)], env=env, cwd=cwd, input=input, text=True, capture_output=True, timeout=8)

def test_version_and_help_flags(envhome):
    p=run('--version',env=envhome); assert (p.returncode,p.stdout,p.stderr)==(0,'gittype 0.8.0\n','')
    assert run('-V',env=envhome).stdout=='gittype 0.8.0\n'
    assert run('--version','--help',env=envhome).stdout=='gittype 0.8.0\n'
    assert 'Usage: executable [OPTIONS] [REPO_PATH] [COMMAND]' in run('-h',env=envhome).stdout
    assert run('--help',env=envhome).stdout.startswith('GitType turns your own source code')
    assert run('help',env=envhome).stdout==run('--help',env=envhome).stdout

def test_leaf_help_and_usage(envhome):
    for cmd, phrase in [('history','Show session history'),('stats','Show analytics'),('export','Export session data')]:
        p=run(cmd,'--help',env=envhome); assert p.returncode==0 and phrase in p.stdout and not p.stderr
    assert run('cache','stats','--help',env=envhome).stdout.startswith('Show cache statistics\n')
    assert run('repo','clear','--help',env=envhome).stdout.startswith('Clear all cached repositories\n')
    for cmd, msg in [('cache','Manage challenge cache'),('repo','Manage repositories')]:
        p=run(cmd,env=envhome); assert p.returncode==2 and p.stdout=='' and msg in p.stderr

def test_help_precedence_and_bad_args(envhome):
    assert run('history','--help','--invalid',env=envhome).returncode==0
    p=run('history','--invalid','--help',env=envhome); assert p.returncode==2 and 'unexpected argument' in p.stderr
    p=run('history','x',env=envhome); assert p.returncode==2 and 'unexpected argument' in p.stderr and p.stdout==''
    p=run('stats','x',env=envhome); assert p.returncode==2 and 'unexpected argument' in p.stderr
    p=run('help','nonexistent',env=envhome); assert p.returncode==2 and "unrecognized subcommand 'nonexistent'" in p.stderr

def test_unimplemented_history_stats(envhome):
    for c, title in [('history','History'),('stats','Stats')]:
        p=run(c,env=envhome); assert p.returncode==1 and p.stdout==''
        assert p.stderr==f'❌ {title} command is not yet implemented\n💡 This feature is planned for a future release\n'

def test_export_defaults_and_values(envhome):
    p=run('export',env=envhome)
    assert p.returncode==1 and p.stdout==''
    assert p.stderr=='❌ Export command is not yet implemented\n💡 Requested format: json\n💡 This feature is planned for a future release\n'
    p=run('export','--output=','--format','CSV ',env=envhome)
    assert p.returncode==1 and '💡 Requested format: CSV \n' in p.stderr and '💡 Requested output: \n' in p.stderr

def test_export_parser(envhome):
    for args in [('--format',),('--format','a','--format','b'),('--output','a','--output','b'),('extra',),('--bad',)]:
        p=run('export',*args,env=envhome); assert p.returncode==2 and p.stdout==''

def test_lang_validation(envhome):
    p=run('--langs','RUST,not-a-language','envhome',env=envhome)
    assert p.returncode==1 and '❌ Unsupported language(s): not-a-language' in p.stderr
    assert 'clojure, clj' in p.stderr
    p=run('--langs','rust, python','history',env=envhome)
    assert p.returncode==1 and ' python' in p.stderr

def test_trending_validation_and_name(envhome, tmp_path):
    p=run('trending','Zig','owner/repo',env=envhome,cwd=tmp_path)
    assert p.returncode==1 and p.stdout=='' and "Unsupported language: Zig" in p.stderr
    assert 'gittype_error_' in p.stderr
    assert len(list(tmp_path.glob('gittype_error_*.log')))==1
    p=run('trending','Python','noslash',env=envhome,cwd=tmp_path)
    assert p.returncode==0 and p.stderr=="⚠️ Repository name must be in format 'owner/repo'\n"
    p=run('trending','Python','/',env=envhome,cwd=tmp_path)
    assert p.returncode==1 and 'Terminal error' in p.stderr

def test_cache_empty_and_nonempty(envhome):
    root=pathlib.Path(envhome['HOME'])/'.gittype'; cache=root/'cache'
    p=run('cache','stats',env=envhome)
    assert p.returncode==0 and p.stderr=='' and p.stdout=='Challenge Cache Statistics:\n  Cached repositories: 0\n  Total size: 0 bytes\n'
    assert not cache.exists()
    p=run('cache','list',env=envhome); assert p.returncode==0 and p.stdout=='No cached challenges found.\n' and not cache.exists()
    cache.mkdir(parents=True); (cache/'odd.dat').write_bytes(b'abc'); (cache/'.hidden').write_bytes(b'')
    (cache/'nested').mkdir(); (cache/'nested'/'nested.bin').write_bytes(b'123456')
    p=run('cache','stats',env=envhome)
    assert 'Cached repositories: 2' in p.stdout and 'Total size: 3 bytes' in p.stdout
    p=run('cache','list',env=envhome); assert p.returncode==0 and p.stdout=='No cached challenges found.\n'

def test_cache_clear_only_immediate_files(envhome):
    root=pathlib.Path(envhome['HOME'])/'.gittype'; c=root/'cache'; repo=root/'repos'
    c.mkdir(parents=True); (c/'a.bin').write_bytes(b'x'); (c/'sub').mkdir(); (c/'sub'/'keep').write_text('y')
    repo.mkdir(); (repo/'keep').write_text('z')
    p=run('cache','clear',env=envhome)
    assert p.returncode==0 and p.stderr=='' and p.stdout=='Challenge cache cleared successfully.\n'
    assert list(c.iterdir())==[c/'sub'] and (c/'sub'/'keep').exists() and (repo/'keep').exists()
    assert run('cache','clear',env=envhome).returncode==0

def test_repo_clear_no_repos_and_force(envhome):
    root=pathlib.Path(envhome['HOME'])/'.gittype'; repos=root/'repos'
    p=run('repo','clear','--force',env=envhome); assert p.returncode==0 and p.stdout=='No cached repositories directory found.\n'
    repos.mkdir(parents=True); (repos/'ordinary').mkdir()
    p=run('repo','clear','--force',env=envhome); assert p.returncode==0 and p.stdout=='No cached repositories found.\n'
    d=repos/'nested'/'repo'; (d/'.git').mkdir(parents=True); (repos/'filegit').mkdir(); (repos/'filegit'/'.git').write_text('gitdir: x')
    cache=root/'cache'; cache.mkdir(); (cache/'preserve').write_text('cache')
    p=run('repo','clear','--force',env=envhome)
    assert p.returncode==0 and 'Successfully deleted all cached repositories.\n' in p.stdout
    assert not repos.exists() and (cache/'preserve').exists()

def test_repo_clear_cancel(envhome):
    root=pathlib.Path(envhome['HOME'])/'.gittype'; repos=root/'repos'; d=repos/'r'; (d/'.git').mkdir(parents=True)
    p=run('repo','clear',env=envhome,input='  No  \n')
    assert p.returncode==0 and '(1 cached repositories will be removed)\n' in p.stdout
    assert p.stdout.endswith('Operation cancelled.\n') and (d/'.git').exists()

def test_runtime_logs_and_terminal_error(envhome,tmp_path):
    p=run('repo','list',env=envhome,cwd=tmp_path)
    assert p.returncode==1 and p.stdout=='' and 'Terminal error' in p.stderr
    state=pathlib.Path(envhome['HOME'])/'.gittype'
    assert (state/'logs').is_dir()
    logs=list((state/'logs').glob('*.log')); assert logs and all(x.stat().st_size>0 for x in logs)
    assert not list(state.glob('*.log'))
    errors=list(tmp_path.glob('gittype_error_*.log')); assert len(errors)==1
    body=errors[0].read_text(); assert 'ERROR OCCURRED AT:' in body and 'ERROR MESSAGE:' in body and 'EXECUTABLE:' in body and 'COMMAND_ARGS:' in body

def test_trending_help_and_parser(envhome):
    assert run('trending','--help',env=envhome).stdout.startswith('Select and practice with trending repositories from GitHub\n')
    p=run('trending','--period',env=envhome); assert p.returncode==2 and 'value is required' in p.stderr
    p=run('trending','--wat',env=envhome); assert p.returncode==2 and 'unexpected argument' in p.stderr
