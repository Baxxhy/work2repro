import os
import pexpect
import re
import shutil
from pathlib import Path

EXE = '/workspace/executable'


def launch(args=(), *, cwd=None, env=None, size=(24, 80), timeout=4):
    child = pexpect.spawn(EXE, list(args), cwd=str(cwd) if cwd else None,
                          env=env or os.environ.copy(), encoding='utf-8', timeout=timeout)
    child.setwinsize(*size)
    return child


def close_with_escape(child):
    child.send('\x1b')
    child.expect(pexpect.EOF)
    return child.before


def test_finish_normal_flattens_editor_line_separators(tmp_path):
    child = launch(['--no-isolation', '--default', '  a\n\tb  \n', '--out-file', str(tmp_path/'out')], cwd=tmp_path)
    transcript = close_with_escape(child)
    assert (tmp_path/'out').read_bytes() == b'  a \tb  '
    assert '  a \tb  ' in transcript


def test_finish_raw_preserves_internal_lines(tmp_path):
    child = launch(['-r', '--no-isolation', '-d', 'a\nβ\n', '-o', str(tmp_path/'out')], cwd=tmp_path)
    close_with_escape(child)
    assert (tmp_path/'out').read_bytes() == 'a\nβ'.encode()


def test_empty_output_file_is_created(tmp_path):
    target = tmp_path/'empty'
    child = launch(['--no-isolation', '-o', str(target)], cwd=tmp_path)
    close_with_escape(child)
    assert target.exists() and target.read_bytes() == b''


def test_in_file_is_not_modified_by_output(tmp_path):
    source, target = tmp_path/'source', tmp_path/'target'
    source.write_bytes(b'original\n')
    target.write_bytes(b'old contents')
    child = launch(['--no-isolation', '--in-file', str(source), '--out-file', str(target)], cwd=tmp_path)
    close_with_escape(child)
    assert source.read_bytes() == b'original\n'
    assert target.read_bytes() == b'original'


def test_created_config_and_empty_existing_config(tmp_path):
    cfg = tmp_path/'xdg'/'pipr'/'pipr.toml'
    env = dict(os.environ, XDG_CONFIG_HOME=str(tmp_path/'xdg'), HOME=str(tmp_path/'home'))
    child = launch(['--no-isolation'], cwd=tmp_path, env=env)
    close_with_escape(child)
    data = cfg.read_bytes()
    assert data.startswith(b'\n#  ____') and data.endswith(b'less"\n')
    assert not data.endswith(b'less"\n\n')
    cfg.write_bytes(b'')
    child = launch(['--no-isolation'], cwd=tmp_path, env=env)
    screen = close_with_escape(child)
    assert 'Command [Autoeval]' not in screen


def test_empty_xdg_config_home_uses_relative_config(tmp_path):
    env = dict(os.environ, XDG_CONFIG_HOME='', HOME=str(tmp_path/'home'))
    child = launch(['--no-isolation'], cwd=tmp_path, env=env)
    close_with_escape(child)
    assert (tmp_path/'pipr'/'pipr.toml').exists()
    assert not (tmp_path/'home'/'.config'/'pipr'/'pipr.toml').exists()


def test_editor_printable_and_ctrl_d_ctrl_l_are_literal(tmp_path):
    child = launch(['--no-isolation', '-o', str(tmp_path/'out')], cwd=tmp_path)
    child.send('a\x04\x0c')
    close_with_escape(child)
    assert (tmp_path/'out').read_bytes() == b'adl'


def test_ctrl_u_clears_buffer_and_output(tmp_path):
    env = dict(os.environ, XDG_CONFIG_HOME=str(tmp_path/'cfg'))
    child = launch(['--no-isolation', '-d', 'hello world', '-o', str(tmp_path/'out')], cwd=tmp_path, env=env)
    child.send('\x15')
    close_with_escape(child)
    assert (tmp_path/'out').read_bytes() == b''


def test_tui_starts_with_expected_panes():
    child = launch(['--no-isolation'])
    child.expect('Command [Autoeval]')
    child.expect('Output')
    child.expect('Help: F1')
    close_with_escape(child)


def test_config_and_help_options_do_not_need_a_tty():
    p = __import__('subprocess').run([EXE, '--help'], capture_output=True)
    assert p.returncode == 0 and p.stdout.startswith(b'Usage:') and p.stderr == b''
