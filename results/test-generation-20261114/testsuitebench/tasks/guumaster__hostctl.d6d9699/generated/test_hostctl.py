import json
import os
import pathlib
import subprocess
import datetime
import re

BIN = '/workspace/executable'

def invoke(*args, data=None, env=None, cwd=None):
    e = os.environ.copy()
    if env: e.update(env)
    return subprocess.run([BIN, *map(str,args)], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          cwd=cwd or '/workspace/eval', env=e, timeout=8)

def setup_file(tmp_path, content=''):
    p=tmp_path/'hosts'; p.write_text(content,encoding='utf-8'); return p

def run_file(p,*args,data=None,env=None): return invoke(*args,'--host-file',p,data=data,env=env)

def records(p, *args):
    r=run_file(p,*args,'-o','json')
    assert r.returncode==0, (r.stdout,r.stderr)
    return json.loads(r.stdout.decode())

def test_help_version_and_info_are_stable():
    h=invoke()
    assert h.returncode==0 and h.stderr==b''
    s=h.stdout.decode()
    assert s.startswith('\nhostctl is a CLI tool') and 'Available Commands:' in s and '  sync        Sync some system IPs with a profile.' in s
    assert invoke('--help').stdout==h.stdout
    assert invoke('-h').stdout==h.stdout
    assert invoke('--version').stdout==b'hostctl version dev\n'
    assert invoke('-v').stdout==b'hostctl version dev\n'
    i=invoke('info')
    assert i.returncode==0 and b'Version: dev' in i.stdout and b'Your dev tool' in i.stdout

def test_global_options_validate_and_are_position_independent(tmp_path):
    p=setup_file(tmp_path,'# profile.on alpha\n1.2.3.4 a\n# end\n')
    for args in [('--out','json'),('-o=json',),('--out=json',)]:
        r=run_file(p,*args,'status')
        assert r.returncode==0 and json.loads(r.stdout.split(b'\n')[-2] if b'Using hosts' in r.stdout else r.stdout)==[{'Profile':'alpha','Status':'on','IP':'','Host':''}]
    r=run_file(p,'status','--out','json')
    assert r.returncode==0 and '[ℹ]'.encode() not in r.stdout and json.loads(r.stdout)==[{'Profile':'alpha','Status':'on','IP':'','Host':''}]
    r=run_file(p,'status','--help','--bad-flag','extra')
    assert r.returncode!=0 and r.stdout=='[✖] error: unknown flag: --bad-flag\n'.encode() and r.stderr==b''
    assert invoke('rm','x').returncode!=0 and b'unknown command "rm"' in invoke('rm','x').stdout
    assert invoke('enable','--bad-flag').returncode!=0 and b'unknown flag: --bad-flag' in invoke('enable','--bad-flag').stdout

def test_file_selection_prefix_missing_and_argument_validation(tmp_path):
    p=setup_file(tmp_path,'# profile.on p\n# end\n')
    r=run_file(p,'status')
    assert r.returncode==0 and r.stdout.startswith(f'[ℹ] Using hosts file: {p}\n\n'.encode())
    quiet=run_file(p,'status','--quiet')
    assert quiet.returncode==0 and not quiet.stdout.startswith(f'[ℹ] Using hosts file: {p}'.encode())
    q=tmp_path/'missing'
    r=run_file(q,'status')
    assert r.returncode!=0 and r.stdout==f'[ℹ] Using hosts file: {q}\n\n[✖] error: open {q}: no such file or directory\n'.encode() and r.stderr==b''
    r=run_file(q,'enable')
    assert r.returncode!=0 and b'missing profile name' in r.stdout and b'open ' not in r.stdout

def test_route_parsing_canonicalization_default_and_disabled_state(tmp_path):
    p=setup_file(tmp_path,'''# retained
127.0.0.1\tlocal café
::1 localhost ip6-localhost ip6-loopback
# 2001:0db8:85a3:0:0:8a2e:0370:7335 disabled extra
bad.ip nope
1.2.3.4 name#tail
''')
    rows=records(p,'list')
    assert rows==[
      {'Profile':'default','Status':'on','IP':'127.0.0.1','Host':'local'},
      {'Profile':'default','Status':'on','IP':'::1','Host':'localhost'},
      {'Profile':'default','Status':'off','IP':'2001:db8:85a3::8a2e:370:7335','Host':'disabled'},
      {'Profile':'default','Status':'on','IP':'1.2.3.4','Host':'name'}]
    assert records(p,'status') is None
    assert run_file(p,'status','--out','json').stdout==b'null\n'

