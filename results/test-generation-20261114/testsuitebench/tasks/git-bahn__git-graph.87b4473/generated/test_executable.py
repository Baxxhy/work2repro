import os, subprocess, pathlib, re, xml.etree.ElementTree as ET
import pytest

EXE = '/workspace/executable'

def run(*args, cwd=None, env=None):
    return subprocess.run([EXE, *map(str,args)], cwd=cwd, env=env, text=True, capture_output=True)

def git(repo, *args):
    return subprocess.run(['git', *args], cwd=repo, check=True, text=True, capture_output=True).stdout.strip()

@pytest.fixture
def repo(tmp_path):
    p=tmp_path/'repo'; p.mkdir()
    git(p,'init','-q','-b','master'); git(p,'config','user.name','Test User'); git(p,'config','user.email','test@example.com')
    (p/'file.txt').write_text('initial'); git(p,'add','.'); git(p,'commit','-qm','First commit')
    (p/'file.txt').write_text('second'); git(p,'commit','-qam','Second commit')
    (p/'file.txt').write_text('third'); git(p,'commit','-qam','Third commit')
    return p

def sha(repo, rev): return git(repo,'rev-parse',rev)

def test_exact_version_and_short_alias():
    for opt in ('--version','-V'):
        r=run(opt,'garbage'); assert (r.returncode,r.stdout,r.stderr)==(0,'git-graph 0.7.0\n','')

def test_help_forms_and_precedence():
    short=run('-h'); long=run('--help'); assert short.returncode==long.returncode==0
    for s in (short.stdout,long.stdout):
        for x in ('git-graph','Structured Git graphs for your branching model','https://github.com/mlange-42/git-graph','EXAMPES:','Usage:','Commands:','Options:','model','help','[auto|always|never]','[normal/thin|round|bold|double|ascii]'):
            assert x in s
    assert short.stdout != long.stdout
    assert run('help').stdout==long.stdout
    assert run('--help','--unknown').stdout==long.stdout

def test_help_model_exact():
    a=run('help','model'); b=run('model','--help')
    assert a.returncode==b.returncode==0 and a.stdout==b.stdout
    assert 'Usage: executable model [OPTIONS] [model]' in a.stdout
    assert '[simple|git-flow|none]' in a.stdout
    assert run('help','--help').returncode==2

def test_cli_errors_and_root_option_placement():
    r=run('--invalid-flag'); assert r.returncode==2 and "unexpected argument '--invalid-flag' found" in r.stderr and 'Usage: executable [OPTIONS] [COMMAND]' in r.stderr
    assert run('unknown').returncode==2
    assert run('--no-pager').returncode==2 and "unexpected argument '--no-pager'" in run('--no-pager').stderr
    assert run('model','--no-color').returncode==2
    assert run('model','--bad').returncode==2 and "-- <token>" in run('model','--bad').stderr

def test_model_list_is_independent_of_config(tmp_path):
    env=os.environ.copy(); env['XDG_CONFIG_HOME']=str(tmp_path/'empty-config'); env['HOME']=str(tmp_path/'home')
    for opt in ('--list','-l'):
        r=run('model',opt,env=env); assert r.returncode==0 and r.stdout=='git-flow\nnone\nsimple\n'
    assert sorted(p.name for p in (tmp_path/'empty-config/git-graph/models').glob('*.toml'))==['git-flow.toml','none.toml','simple.toml']

def test_repository_discovery_paths_and_unicode(repo,tmp_path):
    sub=repo/'深い folder'; sub.mkdir(); f=sub/'some file'; f.write_text('x')
    for path in (repo,sub,f,repo/'.git'):
        r=run('--path',path); assert r.returncode==0 and 'First commit' in r.stdout
    link=tmp_path/'link'; link.symlink_to(sub, target_is_directory=True)
    assert run('--path',link).returncode==0
    outer=tmp_path/'outer'; outer.mkdir(); git(outer,'init','-q','-b','master'); git(outer,'config','user.name','T'); git(outer,'config','user.email','t@x'); (outer/'o').write_text('o'); git(outer,'add','.'); git(outer,'commit','-qm','Outer')
    inner=outer/'inner'; inner.mkdir(); git(inner,'init','-q','-b','master'); git(inner,'config','user.name','T'); git(inner,'config','user.email','t@x'); (inner/'i').write_text('i'); git(inner,'add','.'); git(inner,'commit','-qm','Inner')
    assert 'Outer' in run('--path',outer).stdout and 'Inner' not in run('--path',outer).stdout
    assert 'Inner' in run('--path',inner).stdout and 'Outer' not in run('--path',inner).stdout

