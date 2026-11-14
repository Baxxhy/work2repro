import os, pathlib, subprocess, textwrap
import pytest

ROOT = pathlib.Path(__file__).resolve().parent
EXE = pathlib.Path('/workspace/executable')

def call(args=(), *, cwd=None, config=None, env=None):
    cwd = pathlib.Path(cwd or ROOT); cwd.mkdir(parents=True, exist_ok=True)
    e = os.environ.copy()
    for k in ('PIER_CONFIG_PATH','SHELL','EDITOR','XDG_CONFIG_HOME'): e.pop(k, None)
    e.update(HOME=str(cwd/'home'), XDG_CONFIG_HOME=str(cwd/'xdg'))
    if env: e.update({k:str(v) for k,v in env.items()})
    if config is not None: args = ['-c',str(config),*args]
    return subprocess.run([str(EXE),*map(str,args)], cwd=cwd, env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)

def config(path, body):
    path=pathlib.Path(path); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(textwrap.dedent(body),encoding='utf8'); return path

def fail(p, text):
    assert p.returncode != 0 and p.stdout == b'' and p.stderr.startswith(b'error: ')
    assert text.encode() in p.stderr

def data(path):
    import tomllib
    return tomllib.loads(pathlib.Path(path).read_text(encoding='utf8'))

@pytest.mark.parametrize('arg',['--version','-V'],ids=['long','short'])
def test_version(arg):
    p=call([arg]); assert (p.returncode,p.stdout,p.stderr)==(0,b'pier 0.1.6\n',b'')

def test_main_help():
    p=call(['--help']); s=p.stdout.decode(); assert p.returncode==0
    assert s.splitlines()[0]=='pier 0.1.6'
    for x in ['A simple script management CLI','USAGE:','FLAGS:','OPTIONS:','ARGS:','SUBCOMMANDS:']: assert x in s
    for x in ['add','config-init','copy','edit','list','move','remove','run','show','help']: assert '    '+x in s

@pytest.mark.parametrize('alias,canonical',[('init','config-init'),('cp','copy'),('ls','list'),('mv','move'),('rename','move'),('rm','remove')],ids=['init','cp','ls','mv','rename','rm'])
def test_alias_help(alias,canonical):
    p=call([alias,'--help']); assert p.returncode==0 and f'USAGE:\n    executable {canonical}'.encode() in p.stdout

def test_subcommand_versions():
    for n in ['add','config-init','copy','edit','list','move','remove','run','show']:
        p=call([n,'-V']); assert p.returncode==0 and p.stdout==f'executable-{n} 0.1.6\n'.encode()

def test_parser_precedence_and_verbose(tmp_path):
    for a in [[],['-v'],['--bad']]:
        p=call(a,cwd=tmp_path); assert p.returncode and b'USAGE:' in p.stderr and b'For more information try --help' in p.stderr
    for a in [['-c'],['--config-file']]:
        p=call(a,cwd=tmp_path); assert p.returncode and b'executable <alias> --config-file <path>' in p.stderr
    for a in [['-vv'],['-v','-v'],['-v','--verbose']]:
        p=call(a,cwd=tmp_path); assert p.returncode and b'executable <alias> --verbose' in p.stderr
    c=config(tmp_path/'c.toml',"[scripts.x]\ncommand='x'\n")
    p=call(['-vv','show','x'],cwd=tmp_path,config=c); assert b'provided more than once' in p.stderr

def test_direct_alias_compatibility(tmp_path):
    c=config(tmp_path/'c.toml',"[scripts.x]\ncommand='true'\n")
    fail(call(['absent'],cwd=tmp_path,config=c),'AliasNotFound: No script found by alias absent')
    p=call(['whatever','--help'],cwd=tmp_path); assert p.returncode==0 and b'SUBCOMMANDS:' in p.stdout
    p=call(['hello'],cwd=tmp_path,config=c); assert p.returncode and b'subcommand' in p.stderr and b"wasn't recognized" in p.stderr

def test_discovery_precedence_and_paths(tmp_path):
    cwd=tmp_path/'work space'; cwd.mkdir()
    config(cwd/'pier.toml',"[scripts.local]\ncommand='local'\n")
    xdg=config(tmp_path/'xdg'/'pier'/'config.toml',"[scripts.xdg]\ncommand='xdg'\n")
    assert call(['show','local'],cwd=cwd).stdout==b'local\n'
    assert call(['show','xdg'],cwd=cwd,env={'XDG_CONFIG_HOME':tmp_path/'xdg'}).stdout==b'xdg\n'
    special=config(tmp_path/'配置 file.toml',"[scripts.y]\ncommand='ok'\n")
    assert call(['show','y'],cwd=cwd,config=special).stdout==b'ok\n'
    assert call(['show','y'],cwd=cwd,config=special,env={'PIER_CONFIG_PATH':xdg}).stdout==b'xdg\n'

