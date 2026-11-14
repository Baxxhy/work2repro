import fcntl
import os
import pty
import select
import shutil
import struct
import subprocess
import termios
import time
from pathlib import Path

import pytest

EXE = Path('/workspace/executable')


def invoke(*args):
    return subprocess.run([str(EXE), *map(str, args)], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=5)


def test_version_aliases_are_exact():
    for args in [('-v',), ('--version',), ('-vh',)]:
        p = invoke(*args)
        assert (p.returncode, p.stdout, p.stderr) == (0, b'0.4.3\n', b'')


def test_help_has_usage_and_argv0_twice():
    p = invoke('--help')
    expected = os.fsencode(str(EXE))
    assert p.returncode == 0 and not p.stderr
    assert p.stdout.startswith(expected + b': A tiny UTF-8 terminal text editor\n')
    assert b'Usage:\n    ' + expected + b' [options] [FILES...]' in p.stdout
    assert p.stdout.endswith(b'\n\n')
    assert b'Ctrl-Q                        : Quit' in p.stdout


@pytest.mark.parametrize('args,needle', [
    (('--version', '--version'), b'more than once'),
    (('-v', '--version'), b'more than once'),
    (('--help', '--help'), b'more than once'),
])
def test_repeated_info_options_fail(args, needle):
    p = invoke(*args)
    assert p.returncode == 1 and not p.stdout
    assert p.stderr.startswith(b'Error:') and needle in p.stderr


def test_unknown_and_attached_option_diagnostics():
    p = invoke('--nonexistent-flag')
    assert p.returncode == 1 and not p.stdout
    assert p.stderr.startswith(b'Error:') and b"Unrecognized option 'nonexistent-flag'" in p.stderr
    assert b'--help' in p.stderr and p.stderr.endswith(b'\n')
    p = invoke('--version=1.0')
    assert (p.returncode, p.stdout, p.stderr) == (1, b'', b"Error: Option 'version' does not take an argument. Please see --help for more details\n")


def test_non_tty_requires_terminal_even_with_file(tmp_path):
    for args in [(), (str(tmp_path / 'missing'),)]:
        p = invoke(*args)
        assert p.returncode == 1 and p.stdout == b''
        assert p.stderr.startswith(b'Error:') and b'Inappropriate ioctl for device' in p.stderr


class Editor:
    def __init__(self, args=(), size=(80, 24), env=None):
        self.master, slave = pty.openpty()
        self.resize(*size)
        e = os.environ.copy()
        e.update({'TERM': 'xterm-256color', 'LC_ALL': 'C.UTF-8'})
        if env: e.update(env)
        self.proc = subprocess.Popen([str(EXE), *map(str, args)], stdin=slave,
                                     stdout=slave, stderr=slave, env=e, close_fds=True)
        os.close(slave)
        self.read(0.15)

    def resize(self, width, height):
        fcntl.ioctl(self.master, termios.TIOCSWINSZ, struct.pack('HHHH', height, width, 0, 0))

    def send(self, data):
        os.write(self.master, data)
        return self.read(0.12)

    def read(self, duration=.1):
        out = bytearray(); end = time.monotonic() + duration
        while time.monotonic() < end:
            r, _, _ = select.select([self.master], [], [], max(0, end-time.monotonic()))
            if not r: break
            try: out.extend(os.read(self.master, 65536))
            except OSError: break
        return bytes(out)

    def stop(self):
        if self.proc.poll() is None:
            self.send(b'\x11')
            try: self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill(); self.proc.wait()
        os.close(self.master)

    def finish(self):
        self.send(b'\x11')
        return self.proc.wait(timeout=2)


@pytest.fixture
def editor_factory():
    opened = []
    def make(*a, **kw):
        ed = Editor(*a, **kw); opened.append(ed); return ed
    yield make
    for ed in opened: ed.stop()


