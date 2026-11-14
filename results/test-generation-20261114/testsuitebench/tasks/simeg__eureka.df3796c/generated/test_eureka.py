import json
import os
import pathlib
import subprocess
import tempfile

EXE = pathlib.Path('/workspace/executable')
HELP = ("Input and store your ideas without leaving the terminal\n\n"
        "Usage: executable [OPTIONS]\n\nOptions:\n"
        "      --clear-config  Clear your stored configuration\n"
        "  -v, --view          View ideas with your $PAGER env variable. If unset use less\n"
        "  -h, --help          Print help\n"
        "  -V, --version       Print version\n")
PROMPT = b'\x1b[0m\x1b[1m\x1b[32m>> Idea summary\n\x1b[0m> '
SETUP_HEAD = (b'\x1b[0m\x1b[33m' + b'#'*60 + b'\n####                  First Time Setup                  ####\n' +
              b'#'*60 + b'\n\nThis tool requires you to have a repository with a README.md\n'
              b'in the root folder. The markdown file is where your ideas\nwill be stored.\n\n'
              b'Once first time setup has completed, simply run Eureka again\nto begin writing down ideas.\n'
              b'        \n\x1b[0m\x1b[0m\x1b[1m\x1b[32mAbsolute path to your idea repo\n\x1b[0m> ')

def run(args=(), *, env=None, data=b'', cwd=None, timeout=5):
    e = os.environ.copy()
    for k in ('XDG_CONFIG_HOME','HOME','EDITOR','PAGER'):
        e.pop(k, None)
    e.update(env or {})
    return subprocess.run([str(EXE), *args], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=e, cwd=cwd, timeout=timeout)

def confdir(base): return pathlib.Path(base) / 'eureka'
def write_config(base, repo, **extra):
    d=confdir(base); d.mkdir(parents=True, exist_ok=True)
    (d/'config.json').write_text(json.dumps(dict(repo=repo, **extra), separators=(',',':')), encoding='utf8')
    return d
def git(path, *args): return subprocess.run(['git','-C',str(path),*args],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True).stdout.strip()
def repo_init(p, branch='main'):
    p.mkdir(parents=True,exist_ok=True); git(p,'init','-b',branch)
    git(p,'config','user.name','Tester'); git(p,'config','user.email','tester@example.test')
    (p/'README.md').write_text('seed\n'); git(p,'add','README.md'); git(p,'commit','-m','seed')

def test_help_exact_and_aliases():
    a=run(['-h']); b=run(['--help'])
    assert (a.returncode,a.stdout,a.stderr)==(0,HELP.encode(),b'')
    assert (b.returncode,b.stdout,b.stderr)==(0,a.stdout,b'')

def test_help_precedence_and_cluster():
    for args in (['--help','--view'],['-vh'],['--help','--version']):
        r=run(args); assert (r.returncode,r.stdout,r.stderr)==(0,HELP.encode(),b'')

def test_version_exact_alias_and_operation_precedence():
    for args in (['-V'],['--version'],['--version','--clear-config']):
        r=run(args); assert (r.returncode,r.stdout,r.stderr)==(0,b'eureka 2.0.0\n',b'')

def test_cli_errors_have_status_and_diagnostic():
    for arg in ('--bogus','operand','--','--clear-config=true','--clear-config=false','--clear-config','--View'):
        args=[arg] if arg!='--clear-config' else ['--clear-config','true']
        r=run(args)
        assert r.returncode==2 and r.stdout==b''
        s=r.stderr.decode(); assert 'error:' in s and arg in s and "For more information, try '--help'." in s
        assert 'Usage: executable' in s

def test_clear_config_only_target_file():
    with tempfile.TemporaryDirectory() as t:
        d=confdir(t); d.mkdir(); (d/'config.json').write_text('{}'); (d/'keep').write_text('x')
        r=run(['--clear-config'],env={'XDG_CONFIG_HOME':t})
        assert (r.returncode,r.stdout,r.stderr)==(0,b'',b'')
        assert d.is_dir() and not (d/'config.json').exists() and (d/'keep').read_text()=='x'

def test_clear_missing_exact_error():
    with tempfile.TemporaryDirectory() as t:
        r=run(['--clear-config'],env={'XDG_CONFIG_HOME':t})
        assert (r.returncode,r.stdout,r.stderr)==(0,b'',b' ERROR eureka > No such file or directory (os error 2)\n')