def test_profile_markers_routes_dedup_order_and_duplicate_names(tmp_path):
    p=setup_file(tmp_path,'''# profile.on first
1.1.1.1 a b
1.1.1.1 a
2.2.2.2 a
# end
# Profile.on ignored
4.4.4.4 fallback
# profile.off dup
3.3.3.3 old
# END
# profile.on middle
# end
# profile.off dup
3.3.3.3 new other
# end
# profile.off 
# profile.on café
''')
    status=records(p,'status')
    assert [(x['Profile'],x['Status']) for x in status]==[('first','on'),('dup','off'),('middle','on'),('dup','off'),('caf','on')]
    rows=records(p,'list')
    assert [(x['Profile'],x['Host'],x['Status']) for x in rows[:3]]==[
      ('default','fallback','on'),('first','a','on'),('first','b','on')]
    # Last duplicate definition is used at both sequence positions; exact route order is preserved.
    dup=[x for x in rows if x['Profile']=='dup']
    assert len(dup)==4 and {x['Host'] for x in dup}=={'new','other'} and all(x['Status']=='off' for x in dup)
    assert not any(x['Host']=='old' for x in rows)

def test_list_status_filters_columns_and_renderer_shapes(tmp_path):
    p=setup_file(tmp_path,'# profile.off a\n1.1.1.1 x\n# end\n# profile.on b\n2.2.2.2 y\n# end\n')
    assert [x['Profile'] for x in records(p,'list','b','missing','default','a')]==['a','b']
    assert [x['Profile'] for x in records(p,'status','b','missing','a')]==['a','b']
    assert [x['Profile'] for x in records(p,'list','enabled')]==['b']
    assert [x['Profile'] for x in records(p,'list','disabled')]==['a']
    assert records(p,'status','-c','ip,profile')[0]['IP']==''
    r=run_file(p,'list','-q','-c','profile,status','--raw')
    assert r.returncode==0 and r.stdout.startswith(b'PROFILE\tSTATUS ') and r.stdout.endswith(b'\t\n')
    j=run_file(p,'list','-q','-o','json')
    assert j.stdout.startswith(b'[') and j.stdout.endswith(b'\n') and b'"Profile":"a"' in j.stdout
    t=run_file(p,'status','-q','--no-color')
    assert t.stdout.startswith(b'+') and b'\x1b' not in t.stdout
    m=run_file(p,'status','-q','-o','markdown')
    assert m.stdout.startswith(b'| PROFILE | STATUS |') and m.stdout.endswith(b'\n')

def test_empty_renderers_and_raw_json_precedence(tmp_path):
    p=setup_file(tmp_path,'')
    assert run_file(p,'status','--out','json').stdout==b'null\n'
    assert run_file(p,'status','-q','--raw').stdout==b''
    assert run_file(p,'status','-o','json','--raw').stdout==b''
    assert run_file(p,'status','-oq').returncode==0
    p.write_text('# profile.on p\n# end\n')
    r=run_file(p,'status','-oq')
    assert r.returncode==0 and b'PROFILE' in r.stdout and b'Using hosts file' in r.stdout

def test_add_domains_creation_dedup_disabled_arbitrary_values(tmp_path):
    p=setup_file(tmp_path,'')
    r=run_file(p,'add','domains','p','*.a:80','café','--ip','2001:db8::1','-o','json')
    assert r.returncode==0 and "[✔] Domains '*.a:80, café' added.".encode() in r.stdout
    assert records(p,'list')==[{'Profile':'p','Status':'on','IP':'2001:db8::1','Host':'*.a:80'},{'Profile':'p','Status':'on','IP':'2001:db8::1','Host':'café'}]
    run_file(p,'disable','p','-q')
    run_file(p,'add','domains','p','café','new','--ip','2001:db8::1','-q')
    assert [(x['Host'],x['Status']) for x in records(p,'list')]==[('*.a:80','off'),('café','off'),('new','off')]
    assert run_file(p,'add','domains','default','x').stdout.endswith("[✖] error: 'default' profile should not be handled by hostctl\n".encode())