def test_empty_env_and_read_failures(tmp_path):
    config(tmp_path/'pier.toml',"[scripts.x]\ncommand='x'\n")
    fail(call(['list'],cwd=tmp_path,env={'PIER_CONFIG_PATH':''}),'Unable to read config from file : No such file or directory (os error 2)')
    p=call(['list'],cwd=tmp_path/'none'); assert p.stderr==b'error: No default config file found. See help for more info.\n'
    missing=tmp_path/'missing.toml'; fail(call(['list'],cwd=tmp_path,config=missing),f'Unable to read config from file {missing}:')
    fail(call(['list'],cwd=tmp_path,config=tmp_path),'Is a directory (os error 21)')

def test_init_exact_nonoverwrite_and_one_level_mkdir(tmp_path):
    c=tmp_path/'parent'/'pier.toml'; p=call(['config-init'],cwd=tmp_path,config=c)
    assert p.returncode==0 and p.stdout==b'Added hello-pier\n'
    assert c.read_text()=="[scripts.hello-pier]\ncommand = 'echo Hello, Pier!'\ndescription = 'This is an example command.'\n\n[default]\n"
    p=call(['init'],cwd=tmp_path,config=c); assert p.returncode==1 and p.stderr==f'error: Cannot initialize config at {c}, file already exists.\n'.encode()
    p=call(['init'],cwd=tmp_path,config=tmp_path/'absent'/'deeper'/'x'); assert p.returncode and b'Failed to create directory' in p.stderr

def test_schema_compatibility_errors(tmp_path):
    cases=[('[scripts.x\ncommand="x"','expected a right bracket, found a newline at line 1'),("[scripts.x]\ncommand='x'\ncommand='y'",'duplicate field `command` for key `scripts.x`'),("[scripts.x]\ndescription='x'",'missing field `command` for key `scripts.x`'),("scripts='x'",'expected map')]
    for i,(body,detail) in enumerate(cases): fail(call(['list'],cwd=tmp_path,config=config(tmp_path/f'{i}.toml',body)),detail)

def test_add_metadata_literal_command_and_force(tmp_path):
    c=config(tmp_path/'c.toml',"[scripts.keep]\ncommand='old'\ntags=[]\n")
    cmd="printf '$HOME `echo no` \\\\ | >\nsecond"
    p=call(['add','-a','New.界','-d','','-t','one','-t','two','-t','one',cmd],cwd=tmp_path,config=c)
    assert p.returncode==0 and p.stdout=='Added New.界\n'.encode()
    assert data(c)['scripts']['New.界']=={'command':cmd,'description':'','tags':['one','two','one']}
    old=c.read_bytes(); fail(call(['add','-a','New.界','replacement'],cwd=tmp_path,config=c),'AliasAlreadyExists:  New.界'); assert c.read_bytes()==old
    p=call(['add','-a','New.界','--force','replacement'],cwd=tmp_path,config=c)
    assert p.returncode==0 and data(c)['scripts']['New.界']=={'command':'replacement'}

def test_editor_add_and_failed_editor(tmp_path):
    c=config(tmp_path/'c.toml','[scripts]\n'); ed=tmp_path/'editor'
    ed.write_text("#!/usr/bin/env python3\nimport pathlib,sys\npathlib.Path(sys.argv[1]).write_text('line\\n',encoding='utf8')\n"); ed.chmod(0o755)
    assert call(['add','-a','edited'],cwd=tmp_path,config=c,env={'EDITOR':ed}).returncode==0
    assert data(c)['scripts']['edited']['command']=='line\n'
    p=call(['add','-a','failed'],cwd=tmp_path,config=c,env={'EDITOR':tmp_path/'missing-editor'}); assert p.returncode and b'editor' in p.stderr.lower() and 'failed' not in data(c)['scripts']

def test_show_and_empty_catalog(tmp_path):
    c=config(tmp_path/'c.toml',"[scripts.multi]\ncommand='''one\n界 two'''\n[scripts.empty]\ncommand=''\n")
    assert call(['show','multi'],cwd=tmp_path,config=c).stdout=='one\n界 two\n'.encode()
    assert call(['show','empty'],cwd=tmp_path,config=c).stdout==b'\n'
    fail(call(['show','missing'],cwd=tmp_path,config=c),'AliasNotFound: No script found by alias missing')
    empty=config(tmp_path/'empty.toml','[default]\n')
    for a in [['list'],['run','x'],['remove','x'],['show','x'],['edit','x']]: fail(call(a,cwd=tmp_path,config=empty),'No scripts exist. Would you like to add a new script?')

def test_edit_full_contents_and_metadata(tmp_path):
    c=config(tmp_path/'c.toml',"[scripts.x]\ncommand='old'\ndescription='keep'\nreference='ref'\ntags=[]\n")
    ed=tmp_path/'editor'; ed.write_text("#!/usr/bin/env python3\nimport pathlib,sys\npathlib.Path(sys.argv[1]).write_text('new\\n\\n界',encoding='utf8')\n"); ed.chmod(0o755)
    p=call(['edit','x'],cwd=tmp_path,config=c,env={'EDITOR':ed})
    assert p.returncode==0 and p.stdout==b'Edited x\n'
    assert data(c)['scripts']['x']=={'command':'new\n\n界','description':'keep','reference':'ref','tags':[]}

