import os, pathlib, subprocess, tempfile
import pytest

EVAL = pathlib.Path(__file__).resolve().parent
EXE = pathlib.Path('/workspace/executable')
REF = EVAL / 'reference' / 'resources'


def run(*args, env=None, cwd=None):
    e = os.environ.copy()
    e.update({'BR_INSTALL': 'no', 'BROOT_CONFIG_DIR': str(EVAL / 'unused-config')})
    if env: e.update(env)
    return subprocess.run([str(EXE), *map(str,args)], cwd=cwd, env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)


def test_version_exact():
    p=run('--version')
    assert (p.returncode,p.stdout,p.stderr)==(0,b'broot 1.54.0\n',b'')

@pytest.mark.parametrize('shell,file', [('bash','shell-function-bash.txt'),('zsh','shell-function-zsh.txt'),('fish','shell-function-fish.txt'),('nushell','shell-function-nushell.txt'),('powershell','shell-function-powershell.txt')], ids=['bash','zsh','fish','nushell','powershell'])
def test_print_shell_exact(shell,file):
    p=run('--print-shell-function',shell,'--version')
    assert p.returncode==0 and p.stderr==b''
    assert p.stdout==b'broot 1.54.0\n'+(REF/file).read_bytes()

@pytest.mark.parametrize('name', ['Bash','unknown'], ids=['case-sensitive','unknown'])
def test_bad_shell(name):
    p=run('--print-shell-function',name)
    assert p.returncode!=0 and p.stdout==b'' and p.stderr==f'Unknown shell: {name}\n'.encode()


def test_help_exact_captured():
    p=run('--help')
    assert p.returncode==0 and p.stderr==b''
    assert p.stdout==(REF/'cli-help.txt').read_bytes()

@pytest.mark.parametrize('arg', ['--max-depth=65536','--max-depth=4294967296'], ids=['depth-over-limit','depth-overflow'])
def test_max_depth_upper_bound(arg):
    p=run(arg,'--version')
    assert p.returncode==2 and b'is not in 0..=65535' in p.stderr and p.stdout==b''

@pytest.mark.parametrize('args,fragment', [(['--color','invalid'],b"[possible values: auto, yes, no]"),(['--height','abc'],b'invalid digit found in string'),(['--max-depth','xyz'],b'invalid digit found in string'),(['--set-install-state','invalid_value'],b"similar value exists: 'installed'")], ids=['color-enum','height-integer','depth-integer','install-state-enum'])
def test_invalid_values(args,fragment):
    p=run(*args)
    assert p.returncode==2 and fragment in p.stderr and p.stdout==b''


def test_unknown_option_exact_suggestion():
    p=run('--not-real')
    assert p.returncode==2 and p.stdout==b''
    assert p.stderr==b"error: unexpected argument '--not-real' found\n\n  tip: a similar argument exists: '--no-tree'\n\nUsage: executable --no-tree [ROOT]\n"


def test_second_root():
    p=run('/tmp','/var')
    assert p.returncode==2 and p.stdout==b''
    assert b"unexpected argument '/var' found" in p.stderr and b'Usage: executable [OPTIONS] [ROOT]' in p.stderr

@pytest.mark.parametrize('flags,indicator', [(['--hidden'],'h:y'),(['--hidden','--no-hidden'],'h:y'),(['--no-hidden'],'h:n'),(['--git-ignored','--no-git-ignored'],'gi:n')], ids=['hidden-on','positive-wins','hidden-off','ignored-positive-wins'])
def test_feature_flags_reach_version(flags,indicator):
    p=run(*flags,'--version')
    assert p.returncode==0 and p.stdout==b'broot 1.54.0\n' and p.stderr==b''


def test_conf_unknown_extension_rejected_verbatim(tmp_path):
    f=tmp_path/'x.conf'; f.write_text('{}')
    p=run('--conf',f)
    assert p.returncode==1 and p.stdout==b''
    assert p.stderr==f'Bad configuration: unexpected file extension in "{f}"\n'.encode()


def test_conf_extension_relative_path(tmp_path):
    (tmp_path/'x.conf').write_text('not config')
    p=run('--conf','x.conf',cwd=tmp_path)
    assert p.returncode==1 and p.stderr==b'Bad configuration: unexpected file extension in "x.conf"\n'


def test_conf_malformed_hjson_ordinary_launch(tmp_path):
    f=tmp_path/'broken.hjson'; f.write_text('{ default_flags: [')
    p=run('--conf',f)
    assert p.returncode!=0 and b'Bad configuration file' in p.stderr and b'unable to parse Hjson' in p.stderr


def test_export_default_config_payload(tmp_path):
    dest=tmp_path/'new'/'nested'
    p=run('--write-default-conf',dest)
    assert p.returncode==0 and p.stdout==b'' and p.stderr==b''
    expected=REF/'default-conf'
    for f in expected.rglob('*'):
        if f.is_file():
            out=dest/f.relative_to(expected)
            assert out.read_bytes()==f.read_bytes()
            mode=out.stat().st_mode
            assert mode & 0o400 and not mode & 0o002


def test_export_preserves_custom_existing_file(tmp_path):
    dest=tmp_path/'conf'; dest.mkdir(); (dest/'conf.hjson').write_text('custom')
    p=run('--write-default-conf',dest)
    assert p.returncode==0 and (dest/'conf.hjson').read_text()=='custom'
    assert (dest/'verbs.hjson').exists()


def test_export_regular_file_fails(tmp_path):
    f=tmp_path/'file'; f.write_text('x')
    p=run('--write-default-conf',f)
    assert p.returncode!=0 and b"isn't a directory" in p.stderr


@pytest.mark.parametrize('state,marker,body', [('refused','refused',b'\nThis file tells broot you refused the installation of the companion shell function.\nIf you want to install it run\n    broot -- install\n'),('installed','installed-v4',b"\nThis file tells broot the installation of the br function was done.\nIf there's a problem and you want to install it again run\n    broot -- install\n"),('undefined',None,None)], ids=['refused','installed','undefined'])
def test_install_state_writes_exact_marker(tmp_path,state,marker,body):
    p=run('--set-install-state',state,env={'BROOT_CONFIG_DIR':str(tmp_path)})
    assert p.returncode==0 and p.stderr==b''
    launcher=tmp_path/'launcher'
    if marker:
        assert (launcher/marker).read_bytes()==body
    else:
        assert list(launcher.iterdir())==[]