def test_add_replace_import_stdin_expands_all_hosts_and_orders(tmp_path):
    p=setup_file(tmp_path,'# profile.on first\n# end\n# profile.off target\n9.9.9.9 old\n# end\n# profile.on last\n# end\n')
    source=b'1.1.1.1 a b\n# profile.off z\n2.2.2.2 c d\n# end\n'
    r=run_file(p,'add','target','--from','does-not-exist',data=source)
    assert r.returncode==0
    assert [(x['Profile'],x['Host']) for x in records(p,'list')]==[('target','old'),('target','a'),('target','b'),('target','c'),('target','d')]
    r=run_file(p,'replace','target','--from','http:///ignore',data=b'3.3.3.3 x y\n')
    assert r.returncode==0
    assert [x['Profile'] for x in records(p,'status')]==['first','last','target']
    assert [(x['IP'],x['Host'],x['Status']) for x in records(p,'list') if x['Profile']=='target']==[('3.3.3.3','x','on'),('3.3.3.3','y','on')]

def test_empty_stdin_add_replace_and_one_profile_validation(tmp_path):
    p=setup_file(tmp_path,'# profile.off p\n1.1.1.1 old\n# end\n')
    r=run_file(p,'add','empty',data=b'')
    assert r.returncode==0 and ('empty' in [x['Profile'] for x in records(p,'status')])
    r=run_file(p,'replace','p',data=b'')
    assert r.returncode==0 and [(x['Profile'],x['Status']) for x in records(p,'status')]==[('p','on'),('empty','on')]
    before=p.read_bytes()
    r=run_file(p,'add','p','q',data=b'')
    assert r.returncode!=0 and b'specify only one profile' in r.stdout and p.read_bytes()==before

def test_remove_profiles_atomic_all_and_domain_pruning(tmp_path):
    p=setup_file(tmp_path,'# retained\n127.0.0.1 local\n# profile.on a\n1.1.1.1 x\n1.1.1.2 y\n# end\n# profile.off b\n# end\n')
    before=p.read_bytes()
    r=run_file(p,'remove','a','missing')
    assert r.returncode!=0 and b'unknown profile name' in r.stdout and p.read_bytes()==before
    assert run_file(p,'remove','a','--all').returncode!=0
    r=run_file(p,'remove','domains','a','x','-q')
    assert r.returncode==0 and [(x['Host']) for x in records(p,'list') if x['Profile']=='a']==['y']
    r=run_file(p,'remove','domains','a','y')
    assert r.returncode==0 and "[✔] Profile 'a' removed.".encode() in r.stdout
    r=run_file(p,'remove','--all','-o','json')
    assert r.returncode==0 and "Profile(s) '' removed.".encode() in r.stdout
    assert records(p,'status') is None and records(p,'list')==[{'Profile':'default','Status':'on','IP':'127.0.0.1','Host':'local'}]
    assert b'# Content under this line is handled by hostctl.' in p.read_bytes()

def test_enable_disable_toggle_selection_only_idempotence(tmp_path):
    p=setup_file(tmp_path,'# profile.off a\n1.1.1.1 a\n# end\n# profile.on b\n2.2.2.2 b\n# end\n')
    r=run_file(p,'enable','b','a','-q')
    assert r.returncode==0 and [(x['Profile'],x['Status']) for x in records(p,'status')]==[('a','on'),('b','on')]
    before=p.read_bytes(); assert run_file(p,'enable','a','-q').returncode==0
    assert [(x['Profile'],x['Status']) for x in records(p,'status')][0]==('a','on')
    assert run_file(p,'toggle','b','-q').returncode==0
    assert [x['Status'] for x in records(p,'status')]==['on','off']
    r=run_file(p,'disable','--only','a','unknown','-q')
    assert r.returncode==0 and [x['Status'] for x in records(p,'status')]==['off','on']
    before=p.read_bytes(); r=run_file(p,'toggle','a','missing','-q')
    assert r.returncode!=0 and p.read_bytes()==before
    assert run_file(p,'enable','default').returncode!=0

def test_wait_runs_inverse_and_quiet_wait_emits_one_newline(tmp_path):
    p=setup_file(tmp_path,'# profile.off p\n1.1.1.1 x\n# end\n')
    r=run_file(p,'enable','p','--wait','50ms','-q')
    assert r.returncode==0 and r.stdout==b'\n' and r.stderr==b''
    assert records(p,'status')[0]['Status']=='off'
    r=run_file(p,'enable','p','--wait','-1s','-q')
    assert r.returncode==0 and r.stdout==b'' and records(p,'status')[0]['Status']=='on'
    r=run_file(p,'enable','p','--wait','5x','-q')
    assert r.returncode!=0 and b'invalid argument "5x"' in r.stdout