def test_clear_then_setup_again():
    with tempfile.TemporaryDirectory() as t:
        d=write_config(t,'/old'); run(['--clear-config'],env={'XDG_CONFIG_HOME':t})
        r=run([],env={'XDG_CONFIG_HOME':t},data=b'/new\n')
        assert r.returncode==0 and r.stdout.endswith(b'First time setup complete. Happy ideation!\n')
        assert json.loads((d/'config.json').read_text())=={'repo':'/new'}

def test_setup_exact_config_and_banner():
    with tempfile.TemporaryDirectory() as t:
        path='/tmp/path with spaces/λ'; r=run([],env={'XDG_CONFIG_HOME':t},data=(path+'\nignored\n').encode())
        assert r.returncode==0 and r.stderr==b'' and r.stdout==SETUP_HEAD+b'First time setup complete. Happy ideation!\n'
        assert (confdir(t)/'config.json').read_bytes()==json.dumps({'repo':path},ensure_ascii=False,separators=(',',':')).encode()

def test_setup_rejects_empty_and_relative_lines():
    with tempfile.TemporaryDirectory() as t:
        r=run([],env={'XDG_CONFIG_HOME':t},data=b'  \nrelative/path\n/tmp/ok\n')
        again=b'\x1b[0m\x1b[1m\x1b[32mAbsolute path to your idea repo\n\x1b[0m> '
        assert r.returncode==0 and r.stdout==SETUP_HEAD+again+b'\x1b[0m\x1b[31mPath must be absolute\n\x1b[0m'+again+b'First time setup complete. Happy ideation!\n'
        assert json.loads((confdir(t)/'config.json').read_text())=={'repo':'/tmp/ok'}

def test_setup_preserves_lexical_absolute_paths_and_long_json():
    path='/x/'+('λ\\"\t '*350)
    with tempfile.TemporaryDirectory() as t:
        r=run([],env={'XDG_CONFIG_HOME':t},data=(path+'\n').encode())
        assert r.returncode==0 and json.loads((confdir(t)/'config.json').read_text())=={'repo':path}
        assert (confdir(t)/'config.json').read_bytes()==json.dumps({'repo':path},ensure_ascii=False,separators=(',',':')).encode()

def test_config_location_xdg_empty_overrides_home():
    with tempfile.TemporaryDirectory() as t:
        home=pathlib.Path(t)/'home'; home.mkdir(); write_config(home/'.config','/wrong')
        cwd=pathlib.Path(t)/'work'; cwd.mkdir()
        r=run(['--view'],env={'XDG_CONFIG_HOME':'','HOME':str(home),'PAGER':'missing-pager'},cwd=cwd)
        assert b'No such file or directory' in r.stderr
        assert (cwd/'eureka'/'config.json').exists() is False

def test_config_location_home_and_xdg_independence():
    with tempfile.TemporaryDirectory() as t:
        home=pathlib.Path(t)/'home'; xdg=pathlib.Path(t)/'xdg'; home.mkdir(); xdg.mkdir()
        write_config(home/'.config','/home-repo'); write_config(xdg,'/xdg-repo')
        a=run(['--view'],env={'HOME':str(home),'PAGER':'nope'})
        b=run(['--view'],env={'HOME':str(home),'XDG_CONFIG_HOME':str(xdg),'PAGER':'nope'})
        assert b'/home-repo/README.md' not in a.stderr and b'/xdg-repo/README.md' not in b.stderr
        assert a.returncode==b.returncode==0

def test_view_exact_bytes_cat_and_extra_config_fields():
    with tempfile.TemporaryDirectory() as t:
        root=pathlib.Path(t); repo=root/'repo'; repo.mkdir(); content='λ\n\n$HOME \' "\\\n'
        (repo/'README.md').write_bytes(content.encode()); write_config(root/'cfg',str(repo),other={'x':1})
        r=run(['--view'],env={'XDG_CONFIG_HOME':str(root/'cfg'),'PAGER':'cat'})
        assert (r.returncode,r.stdout,r.stderr)==(0,content.encode(),b'')

def test_view_pager_path_single_argument_echo():
    with tempfile.TemporaryDirectory() as t:
        root=pathlib.Path(t); repo=root/'sp ace λ'; repo.mkdir(); (repo/'README.md').write_text('x')
        write_config(root/'cfg',str(repo)); r=run(['-v'],env={'XDG_CONFIG_HOME':str(root/'cfg'),'PAGER':'echo'})
        assert r.stdout==str(repo/'README.md').encode()+b'\n' and r.stderr==b''