def test_repository_discovery_failures(tmp_path):
    missing=tmp_path/'missing'; r=run('--path',missing)
    assert r.returncode==1 and str(missing) in r.stderr and 'failed to resolve path' in r.stderr
    ordinary=tmp_path/'outside'; ordinary.write_text('x'); r=run('--path',ordinary)
    assert r.returncode==1 and 'could not find repository' in r.stderr and str(ordinary) in r.stderr

def test_empty_repo_error(tmp_path):
    p=tmp_path/'empty'; p.mkdir(); git(p,'init','-q','-b','master')
    r=run('--path',p); assert r.returncode==1 and not r.stdout and 'reference' in r.stderr and 'not found' in r.stderr

def test_single_commit_output_decorations_and_subject(tmp_path):
    p=tmp_path/'one'; p.mkdir(); git(p,'init','-q','-b','master'); git(p,'config','user.name','T'); git(p,'config','user.email','t@x'); (p/'x').write_text('x'); git(p,'add','.'); git(p,'commit','-qm','Single commit')
    r=run('--path',p); h=sha(p,'HEAD')[:7]
    assert r.returncode==0 and r.stdout==f' ●  {h} (HEAD -> master) Single commit\n' and not r.stderr

def test_linear_order_reverse_count_and_zero(repo):
    newest=run('--path',repo); hashes=[sha(repo,x)[:7] for x in ('HEAD','HEAD~1','HEAD~2')]
    assert [x for x in hashes if x in newest.stdout]==hashes
    assert newest.stdout.index('Third commit')<newest.stdout.index('Second commit')<newest.stdout.index('First commit')
    rev=run('--path',repo,'--reverse'); assert rev.stdout.index('First commit')<rev.stdout.index('Third commit')
    assert 'Third commit' in run('--path',repo,'--reverse','--max-count','1').stdout
    assert run('--path',repo,'--max-count','0').stdout==''
    assert len(re.findall(r'(?m)^ ●',run('--path',repo,'--max-count','2').stdout))==2
    assert len(re.findall(r'(?m)^ ●',run('--path',repo,'--max-count','99').stdout))==3

def test_ref_decorations_tags_and_detached(repo):
    git(repo,'branch','feature'); git(repo,'tag','z-tag'); git(repo,'tag','a-tag')
    out=run('--path',repo).stdout
    assert '(HEAD -> master, feature)' in out and '[a-tag, z-tag]' in out
    git(repo,'checkout','--detach','-q'); out=run('--path',repo).stdout
    assert '(master, feature)' in out and 'HEAD ->' in out

def test_local_excludes_remote_only_history(repo):
    git(repo,'branch','remote-only'); git(repo,'update-ref','refs/remotes/origin/remote-only',sha(repo,'HEAD'))
    out=run('--path',repo).stdout
    assert '(origin/remote-only)' in out
    local=run('--path',repo,'--local').stdout
    assert 'origin/remote-only' not in local and 'Third commit' in local

def test_commit_formats_and_unicode(repo):
    (repo/'u.txt').write_text('u'); git(repo,'add','.'); git(repo,'commit','-qm','雪 café\n\nbody paragraph')
    for fmt in ('oneline','o','short','s','medium','m','full','f'):
        r=run('--path',repo,'--format',fmt); assert r.returncode==0 and '雪 café' in r.stdout
    custom=run('--path',repo,'--format','%H|%h|%P|%s|%an|%ae|%cn|%ce|%as|%cs|%n%B|%invalid')
    assert custom.returncode==0 and sha(repo,'HEAD') in custom.stdout and 'Test User' in custom.stdout and '%invalid' in custom.stdout and 'body paragraph' in custom.stdout
    assert run('--path',repo,'--format','%s').stdout.startswith(' ●  雪 café')

def test_wrap_and_multiline_graph_prefix(repo):
    (repo/'x').write_text('x'); git(repo,'add','.'); git(repo,'commit','-qm','This is a long commit message that should be wrapped at the specified width')
    r=run('--path',repo,'--format','%s','--wrap','40','0','0')
    assert 'This is a long commit message that\n' in r.stdout and 'should be wrapped at the specified width' in r.stdout
    h=run('--path',repo,'--format','%H','--wrap','5','0','0'); assert len([x for x in h.stdout.splitlines() if x.strip()])>=8
    assert run('--path',repo,'--format','%s','--wrap','none').stdout.endswith('This is a long commit message that should be wrapped at the specified width\n')