def test_mutations_canonicalize_unmanaged_and_banner(tmp_path):
    p=setup_file(tmp_path,'# keep me\n\n127.0.0.1\tlocal café\n# profile.on p\n1.1.1.1 a b\nstray text\n# end\n# profile.off q\n# end\n')
    r=run_file(p,'toggle','q','-q')
    assert r.returncode==0
    s=p.read_text()
    assert s.startswith('# keep me\n\n127.0.0.1 local\nstray text\n\n##################################################################\n# Content under this line is handled by hostctl. DO NOT EDIT.\n##################################################################\n\n')
    assert s.count('##################################################################')==2 and '1.1.1.1 a\n1.1.1.1 b\n# end' in s
    assert run_file(p,'remove','p','q','-q').returncode==0
    assert p.read_text().endswith('##################################################################\n# Content under this line is handled by hostctl. DO NOT EDIT.\n##################################################################\n')

def test_backup_restore_byte_fidelity_and_errors(tmp_path):
    p=tmp_path/'source'; payload=b'\xff\x00odd\r\n trailing  '
    p.write_bytes(payload)
    dest=tmp_path/'backups'; dest.mkdir()
    r=invoke('backup','--host-file',p,'--path',dest)
    assert r.returncode==0 and '[✔] Backup '.encode() in r.stdout
    name=f'source.{datetime.datetime.now().strftime("%Y%m%d")}'
    backup=dest/name
    assert backup.read_bytes()==payload
    target=tmp_path/'target'; target.write_bytes(b'old')
    r=invoke('restore','--host-file',target,'--from',backup)
    assert r.returncode==0 and target.read_bytes()==payload and '[✔] File '.encode() in r.stdout
    prior=target.read_bytes(); r=invoke('restore','--host-file',target,'--from',tmp_path/'absent')
    assert r.returncode!=0 and target.read_bytes()==prior
    assert invoke('backup','--host-file',p,'--path',tmp_path/'absent').returncode!=0

def test_sync_docker_validation_and_docker_compose_path_precedence(tmp_path):
    p=setup_file(tmp_path,'')
    r=run_file(p,'sync','docker','p','--domain','a-b_1.x','--network','net_1')
    assert r.returncode!=0 and r.stdout=='[✖] error: Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?\n'.encode()
    assert b'Using hosts file' not in r.stdout and r.stderr==b''
    missing=tmp_path/'no-compose.yml'
    r=run_file(p,'sync','docker-compose','p','--compose-file',missing)
    assert r.returncode!=0 and f'open {missing}: no such file or directory'.encode() in r.stdout
    compose=tmp_path/'compose.yml'; compose.write_text('not valid yaml')
    r=run_file(p,'sync','docker-compose','p','--compose-file',compose,'--project-name','a-b_1.x','--prefix')
    assert b'Cannot connect to the Docker daemon' in r.stdout
    assert run_file(p,'sync','docker','default').returncode!=0

def test_help_pages_and_nested_routing():
    for cmd in ['add','backup','disable','enable','list','remove','replace','restore','status','sync','toggle']:
        r=invoke(cmd,'--help')
        assert r.returncode==0 and b'Usage:' in r.stdout and b'Global Flags:' in r.stdout, cmd
        assert invoke('help',cmd).stdout==r.stdout
    a=invoke('add','--help').stdout
    assert b'hostctl add [profiles] [flags]' in a and b'-f, --from' in a and b'-w, --wait' in a and b'  domains     Add content in your hosts file.' in a
    assert invoke('add','domains','--help').returncode==0
    assert invoke('remove','domains','--help').returncode==0
    assert invoke('add','domain','--help').stdout==invoke('add','--help').stdout
    assert invoke('remove','domain','--help').stdout==invoke('remove','--help').stdout
    s=invoke('sync','--help').stdout.decode()
    assert '  docker         Sync your Docker containers IPs with a profile.' in s
    assert '  docker-compose Sync your docker-compose containers IPs with a profile.' in s

def test_completion_commands_have_contract_shape():
    b=invoke('completion','bash'); z=invoke('completion','zsh','ignored','--quiet')
    assert b.returncode==0 and b.stderr==b'' and b.stdout.startswith(b'# bash completion for hostctl')
    assert b.stdout.count(b'\n')>1000 and b'__hostctl_root_command' in b.stdout and b'_hostctl_add_domains' in b.stdout
    assert b'_hostctl_sync_docker-compose' in b.stdout and b'BASH_COMP_DEBUG_FILE' in b.stdout
    x=subprocess.run(['bash','-n'],input=b.stdout,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    assert x.returncode==0
    assert z.returncode==0 and z.stderr==b'' and z.stdout.startswith(b'#compdef hostctl\ncompdef _hostctl hostctl\n')
    assert len(z.stdout.splitlines())==212 and z.stdout.endswith(b'    _hostctl\nfi\n')
