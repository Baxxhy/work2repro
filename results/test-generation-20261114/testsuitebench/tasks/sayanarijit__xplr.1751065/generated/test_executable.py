import json
import os
import pathlib
import subprocess
import tempfile

EXE = pathlib.Path('/workspace/executable')


def run(args=(), *, cwd=None, data=None, env=None, timeout=5):
    e = os.environ.copy()
    e.pop('XPLR_PIPE_MSG_IN', None)
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd, input=data,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=e, timeout=timeout)


def test_version_and_alias_exact():
    for args in (['--version'], ['-V'], ['-m', '--version'], ['--version', '--']):
        p = run(args)
        assert (p.returncode, p.stdout, p.stderr) == (0, b'xplr 1.1.0\n', b'')


def test_help_alias_and_help_ordering():
    a = run(['--help'])
    b = run(['-h'])
    assert a.returncode == b.returncode == 0
    assert a.stdout == b.stdout and a.stdout.startswith(b'xplr 1.1.0\n')
    assert a.stdout.endswith(b'\n') and a.stderr == b.stderr == b''
    assert run(['--help', '--version']).stdout == a.stdout
    assert b'USAGE:' in a.stdout and b'  -0  --null' in a.stdout


def test_invalid_flags_and_option_terminator():
    p = run(['--invalid-flag'])
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr == b'error: invalid argument: "--invalid-flag", try `-- "--invalid-flag"` or `--help`\n'
    assert run(['-x']).returncode == 1
    assert run(['--version', '--invalid']).returncode == 1
    q = run(['--', '--version'])
    assert q.returncode != 0 and b'USAGE:' not in q.stdout


def test_missing_option_values_and_no_tty():
    for args, phrase in [(['-c'], b'usage: xplr -c PATH'),
                         (['--config'], b'usage: xplr --config PATH'),
                         (['--vroot'], b'usage: xplr --vroot PATH'),
                         (['-M'], b'usage: xplr -M FORMAT')]:
        p = run(args)
        assert p.returncode == 1 and phrase in p.stderr
    p = run(['--on-load'])
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr == b'error: No such device or address (os error 6)\n'


def test_message_normalization_unit_and_data_variants():
    cases = {
        'Quit': '"Quit"', 'ExplorePwd': '"ExplorePwd"',
        'PrintPwdAndQuit': '"PrintPwdAndQuit"',
        'SelectPath: /tmp/a': '{"SelectPath":"/tmp/a"}',
        'FocusByIndex: 999999999': '{"FocusByIndex":999999999}',
        'SwitchMode: custom_mode': '{"SwitchMode":"custom_mode"}',
        'UpdateInputBuffer: {SetCursor: 5}': '{"UpdateInputBuffer":{"SetCursor":5}}',
        'AddNodeSorter: {sorter: BySize, reverse: true}': '{"AddNodeSorter":{"sorter":"BySize","reverse":true}}',
        'Call0: {command: echo}': '{"Call0":{"command":"echo"}}',
        'StartFifo: /tmp/fifo': '{"StartFifo":"/tmp/fifo"}',
        'ToggleFifo: /tmp/fifo': '{"ToggleFifo":"/tmp/fifo"}',
    }
    for source, expected in cases.items():
        p = run(['-M', source])
        assert p.returncode == 0 and p.stdout.decode() == expected and p.stderr == b''


def test_message_json_unicode_escapes_and_compact_output():
    p = run(['-M', 'LogInfo: "snow ☀ and \\\"quote\\\"\\nnext"'])
    assert p.returncode == 0 and p.stderr == b''
    assert json.loads(p.stdout) == {'LogInfo': 'snow ☀ and "quote"\nnext'}
    assert b' ' not in p.stdout
    p = run(['-M', '{"SearchRegex":".*\\\\.txt$"}'])
    assert p.returncode == 0 and json.loads(p.stdout) == {'SearchRegex': r'.*\.txt$'}


def test_placeholder_expansion_and_errors():
    p = run(['-M', 'Call: {command: %s, args: [%s, %s]}', 'bash', '-c', 'echo test'])
    assert p.returncode == 0 and json.loads(p.stdout) == {'Call': {'command': 'bash', 'args': ['-c', 'echo test']}}
    p = run(['-M', 'LogInfo: %q', 'space \'quote\' "double" ☀'])
    assert p.returncode == 0 and json.loads(p.stdout) == {'LogInfo': 'space \'quote\' "double" ☀'}
    assert json.loads(run(['-M', 'LogInfo: test %%']).stdout) == {'LogInfo': 'test %'}
    p = run(['-M', 'LogInfo: %s'])
    assert p.returncode == 1 and b'placeholder missing value' in p.stderr
    p = run(['-M', 'Quit', 'extra'])
    assert p.returncode == 1 and b'too many positional values' in p.stderr