def test_view_default_pager_and_literal_pager_value_fail():
    with tempfile.TemporaryDirectory() as t:
        root=pathlib.Path(t); repo=root/'r'; repo.mkdir(); (repo/'README.md').write_text('a\n'); write_config(root/'cfg',str(repo))
        a=run(['--view'],env={'XDG_CONFIG_HOME':str(root/'cfg'),'PAGER':'head -n 3'})
        assert a.returncode==0 and a.stdout==b'' and b'No such file or directory' in a.stderr
        b=run(['--view'],env={'XDG_CONFIG_HOME':str(root/'cfg'),'PAGER':'cat'})
        assert b.stdout==b'a\n'

def test_view_missing_config_and_missing_readme_errors():
    with tempfile.TemporaryDirectory() as t:
        r=run(['--view'],env={'XDG_CONFIG_HOME':t})
        assert r.returncode==0 and r.stdout==b'' and b'ERROR eureka >' in r.stderr
        root=pathlib.Path(t); write_config(root,'/nonexistent-eureka-repo')
        r=run(['--view'],env={'XDG_CONFIG_HOME':t,'PAGER':'cat'})
        assert (r.returncode,r.stdout,r.stderr)==(0,b'',b' ERROR eureka > No such file or directory (os error 2)\n')

def test_view_malformed_json_exact_errors():
    cases=[(b'{"repo": "/some/path"',b' ERROR eureka > EOF while parsing an object at line 1 column 21\n'),
           (b'{repo: "/some/path"}',b' ERROR eureka > key must be a string at line 1 column 2\n'),
           (b'{"other_key": "value"}',b' ERROR eureka > missing field `repo` at line 1 column 22\n'),
           (b'   \n  \t  \n',b' ERROR eureka > EOF while parsing a value at line 3 column 0\n'),
           (b'{\n  // This is a comment\n  "repo": "/some/path"\n}',b' ERROR eureka > key must be a string at line 2 column 3\n')]
    for i,(raw,err) in enumerate(cases):
        with tempfile.TemporaryDirectory() as t:
            d=confdir(t); d.mkdir(); (d/'config.json').write_bytes(raw)
            r=run(['--view'],env={'XDG_CONFIG_HOME':t})
            assert (r.returncode,r.stdout,r.stderr)==(0,b'',err), i

def test_empty_config_is_capture_mode_not_setup():
    with tempfile.TemporaryDirectory() as t:
        d=confdir(t); d.mkdir(); (d/'config.json').write_bytes(b'')
        r=run([],env={'XDG_CONFIG_HOME':t},data=b'idea\n')
        assert r.returncode==0 and b'First Time Setup' not in r.stdout and r.stdout.startswith(PROMPT)
        assert b"failed to resolve path ''" in r.stderr

def test_unflagged_malformed_config_falls_back_to_setup():
    with tempfile.TemporaryDirectory() as t:
        d=confdir(t); d.mkdir(); (d/'config.json').write_text('{"repo": "/some/path"')
        r=run([],env={'XDG_CONFIG_HOME':t},data=b'unused summary\n/tmp/repaired\n')
        assert r.returncode==0 and b'First Time Setup' in r.stdout and b'Path must be absolute' in r.stdout
        assert json.loads((d/'config.json').read_text())=={'repo':'/tmp/repaired'}

def test_view_rejects_nonstring_and_ignores_unknown_fields():
    with tempfile.TemporaryDirectory() as t:
        d=confdir(t); d.mkdir(); (d/'config.json').write_text('{"repo": 3}')
        r=run(['--view'],env={'XDG_CONFIG_HOME':t})
        assert r.returncode==0 and r.stdout==b'' and r.stderr.startswith(b' ERROR eureka >')

def test_view_clear_precedence_both_orders():
    for args in (['--clear-config','--view'],['--view','--clear-config']):
        with tempfile.TemporaryDirectory() as t:
            write_config(t,'/repo'); r=run(args,env={'XDG_CONFIG_HOME':t})
            assert (r.returncode,r.stdout,r.stderr)==(0,b'',b'') and not (confdir(t)/'config.json').exists()

def test_capture_prompts_until_nonempty_then_git_failure():
    with tempfile.TemporaryDirectory() as t:
        write_config(t,'/not-here-eureka')
        r=run([],env={'XDG_CONFIG_HOME':t},data=b' \n\t\nsummary\n')
        assert r.returncode==0 and r.stdout==PROMPT*3
        assert b"failed to resolve path '/not-here-eureka'" in r.stderr and b'Adding and committing' not in r.stdout

