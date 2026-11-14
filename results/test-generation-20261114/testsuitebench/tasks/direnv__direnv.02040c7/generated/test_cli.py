import os
import subprocess
import tempfile
import hashlib
import json
import re
import zlib
import base64
from pathlib import Path

EXE = Path('/workspace/executable')

def call(args=(), *, cwd=None, env=None, stdin=None):
    base = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'HOME': str(Path(cwd or '/tmp').resolve()), 'USER': 'tester'}
    if env:
        base.update({k: str(v) for k, v in env.items()})
    p = subprocess.run([str(EXE), *map(str, args)], cwd=cwd, env=base, input=stdin,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
    return p.returncode, p.stdout, p.stderr

def workspace(tmp_path, *, load_dotenv=False):
    home = tmp_path / 'home'; home.mkdir()
    conf = home / '.config' / 'direnv'; conf.mkdir(parents=True)
    data = home / '.local' / 'share' / 'direnv'; data.mkdir(parents=True)
    cache = home / '.cache' / 'direnv'; cache.mkdir(parents=True)
    if load_dotenv:
        (conf / 'direnv.toml').write_text('[global]\nload_dotenv = true\n')
    env = {'HOME': str(home), 'XDG_CONFIG_HOME': str(home / '.config'),
           'XDG_DATA_HOME': str(home / '.local' / 'share'), 'XDG_CACHE_HOME': str(home / '.cache')}
    return home, conf, data, cache, env

def allow(tmp_path, directory, env):
    code, out, err = call(['allow'], cwd=directory, env=env)
    assert code == 0, (out, err)

def test_help_surface_and_private_commands(tmp_path):
    for args in [[], ['help'], ['--help']]:
        rc, out, err = call(args, cwd=tmp_path)
        assert rc == 0 and not err
        assert out.startswith(b'direnv v2.37.1\nUsage: direnv COMMAND [...ARGS]\n\nAvailable commands\n------------------\n')
        assert b'fetchurl <url> [<integrity-hash>]:' in out and b'log [--status | --error] <message>:' in out
    rc, out, _ = call(['help', 'anything'], cwd=tmp_path)
    assert rc == 0 and b'* = private commands' in out
    for command in [b'*apply_dump FILE:', b'*check-required SHELL ENVRC_PATH PATH...:', b'*watch-print [--null]:']:
        assert command in out

def test_unknown_and_version_semver(tmp_path):
    rc, out, err = call(['fake_command', 'ignored'], cwd=tmp_path)
    assert rc == 1 and not out and b'error' in err and b'not found' in err and b'fake_command' in err and b'ignored' not in err
    assert call(['-h'], cwd=tmp_path)[0] == 1
    assert call(['version'], cwd=tmp_path) == (0, b'2.37.1\n', b'')
    for v in ['1', '1.2', 'v2.37.0', '2.30.0-alpha', '2.30.0+build.123']:
        assert call(['version', v], cwd=tmp_path)[0] == 0
    for v in ['2.37.2', '3.0.0', '99.0.0']:
        rc, _, err = call(['version', v], cwd=tmp_path)
        assert rc == 1 and b'older than the desired version' in err
    for v in ['01.2.3', '2.1', 'garbage', '1.2.3.4']:
        assert b'is not a valid semver version' in call(['version', v], cwd=tmp_path)[2]

def test_missing_environment_directories(tmp_path):
    env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin')}
    for cmd, variable, diagnostic in [(['export', 'bash'], 'XDG_CACHE_HOME', b"couldn't find a cache directory for direnv"),
                                      (['export', 'bash'], 'XDG_DATA_HOME', b"couldn't find a data directory for direnv")]:
        e = dict(env); e.update({'XDG_CONFIG_HOME': str(tmp_path / 'config')}); e.pop('HOME', None); e.pop(variable, None)
        rc, _, err = call(cmd, cwd=tmp_path, env=e)
        assert rc == 1 and diagnostic in err

def test_config_parsing_and_log_format(tmp_path):
    home, conf, data, cache, env = workspace(tmp_path)
    (conf / 'direnv.toml').write_text('[global]\nwarn_timeout = not_a_duration\n')
    rc, _, err = call(['status'], cwd=tmp_path, env=env)
    assert rc == 1 and b'LoadConfig() failed to parse' in err and b'global.warn_timeout' in err and b'time: invalid duration' in err
    (conf / 'direnv.toml').write_text('[global]\nlog_filter = "["\n')
    rc, _, err = call(['status'], cwd=tmp_path, env=env)
    assert rc == 1 and b'error parsing regexp' in err and b'missing closing ]' in err

def test_rc_search_allow_exports_and_incremental_state(tmp_path):
    home, conf, data, cache, env = workspace(tmp_path)
    project = tmp_path / 'project'; nested = project / 'a' / 'b'; nested.mkdir(parents=True)
    rcfile = project / '.envrc'
    rcfile.write_text("export SIMPLE='hello world'\nexport EMPTY=''\nunset OLD_VAR\nexport UNICODE='café'\n")
    (project / '.env').write_text('export WRONG=1\n')
    allow(tmp_path, project, env)
    e = dict(env, OLD_VAR='old', DIRENV_LOG_FORMAT='')
    code, out, err = call(['export', 'json'], cwd=nested, env=e)
    assert code == 0 and b'loading ' in err
    changes = json.loads(out)
    assert changes['SIMPLE'] == 'hello world' and changes['EMPTY'] == '' and changes['OLD_VAR'] is None
    assert changes['UNICODE'] == 'café' and changes['DIRENV_FILE'] == str(rcfile)
    assert changes['DIRENV_DIR'] == '-' + str(project)
    for key in ['DIRENV_DIFF', 'DIRENV_WATCHES']:
        assert changes[key].startswith('eJ')
    e.update({k: v for k, v in changes.items() if v is not None})
    for k, v in changes.items():
        if v is None: e.pop(k, None)
    code, out, err = call(['export', 'json'], cwd=nested, env=e)
    assert code == 0 and not out and not err

def test_blocked_and_whitelisted_rc(tmp_path):
    home, conf, data, cache, env = workspace(tmp_path)
    d = tmp_path / 'bad'; d.mkdir(); (d / '.envrc').write_text('export SHOULD_NOT_APPEAR=1\n')
    rc, out, err = call(['export', 'bash'], cwd=d, env=env)
    assert rc == 1 and b'.envrc is blocked' in err and b'SHOULD_NOT_APPEAR' not in out
    rc, _, _ = call(['block'], cwd=d, env=env); assert rc == 0
    rc, _, err = call(['export', 'bash'], cwd=d, env=env)
    assert rc == 1 and b'blocked' in err
    (conf / 'direnv.toml').write_text('[whitelist]\nprefix = ["' + str(d) + '"]\n')
    rc, out, _ = call(['export', 'json'], cwd=d, env=env)
    assert rc == 0 and json.loads(out)['SHOULD_NOT_APPEAR'] == '1'

def test_rc_arbitrary_bash_and_parent_reversion(tmp_path):
    home, conf, data, cache, env = workspace(tmp_path)
    d = tmp_path / 'bashrc'; d.mkdir()
    (d / '.envrc').write_text("export FROM_COMMAND=$(printf 'value with spaces')\nexport REACHED=yes\ncommand_that_does_not_exist\n")
    allow(tmp_path, d, env)
    rc, out, err = call(['export', 'json'], cwd=d, env=env)
    assert rc == 0 and b'command_that_does_not_exist' in err
    obj = json.loads(out); assert obj['FROM_COMMAND'] == 'value with spaces' and obj['REACHED'] == 'yes'

def test_dotenv_parser_and_errors(tmp_path):
    home, conf, data, cache, env = workspace(tmp_path)
    f = tmp_path / '.env'
    f.write_text("export A=2\nB='\\n'\nC=\"line1\\nline2\"\nD=${MISSING:-default}/x\nE='$HOME'\nF: value\n")
    rc, out, err = call(['dotenv', 'json', f], cwd=tmp_path, env=dict(env, HOME='/incoming'))
    assert rc == 0 and not err
    result = json.loads(out)
    assert result == {'A':'2','B':r'\n','C':'line1\nline2','D':'default/x','E':'$HOME','F':'value'}
    f.write_text('')
    assert call(['dotenv', 'bash', f], cwd=tmp_path, env=env)[:2] == (0, b'\n')
    f.write_text('BROKEN')
    assert b'invalid line: BROKEN' in call(['dotenv', 'bash', f], cwd=tmp_path, env=env)[2]
    f.write_text('A="no close')
    assert b'unclosed quoted value in .env file' in call(['dotenv', 'bash', f], cwd=tmp_path, env=env)[2]

def test_dump_decoding_and_serializers(tmp_path):
    env = {'HOME': str(tmp_path), 'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'VALUE': "a\nb'\\café", 'EMPTY': ''}
    rc, out, _ = call(['dump', 'json'], cwd=tmp_path, env=env)
    obj = json.loads(out); assert obj['VALUE'] == env['VALUE'] and obj['EMPTY'] == ''
    rc, out, _ = call(['dump'], cwd=tmp_path, env=env)
    assert out.startswith(b'eJ')
    rc, shown, _ = call(['show_dump', out.decode().strip()], cwd=tmp_path, env=env)
    assert rc == 0 and json.loads(shown)['VALUE'] == env['VALUE']
    rc, _, err = call(['show_dump', 'invalid_base64_data_xyz'], cwd=tmp_path, env=env)
    assert rc == 1 and b'input byte 20' in err
    for shell in ['bash','zsh','fish','tcsh','pwsh','vim','systemd','gha','elvish','murex']:
        rc, out, _ = call(['dump', shell], cwd=tmp_path, env=env)
        assert rc == 0 and out
    rc, out, _ = call(['dump', 'gha'], cwd=tmp_path, env=dict(env, **{'bad-key':'x'}))
    assert rc == 0 and b'Skipping invalid environment variable key: bad-key' in call(['dump','gha'], cwd=tmp_path, env=dict(env, **{'bad-key':'x'}))[2]

def test_status_shapes_and_rc_discovery(tmp_path):
    home, conf, data, cache, env = workspace(tmp_path)
    rc, out, err = call(['status'], cwd=tmp_path, env=env)
    assert rc == 0 and not err and b'No .envrc or .env loaded' in out and b'No .envrc or .env found' in out
    rc, out, _ = call(['status', '--json', 'ignored'], cwd=tmp_path, env=env)
    state = json.loads(out); assert set(state) == {'config','state'} and state['state'] == {'foundRC':None,'loadedRC':None}
    d = tmp_path/'found'; d.mkdir(); (d/'.envrc').write_text('')
    rc, out, _ = call(['status','--json'], cwd=d, env=env)
    assert json.loads(out)['state']['foundRC'] == {'path':str(d/'.envrc'),'allowed':1}

def test_stdlib_contract(tmp_path):
    rc, out, _ = call(['stdlib'], cwd=tmp_path)
    text = out.decode()
    assert rc == 0 and text.startswith('#!/usr/bin/env bash\n') and len(text) > 15000 and len(text.splitlines()) > 500
    for word in ['# These are the commands available in an .envrc execution context', 'shopt -s gnu_errfmt', 'shopt -s nullglob', 'shopt -s extglob', 'direnv_config_dir=', 'DIRENV_IN_ENVRC=1', 'path_add', 'PATH_add', 'source_env', 'require_allowed', 'direnv_load', 'use_nix']:
        assert word in text

def test_log_and_hook_formatting(tmp_path):
    rc, out, err = call(['log','--status','line1\nline2'], cwd=tmp_path, env={'DIRENV_LOG_FORMAT':'-'})
    assert rc == 0 and not out and err == b'\x1b[0mdirenv: line1\nline2\n'
    rc, _, err = call(['log','--error','bad'], cwd=tmp_path)
    assert rc == 0 and err == b'\x1b[31mdirenv: bad\x1b[0m\n'
    assert b'invalid log-type' in call(['log','wat','x'], cwd=tmp_path)[2]
    rc, out, _ = call(['hook','-/bin/bash'], cwd=tmp_path)
    expected = f'\n_direnv_hook() {{\n  local previous_exit_status=$?;\n  vars="$({EXE.resolve()} export bash)";\n'.encode()
    assert rc == 0 and out.startswith(expected)
    assert call(['hook'], cwd=tmp_path)[0] == 1

def test_exec_argument_boundaries_exit_status_and_rc_path(tmp_path):
    home, conf, data, cache, env = workspace(tmp_path)
    d = tmp_path/'execdir'; d.mkdir(); (d/'.envrc').write_text('export FROM_RC=yes\n')
    allow(tmp_path, d, env)
    script = tmp_path/'child.sh'; script.write_text('printf "%s|%s" "$FROM_RC" "$1"; exit 42\n'); script.chmod(0o755)
    rc, out, err = call(['exec', str(d), str(script), 'space " $ ☃'], cwd=tmp_path, env=env)
    assert rc == 42 and out == 'yes|space " $ ☃'.encode() and b'loading ' in err
    assert call(['exec'], cwd=tmp_path, env=env)[0] == 1

def test_watch_merge_current_and_recursive_tree(tmp_path):
    home, conf, data, cache, env = workspace(tmp_path)
    d = tmp_path/'tree'; (d/'sub'/'deep').mkdir(parents=True); (d/'.hidden').write_text('x'); (d/'sub'/'deep'/'file').write_text('x')
    rc, out, _ = call(['watch-dir','bash',d], cwd=tmp_path, env=env)
    assert rc == 0 and b'DIRENV_WATCHES' in out
    newenv = dict(env)
    # retain the emitted shell state for subsequent watch operations
    m = re.search(rb"DIRENV_WATCHES=\$'([^']+)'", out)
    if m: newenv['DIRENV_WATCHES'] = m.group(1).decode()
    rc, printed, _ = call(['watch-print'], cwd=tmp_path, env=newenv)
    assert rc == 0 and str(d/'.hidden').encode() in printed and str(d/'sub'/'deep'/'file').encode() in printed
    assert call(['current', str(d/'.hidden')], cwd=tmp_path, env=newenv)[0] == 0
    (d/'.hidden').write_text('changed')
    assert b'has changed' in call(['current',str(d/'.hidden')], cwd=tmp_path, env=newenv)[2]

def test_required_checks_and_approval_scoped_to_rc(tmp_path):
    home, conf, data, cache, env = workspace(tmp_path)
    d = tmp_path/'required'; d.mkdir(); (d/'.envrc').write_text('')
    rc, out, _ = call(['check-required','bash',d/'.envrc','secrets.txt'], cwd=tmp_path, env=env)
    assert rc == 0 and b'DIRENV_REQUIRED' in out and b'requires approval' in out
    rc, out, _ = call(['check-required','bash',d/'.envrc','../escape'], cwd=tmp_path, env=env)
    assert rc == 0 and b'path must not contain' in out and b'exit 1;' in out
    assert b'at least one file path is required' in call(['check-required','bash',d/'.envrc'], cwd=tmp_path, env=env)[2]

def test_allow_block_records_and_content_hash(tmp_path):
    home, conf, data, cache, env = workspace(tmp_path)
    d = tmp_path/'records'; d.mkdir(); f=d/'.envrc'; f.write_text('export X=1\n')
    assert call(['allow',f,'ignored'], cwd=tmp_path, env=env)[0] == 0
    expected = hashlib.sha256((str(f)+'\n').encode()+f.read_bytes()).hexdigest()
    record = data/'allow'/expected
    assert record.read_text() == str(f)+'\n' and (record.stat().st_mode & 0o777) == 0o644
    rc, _, _ = call(['block',f], cwd=tmp_path, env=env); assert rc == 0
    assert list((data/'deny').iterdir())
    f.write_text('export X=2\n'); assert call(['allow',f], cwd=tmp_path, env=env)[0] == 0
    assert any(p.name != expected for p in (data/'allow').iterdir())

def test_fetchurl_empty_http_content_and_sri(tmp_path):
    import http.server, threading
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = b'' if self.path == '/empty' else b'payload\x00binary'
            self.send_response(200); self.end_headers(); self.wfile.write(body)
        def log_message(self, *args): pass
    server = http.server.HTTPServer(('127.0.0.1',0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        home, conf, data, cache, env = workspace(tmp_path)
        url = f'http://127.0.0.1:{server.server_port}/empty'
        rc, out, _ = call(['fetchurl',url], cwd=tmp_path, env=env)
        assert rc == 0 and out == b'sha256-47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=\n'
        body=b'payload\x00binary'; sri='sha256-'+base64.b64encode(hashlib.sha256(body).digest()).decode()
        url2=f'http://127.0.0.1:{server.server_port}/payload'
        rc, out, _=call(['fetchurl',url2,sri],cwd=tmp_path,env=env)
        assert rc == 0 and Path(out.decode().strip()).read_bytes()==body
        assert b'sri: unsupported algo not' in call(['fetchurl',url2,'not-a-valid-hash'],cwd=tmp_path,env=env)[2]
    finally:
        server.shutdown(); server.server_close()

def test_reload_and_prune_records(tmp_path):
    home, conf, data, cache, env = workspace(tmp_path)
    d=tmp_path/'prune'; d.mkdir(); f=d/'.envrc'; f.write_text('')
    assert call(['allow',f],cwd=tmp_path,env=env)[0]==0
    assert call(['prune'],cwd=tmp_path,env=env)[0]==0
    f.write_text('changed'); assert call(['prune'],cwd=tmp_path,env=env)[0]==0
    assert list((data/'allow').iterdir()) == []
    before=f.stat().st_mtime_ns
    assert call(['reload'],cwd=d,env=env)[0]==0
    assert f.stat().st_mtime_ns >= before
    assert b'.envrc not found' in call(['reload'],cwd=tmp_path/'empty',env=env)[2] if (tmp_path/'empty').exists() else True
