import os, pathlib, subprocess, tempfile
import pytest

EXE = '/workspace/executable'
ASSETS = pathlib.Path('/workspace/assets')

@pytest.fixture
def envbox(tmp_path):
    bindir=tmp_path/'bin'; bindir.mkdir()
    log=tmp_path/'calls'
    for name in ('i3','i3-msg','swaymsg'):
        p=bindir/name
        p.write_text('#!/bin/sh\nprintf "%s\\n" "$0 $*" >> "$CALLLOG"\ncase "'+name+'" in i3) exit "${I3_EXIT:-0}";; *) exit "${RELOAD_EXIT:-0}";; esac\n')
        p.chmod(0o755)
    return {'PATH':str(bindir)+':'+os.environ.get('PATH',''),'CALLLOG':str(log),'HOME':str(tmp_path)}

def run(args, envbox, cwd=None):
    e=os.environ.copy(); e.update(envbox)
    return subprocess.run([EXE,*map(str,args)],cwd=cwd,env=e,stdout=subprocess.PIPE,stderr=subprocess.PIPE)

def config(tmp_path, text='client.focused #111111 #222222 #333333 #444444\n'):
    p=tmp_path/'config'; p.write_text(text); return p

def test_exact_help_version_list(envbox):
    h=run(['--help'],envbox); assert h.returncode==0 and h.stderr==b'' and h.stdout.decode().startswith('i3-style 1.0\nMake your i3 config a bit more stylish\n')
    v=run(['--version'],envbox); assert (v.returncode,v.stdout,v.stderr)==(0,b'i3-style 1.0\n',b'')
    l=run(['--list-all'],envbox); assert l.returncode==0 and l.stderr==b'' and l.stdout.decode().startswith('\nAvailable themes:\n\n  slate') and '  mate               - Theme for blending i3 into MATE\n' in l.stdout.decode()

def test_early_precedence_and_missing_theme(envbox):
    assert run(['--version','--help','--bad'],envbox).stdout==b'i3-style 1.0\n'
    assert run(['--help','--version'],envbox).stdout.decode().startswith('i3-style 1.0\nMake')
    assert run(['--list-all','--','--bad'],envbox).returncode==0
    for args in ([],['-r'],['-s'],['-o','x'],['-c','x']):
        r=run(args,envbox); assert r.returncode==1 and r.stderr==b'' and b'Select a theme as the first argument.' in r.stdout

def test_parser_failures(envbox):
    for args, msg in [(['--config'],'--config <file>'),(['-o'],'--output <file>'),(['-c','x','--config','y'],'--config <file>'),(['-t','a','-t','b'],'--to-theme <file>'),(['--wat'],'Found argument')]:
        r=run(args,envbox); assert r.returncode==1 and not r.stdout and b'error:' in r.stderr and b'USAGE:' in r.stderr and b'For more information try --help' in r.stderr
        assert msg.encode() in r.stderr

def test_config_discovery_and_validation_order(tmp_path,envbox):
    r=run(['nonesuch'],envbox); assert r.returncode==1 and b'Could not find i3 config' in r.stderr
    p=tmp_path/'.config/i3/config'; p.parent.mkdir(parents=True); p.write_text('')
    e=dict(envbox,HOME=str(tmp_path)); r=run(['--to-theme'],e); assert r.returncode==0 and b'colors: {}' in r.stdout
    assert pathlib.Path(envbox['CALLLOG']).read_text().splitlines()[-1].endswith(' -C -c '+str(p))

def test_exact_asset_transformations(envbox):
    r=run(['--config',ASSETS/'minimal-config.input','solarized'],envbox)
    assert r.returncode==0 and r.stdout== (ASSETS/'minimal-config-solarized.expected').read_bytes() and not r.stderr
    r=run(['--config',ASSETS/'minimal-config.input','alphare'],envbox)
    assert r.stdout==(ASSETS/'minimal-config-alphare.expected').read_bytes()
    r=run(['--config',ASSETS/'default-config.input','purple'],envbox)
    assert r.stdout==(ASSETS/'default-config-purple.expected').read_bytes()

def test_custom_theme_path_and_preservation(tmp_path,envbox):
    c=ASSETS/'minimal-config.input'
    theme=ASSETS/'custom-test-theme.yaml'
    r=run(['-c',c,str(theme)],envbox)
    assert r.returncode==0 and r.stdout==(ASSETS/'minimal-config-testtheme.expected').read_bytes()