def test_capture_summary_preserved_commit_editor_and_main_checkout():
    with tempfile.TemporaryDirectory() as t:
        root=pathlib.Path(t); repo=root/'repo'; repo_init(repo,'other'); git(repo,'checkout','-b','main'); git(repo,'checkout','other')
        editor=root/'editor'; editor.write_text('#!/bin/sh\nprintf "edited λ\\n" >> "$1"\n'); editor.chmod(0o755)
        bare=root/'remote.git'; subprocess.run(['git','init','--bare',str(bare)],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        git(repo,'remote','add','origin',str(bare))
        cfg=root/'cfg'; write_config(cfg,str(repo)); summary='  idea "$x" λ\\ tail  '
        r=run([],env={'XDG_CONFIG_HOME':str(cfg),'EDITOR':str(editor)},data=(summary+'\n').encode())
        assert r.returncode==0 and r.stdout==PROMPT+b'Adding and committing your new idea to main..\nAdded and committed!\nPushing your new idea..\nPushed!\n' and r.stderr==b''
        assert git(repo,'branch','--show-current')=='main'
        assert git(repo,'log','-1','--format=%s')==summary.strip()
        assert (repo/'README.md').read_text().endswith('edited λ\n')
        assert git(bare,'rev-parse','refs/heads/main')==git(repo,'rev-parse','main')

def test_capture_noop_editor_still_commits_and_absent_origin_logs():
    with tempfile.TemporaryDirectory() as t:
        root=pathlib.Path(t); repo=root/'repo'; repo_init(repo)
        cfg=root/'cfg'; write_config(cfg,str(repo))
        r=run([],env={'XDG_CONFIG_HOME':str(cfg),'EDITOR':'true'},data=b'new thought\n')
        assert r.returncode==0 and r.stdout==PROMPT+b'Adding and committing your new idea to main..\nAdded and committed!\nPushing your new idea..\n'
        assert r.stderr==b" ERROR eureka > remote 'origin' does not exist; class=Config (7); code=NotFound (-3)\n"
        assert git(repo,'log','-1','--format=%s')=='new thought'

def test_capture_unborn_master_reaches_add_failure():
    with tempfile.TemporaryDirectory() as t:
        root=pathlib.Path(t); repo=root/'repo'; repo.mkdir(); subprocess.run(['git','init',str(repo)],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        git(repo,'config','user.name','Tester'); git(repo,'config','user.email','tester@example.test'); (repo/'README.md').write_text('x')
        cfg=root/'cfg'; write_config(cfg,str(repo)); r=run([],env={'XDG_CONFIG_HOME':str(cfg),'EDITOR':'true'},data=b'idea\n')
        assert r.returncode==0 and r.stdout==PROMPT+b'Adding and committing your new idea to main..\n'
        assert r.stderr==b" ERROR eureka > reference 'refs/heads/master' not found; class=Reference (4); code=UnbornBranch (-9)\n"

def test_capture_non_git_does_not_launch_editor_or_progress():
    with tempfile.TemporaryDirectory() as t:
        root=pathlib.Path(t); repo=root/'plain'; repo.mkdir(); marker=root/'marker'
        editor=root/'editor'; editor.write_text('#!/bin/sh\ntouch '+str(marker)+'\n'); editor.chmod(0o755)
        cfg=root/'cfg'; write_config(cfg,str(repo)); r=run([],env={'XDG_CONFIG_HOME':str(cfg),'EDITOR':str(editor)},data=b'idea\n')
        assert r.returncode==0 and r.stdout==PROMPT and not marker.exists()
        assert b'could not find repository from' in r.stderr

def test_capture_main_only_and_repeat_noop_commits_are_distinct():
    with tempfile.TemporaryDirectory() as t:
        root=pathlib.Path(t); repo=root/'repo'; repo_init(repo,'master'); cfg=root/'cfg'; write_config(cfg,str(repo))
        for s in ('first','second'):
            r=run([],env={'XDG_CONFIG_HOME':str(cfg),'EDITOR':'true'},data=(s+'\n').encode())
            assert r.returncode==0 and b'Added and committed!\n' in r.stdout
        assert git(repo,'branch','--show-current')=='main'
        assert git(repo,'log','-2','--format=%s')=='second\nfirst'