def test_styles_color_and_debug(repo):
    for style in ('normal','thin','n','t','round','r','bold','b','double','d','ascii','a'):
        r=run('--path',repo,'--style',style); assert r.returncode==0 and 'Third commit' in r.stdout
    asciiout=run('--path',repo,'--style','ascii').stdout
    assert all(ord(c)<128 for c in asciiout)
    colored=run('--path',repo,'--color','always'); assert '\x1b[' in colored.stdout
    for args in (('--color','never'),('--no-color',),('--color','always','--no-color')):
        assert '\x1b[' not in run('--path',repo,*args).stdout
    dbg=run('--path',repo,'--debug'); assert dbg.returncode==0 and 'Third commit' in dbg.stdout and '(col ' in dbg.stderr and 'Some(' in dbg.stderr and 'ms' in dbg.stderr and 'commits)' in dbg.stderr

def test_cli_value_errors_and_repetitions(repo):
    for opt,val in (('--color','bad'),('--style','bad'),('--model','bad')):
        r=run('--path',repo,opt,val); assert r.returncode==1 and r.stderr
    assert run('--path',repo,'--max-count','abc').returncode==1
    for opt,val in (('--model','simple'),('--color','never'),('--style','ascii')):
        assert run('--path',repo,opt,val,opt,val).returncode==2
    assert run('--path',repo,'--max-count','-1').returncode==2
    assert run('--path',repo,'--wrap','bad').returncode==1
    assert run('--path',repo,'--wrap','1','2','3','9').returncode==2

def test_skip_owner_warning(repo):
    r=run('--path',repo,'--skip-repo-owner-validation')
    assert r.returncode==0 and r.stdout.startswith('Warning: skip-repo-owner-validation is set! \n')

def test_model_persistence_and_invalid_name(repo,tmp_path):
    env=os.environ.copy(); env['XDG_CONFIG_HOME']=str(tmp_path/'cfg')
    q=run('--path',repo,'model',env=env); assert (q.returncode,q.stdout,q.stderr)==(0,'No branching model set','')
    setr=run('--path',repo,'model','simple',env=env)
    assert setr.returncode==0 and setr.stdout=='' and setr.stderr=="Branching model set to 'simple'"
    cfg=repo/'.git/git-graph.toml'; assert cfg.read_text()=='model = "simple"\n' and (cfg.stat().st_mode & 0o002)==0
    assert run('--path',repo,'model',env=env).stdout=='simple'
    before=cfg.read_text(); bad=run('--path',repo,'model','missing',env=env)
    assert bad.returncode==1 and 'No branching model named' in bad.stderr and cfg.read_text()==before

def test_model_config_errors_and_unknown_keys(repo,tmp_path):
    env=os.environ.copy(); env['XDG_CONFIG_HOME']=str(tmp_path/'cfg')
    cfg=repo/'.git/git-graph.toml'; cfg.write_text('model = "none"\nextra = true\n')
    assert run('--path',repo,'model',env=env).stdout=='none'
    cfg.write_text('model = [\n')
    r=run('--path',repo,env=env); assert r.returncode==1 and 'TOML parse error' in r.stderr and 'line' in r.stderr.lower()

def test_svg_geometry_and_options(repo):
    out=run('--path',repo,'--svg'); assert out.returncode==0 and out.stderr==''
    root=ET.fromstring(out.stdout); assert root.tag.endswith('svg') and root.attrib['height']=='75' and root.attrib['width']=='30'
    ns={'s':'http://www.w3.org/2000/svg'}
    assert len(root.findall('s:circle',ns))==3
    for i in range(3):
        assert len(root.findall('s:line',ns))==2
    assert run('--path',repo,'--svg','--max-count','0').stdout=='<svg height="30" viewBox="0 0 30 30" width="30" xmlns="http://www.w3.org/2000/svg"/>\n'
    a=run('--path',repo,'--svg').stdout
    for flags in (('--reverse',),('--sparse',),('--style','ascii'),('--color','always')):
        assert run('--path',repo,'--svg',*flags).stdout==a
    lim=ET.fromstring(run('--path',repo,'--svg','--max-count','1').stdout); assert lim.attrib['height']=='45' and len(lim.findall('s:circle',ns))==1
    dbg=run('--path',repo,'--svg','--debug'); ET.fromstring(dbg.stdout); assert 'stroke="cyan"' in dbg.stdout and 'ms' in dbg.stderr

def test_bare_repository_and_model_config(repo,tmp_path):
    bare=tmp_path/'bare.git'; git(repo,'clone','-q','--bare',str(bare))
    r=run('--path',bare); assert r.returncode==0 and 'First commit' in r.stdout
    env=os.environ.copy(); env['XDG_CONFIG_HOME']=str(tmp_path/'cfg')
    assert run('--path',bare,'model','simple',env=env).returncode==0
    assert (bare/'git-graph.toml').read_text()=='model = "simple"\n'