def test_minimum_size_error_is_exact_and_restores_terminal():
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 2, 10, 0, 0))
    p = subprocess.Popen([str(EXE)], stdin=slave, stdout=slave, stderr=slave)
    os.close(slave)
    data = b''
    while True:
        r, _, _ = select.select([master], [], [], 2)
        if not r: break
        try: data += os.read(master, 4096)
        except OSError: break
    assert p.wait(timeout=2) == 1
    assert b'Error: Screen 10x2 is too small. At least 1x3 is necessary in width x height\r\n' in data
    assert b'\x1b[?1049l' in data or b'\x1b[?25h' in data
    os.close(master)


def test_startup_and_clean_quit(editor_factory):
    ed = editor_factory()
    assert b'Kiro editor -- version 0.4.3' in ed.read()
    assert b'Ctrl-? for help' in ed.read()
    assert ed.finish() == 0


def test_insert_unicode_tab_and_save_serialization(editor_factory, tmp_path):
    path = tmp_path / 'wide name-犬.txt'
    ed = editor_factory((path,))
    ed.send('caféこんにちは日本🌍'.encode() + b'\tX\x13')
    ed.send(b'\x11')
    assert ed.proc.wait(timeout=2) == 0
    assert path.read_bytes() == 'caféこんにちは日本🌍\tX\n'.encode()


def test_enter_and_save_add_final_lf(editor_factory, tmp_path):
    path = tmp_path / 'split.txt'; ed = editor_factory((path,))
    ed.send(b'Hello World\rThis is line 2\x13')
    ed.send(b'\x11'); assert ed.proc.wait(timeout=2) == 0
    assert path.read_bytes() == b'Hello World\nThis is line 2\n'


def test_unnamed_save_prompt_assigns_path(editor_factory, tmp_path):
    path = tmp_path / 'new.rs'; ed = editor_factory()
    ed.send(b'abc\x13'); ed.send(os.fsencode(path) + b'\r')
    ed.send(b'\x11'); assert ed.proc.wait(timeout=2) == 0
    assert path.read_bytes() == b'abc\n'


def test_open_prompt_adds_buffer_and_switches(editor_factory, tmp_path):
    path = tmp_path / 'other.txt'; path.write_text('loaded')
    ed = editor_factory(); ed.send(b'\x0f'); ed.send(os.fsencode(path) + b'\r')
    data = ed.read()
    assert b'loaded' in data and b'2/2' in data
    ed.send(b'\x18'); data = ed.read()
    assert b'1/2' in data


def test_search_finds_and_cancel_restores_live_editor(editor_factory, tmp_path):
    path = tmp_path / 'search.txt'; path.write_text('first\ntarget here\nlast\n')
    ed = editor_factory((path,)); ed.send(b'\x07target\r')
    assert b'Found' in ed.read()
    ed.send(b'\x07missing\x07')
    assert b'Canceled' in ed.read()
    assert ed.proc.poll() is None


def test_undo_redo_and_modified_save_point(editor_factory, tmp_path):
    path = tmp_path / 'undo.txt'; ed = editor_factory((path,))
    ed.send(b'hello\x15')
    data = ed.read()
    assert b'hello' not in data or b' (modified)' not in data
    ed.send(b'\x12\x13'); ed.send(b'\x11')
    assert ed.proc.wait(timeout=2) == 0
    assert path.read_bytes() == b'hello\n'


def test_directory_open_fails_with_os_error(tmp_path):
    p = invoke(str(tmp_path))
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr == b'Error: Is a directory (os error 21)\n'


def test_zero_byte_file_status_and_empty_save(editor_factory, tmp_path):
    path = tmp_path / 'empty.txt'; path.write_bytes(b'')
    ed = editor_factory((path,)); data = ed.read()
    assert b'plain 1/0' in data
    ed.send(b'\x13'); ed.send(b'\x11')
    assert ed.proc.wait(timeout=2) == 0 and path.read_bytes() == b''


def test_control_character_is_fatal_without_panic(editor_factory, tmp_path):
    path = tmp_path / 'bad.txt'; path.write_bytes(b'good\x01bad')
    ed = editor_factory((path,)); ed.send(b'')
    data = ed.read(.4)
    assert ed.proc.wait(timeout=2) == 1
    assert b"Error: Invalid character for text is included: '\\u{1}'" in data
    assert b'panicked at' not in data