def test_output_save_reload_and_no_parent_creation(tmp_path,envbox):
    c=config(tmp_path); out=tmp_path/'folder with space'/'result'; out.parent.mkdir()
    r=run(['-c',c,'-o',out,'-r','solarized'],envbox)
    assert r.returncode==0 and out.read_bytes() and b'saving config at' in r.stderr
    log=pathlib.Path(envbox['CALLLOG']).read_text(); assert 'reload' in log
    bad=run(['-c',c,'-o',tmp_path/'missing'/'x','solarized'],envbox); assert bad.returncode!=0 and b'saving config at' in bad.stderr

def test_extraction_exact_minimal_and_colorless(tmp_path,envbox):
    c=ASSETS/'minimal-config.input'; r=run(['-c',c,'-t'],envbox)
    assert r.returncode==0 and r.stdout.decode().startswith('---\nmeta:\n  description: AUTOMATICALLY GENERATED THEME\ncolors:\n  crimson: "#DC322F"')
    empty=config(tmp_path,'# just comment\n')
    r=run(['-t',empty],envbox); assert r.stdout==b'---\nmeta:\n  description: AUTOMATICALLY GENERATED THEME\ncolors: {}\nwindow_colors: {}\nbar_colors: {}\n'

def test_line_handling_and_insertion(tmp_path,envbox):
    c=config(tmp_path,'# bar {\nbar {\n  bindsym x y\n}\n')
    r=run(['-c',c,'slate'],envbox)
    assert r.returncode==0 and b'# bar {\n' in r.stdout and b'  bindsym x y\n' in r.stdout and b'  colors {\n' in r.stdout

def test_explicit_theme_file_spaces_unicode_and_large_config(tmp_path,envbox):
    c=tmp_path/'配置 file'; c.write_text(('set $x café\n' * 10000)+'client.focused #111111 #222222 #333333 #444444')
    t=tmp_path/'thème custom.yaml'; t.write_text('window_colors:\n  focused:\n    border: "#ABC"\n')
    r=run(['-c',c,str(t)],envbox)
    assert r.returncode==0 and 'set $x café\n'.encode() in r.stdout and r.stdout.endswith(b'\n')

def test_validation_failure_suppresses_output(tmp_path,envbox):
    c=config(tmp_path); out=tmp_path/'out'
    e=dict(envbox,I3_EXIT='2'); r=run(['-c',c,'-o',out,'solarized'],e)
    assert r.returncode==1 and b'Could not validate config.' in r.stderr and not out.exists()

def test_theme_loading_after_validation_and_missing_theme(tmp_path,envbox):
    c=config(tmp_path)
    r=run(['-c',c,'NoSuchTheme'],envbox)
    assert r.returncode==1 and b'Could not open theme: NoSuchTheme' in r.stderr
    assert len(pathlib.Path(envbox['CALLLOG']).read_text().splitlines())==1
    emptyhome=dict(envbox,HOME=str(tmp_path/'empty-home'))
    r=run(['-c',tmp_path/'absent',''],emptyhome)
    assert r.returncode!=0 and b'Could not find i3 config' not in r.stderr

def test_window_directives_and_workspace_fourth_component(tmp_path,envbox):
    c=config(tmp_path,'client.focused #111111 #222222 #333333\nbar {\n colors {\n  focused_workspace #111111 #222222 #333333\n }\n}\n')
    r=run(['-c',c,'solarized'],envbox)
    assert r.returncode==0
    assert b'client.focused #859900 #859900 #fdf6e3 ' in r.stdout
    assert b'focused_workspace #fdf6e3 #859900 #fdf6e3 #333333\n' in r.stdout
    assert r.stdout.count(b'client.focused ')==1

def test_extraction_ignores_active_workspace_and_keeps_empty_maps(tmp_path,envbox):
    c=config(tmp_path,'bar {\n colors {\n  active_workspace #010203 #040506 #070809\n  separator #010203\n }\n}\nclient.focused #AABBCC #DDEEFF #112233\n')
    r=run(['-t',c],envbox)
    assert r.returncode==0 and b'separator:' in r.stdout
    assert b'active_workspace:' not in r.stdout and b'focused:' in r.stdout

def test_reload_selects_wayland_and_nonzero_started_reload_succeeds(tmp_path,envbox):
    c=config(tmp_path,'')
    e=dict(envbox,WAYLAND_DISPLAY='wayland-1',RELOAD_EXIT='7')
    r=run(['-c',c,'-r','solarized'],e)
    assert r.returncode==0 and not r.stderr
    assert pathlib.Path(envbox['CALLLOG']).read_text().splitlines()[-1].endswith('swaymsg reload')