def test_message_type_validation():
    for source, expected in [('', b'expected value at line 1 column 1'),
                             ('explorepwd', b'unknown variant'),
                             ('{Foo: Bar}', b'unknown variant `Foo`'),
                             ('{"FocusPath":123}', b'invalid type: integer `123`, expected a string'),
                             ('FocusByIndex: -1', b'invalid value: integer `-1`, expected usize'),
                             ('Call0: {args: []}', b'missing field `command`'),
                             ('StartFifo', b'unit variant, expected newtype variant')]:
        p = run(['-M', source])
        assert p.returncode == 1 and p.stdout == b'' and expected in p.stderr
    p = run(['-M', '{"FocusPath": "/path/to/file"'])
    assert p.returncode == 1 and p.stderr == b"error: xplr -m: yaml: did not find expected ',' or '}' at line 2 column 1, while parsing a flow mapping\n"


def test_pipe_msg_appends_detects_delimiter_and_reports_empty():
    with tempfile.TemporaryDirectory() as td:
        f = pathlib.Path(td) / 'pipe'
        f.write_bytes(b'\nold\n')
        p = run(['-m', 'Select'], env={'XPLR_PIPE_MSG_IN': str(f)})
        assert p.returncode == 0 and p.stdout == p.stderr == b''
        assert f.read_bytes() == b'\nold\n"Select"\n'
        f.write_bytes(b'')
        p = run(['-m', 'Select'], env={'XPLR_PIPE_MSG_IN': str(f)})
        assert p.returncode == 1 and p.stdout == b''
        assert p.stderr == b'error: failed to detect delimmiter\n'


def test_path_validation_normalization_and_results():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        (root / 'hello world.txt').write_text('x')
        p = run(['--on-load', 'PrintResultAndQuit'], cwd=root)
        assert p.returncode == 0 and p.stdout == str(root / 'hello world.txt').encode() + b'\n'
        p = run(['-c', '/nonexistent/config.lua'], cwd=root)
        assert p.returncode == 1 and p.stdout == b''
        assert p.stderr == b"error: path doesn't exist: /nonexistent/config.lua\n"
        p = run(['/nonexistent/path/does/not/exist'], cwd=root)
        assert p.returncode == 1 and p.stderr == b"error: path doesn't exist: /nonexistent/path/does/not/exist\n"
        p = run(['--on-load', 'PrintPwdAndQuit', str(root / '.' / '..' / root.name)], cwd=root)
        assert p.returncode == 0 and p.stdout == str(root).encode() + b'\n'


def test_stdin_paths_and_nul_read_write_modes():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        (root / 'one α').touch(); (root / 'two').touch()
        p = run(['-', '--on-load', 'PrintAppStateAndQuit'], cwd=root,
                data=b'one Î±\ntwo\n')
        assert p.returncode == 0 and b'one \xce±' in p.stdout and b'two' in p.stdout
        p = run(['--null', '-', '--on-load', 'PrintSelectionAndQuit'], cwd=root,
                data=b'one Î±\0two\0')
        assert p.returncode == 0 and p.stdout.endswith(b'\0')
        assert p.stdout.split(b'\0')[:-1] == [str(root / 'one α').encode(), str(root / 'two').encode()]


def test_app_state_contains_required_sections_and_node_metadata():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        (root / 'sample.tar.gz').write_bytes(b'1234')
        p = run(['--on-load', 'PrintAppStateAndQuit'], cwd=root)
        assert p.returncode == 0 and p.stderr == b''
        out = p.stdout.decode()
        for key in ('bin:', 'version:', 'config:', 'pwd:', 'initial_pwd:', 'vroot:',
                    'directory_buffer:', 'selection:', 'mode:', 'layout:', 'input:',
                    'session_path:', 'explorer_config:', 'logs:', 'history:'):
            assert key in out
        assert 'sample.tar.gz' in out and 'extension: gz' in out
        assert 'size: 4' in out and 'text/plain' not in out


def test_configs_are_validated_and_early_help_ignores_minimal_file():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        cfg = root / 'my config 日本.lua'; cfg.write_text('-- minimal\n')
        assert run(['-c', cfg, '--help']).returncode == 0
        p = run(['-C', cfg, '/nonexistent/extra.lua'])
        assert p.returncode == 1 and b'/nonexistent/extra.lua' in p.stderr
        d = root / 'directory'; d.mkdir()
        assert run(['-c', d]).returncode == 1


def test_print_pwd_result_flag_and_vroot_validation():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td); sub = root / 'sub'; sub.mkdir(); (sub / 'f').touch()
        p = run([str(sub), '--print-pwd-as-result', '--on-load', 'PrintResultAndQuit'], cwd=root)
        assert p.returncode == 0 and p.stdout == str(sub).encode() + b'\n'
        assert run(['--vroot', root / 'missing']).returncode == 1