def test_copy_move_collision_order_and_legacy_alias(tmp_path):
    c=config(tmp_path/'c.toml',"""
        [scripts.a]
        command='A'
        alias=99
        tags=['x','x']
        [scripts.b]
        command='B'
        description='destination'
        [scripts.other]
        command='O'
        alias='old'
    """)
    p=call(['cp','a','c'],cwd=tmp_path,config=c); assert p.returncode==0 and p.stdout==b'Copy from alias a to new alias c\n'
    d=data(c)['scripts']; assert d['a']==d['c']=={'command':'A','tags':['x','x']} and 'alias' not in d['other']
    old=c.read_bytes(); fail(call(['copy','missing','b'],cwd=tmp_path,config=c),'AliasAlreadyExists:  b'); assert c.read_bytes()==old
    p=call(['move','a','b','--force'],cwd=tmp_path,config=c); assert p.returncode==0 and p.stdout==b'Move from alias a to new alias b\n'
    d=data(c)['scripts']; assert 'a' not in d and d['b']=={'command':'A','tags':['x','x']}

def test_remove_last_and_failed_move_unchanged(tmp_path):
    c=config(tmp_path/'c.toml',"[scripts.x]\ncommand='x'\n"); old=c.read_bytes()
    fail(call(['move','absent','free'],cwd=tmp_path,config=c),'AliasNotFound: No script found by alias absent'); assert c.read_bytes()==old
    p=call(['rm','x'],cwd=tmp_path,config=c); assert p.returncode==0 and p.stdout==b'Removed x\n' and 'scripts' in data(c)

def test_list_alias_sort_filter_duplicates_and_exactness(tmp_path):
    c=config(tmp_path/'c.toml',"""
        [scripts.z]
        command='z'
        tags=['red']
        [scripts.a]
        command='a'
        tags=['red','blue']
        [scripts.m]
        command='m'
    """)
    assert call(['ls','-q'],cwd=tmp_path,config=c).stdout==b'a\nm\nz\n'
    assert call(['list','-q','-t','red','-t','blue'],cwd=tmp_path,config=c).stdout==b'a\na\nz\n'
    assert call(['list','-q','-t','RED'],cwd=tmp_path,config=c).stdout==b''

def test_list_format_truncation_unicode_and_modes(tmp_path):
    c=config(tmp_path/'c.toml',"[scripts.u]\ncommand='  ab界dé  '\n[scripts.h]\ncommand='#!/bin/sh'\n")
    def output(*a): return call(['list',*a],cwd=tmp_path,config=c).stdout.decode()
    assert '  ab' in output('--cmd_width','4') and '  ab界' in output('--cmd_width','7')
    p=call(['list','--cmd_width','5'],cwd=tmp_path,config=c); assert p.returncode==101 and p.stdout==b'' and b'not a char boundary' in p.stderr
    assert '  ab界dé  ' in output('-l','--cmd_width','4')
    assert output('-q','--cmd_width','4').splitlines()==['h','u']
    for args in [['--cmd_width=-1'],['--cmd_width','-1'],['--cmd_width','bad']]:
        p=call(['list',*args],cwd=tmp_path,config=c); assert p.returncode and (b'Invalid value for' in p.stderr or b"Found argument '-1'" in p.stderr)

def test_run_inline_direct_args_status_and_verbose(tmp_path):
    c=config(tmp_path/'c.toml',"[scripts.echo]\ncommand='printf \"%s|%s\\\\n\" \"$0\" \"$1\"'\n[scripts.fail]\ncommand='exit 42'\n[scripts.empty]\ncommand=''\n")
    p=call(['run','echo','--','a b'],cwd=tmp_path,config=c); assert p.returncode==0 and p.stdout==b'echo|a b\n'
    assert call(['echo','--','direct'],cwd=tmp_path,config=c).stdout==b'echo|direct\n'
    assert call(['run','fail'],cwd=tmp_path,config=c).returncode==42
    assert call(['run','empty'],cwd=tmp_path,config=c).stdout==b''
    p=call(['run','echo','-n'],cwd=tmp_path,config=c); assert p.returncode and b"Found argument '-n'" in p.stderr

def test_run_stderr_shell_empty_and_verbose_shebang(tmp_path):
    c=config(tmp_path/'c.toml',"[scripts.err]\ncommand='printf error >&2'\n[scripts.sh]\ncommand='''#!/bin/sh\nprintf 'out %s\\n' \"$1\"'''\n")
    p=call(['run','err'],cwd=tmp_path,config=c); assert p.returncode==0 and p.stderr==b'error\n\n'
    p=call(['run','err'],cwd=tmp_path,config=c,env={'SHELL':''}); assert p.returncode==1 and b'Command execution failed with: No such file or directory (os error 2)' in p.stderr
    p=call(['-v','run','sh','--','arg'],cwd=tmp_path,config=c)
    assert p.stdout==b'Starting script "sh"\n-------------------------\nout arg\n-------------------------\nScript complete\n'
