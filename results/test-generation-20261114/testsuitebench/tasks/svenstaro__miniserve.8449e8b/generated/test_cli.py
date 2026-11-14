import os
import re
import subprocess
from pathlib import Path

BIN = Path('/workspace/executable')

def run(*args, env=None, cwd=None):
    e = os.environ.copy()
    for k in list(e):
        if k.startswith('MINISERVE_') or k.startswith('MINISERVER_'):
            e.pop(k)
    if env: e.update(env)
    return subprocess.run([str(BIN), *map(str,args)], cwd=cwd, env=e, capture_output=True, timeout=8)

def test_version_and_help():
    p=run('--version'); assert p.returncode == 0 and not p.stderr
    assert re.fullmatch(rb'minis serve.*', p.stdout) is None
    assert re.fullmatch(rb'miniserve \d+\.\d+\.\d+[^\n]*\n', p.stdout)
    for opt in ('--help','-h'):
        p=run(opt); assert p.returncode == 0 and not p.stderr and b'Usage: executable [OPTIONS] [PATH]' in p.stdout
        assert b'\x1b[' not in p.stdout

def test_no_path_and_bad_paths():
    p=run(); assert p.returncode == 1 and p.stdout == b'minis erve v0.32.0\n'.replace(b' ',b'')
    assert b'no explicit serve path was set' in p.stderr and b'no interactive terminal was attached' in p.stderr
    p=run('/definitely/not/a/real/path'); assert p.returncode == 1 and not p.stdout
    assert b'Error' in p.stderr and b'Failed to resolve path to be served' in p.stderr

def test_parse_errors():
    for args, pieces in [
        (('--definitely-invalid',),(b"error: unexpected argument '--definitely-invalid' found",b'Usage:',b"try '--help'")),
        (('--port',),(b"a value is required for '--port <PORT>'",)),
        (('--index',),(b"a value is required for '--index <INDEX>'",)),
        (('--header',),(b"a value is required for '--header <HEADER>'",)),
        (('--port','abc'),(b"invalid value 'abc' for '--port <PORT>'",)),
        (('--port','99999'),(b'invalid value',)),
        (('--chmod','invalid'),(b"invalid value 'invalid' for '--chmod <CHMOD>'",)),
        (('--default-sorting-method','wat'),(b'name',b'size',b'date')),
        (('--default-sorting-order','wat'),(b'asc',b'desc')),
        (('--color-scheme','wat'),(b'squirrel',b'archlinux',b'zenburn',b'monokai')),
        (('--size-display','wat'),(b'human',b'exact')),
        (('--print-completions','wat'),(b'bash',b'elvish',b'fish',b'powershell',b'zsh')),
        (('--media-type','wat'),(b'image',b'audio',b'video')),
        (('--on-duplicate-files','wat'),(b'error',b'overwrite',b'rename')),
        (('--verbose=false',),(b'unexpected argument',)),
        (('--upload-files=',),(b'but none was supplied',)),
        (('--mkdir',),(b'--upload-files',)),
        (('--spa',),(b'--index <INDEX>',)),
        (('--media-type','image','--raw-media-type','x'),(b"error: the argument '--media-type <MEDIA_TYPE>' cannot be used with '--raw-media-type <MEDIA_TYPE_RAW>'",)),
    ]:
        p=run(*args)
        assert p.returncode == 2 and not p.stdout, (args,p.returncode,p.stdout,p.stderr)
        for needle in pieces: assert needle in p.stderr, (args,p.stderr)

def test_shell_data():
    markers={'bash':b'complete','zsh':b'#compdef','fish':b'complete','powershell':b'Register-ArgumentCompleter','elvish':b'edit:completion:arg-completer'}
    for shell,marker in markers.items():
        p=run('--print-completions',shell); assert p.returncode==0 and not p.stderr
        assert len(p.stdout)>100 and b'miniserve' in p.stdout and marker in p.stdout
    p=run('--print-manpage'); assert p.returncode==0 and not p.stderr and len(p.stdout)>500
    for s in (b'.TH miniserve',b'.SH NAME',b'.SH SYNOPSIS'): assert s in p.stdout

def test_environment_configuration(tmp_path):
    (tmp_path/'f').write_text('ok')
    p=run('--version',env={'MINISERVE_PORT':'notanint'})
    # Informational commands take precedence over unrelated environment configuration.
    assert p.returncode == 0
    p=run(env={'MINISERVE_PATH':str(tmp_path),'MINISERVE_PORT':'notanint'})
    assert p.returncode != 0 and not p.stdout
    p=run(env={'MINISERVE_PATH':str(tmp_path),'MINISERVE_ALLOWED_UPLOAD_DIR':''})
    assert p.returncode != 0

def test_tls_validation(tmp_path):
    p=run('--tls-cert','missing-cert.pem','--tls-key','missing-key.pem',tmp_path,cwd=tmp_path)
    assert p.returncode == 1 and not p.stdout
    assert b'Couldn\'t access TLS certificate "missing-cert.pem"' in p.stderr
    assert b'No such file or directory' in p.stderr
    p=run('--tls-cert','missing-cert.pem',tmp_path,cwd=tmp_path)
    assert p.returncode != 0 and not p.stdout
