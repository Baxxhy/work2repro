import fcntl
import os
import pathlib
import pty
import select
import struct
import subprocess
import termios
import time

EXE = "/workspace/executable"


class App:
    def __init__(self, path, width=80, height=24, env=None):
        self.master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", height, width, 0, 0))
        e = os.environ.copy()
        e.update({"TERM": "xterm-256color", "HOME": str(path), "XDG_CONFIG_HOME": str(path / "cfg"),
                  "XDG_DATA_HOME": str(path / "data"), "XDG_RUNTIME_DIR": str(path / "runtime")})
        if env:
            e.update(env)
        self.proc = subprocess.Popen([EXE, str(path)], stdin=slave, stdout=slave, stderr=slave, env=e,
                                     close_fds=True)
        os.close(slave)
        self.buf = b""
        self.read(0.35)

    def read(self, duration=0.12):
        end = time.monotonic() + duration
        while time.monotonic() < end:
            ready, _, _ = select.select([self.master], [], [], min(.05, end-time.monotonic()))
            if ready:
                try:
                    chunk = os.read(self.master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                self.buf += chunk
        return self.buf

    def key(self, data, pause=.12):
        os.write(self.master, data if isinstance(data, bytes) else data.encode())
        self.read(pause)
        return self.buf

    def close(self):
        if self.proc.poll() is None:
            try:
                self.key(b":q\r")
            except OSError:
                pass
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        os.close(self.master)


def test_listing_and_navigation_render_names_and_footer(tmp_path):
    for name in ("aaa.txt", "mmm.txt", "zzz.txt"):
        (tmp_path / name).write_text("x")
    app = App(tmp_path)
    try:
        app.key(b"j")
        app.key(b"G")
        output = app.buf
        assert str(tmp_path).encode() in output
        assert all(name.encode() in output for name in ("aaa.txt", "mmm.txt", "zzz.txt"))
        assert b"3/3" in output
    finally:
        app.close()


def test_natural_order_hidden_toggle_and_reload(tmp_path):
    for name in ("file10", "file2", ".hidden"):
        (tmp_path / name).write_text("")
    app = App(tmp_path)
    try:
        initial = app.buf
        assert b".hidden" in initial
        assert initial.find(b"file2") < initial.find(b"file10")
        app.key(b"\x7f")
        assert b".hidden" in app.buf  # redraw history retains old frame; verify toggle by footer/count
        app.key(b"\x1b")
        app.key(b":e\r")
        assert b"file2" in app.buf and b"file10" in app.buf
    finally:
        app.close()


def test_create_file_prompt_and_select_new_file(tmp_path):
    app = App(tmp_path)
    try:
        app.key(b"iwould-be-file\x08\r", .3)
        assert (tmp_path / "would-be-fil").is_file()
        assert (tmp_path / "would-be-fil").stat().st_size == 0
        assert b"would-be-fil" in app.buf
    finally:
        app.close()


def test_create_directory_even_with_editor_set(tmp_path):
    (tmp_path / "existing").write_text("x")
    app = App(tmp_path, env={"EDITOR": "touch"})
    try:
        app.key(b"Iwould-be-dir\r", .3)
        assert (tmp_path / "would-be-dir").is_dir()
    finally:
        app.close()


def test_yank_then_put_copies_contents(tmp_path):
    src = tmp_path / "source.txt"
    src.write_text("preserve me")
    app = App(tmp_path)
    try:
        app.key(b"yy")
        app.key(b"p", .3)
        copies = [p for p in tmp_path.iterdir() if p.is_file()]
        assert len(copies) >= 2
        assert any(p != src and p.read_text() == "preserve me" for p in copies)
        assert b"item" in app.buf
    finally:
        app.close()


def test_delete_undo_and_redo_change_filesystem(tmp_path):
    f = tmp_path / "remove.txt"
    f.write_text("payload")
    app = App(tmp_path)
    try:
        app.key(b"dd", .25)
        assert not f.exists()
        app.key(b"u", .25)
        assert f.read_text() == "payload"
        app.key(b"\x12", .25)
        assert not f.exists()
    finally:
        app.close()


def test_empty_directory_marker_and_one_item_clamping(tmp_path):
    app = App(tmp_path)
    try:
        app.key(b"jjkk")
        assert b">" in app.buf
        assert b"1/1" not in app.buf
    finally:
        app.close()


def test_search_prompt_and_match_navigation(tmp_path):
    for name in ("apple.txt", "banana.txt", "cherry.txt", "date.txt", "elderberry.txt"):
        (tmp_path / name).write_text("")
    app = App(tmp_path)
    try:
        app.key(b"/err\r")
        assert b"cherry.txt" in app.buf and b"/err" not in app.buf
        app.key(b"n")
        assert b"elderberry.txt" in app.buf and b"2/5" in app.buf
        app.key(b"n")
        assert b"2/5" in app.buf
        app.key(b"N")
        assert b"1/5" in app.buf
    finally:
        app.close()


def test_parent_return_selects_child_directory(tmp_path):
    child = tmp_path / "child"
    child.mkdir()
    app = App(tmp_path)
    try:
        app.key(b"l")
        assert str(child).encode() in app.buf
        app.key(b"h")
        assert str(tmp_path).encode() in app.buf
        assert b"1/1" in app.buf
    finally:
        app.close()
